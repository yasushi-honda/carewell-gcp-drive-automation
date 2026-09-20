import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount, type VueWrapper } from '@vue/test-utils';
import { createRouter, createMemoryHistory } from 'vue-router';
import { defineComponent, h, nextTick } from 'vue';
import StudentsView from '../StudentsView.vue';
import { installViewport, resizeTo, resetViewport } from '../../test/viewport';
import { linkedStudentIds } from '../../test/dom';
import type { Student } from '../../types/models';

// 受講生一覧: <1280px はカード、≥1280px は従来の表（どちらか一方だけ描画する）。
// 表の最小幅が約1012pxで、1024〜1279pxでも横スクロールが残るため 1280px を境にしている。
// レイアウト（横スクロールの有無など）は happy-dom では計算できないため、
// docs/dashboard-mobile-measurement.md の手順で実測する。

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

// 元の並び（N03, N01, N02）は、ふりがな昇順・受講者番号昇順のどちらとも一致しない
const DATA: Student[] = [
  student('N03', { furigana: 'う', student_number: 'A002', class_name: 'No1' }),
  student('N01', { furigana: 'あ', student_number: 'A003', class_name: 'No1' }),
  student('N02', { furigana: 'い', student_number: 'A001', class_name: 'No2' }),
];

const mounted: VueWrapper[] = [];

async function mountView(width: number) {
  installViewport(width);
  const Stub = defineComponent({ render: () => h('div') });
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/students', component: StudentsView },
      { path: '/students/:id', component: Stub },
    ],
  });
  await router.push('/students');
  await router.isReady();
  const wrapper = mount(StudentsView, { global: { plugins: [router] } });
  mounted.push(wrapper);
  return wrapper;
}

/** 表示中の受講生（カード or 表の行）の日介番号を、表示順に返す */
function shownIds(wrapper: VueWrapper) {
  return linkedStudentIds(wrapper.element);
}

const cards = (wrapper: VueWrapper) => wrapper.find('ul[aria-label="受講生一覧"]');
const sortGroup = (wrapper: VueWrapper) => wrapper.find('[role="group"][aria-label="ソートオプション"]');

