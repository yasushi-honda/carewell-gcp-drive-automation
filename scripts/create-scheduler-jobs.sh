#!/bin/bash
#
# Cloud Scheduler ジョブ作成スクリプト（Phase 11対応）
# 8クラス × 2課題 = 16ジョブを新命名規則で作成
#
# Bash 3.2互換バージョン（連想配列不使用）
#

set -e

# 色付きログ
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 設定
CLOUD_RUN_URL="https://carewell-file-collector-imczapxkba-an.a.run.app"
SERVICE_ACCOUNT="carewell-automation-sa@carewell-automation.iam.gserviceaccount.com"
LOCATION="asia-northeast1"
TIMEZONE="Asia/Tokyo"

# ドライランモード（デフォルト: true）
DRY_RUN=${DRY_RUN:-true}

# ヘッダー
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  Cloud Scheduler Jobs 作成スクリプト${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo "モード: $([ "$DRY_RUN" = true ] && echo "${YELLOW}ドライラン${NC}" || echo "${GREEN}実行${NC}")"
echo "Cloud Run URL: ${CLOUD_RUN_URL}"
echo "Service Account: ${SERVICE_ACCOUNT}"
echo "Location: ${LOCATION}"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}⚠️  ドライランモード: 実際にはジョブを作成しません${NC}"
    echo -e "${YELLOW}   実行するには: DRY_RUN=false $0${NC}"
    echo ""
fi

# ジョブ作成カウンタ
TOTAL_JOBS=0
CREATED_JOBS=0
SKIPPED_JOBS=0

# ジョブ作成関数
create_job() {
    local class_num=$1
    local task_num=$2
    local task_id=$3
    local task_pattern=$4
    local cron_schedule=$5
    local drive_folder_id=$6
    local spreadsheet_id=$7

    local job_name="carewell-class${class_num}-task${task_num}"
    local class_name="令和8年度 デジタル中核人材養成研修 №${class_num}"

    TOTAL_JOBS=$((TOTAL_JOBS + 1))

    echo -e "${BLUE}----------------------------------------${NC}"
    echo -e "${BLUE}[${TOTAL_JOBS}/16] ${job_name}${NC}"
    echo -e "${BLUE}----------------------------------------${NC}"
    echo "クラス: ${class_name}"
    echo "課題ID: ${task_id}"
    echo "課題パターン: ${task_pattern}"
    echo "Cronスケジュール: ${cron_schedule}"
    echo ""

    # ジョブ存在チェック
    if gcloud scheduler jobs describe "${job_name}" --location="${LOCATION}" &>/dev/null; then
        echo -e "${YELLOW}⚠️  ジョブは既に存在します。スキップします。${NC}"
        SKIPPED_JOBS=$((SKIPPED_JOBS + 1))
        echo ""
        return
    fi

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

    echo "リクエストボディ:"
    echo "${request_body}" | jq .
    echo ""

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[ドライラン] ジョブ作成コマンド:${NC}"
        echo "gcloud scheduler jobs create http \"${job_name}\" \\"
        echo "  --location=\"${LOCATION}\" \\"
        echo "  --schedule=\"${cron_schedule}\" \\"
        echo "  --time-zone=\"${TIMEZONE}\" \\"
        echo "  --uri=\"${CLOUD_RUN_URL}\" \\"
        echo "  --http-method=POST \\"
        echo "  --headers=\"Content-Type=application/json\" \\"
        echo "  --message-body='${request_body}' \\"
        echo "  --oidc-service-account-email=\"${SERVICE_ACCOUNT}\""
        echo ""
    else
        echo -e "${GREEN}ジョブを作成中...${NC}"

        if gcloud scheduler jobs create http "${job_name}" \
            --location="${LOCATION}" \
            --schedule="${cron_schedule}" \
            --time-zone="${TIMEZONE}" \
            --uri="${CLOUD_RUN_URL}" \
            --http-method=POST \
            --headers="Content-Type=application/json" \
            --message-body="${request_body}" \
            --oidc-service-account-email="${SERVICE_ACCOUNT}"; then

            echo -e "${GREEN}✓ ジョブ作成成功${NC}"
            CREATED_JOBS=$((CREATED_JOBS + 1))
        else
            echo -e "${RED}✗ ジョブ作成失敗${NC}"
        fi
    fi

    echo ""
}

