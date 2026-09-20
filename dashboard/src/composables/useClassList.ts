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
   * - 全（クラス×課題）の親ドキュメント取得を同時に発行する
   *   （以前は for…await で1件ずつ待っており、往復回数ぶんだけ表示が遅れていた。
   *    計測: docs/dashboard-mobile-measurement.md）
   *
   * 互換性:
   * - 発行順・結果の並び順はクラス優先（KNOWN_CLASSES順、課題はKNOWN_TASK_IDS順）のまま
   * - 個別のタスク取得エラーは警告して読み飛ばす（全件失敗でもエラー扱いにせず fileCount=0 で返す現行挙動を維持）
   */
  const fetchClasses = async (): Promise<void> => {
    loading.value = true;
    error.value = null;

    try {
      // 全クラス×全課題の親ドキュメントを同時に取得（結果はクラス順・課題順の二次元配列）
      const taskDocsByClass = await Promise.all(
        KNOWN_CLASSES.map((className) =>
          Promise.all(
            KNOWN_TASK_IDS.map(async (taskId) => {
              try {
                // 親ドキュメント（タスクメタデータ）を取得
                return await getTaskDocument(className, taskId);
              } catch (taskError) {
                // 個別のタスク取得エラーは警告として記録し、スキップ
                console.warn(`Failed to fetch task data for ${className}/${taskId}:`, taskError);
                return null;
              }
            })
          )
        )
      );

      // 各クラスの統計情報を集計
      classes.value = KNOWN_CLASSES.map((className, classIndex): ClassData => {
        let totalFileCount = 0;
        let latestUpdate: string | null = null;
        let taskCount = 0;

        for (const taskDoc of taskDocsByClass[classIndex]) {
          if (!taskDoc) continue;

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

        return {
          name: className,
          taskCount: taskCount,
          fileCount: totalFileCount,
          lastUpdated: latestUpdate,
        };
      });
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
