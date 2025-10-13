# Phase 2: 認証機能追加の設計書

## 概要

Phase 1では全ユーザーが読み取り可能な状態ですが、Phase 2では講師認証を追加し、認証済みユーザーのみがダッシュボードにアクセスできるようにします。

## 目的

- 講師アカウントによる認証
- 認証済みユーザーのみダッシュボードへアクセス可能
- 将来的に講師別の担当クラスフィルタリングへ拡張可能な設計

## アーキテクチャ設計

### 1. 認証方式

**Firebase Authentication**を使用

推奨認証方式：
- **Email/Password**: シンプルで管理しやすい
- **Google Sign-In**: 学校のGoogleアカウントと統合可能

```typescript
// 認証プロバイダーの選択肢
- Email/Password
- Google Sign-In
- SAML (将来的なSSO統合用)
```

### 2. Composables設計

#### 2.1. useAuth.ts（新規作成）

認証状態管理を行うComposable

```typescript
// dashboard/src/composables/useAuth.ts

import { ref, computed, Ref } from 'vue';
import {
  getAuth,
  signInWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  signOut,
  onAuthStateChanged,
  User
} from 'firebase/auth';

interface UseAuthReturn {
  user: Ref<User | null>;
  loading: Ref<boolean>;
  error: Ref<string | null>;
  isAuthenticated: ComputedRef<boolean>;
  signInWithEmail: (email: string, password: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  logout: () => Promise<void>;
}

export function useAuth(): UseAuthReturn {
  const user = ref<User | null>(null);
  const loading = ref(true);
  const error = ref<string | null>(null);

  const auth = getAuth();

  // 認証状態の監視
  onAuthStateChanged(auth, (currentUser) => {
    user.value = currentUser;
    loading.value = false;
  });

  const isAuthenticated = computed(() => user.value !== null);

  const signInWithEmail = async (email: string, password: string) => {
    loading.value = true;
    error.value = null;
    try {
      await signInWithEmailAndPassword(auth, email, password);
    } catch (err: any) {
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  const signInWithGoogle = async () => {
    loading.value = true;
    error.value = null;
    try {
      const provider = new GoogleAuthProvider();
      await signInWithPopup(auth, provider);
    } catch (err: any) {
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  const logout = async () => {
    loading.value = true;
    error.value = null;
    try {
      await signOut(auth);
    } catch (err: any) {
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  return {
    user,
    loading,
    error,
    isAuthenticated,
    signInWithEmail,
    signInWithGoogle,
    logout,
  };
}
```

#### 2.2. 既存Composablesの変更ポイント

**useFirestore.ts, useClassList.ts, useTaskList.ts, useFileList.ts**

現在の実装は認証不要なので、**変更不要**です。

理由：
- Firestoreクエリ自体は変更不要（Security Rulesで認証チェック）
- Firebase SDKが自動的に認証トークンをリクエストに含める
- クライアント側で追加のロジックは不要

### 3. ルーター設計

#### 3.1. 認証ガード追加

```typescript
// dashboard/src/router/index.ts

import { createRouter, createWebHistory } from 'vue-router';
import { getAuth } from 'firebase/auth';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('../views/LoginView.vue'),
      meta: { requiresAuth: false }
    },
    {
      path: '/',
      name: 'ClassList',
      component: () => import('../views/ClassListView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/:className',
      name: 'TaskList',
      component: () => import('../views/TaskListView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/:className/:taskId',
      name: 'FileList',
      component: () => import('../views/FileListView.vue'),
      meta: { requiresAuth: true }
    }
  ]
});

// ナビゲーションガード
router.beforeEach((to, from, next) => {
  const auth = getAuth();
  const user = auth.currentUser;
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth);

  if (requiresAuth && !user) {
    // 認証が必要だが未認証の場合、ログインページへリダイレクト
    next({ name: 'Login', query: { redirect: to.fullPath } });
  } else if (to.name === 'Login' && user) {
    // 既に認証済みの場合、ログインページからホームへリダイレクト
    next({ name: 'ClassList' });
  } else {
    next();
  }
});

export default router;
```

### 4. UI設計

#### 4.1. LoginView.vue（新規作成）

