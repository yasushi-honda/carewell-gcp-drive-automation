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
  const className = '令和7年度 デジタル中核人材養成研修 №01';

  beforeEach(() => {
    vi.clearAllMocks();
  });

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
});
