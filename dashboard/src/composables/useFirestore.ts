// src/composables/useFirestore.ts
// Firestore data access layer
//
// Phase 2 認証対応について:
// このファイルは認証対応のための変更は不要です。
// Firebase SDKが自動的に認証トークンをリクエストに含めるため、
// Firestore Security Rulesの変更だけで認証制御が可能です。
//
// Phase 2での変更点:
// - firestore.rules を変更: allow read: if request.auth != null;
// - useAuth.ts を追加（認証状態管理）
// - LoginView.vue を追加（ログイン画面）
// - Router に認証ガードを追加
//
// 参考: docs/phase2-authentication-design.md

import { getDb } from '../config/firebase';
import {
  collection,
  getDocs,
  doc,
  getDoc,
  DocumentData,
  CollectionReference,
  DocumentSnapshot,
} from 'firebase/firestore';
import { FirestoreTaskDocument } from '../types/models';

/**
 * Helper function to recursively convert Firestore Timestamps to ISO 8601 strings
 *
 * @param obj - Object potentially containing Timestamp fields
 * @returns Object with all Timestamps converted to strings
 */
function convertTimestampsToStrings(obj: any): any {
  if (obj === null || obj === undefined) {
    return obj;
  }

  // Check if it's a Firestore Timestamp
  if (obj.toDate && typeof obj.toDate === 'function') {
    return obj.toDate().toISOString();
  }

  // If it's an array, convert each element
  if (Array.isArray(obj)) {
    return obj.map((item) => convertTimestampsToStrings(item));
  }

  // If it's an object, convert each property
  if (typeof obj === 'object') {
    const converted: any = {};
    for (const key in obj) {
      if (Object.prototype.hasOwnProperty.call(obj, key)) {
        converted[key] = convertTimestampsToStrings(obj[key]);
      }
    }
    return converted;
  }

  return obj;
}

/**
 * 汎用ドキュメント取得関数
 *
 * @param collectionPath - コレクションパス（例: "令和8年度 デジタル中核人材養成研修 №01"）
 * @param pathSegments - 追加のパスセグメント（例: ["課題①", "documents"]）
 * @returns ドキュメントの配列
 *
 * @example
 * // クラス内の課題一覧を取得
 * const tasks = await getDocuments("令和8年度 デジタル中核人材養成研修 №01");
 *
 * // 特定課題のファイル一覧を取得
 * const files = await getDocuments("令和8年度 デジタル中核人材養成研修 №01", "課題①", "documents");
 */
export async function getDocuments<T = DocumentData>(
  collectionPath: string,
  ...pathSegments: string[]
): Promise<T[]> {
  try {
    const db = getDb();
    const colRef: CollectionReference<DocumentData> = collection(db, collectionPath, ...pathSegments);
    const snapshot = await getDocs(colRef);

    return snapshot.docs.map((doc) => {
      const data = doc.data();
      // Convert all Timestamp fields to ISO strings
      const convertedData = convertTimestampsToStrings(data);
      return {
        id: doc.id,
        ...convertedData,
      } as T;
    });
  } catch (error) {
    console.error('Firestore getDocuments error:', {
      collectionPath,
      pathSegments,
      error,
    });
    throw error;
  }
}

/**
 * 親ドキュメント（タスクメタデータ）を取得
 *
 * Firestore Schema Improvementで追加された親ドキュメントから、
 * file_count, last_updatedなどのメタデータを効率的に取得する。
 *
 * @param className - クラス名（例: "令和8年度 デジタル中核人材養成研修 №01"）
 * @param taskId - タスクID（例: "課題①"）
 * @returns 親ドキュメントデータ、存在しない場合はnull
 *
 * @example
 * const taskDoc = await getTaskDocument("令和8年度 デジタル中核人材養成研修 №01", "課題①");
 * if (taskDoc) {
 *   console.log(`File count: ${taskDoc.file_count}`);
 *   console.log(`Last updated: ${taskDoc.last_updated}`);
 * }
 */
export async function getTaskDocument(
  className: string,
  taskId: string
): Promise<FirestoreTaskDocument | null> {
  try {
    const db = getDb();
    const docRef = doc(db, "submissions", className, "tasks", taskId);
    const docSnap: DocumentSnapshot<DocumentData> = await getDoc(docRef);

    if (docSnap.exists()) {
      const data = docSnap.data();

      // Convert Firestore Timestamps to ISO 8601 strings
      // Firestore returns Timestamp objects for timestamp fields, which need to be converted
      const taskDoc: FirestoreTaskDocument = {
        task_id: data.task_id,
        task_pattern: data.task_pattern,
        file_count: data.file_count,
        created_at: data.created_at?.toDate ? data.created_at.toDate().toISOString() : data.created_at,
        last_updated: data.last_updated?.toDate ? data.last_updated.toDate().toISOString() : data.last_updated,
      };

      return taskDoc;
    }
    return null;
  } catch (error) {
    console.error('Firestore getTaskDocument error:', {
      className,
      taskId,
      error,
    });
    throw error;
  }
}

/**
 * Firestoreエラーハンドリングヘルパー
 *
 * @param error - キャッチされたエラー
 * @returns ユーザーフレンドリーなエラーメッセージ
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    // Firestore permission denied
    if (error.message.includes('permission-denied')) {
      return 'アクセス権限がありません';
    }

    // Network error
    if (error.message.includes('Failed to fetch') || error.message.includes('network')) {
      return 'ネットワーク接続を確認してください';
    }

    // Generic error
    return `データの取得に失敗しました: ${error.message}`;
  }

  return 'データの取得に失敗しました';
}
