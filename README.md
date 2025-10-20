# Carewell GCP Drive Automation

Carewell Webサービスから提出ファイルを自動収集し、Google Driveへ保存、Googleスプレッドシートに記録するシステム + Firestore可視化ダッシュボード

## 概要

このプロジェクトは2つのシステムで構成されています：

### 1. ファイル自動収集システム（Cloud Run Functions）
Carewell学習管理システムから学生の提出物を自動的に収集し、Google Driveに整理して保存、メタデータをGoogleスプレッドシートとFirestoreに記録する自動化システムです。

### 2. Carewell Dashboard（Firebase Hosting）
Firestoreに蓄積された提出ファイルのメタ情報を、講師が直感的に確認できるWebダッシュボードです。Vue.js 3で構築されたSPAで、3段階ドリルダウンUI（クラス一覧 → 課題一覧 → ファイル一覧）により、必要な情報へ素早くアクセスできます。

**現在の状態**: ✅ **Ver1リリース完了** - https://carewell-automation.web.app

**実装済み機能（Phase 1完了 - 48/48タスク）**:
- ✅ 3段階ドリルダウンUI（クラス → 課題 → ファイル一覧）
- ✅ 検索・フィルター機能（学生名・学生ID）
- ✅ ソート機能（学生名・提出日時）
- ✅ Google Drive直接リンク
- ✅ レスポンシブデザイン（PC・タブレット・スマホ対応）
- ✅ パンくずリストナビゲーション
- ✅ ローディング・エラーハンドリング
- ✅ テスト実装（Unit・Integration・E2E）
- ✅ パフォーマンス最適化（コード分割・キャッシング）
- ✅ CI/CD自動デプロイ

**次のステップ（オプション）**: Phase 2 認証機能実装（Firebase Authentication、講師別クラスフィルタリング）

詳細は [dashboard/README.md](dashboard/README.md) を参照してください。

## アーキテクチャ

### 主要コンポーネント

**バックエンド（ファイル自動収集）**:
- **Cloud Run Functions (2nd Gen)**: サーバーレス実行環境
- **Playwright**: Carewell Webサイトの自動操作
- **Secret Manager**: 認証情報の安全な管理
- **Artifact Registry**: Dockerイメージの保存（最新2つのみ保持）
- **Firestore**: 重複チェック用メタデータストア
  - **使用DB**: `carewell-native` (FIRESTORE_NATIVE)
  - **未使用DB**: `(default)` (DATASTORE_MODE) - 削除不可のため共存、コスト影響なし
- **Google Drive API**: ファイル保存
- **Google Sheets API**: 記録管理

**フロントエンド（Dashboard）**:
- **Firebase Hosting**: Vue.js 3 SPA配信（グローバルCDN）
- **Firestore**: 読み取り専用データソース（メタ情報可視化）
- **Vue.js 3 + Vite**: フロントエンドフレームワーク
- **Tailwind CSS**: UIスタイリング

### CI/CDパイプライン

GitHub Actions + Workload Identity Federationによる自動デプロイ

```
GitHub Push → GitHub Actions → Artifact Registry → Cloud Run Functions
GitHub Push → GitHub Actions → Firebase Hosting (Dashboard)
```

**2つのデプロイパイプライン**:
1. **Cloud Run Functions**: `src/`, `Dockerfile`, `requirements.txt`の変更時
2. **Firebase Hosting**: `dashboard/`の変更時

## プロジェクト構成

```
.
├── .github/
│   └── workflows/
│       ├── deploy.yml                # CI/CD: Cloud Run Functions
│       └── deploy-dashboard.yml      # CI/CD: Firebase Hosting
├── dashboard/                        # Carewell Dashboard (Vue.js 3 SPA)
│   ├── src/                          # ソースコード
│   ├── public/                       # 静的ファイル
│   ├── firebase.json                 # Firebase Hosting設定
│   └── package.json                  # npm依存関係
├── src/
│   ├── main.py                       # Cloud Functions エントリーポイント
│   ├── playwright_automation.py      # Playwright自動化エンジン
│   ├── google_drive_service.py       # Google Drive API サービス
│   ├── firestore_service.py          # Firestore 重複チェックサービス
│   └── sheets_service.py             # Google Sheets API サービス
├── firestore.rules                   # Firestore Security Rules
├── Dockerfile                        # コンテナイメージ定義
├── requirements.txt                  # Python依存関係
└── .gitignore                        # Git除外設定
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
  "task_id": "課題①",
  "task_pattern": "課題①",
  "drive_folder_id": "1abc...xyz",
  "spreadsheet_id": "1def...uvw"
}
```

**パラメータ説明**:
- `task_id`: Firestore/Sheetsでの管理用識別子（例: "課題①"）
- `task_pattern`: Carewell画面での検索パターン（例: "課題①" で部分一致検索）

### レスポンス形式

```json
{
  "status": "success",
  "message": "File collection completed",
  "submissions_found": 12,
  "processed": 10,
  "skipped": 2,
  "failed": 0,
  "total_count_from_ui": 12,
  "count_verified": true
}
```