# 令和8年度（2026年度）ジョブパラメータ定義
# 順番: class_num task_num task_id task_pattern cron_schedule drive_folder_id spreadsheet_id
#
# ⚠️⚠️ 2026-08-26時点で全エントリをコメントアウトしています ⚠️⚠️
# 下記のdrive_folder_id / spreadsheet_idは全て「令和7年度」に用意されたものです。
# 令和8年度でもそのまま流用してよいかは未検証（クロスレビューで発見、docs/SERVICE_SHUTDOWN_AND_RESUME.md
# 「令和8年度再開ステータス」参照）。№06・07は保存先ID自体が未作成。
# 対象クラスごとに令和8年度用の保存先を確認・確定してから、該当行のコメントを解除して使うこと。
#
# ⚠️ 重要: task_patternは現在暫定値（task_idと同じ）です
# TODO: Carewell実際の課題名に更新する必要があります
#   例: "課題①" → "課題①業務分析　※～11/3〆切"
#
# create_job "01" "01" "課題①" "課題①" "0,30 * * * *" "1gxt-OVloMfJWi73Yjm4v5bjupKL25Pag" "1R1bsr24uyFf67p7_0I0yUA47ap5uIrJE7n89A9NbRYI"
# create_job "01" "02" "課題②" "課題②" "5,35 * * * *" "1gxt-OVloMfJWi73Yjm4v5bjupKL25Pag" "1R1bsr24uyFf67p7_0I0yUA47ap5uIrJE7n89A9NbRYI"
#
# create_job "02" "01" "課題①" "課題①" "10,40 * * * *" "1yJ60hEUHCHGOZNdMbACteoM5C2-pPVmC" "1qmczJQo2f3rSsZxhRWF3XfjCVc5Y3yW7K4wrk7bAcnc"
# create_job "02" "02" "課題②" "課題②" "15,45 * * * *" "1yJ60hEUHCHGOZNdMbACteoM5C2-pPVmC" "1qmczJQo2f3rSsZxhRWF3XfjCVc5Y3yW7K4wrk7bAcnc"
#
# create_job "03" "01" "課題①" "課題①" "20,50 * * * *" "1IR81q87NIN9PkUAUDZpW9c2XZdkWTM7p" "1kzDATIoQ1hOM9KYuYloCPsbmGn-tSDHSwYxK9pYQkwA"
# create_job "03" "02" "課題②" "課題②" "25,55 * * * *" "1IR81q87NIN9PkUAUDZpW9c2XZdkWTM7p" "1kzDATIoQ1hOM9KYuYloCPsbmGn-tSDHSwYxK9pYQkwA"
#
# create_job "04" "01" "課題①" "課題①" "0,30 * * * *" "1OuJk_u1Ig9CfIVXu3n5wQu0Ft6lfr3jQ" "12Xg8Edrtloct-jk_IBVApnqLVz6fPeQFTxxQDPXxi_Q"
# create_job "04" "02" "課題②" "課題②" "5,35 * * * *" "1OuJk_u1Ig9CfIVXu3n5wQu0Ft6lfr3jQ" "12Xg8Edrtloct-jk_IBVApnqLVz6fPeQFTxxQDPXxi_Q"
#
# create_job "05" "01" "課題①" "課題①" "10,40 * * * *" "1rNnmEJ92smjkcKFOd1L_u1n8SO1LDAC4" "1CPVDaX4E3AX3xl5I_sm-DjRVr7SfYKz4DjoBSS-h74o"
# create_job "05" "02" "課題②" "課題②" "15,45 * * * *" "1rNnmEJ92smjkcKFOd1L_u1n8SO1LDAC4" "1CPVDaX4E3AX3xl5I_sm-DjRVr7SfYKz4DjoBSS-h74o"
#
# create_job "06" "01" "課題①" "課題①" "??,?? * * * *" "TODO: 令和8年度用Driveフォルダ未作成" "TODO: 令和8年度用スプレッドシート未作成"
# create_job "06" "02" "課題②" "課題②" "??,?? * * * *" "TODO: 令和8年度用Driveフォルダ未作成" "TODO: 令和8年度用スプレッドシート未作成"
#
# create_job "07" "01" "課題①" "課題①" "??,?? * * * *" "TODO: 令和8年度用Driveフォルダ未作成" "TODO: 令和8年度用スプレッドシート未作成"
# create_job "07" "02" "課題②" "課題②" "??,?? * * * *" "TODO: 令和8年度用Driveフォルダ未作成" "TODO: 令和8年度用スプレッドシート未作成"
#
# create_job "08" "01" "課題①" "課題①" "20,50 * * * *" "1kdKwI7nQ8N6j8gD6agZap5FWL-uDTbwg" "1Zm2ePE2gbKm8Yw_4B6vuO8HP3kfN2wZpFCQaNFHfcsk"
# create_job "08" "02" "課題②" "課題②" "25,55 * * * *" "1kdKwI7nQ8N6j8gD6agZap5FWL-uDTbwg" "1Zm2ePE2gbKm8Yw_4B6vuO8HP3kfN2wZpFCQaNFHfcsk"
#
# create_job "09" "01" "課題①" "課題①" "0,30 * * * *" "1nllFEyyDEV7jiTSEgyBnnNeXhC_4Ttu6" "1O8S3w3F8RvLJp0LrS-eZtX0sZW5HcjOgMhyWJ_e8YPA"
# create_job "09" "02" "課題②" "課題②" "5,35 * * * *" "1nllFEyyDEV7jiTSEgyBnnNeXhC_4Ttu6" "1O8S3w3F8RvLJp0LrS-eZtX0sZW5HcjOgMhyWJ_e8YPA"
#
# create_job "10" "01" "課題①" "課題①" "10,40 * * * *" "1BkDi3e_snacC3ITusTSAf3wojbxtpbsH" "1KPEj6LpE6gF76S3jdvADdWKlZeF-9nQ_BfhYi2dlkYA"
# create_job "10" "02" "課題②" "課題②" "15,45 * * * *" "1BkDi3e_snacC3ITusTSAf3wojbxtpbsH" "1KPEj6LpE6gF76S3jdvADdWKlZeF-9nQ_BfhYi2dlkYA"

# サマリー
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  サマリー${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo "総ジョブ数: ${TOTAL_JOBS}"

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}モード: ドライラン（実行なし）${NC}"
    echo ""
    echo -e "${GREEN}実際にジョブを作成するには:${NC}"
    echo "  DRY_RUN=false $0"
else
    echo -e "${GREEN}作成成功: ${CREATED_JOBS}${NC}"
    echo -e "${YELLOW}スキップ: ${SKIPPED_JOBS}${NC}"
    echo ""

    if [ "${CREATED_JOBS}" -gt 0 ]; then
        echo -e "${GREEN}✓ ジョブ作成完了${NC}"
        echo ""
        echo "ジョブ一覧を確認:"
        echo "  gcloud scheduler jobs list --location=${LOCATION}"
    fi
fi

echo ""
