import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount, type VueWrapper } from '@vue/test-utils';
import { createRouter, createMemoryHistory } from 'vue-router';
import { defineComponent, h, nextTick } from 'vue';
import GroupStudentsView from '../GroupStudentsView.vue';
import { installViewport, resizeTo, resetViewport } from '../../test/viewport';
import { linkedStudentIds } from '../../test/dom';
import type { Student } from '../../types/models';

// グループ内の受講生一覧: <1024px はカード、≥1024px は従来の表（表の最小幅は約812px）。
// 受講者番号・ふりがなの並べ替えは「昇順 ⇄ 降順」の2状態（受講生一覧の3状態とは別仕様）。
// レイアウトは happy-dom では計算できないため、docs/dashboard-mobile-measurement.md の手順で実測する。

vi.mock('../../composables/useStudents', async () => {
  const { ref } = await import('vue');
  const students = ref<Student[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);
  return {
    useStudents: () => ({ students, loading, error }),
    __state: { students, loading, error },
  };
});

const studentsState = (await import('../../composables/useStudents') as any).__state;

function student(id: string, overrides: Partial<Student> = {}): Student {
  return {
    student_id: id,
    name: `${id}の氏名`,
    furigana: 'ふりがな',
    group: 'A',
    company: '',
    office: '',
    service_type: '通所系',
    serial_number: 1,
    student_number: 'A001',
    class_name: 'No1',
    status: 'active',
    ...overrides,
  };
}

// 元の並び（N03, N01, N02）は、ふりがな昇順・受講者番号昇順のどちらとも一致しない。
// N09 は別グループ、N08 は別クラスなので、この画面には出ない。
const DATA: Student[] = [
  student('N03', { furigana: 'う', student_number: 'A002' }),
  student('N01', { furigana: 'あ', student_number: 'A003' }),
  student('N02', { furigana: 'い', student_number: 'A001' }),
  student('N09', { furigana: 'え', student_number: 'A004', group: 'B' }),
  student('N08', { furigana: 'お', student_number: 'A005', class_name: 'No2' }),
];

const mounted: VueWrapper[] = [];

async function mountView(width: number) {
  installViewport(width);
  const Stub = defineComponent({ render: () => h('div') });
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: Stub },
      { path: '/class/:className', component: Stub },
      { path: '/class/:className/task/:taskId', component: Stub },
      { path: '/class/:className/task/:taskId/groups', component: Stub },
      { path: '/class/:className/task/:taskId/group/:groupName/students', component: GroupStudentsView },
      { path: '/students/:id', component: Stub },
    ],
  });
  // className が短縮名の表に無ければ、そのまま比較に使われる（'No1'）
  await router.push('/class/No1/task/task1/group/A/students');
  await router.isReady();
  const wrapper = mount(GroupStudentsView, { global: { plugins: [router] } });
  mounted.push(wrapper);
  return wrapper;
}

function shownIds(wrapper: VueWrapper) {
  return linkedStudentIds(wrapper.element);
}

const cards = (wrapper: VueWrapper) => wrapper.find('ul[aria-label="受講生一覧"]');
const sortGroup = (wrapper: VueWrapper) => wrapper.find('[role="group"][aria-label="ソートオプション"]');

