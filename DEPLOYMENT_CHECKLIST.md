# デプロイ前チェックリスト

## 1. GCP IAM権限の確認

Cloud Run Functionsのサービスアカウントに必要な権限：

### 必須権限

- [ ] **Secret Manager Secret Accessor** (`roles/secretmanager.secretAccessor`)
  - Secret Managerからの認証情報取得用
  - 必要なシークレット:
    - `carewell-user-id`
    - `carewell-password`

- [ ] **Cloud Datastore User** (`roles/datastore.user`)
  - Firestoreへの読み書き用
  - コレクション: `uploaded_files`

- [ ] **Service Account Token Creator** (自分自身に対して)
  - Application Default Credentials用

### Google Drive API権限

- [ ] **サービスアカウントにDriveフォルダへのアクセス権付与**
  - 手順:
    1. サービスアカウントのメールアドレスを確認
       ```
       [project-number]-compute@developer.gserviceaccount.com
       ```
    2. Google Driveでターゲットフォルダを開く
    3. 「共有」→ サービスアカウントのメールアドレスを追加
    4. 権限: 「編集者」に設定

### Google Sheets API権限

- [ ] **サービスアカウントにスプレッドシートへのアクセス権付与**
  - 手順:
    1. 記録用スプレッドシートを開く
    2. 「共有」→ サービスアカウントのメールアドレスを追加
    3. 権限: 「編集者」に設定

## 2. GCP API有効化の確認

以下のAPIが有効になっていることを確認：

```bash
# 確認コマンド
gcloud services list --enabled --project=carewell-automation

# 必要に応じて有効化
gcloud services enable \
  secretmanager.googleapis.com \
  firestore.googleapis.com \
  drive.googleapis.com \
  sheets.googleapis.com \
  --project=carewell-automation
```

- [ ] Secret Manager API (`secretmanager.googleapis.com`)
- [ ] Firestore API (`firestore.googleapis.com`)
- [ ] Google Drive API (`drive.googleapis.com`)
- [ ] Google Sheets API (`sheets.googleapis.com`)

## 3. Firestoreデータベース初期化

- [ ] Firestoreをネイティブモードで有効化
  ```bash
  gcloud firestore databases create --region=asia-northeast1 --project=carewell-automation
  ```

- [ ] インデックス設定（必要に応じて）
  - `uploaded_files`コレクションに以下のフィールドでクエリ可能:
    - `class_name`
    - `task_name`
    - `uploaded_at`

## 4. テストデータ準備

### テスト用Google Driveフォルダ

- [ ] テスト用フォルダを作成
- [ ] フォルダIDを取得（URLから）
  ```
  https://drive.google.com/drive/folders/[FOLDER_ID]
  ```

### テスト用Google Spreadsheet

- [ ] 新規スプレッドシートを作成
- [ ] スプレッドシートIDを取得（URLから）
  ```
  https://docs.google.com/spreadsheets/d/[SPREADSHEET_ID]/edit
  ```

### テストリクエストペイロード

```json
{
  "class_name": "令和7年度 デジタル中核人材養成研修 №01",
  "task_name": "課題①業務分析　※～11/3〆切",
  "drive_folder_id": "YOUR_FOLDER_ID_HERE",
  "spreadsheet_id": "YOUR_SPREADSHEET_ID_HERE"
}
```

## 5. デプロイ実行

### GitHub経由の自動デプロイ

```bash
# 変更をコミット
git add .
git commit -m "Complete implementation: Drive, Firestore, Sheets integration"
git push origin main
```

### GitHub Actionsの確認

- [ ] `.github/workflows/deploy.yml`のワークフロー実行を確認
- [ ] ビルドが成功したことを確認
- [ ] デプロイが成功したことを確認

### デプロイ後の確認

```bash
# Cloud Run Functionsのステータス確認
gcloud run services describe carewell-file-collector \
  --region=asia-northeast1 \
  --project=carewell-automation

# ログ確認
gcloud run services logs read carewell-file-collector \
  --region=asia-northeast1 \
  --project=carewell-automation \
  --limit=50
```