```vue
<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-md w-full space-y-8">
      <!-- ロゴ・タイトル -->
      <div>
        <h2 class="mt-6 text-center text-3xl font-bold text-gray-900">
          Carewell Dashboard
        </h2>
        <p class="mt-2 text-center text-sm text-gray-600">
          講師アカウントでログイン
        </p>
      </div>

      <!-- エラー表示 -->
      <ErrorAlert v-if="error" :message="error" @retry="error = null" />

      <!-- ログインフォーム -->
      <form class="mt-8 space-y-6" @submit.prevent="handleLogin">
        <div class="rounded-md shadow-sm -space-y-px">
          <div>
            <label for="email" class="sr-only">メールアドレス</label>
            <input
              id="email"
              v-model="email"
              type="email"
              required
              class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm"
              placeholder="メールアドレス"
            />
          </div>
          <div>
            <label for="password" class="sr-only">パスワード</label>
            <input
              id="password"
              v-model="password"
              type="password"
              required
              class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm"
              placeholder="パスワード"
            />
          </div>
        </div>

        <div>
          <button
            type="submit"
            :disabled="loading"
            class="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
          >
            {{ loading ? 'ログイン中...' : 'ログイン' }}
          </button>
        </div>

        <!-- Googleログイン -->
        <div class="mt-4">
          <button
            type="button"
            @click="handleGoogleLogin"
            :disabled="loading"
            class="group relative w-full flex justify-center py-2 px-4 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
          >
            Googleアカウントでログイン
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuth } from '../composables/useAuth';
import ErrorAlert from '../components/ErrorAlert.vue';

const router = useRouter();
const { signInWithEmail, signInWithGoogle, loading, error } = useAuth();

const email = ref('');
const password = ref('');

const handleLogin = async () => {
  try {
    await signInWithEmail(email.value, password.value);
    router.push('/');
  } catch (err) {
    // エラーはuseAuthで処理済み
  }
};

const handleGoogleLogin = async () => {
  try {
    await signInWithGoogle();
    router.push('/');
  } catch (err) {
    // エラーはuseAuthで処理済み
  }
};
</script>
```

#### 4.2. ヘッダーにログアウトボタン追加

既存のヘッダーコンポーネントに以下を追加：

```vue
<template>
  <header class="bg-white shadow">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
      <!-- 既存のタイトル部分 -->
      <h1>Carewell Dashboard</h1>

      <!-- ログアウトボタン追加 -->
      <button
        @click="handleLogout"
        class="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900"
      >
        ログアウト
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useAuth } from '../composables/useAuth';
import { useRouter } from 'vue-router';

const { logout } = useAuth();
const router = useRouter();

const handleLogout = async () => {
  await logout();
  router.push('/login');
};
</script>
```

### 5. Firestore Security Rules変更

現在のルール（Phase 1）:
```javascript
match /{document=**} {
  allow read: if true;   // 誰でも読み取り可能
  allow write: if false;  // 書き込み禁止
}
```

Phase 2のルール:
```javascript
match /{document=**} {
  allow read: if request.auth != null;  // 認証済みユーザーのみ読み取り可能
  allow write: if false;                 // 書き込みは引き続き禁止
}
```

**変更手順**:
1. `dashboard/firestore.rules`の該当行をアンコメント
2. `firebase deploy --only firestore:rules`で本番環境に適用

### 6. Firebase設定変更

#### 6.1. Firebase Authenticationの有効化

Firebase Consoleで以下を有効化：
1. Authentication > Sign-in method
2. Email/Passwordプロバイダーを有効化
3. （オプション）Googleプロバイダーを有効化

#### 6.2. 環境変数（変更不要）

現在の`dashboard/src/config/firebase.ts`は変更不要です。Firebase SDKが自動的に認証を処理します。

### 7. 講師アカウント管理

#### 7.1. 初期アカウント作成

Firebase Consoleで手動作成、またはスクリプトで一括作成：

```javascript
// scripts/create-teacher-accounts.js
import { getAuth } from 'firebase-admin/auth';
import admin from 'firebase-admin';

admin.initializeApp();

const teachers = [
  { email: 'teacher1@example.com', password: 'SecurePassword123!' },
  { email: 'teacher2@example.com', password: 'SecurePassword123!' },
];

for (const teacher of teachers) {
  await getAuth().createUser({
    email: teacher.email,
    password: teacher.password,
    displayName: teacher.email.split('@')[0],
  });
  console.log(`Created: ${teacher.email}`);
}
```

