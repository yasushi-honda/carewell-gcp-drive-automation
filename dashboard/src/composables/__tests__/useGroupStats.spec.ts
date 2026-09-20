import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { defineComponent, h, ref } from 'vue';
import {
  useGroupStats,
  classifyPassStatus,
  pickCurrentStatus,
  summarizeSubmissions,
  type SubmissionFile,
  type RosterStudent,
} from '../useGroupStats';
import * as firestore from 'firebase/firestore';
import * as useFirestore from '../useFirestore';

vi.mock('firebase/firestore', () => ({
  collection: vi.fn(() => 'students-collection'),
  query: vi.fn((...args: unknown[]) => ({ query: args })),
  where: vi.fn((...args: unknown[]) => ({ where: args })),
  getDocs: vi.fn(),
}));
vi.mock('../../config/firebase', () => ({ getDb: vi.fn(() => ({})) }));
vi.mock('../useFirestore', () => ({ getDocuments: vi.fn() }));

const CLASS_FULL = '令和8年度 デジタル中核人材養成研修 №01';
const TASK = '課題①';

/** 解決/拒否のタイミングをテスト側で制御できる Promise */
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

/** 受講生のスナップショット。id が日介番号（useStudents と同じ） */
function studentsSnapshot(rows: Array<{ id: string; group?: string }>) {
  return { docs: rows.map((r) => ({ id: r.id, data: () => (r.group === undefined ? {} : { group: r.group }) })) };
}

function file(studentId: string, passStatus: unknown, submitDate = '2026/09/20 10:00:00'): SubmissionFile {
  return { student_id: studentId, submit_date: submitDate, metadata: { pass_status: passStatus } };
}

// ---------------------------------------------------------------------------
// 判定ロジック（純粋関数）
// ---------------------------------------------------------------------------
describe('classifyPassStatus', () => {
  it('should classify exact 合格 and 不合格', () => {
    expect(classifyPassStatus('合格')).toBe('passed');
    expect(classifyPassStatus('不合格')).toBe('failed');
  });

  it('should not treat 不合格 as 合格 (no substring matching)', () => {
    expect(classifyPassStatus('不合格')).not.toBe('passed');
  });

  it('should ignore surrounding whitespace', () => {
    expect(classifyPassStatus(' 合格 ')).toBe('passed');
    expect(classifyPassStatus('\t不合格\n')).toBe('failed');
  });

  it.each([['', 'empty'], ['   ', 'blank'], ['採点待ち', 'unknown text'], ['合格（再提出可）', 'partial match'], [null, 'null'], [undefined, 'undefined'], [1, 'number'], [true, 'boolean'], [{}, 'object']])(
    'should treat %j (%s) as pending',
    (value) => {
      expect(classifyPassStatus(value)).toBe('pending');
    }
  );
});

describe('pickCurrentStatus', () => {
  it('should use the latest submission (fail then a newer pending → pending)', () => {
    const files = [file('N1', '不合格', '2026/09/20 10:00:00'), file('N1', '', '2026/09/21 09:00:00')];
    expect(pickCurrentStatus(files)).toBe('pending');
  });

  it('should reflect a newer failure even after an older pass', () => {
    const files = [file('N1', '合格', '2026/09/20 10:00:00'), file('N1', '不合格', '2026/09/22 10:00:00')];
    expect(pickCurrentStatus(files)).toBe('failed');
  });

  it('should not depend on the order of the input', () => {
    const files = [file('N1', '不合格', '2026/09/22 10:00:00'), file('N1', '合格', '2026/09/20 10:00:00')];
    expect(pickCurrentStatus(files)).toBe('failed');
  });

  it('should break a tie on the same second by 合格 > 採点待ち > 不合格', () => {
    const same = '2026/09/20 10:00:00';
    expect(pickCurrentStatus([file('N1', '不合格', same), file('N1', '', same), file('N1', '合格', same)])).toBe('passed');
    expect(pickCurrentStatus([file('N1', '不合格', same), file('N1', '', same)])).toBe('pending');
  });

  it('should break the tie by rank regardless of the input order (not last-wins)', () => {
    const same = '2026/09/20 10:00:00';
    expect(pickCurrentStatus([file('N1', '合格', same), file('N1', '', same), file('N1', '不合格', same)])).toBe('passed');
    expect(pickCurrentStatus([file('N1', '', same), file('N1', '合格', same)])).toBe('passed');
    expect(pickCurrentStatus([file('N1', '', same), file('N1', '不合格', same)])).toBe('pending');
  });

  it('should not pick an undated file just because it comes last (a dated file is newer)', () => {
    const files: SubmissionFile[] = [
      file('N1', '不合格', '2026/09/20 10:00:00'),
      { student_id: 'N1', metadata: { pass_status: '合格' } },
    ];
    expect(pickCurrentStatus(files)).toBe('failed');
  });

  it('should treat a missing or invalid submit_date as the oldest', () => {
    const files: SubmissionFile[] = [
      { student_id: 'N1', metadata: { pass_status: '合格' } },
      { student_id: 'N1', submit_date: 123, metadata: { pass_status: '合格' } },
      file('N1', '不合格', '2026/09/20 10:00:00'),
    ];
    expect(pickCurrentStatus(files)).toBe('failed');
  });

  it('should treat missing metadata as pending', () => {
    expect(pickCurrentStatus([{ student_id: 'N1', submit_date: '2026/09/20 10:00:00' }])).toBe('pending');
    expect(pickCurrentStatus([{ student_id: 'N1', submit_date: '2026/09/20 10:00:00', metadata: null }])).toBe('pending');
  });

  it('should return pending for an empty list', () => {
    expect(pickCurrentStatus([])).toBe('pending');
  });
});

