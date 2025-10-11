# Carewell Dashboard

Firestoreに蓄積された提出ファイルのメタ情報を可視化するWebダッシュボード

## 概要

講師がFirestoreに保存された学生の提出ファイル情報を直感的に確認できるSPA（Single Page Application）です。

### 主要機能

- **3段階ドリルダウンUI**: クラス一覧 → 課題一覧 → ファイル一覧
- **検索・フィルター**: 学生名・学生IDによる部分一致検索
- **ソート機能**: 学生名・提出日時でのソート
- **Google Drive連携**: ファイルへの直接リンク
- **レスポンシブデザイン**: PC・タブレット・スマホ対応

## 技術スタック

- **フレームワーク**: Vue.js 3 (Composition API)
- **ビルドツール**: Vite 5
- **言語**: TypeScript
- **ルーティング**: Vue Router 4
- **スタイリング**: Tailwind CSS 3
- **データベース**: Firestore (読み取り専用)
- **ホスティング**: Firebase Hosting
- **CI/CD**: GitHub Actions

## 開発環境セットアップ

### 前提条件

- Node.js 20以上
- npm または yarn

### 初回セットアップ

```bash
# 依存関係のインストール
npm install

# 環境変数の設定
cp .env.example .env
# .envファイルを編集してFirebase設定を入力
```

### Firebase設定の取得

Firebase設定は以下の手順で取得できます：

1. [Firebase Console](https://console.firebase.google.com/)にアクセス
2. `carewell-automation`プロジェクトを選択
3. 歯車アイコン → プロジェクトの設定
4. 「全般」タブ → 「マイアプリ」セクション
5. Web アプリを選択（存在しない場合は作成）
6. 「SDK の設定と構成」から設定情報をコピー

`.env`ファイルに以下の形式で設定：

```env
VITE_FIREBASE_API_KEY=your-api-key
VITE_FIREBASE_AUTH_DOMAIN=carewell-automation.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=carewell-automation
VITE_FIREBASE_STORAGE_BUCKET=carewell-automation.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=your-sender-id
VITE_FIREBASE_APP_ID=your-app-id
```

### 開発サーバー起動

```bash
npm run dev
```

http://localhost:5173 でアプリケーションが起動します。

### 本番ビルド

```bash
npm run build
```

ビルド成果物は `dist/` ディレクトリに出力されます。

### ビルドプレビュー

```bash
npm run preview
```

## デプロイ

### 自動デプロイ（CI/CD）

`main`ブランチへのプッシュで自動的にFirebase Hostingにデプロイされます。

```bash
git add .
git commit -m "Update dashboard"
git push origin main
```

GitHub Actionsが以下を自動実行：

1. 依存関係のインストール
2. 本番ビルド
3. Firestore Security Rulesのデプロイ
4. Firebase Hostingへのデプロイ

### 手動デプロイ

```bash
# Firebase CLIにログイン
firebase login

# デプロイ
npm run build
firebase deploy --only hosting --project carewell-automation
```

## プロジェクト構造

```
dashboard/
├── public/                  # 静的ファイル
├── src/
│   ├── assets/
│   │   └── styles/         # グローバルスタイル
│   ├── components/         # 再利用可能コンポーネント
│   ├── composables/        # Composition API ロジック
│   ├── config/             # Firebase設定
│   ├── router/             # Vue Router設定
│   ├── types/              # TypeScript型定義
│   ├── views/              # ページコンポーネント
│   ├── App.vue             # ルートコンポーネント
│   └── main.ts             # エントリーポイント
├── .env                    # 環境変数（gitignore対象）
├── .env.example            # 環境変数サンプル
├── firebase.json           # Firebase Hosting設定
├── .firebaserc             # Firebaseプロジェクト設定
├── package.json
├── vite.config.ts
├── tsconfig.json
└── tailwind.config.js
```

## 環境変数

| 変数名 | 説明 | 必須 |
|--------|------|------|
| VITE_FIREBASE_API_KEY | Firebase APIキー | ✅ |
| VITE_FIREBASE_AUTH_DOMAIN | Firebase認証ドメイン | ✅ |
| VITE_FIREBASE_PROJECT_ID | FirebaseプロジェクトID | ✅ |
| VITE_FIREBASE_STORAGE_BUCKET | Firebase Storageバケット | ✅ |
| VITE_FIREBASE_MESSAGING_SENDER_ID | Firebase Messaging送信者ID | ✅ |
| VITE_FIREBASE_APP_ID | FirebaseアプリID | ✅ |

## セキュリティ

### Phase 1（現在）

- **認証**: なし（リンクを知っている人全員がアクセス可能）
- **Firestore Security Rules**: 読み取り専用（`allow read: if true`）
- **書き込み**: フロントエンドからの書き込みは完全禁止

### Phase 2（将来予定）

- **認証**: Firebase Authentication (Google Sign-in)
- **認可**: 講師別の担当クラスフィルタリング

## トラブルシューティング

### ビルドエラー

**症状**: `npm run build`でエラーが発生

**解決策**:
```bash
# node_modulesとpackage-lock.jsonを削除
rm -rf node_modules package-lock.json

# 依存関係を再インストール
npm install
```

### Firebase設定エラー

**症状**: 「Firebase configuration error」が表示される

**解決策**:
- `.env`ファイルが正しく設定されているか確認
- 環境変数名が`VITE_`プレフィックスで始まっているか確認
- 開発サーバーを再起動（環境変数の変更後は必須）

### デプロイエラー

**症状**: GitHub Actionsでデプロイが失敗

**解決策**:
- GitHub SecretsとVariablesが正しく設定されているか確認
- IAM権限が付与されているか確認（`roles/firebase.admin`, `roles/firebasehosting.admin`）

## パフォーマンス目標

| メトリック | 目標値 |
|-----------|--------|
| 初回表示時間 | 3秒以内 |
| 画面遷移時間 | 1秒以内 |
| バンドルサイズ（gzipped） | 200KB以下 |
| 月間コスト | $1未満 |

## 開発ガイドライン

- コンポーネントは単一責任の原則に従う
- Composablesでロジックを再利用可能にする
- TypeScriptの型安全性を活用する
- Tailwind CSSでレスポンシブデザインを実装
- コミット前に`npm run build`でビルドエラーがないか確認

## ライセンス

このプロジェクトは内部利用を目的としています。

## 関連ドキュメント

- [仕様書](.kiro/specs/carewell-dashboard/requirements.md)
- [設計書](.kiro/specs/carewell-dashboard/design.md)
- [実装タスク](.kiro/specs/carewell-dashboard/tasks.md)
- [親プロジェクトREADME](../README.md)
