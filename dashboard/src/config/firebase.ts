// src/config/firebase.ts
// Firebase configuration and initialization

import { initializeApp, FirebaseApp } from 'firebase/app';
import { getFirestore, Firestore } from 'firebase/firestore';
import { getAuth, Auth } from 'firebase/auth';

/**
 * Firebase設定
 *
 * Note: これらの値はpublic情報として扱われ、フロントエンドに露出しても
 * セキュリティ上の問題はありません。Firestore Security Rulesで保護されています。
 *
 * 環境変数が設定されている場合はそちらを優先し、なければデフォルト値を使用します。
 */
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || 'AIzaSyDaCWgF0MUxqCtqaCAtvifVDja6poFYrH4',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || 'carewell-automation.firebaseapp.com',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || 'carewell-automation',
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || 'carewell-automation.firebasestorage.app',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '61759806259',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || '1:61759806259:web:a553e9e860314d8e95bc46',
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID,
};

let app: FirebaseApp | null = null;
let db: Firestore | null = null;
let authInstance: Auth | null = null;

/**
 * Firebaseアプリを初期化
 * シングルトンパターンで一度だけ初期化
 */
export function initializeFirebase(): FirebaseApp {
  if (!app) {
    app = initializeApp(firebaseConfig);
  }
  return app;
}

/**
 * Firestoreインスタンスを取得
 * 自動的にFirebaseアプリを初期化
 *
 * Note: carewell-drive-automationが使用している`carewell-native`データベースに接続
 */
export function getDb(): Firestore {
  if (!db) {
    const firebaseApp = initializeFirebase();
    // carewell-nativeデータベースに接続
    db = getFirestore(firebaseApp, 'carewell-native');
  }
  return db;
}

/**
 * Firebase Authenticationインスタンスを取得
 * 自動的にFirebaseアプリを初期化（getDb()と同じシングルトンパターン）
 */
export function getAuthInstance(): Auth {
  if (!authInstance) {
    const firebaseApp = initializeFirebase();
    authInstance = getAuth(firebaseApp);
  }
  return authInstance;
}
