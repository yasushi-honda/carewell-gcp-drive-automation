import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { defineComponent, h, ref } from 'vue';
import { useStudentSubmissions, summarizeByStudent, statusOf } from '../useStudentSubmissions';
import type { SubmissionFile } from '../useGroupStats';
import * as useFirestore from '../useFirestore';

vi.mock('../../config/firebase', () => ({ getDb: vi.fn(() => ({})) }));
vi.mock('../useFirestore', () => ({ getDocuments: vi.fn() }));

const CLASS_FULL = '令和8年度 デジタル中核人材養成研修 №01';
const TASK = '課題①';

function file(studentId: unknown, passStatus: unknown, submitDate: unknown = '2026/09/20 10:00:00'): SubmissionFile {
  return { student_id: studentId, submit_date: submitDate, metadata: { pass_status: passStatus } };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe('summarizeByStudent', () => {
  it('should return an empty map for no files', () => {
    expect(summarizeByStudent([])).toEqual({ byStudent: new Map(), unidentifiedFiles: 0 });
  });

  it('should use the latest submission as the current status, and report its date and the number of files', () => {
    const { byStudent } = summarizeByStudent([
      file('N1', '不合格', '2026/09/20 09:00:00'),
      file('N1', '合格', '2026/09/21 08:30:15'),
      file('N1', '不合格', '2026/09/19 12:00:00'),
    ]);

    expect(byStudent.get('N1')).toEqual({
      status: 'passed',
      latestSubmitDate: '2026/09/21 08:30:15',
      fileCount: 3,
    });
  });

  it('should treat a resubmission that is not graded yet as pending (the latest wins over an older pass)', () => {
    const { byStudent } = summarizeByStudent([
      file('N1', '合格', '2026/09/20 09:00:00'),
      file('N1', '', '2026/09/22 09:00:00'),
    ]);

    expect(byStudent.get('N1')?.status).toBe('pending');
  });

  it('should keep each student separate and trim the student id', () => {
    const { byStudent } = summarizeByStudent([file(' N1 ', '合格'), file('N2', '不合格')]);

    expect([...byStudent.keys()].sort()).toEqual(['N1', 'N2']);
    expect(byStudent.get('N1')?.status).toBe('passed');
    expect(byStudent.get('N2')?.status).toBe('failed');
  });

  it('should give an empty date when the submit date is missing or not a string', () => {
    // undefined を渡すと file() の既定値になってしまうため、欠損は null で表す
    const { byStudent } = summarizeByStudent([file('N1', '合格', null), file('N2', '合格', 20260920)]);

    expect(byStudent.get('N1')?.latestSubmitDate).toBe('');
    expect(byStudent.get('N2')?.latestSubmitDate).toBe('');
  });

  it('should count files without a usable student id instead of attributing them to someone', () => {
    const { byStudent, unidentifiedFiles } = summarizeByStudent([
      file('', '合格'),
      file('  ', '合格'),
      file(undefined, '合格'),
      file(123, '合格'),
      file('N1', '合格'),
    ]);

    expect(unidentifiedFiles).toBe(4);
    expect([...byStudent.keys()]).toEqual(['N1']);
  });
});

describe('statusOf', () => {
  it('should be not_submitted for a student without files, and the current status otherwise', () => {
    const { byStudent } = summarizeByStudent([file('N1', '合格')]);

    expect(statusOf(byStudent, 'N1')).toBe('passed');
    expect(statusOf(byStudent, 'N2')).toBe('not_submitted');
  });
});

describe('useStudentSubmissions', () => {
  const getDocuments = vi.mocked(useFirestore.getDocuments);

  beforeEach(() => {
    getDocuments.mockReset();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function mountComposable(className: unknown = CLASS_FULL, taskId: unknown = TASK, enabled: unknown = true) {
    let result!: ReturnType<typeof useStudentSubmissions>;
    const Host = defineComponent({
      setup() {
        result = useStudentSubmissions(className as never, taskId as never, enabled as never);
        return () => h('div');
      },
    });
    const wrapper = mount(Host);
    return { result, wrapper };
  }

  it('should read the files of this class and task, showing loading until they arrive', async () => {
    const files = deferred<SubmissionFile[]>();
    getDocuments.mockReturnValue(files.promise as never);

    const { result } = mountComposable();
    expect(result.state.value).toBe('loading');
    expect(getDocuments).toHaveBeenCalledWith('submissions', CLASS_FULL, 'tasks', TASK, 'files');

    files.resolve([file('N1', '合格'), file('', '合格')]);
    await flushPromises();

    expect(result.state.value).toBe('ready');
    expect(result.byStudent.value.get('N1')?.status).toBe('passed');
    expect(result.fileCount.value).toBe(2);
    expect(result.unidentifiedFiles.value).toBe(1);
  });

  it('should not request the files until enabled (so it never slows the first paint of the list), then load once', async () => {
    getDocuments.mockResolvedValue([file('N1', '合格')]);
    const enabled = ref(false);

    const { result } = mountComposable(CLASS_FULL, TASK, enabled);
    await flushPromises();

    expect(getDocuments).not.toHaveBeenCalled();
    expect(result.state.value).toBe('loading');

    enabled.value = true;
    await flushPromises();

    expect(getDocuments).toHaveBeenCalledTimes(1);
    expect(result.state.value).toBe('ready');
    expect(result.byStudent.value.get('N1')?.status).toBe('passed');
  });

  it('should be ready with nobody submitted when the task has no files (not an error)', async () => {
    getDocuments.mockResolvedValue([]);

    const { result } = mountComposable();
    await flushPromises();

    expect(result.state.value).toBe('ready');
    expect(result.byStudent.value.size).toBe(0);
    expect(result.fileCount.value).toBe(0);
  });

  it('should report an error on failure and never fall back to "nobody submitted"', async () => {
    getDocuments.mockRejectedValue(new Error('permission-denied'));

    const { result } = mountComposable();
    await flushPromises();

    expect(result.state.value).toBe('error');
    expect(result.byStudent.value.size).toBe(0);
  });

  it('should recover with refetch', async () => {
    getDocuments.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce([file('N1', '不合格')]);

    const { result } = mountComposable();
    await flushPromises();
    expect(result.state.value).toBe('error');

    const retry = result.refetch();
    expect(result.state.value).toBe('loading');
    await retry;

    expect(result.state.value).toBe('ready');
    expect(result.byStudent.value.get('N1')?.status).toBe('failed');
  });

  it('should ignore a stale response that arrives after a newer request', async () => {
    const first = deferred<SubmissionFile[]>();
    const second = deferred<SubmissionFile[]>();
    getDocuments.mockReturnValueOnce(first.promise as never).mockReturnValueOnce(second.promise as never);

    const { result } = mountComposable();
    const retry = result.refetch();

    second.resolve([file('N2', '合格')]);
    await retry;
    first.resolve([file('N1', '不合格')]);
    await flushPromises();

    expect([...result.byStudent.value.keys()]).toEqual(['N2']);
    expect(result.state.value).toBe('ready');
  });

  it('should ignore a stale failure that arrives after a newer request', async () => {
    const first = deferred<SubmissionFile[]>();
    getDocuments.mockReturnValueOnce(first.promise as never).mockResolvedValueOnce([file('N2', '合格')]);

    const { result } = mountComposable();
    await result.refetch();
    first.reject(new Error('late failure'));
    await flushPromises();

    expect(result.state.value).toBe('ready');
    expect([...result.byStudent.value.keys()]).toEqual(['N2']);
  });

  it('should refetch when the task changes under the same view', async () => {
    getDocuments.mockResolvedValueOnce([file('N1', '合格')]).mockResolvedValueOnce([]);
    const taskId = ref('課題①');

    const { result } = mountComposable(CLASS_FULL, taskId);
    await flushPromises();
    expect(result.byStudent.value.size).toBe(1);

    taskId.value = '課題②';
    await flushPromises();

    expect(getDocuments).toHaveBeenLastCalledWith('submissions', CLASS_FULL, 'tasks', '課題②', 'files');
    expect(result.byStudent.value.size).toBe(0);
  });
});
