#!/bin/bash
#
# Phase 11 全パターンテストスクリプト
# 7クラス × 2課題 = 14パターンをCloud Run本番環境でテスト
#

set -e

# 色付きログ
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Cloud Run URL
CLOUD_RUN_URL="https://carewell-file-collector-imczapxkba-an.a.run.app"

# ログディレクトリ
LOG_DIR="./test-results"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RESULT_FILE="${LOG_DIR}/test_results_${TIMESTAMP}.txt"

# ディレクトリ作成
mkdir -p "${LOG_DIR}"

# テスト設定データ
#
# ⚠️⚠️ 2026-08-26時点でCLASSESを空にし、このスクリプトは無効化しています ⚠️⚠️
# 下記のDRIVE_FOLDERS/SPREADSHEETSは全て「令和7年度」に用意されたものです。
# このスクリプトは実際にCloud Runへリクエストを送り、見つかった新規提出物を実際にダウンロード・
# 記録する（dry-runではない）ため、令和8年度のclass_nameのまま古い令和7年度の保存先IDを使うと
# 令和8年度の提出物が令和7年度のフォルダ・シートに誤って書き込まれるおそれがある。
# 令和8年度用の保存先を確認・確定してから、CLASSESに対象クラス番号を追加すること。
# №10がそもそも元々このリストに含まれていない不備も未修正のまま（要確認）。
declare -A DRIVE_FOLDERS=(
    ["01"]="1gxt-OVloMfJWi73Yjm4v5bjupKL25Pag"  # 令和7年度用（令和8年度での流用可否は未検証）
    ["02"]="1yJ60hEUHCHGOZNdMbACteoM5C2-pPVmC"  # 令和7年度用（令和8年度での流用可否は未検証）
    ["03"]="1IR81q87NIN9PkUAUDZpW9c2XZdkWTM7p"  # 令和7年度用（令和8年度での流用可否は未検証）
    ["04"]="1OuJk_u1Ig9CfIVXu3n5wQu0Ft6lfr3jQ"  # 令和7年度用（令和8年度での流用可否は未検証）
    ["05"]="1rNnmEJ92smjkcKFOd1L_u1n8SO1LDAC4"  # 令和7年度用（令和8年度での流用可否は未検証）
    ["08"]="1kdKwI7nQ8N6j8gD6agZap5FWL-uDTbwg"  # 令和7年度用（令和8年度での流用可否は未検証）
    ["09"]="1nllFEyyDEV7jiTSEgyBnnNeXhC_4Ttu6"  # 令和7年度用（令和8年度での流用可否は未検証）
)

declare -A SPREADSHEETS=(
    ["01"]="1R1bsr24uyFf67p7_0I0yUA47ap5uIrJE7n89A9NbRYI"  # 令和7年度用（令和8年度での流用可否は未検証）
    ["02"]="1qmczJQo2f3rSsZxhRWF3XfjCVc5Y3yW7K4wrk7bAcnc"  # 令和7年度用（令和8年度での流用可否は未検証）
    ["03"]="1kzDATIoQ1hOM9KYuYloCPsbmGn-tSDHSwYxK9pYQkwA"  # 令和7年度用（令和8年度での流用可否は未検証）
    ["04"]="12Xg8Edrtloct-jk_IBVApnqLVz6fPeQFTxxQDPXxi_Q"  # 令和7年度用（令和8年度での流用可否は未検証）
    ["05"]="1CPVDaX4E3AX3xl5I_sm-DjRVr7SfYKz4DjoBSS-h74o"  # 令和7年度用（令和8年度での流用可否は未検証）
    ["08"]="1Zm2ePE2gbKm8Yw_4B6vuO8HP3kfN2wZpFCQaNFHfcsk"  # 令和7年度用（令和8年度での流用可否は未検証）
    ["09"]="1O8S3w3F8RvLJp0LrS-eZtX0sZW5HcjOgMhyWJ_e8YPA"  # 令和7年度用（令和8年度での流用可否は未検証）
)

# 令和8年度用の保存先が確認・確定するまで空のまま（このスクリプトは実際に書込みを行うため）
CLASSES=()
TASKS=("課題①" "課題②")

