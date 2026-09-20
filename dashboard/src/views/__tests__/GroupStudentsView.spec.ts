import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils';
import { createRouter, createMemoryHistory } from 'vue-router';
import { defineComponent, h, nextTick } from 'vue';
import GroupStudentsView from '../GroupStudentsView.vue';
import { installViewport, resizeTo, resetViewport } from '../../test/viewport';
import { linkedStudentIds } from '../../test/dom';
import type { Student } from '../../types/models';
import type { SubmissionFile } from '../../composables/useGroupStats';
import * as useFirestore from '../../composables/useFirestore';

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

// 提出状況（この課題の提出ファイル）は Firestore から取る。既定は「提出なし」
vi.mock('../../composables/useFirestore', () => ({ getDocuments: vi.fn() }));
vi.mock('../../config/firebase', () => ({ getDb: vi.fn(() => ({})) }));

const getDocuments = vi.mocked(useFirestore.getDocuments);

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
    getDocuments.mockReset();
    getDocuments.mockResolvedValue([]);
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount());
    resetViewport();
    vi.restoreAllMocks();
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

  describe('受講者番号の列（表・1024px 以上）', () => {
    const header = (wrapper: VueWrapper) =>
      wrapper.findAll('th').find((th) => th.text().includes('受講者番号'))!;
    const numberCells = (wrapper: VueWrapper) =>
      wrapper.findAll('tbody tr').map((row) => row.findAll('td')[0].text());

    it('should show the student number column and its values in the table', async () => {
      const wrapper = await mountView(1024);

      expect(header(wrapper).exists()).toBe(true);
      expect(wrapper.text()).not.toContain('通し番号');
      expect(numberCells(wrapper)).toEqual(['A002', 'A003', 'A001']);
    });

    it('should show "-" in the cell of a student without a student number', async () => {
      studentsState.students.value = [student('N01', { student_number: '' })];
      const wrapper = await mountView(1024);

      expect(numberCells(wrapper)).toEqual(['-']);
    });

    it('should sort by the header and show the direction indicator', async () => {
      const wrapper = await mountView(1024);
      expect(header(wrapper).text()).toContain('⇅');

      await header(wrapper).trigger('click');
      expect(header(wrapper).text()).toContain('▲');
      expect(shownIds(wrapper)).toEqual(['N02', 'N03', 'N01']);

      await header(wrapper).trigger('click');
      expect(header(wrapper).text()).toContain('▼');
      expect(shownIds(wrapper)).toEqual(['N01', 'N03', 'N02']);
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
  describe('提出状況（誰が提出済みかを一覧で分かるようにする）', () => {
    const file = (studentId: unknown, passStatus: unknown, submitDate = '2026/09/20 10:00:00'): SubmissionFile => ({
      student_id: studentId,
      submit_date: submitDate,
      metadata: { pass_status: passStatus },
    });

    // グループ A（N03, N01, N02）: N01=合格（不合格→合格の再提出）/ N03=採点待ち / N02=未提出。N09 は別グループ
    const FILES = [
      file('N01', '不合格', '2026/09/19 09:00:00'),
      file('N01', '合格', '2026/09/20 09:00:00'),
      file('N03', ''),
      file('N09', '合格'),
    ];

    const statuses = (wrapper: VueWrapper) => wrapper.findAll('[data-status]').map((b) => b.attributes('data-status'));
    const chip = (wrapper: VueWrapper, key: string) => wrapper.get(`[data-chip="${key}"]`);
    const chipCounts = (wrapper: VueWrapper) =>
      Object.fromEntries(
        wrapper.findAll('[data-chip]').map((c) => [c.attributes('data-chip'), c.get('span').text()])
      );

    it('should read the files of this class and task', async () => {
      await mountView(1280);
      await flushPromises();

      expect(getDocuments).toHaveBeenCalledWith('submissions', 'No1', 'tasks', 'task1', 'files');
    });

    it('should show each student\'s status in the table (in the row order: N03, N01, N02)', async () => {
      getDocuments.mockResolvedValue(FILES);
      const wrapper = await mountView(1280);
      await flushPromises();

      expect(wrapper.findAll('th').some((th) => th.text() === '提出状況')).toBe(true);
      expect(statuses(wrapper)).toEqual(['pending', 'passed', 'not_submitted']);
    });

    it('should show the latest submit time and the number of submissions for a resubmission', async () => {
      getDocuments.mockResolvedValue(FILES);
      const wrapper = await mountView(1280);
      await flushPromises();

      const n01Row = wrapper.findAll('tbody tr')[1];
      expect(n01Row.text()).toContain('合格');
      expect(n01Row.text()).toContain('最終提出 2026/09/20 09:00');
      expect(n01Row.text()).toContain('（2回）');
    });

    it('should show each student\'s status on the cards too', async () => {
      getDocuments.mockResolvedValue(FILES);
      const wrapper = await mountView(390);
      await flushPromises();

      expect(wrapper.find('table').exists()).toBe(false);
      expect(statuses(wrapper)).toEqual(['pending', 'passed', 'not_submitted']);
    });

    it('should count only this group in the chips, and never count another group\'s submissions', async () => {
      getDocuments.mockResolvedValue(FILES);
      const wrapper = await mountView(1280);
      await flushPromises();

      expect(chipCounts(wrapper)).toEqual({ all: '3', not_submitted: '1', passed: '1', pending: '1', failed: '0' });
    });

    it('should treat everyone as 未提出 when the task has no files yet (a real zero, not an error)', async () => {
      getDocuments.mockResolvedValue([]);
      const wrapper = await mountView(1280);
      await flushPromises();

      expect(statuses(wrapper)).toEqual(['not_submitted', 'not_submitted', 'not_submitted']);
      expect(chipCounts(wrapper)).toMatchObject({ all: '3', not_submitted: '3' });
      expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    });

    it('should narrow the list to one status by the chips, and back to everyone', async () => {
      getDocuments.mockResolvedValue(FILES);
      const wrapper = await mountView(1280);
      await flushPromises();
      expect(chip(wrapper, 'all').attributes('aria-pressed')).toBe('true');

      await chip(wrapper, 'not_submitted').trigger('click');
      expect(shownIds(wrapper)).toEqual(['N02']);
      expect(chip(wrapper, 'not_submitted').attributes('aria-pressed')).toBe('true');
      expect(chip(wrapper, 'all').attributes('aria-pressed')).toBe('false');

      await chip(wrapper, 'passed').trigger('click');
      expect(shownIds(wrapper)).toEqual(['N01']);

      await chip(wrapper, 'all').trigger('click');
      expect(shownIds(wrapper).sort()).toEqual(['N01', 'N02', 'N03']);
    });

    it('should combine the status filter with the search, and keep the chip counts for the whole group', async () => {
      getDocuments.mockResolvedValue(FILES);
      const wrapper = await mountView(390);
      await flushPromises();

      await chip(wrapper, 'passed').trigger('click');
      await wrapper.get('#search-query').setValue('N02');

      expect(shownIds(wrapper)).toEqual([]);
      expect(wrapper.text()).toContain('該当する受講生が見つかりませんでした');
      expect(chipCounts(wrapper)).toMatchObject({ all: '3', passed: '1' });
    });

    it('should show the empty state for a status nobody has (不合格 0)', async () => {
      getDocuments.mockResolvedValue(FILES);
      const wrapper = await mountView(1280);
      await flushPromises();

      await chip(wrapper, 'failed').trigger('click');

      expect(shownIds(wrapper)).toEqual([]);
      expect(wrapper.text()).toContain('該当する受講生が見つかりませんでした');
    });

    it('should keep the chips and status column in the same place while loading (skeletons), without claiming 未提出', async () => {
      getDocuments.mockReturnValue(new Promise(() => {}) as never);
      const wrapper = await mountView(1280);
      await flushPromises();

      expect(wrapper.find('[data-testid="chips-skeleton"]').exists()).toBe(true);
      expect(wrapper.findAll('[data-testid="submission-cell-loading"]')).toHaveLength(3);
      expect(wrapper.find('[data-chip]').exists()).toBe(false);
      expect(wrapper.text()).not.toContain('未提出');
      expect(shownIds(wrapper).sort()).toEqual(['N01', 'N02', 'N03']);
    });

    it('should keep the list and warn when the submissions cannot be fetched (never everyone 未提出), then recover on retry', async () => {
      getDocuments.mockRejectedValueOnce(new Error('permission-denied')).mockResolvedValueOnce(FILES);
      const wrapper = await mountView(1280);
      await flushPromises();

      expect(wrapper.get('[role="alert"]').text()).toContain('提出状況を取得できませんでした');
      expect(shownIds(wrapper).sort()).toEqual(['N01', 'N02', 'N03']);
      expect(wrapper.find('[data-status]').exists()).toBe(false);
      expect(wrapper.text()).not.toContain('未提出');
      expect(wrapper.find('[data-chip]').exists()).toBe(false);

      await wrapper.get('[role="alert"] button').trigger('click');
      await flushPromises();

      expect(wrapper.find('[role="alert"]').exists()).toBe(false);
      expect(statuses(wrapper)).toEqual(['pending', 'passed', 'not_submitted']);
    });

    it('should warn instead of showing everyone as 未提出 when no file matches anyone in the class (mismatch)', async () => {
      getDocuments.mockResolvedValue([file('N99', '合格'), file('', '合格')]);
      const wrapper = await mountView(1280);
      await flushPromises();

      expect(wrapper.get('[role="alert"]').text()).toContain('提出データと受講生名簿が一致しなかった');
      expect(wrapper.find('[data-status]').exists()).toBe(false);
      expect(wrapper.text()).not.toContain('未提出');
      expect(wrapper.find('[data-chip]').exists()).toBe(false);
      expect(shownIds(wrapper).sort()).toEqual(['N01', 'N02', 'N03']);
    });

    it('should not treat a class where only another group has submitted as a mismatch', async () => {
      // N09 は別グループだが同じクラス。名簿と一致しているので不一致ではなく、このグループは全員未提出
      getDocuments.mockResolvedValue([file('N09', '合格')]);
      const wrapper = await mountView(1280);
      await flushPromises();

      expect(wrapper.find('[role="alert"]').exists()).toBe(false);
      expect(statuses(wrapper)).toEqual(['not_submitted', 'not_submitted', 'not_submitted']);
    });

    it('should tell how many files have no student id (those students look 未提出)', async () => {
      getDocuments.mockResolvedValue([file('N01', '合格'), file('', '合格'), file(undefined, '合格')]);
      const wrapper = await mountView(1280);
      await flushPromises();

      expect(wrapper.text()).toContain('日介番号が空の提出ファイルが 2 件あります');
    });

    it('should not show that note when every file has a student id', async () => {
      getDocuments.mockResolvedValue(FILES);
      const wrapper = await mountView(1280);
      await flushPromises();

      expect(wrapper.text()).not.toContain('日介番号が空の提出ファイル');
    });

    it('should give the chips a 44px touch target below lg', async () => {
      getDocuments.mockResolvedValue(FILES);
      const wrapper = await mountView(390);
      await flushPromises();

      for (const c of wrapper.findAll('[data-chip]')) {
        expect(c.classes()).toEqual(expect.arrayContaining(['min-h-11', 'lg:min-h-0']));
      }
    });
  });
});
