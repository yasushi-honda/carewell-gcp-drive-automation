import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useTaskList } from '../useTaskList';
import * as useFirestore from '../useFirestore';

// Mock useFirestore
vi.mock('../useFirestore', () => ({
  getTaskDocument: vi.fn(),
  getDocuments: vi.fn(),
  getErrorMessage: vi.fn((err) => `Error: ${err.message}`),
}));

// Mock classes config
vi.mock('../../config/classes', () => ({
  KNOWN_TASK_IDS: ['課題①', '課題②'],
}));

describe('useTaskList', () => {
  const className = '令和8年度 デジタル中核人材養成研修 №01';

  beforeEach(() => {
    vi.clearAllMocks();
    // 前のテストで設定した実装・未消費の Once が漏れないようにする
    vi.mocked(useFirestore.getTaskDocument).mockReset();
    vi.mocked(useFirestore.getDocuments).mockReset();
  });

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

  it('should fetch tasks with aggregated statistics', async () => {
    // Mock parent documents
    vi.mocked(useFirestore.getTaskDocument)
      .mockResolvedValueOnce({
        task_id: '課題①',
        task_pattern: '課題①',
        file_count: 10,
        created_at: '2025-10-13T10:00:00.000Z',
        last_updated: '2025-10-13T12:00:00.000Z',
      })
      .mockResolvedValueOnce({
        task_id: '課題②',
        task_pattern: '課題②',
        file_count: 5,
        created_at: '2025-10-13T10:00:00.000Z',
        last_updated: '2025-10-13T11:00:00.000Z',
      });

    // Mock subcollection documents for student count
    vi.mocked(useFirestore.getDocuments)
      .mockResolvedValueOnce([
        { student_id: 'S001', student_name: '森平太郎' },
        { student_id: 'S002', student_name: '田中花子' },
        { student_id: 'S001', student_name: '森平太郎' }, // Duplicate
      ] as any)
      .mockResolvedValueOnce([
        { student_id: 'S003', student_name: '佐藤次郎' },
      ] as any);

    const { tasks, loading, error, fetchTasks } = useTaskList(className);

    await fetchTasks();

    expect(loading.value).toBe(false);
    expect(error.value).toBeNull();
    expect(tasks.value).toHaveLength(2);

    expect(tasks.value[0]).toEqual({
      taskId: '課題①',
      fileCount: 10,
      studentCount: 2, // S001, S002 (unique)
      lastSubmit: '2025-10-13T12:00:00.000Z',
    });

    expect(tasks.value[1]).toEqual({
      taskId: '課題②',
      fileCount: 5,
      studentCount: 1, // S003
      lastSubmit: '2025-10-13T11:00:00.000Z',
    });
  });

  it('should skip tasks without parent documents', async () => {
    vi.mocked(useFirestore.getTaskDocument)
      .mockResolvedValueOnce({
        task_id: '課題①',
        task_pattern: '課題①',
        file_count: 10,
        created_at: '2025-10-13T10:00:00.000Z',
        last_updated: '2025-10-13T12:00:00.000Z',
      })
      .mockResolvedValueOnce(null); // Task② doesn't exist

    vi.mocked(useFirestore.getDocuments).mockResolvedValueOnce([
      { student_id: 'S001', student_name: '森平太郎' },
    ] as any);

    const { tasks, fetchTasks } = useTaskList(className);

    await fetchTasks();

    expect(tasks.value).toHaveLength(1);
    expect(tasks.value[0].taskId).toBe('課題①');
  });

  it('should handle student count fetch errors', async () => {
    vi.mocked(useFirestore.getTaskDocument).mockResolvedValueOnce({
      task_id: '課題①',
      task_pattern: '課題①',
      file_count: 10,
      created_at: '2025-10-13T10:00:00.000Z',
      last_updated: '2025-10-13T12:00:00.000Z',
    });

    vi.mocked(useFirestore.getDocuments).mockRejectedValueOnce(new Error('Documents fetch error'));

    const { tasks, fetchTasks } = useTaskList(className);

    await fetchTasks();

    expect(tasks.value).toHaveLength(1);
    expect(tasks.value[0].studentCount).toBe(0); // Default to 0 on error
  });

  it('should set loading state correctly', async () => {
    vi.mocked(useFirestore.getTaskDocument).mockResolvedValue({
      task_id: '課題①',
      task_pattern: '課題①',
      file_count: 10,
      created_at: '2025-10-13T10:00:00.000Z',
      last_updated: '2025-10-13T12:00:00.000Z',
    });

    vi.mocked(useFirestore.getDocuments).mockResolvedValue([
      { student_id: 'S001', student_name: '森平太郎' },
    ] as any);

    const { loading, fetchTasks } = useTaskList(className);

    expect(loading.value).toBe(false);

    const fetchPromise = fetchTasks();
    expect(loading.value).toBe(true);

    await fetchPromise;
    expect(loading.value).toBe(false);
  });

  describe('parallel fetching', () => {
    it('should issue all task document requests before any of them resolves', async () => {
      const pending = [deferred<ReturnType<typeof taskDoc> | null>(), deferred<ReturnType<typeof taskDoc> | null>()];
      pending.forEach((d) => vi.mocked(useFirestore.getTaskDocument).mockReturnValueOnce(d.promise));

      const { fetchTasks } = useTaskList(className);
      const fetchPromise = fetchTasks();

      // どちらも解決していない時点で、2課題ぶんが発行済み（直列なら1件のみ）
      expect(useFirestore.getTaskDocument).toHaveBeenCalledTimes(2);

      pending.forEach((d) => d.resolve(null));
      await fetchPromise;
    });

    it('should keep task order even when the second task responds first', async () => {
      const slowTask1 = deferred<ReturnType<typeof taskDoc> | null>();
      vi.mocked(useFirestore.getTaskDocument).mockImplementation((_cls, taskId) =>
        taskId === '課題①'
          ? slowTask1.promise
          : Promise.resolve(taskDoc('課題②', 5, '2025-10-13T11:00:00.000Z'))
      );
      vi.mocked(useFirestore.getDocuments).mockImplementation(((_a: string, _b: string, _c: string, taskId: string) =>
        Promise.resolve(taskId === '課題①' ? [{ student_id: 'S001' }, { student_id: 'S002' }] : [{ student_id: 'S003' }])) as any);

      const { tasks, fetchTasks } = useTaskList(className);
      const fetchPromise = fetchTasks();

      // 課題② の応答が先に届き、課題① は最後に届く
      await Promise.resolve();
      slowTask1.resolve(taskDoc('課題①', 10, '2025-10-13T12:00:00.000Z'));
      await fetchPromise;

      expect(tasks.value.map((t) => t.taskId)).toEqual(['課題①', '課題②']);
      expect(tasks.value[0].studentCount).toBe(2);
      expect(tasks.value[1].studentCount).toBe(1);
    });

    it('should skip only the failed task and keep the other', async () => {
      vi.mocked(useFirestore.getTaskDocument).mockImplementation((_cls, taskId) =>
        taskId === '課題①'
          ? Promise.reject(new Error('boom'))
          : Promise.resolve(taskDoc('課題②', 5, '2025-10-13T11:00:00.000Z'))
      );
      vi.mocked(useFirestore.getDocuments).mockResolvedValue([{ student_id: 'S003' }] as any);

      const { tasks, error, fetchTasks } = useTaskList(className);
      await fetchTasks();

      expect(error.value).toBeNull();
      expect(tasks.value).toEqual([
        { taskId: '課題②', fileCount: 5, studentCount: 1, lastSubmit: '2025-10-13T11:00:00.000Z' },
      ]);
    });

    it('should return an empty list (not an error) when every request fails', async () => {
      // 現行挙動の固定: 全件失敗でもエラー表示にはせず、空の一覧を返す
      vi.mocked(useFirestore.getTaskDocument).mockRejectedValue(new Error('offline'));

      const { tasks, error, fetchTasks } = useTaskList(className);
      await fetchTasks();

      expect(error.value).toBeNull();
      expect(tasks.value).toEqual([]);
    });

    it('should return an empty list when no task documents exist', async () => {
      vi.mocked(useFirestore.getTaskDocument).mockResolvedValue(null);

      const { tasks, error, fetchTasks } = useTaskList(className);
      await fetchTasks();

      expect(useFirestore.getDocuments).not.toHaveBeenCalled();
      expect(error.value).toBeNull();
      expect(tasks.value).toEqual([]);
    });
  });
});