describe('GroupStudentsView (responsive table / cards)', () => {
  beforeEach(() => {
    studentsState.students.value = DATA;
    studentsState.loading.value = false;
    studentsState.error.value = null;
  });

  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount());
    resetViewport();
  });

  describe('表示の切替（単一描画）', () => {
    it('should render cards (and no table) on a phone', async () => {
      const wrapper = await mountView(390);

      expect(wrapper.find('table').exists()).toBe(false);
      expect(cards(wrapper).exists()).toBe(true);
      expect(sortGroup(wrapper).exists()).toBe(true);
    });

    it('should still render cards just below 1024px', async () => {
      const wrapper = await mountView(1023);

      expect(wrapper.find('table').exists()).toBe(false);
      expect(cards(wrapper).exists()).toBe(true);
    });

    it('should render the table (and no cards or sort buttons) from 1024px', async () => {
      const wrapper = await mountView(1024);

      expect(wrapper.find('table').exists()).toBe(true);
      expect(wrapper.findAll('tbody tr')).toHaveLength(3);
      expect(cards(wrapper).exists()).toBe(false);
      expect(sortGroup(wrapper).exists()).toBe(false);
    });

    it('should show only the students of this class and group, exactly once each', async () => {
      const compact = await mountView(390);
      expect(shownIds(compact).sort()).toEqual(['N01', 'N02', 'N03']);

      const wide = await mountView(1280);
      expect(shownIds(wide).sort()).toEqual(['N01', 'N02', 'N03']);
    });

    it('should not repeat the class and group on each card (they are the same for everyone here)', async () => {
      const wrapper = await mountView(390);

      const list = cards(wrapper);
      expect(list.text()).not.toContain('クラス');
      expect(list.text()).not.toContain('グループ');
    });
  });

  describe('検索', () => {
    it('should filter the cards by the search box', async () => {
      const wrapper = await mountView(390);

      await wrapper.get('#search-query').setValue('う');

      expect(shownIds(wrapper)).toEqual(['N03']);
    });

    it('should show the empty state in both layouts when nothing matches', async () => {
      const compact = await mountView(390);
      await compact.get('#search-query').setValue('該当なし');
      expect(compact.text()).toContain('該当する受講生が見つかりませんでした');

      const wide = await mountView(1280);
      await wide.get('#search-query').setValue('該当なし');
      expect(wide.text()).toContain('該当する受講生が見つかりませんでした');
    });

    it('should give the search box a 44px touch target below lg', async () => {
      const wrapper = await mountView(390);

      expect(wrapper.get('#search-query').classes()).toEqual(expect.arrayContaining(['min-h-11', 'lg:min-h-0']));
    });
  });

  describe('並べ替え（カード表示。昇順 ⇄ 降順の2状態）', () => {
    it('should keep the original order until a sort is chosen', async () => {
      const wrapper = await mountView(390);

      expect(shownIds(wrapper)).toEqual(['N03', 'N01', 'N02']);
      for (const button of sortGroup(wrapper).findAll('button')) {
        expect(button.attributes('aria-pressed')).toBe('false');
      }
    });

    it('should toggle furigana between ascending and descending (it never returns to unsorted)', async () => {
      const wrapper = await mountView(390);
      const furigana = () => sortGroup(wrapper).findAll('button')[0];

      await furigana().trigger('click');
      expect(shownIds(wrapper)).toEqual(['N01', 'N02', 'N03']);

      await furigana().trigger('click');
      expect(shownIds(wrapper)).toEqual(['N03', 'N02', 'N01']);

      await furigana().trigger('click');
      expect(shownIds(wrapper)).toEqual(['N01', 'N02', 'N03']);
      expect(furigana().attributes('aria-pressed')).toBe('true');
    });

    it('should toggle student number between ascending and descending', async () => {
      const wrapper = await mountView(390);
      const serial = () => sortGroup(wrapper).findAll('button')[1];

      await serial().trigger('click');
      expect(shownIds(wrapper)).toEqual(['N02', 'N03', 'N01']);

      await serial().trigger('click');
      expect(shownIds(wrapper)).toEqual(['N01', 'N03', 'N02']);
    });

    it('should let only one sort key be active at a time', async () => {
      const wrapper = await mountView(390);
      const [furigana, serial] = sortGroup(wrapper).findAll('button');

      await furigana.trigger('click');
      await serial.trigger('click');

      expect(serial.attributes('aria-pressed')).toBe('true');
      expect(furigana.attributes('aria-pressed')).toBe('false');
    });

    it('should switch from student number to furigana ascending (only one sort key stays active)', async () => {
      const wrapper = await mountView(390);
      const [furigana, serial] = sortGroup(wrapper).findAll('button');

      await serial.trigger('click'); // 受講者番号昇順
      await serial.trigger('click'); // 受講者番号降順
      await furigana.trigger('click');

      expect(shownIds(wrapper)).toEqual(['N01', 'N02', 'N03']);
      expect(furigana.attributes('aria-pressed')).toBe('true');
      expect(serial.attributes('aria-pressed')).toBe('false');
    });
  });

  describe('画面幅の変化（回転・リサイズ）', () => {
    it('should switch from cards to the table across 1024px and keep search and sort state', async () => {
      const wrapper = await mountView(390);
      await wrapper.get('#search-query').setValue('氏名');
      await sortGroup(wrapper).findAll('button')[0].trigger('click'); // ふりがな昇順
      expect(shownIds(wrapper)).toEqual(['N01', 'N02', 'N03']);

      resizeTo(1280);
      await nextTick();

      expect(wrapper.find('table').exists()).toBe(true);
      expect(cards(wrapper).exists()).toBe(false);
      expect((wrapper.get('#search-query').element as HTMLInputElement).value).toBe('氏名');
      expect(shownIds(wrapper)).toEqual(['N01', 'N02', 'N03']);
    });
  });

  describe('読み込み・エラー', () => {
    it('should show neither table nor cards while loading', async () => {
      studentsState.loading.value = true;
      const wrapper = await mountView(390);

      expect(wrapper.find('table').exists()).toBe(false);
      expect(cards(wrapper).exists()).toBe(false);
    });

    it('should show the error instead of the list', async () => {
      studentsState.error.value = '取得に失敗しました';
      const wrapper = await mountView(390);

      expect(wrapper.text()).toContain('取得に失敗しました');
      expect(cards(wrapper).exists()).toBe(false);
    });
  });
});
