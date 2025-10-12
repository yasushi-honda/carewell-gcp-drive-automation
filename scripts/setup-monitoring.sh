#!/bin/bash
#
# Cloud Monitoring監視・アラート設定スクリプト
# タスク10.4.4対応
#
# 実行前の確認:
# - gcloud CLIがインストールされている
# - 適切な権限を持つアカウントでログインしている
# - Monitoring API が有効化されている
#

set -e

# 色付きログ
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 設定
PROJECT_ID="carewell-automation"
SERVICE_NAME="carewell-file-collector"
NOTIFICATION_EMAIL="hy.unimail.11@gmail.com"

# ドライランモード（デフォルト: true）
DRY_RUN=${DRY_RUN:-true}

# ヘッダー
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  Cloud Monitoring 設定スクリプト${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo "プロジェクト: ${PROJECT_ID}"
echo "サービス: ${SERVICE_NAME}"
echo "通知先: ${NOTIFICATION_EMAIL}"
echo "モード: $([ "$DRY_RUN" = true ] && echo "${YELLOW}ドライラン${NC}" || echo "${GREEN}実行${NC}")"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}⚠️  ドライランモード: 実際には設定を作成しません${NC}"
    echo -e "${YELLOW}   実行するには: DRY_RUN=false $0${NC}"
    echo ""
fi

# ステップカウンタ
STEP=1

# ========================================
# 1. 通知チャネルの作成
# ========================================

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ステップ${STEP}: 通知チャネルの作成${NC}"
echo -e "${BLUE}========================================${NC}"
STEP=$((STEP + 1))
echo ""

NOTIFICATION_CHANNEL_NAME="carewell-email-notification"

echo "通知チャネル名: ${NOTIFICATION_CHANNEL_NAME}"
echo "通知先メールアドレス: ${NOTIFICATION_EMAIL}"
echo ""

# 既存の通知チャネルを確認
EXISTING_CHANNEL=$(gcloud alpha monitoring channels list \
  --project="${PROJECT_ID}" \
  --filter="displayName='${NOTIFICATION_CHANNEL_NAME}'" \
  --format="value(name)" 2>/dev/null | head -1)

if [ -n "$EXISTING_CHANNEL" ]; then
    echo -e "${YELLOW}⚠️  通知チャネルは既に存在します: ${EXISTING_CHANNEL}${NC}"
    NOTIFICATION_CHANNEL_ID="${EXISTING_CHANNEL}"
else
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[ドライラン] 通知チャネル作成コマンド:${NC}"
        echo "gcloud alpha monitoring channels create \\"
        echo "  --display-name=\"${NOTIFICATION_CHANNEL_NAME}\" \\"
        echo "  --type=email \\"
        echo "  --channel-labels=email_address=\"${NOTIFICATION_EMAIL}\" \\"
        echo "  --project=\"${PROJECT_ID}\""
        echo ""
        NOTIFICATION_CHANNEL_ID="projects/${PROJECT_ID}/notificationChannels/PLACEHOLDER"
    else
        echo -e "${GREEN}通知チャネルを作成中...${NC}"
        NOTIFICATION_CHANNEL_ID=$(gcloud alpha monitoring channels create \
          --display-name="${NOTIFICATION_CHANNEL_NAME}" \
          --type=email \
          --channel-labels=email_address="${NOTIFICATION_EMAIL}" \
          --project="${PROJECT_ID}" \
          --format="value(name)")

        echo -e "${GREEN}✓ 通知チャネル作成成功: ${NOTIFICATION_CHANNEL_ID}${NC}"
    fi
fi

echo ""

# ========================================
# 2. ログベースメトリクスの作成
# ========================================

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ステップ${STEP}: ログベースメトリクスの作成${NC}"
echo -e "${BLUE}========================================${NC}"
STEP=$((STEP + 1))
echo ""

# メトリクス1: HTTP成功回数
METRIC_NAME_1="carewell_http_success_count"
echo "[1/3] ${METRIC_NAME_1}"
echo "説明: HTTPステータス200（成功）のリクエスト数"
echo ""

if gcloud logging metrics describe "${METRIC_NAME_1}" --project="${PROJECT_ID}" &>/dev/null; then
    echo -e "${YELLOW}⚠️  メトリクスは既に存在します${NC}"
