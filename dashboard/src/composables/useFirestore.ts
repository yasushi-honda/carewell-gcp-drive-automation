// src/composables/useFirestore.ts
// Firestore data access layer

import { getDb } from '../config/firebase';
import { collection, getDocs, DocumentData, CollectionReference } from 'firebase/firestore';

/**
 * 汎用ドキュメント取得関数
 *
 * @param collectionPath - コレクションパス（例: "令和7年度 デジタル中核人材養成研修 №01"）
 * @param pathSegments - 追加のパスセグメント（例: ["課題①", "documents"]）
 * @returns ドキュメントの配列
 *
 * @example
 * // クラス内の課題一覧を取得
 * const tasks = await getDocuments("令和7年度 デジタル中核人材養成研修 №01");
 *
 * // 特定課題のファイル一覧を取得
 * const files = await getDocuments("令和7年度 デジタル中核人材養成研修 №01", "課題①", "documents");
 */
export async function getDocuments<T = DocumentData>(
  collectionPath: string,
  ...pathSegments: string[]
): Promise<T[]> {
  try {
    const db = getDb();
    const colRef: CollectionReference<DocumentData> = collection(db, collectionPath, ...pathSegments);
    const snapshot = await getDocs(colRef);

    return snapshot.docs.map((doc) => ({
      id: doc.id,
      ...doc.data(),
    })) as T[];
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