#### 7.2. パスワードリセット

Firebase Authenticationの標準機能を使用：
```typescript
import { sendPasswordResetEmail } from 'firebase/auth';

await sendPasswordResetEmail(auth, email);
```

### 8. Phase 3への拡張（講師別クラスフィルタリング）

Phase 3では、講師が自分の担当クラスのみ閲覧できるようにします。

#### 8.1. Firestoreデータ構造追加

```
/teachers/{teacherUid}
  - email: string
  - displayName: string
  - assignedClasses: string[]  // 担当クラス名のリスト

例：
/teachers/abc123
  - email: "teacher1@example.com"
  - displayName: "山田太郎"
  - assignedClasses: ["令和7年度 デジタル中核人材養成研修 №01", "..."]
```

#### 8.2. Security Rules（Phase 3）

```javascript
match /{className}/{document=**} {
  allow read: if request.auth != null &&
                 className in get(/databases/$(database)/documents/teachers/$(request.auth.uid)).data.assignedClasses;
  allow write: if false;
}
```

#### 8.3. Composables変更（Phase 3）

`useClassList.ts`で、ユーザーの担当クラスのみフィルタリング：

```typescript
// Phase 3の実装例
import { useAuth } from './useAuth';
import { doc, getDoc } from 'firebase/firestore';

const { user } = useAuth();

// 講師の担当クラスを取得
const teacherDoc = await getDoc(doc(db, 'teachers', user.value!.uid));
const assignedClasses = teacherDoc.data()?.assignedClasses || [];

// フィルタリング
const filteredClasses = allClasses.filter(c => assignedClasses.includes(c.name));
```

## 移行手順

### ステップ1: 開発環境での実装

1. `useAuth.ts`を作成
2. `LoginView.vue`を作成
3. ルーターに認証ガードを追加
4. ヘッダーにログアウトボタン追加
5. ローカルでテスト

### ステップ2: Firebase設定

1. Firebase Console > Authentication > Sign-in methodを有効化
2. テスト用講師アカウントを作成
3. Firestore Rulesを更新してテスト

### ステップ3: デプロイ

1. `firebase deploy --only firestore:rules`
2. `git push origin main`（GitHub Actionsで自動デプロイ）
3. 本番環境で動作確認

### ステップ4: 本番講師アカウント作成

1. 全講師のアカウントを作成
2. 初期パスワードを配布
3. 各講師に初回ログイン後のパスワード変更を依頼

## セキュリティ考慮事項

1. **パスワード要件**:
   - 最小8文字
   - 大文字・小文字・数字を含む

2. **セッション管理**:
   - Firebase Authenticationが自動管理
   - デフォルトで1時間のIDトークン有効期限

3. **HTTPS強制**:
   - Firebase Hostingでデフォルト有効

4. **CORS設定**:
   - Firebase側で自動設定

## テスト計画

1. **ユニットテスト**: useAuth.tsのテスト追加
2. **統合テスト**: ログイン・ログアウトフローのテスト
3. **E2Eテスト**: Playwrightで認証シナリオ追加

## ロールバック計画

Phase 2で問題が発生した場合：

1. Firestore Rulesを Phase 1 に戻す:
   ```javascript
   allow read: if true;
   ```
2. `firebase deploy --only firestore:rules`
3. GitHubで以前のコミットにrevert

## 工数見積もり

- **開発**: 3-5日
  - useAuth実装: 1日
  - LoginView実装: 1日
  - ルーター・ガード実装: 1日
  - テスト実装: 1-2日
- **テスト・検証**: 1-2日
- **デプロイ・アカウント作成**: 1日

**合計**: 5-8日

## 参考リンク

- [Firebase Authentication Documentation](https://firebase.google.com/docs/auth)
- [Vue Router Navigation Guards](https://router.vuejs.org/guide/advanced/navigation-guards.html)
- [Firestore Security Rules](https://firebase.google.com/docs/firestore/security/get-started)