## 6. テスト実行

### ヘルスチェック（オプション）

関数URLにGETリクエストを送信:
```bash
curl -X GET https://carewell-file-collector-imczapxkba-an.a.run.app
```

### 実地テスト

```bash
curl -X POST https://carewell-file-collector-imczapxkba-an.a.run.app \
  -H "Content-Type: application/json" \
  -d '{
    "class_name": "令和7年度 デジタル中核人材養成研修 №01",
    "task_name": "課題①業務分析　※～11/3〆切",
    "drive_folder_id": "YOUR_FOLDER_ID",
    "spreadsheet_id": "YOUR_SPREADSHEET_ID"
  }'
```

### 期待されるレスポンス

```json
{
  "status": "success",
  "message": "File collection completed",
  "submissions_found": 5,
  "processed": 5,
  "skipped": 0,
  "failed": 0
}
```

## 7. 検証項目

テスト実行後、以下を確認：

- [ ] **Google Drive**
  - フォルダ内にファイルがアップロードされている
  - ファイル名が正しい
  - ファイルが開ける

- [ ] **Firestore**
  - `uploaded_files`コレクションにドキュメントが作成されている
  - `file_hash`が正しく設定されている
  - `drive_file_id`が記録されている

- [ ] **Google Sheets**
  - スプレッドシートに行が追加されている
  - 全カラムにデータが入っている
  - Drive Linkが機能する

- [ ] **重複チェック**
  - 同じリクエストを再実行
  - `skipped`カウントが増加する
  - 新規ファイルは作成されない

- [ ] **ログ確認**
  ```bash
  gcloud run services logs read carewell-file-collector \
    --region=asia-northeast1 \
    --limit=100
  ```

## 8. エラーハンドリング検証

以下のエラーケースをテスト：

- [ ] 存在しないクラス名を指定
- [ ] 存在しない課題名を指定
- [ ] アクセス権のないDriveフォルダIDを指定
- [ ] アクセス権のないSpreadsheet IDを指定
- [ ] 不正なJSONリクエスト
- [ ] 必須パラメータの欠落

期待される動作：
- 適切なエラーメッセージが返される
- ステータスコード 400 または 500
- ログに詳細なエラー情報が記録される

## 9. 本番運用前の最終確認

- [ ] タイムアウト設定が適切（現在: 540秒）
- [ ] メモリ設定が適切（現在: 2Gi）
- [ ] 認証設定の確認（本番では認証を有効化推奨）
- [ ] コスト見積もりの確認
- [ ] モニタリング・アラート設定（オプション）

## トラブルシューティング

### Secret Manager関連エラー

```
Error: Failed to retrieve credentials from Secret Manager
```

**対処法:**
1. シークレットが存在するか確認
2. サービスアカウントに`secretmanager.secretAccessor`権限があるか確認

### Drive API関連エラー

```
Error: Failed to upload file to Google Drive
```

**対処法:**
1. Drive APIが有効か確認
2. サービスアカウントがフォルダにアクセスできるか確認
3. フォルダIDが正しいか確認

### Firestore関連エラー

```
Error: Firestore database not found
```

**対処法:**
1. Firestoreが有効化されているか確認
2. データベースがネイティブモードか確認

### Sheets API関連エラー

```
Error: The caller does not have permission
```

**対処法:**
1. Sheets APIが有効か確認
2. サービスアカウントがスプレッドシートにアクセスできるか確認

## 完了チェック

- [ ] すべての権限が設定されている
- [ ] すべてのAPIが有効化されている
- [ ] テストデータが準備されている
- [ ] デプロイが成功している
- [ ] テストが成功している
- [ ] すべての検証項目をクリアしている
- [ ] ドキュメントが最新の状態である

---

**注意事項:**
- 初回デプロイ時はSecret Managerの認証情報が正しく設定されているか特に注意
- Cloud Run Functionsのコールドスタート時は初回レスポンスに時間がかかる場合がある
- Playwrightのブラウザ起動にメモリを多く消費するため、メモリ設定は2Gi以上推奨
