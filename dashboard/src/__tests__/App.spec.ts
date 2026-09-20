import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createRouter, createMemoryHistory } from 'vue-router';
import { nextTick } from 'vue';
import App from '../App.vue';

// ヘッダーのモバイル対応（構造）の検証。
// happy-dom はレイアウトを計算できないため、ここではクラス構成と要素の有無だけを確認する。
// 実レイアウト（高さ・折り返し・44px）は docs/dashboard-mobile-measurement.md の手順で実測する。

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

function createTestRouter() {
  const Page = { template: '<div />' };
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: Page },
      { path: '/students', component: Page },
      { path: '/admin/duplicates', component: Page },
    ],
  });
}

async function mountApp() {
  const router = createTestRouter();
  await router.push('/');
  await router.isReady();
  return mount(App, { global: { plugins: [router] } });
}

describe('App header (mobile-first)', () => {
  beforeEach(() => {
    authState.user.value = null;
    authState.isAdmin.value = false;
    authState.authReady.value = true;
    syncState.syncing.value = false;
    syncState.syncStudents.mockReset();
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

    it('should stack in two rows below lg and switch to one row at lg', async () => {
      const wrapper = await mountApp();
      const row = wrapper.get('header .flex.flex-col');

      expect(row.classes()).toEqual(expect.arrayContaining(['flex-col', 'lg:flex-row', 'lg:justify-between']));
    });

    it('should scale the title down on small screens and keep text-3xl at lg', async () => {
      const wrapper = await mountApp();
      const h1 = wrapper.get('header h1');

      expect(h1.classes()).toEqual(expect.arrayContaining(['text-xl', 'sm:text-2xl', 'lg:text-3xl', 'whitespace-nowrap']));
    });

    it('should give every nav link a 44px touch target below lg and release it at lg', async () => {
      const wrapper = await mountApp();
      const links = wrapper.findAll('header nav a');

      expect(links).toHaveLength(2);
      for (const link of links) {
        expect(link.classes()).toEqual(expect.arrayContaining(['min-h-11', 'lg:min-h-0', 'whitespace-nowrap']));
      }
    });

    it('should make the brand link a 44px touch target below lg', async () => {
      const wrapper = await mountApp();
      const brand = wrapper.get('header a[href="/"]');

      expect(brand.get('h1').text()).toBe('Carewell Dashboard');
      expect(brand.classes()).toEqual(expect.arrayContaining(['min-h-11', 'lg:min-h-0']));
    });

    it('should never shrink the nav tabs below their content width (no horizontal overflow)', async () => {
      const wrapper = await mountApp();
      const nav = wrapper.get('header nav');

      // 2件でも3件（管理者の重複一覧あり）でも、タブが内容幅より縮まず横にはみ出さない
      expect(nav.classes()).toEqual(expect.arrayContaining(['flex-1', 'min-w-fit', 'lg:flex-none', 'lg:min-w-0']));
    });

    it('should show a shortened login label below sm while keeping the accessible name', async () => {
      const wrapper = await mountApp();
      const login = wrapper.get('header button[aria-label="管理者ログイン"]');

      expect(login.classes()).toEqual(expect.arrayContaining(['min-h-11', 'lg:min-h-0']));
      const [short, full] = login.findAll('span');
      expect(short.text()).toBe('管理者');
      expect(short.classes()).toContain('sm:hidden');
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

  describe('管理者ログイン済み', () => {
    beforeEach(() => {
      authState.user.value = { email: 'admin@example.com' };
      authState.isAdmin.value = true;
    });

    it('should render admin controls with 44px touch targets below lg', async () => {
      const wrapper = await mountApp();
      const header = wrapper.get('header');

      const sync = header.findAll('button').find((b) => b.text().includes('データ同期'));
      expect(sync).toBeDefined();
      expect(sync!.classes()).toEqual(expect.arrayContaining(['min-h-11', 'lg:min-h-0']));
      // <lg は行を詰めやすいよう末尾へ、≥lg は従来どおり先頭（DOM順）
      expect(sync!.classes()).toEqual(expect.arrayContaining(['order-last', 'lg:order-none']));

      const duplicates = header.findAll('nav a').find((a) => a.text() === '重複一覧');
      expect(duplicates).toBeDefined();
      expect(duplicates!.classes()).toEqual(expect.arrayContaining(['min-h-11', 'lg:min-h-0']));
    });

    it('should let the control cluster wrap below lg so nothing overflows', async () => {
      const wrapper = await mountApp();
      const cluster = wrapper.get('header nav').element.parentElement!;

      expect(cluster.classList.contains('flex-wrap')).toBe(true);
      expect(cluster.classList.contains('lg:flex-nowrap')).toBe(true);
    });

    it('should truncate a long e-mail on small screens and keep a 44px logout target', async () => {
      authState.user.value = { email: 'a-very-long-address-for-layout-check@example.co.jp' };
      const wrapper = await mountApp();
      const header = wrapper.get('header');

      // 省略（truncate）するのはメールだけ。全体の幅は <lg で上限を設け、≥lg は従来どおり無制限
      const email = header.findAll('span').find((s) => s.classes().includes('truncate') && s.text().includes('a-very-long-address'));
      expect(email).toBeDefined();
      const wrapper_ = email!.element.parentElement!;
      expect(wrapper_.classList.contains('max-w-[12rem]')).toBe(true);
      expect(wrapper_.classList.contains('lg:max-w-none')).toBe(true);

      const logout = header.findAll('button').find((b) => b.text() === 'ログアウト');
      expect(logout).toBeDefined();
      expect(logout!.classes()).toEqual(expect.arrayContaining(['min-h-11', 'lg:min-h-0']));
    });

    it('should keep the 「権限なし」 label visible (not truncated) for a non-admin user with a long e-mail', async () => {
      authState.user.value = { email: 'a-very-long-address-for-layout-check@example.co.jp' };
      authState.isAdmin.value = false;
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

    it('should show the syncing state and disable the sync button', async () => {
      syncState.syncing.value = true;
      const wrapper = await mountApp();

      const sync = wrapper.findAll('header button').find((b) => b.text().includes('同期中'));
      expect(sync).toBeDefined();
      expect(sync!.attributes('disabled')).toBeDefined();
    });
  });

  describe('同期結果のトースト', () => {
    it('should span the viewport width below sm and fall back to the right-aligned card from sm', async () => {
      authState.user.value = { email: 'admin@example.com' };
      authState.isAdmin.value = true;
      syncState.syncStudents.mockResolvedValue({ status: 'success', classes: [{ synced: 3 }] });

      const wrapper = await mountApp();
      const sync = wrapper.findAll('header button').find((b) => b.text().includes('データ同期'))!;
      await sync.trigger('click');
      await flushPromises();
      await nextTick();

      const toast = wrapper.get('.fixed');
      expect(toast.text()).toContain('同期完了');
      expect(toast.classes()).toEqual(
        expect.arrayContaining(['left-4', 'right-4', 'sm:left-auto', 'sm:max-w-sm', 'sm:w-full'])
      );
    });
  });
});
