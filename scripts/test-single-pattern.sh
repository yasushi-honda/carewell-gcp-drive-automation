#!/bin/bash
#
# 単一パターンクイックテストスクリプト
# 最初のパターン（№01-課題①）のみをテスト
#

set -e

# 色付きログ
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Cloud Run URL
CLOUD_RUN_URL="https://carewell-file-collector-imczapxkba-an.a.run.app"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  単一パターンクイックテスト (№01-課題①)${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# 認証トークン取得
echo -e "${YELLOW}認証トークン取得中...${NC}"
ID_TOKEN=$(gcloud auth print-identity-token)
if [ -z "$ID_TOKEN" ]; then
    echo -e "${RED}✗ 認証トークン取得失敗${NC}"
    exit 1
fi
echo -e "${GREEN}✓ 認証トークン取得成功${NC}"
echo ""

# リクエストボディ
REQUEST_BODY='{
  "class_name": "令和7年度 デジタル中核人材養成研修 №01",
  "task_id": "課題①",
  "task_pattern": "課題①",
  "drive_folder_id": "1gxt-OVloMfJWi73Yjm4v5bjupKL25Pag",
  "spreadsheet_id": "1R1bsr24uyFf67p7_0I0yUA47ap5uIrJE7n89A9NbRYI"
}'

echo "リクエスト:"
echo "${REQUEST_BODY}" | jq .
echo ""

# HTTPリクエスト送信
echo -e "${YELLOW}テスト実行中...${NC}"
start_time=$(date +%s)

RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST "${CLOUD_RUN_URL}" \
    -H "Authorization: Bearer ${ID_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "${REQUEST_BODY}")

end_time=$(date +%s)
duration=$((end_time - start_time))

# レスポンス分離
HTTP_CODE=$(echo "${RESPONSE}" | tail -n1)
RESPONSE_BODY=$(echo "${RESPONSE}" | sed '$d')

echo ""
echo -e "${BLUE}結果:${NC}"
echo "HTTPステータス: ${HTTP_CODE}"
echo "実行時間: ${duration}秒"
echo ""
echo "レスポンス:"
echo "${RESPONSE_BODY}" | jq . || echo "${RESPONSE_BODY}"
echo ""

# 判定
if [ "${HTTP_CODE}" == "200" ]; then
    STATUS=$(echo "${RESPONSE_BODY}" | jq -r '.status // "unknown"')
    if [ "${STATUS}" == "success" ]; then
        echo -e "${GREEN}✓ テスト成功${NC}"

        # 詳細情報
        SUBMISSIONS=$(echo "${RESPONSE_BODY}" | jq -r '.submissions_found // 0')
        PROCESSED=$(echo "${RESPONSE_BODY}" | jq -r '.processed // 0')
        SKIPPED=$(echo "${RESPONSE_BODY}" | jq -r '.skipped // 0')
        FAILED=$(echo "${RESPONSE_BODY}" | jq -r '.failed // 0')

        echo ""
        echo "提出一覧: ${SUBMISSIONS}件"
        echo "処理成功: ${PROCESSED}件"
        echo "スキップ: ${SKIPPED}件"
        echo "失敗: ${FAILED}件"
        exit 0
    else
        echo -e "${RED}✗ レスポンスステータスがエラー${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ HTTP ${HTTP_CODE} エラー${NC}"
    exit 1
fi