else
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[ドライラン] メトリクス作成コマンド:${NC}"
        echo "gcloud logging metrics create \"${METRIC_NAME_1}\" \\"
        echo "  --description=\"HTTP 200 success count for ${SERVICE_NAME}\" \\"
        echo "  --log-filter='resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${SERVICE_NAME}\" AND httpRequest.status=200' \\"
        echo "  --project=\"${PROJECT_ID}\""
    else
        gcloud logging metrics create "${METRIC_NAME_1}" \
          --description="HTTP 200 success count for ${SERVICE_NAME}" \
          --log-filter="resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${SERVICE_NAME}\" AND httpRequest.status=200" \
          --project="${PROJECT_ID}"
        echo -e "${GREEN}✓ メトリクス作成成功${NC}"
    fi
fi
echo ""

# メトリクス2: HTTPエラー回数
METRIC_NAME_2="carewell_http_error_count"
echo "[2/3] ${METRIC_NAME_2}"
echo "説明: HTTPステータス500（エラー）のリクエスト数"
echo ""

if gcloud logging metrics describe "${METRIC_NAME_2}" --project="${PROJECT_ID}" &>/dev/null; then
    echo -e "${YELLOW}⚠️  メトリクスは既に存在します${NC}"
else
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[ドライラン] メトリクス作成コマンド:${NC}"
        echo "gcloud logging metrics create \"${METRIC_NAME_2}\" \\"
        echo "  --description=\"HTTP 500 error count for ${SERVICE_NAME}\" \\"
        echo "  --log-filter='resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${SERVICE_NAME}\" AND httpRequest.status>=500' \\"
        echo "  --project=\"${PROJECT_ID}\""
    else
        gcloud logging metrics create "${METRIC_NAME_2}" \
          --description="HTTP 500 error count for ${SERVICE_NAME}" \
          --log-filter="resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${SERVICE_NAME}\" AND httpRequest.status>=500" \
          --project="${PROJECT_ID}"
        echo -e "${GREEN}✓ メトリクス作成成功${NC}"
    fi
fi
echo ""

# メトリクス3: 実行時間（秒単位で抽出）
METRIC_NAME_3="carewell_execution_time_seconds"
echo "[3/3] ${METRIC_NAME_3}"
echo "説明: Cloud Run実行時間（秒単位）"
echo ""

if gcloud logging metrics describe "${METRIC_NAME_3}" --project="${PROJECT_ID}" &>/dev/null; then
    echo -e "${YELLOW}⚠️  メトリクスは既に存在します${NC}"
else
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[ドライラン] メトリクス作成コマンド:${NC}"
        echo "gcloud logging metrics create \"${METRIC_NAME_3}\" \\"
        echo "  --description=\"Execution time in seconds for ${SERVICE_NAME}\" \\"
        echo "  --log-filter='resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${SERVICE_NAME}\" AND httpRequest.latency:*' \\"
        echo "  --value-extractor='EXTRACT(httpRequest.latency)' \\"
        echo "  --metric-kind=DELTA \\"
        echo "  --value-type=DISTRIBUTION \\"
        echo "  --project=\"${PROJECT_ID}\""
        echo ""
        echo -e "${YELLOW}注意: 実行時間メトリクスはCloud RunのhttpRequest.latencyを使用します${NC}"
    else
        # Note: Cloud LoggingのメトリクスはhttpRequest.latencyを直接抽出できないため、
        # 代わりにCloud Runの組み込みメトリクスを使用することを推奨
        echo -e "${YELLOW}注意: httpRequest.latencyの抽出は複雑なため、スキップします${NC}"
        echo -e "${YELLOW}   代わりにCloud Runの組み込みメトリクス 'run.googleapis.com/request_latencies' を使用してください${NC}"
    fi
fi
echo ""

# ========================================
# 3. アラートポリシーの作成
# ========================================

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ステップ${STEP}: アラートポリシーの作成${NC}"
echo -e "${BLUE}========================================${NC}"
STEP=$((STEP + 1))
echo ""

# アラート1: エラー率20%超過
ALERT_NAME_1="carewell-high-error-rate"
echo "[1/3] ${ALERT_NAME_1}"
echo "条件: エラー率が20%を超過した場合"
echo ""

if gcloud alpha monitoring policies list --project="${PROJECT_ID}" --filter="displayName='${ALERT_NAME_1}'" --format="value(name)" | grep -q .; then
    echo -e "${YELLOW}⚠️  アラートポリシーは既に存在します${NC}"
else
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[ドライラン] アラートポリシー作成${NC}"
        echo "詳細: エラー率 = (エラー数 / (成功数 + エラー数)) > 0.20"
        echo ""
        echo "注意: gcloud alpha monitoring policies createコマンドはYAMLファイルが必要です"
        echo "   代わりにGCPコンソールでの作成を推奨します:"
        echo "   https://console.cloud.google.com/monitoring/alerting/policies/create?project=${PROJECT_ID}"
    else
        echo -e "${YELLOW}注意: gcloud CLIではアラートポリシーの作成が複雑なため、GCPコンソールでの作成を推奨します${NC}"
        echo "URL: https://console.cloud.google.com/monitoring/alerting/policies/create?project=${PROJECT_ID}"
    fi