# 統計カウンタ
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# ヘッダー出力
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  Phase 11 全パターンテスト実行${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo "テスト開始時刻: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Cloud Run URL: ${CLOUD_RUN_URL}"
echo "結果ファイル: ${RESULT_FILE}"
echo ""

# 結果ファイルにヘッダー書き込み
cat > "${RESULT_FILE}" <<EOF
Phase 11 全パターンテスト結果
================================
テスト開始時刻: $(date '+%Y-%m-%d %H:%M:%S')
Cloud Run URL: ${CLOUD_RUN_URL}

EOF

# 認証トークン取得
echo -e "${YELLOW}認証トークン取得中...${NC}"
ID_TOKEN=$(gcloud auth print-identity-token)
if [ -z "$ID_TOKEN" ]; then
    echo -e "${RED}✗ 認証トークン取得失敗${NC}"
    exit 1
fi
echo -e "${GREEN}✓ 認証トークン取得成功${NC}"
echo ""

# テスト実行関数
run_test() {
    local class_num=$1
    local task_id=$2
    local task_pattern=$3
    local drive_folder_id=$4
    local spreadsheet_id=$5

    local test_name="№${class_num}-${task_id}"
    local class_name="令和8年度 デジタル中核人材養成研修 №${class_num}"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    echo -e "${BLUE}----------------------------------------${NC}"
    echo -e "${BLUE}テスト ${TOTAL_TESTS}/14: ${test_name}${NC}"
    echo -e "${BLUE}----------------------------------------${NC}"

    # リクエストボディ作成
    local request_body=$(cat <<EOF
{
  "class_name": "${class_name}",
  "task_id": "${task_id}",
  "task_pattern": "${task_pattern}",
  "drive_folder_id": "${drive_folder_id}",
  "spreadsheet_id": "${spreadsheet_id}"
}
EOF
)

    echo "リクエスト:"
    echo "${request_body}" | jq .
    echo ""

    # 実行時刻記録
    local start_time=$(date '+%Y-%m-%d %H:%M:%S')
    local start_epoch=$(date +%s)

    # HTTPリクエスト送信
    echo "実行中..."
    local response_file="${LOG_DIR}/response_${class_num}_${task_id}_${TIMESTAMP}.json"
    local http_code=$(curl -s -w "%{http_code}" -o "${response_file}" \
        -X POST "${CLOUD_RUN_URL}" \
        -H "Authorization: Bearer ${ID_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "${request_body}")

    local end_epoch=$(date +%s)
    local duration=$((end_epoch - start_epoch))

    # 結果判定
    local status="FAILED"
    local response_body=$(cat "${response_file}")

    if [ "${http_code}" == "200" ]; then
        echo -e "${GREEN}✓ HTTP 200 OK${NC}"
        echo "レスポンス:"
        echo "${response_body}" | jq .

        # レスポンスボディのstatus確認
        local response_status=$(echo "${response_body}" | jq -r '.status // "error"')
        if [ "${response_status}" == "success" ]; then
            status="PASSED"
            PASSED_TESTS=$((PASSED_TESTS + 1))
            echo -e "${GREEN}✓ テスト成功${NC}"
        else
            FAILED_TESTS=$((FAILED_TESTS + 1))
            echo -e "${RED}✗ レスポンスステータスがエラー${NC}"
        fi
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
        echo -e "${RED}✗ HTTP ${http_code}${NC}"
        echo "レスポンス:"
        echo "${response_body}" | jq . || echo "${response_body}"
    fi

    echo "実行時間: ${duration}秒"
    echo ""

    # 結果をファイルに記録
    cat >> "${RESULT_FILE}" <<EOF
----------------------------------------
テスト: ${test_name}
クラス: ${class_name}
課題ID: ${task_id}
課題パターン: ${task_pattern}
実行時刻: ${start_time}
実行時間: ${duration}秒
HTTPステータス: ${http_code}
結果: ${status}
レスポンス: ${response_body}

EOF

    # 次のテストまで待機（ブラウザ操作の完了を待つ）
    if [ "${TOTAL_TESTS}" -lt 14 ]; then
        echo -e "${YELLOW}次のテストまで30秒待機...${NC}"
        sleep 30
        echo ""
    fi
}

# メインループ: 全14パターン実行
for class_num in "${CLASSES[@]}"; do
    drive_folder_id="${DRIVE_FOLDERS[$class_num]}"
    spreadsheet_id="${SPREADSHEETS[$class_num]}"

    for task_id in "${TASKS[@]}"; do
        task_pattern="${task_id}"
        run_test "${class_num}" "${task_id}" "${task_pattern}" "${drive_folder_id}" "${spreadsheet_id}"
    done
done

# サマリー出力
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  テスト結果サマリー${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo "総テスト数: ${TOTAL_TESTS}"
echo -e "${GREEN}成功: ${PASSED_TESTS}${NC}"
echo -e "${RED}失敗: ${FAILED_TESTS}${NC}"
echo ""
echo "テスト終了時刻: $(date '+%Y-%m-%d %H:%M:%S')"
echo "結果ファイル: ${RESULT_FILE}"
echo ""

# サマリーを結果ファイルに追記
cat >> "${RESULT_FILE}" <<EOF
========================================
テスト結果サマリー
========================================
総テスト数: ${TOTAL_TESTS}
成功: ${PASSED_TESTS}
失敗: ${FAILED_TESTS}
テスト終了時刻: $(date '+%Y-%m-%d %H:%M:%S')
EOF

# 終了コード
if [ "${FAILED_TESTS}" -eq 0 ]; then
    echo -e "${GREEN}✓ 全テスト成功！${NC}"
    exit 0
else
    echo -e "${RED}✗ ${FAILED_TESTS}件のテストが失敗しました${NC}"
    exit 1
fi