**レスポンスフィールド説明**:
- `status`: 処理ステータス（"success" または "error"）
- `message`: 処理メッセージ
- `submissions_found`: 検出された提出物の総数
- `processed`: 新規ダウンロード・処理された件数
- `skipped`: 既に処理済みでスキップされた件数
- `failed`: 処理に失敗した件数
- `total_count_from_ui`: UI画面から取得した総件数（データ完全性チェック用）
- `count_verified`: 抽出件数とUI件数が一致しているか（true/false）
- `warning`: 件数不一致時の警告メッセージ（オプション、count_verified=falseの場合のみ）

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
| Cloud Run | carewell-file-collector | asia-northeast1 | ファイル収集Functions実行 |
| Cloud Run | carewell-automation | asia-northeast1 | 申し込み状況取得Functions実行 |
| Cloud Scheduler | carewell-class{01-05,08-09}-task{01-02} | asia-northeast1 | ファイル収集自動実行（14ジョブ、30分間隔） |
| Cloud Scheduler | carewell-automation-pattern{1-5,8-9} | asia-northeast1 | **申し込み状況取得自動実行（7ジョブ、30分間隔）⚠️絶対削除禁止** |
| Artifact Registry | carewell-functions | asia-northeast1 | イメージ保存 |
| Firestore | carewell-native | asia-northeast1 | 重複チェック用メタデータストア（NATIVE） |
| Firestore | (default) | asia-northeast1 | 未使用（DATASTORE_MODE、削除不可） |
| Secret Manager | carewell-user-id, carewell-password | global | 認証情報 |
| Workload Identity Pool | github-actions-pool | global | GitHub Actions認証 |

### リソース設定

- **メモリ**: 2Gi
- **CPU**: 1
- **タイムアウト**: 540秒
- **認証**: サービスアカウント認証（github-actions-sa）

## セキュリティ

- 認証情報はSecret Managerで管理
- Workload Identity Federationによる鍵なし認証
- Cloud Run: 認証トークン必須（パブリックアクセス無効化）
- サービスアカウント最小権限の原則
- 環境変数での認証情報保存は禁止

## ライセンス

このプロジェクトは内部利用を目的としています。

## 開発ステータス

### 実装済み機能

- ✅ CI/CDパイプライン
- ✅ Playwright自動化基盤
- ✅ Secret Manager統合
- ✅ Carewellログイン・ナビゲーション
- ✅ ファイル収集ロジック（提出リスト取得・ダウンロード）
- ✅ Google Drive統合（Application Default Credentials）
- ✅ Firestore統合（SHA256ハッシュによる重複チェック）
- ✅ Googleスプレッドシート統合（自動記録・リンク生成）
- ✅ 一時ファイル自動クリーンアップ
- ✅ 総件数照合機能（データ完全性チェック）
- ✅ Cloud Scheduler自動実行基盤
  - ファイル収集: 14ジョブ（7クラス × 2課題）
  - 申し込み状況取得: 7ジョブ（7クラス）⚠️別システム・絶対削除禁止

### 未実装機能（今後のタスク）

詳細は `.kiro/specs/carewell-drive-automation/tasks.md` を参照

**優先度：中**
- ⬜ ユニットテスト・統合テストの実装

**優先度：低（オプション）**
- ⬜ エラー通知機能（Gmail API）の実装

## Cloud Scheduler運用状態

### 現在の構成

**合計21ジョブ**が稼働中：
- **ファイル収集用（本システム）**: 14ジョブ（7クラス × 2課題）
- **申し込み状況取得用**: 7ジョブ（7クラス）⚠️別システム・絶対削除禁止

#### ファイル収集ジョブ（carewell-class系、14ジョブ）

| ジョブ名 | 対象クラス | 対象課題 | 実行間隔 | 状態 |
|---------|-----------|---------|---------|------|
| carewell-class01-task01 | №01 | 課題① | 30分毎 | ✅ ENABLED |
| carewell-class01-task02 | №01 | 課題② | 30分毎 | ✅ ENABLED |
| carewell-class02-task01 | №02 | 課題① | 30分毎 | ⏸️ PAUSED |
| carewell-class02-task02 | №02 | 課題② | 30分毎 | ⏸️ PAUSED |
| carewell-class03-task01 | №03 | 課題① | 30分毎 | ⏸️ PAUSED |
| carewell-class03-task02 | №03 | 課題② | 30分毎 | ⏸️ PAUSED |
| carewell-class04-task01 | №04 | 課題① | 30分毎 | ⏸️ PAUSED |
| carewell-class04-task02 | №04 | 課題② | 30分毎 | ⏸️ PAUSED |
| carewell-class05-task01 | №05 | 課題① | 30分毎 | ⏸️ PAUSED |
| carewell-class05-task02 | №05 | 課題② | 30分毎 | ⏸️ PAUSED |
| carewell-class08-task01 | №08 | 課題① | 30分毎 | ⏸️ PAUSED |
| carewell-class08-task02 | №08 | 課題② | 30分毎 | ⏸️ PAUSED |
| carewell-class09-task01 | №09 | 課題① | 30分毎 | ⏸️ PAUSED |
| carewell-class09-task02 | №09 | 課題② | 30分毎 | ⏸️ PAUSED |