fi
echo ""

# アラート2: 連続3回失敗
ALERT_NAME_2="carewell-consecutive-failures"
echo "[2/3] ${ALERT_NAME_2}"
echo "条件: 連続3回失敗（HTTP 500）した場合"
echo ""

if gcloud alpha monitoring policies list --project="${PROJECT_ID}" --filter="displayName='${ALERT_NAME_2}'" --format="value(name)" | grep -q .; then
    echo -e "${YELLOW}⚠️  アラートポリシーは既に存在します${NC}"
else
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[ドライラン] アラートポリシー作成${NC}"
        echo "詳細: 過去15分間でエラー数 >= 3"
    else
        echo -e "${YELLOW}注意: GCPコンソールでの作成を推奨します${NC}"
        echo "URL: https://console.cloud.google.com/monitoring/alerting/policies/create?project=${PROJECT_ID}"
    fi
fi
echo ""

# アラート3: 実行時間8分超過
ALERT_NAME_3="carewell-long-execution-time"
echo "[3/3] ${ALERT_NAME_3}"
echo "条件: 実行時間が8分（480秒）を超過した場合"
echo ""

if gcloud alpha monitoring policies list --project="${PROJECT_ID}" --filter="displayName='${ALERT_NAME_3}'" --format="value(name)" | grep -q .; then
    echo -e "${YELLOW}⚠️  アラートポリシーは既に存在します${NC}"
else
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[ドライラン] アラートポリシー作成${NC}"
        echo "詳細: httpRequest.latency > 480s"
        echo ""
        echo "注意: Cloud Runの組み込みメトリクス 'run.googleapis.com/request_latencies' を使用"
        echo "   95パーセンタイルが480秒を超えた場合にアラート"
    else
        echo -e "${YELLOW}注意: GCPコンソールでの作成を推奨します${NC}"
        echo "URL: https://console.cloud.google.com/monitoring/alerting/policies/create?project=${PROJECT_ID}"
    fi
fi
echo ""

# ========================================
# サマリー
# ========================================

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  サマリー${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}モード: ドライラン${NC}"
    echo ""
    echo "作成予定の設定:"
    echo "  - 通知チャネル: ${NOTIFICATION_CHANNEL_NAME} (${NOTIFICATION_EMAIL})"
    echo "  - ログベースメトリクス:"
    echo "      1. ${METRIC_NAME_1} (成功カウント)"
    echo "      2. ${METRIC_NAME_2} (エラーカウント)"
    echo "      3. ${METRIC_NAME_3} (実行時間) ※スキップ推奨"
    echo "  - アラートポリシー:"
    echo "      1. ${ALERT_NAME_1} (エラー率20%超過)"
    echo "      2. ${ALERT_NAME_2} (連続3回失敗)"
    echo "      3. ${ALERT_NAME_3} (実行時間8分超過)"
    echo ""
    echo -e "${GREEN}実際に設定を作成するには:${NC}"
    echo "  DRY_RUN=false $0"
    echo ""
    echo -e "${YELLOW}推奨事項:${NC}"
    echo "  1. まずこのスクリプトで通知チャネルとログベースメトリクスを作成"
    echo "  2. アラートポリシーはGCPコンソールで作成（より柔軟な設定が可能）"
    echo "     https://console.cloud.google.com/monitoring/alerting?project=${PROJECT_ID}"
else
    echo -e "${GREEN}設定作成完了${NC}"
    echo ""
    echo "作成された設定:"
    echo "  - 通知チャネル: ${NOTIFICATION_CHANNEL_ID}"
    echo "  - ログベースメトリクス: ${METRIC_NAME_1}, ${METRIC_NAME_2}"
    echo ""
    echo -e "${YELLOW}次のステップ:${NC}"
    echo "  1. GCPコンソールでアラートポリシーを作成"
    echo "     https://console.cloud.google.com/monitoring/alerting?project=${PROJECT_ID}"
    echo ""
    echo "  2. ダッシュボードを作成"
    echo "     https://console.cloud.google.com/monitoring/dashboards?project=${PROJECT_ID}"
    echo ""
    echo "  3. 作成したメトリクスを確認"
    echo "     gcloud logging metrics list --project=${PROJECT_ID}"
fi

echo ""
