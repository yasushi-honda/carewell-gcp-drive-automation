# Cloud Scheduler運用手順書

## 目次

1. [概要](#概要)
2. [ジョブライフサイクル管理](#ジョブライフサイクル管理)
3. [日常運用タスク](#日常運用タスク)
4. [トラブルシューティング](#トラブルシューティング)
5. [緊急時対応手順](#緊急時対応手順)
6. [コスト分析](#コスト分析)
7. [FAQ](#faq)

---

## 概要

本ドキュメントは、Carewell自動ファイル収集システムのCloud Schedulerジョブの運用に関する手順書です。

### 対象読者

- システム運用担当者
- 開発チームメンバー
- インシデント対応担当者

### システム構成

- **ジョブ数**: 現在14ジョブ（7クラス × 2課題）、最大40ジョブまで拡張可能
- **実行間隔**: 30分ごと（各時間の0分と30分、オフセット付き）
- **タイムゾーン**: Asia/Tokyo（日本標準時）
- **実行時間帯**: 24時間365日稼働
- **対象Cloud Run**: `carewell-file-collector`
- **リージョン**: asia-northeast1（東京）
- **認証方式**: OIDC (Service Account)

### 前提知識

- gcloud CLI の基本操作
- Cloud Scheduler と Cloud Run の基礎知識
- JSON形式の理解

---

## ジョブライフサイクル管理

### 1. 新規ジョブの作成

#### 前提条件

- 新しいクラス名/タスクIDが確定している
- Google Driveフォルダが作成されている
- Google Spreadsheetsが作成されている
- `src/config/classes.py` に新しいクラス/タスクが追加されている

#### 手順

**ステップ1: パラメータの準備**

新しいジョブに必要な情報を準備します：

```bash
# 例: クラス10、課題①を追加する場合
CLASS_NUM="10"
TASK_NUM="01"
TASK_NAME="課題①"
CLASS_NAME="令和7年度 デジタル中核人材養成研修 №${CLASS_NUM}"
DRIVE_FOLDER_ID="1xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # Google DriveのフォルダID
SPREADSHEET_ID="1xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"   # Google SheetsのID
```

**ステップ2: Cronスケジュールの決定**

既存のジョブと重複しないようにCronスケジュールを決定します：

```bash
# 現在使用中のスケジュール確認
gcloud scheduler jobs list --location=asia-northeast1 \
  --format="table(name,schedule)" | sort -k2

# 利用可能なスケジュール（5分刻み、30分間隔）
# 0,30 * * * *   (00:00, 00:30, 01:00, 01:30, ...)
# 5,35 * * * *   (00:05, 00:35, 01:05, 01:35, ...)
# 10,40 * * * *  (00:10, 00:40, 01:10, 01:40, ...)
# 15,45 * * * *  (00:15, 00:45, 01:15, 01:45, ...)
# 20,50 * * * *  (00:20, 00:50, 01:20, 01:50, ...)
# 25,55 * * * *  (00:25, 00:55, 01:25, 01:55, ...)
```

**ステップ3: ジョブの作成**

```bash
# 環境変数設定
JOB_NAME="carewell-class${CLASS_NUM}-task${TASK_NUM}"
CLOUD_RUN_URL="https://carewell-file-collector-imczapxkba-an.a.run.app"
SERVICE_ACCOUNT="carewell-automation-sa@carewell-automation.iam.gserviceaccount.com"
LOCATION="asia-northeast1"
TIMEZONE="Asia/Tokyo"
CRON_SCHEDULE="10,40 * * * *"  # 例: 利用可能なスケジュールを選択

# リクエストボディ作成
REQUEST_BODY=$(cat <<EOF
{
  "class_name": "${CLASS_NAME}",
  "task_id": "${TASK_NAME}",
  "task_pattern": "${TASK_NAME}",
  "drive_folder_id": "${DRIVE_FOLDER_ID}",
  "spreadsheet_id": "${SPREADSHEET_ID}"
}
EOF
)

# ジョブ作成
gcloud scheduler jobs create http "${JOB_NAME}" \
  --location="${LOCATION}" \
  --schedule="${CRON_SCHEDULE}" \
  --time-zone="${TIMEZONE}" \
  --uri="${CLOUD_RUN_URL}" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body="${REQUEST_BODY}" \
  --oidc-service-account-email="${SERVICE_ACCOUNT}"

# 作成確認
gcloud scheduler jobs describe "${JOB_NAME}" --location="${LOCATION}"
```

**ステップ4: 動作確認**

```bash
# 手動トリガーでテスト実行
gcloud scheduler jobs run "${JOB_NAME}" --location="${LOCATION}"

# 実行ログ確認（1-2分待機後）
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  jsonPayload.execution_id:*" \
  --limit 5 \
  --format json

# Firestoreで結果確認
# → GCPコンソール → Firestore → データベース: carewell-native
#    → ${CLASS_NAME} → ${TASK_NAME} → documents
```

#### 自動作成スクリプトの使用

複数のジョブを一括作成する場合は、`scripts/create-scheduler-jobs.sh`を編集して使用できます：

```bash
# スクリプトを編集してジョブを追加
vim scripts/create-scheduler-jobs.sh

# ドライランで確認
DRY_RUN=true bash scripts/create-scheduler-jobs.sh

# 実行
DRY_RUN=false bash scripts/create-scheduler-jobs.sh
```

---

### 2. ジョブの一時停止

#### 用途

- 特定のクラスの課題提出期限が終了した場合
- メンテナンス時の一時停止
- コスト削減のための停止

#### 手順

**個別ジョブの一時停止:**

```bash
# ジョブ名を指定して一時停止
gcloud scheduler jobs pause carewell-class01-task01 \
  --location=asia-northeast1

# 確認
gcloud scheduler jobs describe carewell-class01-task01 \
  --location=asia-northeast1 \
  --format="value(state)"
# 出力: PAUSED
```

**複数ジョブの一時停止:**

```bash
# 特定クラスの全ジョブを一時停止（例: クラス01）
for task_num in 01 02; do
  gcloud scheduler jobs pause "carewell-class01-task${task_num}" \
    --location=asia-northeast1
  echo "✓ Paused: carewell-class01-task${task_num}"
done

# 全ジョブを一時停止（メンテナンス時）
gcloud scheduler jobs list --location=asia-northeast1 \
  --format="value(name)" | while read job; do
  gcloud scheduler jobs pause "$job" --location=asia-northeast1
  echo "✓ Paused: $job"
done
```

---

### 3. ジョブの再開

#### 手順

**個別ジョブの再開:**

```bash
# ジョブ名を指定して再開
gcloud scheduler jobs resume carewell-class01-task01 \
  --location=asia-northeast1

# 確認
gcloud scheduler jobs describe carewell-class01-task01 \
  --location=asia-northeast1 \
  --format="value(state)"
# 出力: ENABLED
```

**複数ジョブの再開:**

```bash
# 特定クラスの全ジョブを再開
for task_num in 01 02; do
  gcloud scheduler jobs resume "carewell-class01-task${task_num}" \
    --location=asia-northeast1
  echo "✓ Resumed: carewell-class01-task${task_num}"
done

# 全ジョブを再開
gcloud scheduler jobs list --location=asia-northeast1 \
  --format="value(name)" | while read job; do
  gcloud scheduler jobs resume "$job" --location=asia-northeast1
  echo "✓ Resumed: $job"
done
```

---

### 4. ジョブパラメータの更新

#### よくある更新ケース

- Google DriveフォルダIDの変更
- Google SheetsのIDの変更
- 実行スケジュールの変更

#### 手順

**ステップ1: 現在の設定確認**

```bash
# ジョブの詳細を確認
gcloud scheduler jobs describe carewell-class01-task01 \
  --location=asia-northeast1 \
  --format json > current_job_config.json

# リクエストボディを確認
cat current_job_config.json | jq '.httpTarget.body' -r | base64 -d | jq .
```

**ステップ2: パラメータ更新**

```bash
# 新しいリクエストボディを作成
NEW_REQUEST_BODY=$(cat <<EOF
{
  "class_name": "令和7年度 デジタル中核人材養成研修 №01",
  "task_id": "課題①",
  "task_pattern": "課題①",
  "drive_folder_id": "1NEW_FOLDER_ID_HERE",
  "spreadsheet_id": "1NEW_SPREADSHEET_ID_HERE"
}
EOF
)

# ジョブを更新
gcloud scheduler jobs update http carewell-class01-task01 \
  --location=asia-northeast1 \
  --message-body="${NEW_REQUEST_BODY}"

# 更新確認
gcloud scheduler jobs describe carewell-class01-task01 \
  --location=asia-northeast1 \
  --format json | jq '.httpTarget.body' -r | base64 -d | jq .
```

**ステップ3: 動作確認**

```bash
# 手動トリガーでテスト
gcloud scheduler jobs run carewell-class01-task01 \
  --location=asia-northeast1

# ログで確認（1-2分待機後）
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  jsonPayload.class_name=\"令和7年度 デジタル中核人材養成研修 №01\"" \
  --limit 5
```

**スケジュールの更新:**

```bash
# Cronスケジュールを変更
gcloud scheduler jobs update http carewell-class01-task01 \
  --location=asia-northeast1 \
  --schedule="15,45 * * * *"

# 確認
gcloud scheduler jobs describe carewell-class01-task01 \
  --location=asia-northeast1 \
  --format="value(schedule)"
```

---

### 5. ジョブの削除

#### 注意事項

- 削除したジョブは復元できません
- 削除前に必ずバックアップとして設定をエクスポートしてください
- Firestoreのデータは削除されません（ジョブのみ削除）

#### 手順

**ステップ1: 設定のバックアップ**

```bash
# ジョブ設定をエクスポート
gcloud scheduler jobs describe carewell-class01-task01 \
  --location=asia-northeast1 \
  --format json > backup_carewell-class01-task01_$(date +%Y%m%d).json

# リクエストボディも別途保存
cat backup_carewell-class01-task01_*.json | \
  jq '.httpTarget.body' -r | base64 -d | jq . \
  > backup_carewell-class01-task01_body.json
```

**ステップ2: 削除実行**

```bash
# ジョブ削除
gcloud scheduler jobs delete carewell-class01-task01 \
  --location=asia-northeast1 \
  --quiet

# 削除確認（エラーが返ればOK）
gcloud scheduler jobs describe carewell-class01-task01 \
  --location=asia-northeast1
# 出力: ERROR: (gcloud.scheduler.jobs.describe) NOT_FOUND: ...
```

**複数ジョブの削除:**

```bash
# 特定クラスの全ジョブを削除
for task_num in 01 02; do
  JOB_NAME="carewell-class01-task${task_num}"

  # バックアップ
  gcloud scheduler jobs describe "$JOB_NAME" \
    --location=asia-northeast1 \
    --format json > "backup_${JOB_NAME}_$(date +%Y%m%d).json"

  # 削除
  gcloud scheduler jobs delete "$JOB_NAME" \
    --location=asia-northeast1\
    --quiet

  echo "✓ Deleted: $JOB_NAME"
done
```

---

## 日常運用タスク

### 1. ジョブ実行状況の確認

#### 実行頻度

- **推奨**: 週1回（月曜日午前など）
- **必須**: 新しいジョブ追加後24時間以内

#### 手順

**ステップ1: 全ジョブの状態確認**

```bash
# 全ジョブの一覧と状態を確認
gcloud scheduler jobs list --location=asia-northeast1 \
  --format="table(name,state,schedule,lastAttemptTime.date('%Y-%m-%d %H:%M:%S'),status.message)"
```

**出力例（正常時）:**

```
NAME                        STATE     SCHEDULE           LAST_ATTEMPT_TIME    STATUS_MESSAGE
carewell-class01-task01     ENABLED   0,30 * * * *       2025-10-13 10:30:00  Success
carewell-class01-task02     ENABLED   5,35 * * * *       2025-10-13 10:35:00  Success
carewell-class02-task01     ENABLED   10,40 * * * *      2025-10-13 10:40:00  Success
...
```

**出力例（異常あり）:**

```
NAME                        STATE     SCHEDULE           LAST_ATTEMPT_TIME    STATUS_MESSAGE
carewell-class01-task01     ENABLED   0,30 * * * *       2025-10-13 10:30:00  Success
carewell-class01-task02     ENABLED   5,35 * * * *       2025-10-13 10:35:00  HTTP 500
carewell-class02-task01     PAUSED    10,40 * * * *      2025-10-12 15:00:00  Paused by user
```

**ステップ2: エラー発生ジョブの特定**

```bash
# 最近失敗したジョブを確認（過去24時間）
gcloud logging read "resource.type=cloud_scheduler_job AND \
  severity=ERROR" \
  --limit 50 \
  --format json \
  --freshness=24h | \
  jq -r '.[] | "\(.timestamp) \(.resource.labels.job_name) \(.textPayload // .jsonPayload.message)"'
```

**ステップ3: 成功率の確認**

```bash
# 各ジョブの成功/失敗回数をカウント（過去7日間）
for job in $(gcloud scheduler jobs list --location=asia-northeast1 --format="value(name)"); do
  echo "=== $job ==="

  # 成功回数
  SUCCESS_COUNT=$(gcloud logging read "resource.type=cloud_scheduler_job AND \
    resource.labels.job_name=\"$job\" AND \
    jsonPayload.status=~\"200|204\"" \
    --format json \
    --freshness=7d | jq '. | length')

  # 失敗回数
  FAILURE_COUNT=$(gcloud logging read "resource.type=cloud_scheduler_job AND \
    resource.labels.job_name=\"$job\" AND \
    severity>=ERROR" \
    --format json \
    --freshness=7d | jq '. | length')

  echo "  Success: $SUCCESS_COUNT"
  echo "  Failure: $FAILURE_COUNT"
  echo ""
done
```

---

### 2. エラーログの確認

#### 実行頻度

- **推奨**: 週2回（月・木曜日など）
- **必須**: エラー通知を受け取った際

#### 手順

**ステップ1: Cloud Schedulerのエラーログ確認**

```bash
# 最近のSchedulerエラーログを確認（過去1時間）
gcloud logging read "resource.type=cloud_scheduler_job AND \
  severity>=ERROR" \
  --limit 50 \
  --format json \
  --freshness=1h
```

**ステップ2: Cloud Runのエラーログ確認**

```bash
# Cloud Run Functionのエラーログを確認
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  severity>=ERROR" \
  --limit 50 \
  --format json \
  --freshness=1h
```

**ステップ3: 特定ジョブのログ確認**

```bash
# 特定ジョブの詳細ログを確認
JOB_NAME="carewell-class01-task01"

gcloud logging read "resource.type=cloud_scheduler_job AND \
  resource.labels.job_name=\"${JOB_NAME}\"" \
  --limit 20 \
  --format json
```

---

### 3. ダッシュボード確認

#### Carewell Dashboardでの確認

現在開発中のダッシュボード: https://carewell-automation.web.app/

**確認項目:**
- [ ] 各クラス/タスクのファイル提出数
- [ ] 最終更新日時
- [ ] エラー発生状況

#### Cloud Console Metrics Explorerでの確認

1. **GCPコンソール** → **Cloud Scheduler** → **ジョブ一覧**
2. 各ジョブをクリック → **メトリクス**タブ
3. 確認項目：
   - 実行回数（Request count）
   - 成功率（Success rate）
   - エラー率（Error rate）
   - レイテンシ（Latency）

---

### 4. 定期チェックリスト

#### 週次チェック（推奨: 毎週月曜日10:00）

```bash
# 1. 全ジョブの状態確認
echo "=== 1. ジョブ状態確認 ==="
gcloud scheduler jobs list --location=asia-northeast1 \
  --format="table(name,state,schedule,lastAttemptTime)"

# 2. 最近のエラー確認（過去7日間）
echo -e "\n=== 2. エラーログ確認 ==="
gcloud logging read "resource.type=cloud_scheduler_job AND \
  severity>=ERROR" \
  --limit 20 \
  --format json \
  --freshness=7d | \
  jq -r '.[] | "\(.timestamp) \(.resource.labels.job_name) \(.jsonPayload.message // .textPayload)"'

# 3. Firestore file_count確認
echo -e "\n=== 3. Firestore file_count確認 ==="
python scripts/fix_file_count.py --dry-run

# 4. 結果を記録
echo -e "\n✓ 週次チェック完了: $(date)"
```

#### チェックリスト

- [ ] 全14ジョブがENABLED状態である
- [ ] 過去7日間で重大なエラーがない
- [ ] 各ジョブの最終実行が24時間以内である
- [ ] Firestoreのfile_count不整合がない
- [ ] Cloud Run Functionが正常に稼働している

---

## トラブルシューティング

### トラブルシューティングフロー図

```
エラー発生
    ↓
┌───────────────────────────────────┐
│ 1. エラーの種類を特定              │
│   - Schedulerエラー？              │
│   - Cloud Runエラー？              │
│   - アプリケーションエラー？       │
└───────────────────────────────────┘
    ↓
┌───────────────────────────────────┐
│ 2. 影響範囲の確認                  │
│   - 単一ジョブ？                   │
│   - 複数ジョブ？                   │
│   - 全ジョブ？                     │
└───────────────────────────────────┘
    ↓
┌───────────────────────────────────┐
│ 3. ログ収集                        │
│   - Schedulerログ                  │
│   - Cloud Runログ                  │
│   - Firestoreログ                  │
└───────────────────────────────────┘
    ↓
┌───────────────────────────────────┐
│ 4. 原因特定と対応                  │
│   → 下記の「よくあるエラーと対応」 │
└───────────────────────────────────┘
    ↓
┌───────────────────────────────────┐
│ 5. 解決確認                        │
│   - ジョブ手動実行でテスト         │
│   - 次回定期実行を監視             │
└───────────────────────────────────┘
    ↓
┌───────────────────────────────────┐
│ 6. ポストモーテム作成（重大な場合）│
│   - 原因、影響、対応、再発防止策   │
└───────────────────────────────────┘
```

---

### よくあるエラーと対応

#### エラー1: HTTP 403 Forbidden

**症状:**

```
ERROR: HTTP request failed with status code 403
Message: Your client does not have permission to get URL /
```

**原因:**
- OIDC認証の失敗
- Service Accountの権限不足

**対応手順:**

```bash
# 1. Service Accountの権限確認
gcloud projects get-iam-policy carewell-automation \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:carewell-automation-sa@carewell-automation.iam.gserviceaccount.com"

# 2. 必要な権限を付与（不足している場合）
gcloud run services add-iam-policy-binding carewell-file-collector \
  --member="serviceAccount:carewell-automation-sa@carewell-automation.iam.gserviceaccount.com" \
  --role="roles/run.invoker" \
  --region=asia-northeast1

# 3. Cloud Runの認証設定確認
gcloud run services describe carewell-file-collector \
  --region=asia-northeast1 \
  --format="value(status.url,spec.template.metadata.annotations)"
```

---

#### エラー2: HTTP 500 Internal Server Error

**症状:**

```
ERROR: HTTP request failed with status code 500
Message: Internal Server Error
```

**原因:**
- アプリケーション内部のエラー
- Playwright認証失敗
- Firestore接続エラー

**対応手順:**

```bash
# 1. Cloud Runログで詳細を確認
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  severity>=ERROR" \
  --limit 10 \
  --format json

# 2. 特定エラーパターンで検索
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  textPayload:\"Playwright\" OR textPayload:\"Authentication failed\"" \
  --limit 5

# 3. 手動トリガーでデバッグ
gcloud scheduler jobs run carewell-class01-task01 \
  --location=asia-northeast1

# 4. リアルタイムログ監視（別ターミナル）
gcloud logging tail "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector"
```

**よくある500エラーの原因:**

1. **Carewell認証失敗**
   - Secret Managerの認証情報を確認
   - Carewellサービスの稼働状況を確認

2. **タイムアウト**
   - Cloud Runのタイムアウト設定を確認（現在540秒）
   - 処理対象のファイル数を確認

3. **Firestore接続エラー**
   - Firestoreのステータスを確認: https://status.cloud.google.com/

---

#### エラー3: HTTP 504 Gateway Timeout

**症状:**

```
ERROR: HTTP request failed with status code 504
Message: Upstream request timeout
```

**原因:**
- Cloud Run Functionの実行時間が540秒（9分）を超過
- 大量のファイル処理

**対応手順:**

```bash
# 1. 実行時間を確認
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  httpRequest.latency>500s" \
  --limit 10 \
  --format json

# 2. 処理ファイル数を確認
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  jsonPayload.summary.processed_files>*" \
  --limit 10 \
  --format json | \
  jq -r '.[] | "\(.timestamp) Files: \(.jsonPayload.summary.processed_files)"'

# 3. タイムアウト設定を増加（最大3600秒まで可能）
gcloud run services update carewell-file-collector \
  --timeout=900s \
  --region=asia-northeast1
```

**恒久的対策:**
- バッチ処理の導入（一度に処理する件数を制限）
- 非同期処理の導入

---

#### エラー4: Job is PAUSED

**症状:**

```
Job carewell-class01-task01 is in PAUSED state and will not execute
```

**原因:**
- 意図的な一時停止
- 意図しない一時停止（誤操作など）

**対応手順:**

```bash
# 1. PAUSED状態のジョブを確認
gcloud scheduler jobs list --location=asia-northeast1 \
  --filter="state=PAUSED" \
  --format="table(name,state,lastAttemptTime)"

# 2. 再開が必要なジョブを再開
gcloud scheduler jobs resume carewell-class01-task01 \
  --location=asia-northeast1

# 3. 確認
gcloud scheduler jobs describe carewell-class01-task01 \
  --location=asia-northeast1 \
  --format="value(state)"
```

---

#### エラー5: DEADLINE_EXCEEDED

**症状:**

```
ERROR: Failed to update task document: DEADLINE_EXCEEDED
```

**原因:**
- Firestoreへの書き込みタイムアウト
- Firestoreの負荷が高い

**対応手順:**

```bash
# 1. Firestoreの負荷を確認
# GCPコンソール → Firestore → モニタリング

# 2. file_count不整合を確認・修正
python scripts/fix_file_count.py --dry-run
python scripts/fix_file_count.py --execute

# 3. Firestoreインデックスを確認
gcloud firestore indexes list --database=carewell-native

# 4. 問題が継続する場合、GCPサポートに連絡
```

---

#### エラー6: OUT_OF_RANGE (Too many files)

**症状:**

```
ERROR: Processed too many files (100+) in single execution
```

**原因:**
- 長期間ジョブが停止していた
- 大量の課題提出

**対応手順:**

```bash
# 1. 影響範囲を確認
JOB_NAME="carewell-class01-task01"
CLASS_NAME="令和7年度 デジタル中核人材養成研修 №01"
TASK_ID="課題①"

# Firestoreでドキュメント数を確認
gcloud firestore collections list --database=carewell-native

# 2. 一時的にジョブを手動実行（複数回に分けて処理）
for i in {1..5}; do
  echo "=== Attempt $i ==="
  gcloud scheduler jobs run "$JOB_NAME" --location=asia-northeast1
  sleep 600  # 10分待機
done

# 3. 処理状況をモニタリング
gcloud logging tail "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector"
```

---

## 緊急時対応手順

### シナリオ1: 全ジョブ連続失敗

#### 症状

- 全てのSchedulerジョブが連続して失敗している（3回以上）
- すべてHTTP 500またはHTTP 504エラー

#### 緊急度: **P0 (Critical)** - 即時対応

#### 対応手順

**フェーズ1: 緊急停止（5分以内）**

```bash
# 1. 全ジョブを一時停止
gcloud scheduler jobs list --location=asia-northeast1 \
  --format="value(name)" | while read job; do
  gcloud scheduler jobs pause "$job" --location=asia-northeast1
  echo "✓ Paused: $job"
done

# 2. チームに緊急連絡
# Slack: #carewell-automation
# 件名: [P0] 全Cloud Schedulerジョブ連続失敗
# 内容: 全ジョブが連続失敗したため一時停止しました。調査開始。
```

**フェーズ2: 原因調査（15分以内）**

```bash
# 1. Cloud Runサービスの状態確認
gcloud run services describe carewell-file-collector \
  --region=asia-northeast1 \
  --format json > /tmp/cloudrun_status_$(date +%Y%m%d_%H%M%S).json

# 2. 最近のデプロイ確認
gcloud run revisions list \
  --service=carewell-file-collector \
  --region=asia-northeast1 \
  --limit 5

# 3. エラーログ収集（過去1時間）
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  severity>=ERROR" \
  --limit 100 \
  --format json \
  --freshness=1h > /tmp/error_logs_$(date +%Y%m%d_%H%M%S).json

# 4. GCPサービスステータス確認
# https://status.cloud.google.com/
# → Cloud Run, Firestore, Secret Manager のステータスを確認
```

**フェーズ3: 復旧対応（30分以内）**

**ケース1: 最近のデプロイが原因の場合**

```bash
# 前のリビジョンにロールバック
PREVIOUS_REVISION=$(gcloud run revisions list \
  --service=carewell-file-collector \
  --region=asia-northeast1 \
  --format="value(name)" \
  --limit=2 | tail -n 1)

gcloud run services update-traffic carewell-file-collector \
  --to-revisions="${PREVIOUS_REVISION}=100" \
  --region=asia-northeast1

# 確認
gcloud run services describe carewell-file-collector \
  --region=asia-northeast1 \
  --format="value(status.traffic)"
```

**ケース2: GCPサービス障害の場合**

```bash
# 1. GCPステータスページを確認
# 2. 復旧を待つ（Schedulerは自動リトライする）
# 3. 復旧後、ジョブを手動実行して確認
gcloud scheduler jobs run carewell-class01-task01 --location=asia-northeast1

# 4. 問題なければ全ジョブを再開
gcloud scheduler jobs list --location=asia-northeast1 \
  --format="value(name)" | while read job; do
  gcloud scheduler jobs resume "$job" --location=asia-northeast1
  echo "✓ Resumed: $job"
done
```

**ケース3: Carewell Webサービス側の問題**

```bash
# 1. Carewell Webサービスにアクセス可能か確認
# https://jaccw-carewel.study.jp/

# 2. 認証情報が正しいか確認（Secret Manager）
gcloud secrets versions access latest --secret="carewell-user-id"
gcloud secrets versions access latest --secret="carewell-password"

# 3. Carewell側の復旧を待つ
# 4. 復旧後、ジョブを再開
```

**フェーズ4: 監視継続（24時間）**

```bash
# 1. ジョブを段階的に再開（まず1つのジョブで確認）
gcloud scheduler jobs resume carewell-class01-task01 --location=asia-northeast1

# 2. 30分後に実行ログを確認
gcloud logging read "resource.type=cloud_scheduler_job AND \
  resource.labels.job_name=\"carewell-class01-task01\"" \
  --limit 5 \
  --format json

# 3. 成功が確認できたら残りのジョブを再開
gcloud scheduler jobs list --location=asia-northeast1 \
  --filter="state=PAUSED" \
  --format="value(name)" | while read job; do
  gcloud scheduler jobs resume "$job" --location=asia-northeast1
  echo "✓ Resumed: $job"
  sleep 2
done

# 4. 24時間監視
# - 1時間ごとにエラーログを確認
# - 異常があれば再度対応
```

---

### シナリオ2: API Quota超過

#### 症状

```
ERROR: 429 Resource exhausted
Message: Quota exceeded for quota metric 'Read requests' and limit 'Read requests per minute' of service 'firestore.googleapis.com'
```

#### 緊急度: **P1 (High)** - 2時間以内

#### 対応手順

**ステップ1: 影響範囲の確認**

```bash
# 1. Quota超過ログを確認
gcloud logging read "resource.type=cloud_run_revision AND \
  textPayload:\"429\" OR textPayload:\"Quota exceeded\"" \
  --limit 50 \
  --format json \
  --freshness=1h

# 2. 現在のQuota使用状況を確認
# GCPコンソール → IAM & Admin → Quotas
# → Firestore API → Read requests per minute
```

**ステップ2: 緊急対応**

```bash
# オプション1: ジョブ実行頻度を一時的に削減
# 30分間隔 → 60分間隔に変更

for job in $(gcloud scheduler jobs list --location=asia-northeast1 --format="value(name)"); do
  # 現在のスケジュール取得
  CURRENT_SCHEDULE=$(gcloud scheduler jobs describe "$job" \
    --location=asia-northeast1 \
    --format="value(schedule)")

  # 60分間隔に変更（例: "0,30 * * * *" → "0 * * * *"）
  if [[ "$CURRENT_SCHEDULE" == "0,30 * * * *" ]]; then
    gcloud scheduler jobs update http "$job" \
      --location=asia-northeast1 \
      --schedule="0 * * * *"
    echo "✓ Updated: $job (0,30 → 0)"
  fi
  # ... 他のパターンも同様に変更
done

# オプション2: Quota増加リクエスト
# GCPコンソール → IAM & Admin → Quotas
# → Firestore API → "Read requests per minute" → "Edit Quotas"
# → 増加リクエストを送信
```

**ステップ3: 恒久的対策**

1. **Quota増加リクエスト**
   - GCPサポートに連絡
   - 現在の使用状況と増加理由を説明
   - 承認まで数日かかる場合あり

2. **アプリケーション最適化**
   - Firestoreクエリの最適化
   - キャッシュの導入
   - バッチ処理の見直し

---

### シナリオ3: Cloud Run Function OOM (Out of Memory)

#### 症状

```
ERROR: Memory limit exceeded
Message: The request failed because the instance had insufficient memory.
```

#### 緊急度: **P1 (High)** - 2時間以内

#### 対応手順

**ステップ1: メモリ使用状況の確認**

```bash
# 1. OOMエラーログを確認
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  textPayload:\"Memory limit\" OR textPayload:\"OOM\"" \
  --limit 20 \
  --format json

# 2. 現在のメモリ設定を確認
gcloud run services describe carewell-file-collector \
  --region=asia-northeast1 \
  --format="value(spec.template.spec.containers[0].resources.limits.memory)"
```

**ステップ2: 緊急対応**

```bash
# メモリを増加（現在2GB → 4GBに増加）
gcloud run services update carewell-file-collector \
  --memory=4Gi \
  --region=asia-northeast1

# 確認
gcloud run services describe carewell-file-collector \
  --region=asia-northeast1 \
  --format="value(spec.template.spec.containers[0].resources.limits.memory)"
```

**ステップ3: 原因調査**

```bash
# 1. メモリリーク調査
# → 開発チームに連絡してプロファイリング

# 2. 処理ファイル数の確認
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  jsonPayload.summary.processed_files>50" \
  --limit 10 \
  --format json

# 3. Playwrightブラウザインスタンスのリーク確認
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  textPayload:\"browser.close()\"" \
  --limit 10
```

**ステップ4: 恒久的対策**

1. **コードの最適化**
   - Playwrightブラウザインスタンスの適切なクローズ
   - 大きなファイルのストリーミング処理
   - 不要なオブジェクトの削除

2. **メモリ設定の調整**
   - 最大8GBまで増加可能
   - コストとのバランスを考慮

---

## コスト分析

### 現在のコスト構造

#### Cloud Scheduler料金

**料金体系:**
- ジョブあたり月額: $0.10/ジョブ（最初3ジョブは無料）
- ジョブ実行: 最初100万回/月は無料、以降 $0.4/100万実行

#### 現在の構成（14ジョブ、24時間稼働）

**Schedulerジョブ料金:**
```
課金対象ジョブ数: 14 - 3 (無料枠) = 11ジョブ
月額: 11ジョブ × $0.10 = $1.10 (約165円)
```

**ジョブ実行回数料金:**
```
1ジョブの実行回数: 48回/日 × 30日 = 1,440回/月
全ジョブの実行回数: 1,440回 × 14ジョブ = 20,160回/月

無料枠内のため: $0
```

**Cloud Run料金（概算）:**
```
実行時間: 平均30秒/実行 × 20,160実行 = 604,800秒/月 = 168時間/月
メモリ: 2GB
CPU: 1 vCPU

料金: 約 $0.50/月 (約75円)
※ 無料枠（月2百万vCPU秒、360,000 GB秒）あり
```

**合計（現在14ジョブ、24時間稼働）:**
```
Scheduler: $1.10 (約165円)
Cloud Run: $0.50 (約75円)
合計: $1.60/月 (約240円/月)
```

---

### コストシナリオ分析

#### シナリオ1: 現在の構成（14ジョブ、24時間稼働）

| 項目 | 詳細 | 月額（USD） | 月額（円） |
|------|------|------------|-----------|
| Scheduler ジョブ | 14ジョブ - 3無料 = 11ジョブ | $1.10 | ¥165 |
| Scheduler 実行 | 20,160回/月（無料枠内） | $0.00 | ¥0 |
| Cloud Run | 168時間/月、2GB | $0.50 | ¥75 |
| **合計** | | **$1.60** | **¥240** |

---

#### シナリオ2: 営業時間のみ稼働（6:00-22:00、16時間/日）

**想定:**
- 課題提出は主に営業時間に行われる
- 深夜の実行を停止してコスト削減

**Cronスケジュール例:**
```
# 6:00-22:00のみ実行（30分間隔）
0,30 6-22 * * *   # 00:00, 00:30 を 06:00, 06:30 に変更
```

**コスト:**
```
Scheduler ジョブ: $1.10（変わらず）
実行回数: 32回/日 × 30日 × 14ジョブ = 13,440回/月（無料枠内）
Cloud Run: 約112時間/月 → $0.33

合計: $1.43/月 (約215円/月)
節約: $0.17/月 (約25円/月、10%削減)
```

**メリット:**
- わずかなコスト削減
- 深夜のGCP障害リスク回避

**デメリット:**
- 深夜に提出されたファイルは翌朝6:00まで処理されない
- 即時性が低下

**推奨:** 現状の提出パターンが不明なため、**24時間稼働を推奨**

---

#### シナリオ3: 最大40ジョブ（全クラス展開、24時間稼働）

**想定:**
- 将来的に研修クラスが増加
- 20クラス × 2課題 = 40ジョブ

**コスト:**
```
Scheduler ジョブ: (40 - 3) × $0.10 = $3.70
実行回数: 48回/日 × 30日 × 40ジョブ = 57,600回/月（無料枠内）
Cloud Run: 約480時間/月 → $1.40

合計: $5.10/月 (約765円/月)
増加: +$3.50/月 (+525円/月、26ジョブ増加分)
```

**スケーラビリティ:**
- 14ジョブ → 40ジョブで約3.2倍のコスト増
- ジョブあたり $0.13/月（約20円/月）と非常に安価

---

#### シナリオ4: 最大40ジョブ、営業時間のみ稼働

**コスト:**
```
Scheduler ジョブ: $3.70（変わらず）
Cloud Run: 約320時間/月 → $0.93

合計: $4.63/月 (約695円/月)
節約: $0.47/月 (約70円/月、9%削減)
```

---

### コスト最適化の推奨事項

#### 推奨1: 現状維持（24時間稼働、14ジョブ）

**理由:**
- コストが非常に低い（月額240円）
- 即時性が最も高い（30分以内に処理）
- 運用が単純（スケジュール変更不要）
- 課題提出パターンが不明

**コスト:** ¥240/月

---

#### 推奨2: 段階的な稼働時間最適化

**フェーズ1: データ収集（3ヶ月）**
- 24時間稼働を継続
- 時間帯別の課題提出数を記録

```bash
# 時間帯別の処理ファイル数を集計
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  jsonPayload.summary.processed_files>0" \
  --format json \
  --freshness=30d | \
  jq -r '.[] | "\(.timestamp) \(.jsonPayload.summary.processed_files)"' | \
  awk '{print substr($2,1,2)}' | sort | uniq -c

# 出力例:
#  150 06  (6時台に150ファイル処理)
#   80 07
#   ...
#    5 22
#    0 23  (23時台は0ファイル)
#    0 00
```

**フェーズ2: 最適化（3ヶ月後）**
- データに基づいて稼働時間を調整
- 例: 深夜0:00-6:00に提出がほぼゼロなら、6:00-24:00稼働に変更

---

#### 推奨3: 将来的な拡張（40ジョブ）への準備

**現在のコスト（14ジョブ）:** ¥240/月
**将来のコスト（40ジョブ）:** ¥765/月

**増加分:** ¥525/月（26ジョブ増加）

**準備事項:**
- 予算確保（年間¥10,000程度）
- スケジュール設計（5分刻みで最大12ジョブ/30分まで配置可能 → 24ジョブ/時間）
- 40ジョブの場合、一部を60分間隔に変更する必要あり

---

### コスト内訳詳細

#### Cloud Scheduler料金詳細

**ジョブ数別の月額料金:**

| ジョブ数 | 課金対象 | 月額（USD） | 月額（円） |
|---------|---------|------------|-----------|
| 3 | 0（無料枠） | $0.00 | ¥0 |
| 14 | 11 | $1.10 | ¥165 |
| 20 | 17 | $1.70 | ¥255 |
| 30 | 27 | $2.70 | ¥405 |
| 40 | 37 | $3.70 | ¥555 |
| 50 | 47 | $4.70 | ¥705 |

**実行回数別の料金:**

| 実行回数/月 | 課金対象 | 料金（USD） | 料金（円） |
|-----------|---------|------------|-----------|
| 〜100万回 | 0（無料枠） | $0.00 | ¥0 |
| 200万回 | 100万回 | $0.40 | ¥60 |
| 500万回 | 400万回 | $1.60 | ¥240 |

※ 現在の実行回数（20,160回/月）は無料枠の0.002%のみ使用

---

#### Cloud Run料金詳細

**料金体系:**
- CPU: $0.00002400/vCPU秒
- メモリ: $0.00000250/GB秒
- リクエスト: 最初200万回/月無料、以降 $0.40/100万回

**現在の構成（2GB、平均30秒/実行、20,160実行/月）:**

```
CPU時間: 20,160実行 × 30秒 × 1vCPU = 604,800 vCPU秒
CPU料金: 604,800 × $0.000024 = $14.52
無料枠: 月2百万vCPU秒
実質課金: 0 vCPU秒 → $0.00

メモリ: 20,160実行 × 30秒 × 2GB = 1,209,600 GB秒
メモリ料金: 1,209,600 × $0.0000025 = $3.02
無料枠: 月360,000 GB秒
実質課金: 849,600 GB秒 × $0.0000025 = $2.12

リクエスト料金: 20,160回（無料枠内） = $0.00

合計: $2.12/月 ≈ $0.50/月（実際は無料枠と組み合わせで変動）
```

※ 実際の料金はGCPコンソールの請求書で確認してください

---

#### 総コスト予測

**年間コスト予測:**

| 構成 | 月額 | 年額 |
|------|------|------|
| 現在（14ジョブ、24h） | ¥240 | ¥2,880 |
| 営業時間（14ジョブ、16h） | ¥215 | ¥2,580 |
| 最大（40ジョブ、24h） | ¥765 | ¥9,180 |
| 最大（40ジョブ、16h） | ¥695 | ¥8,340 |

**結論:**
- 現在のコスト（¥240/月）は非常に低く、最適化の優先度は低い
- 将来的に40ジョブに拡張しても年間約¥10,000と許容範囲内
- **推奨: 現状の24時間稼働を継続**

---

## FAQ

### Q1: ジョブが連続で3回失敗した場合、自動的に停止されますか？

**A:** いいえ、Cloud Schedulerは自動的にジョブを停止しません。設定されたスケジュールで実行を続けます。

エラーが継続する場合は、手動で一時停止する必要があります：

```bash
gcloud scheduler jobs pause carewell-class01-task01 \
  --location=asia-northeast1
```

監視とアラートを設定して、連続失敗を検知することを推奨します（タスク10.4.4）。

---

### Q2: ジョブのスケジュールは後から変更できますか？

**A:** はい、いつでも変更可能です：

```bash
gcloud scheduler jobs update http carewell-class01-task01 \
  --location=asia-northeast1 \
  --schedule="0 * * * *"  # 60分間隔に変更
```

変更は即座に反映されます。次回の実行から新しいスケジュールで実行されます。

---

### Q3: ジョブを誤って削除してしまった場合、復元できますか？

**A:** いいえ、削除したジョブは復元できません。再作成する必要があります。

削除前に必ず設定をバックアップしてください：

```bash
gcloud scheduler jobs describe carewell-class01-task01 \
  --location=asia-northeast1 \
  --format json > backup_job.json
```

---

### Q4: 30分間隔ではなく、60分間隔に変更したい場合は？

**A:** スケジュールを更新してください：

```bash
# 現在: 0,30 * * * * (30分間隔)
# 変更後: 0 * * * * (60分間隔)

gcloud scheduler jobs update http carewell-class01-task01 \
  --location=asia-northeast1 \
  --schedule="0 * * * *"
```

---

### Q5: 複数のジョブが同時に実行されると、Cloud Runの負荷が高くなりませんか？

**A:** 現在の設計では、各ジョブは5分刻みでオフセットされているため、同時実行は最大でも同じオフセットを持つジョブのみです。

例:
- 10:00 → class01-task01, class04-task01, class09-task01 (3ジョブ)
- 10:05 → class01-task02, class04-task02, class09-task02 (3ジョブ)

Cloud Runは自動スケーリングするため、問題ありません。各インスタンスは1リクエストのみ処理します。

---

### Q6: Schedulerジョブの最大数は？

**A:** Cloud Schedulerの制限は以下の通りです：

- **プロジェクトあたりのジョブ数:** 100個（デフォルト）
- **リージョンあたりのジョブ数:** 制限なし
- **同時実行リクエスト数:** 制限なし（Cloud Runがスケーリング）

現在14ジョブ、最大40ジョブを想定しているため、制限には十分余裕があります。

---

### Q7: タイムゾーンを変更したい場合は？

**A:** ジョブ作成時に指定したタイムゾーン（Asia/Tokyo）は後から変更可能です：

```bash
gcloud scheduler jobs update http carewell-class01-task01 \
  --location=asia-northeast1 \
  --time-zone="America/Los_Angeles"
```

ただし、日本のサービスであるため、変更する必要はありません。

---

### Q8: ジョブの実行履歴はどこで確認できますか？

**A:** Cloud Loggingで確認できます：

```bash
# 特定ジョブの実行履歴（過去7日間）
gcloud logging read "resource.type=cloud_scheduler_job AND \
  resource.labels.job_name=\"carewell-class01-task01\"" \
  --limit 100 \
  --format json \
  --freshness=7d | \
  jq -r '.[] | "\(.timestamp) \(.jsonPayload.status // .jsonPayload.message)"'
```

GCPコンソールでも確認可能:
- Cloud Scheduler → ジョブ名をクリック → "ログ"タブ

---

### Q9: 手動でジョブを実行した場合、次回のスケジュール実行に影響しますか？

**A:** いいえ、影響しません。手動実行は通常のスケジュール実行とは独立しています。

```bash
# 手動実行
gcloud scheduler jobs run carewell-class01-task01 --location=asia-northeast1

# 次回のスケジュール実行は予定通り実行されます
```

---

### Q10: 新しいクラスを追加する際、既存のジョブに影響しますか？

**A:** いいえ、既存のジョブには影響しません。新しいジョブは独立して作成されます。

ただし、以下を確認してください：
- スケジュールが既存ジョブと重複していないか
- Cloud Runの同時実行数が適切か
- コストへの影響

---

## 付録

### A. Cronスケジュール一覧表

現在の14ジョブのスケジュール配置：

| 時刻 | Cron式 | 配置ジョブ |
|------|--------|-----------|
| XX:00, XX:30 | `0,30 * * * *` | class01-task01, class04-task01, class09-task01 |
| XX:05, XX:35 | `5,35 * * * *` | class01-task02, class04-task02, class09-task02 |
| XX:10, XX:40 | `10,40 * * * *` | class02-task01, class05-task01 |
| XX:15, XX:45 | `15,45 * * * *` | class02-task02, class05-task02 |
| XX:20, XX:50 | `20,50 * * * *` | class03-task01, class08-task01 |
| XX:25, XX:55 | `25,55 * * * *` | class03-task02, class08-task02 |

**利用可能なスロット（将来の拡張用）:**
- 各スロットに最大3-4ジョブ配置可能
- 合計で最大約40-50ジョブまで配置可能

---

### B. よく使うコマンド集

```bash
# ========================================
# ジョブ管理
# ========================================

# 全ジョブの一覧表示
gcloud scheduler jobs list --location=asia-northeast1

# ジョブの詳細表示
gcloud scheduler jobs describe JOB_NAME --location=asia-northeast1

# ジョブの手動実行
gcloud scheduler jobs run JOB_NAME --location=asia-northeast1

# ジョブの一時停止
gcloud scheduler jobs pause JOB_NAME --location=asia-northeast1

# ジョブの再開
gcloud scheduler jobs resume JOB_NAME --location=asia-northeast1

# ジョブの削除
gcloud scheduler jobs delete JOB_NAME --location=asia-northeast1

# ========================================
# ログ確認
# ========================================

# Schedulerのログ確認
gcloud logging read "resource.type=cloud_scheduler_job" \
  --limit 50 --format json

# 特定ジョブのログ確認
gcloud logging read "resource.type=cloud_scheduler_job AND \
  resource.labels.job_name=\"JOB_NAME\"" \
  --limit 20

# エラーログのみ確認
gcloud logging read "resource.type=cloud_scheduler_job AND \
  severity>=ERROR" \
  --limit 50

# Cloud Runのログ確認
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector" \
  --limit 50

# ========================================
# 状態確認
# ========================================

# 全ジョブの状態確認
gcloud scheduler jobs list --location=asia-northeast1 \
  --format="table(name,state,schedule,lastAttemptTime)"

# PAUSED状態のジョブのみ確認
gcloud scheduler jobs list --location=asia-northeast1 \
  --filter="state=PAUSED" \
  --format="table(name,state)"

# 最近失敗したジョブの確認
gcloud logging read "resource.type=cloud_scheduler_job AND \
  severity=ERROR" \
  --limit 20 \
  --format json \
  --freshness=24h

# ========================================
# 一括操作
# ========================================

# 全ジョブを一時停止
gcloud scheduler jobs list --location=asia-northeast1 \
  --format="value(name)" | while read job; do
  gcloud scheduler jobs pause "$job" --location=asia-northeast1
done

# 全ジョブを再開
gcloud scheduler jobs list --location=asia-northeast1 \
  --format="value(name)" | while read job; do
  gcloud scheduler jobs resume "$job" --location=asia-northeast1
done

# 全ジョブの設定をバックアップ
mkdir -p backups/scheduler_$(date +%Y%m%d)
gcloud scheduler jobs list --location=asia-northeast1 \
  --format="value(name)" | while read job; do
  gcloud scheduler jobs describe "$job" \
    --location=asia-northeast1 \
    --format json > "backups/scheduler_$(date +%Y%m%d)/${job}.json"
done

# ========================================
# トラブルシューティング
# ========================================

# Cloud Runの状態確認
gcloud run services describe carewell-file-collector \
  --region=asia-northeast1

# Cloud Runのリビジョン一覧
gcloud run revisions list \
  --service=carewell-file-collector \
  --region=asia-northeast1

# Service Accountの権限確認
gcloud projects get-iam-policy carewell-automation \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:carewell-automation-sa@*"
```

---

### C. エスカレーションフロー

```
インシデント発生
    ↓
┌─────────────────────────────────┐
│ 初動対応（運用担当者）             │
│ - ログ確認                        │
│ - 影響範囲の特定                  │
│ - 緊急度の判定                    │
└─────────────────────────────────┘
    ↓
    ├─【P0】全ジョブ連続失敗、システム停止
    │    ↓
    │  即座にSlack通知 → オンコール担当者
    │    ↓
    │  緊急対応（全ジョブ一時停止、ロールバック等）
    │    ↓
    │  解決 → ポストモーテム作成
    │
    ├─【P1】部分的障害、API Quota超過、OOM
    │    ↓
    │  Slack通知 → 開発チーム
    │    ↓
    │  2時間以内に対応開始
    │    ↓
    │  解決 → 原因分析レポート作成
    │
    └─【P2/P3】軽微なエラー、単一ジョブ失敗
         ↓
       Issue作成 → 計画的に対応
         ↓
       次回メンテナンス時に修正
```

---

### D. メンテナンスカレンダー

| 頻度 | 実施内容 | 担当者 | 所要時間 | 次回予定 |
|------|---------|--------|---------|---------|
| 週次 | ジョブ実行状況確認、エラーログレビュー | 運用担当者 | 15分 | 毎週月曜 10:00 |
| 月次 | コスト確認、パフォーマンスレビュー | 運用担当者 | 30分 | 毎月1日 |
| 四半期 | 稼働時間最適化の検討、ドキュメント更新 | 開発チーム | 2時間 | 四半期末 |

---

## 変更履歴

| 日付 | バージョン | 変更内容 | 担当者 |
|------|-----------|---------|--------|
| 2025-10-13 | 1.0 | 初版作成 - Cloud Scheduler運用手順書 | AI Assistant (Claude) |

---

## フィードバック

本運用手順書に関する質問、提案、改善案は、以下で受け付けています：

- **GitHubリポジトリ**: `carewell-gcp-drive-automation`
- **Issue**: https://github.com/YOUR_ORG/carewell-gcp-drive-automation/issues
- **Slack**: `#carewell-automation`

**ドキュメントパス:** `docs/cloud-scheduler-operations-guide.md`
