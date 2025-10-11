// src/config/firebase.ts
// Firebase configuration and initialization

import { initializeApp, FirebaseApp } from 'firebase/app';
import { getFirestore, Firestore } from 'firebase/firestore';

/**
 * Firebase設定
 * 環境変数から取得（Viteの`import.meta.env`を使用）
 */
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID,
};

let app: FirebaseApp | null = null;
let db: Firestore | null = null;

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
