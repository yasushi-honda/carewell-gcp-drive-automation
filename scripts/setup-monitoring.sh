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
# 4. Cloud Runエラー検知アラートポリシーの作成
# ========================================
#
# 2026-09-25追加（Issue: decision-maker依頼「問題があったら緊急通知メールを」対応）。
# plan-crossreview（grip+codex 2パス）+ 実装後の本番ログ実地検証で以下を確認済み:
# - 通知チャネルはこのステップでは新規作成しない。既存のcarewell-email-notification
#   チャネルが「ちょうど1件」「type=email」「宛先一致」「enabled」「VERIFIED」の
#   全条件を満たす場合のみ再利用し、満たさない場合はfail-close(エラー終了)する
#   （上のステップ1は無ければ新規作成する設計のため、あえて独立したロジックにする）
# - フィルタはseverityフィールドを使わない。carewell-file-collectorはプレーン
#   テキストでログ出力しており(google-cloud-loggingは依存関係にあるだけで未配線)、
#   Cloud Runはプレーンテキストのstderr/stdoutに対してPythonのログレベルを
#   自動解析しないため、実際のlogger.error()呼び出しもseverity=DEFAULT(空欄)の
#   ままであることを本番ログで直接確認した(severity=ERRORでフィルタすると
#   ほぼ何も一致しない)。代わりにログ本文のテキストパターン
#   (" - ERROR - "、Pythonのlogging.Formatterが出力する%(levelname)s)で一致させる
# - 「Table wait failed」等を一度は既知の定型ログとして除外する案を検討したが、
#   src/playwright_automation.py の実装(2026-09-11修正、confirmed_zero_submissions)
#   を確認したところ、提出0件が確定した場合はこのtry節自体に入らずlogger.infoで
#   別途ログされる設計だった。つまりこのtry節のexcept(Table wait failed等)に
#   到達する時点で、確定0件ではない本物のタイムアウト失敗を意味する
#   (codex review指摘、コード確認で反証済み)。除外はせず全件を対象とする。
#   修正後(2026-09-11以降)の実績は過去14日で297件(1日あたり約21件)

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ステップ${STEP}: Cloud Runエラー検知アラートポリシーの作成${NC}"
echo -e "${BLUE}========================================${NC}"
STEP=$((STEP + 1))
echo ""

ERROR_ALERT_NAME="carewell-file-collector エラー検知"
ERROR_ALERT_POLICY_FILE="$(dirname "${BASH_SOURCE[0]}")/monitoring/cloud-run-error-alert-policy.json"
ERROR_ALERT_STATUS="skipped"  # サマリーで参照(既存/作成成功/チャネル未検証等)

echo "[4/4] ${ERROR_ALERT_NAME}"
echo "条件: carewell-file-collectorのstdout/stderrに\" - ERROR - \"を含むログが出力された場合"
echo ""

if gcloud monitoring policies list --project="${PROJECT_ID}" --filter="displayName='${ERROR_ALERT_NAME}'" --format="value(name)" | grep -q .; then
    echo -e "${YELLOW}⚠️  アラートポリシーは既に存在します${NC}"
    ERROR_ALERT_STATUS="already_exists"
