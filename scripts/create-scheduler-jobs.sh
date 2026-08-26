#!/bin/bash
#
# Cloud Scheduler ジョブ作成スクリプト（Phase 11対応）
# 10クラス（№01〜10）× 2課題 = 20ジョブを新命名規則で作成（令和8年度・№06/07追加後）
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
    echo -e "${BLUE}[${TOTAL_JOBS}/20] ${job_name}${NC}"
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
# ⚠️⚠️⚠️ このスクリプトは実行禁止・参照専用です（2026-08-26 実適用時のcodexレビューで判明） ⚠️⚠️⚠️
# 実際の令和8年度対応（既存16ジョブの更新＋№06/07の新規4ジョブ作成）は、下記の値を使って
# gcloud CLIで個別に適用済みです。下記の値はその「適用結果の記録」であり、このスクリプトを
# 実行しても再現はできません:
#   - create_job() は既存ジョブを存在チェックでスキップするだけで、message-bodyの更新はできない
#     （既存16ジョブは gcloud scheduler jobs update http --message-body で個別に更新した）
#   - 新規ジョブ（№06・07）はこのスクリプトのまま実行すると本来のcronで直接ENABLED作成されてしまう。
#     実際には「ダミーcron（0 0 29 2 *）で作成→即pause→本来のcronへupdate」という手順で、
#     既存ピアジョブ（carewell-class03-task01）からattemptDeadline等の実行設定も明示的に複製して
#     作成した（詳細: docs/SERVICE_SHUTDOWN_AND_RESUME.md「令和8年度再開ステータス」）
# 令和7年度時点のDrive/Sheets IDは使い回さず、2026年度用に新規作成したフォルダ・スプレッドシートを
# 使用している（令和7年度分の「2025年」フォルダとは別の「2026年」フォルダ）。
#
# ⚠️ task_patternは現在も暫定値（task_idと同じ短縮形）です。text=部分一致セレクタとして機能する
# ことは実機確認済みだが、締切日入りの正式な表示名は未確定（ポータル人間確認が必要）。
#   例: "課題①" → 将来的に "課題①業務分析　※～11/3〆切" 相当の令和8年度版へ更新予定
#
# create_job "01" "01" "課題①" "課題①" "0,30 * * * *" "1-sYM3bcyGxpvWTOA3MMZJN_2_d1HkgGT" "1sg4YWQ1hHgzFWFXNbOVFXiWTXUhzvjPpejaMArwLQRc"
# create_job "01" "02" "課題②" "課題②" "5,35 * * * *" "1-sYM3bcyGxpvWTOA3MMZJN_2_d1HkgGT" "1sg4YWQ1hHgzFWFXNbOVFXiWTXUhzvjPpejaMArwLQRc"
#
# create_job "02" "01" "課題①" "課題①" "10,40 * * * *" "1VJ9TCpPYqbJ18ImTY548LsDjLeSFJuR-" "1M-QhWSBxHleF0f65AHZofzdysCBZREkgC6XGiwnrgFo"
# create_job "02" "02" "課題②" "課題②" "15,45 * * * *" "1VJ9TCpPYqbJ18ImTY548LsDjLeSFJuR-" "1M-QhWSBxHleF0f65AHZofzdysCBZREkgC6XGiwnrgFo"
#
# create_job "03" "01" "課題①" "課題①" "20,50 * * * *" "18TurAyJL-OClevEOiY3XdjYkN4aJiTlY" "1fELsGrr7CKuEuEQaHk2w8meZXzd5xqHo6IHSQOjWVKI"
# create_job "03" "02" "課題②" "課題②" "25,55 * * * *" "18TurAyJL-OClevEOiY3XdjYkN4aJiTlY" "1fELsGrr7CKuEuEQaHk2w8meZXzd5xqHo6IHSQOjWVKI"
#
# create_job "04" "01" "課題①" "課題①" "0,30 * * * *" "1pEoygSCSShHrbu5DE-qmDEBl5zwV5pE_" "1J-QbRHo0ffuxIUwkicRg6iRtw6EUjF3dNvr3I27YyAY"
# create_job "04" "02" "課題②" "課題②" "5,35 * * * *" "1pEoygSCSShHrbu5DE-qmDEBl5zwV5pE_" "1J-QbRHo0ffuxIUwkicRg6iRtw6EUjF3dNvr3I27YyAY"
#
# create_job "05" "01" "課題①" "課題①" "10,40 * * * *" "1HSBNdBSZM_eq1dvmzfL9HE0F9A7D8eD7" "1D7GDi0Waem0g07se-MBO1AHa0nH2E8wblAcHIm16_2s"
# create_job "05" "02" "課題②" "課題②" "15,45 * * * *" "1HSBNdBSZM_eq1dvmzfL9HE0F9A7D8eD7" "1D7GDi0Waem0g07se-MBO1AHa0nH2E8wblAcHIm16_2s"
#
# create_job "06" "01" "課題①" "課題①" "20,50 * * * *" "1r0J0qHdZtdLkcfq2YjCqtYfzkh5ZVtOK" "1cDV03woQ1tNur1n0XEmMJRxMPKAwl6V2FosGHzG0KA8"
# create_job "06" "02" "課題②" "課題②" "25,55 * * * *" "1r0J0qHdZtdLkcfq2YjCqtYfzkh5ZVtOK" "1cDV03woQ1tNur1n0XEmMJRxMPKAwl6V2FosGHzG0KA8"
#
# create_job "07" "01" "課題①" "課題①" "0,30 * * * *" "1yERlcHarETqjsK9fTX0_cr6jbdU7ZOJv" "1OCX-7mLjFScEwcLx5A0tYMI8YkTNcCKE8C2vh-wQkU8"
# create_job "07" "02" "課題②" "課題②" "5,35 * * * *" "1yERlcHarETqjsK9fTX0_cr6jbdU7ZOJv" "1OCX-7mLjFScEwcLx5A0tYMI8YkTNcCKE8C2vh-wQkU8"
#
# create_job "08" "01" "課題①" "課題①" "20,50 * * * *" "1eo6jJoS_LK291cnyXnxKUi10Z8YpVoN6" "1yBTyiSYG8ZTt-EZiAb69OENCvk9vHgsOPCQ3pzGAftY"
# create_job "08" "02" "課題②" "課題②" "25,55 * * * *" "1eo6jJoS_LK291cnyXnxKUi10Z8YpVoN6" "1yBTyiSYG8ZTt-EZiAb69OENCvk9vHgsOPCQ3pzGAftY"
#
# create_job "09" "01" "課題①" "課題①" "0,30 * * * *" "1jRIGRKZ1UL9ZSN0sdmN_C0a_A8LmgtTx" "15tbkPsitAVjr65xThn5869Ve6l5evvPv4avd28fAV9U"
# create_job "09" "02" "課題②" "課題②" "5,35 * * * *" "1jRIGRKZ1UL9ZSN0sdmN_C0a_A8LmgtTx" "15tbkPsitAVjr65xThn5869Ve6l5evvPv4avd28fAV9U"
#
# create_job "10" "01" "課題①" "課題①" "10,40 * * * *" "1PPdr6X034pbJAmEr-DESn8iNVuKk2x-C" "1Rtw8nqBgrM4cw8YIpjihiclQQxfa378_mHpN9OAJ_CY"
# create_job "10" "02" "課題②" "課題②" "15,45 * * * *" "1PPdr6X034pbJAmEr-DESn8iNVuKk2x-C" "1Rtw8nqBgrM4cw8YIpjihiclQQxfa378_mHpN9OAJ_CY"

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