#### 申し込み状況取得ジョブ（carewell-automation-pattern系、7ジョブ）⚠️絶対削除禁止

| ジョブ名 | 対象クラス | スプレッドシートシート名 | 実行間隔 | 状態 |
|---------|-----------|---------------------|---------|------|
| carewell-automation-pattern1 | №01 | Team1 | 30分毎 | ✅ ENABLED |
| carewell-automation-pattern2 | №02 | Team2 | 30分毎 | ✅ ENABLED |
| carewell-automation-pattern3 | №03 | Team3 | 30分毎 | ✅ ENABLED |
| carewell-automation-pattern4 | №04 | Team4 | 30分毎 | ✅ ENABLED |
| carewell-automation-pattern5 | №05 | Team5 | 30分毎 | ✅ ENABLED |
| carewell-automation-pattern8 | №08 | Team8 | 30分毎 | ✅ ENABLED |
| carewell-automation-pattern9 | №09 | Team9 | 30分毎 | ✅ ENABLED |

**重要**: これらのジョブは別システム（`carewell-automation`）が使用しており、申し込み状況の自動取得を行っています。**絶対に削除・停止しないでください。**

**スプレッドシートID**: `1ZhSDpgxsC0NRkZy2cCmTBqYnKsZ90KRDc8UrKuodQMQ`

### 段階的ロールアウト戦略

**フェーズ1: 初期有効化（完了）**
- №01の2ジョブを有効化（2025-10-11 15:15）
- 24時間監視期間を開始

**フェーズ2: 全体有効化（24時間後予定）**
- №01の監視結果が良好であれば、残り12ジョブを有効化
- 監視結果に問題がある場合は、原因調査・修正後に再開

### 監視コマンド

#### ジョブ状態の確認

```bash
# 全ジョブの状態確認
gcloud scheduler jobs list --location asia-northeast1 | grep carewell

# 特定ジョブの詳細確認
gcloud scheduler jobs describe carewell-class01-task01 --location asia-northeast1
```

#### 実行ログの確認

```bash
# Cloud Runの最新ログ確認（最近10分間）
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=carewell-file-collector" \
  --limit 50 \
  --format json \
  --freshness 10m

# 特定時間範囲のログ確認
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=carewell-file-collector" \
  --limit 100 \
  --format json \
  --freshness 1h
```

#### ジョブの有効化

```bash
# 残り12ジョブを有効化（フェーズ2実行時）
for job in carewell-class{02..05}-task{01,02} carewell-class{08,09}-task{01,02}; do
  gcloud scheduler jobs resume $job --location asia-northeast1
  echo "✅ Enabled: $job"
done
```

#### ジョブの一時停止

```bash
# 問題発生時の緊急停止
for job in carewell-class{01..05}-task{01,02} carewell-class{08,09}-task{01,02}; do
  gcloud scheduler jobs pause $job --location asia-northeast1
  echo "⏸️ Paused: $job"
done
```

### 監視ポイント

24時間監視期間中に以下を確認してください：

1. **実行成功率**: Cloud Runログで200ステータスを確認
2. **データ整合性**: Firestore/Drive/Sheets間の一貫性を確認
3. **重複防止**: 同一ファイルが複数回処理されていないことを確認
4. **エラーログ**: 予期しないエラーが発生していないか確認
5. **実行時間**: タイムアウト（540秒）に近い実行がないか確認

問題が発見された場合は、全ジョブを一時停止し、原因を調査してください。

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
   ├─ UI画面から総件数を取得（「20件中 1 - 20件目表示」）
   └─ 抽出した提出リストと件数を照合
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
6. レスポンス返却（処理件数サマリー + 件数照合結果）
```

### 重複チェック方式

ファイルの一意性判定は以下の複合キーで行います：

```
{student_id}_{filename}_{submit_date}
```

Firestoreコレクション階層: `{class_name}/{task_id}/documents/{composite_key}`

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

## 開発者向けツール

### テストスクリプト

#### 単一パターンテスト

```bash
./scripts/test-single-pattern.sh
```

№01-課題①の単一パターンを本番環境でテストします。

#### 全パターンテスト

```bash
./scripts/test-all-patterns.sh
```

7クラス × 2課題 = 14パターンを本番環境でテストします。

### Firestoreデータクリーンアップ

開発・テスト時にFirestoreのテストデータを削除する場合:

```bash
./scripts/cleanup-firestore.sh
```

**注意**: スクリプト内の変数を編集して、削除対象のクラス・課題を指定してください。

```bash
CLASS_NAME="令和7年度 デジタル中核人材養成研修 №01"
TASK_ID="課題①"
```

## メンテナンス

詳細なコード品質レポートは `docs/maintenance-report.md` を参照してください。

## 貢献

内部プロジェクトのため、貢献ガイドラインは省略。
