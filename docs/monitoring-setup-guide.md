# Cloud Monitoring セットアップガイド

## 目次

1. [概要](#概要)
2. [前提条件](#前提条件)
3. [ステップ1: ログベースメトリクス作成](#ステップ1-ログベースメトリクス作成)
4. [ステップ2: 通知チャネル設定](#ステップ2-通知チャネル設定)
5. [ステップ3: アラートポリシー作成](#ステップ3-アラートポリシー作成)
6. [ステップ4: ダッシュボード作成](#ステップ4-ダッシュボード作成)
7. [動作確認](#動作確認)
8. [トラブルシューティング](#トラブルシューティング)

---

## 概要

本ドキュメントは、Carewell自動ファイル収集システムのCloud Monitoring設定手順を説明します。

### 設定内容

- **ログベースメトリクス**: HTTPステータスと実行時間を抽出
- **通知チャネル**: メール通知（hy.unimail.11@gmail.com）
- **アラートポリシー**: エラー率20%超過、連続3回失敗、実行時間8分超過
- **ダッシュボード**: 実行成功率、処理ファイル数推移、平均実行時間、エラー発生状況

### 所要時間

- 自動設定スクリプト: 約5分
- 手動設定（GCPコンソール）: 約15分
- 合計: 約20分

---

## 前提条件

### 必要な権限

- `roles/logging.configWriter`（ログベースメトリクス作成）
- `roles/monitoring.metricWriter`（メトリクス書き込み）
- `roles/monitoring.alertPolicyEditor`（アラートポリシー作成）
- `roles/monitoring.dashboardEditor`（ダッシュボード作成）
- `roles/monitoring.notificationChannelEditor`（通知チャネル作成）

### 必要なツール

- gcloud CLI（バージョン400.0.0以上）
- インターネット接続

### APIの有効化

```bash
# Monitoring APIの有効化
gcloud services enable monitoring.googleapis.com --project=carewell-automation

# Logging APIの有効化（既に有効化済みのはず）
gcloud services enable logging.googleapis.com --project=carewell-automation

# 確認
gcloud services list --enabled --project=carewell-automation | grep -E "monitoring|logging"
```

---

## ステップ1: ログベースメトリクス作成

### オプション1: 自動設定スクリプト（推奨）

```bash
# ドライランで確認
bash scripts/setup-monitoring.sh

# 実行
DRY_RUN=false bash scripts/setup-monitoring.sh
```

スクリプトが以下を自動作成します：
- 通知チャネル: `carewell-email-notification`
- メトリクス1: `carewell_http_success_count`（成功数）
- メトリクス2: `carewell_http_error_count`（エラー数）

### オプション2: 手動作成

#### メトリクス1: HTTP成功数

```bash
gcloud logging metrics create carewell_http_success_count \
  --description="HTTP 200 success count for carewell-file-collector" \
  --log-filter='resource.type="cloud_run_revision" AND resource.labels.service_name="carewell-file-collector" AND httpRequest.status=200' \
  --project=carewell-automation
```

#### メトリクス2: HTTPエラー数

```bash
gcloud logging metrics create carewell_http_error_count \
  --description="HTTP 500 error count for carewell-file-collector" \
  --log-filter='resource.type="cloud_run_revision" AND resource.labels.service_name="carewell-file-collector" AND httpRequest.status>=500' \
  --project=carewell-automation
```

#### 作成確認

```bash
# メトリクス一覧確認
gcloud logging metrics list --project=carewell-automation

# 特定メトリクスの詳細確認
gcloud logging metrics describe carewell_http_success_count --project=carewell-automation
```

---

## ステップ2: 通知チャネル設定

### オプション1: 自動設定（スクリプトで作成済み）

`scripts/setup-monitoring.sh`を実行済みの場合、通知チャネルは既に作成されています。

### オプション2: GCPコンソールで作成

1. **GCPコンソール** → **Monitoring** → **アラート**
2. 左メニュー → **Notification channels**
3. **Add New** → **Email**
4. 設定:
   - Display name: `carewell-email-notification`
   - Email address: `hy.unimail.11@gmail.com`
5. **Save**

### オプション3: gcloud CLIで作成

```bash
gcloud alpha monitoring channels create \
  --display-name="carewell-email-notification" \
  --type=email \
  --channel-labels=email_address="hy.unimail.11@gmail.com" \
  --project=carewell-automation
```

### 作成確認

```bash
# 通知チャネル一覧
gcloud alpha monitoring channels list --project=carewell-automation

# 出力例:
# name: projects/carewell-automation/notificationChannels/1234567890
# displayName: carewell-email-notification
# type: email
```

### 通知チャネルIDの取得

後のステップで必要になるため、通知チャネルIDを保存します：

```bash
# 通知チャネルIDを取得
NOTIFICATION_CHANNEL_ID=$(gcloud alpha monitoring channels list \
  --project=carewell-automation \
  --filter='displayName="carewell-email-notification"' \
  --format='value(name)')

echo "通知チャネルID: ${NOTIFICATION_CHANNEL_ID}"

# 例: projects/carewell-automation/notificationChannels/1234567890
```

---

## ステップ3: アラートポリシー作成

**注意:** gcloud CLIでのアラートポリシー作成は複雑なため、GCPコンソールでの作成を推奨します。

### 3.1 アラート1: エラー率20%超過

#### GCPコンソールでの作成手順

1. **GCPコンソール** → **Monitoring** → **Alerting**
2. **Create Policy** をクリック
3. **Select a metric** をクリック

**ステップ1: メトリクス選択**

- Resource type: `Cloud Run Revision`
- Metric: `logging.googleapis.com/user/carewell_http_error_count`
- **Add** をクリック

**ステップ2: 条件設定**

- Transform data:
  - Rolling window: `5 minutes`
  - Rolling window function: `rate`
- Configure alert trigger:
  - Condition type: `Threshold`
  - Alert trigger: `Any time series violates`
  - Threshold position: `Above threshold`
  - Threshold value: `0.2`（エラー率20%）

  **計算式:** `エラー数 / (成功数 + エラー数) > 0.2`

- Advanced options:
  - Condition name: `High Error Rate (>20%)`

**ステップ3: 通知設定**

- Use notification channel: `carewell-email-notification`
- Name: `carewell-high-error-rate`
- Documentation (optional):
  ```
  エラー率が20%を超過しました。

  確認事項:
  - Cloud Runログでエラー内容を確認
  - Carewellサービスの稼働状況を確認
  - 最近のデプロイがないか確認

  運用手順書: docs/cloud-scheduler-operations-guide.md
  ```

**ステップ4: 作成完了**

- **Create Policy** をクリック

---

### 3.2 アラート2: 連続3回失敗

#### GCPコンソールでの作成手順

1. **Create Policy** をクリック
2. **Select a metric** をクリック

**ステップ1: メトリクス選択**

- Resource type: `Cloud Run Revision`
- Metric: `logging.googleapis.com/user/carewell_http_error_count`

**ステップ2: 条件設定**

- Transform data:
  - Rolling window: `15 minutes`
  - Rolling window function: `sum`
- Configure alert trigger:
  - Condition type: `Threshold`
  - Alert trigger: `Any time series violates`
  - Threshold position: `Above threshold`
  - Threshold value: `3`
- Advanced options:
  - Condition name: `Consecutive Failures (>=3 in 15min)`

**ステップ3: 通知設定**

- Use notification channel: `carewell-email-notification`
- Name: `carewell-consecutive-failures`
- Documentation:
  ```
  過去15分間で3回以上の失敗が発生しました。

  緊急対応手順:
  1. 全ジョブを一時停止
  2. エラーログを確認
  3. 原因特定と対応

  詳細: docs/cloud-scheduler-operations-guide.md#緊急時対応手順
  ```

---

### 3.3 アラート3: 実行時間8分超過

#### GCPコンソールでの作成手順

1. **Create Policy** をクリック
2. **Select a metric** をクリック

**ステップ1: メトリクス選択**

- Resource type: `Cloud Run Revision`
- Metric: `run.googleapis.com/request_latencies`
  - **注意:** ユーザー定義メトリクスではなく、Cloud Run組み込みメトリクスを使用

**ステップ2: 条件設定**

- Transform data:
  - Rolling window: `10 minutes`
  - Rolling window function: `95th percentile`
- Configure alert trigger:
  - Condition type: `Threshold`
  - Alert trigger: `Any time series violates`
  - Threshold position: `Above threshold`
  - Threshold value: `480000`（480秒 = 8分、ミリ秒単位）
- Advanced options:
  - Condition name: `Long Execution Time (>8min)`

**ステップ3: 通知設定**

- Use notification channel: `carewell-email-notification`
- Name: `carewell-long-execution-time`
- Documentation:
  ```
  実行時間が8分を超過しました。

  考えられる原因:
  - 大量のファイル処理
  - Carewell Webサービスの遅延
  - ネットワーク問題

  対応:
  1. 処理ファイル数を確認
  2. Carewellサービスの稼働状況を確認
  3. 必要に応じてタイムアウト設定を増加

  詳細: docs/cloud-scheduler-operations-guide.md#エラー3-http-504-gateway-timeout
  ```

---

### アラートポリシーの確認

```bash
# アラートポリシー一覧
gcloud alpha monitoring policies list --project=carewell-automation

# 特定ポリシーの詳細
gcloud alpha monitoring policies describe POLICY_NAME --project=carewell-automation
```

---

## ステップ4: ダッシュボード作成

### GCPコンソールでの作成手順

1. **GCPコンソール** → **Monitoring** → **Dashboards**
2. **Create Dashboard** をクリック
3. Dashboard name: `Carewell File Collector - Monitoring Dashboard`

### 4.1 チャート1: 実行成功率

**Add Chart** をクリック

- **Chart type:** Line
- **Title:** Execution Success Rate
- **Metric:**
  - Resource type: `Cloud Run Revision`
  - Metric: `logging.googleapis.com/user/carewell_http_success_count`
- **Transform:**
  - Aggregation: `rate`
  - Alignment period: `5 minutes`
- **Calculation:**
  - 成功率 = 成功数 / (成功数 + エラー数)
  - MQL (Monitoring Query Language) を使用:

  ```
  fetch cloud_run_revision
  | metric 'logging.googleapis.com/user/carewell_http_success_count'
  | group_by 5m, [value_success: rate(value.carewell_http_success_count)]
  | every 5m
  | {
      metric 'logging.googleapis.com/user/carewell_http_error_count'
      | group_by 5m, [value_error: rate(value.carewell_http_error_count)]
      | every 5m
    }
  | outer_join 0
  | div
  | mul 100
  ```

  **簡易版（MQL未使用）:** 成功数とエラー数を別々にプロット

---

### 4.2 チャート2: 処理ファイル数推移

**注意:** 現在のログでは処理ファイル数が記録されていないため、HTTP成功回数を代替として使用します。

**Add Chart** をクリック

- **Chart type:** Stacked Area Chart
- **Title:** Processed Files Trend (HTTP Success Count)
- **Metric:**
  - Resource type: `Cloud Run Revision`
  - Metric: `logging.googleapis.com/user/carewell_http_success_count`
- **Transform:**
  - Aggregation: `sum`
  - Alignment period: `1 hour`
- **Group by:** `resource.service_name`

---

### 4.3 チャート3: 平均実行時間

**Add Chart** をクリック

- **Chart type:** Line
- **Title:** Average Execution Time
- **Metric:**
  - Resource type: `Cloud Run Revision`
  - Metric: `run.googleapis.com/request_latencies`
- **Transform:**
  - Aggregation: `mean`
  - Alignment period: `10 minutes`
- **Filter:**
  - `resource.service_name = "carewell-file-collector"`
- **Y-axis:**
  - Unit: `seconds` (s)
  - Min: 0
  - Max: 600 (10分)

---

### 4.4 チャート4: エラー発生状況

**Add Chart** をクリック

- **Chart type:** Stacked Bar Chart
- **Title:** Error Occurrence
- **Metric:**
  - Resource type: `Cloud Run Revision`
  - Metric: `logging.googleapis.com/user/carewell_http_error_count`
- **Transform:**
  - Aggregation: `sum`
  - Alignment period: `1 hour`
- **Filter:**
  - `resource.service_name = "carewell-file-collector"`
- **Color scheme:** Red (エラーを強調)

---

### 4.5 チャート5: HTTP Status Code分布

**Add Chart** をクリック

- **Chart type:** Pie Chart
- **Title:** HTTP Status Code Distribution
- **Metric:**
  - Resource type: `Cloud Run Revision`
  - Metric: `run.googleapis.com/request_count`
- **Group by:** `response_code_class`
- **Filter:**
  - `resource.service_name = "carewell-file-collector"`
- **Time range:** Last 7 days

---

### ダッシュボードの保存と共有

1. **Save Dashboard** をクリック
2. **Share Dashboard**（オプション）:
   - URLをコピーして関係者に共有
   - 例: `https://console.cloud.google.com/monitoring/dashboards/custom/DASHBOARD_ID?project=carewell-automation`

---

## 動作確認

### 1. メトリクスの動作確認

```bash
# メトリクスが正しく収集されているか確認
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  httpRequest.status=200" \
  --limit 5 \
  --format json | jq '.[0] | {timestamp, httpRequest: {status, latency}}'
```

### 2. テストアラートの発火

**テスト1: 手動でエラーを発生させる**

```bash
# 存在しないクラス名で実行（エラーが発生する）
curl -X POST https://carewell-file-collector-imczapxkba-an.a.run.app \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -d '{
    "class_name": "NONEXISTENT_CLASS",
    "task_id": "課題①",
    "task_pattern": "課題①",
    "drive_folder_id": "1gxt-OVloMfJWi73Yjm4v5bjupKL25Pag",
    "spreadsheet_id": "1R1bsr24uyFf67p7_0I0yUA47ap5uIrJE7n89A9NbRYI"
  }'
```

**テスト2: アラート通知の確認**

- 3回連続でエラーが発生すると、`carewell-consecutive-failures`アラートが発火
- hy.unimail.11@gmail.comにメール通知が届くことを確認

### 3. ダッシュボードの動作確認

1. GCPコンソール → Monitoring → Dashboards → `Carewell File Collector - Monitoring Dashboard`
2. 各チャートにデータが表示されることを確認
3. Time rangeを変更して、過去のデータが表示されることを確認

---

## トラブルシューティング

### 問題1: メトリクスが作成されない

**症状:**

```
ERROR: (gcloud.logging.metrics.create) PERMISSION_DENIED: The caller does not have permission
```

**対応:**

```bash
# 権限を確認
gcloud projects get-iam-policy carewell-automation \
  --flatten="bindings[].members" \
  --filter="bindings.members:user:$(gcloud config get-value account)"

# 必要な権限を付与（プロジェクトオーナーが実行）
gcloud projects add-iam-policy-binding carewell-automation \
  --member="user:$(gcloud config get-value account)" \
  --role="roles/logging.configWriter"
```

---

### 問題2: アラートが発火しない

**考えられる原因:**

1. **メトリクスにデータがない**
   ```bash
   # メトリクスのデータを確認
   gcloud logging read "resource.type=cloud_run_revision AND \
     resource.labels.service_name=carewell-file-collector" \
     --limit 10 \
     --format json
   ```

2. **閾値が不適切**
   - GCPコンソールでアラートポリシーの条件を確認
   - テスト実行で意図的にエラーを発生させる

3. **通知チャネルが正しく設定されていない**
   ```bash
   # 通知チャネルを確認
   gcloud alpha monitoring channels list --project=carewell-automation
   ```

---

### 問題3: ダッシュボードにデータが表示されない

**対応:**

1. **Time rangeを拡大**
   - 過去7日間や30日間に変更して確認

2. **メトリクスが存在するか確認**
   ```bash
   gcloud logging metrics list --project=carewell-automation
   ```

3. **Cloud Run サービスの実行履歴を確認**
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND \
     resource.labels.service_name=carewell-file-collector" \
     --limit 100 \
     --format json
   ```

---

### 問題4: 通知メールが届かない

**対応:**

1. **メールアドレスの確認**
   ```bash
   gcloud alpha monitoring channels describe CHANNEL_ID \
     --project=carewell-automation
   ```

2. **迷惑メールフォルダを確認**
   - Gmailの場合、`from:noreply@google.com` で検索

3. **通知チャネルのテスト**
   - GCPコンソール → Monitoring → Notification channels
   - 該当チャネルをクリック → **Test** をクリック

---

## 付録A: MQL（Monitoring Query Language）の例

### エラー率の計算

```mql
fetch cloud_run_revision
| metric 'logging.googleapis.com/user/carewell_http_success_count'
| group_by 5m, [value_success: sum(value.carewell_http_success_count)]
| every 5m
| {
    metric 'logging.googleapis.com/user/carewell_http_error_count'
    | group_by 5m, [value_error: sum(value.carewell_http_error_count)]
    | every 5m
  }
| ratio
```

### 実行時間の95パーセンタイル

```mql
fetch cloud_run_revision
| metric 'run.googleapis.com/request_latencies'
| filter resource.service_name == 'carewell-file-collector'
| group_by 10m, [value_latency_percentile: percentile(value.request_latencies, 95)]
| every 10m
```

---

## 付録B: よく使うgcloudコマンド

```bash
# ========================================
# メトリクス管理
# ========================================

# メトリクス一覧
gcloud logging metrics list --project=carewell-automation

# メトリクス詳細
gcloud logging metrics describe METRIC_NAME --project=carewell-automation

# メトリクス削除
gcloud logging metrics delete METRIC_NAME --project=carewell-automation

# ========================================
# アラートポリシー管理
# ========================================

# アラートポリシー一覧
gcloud alpha monitoring policies list --project=carewell-automation

# アラートポリシー詳細
gcloud alpha monitoring policies describe POLICY_NAME --project=carewell-automation

# アラートポリシー削除
gcloud alpha monitoring policies delete POLICY_NAME --project=carewell-automation

# ========================================
# 通知チャネル管理
# ========================================

# 通知チャネル一覧
gcloud alpha monitoring channels list --project=carewell-automation

# 通知チャネル詳細
gcloud alpha monitoring channels describe CHANNEL_ID --project=carewell-automation

# 通知チャネル削除
gcloud alpha monitoring channels delete CHANNEL_ID --project=carewell-automation

# ========================================
# ダッシュボード管理
# ========================================

# ダッシュボード一覧
gcloud monitoring dashboards list --project=carewell-automation

# ダッシュボード詳細（JSON形式）
gcloud monitoring dashboards describe DASHBOARD_ID --project=carewell-automation \
  --format json > dashboard_backup.json

# ダッシュボード削除
gcloud monitoring dashboards delete DASHBOARD_ID --project=carewell-automation
```

---

## 付録C: Terraform（Infrastructure as Code）での管理

将来的にTerraformで管理する場合の参考例：

```hcl
# notification_channel.tf
resource "google_monitoring_notification_channel" "email" {
  display_name = "carewell-email-notification"
  type         = "email"
  project      = "carewell-automation"

  labels = {
    email_address = "hy.unimail.11@gmail.com"
  }
}

# log_metric.tf
resource "google_logging_metric" "http_success_count" {
  name    = "carewell_http_success_count"
  project = "carewell-automation"

  filter = <<-EOT
    resource.type="cloud_run_revision"
    AND resource.labels.service_name="carewell-file-collector"
    AND httpRequest.status=200
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

# alert_policy.tf
resource "google_monitoring_alert_policy" "high_error_rate" {
  display_name = "carewell-high-error-rate"
  project      = "carewell-automation"

  conditions {
    display_name = "High Error Rate (>20%)"

    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND metric.type=\"logging.googleapis.com/user/carewell_http_error_count\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.2
    }
  }

  notification_channels = [
    google_monitoring_notification_channel.email.id
  ]
}
```

---

## 変更履歴

| 日付 | バージョン | 変更内容 | 担当者 |
|------|-----------|---------|--------|
| 2025-10-13 | 1.0 | 初版作成 - Cloud Monitoring セットアップガイド | AI Assistant (Claude) |

---

## フィードバック

本セットアップガイドに関する質問、提案、改善案は、以下で受け付けています：

- **GitHubリポジトリ**: `carewell-gcp-drive-automation`
- **Issue**: https://github.com/YOUR_ORG/carewell-gcp-drive-automation/issues
- **Slack**: `#carewell-automation`

**ドキュメントパス:** `docs/monitoring-setup-guide.md`
