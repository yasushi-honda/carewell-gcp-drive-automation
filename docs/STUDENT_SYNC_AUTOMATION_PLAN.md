# Student Data Sync Automation Plan (Cloud Scheduler)

**作成日**: 2025-11-18
**対象**: `/admin/sync-students-from-sheets` API の自動実行化
**目的**: Google Sheets の学生データを定期的に Firestore に自動同期

---

## 📋 目次

1. [概要](#概要)
2. [現状と課題](#現状と課題)
3. [提案する自動化](#提案する自動化)
4. [実装計画](#実装計画)
5. [安全性の検証](#安全性の検証)
6. [運用計画](#運用計画)
7. [リスク評価とロールバック計画](#リスク評価とロールバック計画)

---

## 概要

現在、学生データの同期は手動で `/admin/sync-students-from-sheets` API を実行する必要があります。
この API を Cloud Scheduler で定期実行することで、Google Sheets の変更を自動的に Firestore に反映します。

### 自動化のメリット

| メリット | 説明 |
|---------|------|
| ✅ **運用負荷の削減** | 手動実行の手間を削減 |
| ✅ **データの鮮度向上** | 常に最新の学生情報を Dashboard に反映 |
| ✅ **人的ミス防止** | 同期忘れを防止 |
| ✅ **監視の自動化** | Cloud Logging で実行結果を自動記録 |

### デメリット・懸念事項

| 懸念事項 | 対策 |
|---------|------|
| ⚠️ **意図しないデータ上書き** | `merge=True` による差分更新（既存フィールド保持） |
| ⚠️ **Google Sheets の誤入力が即座に反映** | 深夜実行により、日中に修正可能な時間を確保 |
| ⚠️ **API 実行失敗時の通知** | Cloud Monitoring でアラート設定 |

---

## 現状と課題

### 現在の運用フロー

1. **Google Sheets で学生情報を編集**
   - スプレッドシート: `1AQ12-h3n_NmN2kWxi4Z_g354X0wmUyMKAPeAsXJwu_w`
   - シート: `統合_受講者リスト`

2. **手動で API 実行**
   ```bash
   TOKEN=$(gcloud auth print-identity-token)
   curl -X POST \
     "https://carewell-file-collector-imczapxkba-an.a.run.app/admin/sync-students-from-sheets" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json"
   ```

3. **Dashboard で確認**
   - 学生詳細ページで反映を確認

### 課題

| 課題 | 影響 |
|------|------|
| **同期忘れ** | Google Sheets の変更が Dashboard に反映されない |
| **手動実行の手間** | 運用者の負担 |
| **実行タイミングのばらつき** | データの鮮度にばらつき |

---

## 提案する自動化

### Cloud Scheduler Job の新規作成

**Job 名**: `carewell-student-sync-daily`

**スケジュール**: 毎日深夜 2:00（JST）

**CRON 式**: `0 17 * * *`（UTC 17:00 = JST 02:00）

**理由**:
- ✅ 業務時間外のため、影響が少ない
- ✅ Google Sheets の誤入力があっても、翌日の業務時間中に修正可能
- ✅ 既存の File Collector ジョブと時間帯が重ならない

### エンドポイント

**URL**: `https://carewell-file-collector-imczapxkba-an.a.run.app/admin/sync-students-from-sheets`

**メソッド**: POST

**認証**: Cloud Scheduler Service Account

**タイムアウト**: 180秒（3分）

**リトライ設定**:
- 最大リトライ回数: 3回
- リトライ間隔: 指数バックオフ（初回: 10秒、2回目: 30秒、3回目: 90秒）

---

## 実装計画

### Phase 1: 準備と検証（1日）

#### ステップ1.1: API の安全性確認

**確認項目**:
- ✅ `merge=True` による差分更新が正しく動作するか
- ✅ 既存フィールド（手動追加フィールド）が保持されるか
- ✅ 同じ API を複数回実行しても問題ないか（冪等性）

**検証方法**:
```bash
# 1回目実行
TOKEN=$(gcloud auth print-identity-token)
curl -X POST \
  "https://carewell-file-collector-imczapxkba-an.a.run.app/admin/sync-students-from-sheets" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"

# Firestore Console で確認
# 既存フィールドが保持されているか確認

# 2回目実行（冪等性確認）
curl -X POST \
  "https://carewell-file-collector-imczapxkba-an.a.run.app/admin/sync-students-from-sheets" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"

# 同じ結果になることを確認
```

**期待される結果**:
```json
{
  "status": "success",
  "students_synced": 1155,
  "students_created": 0,
  "students_updated": 1155,
  "errors": []
}
```

---

#### ステップ1.2: Cloud Scheduler Service Account の権限確認

**必要な権限**:
- `roles/run.invoker`: Cloud Run サービスを呼び出す権限

**確認コマンド**:
```bash
# Cloud Scheduler のデフォルト Service Account を確認
gcloud iam service-accounts list --filter="email~scheduler" --format="value(email)"

# 出力例: PROJECT_NUMBER-compute@developer.gserviceaccount.com
```

**権限付与（必要な場合）**:
```bash
SERVICE_ACCOUNT="61759806259-compute@developer.gserviceaccount.com"
gcloud run services add-iam-policy-binding carewell-file-collector \
  --region=asia-northeast1 \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/run.invoker"
```

---

### Phase 2: Cloud Scheduler Job 作成（1日）

#### ステップ2.1: Terraform で Job 定義作成（推奨）

**ファイル**: `.github/workflows/deploy-scheduler.yml` に追加

または

**ファイル**: `terraform/scheduler.tf` (新規作成)

```hcl
# terraform/scheduler.tf
resource "google_cloud_scheduler_job" "student_sync" {
  name        = "carewell-student-sync-daily"
  description = "Daily sync of student data from Google Sheets to Firestore"
  schedule    = "0 17 * * *"  # UTC 17:00 = JST 02:00
  time_zone   = "UTC"
  region      = "asia-northeast1"

  retry_config {
    retry_count          = 3
    max_retry_duration   = "0s"
    min_backoff_duration = "10s"
    max_backoff_duration = "300s"
    max_doublings        = 5
  }

  http_target {
    http_method = "POST"
    uri         = "https://carewell-file-collector-imczapxkba-an.a.run.app/admin/sync-students-from-sheets"

    oidc_token {
      service_account_email = "61759806259-compute@developer.gserviceaccount.com"
    }

    headers = {
      "Content-Type" = "application/json"
    }
  }

  attempt_deadline = "180s"  # 3分
}
```

**適用**:
```bash
cd terraform
terraform init
terraform plan
terraform apply
```

---

#### ステップ2.2: gcloud コマンドで直接作成（代替手段）

```bash
gcloud scheduler jobs create http carewell-student-sync-daily \
  --location=asia-northeast1 \
  --schedule="0 17 * * *" \
  --time-zone="UTC" \
  --uri="https://carewell-file-collector-imczapxkba-an.a.run.app/admin/sync-students-from-sheets" \
  --http-method=POST \
  --oidc-service-account-email="61759806259-compute@developer.gserviceaccount.com" \
  --headers="Content-Type=application/json" \
  --attempt-deadline=180s \
  --max-retry-attempts=3 \
  --min-backoff=10s \
  --max-backoff=300s \
  --max-doublings=5
```

**確認**:
```bash
gcloud scheduler jobs describe carewell-student-sync-daily --location=asia-northeast1
```

---

### Phase 3: テスト実行と監視設定（1日）

#### ステップ3.1: 手動トリガーでテスト実行

```bash
gcloud scheduler jobs run carewell-student-sync-daily --location=asia-northeast1
```

**ログ確認**:
```bash
# Cloud Scheduler のログ
gcloud logging read "resource.type=cloud_scheduler_job AND
  resource.labels.job_id=carewell-student-sync-daily" --limit=10

# Cloud Run のログ
gcloud logging read "resource.type=cloud_run_revision AND
  resource.labels.service_name=carewell-file-collector AND
  textPayload=~\"sync-students-from-sheets\"" --limit=20
```

**期待される結果**:
- Cloud Scheduler: `Job execution succeeded`
- Cloud Run: `"status": "success", "students_synced": 1155`

---

#### ステップ3.2: Cloud Monitoring アラート設定

**アラート条件**:
- Cloud Scheduler Job が失敗した場合
- HTTP ステータスコードが 500 系の場合

**通知先**:
- メール（管理者）
- Slack（オプション）

**設定例（gcloud コマンド）**:
```bash
# アラートポリシー作成（例: メール通知）
gcloud alpha monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="Student Sync Job Failure Alert" \
  --condition-display-name="Job Failed" \
  --condition-threshold-value=1 \
  --condition-threshold-duration=60s \
  --condition-filter='resource.type="cloud_scheduler_job" AND
    resource.labels.job_id="carewell-student-sync-daily" AND
    metric.type="logging.googleapis.com/user/job_failed"'
```

---

### Phase 4: 本番運用開始（継続）

#### ステップ4.1: Job の有効化

```bash
gcloud scheduler jobs resume carewell-student-sync-daily --location=asia-northeast1
```

#### ステップ4.2: 運用監視

**日次チェック**:
- Cloud Logging で実行ログを確認
- Firestore Console で学生数を確認

**週次チェック**:
- Dashboard で学生情報が正しく表示されているか確認

---

## 安全性の検証

### 1. 冪等性の確認

**確認済み**: `merge=True` により、同じ API を複数回実行しても安全

**検証結果**:
```python
# src/firestore_service.py Line 480
doc_ref.set(doc_data, merge=True)
```

**動作**:
- 既存ドキュメント: フィールドのみ更新（他のフィールドは保持）
- 新規ドキュメント: 新規作成
- 手動追加フィールド: 削除されない

---

### 2. データ保護

**保護されるデータ**:
- 手動で追加したカスタムフィールド
- Firestore にのみ存在するフィールド

**上書きされるデータ**:
- Google Sheets に存在するフィールド（A～K列）

---

### 3. エラーハンドリング

**API のエラーレスポンス**:
```json
{
  "status": "error",
  "error": "Error message",
  "students_synced": 0
}
```

**Cloud Scheduler のリトライ**:
- 最大3回リトライ
- 指数バックオフ

**失敗時の影響**:
- Firestore のデータは変更されない（トランザクションではないが、部分的な更新は可能）
- 次回の実行時に再度同期

---

### 4. Google Sheets の誤入力対策

**問題**: Google Sheets で誤ったデータを入力した場合、自動同期で Firestore に反映される

**対策**:
1. **深夜実行**: 業務時間外に実行するため、翌日の業務時間中に修正可能
2. **手動ロールバック**: 必要に応じて Google Sheets を修正 → 次回同期で上書き
3. **バックアップ**: Firestore の自動バックアップ機能を有効化（オプション）

---

## 運用計画

### 実行スケジュール

**CRON**: `0 17 * * *`（UTC 17:00 = JST 02:00）

**実行頻度**: 毎日

**実行時間**: 約30秒～1分

### 監視方法

#### 日次監視

**Cloud Logging**:
```bash
gcloud logging read "resource.type=cloud_scheduler_job AND
  resource.labels.job_id=carewell-student-sync-daily" --limit=10
```

**確認項目**:
- ✅ Job execution succeeded
- ✅ HTTP status code 200
- ✅ `students_synced` の数が正しい

#### 週次監視

**Dashboard**:
- https://carewell-automation.web.app/
- 学生一覧ページで学生数を確認
- 学生詳細ページでクラス情報を確認

**Firestore Console**:
- https://console.firebase.google.com/project/carewell-automation/firestore
- `students` コレクションのドキュメント数を確認

---

### トラブルシューティング

#### 問題1: Job が失敗する

**症状**:
- Cloud Logging に `Job execution failed` が記録される

**原因**:
1. API がエラーを返している
2. タイムアウト（180秒超過）
3. Service Account の権限不足

**解決策**:
1. **Cloud Run ログ確認**:
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND
     resource.labels.service_name=carewell-file-collector" --limit=20
   ```

2. **手動実行で確認**:
   ```bash
   TOKEN=$(gcloud auth print-identity-token)
   curl -X POST "https://carewell-file-collector-imczapxkba-an.a.run.app/admin/sync-students-from-sheets" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json"
   ```

3. **権限確認**:
   ```bash
   gcloud run services get-iam-policy carewell-file-collector --region=asia-northeast1
   ```

---

#### 問題2: 学生データが反映されない

**症状**:
- Job は成功するが、Dashboard に反映されない

**原因**:
1. Google Sheets のデータが空
2. API が成功レスポンスを返しているが、実際には更新されていない
3. Dashboard のキャッシュ

**解決策**:
1. **Google Sheets 確認**:
   - スプレッドシート `1AQ12-h3n_NmN2kWxi4Z_g354X0wmUyMKAPeAsXJwu_w` を開く
   - 「統合_受講者リスト」シートにデータが存在するか確認

2. **Firestore 確認**:
   - Firestore Console で `students` コレクションを確認
   - `last_updated` フィールドが最新のタイムスタンプか確認

3. **Dashboard リフレッシュ**:
   - ハードリフレッシュ（Cmd+Shift+R / Ctrl+Shift+R）

---

## リスク評価とロールバック計画

### リスク評価

| リスク | 影響度 | 発生確率 | 対策 |
|--------|--------|---------|------|
| **Google Sheets 誤入力が反映** | 中 | 低 | 深夜実行により日中修正可能 |
| **API 実行失敗** | 低 | 低 | リトライ設定 + アラート |
| **大量の学生データ削除** | 高 | 極低 | 手動ロールバック + Firestore バックアップ |
| **Service Account 権限不足** | 低 | 低 | 事前に権限確認 |

---

### ロールバック計画

#### シナリオ1: 誤ったデータが同期された場合

**手順**:
1. **Google Sheets を修正**
   - 誤ったデータを正しいデータに修正

2. **手動で即座に再同期**
   ```bash
   TOKEN=$(gcloud auth print-identity-token)
   curl -X POST \
     "https://carewell-file-collector-imczapxkba-an.a.run.app/admin/sync-students-from-sheets" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json"
   ```

3. **Dashboard で確認**
   - 正しいデータが反映されていることを確認

---

#### シナリオ2: Cloud Scheduler Job を無効化したい場合

**手順**:
```bash
# Job の一時停止
gcloud scheduler jobs pause carewell-student-sync-daily --location=asia-northeast1

# 確認
gcloud scheduler jobs describe carewell-student-sync-daily --location=asia-northeast1
# STATE: PAUSED

# 再開（必要に応じて）
gcloud scheduler jobs resume carewell-student-sync-daily --location=asia-northeast1
```

---

#### シナリオ3: Cloud Scheduler Job を完全に削除したい場合

**手順**:
```bash
# Job の削除
gcloud scheduler jobs delete carewell-student-sync-daily --location=asia-northeast1

# 確認
gcloud scheduler jobs list --location=asia-northeast1 | grep student-sync
# （何も表示されないことを確認）
```

---

## まとめ

### 実装のメリット

| メリット | 説明 |
|---------|------|
| ✅ **自動化** | 手動実行の手間を削減 |
| ✅ **データ鮮度** | 毎日最新の学生情報に更新 |
| ✅ **安全性** | `merge=True` により既存データを保護 |
| ✅ **監視** | Cloud Logging で自動記録 |

### 推奨スケジュール

| Phase | 所要時間 | 内容 |
|-------|---------|------|
| **Phase 1** | 1日 | 準備と検証 |
| **Phase 2** | 1日 | Cloud Scheduler Job 作成 |
| **Phase 3** | 1日 | テスト実行と監視設定 |
| **Phase 4** | 継続 | 本番運用開始 |

**合計所要時間**: 約3日

---

## 参考資料

### 関連ドキュメント

- **クラス表示機能**: `docs/DASHBOARD_CLASS_DISPLAY.md`
- **クラス名実装**: `docs/class-name-feature-implementation.md`
- **Firestore スキーマ**: `docs/firestore-schema-improvement-implementation.md`

### 関連コード

- **Backend**: `src/main.py` Line 470-520 (`/admin/sync-students-from-sheets`)
- **Firestore Service**: `src/firestore_service.py` Line 456-494 (`create_student`)
- **Sheets Service**: `src/sheets_service.py` Line 238-340 (`get_student_data`)

### Cloud Scheduler ドキュメント

- **公式ドキュメント**: https://cloud.google.com/scheduler/docs
- **CRON 式リファレンス**: https://cloud.google.com/scheduler/docs/configuring/cron-job-schedules

---

**ドキュメント作成日**: 2025-11-18
**最終更新日**: 2025-11-18
**作成者**: Claude Code AI Agent
