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
  drive_url: string;
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
