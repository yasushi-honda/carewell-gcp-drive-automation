// src/composables/useClassList.ts
// クラス一覧データの取得と状態管理

import { ref, Ref } from 'vue';
import { ClassData } from '../types/models';
import { KNOWN_CLASSES, KNOWN_TASK_IDS } from '../config/classes';
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
   * 2. KNOWN_TASK_IDSから既知のタスクIDリストを取得
   * 3. 各クラス×タスクのdocumentsサブコレクションから統計情報を集計
   *
   * Note: Firestoreではサブコレクション（documents）にデータがあっても、
   * 親ドキュメント（task_id）自体は自動作成されないため、
   * 既知のタスクIDリストを使用して直接documentsサブコレクションを確認する。
   */
  const fetchClasses = async (): Promise<void> => {
    loading.value = true;
    error.value = null;

    try {
      const classDataList: ClassData[] = [];

      // 各クラスの統計情報を取得
      for (const className of KNOWN_CLASSES) {
        try {
          // 各課題配下のファイル数を集計
          let totalFileCount = 0;
          let latestUpdate: string | null = null;
          let taskCountWithFiles = 0;

          // 既知のタスクIDを使って直接documentsサブコレクションを確認
          for (const taskId of KNOWN_TASK_IDS) {
            try {
              // documents サブコレクションからファイル一覧を取得
              const files = await getDocuments(className, taskId, 'documents');

              if (files.length > 0) {
                taskCountWithFiles++;
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
            } catch (taskError) {
              // 個別のタスク取得エラーは警告として記録し、スキップ
              console.warn(`Failed to fetch task data for ${className}/${taskId}:`, taskError);
            }
          }

          classDataList.push({
            name: className,
            taskCount: taskCountWithFiles,
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
