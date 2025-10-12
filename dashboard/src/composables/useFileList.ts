// src/composables/useFileList.ts
// ファイル一覧データの取得、検索、ソート機能

import { ref, computed, Ref, ComputedRef } from 'vue';
import { FileData, SortColumn, SortOrder } from '../types/models';
import { getDocuments, getErrorMessage } from './useFirestore';

interface UseFileListReturn {
  files: Ref<FileData[]>;
  loading: Ref<boolean>;
  error: Ref<string | null>;
  searchQuery: Ref<string>;
  sortColumn: Ref<SortColumn>;
  sortOrder: Ref<SortOrder>;
  filteredFiles: ComputedRef<FileData[]>;
  fetchFiles: () => Promise<void>;
  setSearch: (query: string) => void;
  setSortColumn: (column: SortColumn) => void;
}

/**
 * ファイル一覧データを取得・管理するComposable
 *
 * @param className - クラス名
 * @param taskId - タスクID
 * @returns ファイル一覧の状態、検索・ソート機能、取得関数
 *
 * @example
 * const { files, filteredFiles, loading, error, fetchFiles, setSearch, setSortColumn } =
 *   useFileList('令和7年度 デジタル中核人材養成研修 №01', '課題①');
 * await fetchFiles();
 * setSearch('森平');
 */
export function useFileList(className: string, taskId: string): UseFileListReturn {
  const files = ref<FileData[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const searchQuery = ref('');
  const sortColumn = ref<SortColumn>('submit_date');
  const sortOrder = ref<SortOrder>('desc');

  /**
   * 検索・ソート適用後のファイル一覧（computed）
   */
  const filteredFiles = computed(() => {
    let result = files.value;

    // 検索フィルタ（学生名・学生IDに部分一致）
    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase();
      result = result.filter(
        (file) =>
          file.student_name.toLowerCase().includes(query) ||
          file.student_id.toLowerCase().includes(query)
      );
    }

    // ソート
    result = [...result].sort((a, b) => {
      const aVal = a[sortColumn.value];
      const bVal = b[sortColumn.value];
      const compare = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
      return sortOrder.value === 'asc' ? compare : -compare;
    });

    return result;
  });

  /**
   * ファイル一覧を取得
   *
   * 実装方針:
   * - documentsサブコレクションから全ドキュメントを取得
   * - 親ドキュメントのfile_countと照合して整合性を確認可能
   */
  const fetchFiles = async (): Promise<void> => {
    loading.value = true;
    error.value = null;

    try {
      // documentsサブコレクションからファイル一覧を取得
      const documents = await getDocuments<FileData>(className, taskId, 'documents');

      files.value = documents.map((doc) => ({
        composite_key: doc.composite_key,
        student_id: doc.student_id,
        student_name: doc.student_name,
        filename: doc.filename,
        submit_date: doc.submit_date,
        drive_url: doc.drive_url,
      }));
    } catch (err) {
      error.value = getErrorMessage(err);
      console.error('Failed to fetch files:', err);
    } finally {
      loading.value = false;
    }
  };

  /**
   * 検索クエリを設定
   */
  const setSearch = (query: string): void => {
    searchQuery.value = query;
  };

  /**
   * ソートカラムを設定
   *
   * 同じカラムを再クリックした場合は昇順/降順を切り替え。
   * 異なるカラムをクリックした場合は昇順でソート開始。
   */
  const setSortColumn = (column: SortColumn): void => {
    if (sortColumn.value === column) {
      // 同じカラムをクリック → 昇順/降順切り替え
      sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc';
    } else {
      // 異なるカラムをクリック → 昇順でソート開始
      sortColumn.value = column;
      sortOrder.value = 'asc';
    }
  };

  return {
    files,
    loading,
    error,
    searchQuery,
    sortColumn,
    sortOrder,
    filteredFiles,
    fetchFiles,
    setSearch,
    setSortColumn,
  };
}
