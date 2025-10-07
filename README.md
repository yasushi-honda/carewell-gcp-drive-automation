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
- **Firestore**: 重複チェック用メタデータストア
- **Google Drive API**: ファイル保存
- **Google Sheets API**: 記録管理

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
│       └── deploy.yml             # CI/CDパイプライン定義
├── src/
│   ├── main.py                    # Cloud Functions エントリーポイント
│   ├── playwright_automation.py   # Playwright自動化エンジン
│   ├── google_drive_service.py    # Google Drive API サービス
│   ├── firestore_service.py       # Firestore 重複チェックサービス
│   └── sheets_service.py          # Google Sheets API サービス
├── Dockerfile                     # コンテナイメージ定義
├── requirements.txt               # Python依存関係
└── .gitignore                     # Git除外設定
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
  "message": "File collection completed",
  "submissions_found": 12,
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
- ✅ ファイル収集ロジック（提出リスト取得・ダウンロード）
- ✅ Google Drive統合（Application Default Credentials）
- ✅ Firestore統合（SHA256ハッシュによる重複チェック）
- ✅ Googleスプレッドシート統合（自動記録・リンク生成）
- ✅ 一時ファイル自動クリーンアップ

## 処理フロー

システムは以下の流れで動作します：

```
1. Cloud Functions HTTPリクエスト受信
   ↓
2. Carewellログイン（Secret Manager経由）
   ↓
3. 指定クラス・課題ページへナビゲーション
   ↓
4. 提出リスト取得（全学生）
   ↓
5. 各提出ファイルについて：
   ├─ Firestoreで重複チェック
   │  └─ 既存 → スキップ
   ├─ Carewell→/tmpへダウンロード
   ├─ Google Driveへアップロード
   ├─ Firestoreに記録（SHA256ハッシュ）
   ├─ Google Sheetsに記録
   └─ /tmp一時ファイル削除
   ↓
6. レスポンス返却（処理件数サマリー）
```

### 重複チェック方式

ファイルの一意性判定は以下の組み合わせのSHA256ハッシュで行います：

```
class_name + task_name + student_id + filename + submit_date
```

これにより：
- ✅ 同一学生が同じファイル名で再提出した場合、提出日時が異なれば新しいファイルとして取得
- ✅ 異なる課題での同名ファイルは別物として扱われる
- ✅ 同一提出（同じ提出日時）の重複は確実にスキップ
- ✅ 学生IDベースなので名前の表記ゆれに影響されない

### Google Sheets記録フォーマット

スプレッドシートには以下の情報が自動記録されます：

| 列 | 内容 |
|----|------|
| 学生名 | Carewellの学生名（IDを除く） |
| 学生ID | 学生ID（例：N9902913） |
| ファイル名 | アップロードされたファイル名 |
| 提出日時 | Carewellでの提出日時 |
| スコア | 採点スコア |
| 合否 | 合否判定 |
| 状態 | 提出状態 |
| Drive File ID | Google DriveファイルID |
| Drive Link | クリック可能なDriveリンク |
| アップロード日時 | システムがアップロードした日時 |

**データフォーマット**:
- Carewellから取得される学生情報は `森平　直樹 <N9902913>` の形式
- システムが自動的に学生名と学生IDに分離して記録

## トラブルシューティング

### Dockerビルドエラー

`python:3.11-slim`ではPlaywrightの依存関係が不足するため、`python:3.11-bookworm`を使用してください。

### タイムアウトエラー

Playwrightのデフォルトタイムアウトは180秒に設定されています。ネットワークが遅い場合は調整が必要です。

## 貢献

内部プロジェクトのため、貢献ガイドラインは省略。
