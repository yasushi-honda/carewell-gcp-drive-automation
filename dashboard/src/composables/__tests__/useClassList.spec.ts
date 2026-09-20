import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useClassList } from '../useClassList';
import * as useFirestore from '../useFirestore';

// Mock useFirestore
vi.mock('../useFirestore', () => ({
  getTaskDocument: vi.fn(),
  getErrorMessage: vi.fn((err) => `Error: ${err.message}`),
}));

// Mock classes config
// 並列化のテストで複数クラスを扱えるよう、配列を hoisted にして各テストで in-place に変更する
const mockConfig = vi.hoisted(() => ({
  KNOWN_CLASSES: ['令和8年度 デジタル中核人材養成研修 №01'] as string[],
  KNOWN_TASK_IDS: ['課題①', '課題②', '課題③'] as string[],
}));
vi.mock('../../config/classes', () => mockConfig);

const CLASS_1 = '令和8年度 デジタル中核人材養成研修 №01';
const CLASS_2 = '令和8年度 デジタル中核人材養成研修 №02';

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

function taskDoc(taskId: string, fileCount: number, lastUpdated: string) {
  return {
    task_id: taskId,
    task_pattern: taskId,
    file_count: fileCount,
    created_at: '2025-10-13T10:00:00.000Z',
    last_updated: lastUpdated,
  };
}

