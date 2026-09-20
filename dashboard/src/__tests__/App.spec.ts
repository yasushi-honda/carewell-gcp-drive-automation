import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount, flushPromises, type DOMWrapper, type VueWrapper } from '@vue/test-utils';
import { createRouter, createMemoryHistory } from 'vue-router';
import { defineComponent, h, nextTick } from 'vue';
import App from '../App.vue';

// ヘッダーのモバイル対応（構造）の検証。
// happy-dom はレイアウトを計算できないため、ここではクラス構成と要素の有無だけを確認する。
// 実レイアウト（高さ・折り返し・44px・横スクロール）は docs/dashboard-mobile-measurement.md の手順で実測する。
// ≥lg で「従来どおり」に戻すクラス（lg:py-6 / lg:gap-* 等）の見た目の一致も、テストではなく実測で確認する。

// useAuth / useStudentSync をモック（管理者・ログイン済み・同期中の各状態をテストから注入する）
vi.mock('../composables/useAuth', async () => {
  const { ref } = await import('vue');
  const user = ref<{ email: string } | null>(null);
  const isAdmin = ref(false);
  const authReady = ref(true);
  return {
    useAuth: () => ({
      user,
      isAdmin,
      authReady,
      signInWithGoogle: vi.fn(),
      logout: vi.fn(),
    }),
    __state: { user, isAdmin, authReady },
  };
});

vi.mock('../composables/useStudentSync', async () => {
  const { ref } = await import('vue');
  const syncing = ref(false);
  const syncStudents = vi.fn();
  return {
    useStudentSync: () => ({ syncing, syncStudents }),
    __state: { syncing, syncStudents },
  };
});

const authState = (await import('../composables/useAuth') as any).__state;
const syncState = (await import('../composables/useStudentSync') as any).__state;

const LONG_EMAIL = 'a-very-long-address-for-layout-check@example.co.jp';

function createTestRouter() {
  const Page = defineComponent({ render: () => h('div') });
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: Page },
      { path: '/students', component: Page },
      { path: '/admin/duplicates', component: Page },
    ],
  });
}

// 共有モック(ref)の変更に、前のテストの wrapper が反応し続けないよう、afterEach で必ず破棄する
const mounted: VueWrapper[] = [];

async function mountApp() {
  const router = createTestRouter();
  await router.push('/');
  await router.isReady();
  const wrapper = mount(App, { global: { plugins: [router] } });
  mounted.push(wrapper);
  return wrapper;
}

function loginAs(email: string, isAdmin: boolean) {
  authState.user.value = { email };
  authState.isAdmin.value = isAdmin;
}

/**
 * header 内の全インタラクティブ要素が「<lg で44px、≥lg で従来の高さ」の契約（min-h-11 + lg:min-h-0）を持つこと。
 * 個別列挙ではなく走査するので、操作要素を追加したときの付け忘れも検知できる。
 */
function expectTouchTargetContract(header: DOMWrapper<Element>) {
  const controls = header.findAll('a, button');
  expect(controls.length).toBeGreaterThan(0);
  for (const control of controls) {
    const name = control.text() || control.attributes('aria-label') || '(no name)';
    expect(control.classes(), name).toEqual(expect.arrayContaining(['min-h-11', 'lg:min-h-0']));
  }
}