describe('summarizeSubmissions', () => {
  const roster: RosterStudent[] = [
    { student_id: 'N1', group: 'A' },
    { student_id: 'N2', group: 'A' },
    { student_id: 'N3', group: 'A' },
    { student_id: 'N4', group: 'B' },
    { student_id: 'N5', group: 'B' },
  ];

  it('should count each group by state and make submitted + notSubmitted equal the group size', () => {
    const files = [file('N1', '合格'), file('N2', ''), file('N4', '不合格')];

    const { byGroup } = summarizeSubmissions(roster, files);

    expect(byGroup.get('A')).toEqual({ submitted: 2, notSubmitted: 1, passed: 1, pending: 1, failed: 0 });
    expect(byGroup.get('B')).toEqual({ submitted: 1, notSubmitted: 1, passed: 0, pending: 0, failed: 1 });
  });

  it('should count a student who submitted twice only once', () => {
    const files = [file('N1', '不合格', '2026/09/20 10:00:00'), file('N1', '合格', '2026/09/21 10:00:00')];

    const { byGroup, submitters } = summarizeSubmissions(roster, files);

    expect(submitters).toBe(1);
    expect(byGroup.get('A')).toEqual({ submitted: 1, notSubmitted: 2, passed: 1, pending: 0, failed: 0 });
  });

  it('should exclude submitters who are not on the active roster and report how many', () => {
    const files = [file('N1', '合格'), file('GONE', '合格'), file('GONE2', '')];

    const { byGroup, submitters, unmatchedSubmitters } = summarizeSubmissions(roster, files);

    expect(submitters).toBe(3);
    expect(unmatchedSubmitters).toBe(2);
    const totalSubmitted = [...byGroup.values()].reduce((sum, g) => sum + g.submitted, 0);
    expect(totalSubmitted).toBe(1);
  });

  it('should ignore files without a usable student_id', () => {
    const files: SubmissionFile[] = [
      { submit_date: '2026/09/20 10:00:00' },
      { student_id: '', metadata: { pass_status: '合格' } },
      { student_id: '   ' },
      { student_id: 42 },
      file('N1', '合格'),
    ];

    const { submitters, unmatchedSubmitters, unidentifiedFiles, byGroup } = summarizeSubmissions(roster, files);

    expect(submitters).toBe(1);
    expect(unmatchedSubmitters).toBe(0);
    // 誰の提出か分からないファイルは集計に含めず、数だけ返す
    expect(unidentifiedFiles).toBe(4);
    expect(byGroup.get('A')?.submitted).toBe(1);
  });

  it('should match student ids ignoring surrounding whitespace on the file side', () => {
    const { byGroup } = summarizeSubmissions(roster, [file(' N1 ', '合格')]);

    expect(byGroup.get('A')?.passed).toBe(1);
  });

  it('should return everyone as not submitted when there are no files', () => {
    const { byGroup, submitters, unmatchedSubmitters } = summarizeSubmissions(roster, []);

    expect(submitters).toBe(0);
    expect(unmatchedSubmitters).toBe(0);
    expect(byGroup.get('A')).toEqual({ submitted: 0, notSubmitted: 3, passed: 0, pending: 0, failed: 0 });
    expect(byGroup.get('B')).toEqual({ submitted: 0, notSubmitted: 2, passed: 0, pending: 0, failed: 0 });
  });

  it('should handle about 254 students all having submitted', () => {
    const big: RosterStudent[] = Array.from({ length: 254 }, (_, i) => ({ student_id: `N${i}`, group: `G${i % 15}` }));
    const files = big.map((s, i) => file(s.student_id, i % 3 === 0 ? '合格' : i % 3 === 1 ? '不合格' : ''));

    const { byGroup, submitters, unmatchedSubmitters } = summarizeSubmissions(big, files);

    expect(submitters).toBe(254);
    expect(unmatchedSubmitters).toBe(0);
    const totals = [...byGroup.values()].reduce(
      (acc, g) => ({ submitted: acc.submitted + g.submitted, notSubmitted: acc.notSubmitted + g.notSubmitted }),
      { submitted: 0, notSubmitted: 0 }
    );
    expect(totals).toEqual({ submitted: 254, notSubmitted: 0 });
  });
});