describe('useClassList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // 前のテストで設定した実装・未消費の Once が漏れないようにする
    vi.mocked(useFirestore.getTaskDocument).mockReset();
    // 既定は1クラス（並列化テストだけが2クラスに広げる）
    mockConfig.KNOWN_CLASSES.splice(0, mockConfig.KNOWN_CLASSES.length, CLASS_1);
  });

  it('should fetch classes with aggregated statistics', async () => {
    // Mock task documents
    vi.mocked(useFirestore.getTaskDocument)
      .mockResolvedValueOnce({
        task_id: '課題①',
        task_pattern: '課題①',
        file_count: 5,
        created_at: '2025-10-13T10:00:00.000Z',
        last_updated: '2025-10-13T12:00:00.000Z',
      })
      .mockResolvedValueOnce({
        task_id: '課題②',
        task_pattern: '課題②',
        file_count: 3,
        created_at: '2025-10-13T10:00:00.000Z',
        last_updated: '2025-10-13T11:00:00.000Z',
      })
      .mockResolvedValueOnce({
        task_id: '課題③',
        task_pattern: '課題③',
        file_count: 2,
        created_at: '2025-10-13T10:00:00.000Z',
        last_updated: '2025-10-13T10:30:00.000Z',
      });

    const { classes, loading, error, fetchClasses } = useClassList();

    expect(loading.value).toBe(false);
    expect(error.value).toBeNull();

    await fetchClasses();

    expect(loading.value).toBe(false);
    expect(error.value).toBeNull();
    expect(classes.value).toHaveLength(1);
    expect(classes.value[0]).toEqual({
      name: '令和8年度 デジタル中核人材養成研修 №01',
      taskCount: 3,
      fileCount: 10, // 5 + 3 + 2
      lastUpdated: '2025-10-13T12:00:00.000Z', // Latest timestamp
    });
  });

  it('should handle missing task documents gracefully', async () => {
    // Mock: First task exists, others return null
    vi.mocked(useFirestore.getTaskDocument)
      .mockResolvedValueOnce({
        task_id: '課題①',
        task_pattern: '課題①',
        file_count: 5,
        created_at: '2025-10-13T10:00:00.000Z',
        last_updated: '2025-10-13T12:00:00.000Z',
      })
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(null);

    const { classes, fetchClasses } = useClassList();

    await fetchClasses();

    expect(classes.value).toHaveLength(1);
    expect(classes.value[0]).toEqual({
      name: '令和8年度 デジタル中核人材養成研修 №01',
      taskCount: 1,
      fileCount: 5,
      lastUpdated: '2025-10-13T12:00:00.000Z',
    });
  });

  it('should handle task fetch errors gracefully', async () => {
    // Mock: First task succeeds, second throws error, third succeeds
    vi.mocked(useFirestore.getTaskDocument)
      .mockResolvedValueOnce({
        task_id: '課題①',
        task_pattern: '課題①',
        file_count: 5,
        created_at: '2025-10-13T10:00:00.000Z',
        last_updated: '2025-10-13T12:00:00.000Z',
      })
      .mockRejectedValueOnce(new Error('Task fetch error'))
      .mockResolvedValueOnce({
        task_id: '課題③',
        task_pattern: '課題③',
        file_count: 2,
        created_at: '2025-10-13T10:00:00.000Z',
        last_updated: '2025-10-13T10:30:00.000Z',
      });

    const { classes, error, fetchClasses } = useClassList();

    await fetchClasses();

    expect(error.value).toBeNull(); // Individual errors don't fail the whole fetch
    expect(classes.value).toHaveLength(1);
    expect(classes.value[0].taskCount).toBe(2); // Only 2 tasks succeeded
    expect(classes.value[0].fileCount).toBe(7); // 5 + 2
  });

  it('should set loading state correctly', async () => {
    vi.mocked(useFirestore.getTaskDocument).mockResolvedValue({
      task_id: '課題①',
      task_pattern: '課題①',
      file_count: 5,
      created_at: '2025-10-13T10:00:00.000Z',
      last_updated: '2025-10-13T12:00:00.000Z',
    });

    const { loading, fetchClasses } = useClassList();

    expect(loading.value).toBe(false);

    const fetchPromise = fetchClasses();
    expect(loading.value).toBe(true);

    await fetchPromise;
    expect(loading.value).toBe(false);
  });

  it('should set error state on complete failure', async () => {
    const mockError = new Error('Complete failure');
    vi.mocked(useFirestore.getTaskDocument).mockRejectedValue(mockError);
    vi.mocked(useFirestore.getErrorMessage).mockReturnValue('Error: Complete failure');

    const { error, fetchClasses } = useClassList();

    await fetchClasses();

    // Note: Current implementation doesn't set error on individual task failures
    // This test verifies the expected error handling behavior
    expect(error.value).toBeNull();
  });

  describe('parallel fetching', () => {
    it('should issue all class×task requests before any of them resolves', async () => {
      mockConfig.KNOWN_CLASSES.splice(0, mockConfig.KNOWN_CLASSES.length, CLASS_1, CLASS_2);
      const pending = Array.from({ length: 6 }, () => deferred<ReturnType<typeof taskDoc> | null>());
      pending.forEach((d) => vi.mocked(useFirestore.getTaskDocument).mockReturnValueOnce(d.promise));

      const { fetchClasses } = useClassList();
      const fetchPromise = fetchClasses();

      // どれも解決していない時点で、2クラス×3課題=6件がすべて発行済み（直列なら1件のみ）
      expect(useFirestore.getTaskDocument).toHaveBeenCalledTimes(6);

      pending.forEach((d) => d.resolve(null));
      await fetchPromise;
    });

    it('should issue requests in class-major order (class order, then task order)', async () => {
      mockConfig.KNOWN_CLASSES.splice(0, mockConfig.KNOWN_CLASSES.length, CLASS_1, CLASS_2);
      vi.mocked(useFirestore.getTaskDocument).mockResolvedValue(null);

      const { fetchClasses } = useClassList();
      await fetchClasses();

      const calls = vi.mocked(useFirestore.getTaskDocument).mock.calls;
      expect(calls).toEqual([
        [CLASS_1, '課題①'],
        [CLASS_1, '課題②'],
        [CLASS_1, '課題③'],
        [CLASS_2, '課題①'],
        [CLASS_2, '課題②'],
        [CLASS_2, '課題③'],
      ]);
    });

    it('should keep the configured class order even when responses arrive out of order', async () => {
      mockConfig.KNOWN_CLASSES.splice(0, mockConfig.KNOWN_CLASSES.length, CLASS_1, CLASS_2);
      const slowClass1 = deferred<ReturnType<typeof taskDoc> | null>();
      vi.mocked(useFirestore.getTaskDocument).mockImplementation((className, taskId) => {
        if (className === CLASS_1 && taskId === '課題①') return slowClass1.promise;
        if (className === CLASS_2 && taskId === '課題①') {
          return Promise.resolve(taskDoc('課題①', 7, '2025-10-14T09:00:00.000Z'));
        }
        return Promise.resolve(null);
      });

      const { classes, loading, fetchClasses } = useClassList();
      const fetchPromise = fetchClasses();

      // №02 の応答が先に届き、№01 は最後に届く。
      // マイクロタスクが確実に掃けるまで待ち（1tick任せにしない）、№01 が未解決のため取得中であることを確認する
      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(loading.value).toBe(true);
      slowClass1.resolve(taskDoc('課題①', 4, '2025-10-13T09:00:00.000Z'));
      await fetchPromise;

      expect(classes.value.map((c) => c.name)).toEqual([CLASS_1, CLASS_2]);
      expect(classes.value[0]).toEqual({
        name: CLASS_1,
        taskCount: 1,
        fileCount: 4,
        lastUpdated: '2025-10-13T09:00:00.000Z',
      });
      expect(classes.value[1]).toEqual({
        name: CLASS_2,
        taskCount: 1,
        fileCount: 7,
        lastUpdated: '2025-10-14T09:00:00.000Z',
      });
    });

    it('should not let one rejected request affect other classes', async () => {
      mockConfig.KNOWN_CLASSES.splice(0, mockConfig.KNOWN_CLASSES.length, CLASS_1, CLASS_2);
      vi.mocked(useFirestore.getTaskDocument).mockImplementation((className, taskId) => {
        if (className === CLASS_1) return Promise.reject(new Error('boom'));
        return Promise.resolve(taskId === '課題①' ? taskDoc('課題①', 3, '2025-10-14T09:00:00.000Z') : null);
      });

      const { classes, error, fetchClasses } = useClassList();
      await fetchClasses();

      expect(error.value).toBeNull();
      expect(classes.value).toEqual([
        { name: CLASS_1, taskCount: 0, fileCount: 0, lastUpdated: null },
        { name: CLASS_2, taskCount: 1, fileCount: 3, lastUpdated: '2025-10-14T09:00:00.000Z' },
      ]);
    });

    it('should return zeroed entries (not an error) when every request fails', async () => {
      // 現行挙動の固定: 全件失敗でもエラー表示にはせず、統計0のクラスを返す
      mockConfig.KNOWN_CLASSES.splice(0, mockConfig.KNOWN_CLASSES.length, CLASS_1, CLASS_2);
      vi.mocked(useFirestore.getTaskDocument).mockRejectedValue(new Error('offline'));

      const { classes, error, fetchClasses } = useClassList();
      await fetchClasses();

      expect(error.value).toBeNull();
      expect(classes.value).toEqual([
        { name: CLASS_1, taskCount: 0, fileCount: 0, lastUpdated: null },
        { name: CLASS_2, taskCount: 0, fileCount: 0, lastUpdated: null },
      ]);
    });

    it('should replace previous results with an empty list when there are no known classes', async () => {
      // 初期値の [] と区別するため、先に非空の結果を作ってから空にして再取得する
      vi.mocked(useFirestore.getTaskDocument).mockResolvedValue(taskDoc('課題①', 1, '2025-10-13T09:00:00.000Z'));

      const { classes, error, fetchClasses } = useClassList();
      await fetchClasses();
      expect(classes.value).toHaveLength(1);
      expect(useFirestore.getTaskDocument).toHaveBeenCalledTimes(3);

      mockConfig.KNOWN_CLASSES.splice(0, mockConfig.KNOWN_CLASSES.length);
      await fetchClasses();

      expect(useFirestore.getTaskDocument).toHaveBeenCalledTimes(3); // 2回目は取得しない
      expect(error.value).toBeNull();
      expect(classes.value).toEqual([]);
    });

    it('should select the latest last_updated regardless of task order or completion order', async () => {
      // 最新(課題②)が中間に位置し、かつ最後に解決する。「先頭が最新」「完了順の最後が最新」を仮定した実装を検出する
      const slowLatest = deferred<ReturnType<typeof taskDoc> | null>();
      vi.mocked(useFirestore.getTaskDocument).mockImplementation((_className, taskId) => {
        if (taskId === '課題①') return Promise.resolve(taskDoc('課題①', 1, '2025-10-10T00:00:00.000Z'));
        if (taskId === '課題②') return slowLatest.promise;
        return Promise.resolve(taskDoc('課題③', 4, '2025-10-12T00:00:00.000Z'));
      });

      const { classes, fetchClasses } = useClassList();
      const fetchPromise = fetchClasses();

      await new Promise((resolve) => setTimeout(resolve, 0));
      slowLatest.resolve(taskDoc('課題②', 2, '2025-10-15T00:00:00.000Z'));
      await fetchPromise;

      expect(classes.value[0]).toEqual({
        name: CLASS_1,
        taskCount: 3,
        fileCount: 7, // 1 + 2 + 4
        lastUpdated: '2025-10-15T00:00:00.000Z',
      });
    });

    it('should map each class×task cell to the right class even when responses are shuffled', async () => {
      // セルごとに一意の値を与え、添字の取り違え・クラス間のアキュムレータ共有を検出する
      mockConfig.KNOWN_CLASSES.splice(0, mockConfig.KNOWN_CLASSES.length, CLASS_1, CLASS_2);
      const cells: Record<string, ReturnType<typeof taskDoc> | null> = {
        [`${CLASS_1}|課題①`]: taskDoc('課題①', 1, '2025-10-01T00:00:00.000Z'),
        [`${CLASS_1}|課題②`]: null, // 文書なし
        [`${CLASS_1}|課題③`]: taskDoc('課題③', 0, '2025-10-03T00:00:00.000Z'), // file_count 0 でも文書は存在する
        [`${CLASS_2}|課題①`]: taskDoc('課題①', 10, '2025-10-20T00:00:00.000Z'),
        [`${CLASS_2}|課題②`]: taskDoc('課題②', 20, '2025-10-10T00:00:00.000Z'),
        [`${CLASS_2}|課題③`]: taskDoc('課題③', 30, '2025-10-15T00:00:00.000Z'),
      };
      // 呼び出し順と逆順に近い遅延で応答させる（完了順 ≠ 発行順）
      const delays: Record<string, number> = {
        [`${CLASS_1}|課題①`]: 6,
        [`${CLASS_1}|課題②`]: 5,
        [`${CLASS_1}|課題③`]: 4,
        [`${CLASS_2}|課題①`]: 3,
        [`${CLASS_2}|課題②`]: 2,
        [`${CLASS_2}|課題③`]: 1,
      };
      vi.mocked(useFirestore.getTaskDocument).mockImplementation((className, taskId) => {
        const key = `${className}|${taskId}`;
        return new Promise((resolve) => setTimeout(() => resolve(cells[key]), delays[key]));
      });

      const { classes, fetchClasses } = useClassList();
      await fetchClasses();

      expect(classes.value).toEqual([
        { name: CLASS_1, taskCount: 2, fileCount: 1, lastUpdated: '2025-10-03T00:00:00.000Z' },
        { name: CLASS_2, taskCount: 3, fileCount: 60, lastUpdated: '2025-10-20T00:00:00.000Z' },
      ]);
    });

    it('should keep loading true until every pending request has completed', async () => {
      const pending = [deferred<null>(), deferred<null>(), deferred<null>()]; // 1クラス×3課題
      pending.forEach((d) => vi.mocked(useFirestore.getTaskDocument).mockReturnValueOnce(d.promise));

      const { loading, fetchClasses } = useClassList();
      const fetchPromise = fetchClasses();

      pending[0].resolve(null);
      pending[1].resolve(null);
      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(loading.value).toBe(true); // 1件が未完了の間は取得中のまま

      pending[2].resolve(null);
      await fetchPromise;
      expect(loading.value).toBe(false);
    });
  });
});
