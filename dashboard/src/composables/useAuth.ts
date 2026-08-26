// src/composables/useAuth.ts
// Firebase Authentication（Google Sign-In）による管理者認証を管理する composable
//
// Issue #12対応。user/isAdmin/authReadyはモジュールスコープのシングルトンとして
// 保持する（コンポーネントごとにonAuthStateChangedリスナーを再登録しないため。
// 関数内でrefを作るとコンポーネント間で状態が共有されずリークする既知の罠を回避）。

import { ref, readonly } from 'vue';
import {
  GoogleAuthProvider,
  onAuthStateChanged,
  signInWithPopup,
  signOut,
  type User,
} from 'firebase/auth';
import { doc, getDoc } from 'firebase/firestore';
import { getAuthInstance, getDb } from '../config/firebase';

const user = ref<User | null>(null);
const isAdmin = ref(false);
const authReady = ref(false);

let initialized = false;
let resolveReady: (() => void) | null = null;
const readyPromise = new Promise<void>((resolve) => {
  resolveReady = resolve;
});

/**
 * admins/{email小文字} ドキュメントの存在で管理者判定する。
 * バックエンド(src/auth.py の is_admin_email)・Firestoreルール(isAdmin())と
 * 同じ判定基準（同じコレクション・同じ正規化）。
 *
 * 例外時は必ずFalse（fail-closed）。
 */
async function checkAdmin(currentUser: User): Promise<boolean> {
  if (!currentUser.email) return false;
  try {
    const snap = await getDoc(doc(getDb(), 'admins', currentUser.email.toLowerCase()));
    return snap.exists();
  } catch (err) {
    console.error('[useAuth] admin check failed', err);
    return false;
  }
}

function ensureInitialized(): void {
  if (initialized) return;
  initialized = true;

  onAuthStateChanged(getAuthInstance(), async (currentUser) => {
    user.value = currentUser;
    isAdmin.value = currentUser ? await checkAdmin(currentUser) : false;
    authReady.value = true;
    resolveReady?.();
  });
}

export function useAuth() {
  ensureInitialized();

  /**
   * 初回のauthStateChanged発火（ログイン状態の確定）を待つ。
   * ルーターガード等、直リンクアクセス時に判定が確定してから処理したい箇所で使う。
   */
  const waitUntilReady = async (): Promise<void> => {
    ensureInitialized();
    await readyPromise;
  };

  const signInWithGoogle = async (): Promise<void> => {
    const provider = new GoogleAuthProvider();
    await signInWithPopup(getAuthInstance(), provider);
  };

  const logout = async (): Promise<void> => {
    await signOut(getAuthInstance());
  };

  /**
   * 現在ログイン中のユーザーのFirebase IDトークンを取得する。
   * 未ログイン時はnull。バックエンドへの Authorization: Bearer ヘッダに使う。
   */
  const getIdToken = async (): Promise<string | null> => {
    if (!user.value) return null;
    return user.value.getIdToken();
  };

  return {
    user: readonly(user),
    isAdmin: readonly(isAdmin),
    authReady: readonly(authReady),
    waitUntilReady,
    signInWithGoogle,
    logout,
    getIdToken,
  };
}
