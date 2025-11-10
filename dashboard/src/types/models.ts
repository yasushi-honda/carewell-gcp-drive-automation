// src/types/models.ts
// Domain models for Carewell Dashboard

/**
 * クラス情報
 */
export interface ClassData {
  name: string;
  taskCount: number;
  fileCount: number;
  lastUpdated: string | null;
}

/**
 * 課題情報
 */
export interface TaskData {
  taskId: string;
  fileCount: number;
  studentCount: number;
  lastSubmit: string | null;
}

/**
 * ファイル提出情報（UI表示用）
 */
export interface FileData {
  composite_key: string;
  student_id: string;
  student_name: string;
  filename: string;
  submit_date: string;
  drive_file_id: string; // Google Drive file ID (URLは動的生成)
  task_id?: string; // タスクID（例: "課題①"）
  task_pattern?: string; // タスク表示名（例: "課題①業務分析"）

  /**
   * 合否情報（オプショナル）
   * 既存データでは undefined の可能性がある
   */
  metadata?: {
    pass_status?: string; // "合格" | "不合格"
    score?: string; // "0点 / 1点" 形式
    grading_status?: string; // "採点済み" | "未採点"
    log_no?: string; // ログ番号（文字列）
  };

  /**
   * 学生メタデータ（非正規化フィールド）
   * 既存データには存在しない可能性があるためオプショナル
   */
  student_furigana?: string;         // ふりがな
  student_group?: string;            // グループ
  student_service_type?: string;     // サービス種別
  student_number?: string;           // 学生番号（例: "A014"）
  student_company?: string;          // 会社名
  student_office?: string;           // 事業所名
  student_status?: string;           // ステータス
  student_serial_number?: number;    // 連番
}

/**
 * Firestoreドキュメント（完全な情報）
 */
export interface FirestoreDocument {
  composite_key: string;
  student_id: string;
  student_name: string;
  filename: string;
  submit_date: string;
  drive_file_id: string;
  drive_url: string;
  uploaded_at: string;
}

/**
 * 親ドキュメント（タスクメタデータ）
 *
 * Firestore Schema Improvementで追加された親ドキュメント構造。
 * file_count, last_updatedフィールドにより、サブコレクションをスキャンせずに
 * 統計情報を効率的に取得できる。
 */
export interface FirestoreTaskDocument {
  task_id: string;
  task_pattern: string;
  file_count: number;
  created_at: string; // Firestore Timestamp (ISO 8601)
  last_updated: string; // Firestore Timestamp (ISO 8601)
}

/**
 * ソートカラム
 */
export type SortColumn = 'student_name' | 'submit_date';

/**
 * ソート順序
 */
export type SortOrder = 'asc' | 'desc';

/**
 * 学生情報（students コレクション）
 *
 * 受講生マスターデータ。Google Sheets「統合_受講者リスト」から同期される。
 */
export interface Student {
  student_id: string;       // 日介番号（例: "N0102490"）
  name: string;             // 氏名（例: "田谷　佳寿樹"）
  furigana: string;         // ふりがな（例: "たや　かずき"）
  group: string;            // グループ（例: "A", "B", "C"）
  company: string;          // 勤務先法人名称
  office: string;           // 勤務先名称（事業所）
  service_type: string;     // サービス種別（例: "入所・居住系", "通所系"）
  serial_number: number;    // 通し番号（例: 14）
  student_number: string;   // 学生番号（例: "A014"）
  status: string;           // ステータス（例: "active"）
  created_at?: Date;        // 作成日時
  last_updated?: Date;      // 更新日時
}
