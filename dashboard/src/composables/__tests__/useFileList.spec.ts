import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useFileList } from '../useFileList';
import * as useFirestore from '../useFirestore';
import type { FileData } from '../../types/models';

// Mock useFirestore
vi.mock('../useFirestore', () => ({
  getDocuments: vi.fn(),
  getErrorMessage: vi.fn((err) => `Error: ${err.message}`),
}));

describe('useFileList', () => {
  const className = '令和8年度 デジタル中核人材養成研修 №01';
  const taskId = '課題①';

  const mockFiles: FileData[] = [
    {
      composite_key: 'key1',
      student_id: 'S001',
      student_name: '森平太郎',
      filename: 'report1.pdf',
      submit_date: '2025/10/13 10:00:00',
      drive_file_id: 'drive-id-1',
    },
    {
      composite_key: 'key2',
      student_id: 'S002',
      student_name: '田中花子',
      filename: 'report2.pdf',
      submit_date: '2025/10/13 09:00:00',
      drive_file_id: 'drive-id-2',
    },
    {
      composite_key: 'key3',
      student_id: 'S003',
      student_name: '佐藤次郎',
      filename: 'report3.pdf',
      submit_date: '2025/10/13 11:00:00',
      drive_file_id: 'drive-id-3',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch files successfully', async () => {
    vi.mocked(useFirestore.getDocuments).mockResolvedValue(mockFiles as any);

    const { files, loading, error, fetchFiles } = useFileList(className, taskId);

    await fetchFiles();

    expect(loading.value).toBe(false);
    expect(error.value).toBeNull();
    expect(files.value).toEqual(mockFiles);
  });

  it('should filter files by search query (student name)', async () => {
    vi.mocked(useFirestore.getDocuments).mockResolvedValue(mockFiles as any);

    const { filteredFiles, fetchFiles, setSearch } = useFileList(className, taskId);

    await fetchFiles();
    setSearch('森平');

    expect(filteredFiles.value).toHaveLength(1);
    expect(filteredFiles.value[0].student_name).toBe('森平太郎');
  });

  it('should filter files by search query (student ID)', async () => {
    vi.mocked(useFirestore.getDocuments).mockResolvedValue(mockFiles as any);

    const { filteredFiles, fetchFiles, setSearch } = useFileList(className, taskId);

    await fetchFiles();
    setSearch('S002');

    expect(filteredFiles.value).toHaveLength(1);
    expect(filteredFiles.value[0].student_id).toBe('S002');
  });

  it('should sort files by student name (ascending)', async () => {
    vi.mocked(useFirestore.getDocuments).mockResolvedValue(mockFiles as any);

    const { filteredFiles, fetchFiles, setSortColumn } = useFileList(className, taskId);

    await fetchFiles();
    setSortColumn('student_name');

    // Unicode順: 佐(U+4F50) < 森(U+68EE) < 田(U+7530)
    expect(filteredFiles.value[0].student_name).toBe('佐藤次郎');
    expect(filteredFiles.value[1].student_name).toBe('森平太郎');
    expect(filteredFiles.value[2].student_name).toBe('田中花子');
  });

  it('should sort files by student name (descending)', async () => {
    vi.mocked(useFirestore.getDocuments).mockResolvedValue(mockFiles as any);

    const { filteredFiles, fetchFiles, setSortColumn } = useFileList(className, taskId);

    await fetchFiles();
    setSortColumn('student_name'); // First click: asc
    setSortColumn('student_name'); // Second click: desc

    // Unicode降順: 田(U+7530) > 森(U+68EE) > 佐(U+4F50)
    expect(filteredFiles.value[0].student_name).toBe('田中花子');
    expect(filteredFiles.value[1].student_name).toBe('森平太郎');
    expect(filteredFiles.value[2].student_name).toBe('佐藤次郎');
  });

  it('should sort files by submit date (descending by default)', async () => {
    vi.mocked(useFirestore.getDocuments).mockResolvedValue(mockFiles as any);

    const { filteredFiles, fetchFiles } = useFileList(className, taskId);

    await fetchFiles();

    // Default sort: submit_date desc
    expect(filteredFiles.value[0].submit_date).toBe('2025/10/13 11:00:00');
    expect(filteredFiles.value[1].submit_date).toBe('2025/10/13 10:00:00');
    expect(filteredFiles.value[2].submit_date).toBe('2025/10/13 09:00:00');
  });

  it('should combine search and sort', async () => {
    vi.mocked(useFirestore.getDocuments).mockResolvedValue(mockFiles as any);

    const { filteredFiles, fetchFiles, setSearch, setSortColumn } = useFileList(className, taskId);

    await fetchFiles();
    setSearch('郎'); // Matches "森平太郎" and "佐藤次郎"
    setSortColumn('student_name');

    expect(filteredFiles.value).toHaveLength(2);
    expect(filteredFiles.value[0].student_name).toBe('佐藤次郎');
    expect(filteredFiles.value[1].student_name).toBe('森平太郎');
  });

  it('should handle fetch errors', async () => {
    const mockError = new Error('Fetch error');
    vi.mocked(useFirestore.getDocuments).mockRejectedValue(mockError);
    vi.mocked(useFirestore.getErrorMessage).mockReturnValue('Error: Fetch error');

    const { error, fetchFiles } = useFileList(className, taskId);

    await fetchFiles();

    expect(error.value).toBe('Error: Fetch error');
  });

  it('should set loading state correctly', async () => {
    vi.mocked(useFirestore.getDocuments).mockResolvedValue(mockFiles as any);

    const { loading, fetchFiles } = useFileList(className, taskId);

    expect(loading.value).toBe(false);

    const fetchPromise = fetchFiles();
    expect(loading.value).toBe(true);

    await fetchPromise;
    expect(loading.value).toBe(false);
  });
});
