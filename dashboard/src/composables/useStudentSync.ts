// src/composables/useStudentSync.ts
// Cloud Run API を呼び出して学生データを同期する composable
//
// 使用方法:
// const { syncStudents, syncing, syncResult, syncError } = useStudentSync();
// await syncStudents();

import { ref, readonly } from 'vue';
import { useAuth } from './useAuth';

/**
 * クラス別の同期結果（/admin/sync-students-from-attendance-rosters のレスポンス）
 */
export interface ClassSyncSummary {
  class_name: string;
  status: string; // "ok" | "empty" | "read_error" | "schema_error"
  student_count?: number; // フェーズAのみ実行時(dry_run/aborted)に含まれる
  synced?: number;
  created?: number;
  updated?: number;
  withdrawn?: number;
  write_failed?: number;
}

export interface ErrorClassInfo {
  class_name: string;
  status: string;
  error: string | null;
}

export interface MalformedRowsSummary {
  class_name: string;
  rows: Array<{ row: number; name: string; student_id: string }>;
}

export interface DuplicateStudentIdInfo {
  student_id: string;
  classes: string[];
}

/**
 * 同期結果の型定義
 *
 * status:
 * - "success": フェーズB(書込み)まで完了、またはdry_run/preflightが正常に完了
 * - "partial_failure": フェーズBは実行されたが、一部クラスでcreate_student()や
 *   reconcile(退会検出)の書込みが失敗した(classes[].write_failed > 0)。
 *   同期処理自体は完走しているため"aborted"とは区別する
 * - "aborted": フェーズAで異常(read_error/schema_error/重複/malformed_rows)を検出し、
 *   Firestoreへは書き込まずに中断した(fail-closed)。診断情報は各フィールド参照
 * - "error": ハンドラ自体で例外が発生した
 */
export interface SyncResult {
  status: 'success' | 'partial_failure' | 'aborted' | 'error';
  dry_run?: boolean;
  classes?: ClassSyncSummary[];
  not_configured_classes?: string[];
  error_classes?: ErrorClassInfo[];
  malformed_rows?: MalformedRowsSummary[];
  duplicate_student_ids?: DuplicateStudentIdInfo[];
  error?: string;
}

/**
 * Cloud Run の同期 API エンドポイント
 *
 * 令和8年度は出欠名簿(クラス別受講者リスト)経由の同期に統一されている。
 * 旧エンドポイント(/admin/sync-students-from-sheets、統合_受講者リスト経由)は
 * 令和8年度中は409を返すため使用しない（src/main.pyのsync_students_from_sheets()
 * 参照）。
 */
const SYNC_API_URL =
  'https://carewell-file-collector-imczapxkba-an.a.run.app/admin/sync-students-from-attendance-rosters';

/**
 * 学生データ同期を管理する composable
 *
 * @returns {Object} 同期関連のリアクティブな値と関数
 */
export function useStudentSync() {
  const syncing = ref(false);
  const syncResult = ref<SyncResult | null>(null);
  const syncError = ref<string | null>(null);
  const { getIdToken } = useAuth();

  /**
   * 学生データを出欠管理ファイル(クラス別受講者リスト)から Firestore に同期
   *
   * @param options - 同期オプション
   * @param options.dryRun - trueの場合、読み取り・検証のみ行いFirestoreへは
   *   書き込まない(preflight用。既定: false)
   * @returns 同期結果
   */
  const syncStudents = async (options: { dryRun?: boolean } = {}): Promise<SyncResult> => {
    const { dryRun = false } = options;

    syncing.value = true;
    syncResult.value = null;
    syncError.value = null;

    try {
      console.log('[useStudentSync] Starting sync with dryRun:', dryRun);

      const token = await getIdToken();
      if (!token) {
        throw new Error('管理者ログインが必要です');
      }

      const response = await fetch(SYNC_API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ dry_run: dryRun }),
      });

      if (response.status === 401) {
        throw new Error('セッションが切れました。再ログインしてください');
      }
      if (response.status === 403) {
        throw new Error('管理者権限がありません');
      }
      // 409は「フェーズAで異常検出→書込み中断」の正常な業務レスポンスでもあるため
      // (aborted)、ここではHTTPエラーとして弾かず、通常通りJSONをパースして返す。
      if (!response.ok && response.status !== 409) {
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
