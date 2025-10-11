// src/composables/useClassList.ts
// クラス一覧データの取得と状態管理

import { ref, Ref } from 'vue';
import { ClassData } from '../types/models';
import { KNOWN_CLASSES } from '../config/classes';
import { getDocuments, getErrorMessage } from './useFirestore';

interface UseClassListReturn {
  classes: Ref<ClassData[]>;
  loading: Ref<boolean>;
  error: Ref<string | null>;
  fetchClasses: () => Promise<void>;
}

/**
 * クラス一覧データを取得・管理するComposable
 *
 * @returns クラス一覧の状態と取得関数
 *
 * @example
 * const { classes, loading, error, fetchClasses } = useClassList();
 * await fetchClasses();
 */
export function useClassList(): UseClassListReturn {
  const classes = ref<ClassData[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  /**
   * クラス一覧を取得
   *
   * 実装方針:
   * 1. KNOWN_CLASSESから既知のクラス名リストを取得
   * 2. 各クラスのFirestoreコレクションから課題情報を取得
   * 3. 統計情報（課題数、ファイル数、最終更新日時）を集計
   */
  const fetchClasses = async (): Promise<void> => {
    loading.value = true;
    error.value = null;

    try {
      const classDataList: ClassData[] = [];

      // 各クラスの統計情報を取得
      for (const className of KNOWN_CLASSES) {
        try {
          // Firestoreコレクション: {className}/ 配下のドキュメント（課題）を取得
          // 各ドキュメントIDが課題ID（例: "課題①"）
          const tasks = await getDocuments(className);

          // 課題数を集計
          const taskCount = tasks.length;

          // 各課題配下のファイル数を集計
          let totalFileCount = 0;
          let latestUpdate: string | null = null;

          for (const task of tasks) {
            const taskId = task.id;

            // documents サブコレクションからファイル一覧を取得
            const files = await getDocuments(className, taskId, 'documents');
            totalFileCount += files.length;

            // 最終更新日時を取得（uploaded_at フィールド）
            for (const file of files) {
              const uploadedAt = (file as any).uploaded_at;
              if (uploadedAt) {
                if (!latestUpdate || uploadedAt > latestUpdate) {
                  latestUpdate = uploadedAt;
                }
              }
            }
          }

          classDataList.push({
            name: className,
            taskCount,
            fileCount: totalFileCount,
            lastUpdated: latestUpdate,
          });
        } catch (classError) {
          // 個別のクラス取得エラーは警告として記録し、スキップ
          console.warn(`Failed to fetch class data for ${className}:`, classError);
        }
      }

      classes.value = classDataList;
    } catch (err) {
      error.value = getErrorMessage(err);
      console.error('Failed to fetch classes:', err);
    } finally {
      loading.value = false;
    }
  };

  return {
    classes,
    loading,
    error,
    fetchClasses,
  };
}
