#!/bin/bash

# Carewell File Collector - Test Request Script
# このスクリプトはデプロイ済みCloud Functionsのテストリクエストを送信します

set -e

# カラー出力用
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 設定
FUNCTION_URL="https://carewell-file-collector-imczapxkba-an.a.run.app"

echo -e "${YELLOW}=== Carewell File Collector Test ===${NC}"
echo ""

# 環境変数のチェック
if [ -z "$DRIVE_FOLDER_ID" ]; then
    echo -e "${RED}Error: DRIVE_FOLDER_ID environment variable is not set${NC}"
    echo "Please set it with: export DRIVE_FOLDER_ID='your_folder_id'"
    exit 1
fi

if [ -z "$SPREADSHEET_ID" ]; then
    echo -e "${RED}Error: SPREADSHEET_ID environment variable is not set${NC}"
    echo "Please set it with: export SPREADSHEET_ID='your_spreadsheet_id'"
    exit 1
fi

# デフォルト値（必要に応じて変更）
CLASS_NAME="${CLASS_NAME:-令和7年度 デジタル中核人材養成研修 №01}"
TASK_NAME="${TASK_NAME:-課題①業務分析　※～11/3〆切}"

# リクエストペイロード
REQUEST_PAYLOAD=$(cat <<EOF
{
  "class_name": "${CLASS_NAME}",
  "task_name": "${TASK_NAME}",
  "drive_folder_id": "${DRIVE_FOLDER_ID}",
  "spreadsheet_id": "${SPREADSHEET_ID}"
}
EOF
)

echo -e "${YELLOW}Request Configuration:${NC}"
echo "Function URL: ${FUNCTION_URL}"
echo "Class Name: ${CLASS_NAME}"
echo "Task Name: ${TASK_NAME}"
echo "Drive Folder ID: ${DRIVE_FOLDER_ID}"
echo "Spreadsheet ID: ${SPREADSHEET_ID}"
echo ""

echo -e "${YELLOW}Sending request...${NC}"
echo ""

# リクエスト送信
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${FUNCTION_URL}" \
  -H "Content-Type: application/json" \
  -d "${REQUEST_PAYLOAD}")

# HTTPステータスコードとボディを分離
HTTP_CODE=$(echo "${RESPONSE}" | tail -n 1)
HTTP_BODY=$(echo "${RESPONSE}" | sed '$d')

# レスポンスの表示
echo -e "${YELLOW}Response (HTTP ${HTTP_CODE}):${NC}"
echo "${HTTP_BODY}" | jq '.' 2>/dev/null || echo "${HTTP_BODY}"
echo ""

# 結果の判定
if [ "${HTTP_CODE}" -eq 200 ]; then
    echo -e "${GREEN}✓ Test PASSED${NC}"

    # 処理結果のサマリー表示
    if command -v jq &> /dev/null; then
        SUBMISSIONS_FOUND=$(echo "${HTTP_BODY}" | jq -r '.submissions_found // "N/A"')
        PROCESSED=$(echo "${HTTP_BODY}" | jq -r '.processed // "N/A"')
        SKIPPED=$(echo "${HTTP_BODY}" | jq -r '.skipped // "N/A"')
        FAILED=$(echo "${HTTP_BODY}" | jq -r '.failed // "N/A"')

        echo ""
        echo -e "${YELLOW}Summary:${NC}"
        echo "  Submissions Found: ${SUBMISSIONS_FOUND}"
        echo "  Processed: ${PROCESSED}"
        echo "  Skipped: ${SKIPPED}"
        echo "  Failed: ${FAILED}"
    fi

    exit 0
else
    echo -e "${RED}✗ Test FAILED${NC}"
    exit 1
fi
