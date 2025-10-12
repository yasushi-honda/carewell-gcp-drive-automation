# Dashboard Development Workflow

**Target**: `dashboard/**/*` (Vue.js SPA)

## 🚫 絶対禁止事項

dashboard開発時は、**ローカル開発環境を一切使用しません**。

### 禁止コマンド
```bash
# ❌ 絶対に実行しないこと
npm run dev           # ローカル開発サーバー起動
npm run build         # ローカルビルド
npm install           # 依存関係インストール
npm run preview       # ビルドプレビュー
cd dashboard && ...   # dashboardディレクトリでのnpm操作
```

### 理由
- GitHub Actions CI/CDで全て自動化済み
- ローカル環境セットアップ不要（Node.js, npm不要）
- 環境差異によるトラブル回避
- デプロイフローの完全統一

## ✅ 正しいワークフロー

### Step 1: コード変更
- Vue コンポーネント編集: `dashboard/src/components/*.vue`
- Composables編集: `dashboard/src/composables/*.ts`
- ルーティング設定: `dashboard/src/router/index.ts`
- 型定義追加: `dashboard/src/types/*.ts`

### Step 2: Git操作
```bash
git add dashboard/
git commit -m "feat: Implement [feature description]"
git push origin main
```

### Step 3: 自動デプロイ（GitHub Actions）
`.github/workflows/deploy-dashboard.yml`が自動実行：
1. ✅ Node.js 20セットアップ
2. ✅ `npm install` (CI環境)
3. ✅ `npm run build` (CI環境)
4. ✅ Firestore Security Rulesデプロイ
5. ✅ Firebase Hostingデプロイ

### Step 4: 動作確認
```bash
# GitHub Actionsの実行状態を確認
gh run list --limit 3

# 特定のワークフロー実行を監視
gh run watch [run-id]
```

**デプロイ先**: https://carewell-automation.web.app/

## 🔄 デバッグワークフロー

### ビルドエラーが発生した場合
1. GitHub Actionsのログを確認: `gh run view [run-id]`
2. TypeScriptエラー等を修正
3. 再度 `git add/commit/push`
4. GitHub Actionsが再実行される

### 動作確認
- **本番環境で確認**: https://carewell-automation.web.app/
- ブラウザのDevToolsで動作確認
- FirestoreデータはFirebase Consoleで確認

## 📋 実装パターン

### Vue 3 Composition API
```typescript
<script setup lang="ts">
import { onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';

const router = useRouter();
const route = useRoute();

onMounted(async () => {
  // 初期化処理
});
</script>
```

### Composables パターン
```typescript
// dashboard/src/composables/useXxx.ts
export function useXxx() {
  const data = ref<T[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const fetch = async () => {
    loading.value = true;
    error.value = null;
    try {
      // データ取得
    } catch (err) {
      error.value = err.message;
    } finally {
      loading.value = false;
    }
  };

  return { data, loading, error, fetch };
}
```

### Lazy Loading
```typescript
// router/index.ts
{
  path: '/path',
  name: 'name',
  component: () => import('../views/XxxView.vue'),
  props: true,
}
```

## 🎯 Remember

**dashboardディレクトリでは、npmコマンドを実行することは決してありません。**

**全ての操作はコード編集とGit操作のみです。**

**ビルドとデプロイはGitHub Actionsが自動的に行います。**