else
    # 通知チャネルのfail-close検証（新規作成しない）
    CHANNEL_JSON=$(gcloud alpha monitoring channels list \
      --project="${PROJECT_ID}" \
      --filter="displayName='${NOTIFICATION_CHANNEL_NAME}'" \
      --format="json" 2>/dev/null)
    CHANNEL_COUNT=$(echo "${CHANNEL_JSON}" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)

    if [ "${CHANNEL_COUNT}" != "1" ]; then
        echo -e "${RED}✗ エラー: 通知チャネル「${NOTIFICATION_CHANNEL_NAME}」が${CHANNEL_COUNT}件見つかりました(1件である必要があります)${NC}"
        echo -e "${RED}   新規作成は行いません。手動で確認してください。${NC}"
        ERROR_ALERT_STATUS="channel_invalid"
        [ "$DRY_RUN" = true ] || exit 1
    else
        CHANNEL_TYPE=$(echo "${CHANNEL_JSON}" | python3 -c "import json,sys; print(json.load(sys.stdin)[0].get('type',''))")
        CHANNEL_EMAIL=$(echo "${CHANNEL_JSON}" | python3 -c "import json,sys; print(json.load(sys.stdin)[0].get('labels',{}).get('email_address',''))")
        CHANNEL_ENABLED=$(echo "${CHANNEL_JSON}" | python3 -c "import json,sys; print(json.load(sys.stdin)[0].get('enabled', False))")
        CHANNEL_VERIFIED=$(echo "${CHANNEL_JSON}" | python3 -c "import json,sys; print(json.load(sys.stdin)[0].get('verificationStatus',''))")
        CHANNEL_ID=$(echo "${CHANNEL_JSON}" | python3 -c "import json,sys; print(json.load(sys.stdin)[0].get('name',''))")

        if [ "${CHANNEL_TYPE}" != "email" ] || [ "${CHANNEL_EMAIL}" != "${NOTIFICATION_EMAIL}" ] || \
           [ "${CHANNEL_ENABLED}" != "True" ] || [ "${CHANNEL_VERIFIED}" != "VERIFIED" ]; then
            echo -e "${RED}✗ エラー: 通知チャネルの検証に失敗しました(type=${CHANNEL_TYPE}, email=${CHANNEL_EMAIL}, enabled=${CHANNEL_ENABLED}, verified=${CHANNEL_VERIFIED})${NC}"
            if [ "${CHANNEL_VERIFIED}" != "VERIFIED" ] && [ "${CHANNEL_TYPE}" = "email" ] && [ "${CHANNEL_EMAIL}" = "${NOTIFICATION_EMAIL}" ]; then
                echo -e "${RED}   新規作成は行いません。${NOTIFICATION_EMAIL}に届いている確認メールのリンクをクリックして${NC}"
                echo -e "${RED}   チャネルを検証してから、本スクリプトを再実行してください。${NC}"
                ERROR_ALERT_STATUS="channel_unverified"
            else
                echo -e "${RED}   新規作成は行いません。手動で確認してください。${NC}"
                ERROR_ALERT_STATUS="channel_invalid"
            fi
            [ "$DRY_RUN" = true ] || exit 1
        else
            echo -e "${GREEN}✓ 通知チャネル検証OK: ${CHANNEL_ID}${NC}"
            if [ "$DRY_RUN" = true ]; then
                echo -e "${YELLOW}[ドライラン] アラートポリシー作成コマンド:${NC}"
                echo "gcloud monitoring policies create \\"
                echo "  --policy-from-file=\"${ERROR_ALERT_POLICY_FILE}\" \\"
                echo "  --notification-channels=\"${CHANNEL_ID}\" \\"
                echo "  --project=\"${PROJECT_ID}\""
                ERROR_ALERT_STATUS="dry_run_preview"
            else
                echo -e "${GREEN}アラートポリシーを作成中...${NC}"
                gcloud monitoring policies create \
                  --policy-from-file="${ERROR_ALERT_POLICY_FILE}" \
                  --notification-channels="${CHANNEL_ID}" \
                  --project="${PROJECT_ID}"
                echo -e "${GREEN}✓ アラートポリシー作成成功${NC}"
                ERROR_ALERT_STATUS="created"
            fi
        fi
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
    echo "  2. carewell-file-collectorエラー検知アラート(ステップ4)は本スクリプトで自動作成される"
    echo "  3. 高エラー率・連続失敗・実行時間超過の3件はGCPコンソールで作成（より柔軟な設定が可能）"
    echo "     https://console.cloud.google.com/monitoring/alerting?project=${PROJECT_ID}"
else
    echo -e "${GREEN}設定作成完了${NC}"
    echo ""
    echo "作成された設定:"
    echo "  - 通知チャネル: ${NOTIFICATION_CHANNEL_ID}"
    echo "  - ログベースメトリクス: ${METRIC_NAME_1}, ${METRIC_NAME_2}"
    case "${ERROR_ALERT_STATUS}" in
        created)
            echo "  - carewell-file-collectorエラー検知アラート: 作成完了(GCPコンソールでの追加作成は不要)"
            ;;
        already_exists)
            echo "  - carewell-file-collectorエラー検知アラート: 既存のものを維持(GCPコンソールでの追加作成は不要)"
            ;;
        channel_unverified)
            echo "  - carewell-file-collectorエラー検知アラート: 未作成(通知チャネルのメール検証待ち。${NOTIFICATION_EMAIL}の確認メールのリンクをクリック後、本スクリプトを再実行してください)"
            ;;
        channel_invalid)
            echo "  - carewell-file-collectorエラー検知アラート: 未作成(通知チャネルの検証に失敗。上記のエラー内容を確認してください)"
            ;;
        *)
            echo "  - carewell-file-collectorエラー検知アラート: 未作成"
            ;;
    esac
    echo ""
    echo -e "${YELLOW}次のステップ:${NC}"
    echo "  1. 高エラー率・連続失敗・実行時間超過の3件（今回のスコープ外）はGCPコンソールで作成する場合のみ"
    echo "     https://console.cloud.google.com/monitoring/alerting?project=${PROJECT_ID}"
    echo ""
    echo "  2. ダッシュボードを作成"
    echo "     https://console.cloud.google.com/monitoring/dashboards?project=${PROJECT_ID}"
    echo ""
    echo "  3. 作成したメトリクスを確認"
    echo "     gcloud logging metrics list --project=${PROJECT_ID}"
fi

echo ""