describe('App header (mobile-first)', () => {
  beforeEach(() => {
    authState.user.value = null;
    authState.isAdmin.value = false;
    authState.authReady.value = true;
    syncState.syncing.value = false;
    syncState.syncStudents.mockReset();
  });

  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount());
  });

  describe('未ログイン（匿名）', () => {
    it('should render the title, badge and two nav links', async () => {
      const wrapper = await mountApp();
      const header = wrapper.get('header');

      expect(header.get('h1').text()).toBe('Carewell Dashboard');
      expect(header.text()).toContain('令和8年度');
      const links = header.findAll('nav a');
      expect(links.map((a) => a.text())).toEqual(['クラス一覧', '受講生一覧']);
    });

    it('should stack in two rows below lg, switch to one row at lg and wrap only when it does not fit', async () => {
      const wrapper = await mountApp();
      const row = wrapper.get('header .flex.flex-col');

      expect(row.classes()).toEqual(
        expect.arrayContaining(['flex-col', 'lg:flex-row', 'lg:flex-wrap', 'lg:justify-between'])
      );
    });

    it('should scale the title down on small screens and keep text-3xl at lg', async () => {
      const wrapper = await mountApp();
      const h1 = wrapper.get('header h1');

      expect(h1.classes()).toEqual(expect.arrayContaining(['text-xl', 'sm:text-2xl', 'lg:text-3xl', 'whitespace-nowrap']));
    });

    it('should give every interactive element in the header a 44px touch target below lg', async () => {
      const wrapper = await mountApp();

      expectTouchTargetContract(wrapper.get('header'));
    });

    it('should not stretch the brand link across the whole row below lg', async () => {
      const wrapper = await mountApp();
      const brand = wrapper.get('header a[href="/"]');

      expect(brand.get('h1').text()).toBe('Carewell Dashboard');
      expect(brand.classes()).toEqual(expect.arrayContaining(['self-start', 'lg:self-auto']));
    });

    it('should keep the nav tabs at their content width via min-w-fit (real overflow is verified by measurement)', async () => {
      const wrapper = await mountApp();
      const nav = wrapper.get('header nav[aria-label="メインナビゲーション"]');

      expect(nav.classes()).toEqual(expect.arrayContaining(['flex-1', 'min-w-fit', 'lg:flex-none', 'lg:min-w-0']));
      for (const link of nav.findAll('a')) {
        expect(link.classes()).toEqual(expect.arrayContaining(['flex-1', 'lg:flex-none', 'whitespace-nowrap']));
      }
    });

    it('should show a shortened login label below sm while keeping the accessible name', async () => {
      const wrapper = await mountApp();
      const login = wrapper.get('header button[aria-label="管理者ログイン"]');

      const [short, full] = login.findAll('span');
      expect(short.text()).toBe('管理者');
      expect(short.classes()).toContain('sm:hidden');
      expect(short.attributes('aria-hidden')).toBe('true');
      expect(full.text()).toBe('管理者ログイン');
      expect(full.classes()).toEqual(expect.arrayContaining(['hidden', 'sm:inline']));
    });

    it('should not render admin-only controls', async () => {
      const wrapper = await mountApp();
      const header = wrapper.get('header');

      expect(header.text()).not.toContain('データ同期');
      expect(header.text()).not.toContain('重複一覧');
    });
  });

  describe('認証状態の確定前', () => {
    it('should show only the skeleton (no login or logout button) until auth is ready', async () => {
      authState.authReady.value = false;
      const wrapper = await mountApp();
      const header = wrapper.get('header');

      expect(header.find('.animate-pulse').exists()).toBe(true);
      expect(header.find('button[aria-label="管理者ログイン"]').exists()).toBe(false);
      expect(header.text()).not.toContain('ログアウト');
    });
  });

  describe('管理者ログイン済み', () => {
    beforeEach(() => {
      loginAs('admin@example.com', true);
    });

    it('should render admin controls', async () => {
      const wrapper = await mountApp();
      const header = wrapper.get('header');

      expect(header.findAll('button').some((b) => b.text().includes('データ同期'))).toBe(true);
      expect(header.findAll('nav a').some((a) => a.text() === '重複一覧')).toBe(true);
    });

    it('should give every interactive element in the header a 44px touch target below lg', async () => {
      const wrapper = await mountApp();

      expectTouchTargetContract(wrapper.get('header'));
    });

    it('should keep the sync button first in DOM order and move it last visually below lg only', async () => {
      const wrapper = await mountApp();
      const cluster = wrapper.get('header nav').element.parentElement!;

      // ≥lg は DOM 順のまま先頭（従来どおり）。<lg だけ order-last で視覚上の末尾へ
      expect(cluster.children[0].tagName).toBe('BUTTON');
      expect(cluster.children[0].textContent).toContain('データ同期');
      expect(cluster.children[1].tagName).toBe('NAV');
      const sync = wrapper.findAll('header button').find((b) => b.text().includes('データ同期'))!;
      expect(sync.classes()).toEqual(expect.arrayContaining(['order-last', 'lg:order-none']));
    });

    it('should let the control cluster wrap below lg so nothing overflows', async () => {
      const wrapper = await mountApp();
      const cluster = wrapper.get('header nav').element.parentElement!;

      expect(cluster.classList.contains('flex-wrap')).toBe(true);
      expect(cluster.classList.contains('lg:flex-nowrap')).toBe(true);
    });

    it('should truncate only the e-mail on small screens, expose it via title, and not show 「権限なし」', async () => {
      loginAs(LONG_EMAIL, true);
      const wrapper = await mountApp();
      const header = wrapper.get('header');

      // 省略（truncate）するのはメールだけ。全体の幅は <lg で上限を設け、≥lg は従来どおり無制限
      const email = header.findAll('span').find((s) => s.classes().includes('truncate') && s.text() === LONG_EMAIL);
      expect(email).toBeDefined();
      expect(email!.attributes('title')).toBe(LONG_EMAIL); // 省略されても全文を確認できる
      const emailWrapper = email!.element.parentElement!;
      expect(emailWrapper.classList.contains('max-w-[12rem]')).toBe(true);
      expect(emailWrapper.classList.contains('lg:max-w-none')).toBe(true);
      expect(header.text()).not.toContain('権限なし');
    });

    it('should show the syncing state and disable the sync button', async () => {
      syncState.syncing.value = true;
      const wrapper = await mountApp();

      const sync = wrapper.findAll('header button').find((b) => b.text().includes('同期中'));
      expect(sync).toBeDefined();
      expect(sync!.attributes('disabled')).toBeDefined();
    });
  });

  describe('権限なし（ログイン済み・非管理者）', () => {
    beforeEach(() => {
      loginAs(LONG_EMAIL, false);
    });

    it('should keep the 「権限なし」 label visible (not truncated) even with a long e-mail', async () => {
      const wrapper = await mountApp();
      const header = wrapper.get('header');

      const label = header.findAll('span').find((s) => s.text() === '（権限なし）');
      expect(label).toBeDefined();
      // 縮まず改行もしない（省略されるのはメール側のみ）
      expect(label!.classes()).toEqual(expect.arrayContaining(['shrink-0', 'whitespace-nowrap']));
      expect(label!.classes()).not.toContain('truncate');
      // 省略対象のメールとは別要素
      const email = header.findAll('span').find((s) => s.classes().includes('truncate'));
      expect(email).toBeDefined();
      expect(email!.text()).not.toContain('権限なし');
    });

    it('should not render admin-only controls', async () => {
      const wrapper = await mountApp();
      const header = wrapper.get('header');

      expect(header.text()).not.toContain('データ同期');
      expect(header.text()).not.toContain('重複一覧');
    });

    it('should give every interactive element in the header a 44px touch target below lg', async () => {
      const wrapper = await mountApp();

      expectTouchTargetContract(wrapper.get('header'));
    });
  });

  describe('同期結果のトースト', () => {
    beforeEach(() => {
      loginAs('admin@example.com', true);
    });

    async function clickSync(wrapper: VueWrapper) {
      const sync = wrapper.findAll('header button').find((b) => b.text().includes('データ同期'))!;
      await sync.trigger('click');
      await flushPromises();
      await nextTick();
    }

    it('should span the viewport width below sm and fall back to the right-aligned card from sm', async () => {
      syncState.syncStudents.mockResolvedValue({ status: 'success', classes: [{ synced: 3 }] });
      const wrapper = await mountApp();
      await clickSync(wrapper);

      const toast = wrapper.get('.fixed');
      expect(toast.text()).toContain('同期完了');
      expect(toast.classes()).toEqual(
        expect.arrayContaining(['left-4', 'right-4', 'sm:left-auto', 'sm:max-w-sm', 'sm:w-full'])
      );
    });

    it('should show an error toast when the sync request fails', async () => {
      syncState.syncStudents.mockRejectedValue(new Error('boom'));
      const wrapper = await mountApp();
      await clickSync(wrapper);

      const toast = wrapper.get('.fixed');
      expect(toast.text()).toContain('同期エラー');
      expect(toast.text()).toContain('boom');
      expect(toast.classes()).toContain('bg-red-50');
    });

    it('should dismiss the toast with the close button', async () => {
      syncState.syncStudents.mockResolvedValue({ status: 'success', classes: [{ synced: 1 }] });
      const wrapper = await mountApp();
      await clickSync(wrapper);
      expect(wrapper.find('.fixed').exists()).toBe(true);

      await wrapper.get('.fixed button').trigger('click');
      await nextTick();

      expect(wrapper.find('.fixed').exists()).toBe(false);
    });
  });
});
