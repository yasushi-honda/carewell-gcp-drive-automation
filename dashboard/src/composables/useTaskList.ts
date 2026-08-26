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
      const taskDataList: TaskData[] = [];

      // 各タスクの情報を取得
      for (const taskId of KNOWN_TASK_IDS) {
        try {
          // 親ドキュメント（タスクメタデータ）を取得
          const taskDoc = await getTaskDocument(className, taskId);

          if (taskDoc) {
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

            taskDataList.push({
              taskId: taskDoc.task_id,
              fileCount: taskDoc.file_count,
              studentCount: studentCount,
              lastSubmit: taskDoc.last_updated,
            });
          }
        } catch (taskError) {
          // 個別のタスク取得エラーは警告として記録し、スキップ
          console.warn(`Failed to fetch task metadata for ${className}/${taskId}:`, taskError);
        }
      }

      tasks.value = taskDataList;
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
