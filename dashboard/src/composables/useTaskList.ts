// src/composables/useTaskList.ts
// 課題一覧データの取得と状態管理

import { ref, Ref } from 'vue';
import { TaskData } from '../types/models';
import { KNOWN_TASK_IDS } from '../config/classes';
import { getTaskDocument, getDocuments, getErrorMessage } from './useFirestore';

interface UseTaskListReturn {
  tasks: Ref<TaskData[]>;
  loading: Ref<boolean>;
  error: Ref<string | null>;
  fetchTasks: () => Promise<void>;
}

/**
 * 課題一覧データを取得・管理するComposable
 *
 * @param className - クラス名
 * @returns 課題一覧の状態と取得関数
 *
 * @example
 * const { tasks, loading, error, fetchTasks } = useTaskList('令和8年度 デジタル中核人材養成研修 №01');
 * await fetchTasks();
 */
export function useTaskList(className: string): UseTaskListReturn {
  const tasks = ref<TaskData[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  /**
   * 課題一覧を取得
   *
   * 実装方針（Firestore Schema Improvement対応）:
   * 1. 親ドキュメント（{className}/{taskId}）からメタデータを取得
   * 2. file_count: 親ドキュメントから直接取得（サブコレクションスキャン不要）
   * 3. last_updated: 親ドキュメントから直接取得（最終提出日時）
   * 4. studentCount: サブコレクションからユニークstudent_idの数を計算
   *
   * パフォーマンス向上:
   * - ファイル数と最終更新日時はメタデータから即座に取得可能
   * - サブコレクションスキャンは学生数計算のみ
   */
  const fetchTasks = async (): Promise<void> => {
    loading.value = true;
    error.value = null;

    try {
      // 各タスクの情報を同時に取得（結果の並びはKNOWN_TASK_IDS順のまま。
      // 以前は for…await で課題ごとに直列に待っていた）
      const taskDataResults = await Promise.all(
        KNOWN_TASK_IDS.map(async (taskId): Promise<TaskData | null> => {
          try {
            // 親ドキュメント（タスクメタデータ）を取得
            const taskDoc = await getTaskDocument(className, taskId);

            if (!taskDoc) return null;

            // studentCount算出: サブコレクションからユニークなstudent_idをカウント
            let studentCount = 0;
            try {
              const documents = await getDocuments("submissions", className, "tasks", taskId, 'files');
              const uniqueStudents = new Set(
                documents.map((doc: any) => doc.student_id).filter(Boolean)
              );
              studentCount = uniqueStudents.size;
            } catch (docError) {
              console.warn(`Failed to fetch documents for ${className}/${taskId}:`, docError);
              // エラーの場合は0とする
              studentCount = 0;
            }

            return {
              taskId: taskDoc.task_id,
              fileCount: taskDoc.file_count,
              studentCount: studentCount,
              lastSubmit: taskDoc.last_updated,
            };
          } catch (taskError) {
            // 個別のタスク取得エラーは警告として記録し、スキップ
            console.warn(`Failed to fetch task metadata for ${className}/${taskId}:`, taskError);
            return null;
          }
        })
      );

      tasks.value = taskDataResults.filter((task): task is TaskData => task !== null);
    } catch (err) {
      error.value = getErrorMessage(err);
      console.error('Failed to fetch tasks:', err);
    } finally {
      loading.value = false;
    }
  };

  return {
    tasks,
    loading,
    error,
    fetchTasks,
  };
}