describe('StudentsView (responsive table / cards)', () => {
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

    it('should still render cards just below 1280px (the table would need horizontal scrolling)', async () => {
      const wrapper = await mountView(1279);

      expect(wrapper.find('table').exists()).toBe(false);
      expect(cards(wrapper).exists()).toBe(true);
    });

    it('should render the table (and no cards or sort buttons) from 1280px', async () => {
      const wrapper = await mountView(1280);

      expect(wrapper.find('table').exists()).toBe(true);
      expect(wrapper.findAll('tbody tr')).toHaveLength(3);
      expect(cards(wrapper).exists()).toBe(false);
      expect(sortGroup(wrapper).exists()).toBe(false);
    });

    it('should render each student exactly once in either layout (no duplicated DOM)', async () => {
      const compact = await mountView(390);
      expect(shownIds(compact)).toHaveLength(DATA.length);

      const wide = await mountView(1440);
      expect(shownIds(wide)).toHaveLength(DATA.length);
    });

    it('should link every card to the student detail page', async () => {
      const wrapper = await mountView(390);

      expect(shownIds(wrapper).sort()).toEqual(['N01', 'N02', 'N03']);
    });
  });

  describe('検索・フィルタ', () => {
    it('should filter the cards by the search box', async () => {
      const wrapper = await mountView(390);

      await wrapper.get('#search-query').setValue('う');

      expect(shownIds(wrapper)).toEqual(['N03']);
    });

    it('should filter the cards by class', async () => {
      const wrapper = await mountView(390);

      await wrapper.get('#class-filter').setValue('No1');

      expect(shownIds(wrapper).sort()).toEqual(['N01', 'N03']);
    });

    it('should show the empty state in both layouts when nothing matches', async () => {
      const compact = await mountView(390);
      await compact.get('#search-query').setValue('該当なし');
      expect(compact.text()).toContain('該当する受講生が見つかりませんでした');
      expect(shownIds(compact)).toHaveLength(0);

      const wide = await mountView(1440);
      await wide.get('#search-query').setValue('該当なし');
      expect(wide.text()).toContain('該当する受講生が見つかりませんでした');
    });

    it('should give the search box and filters a 44px touch target while cards are shown (below xl)', async () => {
      const wrapper = await mountView(390);

      for (const selector of ['#search-query', '#class-filter', '#group-filter']) {
        expect(wrapper.get(selector).classes(), selector).toEqual(expect.arrayContaining(['min-h-11', 'xl:min-h-0']));
      }
    });
  });

  describe('並べ替え（カード表示）', () => {
    it('should keep the original order until a sort is chosen', async () => {
      const wrapper = await mountView(390);

      expect(shownIds(wrapper)).toEqual(['N03', 'N01', 'N02']);
    });

    it('should cycle furigana sort: none → ascending → descending → none', async () => {
      const wrapper = await mountView(390);
      const furigana = () => sortGroup(wrapper).findAll('button')[0];

      await furigana().trigger('click');
      expect(shownIds(wrapper)).toEqual(['N01', 'N02', 'N03']);
      expect(furigana().attributes('aria-pressed')).toBe('true');

      await furigana().trigger('click');
      expect(shownIds(wrapper)).toEqual(['N03', 'N02', 'N01']);
      expect(furigana().attributes('aria-pressed')).toBe('true');

      await furigana().trigger('click');
      expect(shownIds(wrapper)).toEqual(['N03', 'N01', 'N02']);
      expect(furigana().attributes('aria-pressed')).toBe('false');
    });

    it('should cycle student number sort: ascending → descending → none', async () => {
      const wrapper = await mountView(390);
      const serial = () => sortGroup(wrapper).findAll('button')[1];

      await serial().trigger('click');
      expect(shownIds(wrapper)).toEqual(['N02', 'N03', 'N01']);

      await serial().trigger('click');
      expect(shownIds(wrapper)).toEqual(['N01', 'N03', 'N02']);

      await serial().trigger('click');
      expect(shownIds(wrapper)).toEqual(['N03', 'N01', 'N02']);
      expect(serial().attributes('aria-pressed')).toBe('false');
    });

    it('should compare the number part of student numbers numerically and put an empty one first', async () => {
      // A9 < A10 は数値比較のときだけ成り立つ（文字列比較なら A10 が先）。空の番号は昇順で先頭
      studentsState.students.value = [
        student('N01', { student_number: 'A10' }),
        student('N02', { student_number: '' }),
        student('N03', { student_number: 'A9' }),
      ];
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
      expect(shownIds(wrapper)).toEqual(['N02', 'N03', 'N01']);
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
    it('should switch from cards to the table across 1280px and keep filter and sort state', async () => {
      const wrapper = await mountView(390);
      await wrapper.get('#class-filter').setValue('No1');
      await sortGroup(wrapper).findAll('button')[0].trigger('click'); // ふりがな昇順
      expect(shownIds(wrapper)).toEqual(['N01', 'N03']);

      resizeTo(1440);
      await nextTick();

      expect(wrapper.find('table').exists()).toBe(true);
      expect(cards(wrapper).exists()).toBe(false);
      expect((wrapper.get('#class-filter').element as HTMLSelectElement).value).toBe('No1');
      expect(shownIds(wrapper)).toEqual(['N01', 'N03']);
    });

    it('should switch from the table back to cards when the screen narrows', async () => {
      const wrapper = await mountView(1440);
      expect(wrapper.find('table').exists()).toBe(true);

      resizeTo(800);
      await nextTick();

      expect(wrapper.find('table').exists()).toBe(false);
      expect(cards(wrapper).exists()).toBe(true);
      expect(shownIds(wrapper)).toHaveLength(DATA.length);
    });
  });

  describe('読み込み・エラー', () => {
    it('should show neither table nor cards while loading', async () => {
      studentsState.loading.value = true;
      const wrapper = await mountView(390);

      expect(wrapper.find('table').exists()).toBe(false);
      expect(cards(wrapper).exists()).toBe(false);
      expect(wrapper.find('[role="status"]').exists()).toBe(true);
    });

    it('should show the error instead of the list', async () => {
      studentsState.error.value = '取得に失敗しました';
      const wrapper = await mountView(390);

      expect(wrapper.text()).toContain('取得に失敗しました');
      expect(cards(wrapper).exists()).toBe(false);
    });
  });
});
