// src/composables/useClassList.ts
// クラス一覧データの取得と状態管理

import { ref, Ref } from 'vue';
import { ClassData } from '../types/models';
import { KNOWN_CLASSES, KNOWN_TASK_IDS } from '../config/classes';
import { getTaskDocument, getErrorMessage } from './useFirestore';

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
   * 実装方針（Firestore Schema Improvement対応）:
   * 1. KNOWN_CLASSESから既知のクラス名リストを取得
   * 2. KNOWN_TASK_IDSから既知のタスクIDリストを取得
   * 3. 各クラス×タスクの親ドキュメント（{className}/{taskId}）からメタデータを取得
   * 4. 親ドキュメントのfile_count, last_updatedフィールドを活用して統計情報を集計
   *
   * パフォーマンス向上:
   * - サブコレクション（documents）の全スキャンが不要
   * - 親ドキュメントのメタデータから直接統計情報を取得
   * - Firestoreクエリコストを大幅削減
   */
  const fetchClasses = async (): Promise<void> => {
    loading.value = true;
    error.value = null;

    try {
      const classDataList: ClassData[] = [];

      // 各クラスの統計情報を取得
      for (const className of KNOWN_CLASSES) {
        try {
          let totalFileCount = 0;
          let latestUpdate: string | null = null;
          let taskCount = 0;

          // 親ドキュメントからメタデータを取得
          for (const taskId of KNOWN_TASK_IDS) {
            try {
              // 親ドキュメント（タスクメタデータ）を取得
              const taskDoc = await getTaskDocument(className, taskId);

              if (taskDoc) {
                // 親ドキュメントが存在する場合、メタデータから統計情報を取得
                taskCount++;
                totalFileCount += taskDoc.file_count;

                // 最終更新日時を比較
                if (taskDoc.last_updated) {
                  if (!latestUpdate || taskDoc.last_updated > latestUpdate) {
                    latestUpdate = taskDoc.last_updated;
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
            taskCount: taskCount,
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
