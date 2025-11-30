// src/composables/useStudentSync.ts
// Cloud Run API を呼び出して学生データを同期する composable
//
// 使用方法:
// const { syncStudents, syncing, syncResult, syncError } = useStudentSync();
// await syncStudents();

import { ref, readonly } from 'vue';

/**
 * 同期結果の型定義
 */
export interface SyncResult {
  status: 'success' | 'error';
  students_synced?: number;
  students_created?: number;
  students_updated?: number;
  files_backfilled?: number;
  files_skipped?: number;
  errors?: Array<{ error: string }>;
  backfill_errors?: Array<{ file_id: string; error: string }>;
  error?: string;
}

/**
 * Cloud Run の同期 API エンドポイント
 */
const SYNC_API_URL =
  'https://carewell-file-collector-imczapxkba-an.a.run.app/admin/sync-students-from-sheets';

/**
 * 学生データ同期を管理する composable
 *
 * @returns {Object} 同期関連のリアクティブな値と関数
 */
export function useStudentSync() {
  const syncing = ref(false);
  const syncResult = ref<SyncResult | null>(null);
  const syncError = ref<string | null>(null);

  /**
   * 学生データを Google Sheets から Firestore に同期
   *
   * @param options - 同期オプション
   * @param options.backfill - 既存ファイルも更新するかどうか (デフォルト: true)
   * @returns 同期結果
   */
  const syncStudents = async (options: { backfill?: boolean } = {}): Promise<SyncResult> => {
    const { backfill = true } = options;

    syncing.value = true;
    syncResult.value = null;
    syncError.value = null;

    try {
      console.log('[useStudentSync] Starting sync with backfill:', backfill);

      const response = await fetch(SYNC_API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ backfill }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const result: SyncResult = await response.json();
      console.log('[useStudentSync] Sync completed:', result);

      syncResult.value = result;
      return result;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '同期に失敗しました';
      console.error('[useStudentSync] Sync failed:', error);
      syncError.value = errorMessage;
      syncResult.value = { status: 'error', error: errorMessage };
      throw error;
    } finally {
      syncing.value = false;
    }
  };

  /**
   * 同期状態をリセット
   */
  const resetSyncState = () => {
    syncResult.value = null;
    syncError.value = null;
  };

  return {
    // 状態 (readonly)
    syncing: readonly(syncing),
    syncResult: readonly(syncResult),
    syncError: readonly(syncError),

    // アクション
    syncStudents,
    resetSyncState,
  };
}