// ---------------------------------------------------------------------------
// composable（取得の順序・失敗・競合）
// ---------------------------------------------------------------------------
describe('useGroupStats', () => {
  const getDocs = vi.mocked(firestore.getDocs);
  const getDocuments = vi.mocked(useFirestore.getDocuments);

  beforeEach(() => {
    vi.clearAllMocks();
    getDocs.mockReset();
    getDocuments.mockReset();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function mountComposable(className: string | { value: string } = CLASS_FULL, taskId: string | { value: string } = TASK) {
    let result!: ReturnType<typeof useGroupStats>;
    const Host = defineComponent({
      setup() {
        result = useGroupStats(className as never, taskId as never);
        return () => h('div');
      },
    });
    const wrapper = mount(Host);
    return { result, wrapper };
  }

  const ROSTER = studentsSnapshot([
    { id: 'N1', group: 'A' },
    { id: 'N2', group: 'A' },
    { id: 'N3', group: 'B' },
    { id: 'N4' }, // group 未設定 → 未分類
  ]);

  it('should read submissions from the full class name and students from the short class name', async () => {
    getDocs.mockResolvedValue(ROSTER as never);
    getDocuments.mockResolvedValue([]);

    mountComposable();
    await flushPromises();

    expect(getDocuments).toHaveBeenCalledWith('submissions', CLASS_FULL, 'tasks', TASK, 'files');
    expect(firestore.where).toHaveBeenCalledWith('class_name', '==', 'No1');
    expect(firestore.where).toHaveBeenCalledWith('status', '==', 'active');
  });

  it('should request the submissions only after the students arrive (so the cards are not slowed by the larger download)', async () => {
    const students = deferred<unknown>();
    getDocs.mockReturnValue(students.promise as never);
    getDocuments.mockResolvedValue([]);

    mountComposable();
    await flushPromises();

    // 受講生が届くまで、提出データは取りに行かない（同じ回線を分け合わない）
    expect(getDocs).toHaveBeenCalledTimes(1);
    expect(getDocuments).not.toHaveBeenCalled();

    students.resolve(ROSTER);
    await flushPromises();

    expect(getDocuments).toHaveBeenCalledTimes(1);
  });

  it('should show the cards before the submissions arrive, then fill in the breakdown', async () => {
    const files = deferred<SubmissionFile[]>();
    getDocs.mockResolvedValue(ROSTER as never);
    getDocuments.mockReturnValue(files.promise as never);

    const { result } = mountComposable();
    await flushPromises();

    // 受講生は取れて提出データは未着
    expect(result.loading.value).toBe(false);
    expect(result.submissionState.value).toBe('loading');
    expect(result.groupStats.value.map((s) => [s.group, s.studentCount])).toEqual([
      ['A', 2],
      ['B', 1],
      ['未分類', 1],
    ]);
    expect(result.groupStats.value.every((s) => s.submission === undefined)).toBe(true);

    files.resolve([file('N1', '合格'), file('N3', '')]);
    await flushPromises();

    expect(result.submissionState.value).toBe('ready');
    const byGroup = Object.fromEntries(result.groupStats.value.map((s) => [s.group, s.submission]));
    expect(byGroup.A).toEqual({ submitted: 1, notSubmitted: 1, passed: 1, pending: 0, failed: 0 });
    expect(byGroup.B).toEqual({ submitted: 1, notSubmitted: 0, passed: 0, pending: 1, failed: 0 });
    expect(byGroup['未分類']).toEqual({ submitted: 0, notSubmitted: 1, passed: 0, pending: 0, failed: 0 });
  });

  it('should treat a successful empty result as everyone not submitted (not an error)', async () => {
    getDocs.mockResolvedValue(ROSTER as never);
    getDocuments.mockResolvedValue([]);

    const { result } = mountComposable();
    await flushPromises();

    expect(result.submissionState.value).toBe('ready');
    expect(result.groupStats.value.map((s) => s.submission?.notSubmitted)).toEqual([2, 1, 1]);
  });

  it('should keep the cards and report an error when only the submissions fail (never everyone-not-submitted)', async () => {
    getDocs.mockResolvedValue(ROSTER as never);
    getDocuments.mockRejectedValue(new Error('permission-denied'));

    const { result } = mountComposable();
    await flushPromises();

    expect(result.error.value).toBeNull();
    expect(result.submissionState.value).toBe('error');
    expect(result.groupStats.value).toHaveLength(3);
    expect(result.groupStats.value.every((s) => s.submission === undefined)).toBe(true);
  });

  it('should recover with refetchSubmissions without refetching the students', async () => {
    getDocs.mockResolvedValue(ROSTER as never);
    getDocuments.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce([file('N1', '合格')]);

    const { result } = mountComposable();
    await flushPromises();
    expect(result.submissionState.value).toBe('error');

    const retry = result.refetchSubmissions();
    expect(result.submissionState.value).toBe('loading');
    await retry;

    expect(result.submissionState.value).toBe('ready');
    expect(getDocs).toHaveBeenCalledTimes(1);
    expect(getDocuments).toHaveBeenCalledTimes(2);
    expect(result.groupStats.value.find((s) => s.group === 'A')?.submission?.passed).toBe(1);
  });

  it('should report a mismatch when files exist but nobody matches the roster (no misleading everyone-not-submitted)', async () => {
    getDocs.mockResolvedValue(ROSTER as never);
    getDocuments.mockResolvedValue([file('X1', '合格'), file('X2', '')]);

    const { result } = mountComposable();
    await flushPromises();

    expect(result.submissionState.value).toBe('mismatch');
    expect(result.unmatchedSubmitters.value).toBe(2);
    expect(result.groupStats.value.every((s) => s.submission === undefined)).toBe(true);
  });

  it('should stay ready and report the count when only some submitters are not on the roster', async () => {
    getDocs.mockResolvedValue(ROSTER as never);
    getDocuments.mockResolvedValue([file('N1', '合格'), file('GONE', '合格')]);

    const { result } = mountComposable();
    await flushPromises();

    expect(result.submissionState.value).toBe('ready');
    expect(result.unmatchedSubmitters.value).toBe(1);
  });

  it('should report the page-level error when the students fail (independent of the submissions)', async () => {
    getDocs.mockRejectedValue(new Error('boom'));
    getDocuments.mockResolvedValue([file('N1', '合格')]);

    const { result } = mountComposable();
    await flushPromises();

    expect(result.error.value).toBe('グループ統計の取得に失敗しました');
    expect(result.loading.value).toBe(false);
    expect(result.groupStats.value).toEqual([]);
    // 取得中のまま固まらない
    expect(result.submissionState.value).toBe('error');
  });

  it('should clear the previous cards when the students fail after a successful load', async () => {
    const taskId = ref('課題①');
    getDocs.mockResolvedValueOnce(ROSTER as never).mockRejectedValueOnce(new Error('offline'));
    getDocuments.mockResolvedValue([]);

    const { result } = mountComposable(CLASS_FULL, taskId);
    await flushPromises();
    expect(result.groupStats.value).toHaveLength(3);

    taskId.value = '課題②';
    await flushPromises();

    expect(result.error.value).toBe('グループ統計の取得に失敗しました');
    expect(result.groupStats.value).toEqual([]);
  });

  it('should not request the submissions at all when the students fail', async () => {
    getDocs.mockRejectedValue(new Error('students down'));
    getDocuments.mockRejectedValue(new Error('files down'));

    const { result } = mountComposable();
    await flushPromises();

    expect(result.error.value).toBe('グループ統計の取得に失敗しました');
    expect(getDocuments).not.toHaveBeenCalled();
  });

  it('should refetch when the task changes and ignore the older response arriving late', async () => {
    const taskId = ref('課題①');
    const firstFiles = deferred<SubmissionFile[]>();
    const secondFiles = deferred<SubmissionFile[]>();
    getDocs.mockResolvedValue(ROSTER as never);
    getDocuments.mockReturnValueOnce(firstFiles.promise as never).mockReturnValueOnce(secondFiles.promise as never);

    const { result } = mountComposable(CLASS_FULL, taskId);
    await flushPromises();

    taskId.value = '課題②';
    await flushPromises();
    expect(getDocuments).toHaveBeenLastCalledWith('submissions', CLASS_FULL, 'tasks', '課題②', 'files');

    // 新しい課題の応答が先に届き、そのあとで古い課題の応答が届く
    secondFiles.resolve([file('N1', '不合格')]);
    await flushPromises();
    firstFiles.resolve([file('N1', '合格'), file('N2', '合格'), file('N3', '合格')]);
    await flushPromises();

    expect(result.submissionState.value).toBe('ready');
    const a = result.groupStats.value.find((s) => s.group === 'A')?.submission;
    expect(a).toEqual({ submitted: 1, notSubmitted: 1, passed: 0, pending: 0, failed: 1 });
  });

  it('should report a mismatch when every file has an unusable student id (never everyone-not-submitted)', async () => {
    getDocs.mockResolvedValue(ROSTER as never);
    getDocuments.mockResolvedValue([{}, { student_id: '' }, { student_id: 42 }, { student_id: '  ' }]);

    const { result } = mountComposable();
    await flushPromises();

    expect(result.submissionState.value).toBe('mismatch');
    expect(result.unidentifiedFiles.value).toBe(4);
    expect(result.groupStats.value.every((s) => s.submission === undefined)).toBe(true);
  });

  it('should stay ready and count the files without a student id when only some are unusable', async () => {
    getDocs.mockResolvedValue(ROSTER as never);
    getDocuments.mockResolvedValue([file('N1', '合格'), { student_id: '' }, {}]);

    const { result } = mountComposable();
    await flushPromises();

    expect(result.submissionState.value).toBe('ready');
    expect(result.unidentifiedFiles.value).toBe(2);
    expect(result.submitters.value).toBe(1);
    expect(result.groupStats.value.find((s) => s.group === 'A')?.submission?.passed).toBe(1);
  });

  it('should sort the groups (A to Z) whatever order the students come in', async () => {
    getDocs.mockResolvedValue(
      studentsSnapshot([
        { id: 'N1', group: 'C' },
        { id: 'N2', group: 'A' },
        { id: 'N3', group: 'B' },
      ]) as never
    );
    getDocuments.mockResolvedValue([]);

    const { result } = mountComposable();
    await flushPromises();

    expect(result.groupStats.value.map((s) => s.group)).toEqual(['A', 'B', 'C']);
  });

  it('should ignore an older students response arriving late (cards and loading follow the latest fetch)', async () => {
    const taskId = ref('課題①');
    const firstStudents = deferred<unknown>();
    getDocs
      .mockReturnValueOnce(firstStudents.promise as never)
      .mockResolvedValueOnce(studentsSnapshot([{ id: 'Z1', group: 'Z' }]) as never);
    getDocuments.mockResolvedValue([]);

    const { result } = mountComposable(CLASS_FULL, taskId);
    taskId.value = '課題②';
    await flushPromises();
    expect(result.groupStats.value.map((s) => s.group)).toEqual(['Z']);
    expect(result.loading.value).toBe(false);

    // 古い課題の受講生が、あとから届く
    firstStudents.resolve(ROSTER);
    await flushPromises();

    expect(result.groupStats.value.map((s) => s.group)).toEqual(['Z']);
    expect(result.loading.value).toBe(false);
    expect(result.error.value).toBeNull();
  });

  it('should not let an older students failure arriving late set the error', async () => {
    const taskId = ref('課題①');
    const firstStudents = deferred<unknown>();
    getDocs
      .mockReturnValueOnce(firstStudents.promise as never)
      .mockResolvedValueOnce(studentsSnapshot([{ id: 'Z1', group: 'Z' }]) as never);
    getDocuments.mockResolvedValue([]);

    const { result } = mountComposable(CLASS_FULL, taskId);
    taskId.value = '課題②';
    await flushPromises();

    firstStudents.reject(new Error('late failure'));
    await flushPromises();

    expect(result.error.value).toBeNull();
    expect(result.groupStats.value.map((s) => s.group)).toEqual(['Z']);
    expect(result.submissionState.value).toBe('ready');
  });

  describe('refetchSubmissions', () => {
    async function mountFailed() {
      getDocs.mockResolvedValue(ROSTER as never);
      getDocuments.mockRejectedValueOnce(new Error('offline'));
      const taskId = ref('課題①');
      const mounted = mountComposable(CLASS_FULL, taskId);
      await flushPromises();
      expect(mounted.result.submissionState.value).toBe('error');
      return { ...mounted, taskId };
    }

    it('should do nothing while the students are still loading (no aggregation against an empty roster)', async () => {
      const students = deferred<unknown>();
      getDocs.mockReturnValue(students.promise as never);
      getDocuments.mockResolvedValue([file('N1', '合格')]);

      const { result } = mountComposable();
      await result.refetchSubmissions();

      expect(getDocuments).not.toHaveBeenCalled();
      students.resolve(ROSTER);
      await flushPromises();
      expect(getDocuments).toHaveBeenCalledTimes(1);
      expect(result.submissionState.value).toBe('ready');
      expect(result.groupStats.value.find((s) => s.group === 'A')?.submission?.passed).toBe(1);
    });

    it('should let the latest of two quick retries win (double click)', async () => {
      const { result } = await mountFailed();
      const first = deferred<SubmissionFile[]>();
      const second = deferred<SubmissionFile[]>();
      getDocuments.mockReturnValueOnce(first.promise as never).mockReturnValueOnce(second.promise as never);

      const p1 = result.refetchSubmissions();
      const p2 = result.refetchSubmissions();
      second.resolve([file('N1', '合格')]);
      await flushPromises();
      first.resolve([file('N2', '不合格')]);
      await Promise.all([p1, p2]);
      await flushPromises();

      const a = result.groupStats.value.find((s) => s.group === 'A')?.submission;
      expect(a).toEqual({ submitted: 1, notSubmitted: 1, passed: 1, pending: 0, failed: 0 });
    });

    it('should not overwrite a newer fetch when the task changes while a retry is in flight', async () => {
      const { result, taskId } = await mountFailed();
      const retry = deferred<SubmissionFile[]>();
      getDocuments.mockReturnValueOnce(retry.promise as never).mockResolvedValueOnce([file('N3', '合格')]);

      const pending = result.refetchSubmissions();
      taskId.value = '課題②';
      await flushPromises();
      retry.resolve([file('N1', '不合格')]);
      await pending;
      await flushPromises();

      const b = result.groupStats.value.find((s) => s.group === 'B')?.submission;
      const a = result.groupStats.value.find((s) => s.group === 'A')?.submission;
      expect(b?.passed).toBe(1);
      expect(a?.submitted).toBe(0);
    });

    it('should not turn a newer successful state into an error when an older retry fails late', async () => {
      const { result, taskId } = await mountFailed();
      const retry = deferred<SubmissionFile[]>();
      getDocuments.mockReturnValueOnce(retry.promise as never).mockResolvedValueOnce([file('N3', '合格')]);

      const pending = result.refetchSubmissions();
      taskId.value = '課題②';
      await flushPromises();
      expect(result.submissionState.value).toBe('ready');
      retry.reject(new Error('late failure'));
      await pending;
      await flushPromises();

      expect(result.submissionState.value).toBe('ready');
    });
  });

  it('should refetch when the class changes', async () => {
    const className = ref(CLASS_FULL);
    getDocs.mockResolvedValue(ROSTER as never);
    getDocuments.mockResolvedValue([]);

    mountComposable(className, TASK);
    await flushPromises();
    className.value = '令和8年度 デジタル中核人材養成研修 №02';
    await flushPromises();

    expect(getDocs).toHaveBeenCalledTimes(2);
    expect(firestore.where).toHaveBeenCalledWith('class_name', '==', 'No2');
    expect(getDocuments).toHaveBeenLastCalledWith('submissions', '令和8年度 デジタル中核人材養成研修 №02', 'tasks', TASK, 'files');
  });
});
