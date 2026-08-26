# Carewell Dashboard

Firestoreに蓄積された提出ファイルのメタ情報を可視化するWebダッシュボード

**バージョン**: Ver1（Phase 1完了）
**リリース日**: 2025-10-13
**公開URL**: https://carewell-dashboard-2026.web.app
**令和8年度サイト稼働開始日**: 2026-08-26（旧サイト https://carewell-automation.web.app は令和7年度の凍結アーカイブ）

## 概要

講師がFirestoreに保存された学生の提出ファイル情報を直感的に確認できるSPA（Single Page Application）です。Ver1として基本機能実装が完了し、本番環境で稼働中です。

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

## 開発ステータス

### 🎉 Phase 0: CI/CD構築（完了）

**実装済み**:
- ✅ Vue.js 3 + Vite + TypeScript プロジェクト骨格
- ✅ Tailwind CSS スタイリング基盤
- ✅ Vue Router 4 ルーティング設定
- ✅ Firebase プロジェクト初期化
- ✅ GitHub Actions CI/CDパイプライン
- ✅ Firestore Security Rules デプロイ自動化
- ✅ Firebase Hosting デプロイ自動化
- ✅ Hello World ページデプロイ

**公開URL**: https://carewell-dashboard-2026.web.app

**ワークフロー**: `.github/workflows/deploy-dashboard.yml`

### 🎉 Phase 1: 基本機能実装（完了）

**実装完了日**: 2025-10-13

**完了タスク数**: 48/48 (100%)

**実装済み機能**:

1. ✅ **データアクセス層** (Composables)
   - `useFirestore`: Firestore接続、親ドキュメント取得、Timestamp自動変換
   - `useClassList`: クラス一覧取得、統計情報集計
   - `useTaskList`: 課題一覧取得、統計情報集計
   - `useFileList`: ファイル一覧取得、検索・ソート機能

2. ✅ **3段階ドリルダウンUI**
   - ClassListView: クラス一覧表示
   - TaskListView: 課題一覧表示
   - FileListView: ファイル一覧表示、検索・ソート
   - パンくずリスト、空状態表示

3. ✅ **共通コンポーネント**
   - ClassCard, TaskCard, FileTable
   - SearchBox, LoadingSkeleton, ErrorAlert
   - Breadcrumb, EmptyState

4. ✅ **レスポンシブデザイン**
   - モバイル/タブレット/デスクトップ対応
   - アクセシビリティ強化（ARIA属性、キーボードナビゲーション）

5. ✅ **パフォーマンス最適化**
   - コード分割と遅延ロード
   - Firestoreクエリ最適化（親ドキュメントメタデータ活用）
   - キャッシング最適化

6. ✅ **テスト実装**
   - Composablesユニットテスト（Vitest）
   - コンポーネント統合テスト（@vue/test-utils）
   - E2Eテスト（Playwright - 5ブラウザ対応）

7. ✅ **デプロイ準備**
   - Firebase Hosting設定
   - GitHub Actions CI/CD統合
   - ブラウザ互換性検証

### 🔐 Phase 2: 認証・セキュリティ（設計完了、実装準備中）

**設計ドキュメント**: `docs/phase2-authentication-design.md`

**予定機能**:
- Firebase Authentication 統合（Email/Password、Google Sign-In）
- useAuth Composable実装
- LoginView UI実装
- Router認証ガード
- Firestore Security Rules 更新
- 講師別クラスフィルタリング（Phase 3予定）

**工数見積もり**: 5-8日

### 🚀 次のステップ

Phase 2の実装を開始する場合は、以下のドキュメントを参照してください：

- **設計書**: `docs/phase2-authentication-design.md`
- **仕様書**: `.kiro/specs/carewell-dashboard/requirements.md`
- **実装タスク**: `.kiro/specs/carewell-dashboard/tasks.md`

または、Kiro Spec-Driven Developmentワークフローを使用：

```bash
/kiro:spec-init carewell-dashboard-phase2
```

## ライセンス

このプロジェクトは内部利用を目的としています。

## 関連ドキュメント

- [仕様書](.kiro/specs/carewell-dashboard/requirements.md)
- [設計書](.kiro/specs/carewell-dashboard/design.md)
- [実装タスク](.kiro/specs/carewell-dashboard/tasks.md)
- [親プロジェクトREADME](../README.md)
