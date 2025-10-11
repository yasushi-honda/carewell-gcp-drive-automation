# GitHub Secrets/Variables 設定手順

CI/CDパイプラインでFirebase Hostingにデプロイするために、GitHub Secrets/Variablesを設定する必要があります。

## 必要な設定

### 1. Firebase設定情報の取得

Firebase Consoleから設定情報を取得します：

1. [Firebase Console](https://console.firebase.google.com/)にアクセス
2. `carewell-automation`プロジェクトを選択
3. 歯車アイコン → 「プロジェクトの設定」
4. 「全般」タブ → 「マイアプリ」セクション
5. Web アプリを選択（存在しない場合は「アプリを追加」で作成）
6. 「SDK の設定と構成」から設定情報をコピー

以下のような形式で表示されます：

```javascript
const firebaseConfig = {
  apiKey: "AIza...",
  authDomain: "carewell-automation.firebaseapp.com",
  projectId: "carewell-automation",
  storageBucket: "carewell-automation.appspot.com",
  messagingSenderId: "617...",
  appId: "1:617...:web:..."
};
```

### 2. GitHub Secretsの設定

GitHubリポジトリの設定画面で以下のSecretsを追加します：

1. GitHubリポジトリ https://github.com/[YOUR_ORG]/carewell-gcp-drive-automation にアクセス
2. 「Settings」タブ → 「Secrets and variables」→ 「Actions」
3. 「Secrets」タブで「New repository secret」をクリック
4. 以下の3つのSecretsを追加：

| Secret名 | 値 | 説明 |
|----------|-----|------|
| `VITE_FIREBASE_API_KEY` | Firebase APIキー | `AIza...`で始まる文字列 |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | Messaging送信者ID | `617...`などの数字 |
| `VITE_FIREBASE_APP_ID` | アプリID | `1:617...:web:...`の形式 |

### 3. GitHub Variablesの設定

同じ画面で「Variables」タブに切り替え、以下のVariablesを追加します：

1. 「Variables」タブで「New repository variable」をクリック
2. 以下の3つのVariablesを追加：

| Variable名 | 値 | 説明 |
|------------|-----|------|
| `VITE_FIREBASE_AUTH_DOMAIN` | `carewell-automation.firebaseapp.com` | 認証ドメイン |
| `VITE_FIREBASE_PROJECT_ID` | `carewell-automation` | プロジェクトID |
| `VITE_FIREBASE_STORAGE_BUCKET` | `carewell-automation.appspot.com` | Storageバケット |

### 4. 設定の確認

設定が完了すると、以下のようになります：

**Secrets（3つ）**:
- ✅ VITE_FIREBASE_API_KEY
- ✅ VITE_FIREBASE_MESSAGING_SENDER_ID
- ✅ VITE_FIREBASE_APP_ID

**Variables（3つ）**:
- ✅ VITE_FIREBASE_AUTH_DOMAIN
- ✅ VITE_FIREBASE_PROJECT_ID
- ✅ VITE_FIREBASE_STORAGE_BUCKET

## なぜSecretsとVariablesを分けるのか？

- **Secrets**: 秘匿性の高い情報（APIキー、認証トークンなど）
  - ログに出力されない
  - 一度設定すると内容は表示されない
  - 値の変更のみ可能

- **Variables**: 秘匿性の低い設定情報（プロジェクトID、ドメインなど）
  - ログに出力される可能性がある
  - 設定後も内容を確認可能
  - 管理しやすい

Firebase設定の中で、`apiKey`、`messagingSenderId`、`appId`は一応秘密扱いにしますが、実際にはFirebaseのSecurity Rulesで保護されているため、フロントエンドに露出しても問題ありません。

## テストデプロイ

設定が完了したら、`dashboard/`ディレクトリに変更を加えてコミット・プッシュすることで、GitHub Actionsが自動的にデプロイを開始します：

```bash
# ルートディレクトリで実行
git add .
git commit -m "feat: Add Carewell Dashboard initial setup"
git push origin main
```

## トラブルシューティング

### デプロイが失敗する場合

1. **GitHub Actionsのログを確認**
   - GitHubリポジトリの「Actions」タブで最新のワークフロー実行を確認
   - エラーメッセージから原因を特定

2. **Secrets/Variablesの確認**
   - 全ての値が正しく設定されているか確認
   - 変数名のタイポがないか確認（`VITE_`プレフィックスが必要）

3. **IAM権限の確認**
   ```bash
   # github-actions-saにFirebase権限が付与されているか確認
   gcloud projects get-iam-policy carewell-automation \
     --flatten="bindings[].members" \
     --filter="bindings.members:serviceAccount:github-actions-sa@carewell-automation.iam.gserviceaccount.com"
   ```

   以下の権限が表示されるはずです：
   - `roles/firebase.admin`
   - `roles/firebasehosting.admin`

### ローカルで動作しない場合

1. **環境変数の確認**
   ```bash
   # dashboard/.envファイルが存在するか確認
   ls -la dashboard/.env

   # 内容を確認（値は表示されないように注意）
   cat dashboard/.env
   ```

2. **依存関係の再インストール**
   ```bash
   cd dashboard
   rm -rf node_modules package-lock.json
   npm install
   ```

3. **開発サーバーの再起動**
   ```bash
   npm run dev
   ```

## 次のステップ

設定が完了し、CI/CDが正常に動作したら、以下のタスクに進みます：

1. Firebase接続とFirestore設定の実装
2. クラス一覧画面の構築
3. 課題一覧画面の構築
4. ファイル一覧画面の構築

詳細は `.kiro/specs/carewell-dashboard/tasks.md` を参照してください。
