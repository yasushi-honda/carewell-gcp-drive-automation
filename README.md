# Carewell GCP Drive Automation

Carewell Webサービスから提出ファイルを自動収集し、Google Driveへ保存、Googleスプレッドシートに記録するシステム

## 概要

このプロジェクトは、Carewell学習管理システムから学生の提出物を自動的に収集し、Google Driveに整理して保存、メタデータをGoogleスプレッドシートに記録する自動化システムです。

## アーキテクチャ

### 主要コンポーネント

- **Cloud Run Functions (2nd Gen)**: サーバーレス実行環境
- **Playwright**: Carewell Webサイトの自動操作
- **Secret Manager**: 認証情報の安全な管理
- **Artifact Registry**: Dockerイメージの保存（最新2つのみ保持）
- **Firestore**: 重複チェック用メタデータストア（予定）
- **Google Drive API**: ファイル保存（予定）
- **Google Sheets API**: 記録管理（予定）

### CI/CDパイプライン

GitHub Actions + Workload Identity Federationによる自動デプロイ

```
GitHub Push → GitHub Actions → Artifact Registry → Cloud Run Functions
```

## プロジェクト構成

```
.
├── .github/
│   └── workflows/
│       └── deploy.yml          # CI/CDパイプライン定義
├── src/
│   ├── main.py                 # Cloud Functions エントリーポイント
│   └── playwright_automation.py # Playwright自動化エンジン
├── Dockerfile                  # コンテナイメージ定義
├── requirements.txt            # Python依存関係
└── .gitignore                  # Git除外設定
```

## セットアップ

### 前提条件

- GCPプロジェクト: `carewell-automation`
- Secret Managerに以下のシークレットが設定済み:
  - `carewell-user-id`: CarewellユーザーID
  - `carewell-password`: Carewellパスワード

### デプロイ方法

mainブランチへのpushで自動的にデプロイされます:

```bash
git add .
git commit -m "Your commit message"
git push origin main
```

GitHub Actionsが自動的に:
1. Dockerイメージをビルド
2. Artifact Registryにプッシュ
3. Cloud Run Functionsにデプロイ

## 使用方法

### APIエンドポイント

```
POST https://carewell-file-collector-imczapxkba-an.a.run.app
```

### リクエスト形式

```json
{
  "class_name": "令和7年度 デジタル中核人材養成研修 №01",
  "task_name": "課題①業務分析　※～11/3〆切",
  "drive_folder_id": "1abc...xyz",
  "spreadsheet_id": "1def...uvw"
}
```

### レスポンス形式

```json
{
  "status": "success",
  "processed": 10,
  "skipped": 2,
  "failed": 0
}
```

## 開発

### ローカル開発

```bash
# 依存関係のインストール
pip install -r requirements.txt

# Playwrightブラウザのインストール
playwright install chromium
```

### 環境変数

- `GCP_PROJECT`: GCPプロジェクトID（デフォルト: carewell-automation）

### 技術スタック

- **言語**: Python 3.11
- **Webオートメーション**: Playwright 1.40.0
- **クラウドプラットフォーム**: Google Cloud Platform
- **コンテナ**: Docker (python:3.11-bookworm)
- **CI/CD**: GitHub Actions

## インフラストラクチャ

### GCPリソース

| リソース | 名前 | リージョン | 用途 |
|---------|------|-----------|------|
| Cloud Run | carewell-file-collector | asia-northeast1 | Functions実行 |
| Artifact Registry | carewell-functions | asia-northeast1 | イメージ保存 |
| Secret Manager | carewell-user-id, carewell-password | global | 認証情報 |
| Workload Identity Pool | github-actions-pool | global | GitHub Actions認証 |

### リソース設定

- **メモリ**: 2Gi
- **CPU**: 1
- **タイムアウト**: 540秒
- **認証**: 未認証アクセス許可（開発中）

## セキュリティ

- 認証情報はSecret Managerで管理
- Workload Identity Federationによる鍵なし認証
- 環境変数での認証情報保存は禁止

## ライセンス

このプロジェクトは内部利用を目的としています。

## 開発ステータス

現在の実装状況:

- ✅ CI/CDパイプライン
- ✅ Playwright自動化基盤
- ✅ Secret Manager統合
- ✅ Carewellログイン・ナビゲーション
- 🚧 ファイル収集ロジック
- 🚧 Google Drive統合
- 🚧 Firestore統合
- 🚧 Googleスプレッドシート統合

## トラブルシューティング

### Dockerビルドエラー

`python:3.11-slim`ではPlaywrightの依存関係が不足するため、`python:3.11-bookworm`を使用してください。

### タイムアウトエラー

Playwrightのデフォルトタイムアウトは180秒に設定されています。ネットワークが遅い場合は調整が必要です。

## 貢献

内部プロジェクトのため、貢献ガイドラインは省略。
