#!/bin/bash
#
# Firestoreの特定クラス・課題のデータをクリアするスクリプト
#
# Usage:
#   ./scripts/cleanup-firestore-class.sh "令和7年度 デジタル中核人材養成研修 №01" "課題①"
#   ./scripts/cleanup-firestore-class.sh "令和7年度 デジタル中核人材養成研修 №01" "課題①" --execute
#

set -e

# 色付きログ
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# パラメータ
CLASS_NAME="${1}"
TASK_ID="${2}"
EXECUTE_FLAG="${3}"

# ドライランモード（デフォルト）
DRY_RUN=true
if [ "$EXECUTE_FLAG" == "--execute" ]; then
    DRY_RUN=false
fi

# パラメータチェック
if [ -z "$CLASS_NAME" ] || [ -z "$TASK_ID" ]; then
    echo -e "${RED}Error: クラス名と課題IDが必要です${NC}"
    echo ""
    echo "Usage:"
    echo "  $0 \"クラス名\" \"課題ID\" [--execute]"
    echo ""
    echo "Example:"
    echo "  $0 \"令和7年度 デジタル中核人材養成研修 №01\" \"課題①\""
    echo "  $0 \"令和7年度 デジタル中核人材養成研修 №01\" \"課題①\" --execute"
    exit 1
fi

# GCPプロジェクト確認
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: GCPプロジェクトが設定されていません${NC}"
    exit 1
fi

# ヘッダー
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  Firestoreデータクリア${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo "Project: ${PROJECT_ID}"
echo "クラス: ${CLASS_NAME}"
echo "課題: ${TASK_ID}"
echo "コレクションパス: ${CLASS_NAME}/${TASK_ID}/documents"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}⚠️  ドライランモード: 実際には削除しません${NC}"
    echo -e "${YELLOW}   実行するには: $0 \"${CLASS_NAME}\" \"${TASK_ID}\" --execute${NC}"
    echo ""
fi

# ドキュメント数を取得
echo -e "${BLUE}ドキュメント数を確認中...${NC}"
COLLECTION_PATH="${CLASS_NAME}/${TASK_ID}/documents"

# Firestoreからドキュメント一覧を取得
DOCUMENT_IDS=$(gcloud firestore documents list \
    --collection-path="${COLLECTION_PATH}" \
    --format="value(name)" \
    2>/dev/null || true)

if [ -z "$DOCUMENT_IDS" ]; then
    echo -e "${YELLOW}ドキュメントが見つかりませんでした${NC}"
    echo "コレクションは空、または存在しません"
    exit 0
fi

# ドキュメント数をカウント
DOC_COUNT=$(echo "$DOCUMENT_IDS" | wc -l | tr -d ' ')
echo -e "${GREEN}ドキュメント数: ${DOC_COUNT}件${NC}"
echo ""

# ドキュメント一覧を表示（最初の10件）
echo "削除対象のドキュメント（最初の10件）:"
echo "$DOCUMENT_IDS" | head -10 | while read -r doc_path; do
    doc_id=$(basename "$doc_path")
    echo "  - $doc_id"
done

if [ "$DOC_COUNT" -gt 10 ]; then
    echo "  ... 他 $((DOC_COUNT - 10))件"
fi
echo ""

# 確認
if [ "$DRY_RUN" = false ]; then
    echo -e "${RED}⚠️  警告: ${DOC_COUNT}件のドキュメントを削除します${NC}"
    echo -e "${RED}   この操作は取り消せません！${NC}"
    echo ""
    read -p "続行しますか? (yes/no): " CONFIRM

    if [ "$CONFIRM" != "yes" ]; then
        echo "キャンセルしました"
        exit 0
    fi
    echo ""

    # 削除実行
    echo -e "${YELLOW}削除中...${NC}"
    DELETED_COUNT=0

    echo "$DOCUMENT_IDS" | while read -r doc_path; do
        doc_id=$(basename "$doc_path")

        if gcloud firestore documents delete "$doc_path" --quiet 2>/dev/null; then
            DELETED_COUNT=$((DELETED_COUNT + 1))
            echo -e "${GREEN}✓${NC} $doc_id"
        else
            echo -e "${RED}✗${NC} $doc_id (削除失敗)"
        fi
    done

    echo ""
    echo -e "${GREEN}✓ 削除完了${NC}"
    echo ""

    # 削除後の確認
    echo "削除後の確認..."
    REMAINING=$(gcloud firestore documents list \
        --collection-path="${COLLECTION_PATH}" \
        --format="value(name)" \
        2>/dev/null | wc -l | tr -d ' ')

    if [ "$REMAINING" -eq 0 ]; then
        echo -e "${GREEN}✓ コレクションは空になりました${NC}"
    else
        echo -e "${YELLOW}⚠️  ${REMAINING}件のドキュメントが残っています${NC}"
    fi
else
    echo -e "${YELLOW}[ドライラン] 削除コマンド例:${NC}"
    echo "$DOCUMENT_IDS" | head -3 | while read -r doc_path; do
        echo "  gcloud firestore documents delete \"$doc_path\" --quiet"
    done
    if [ "$DOC_COUNT" -gt 3 ]; then
        echo "  ... 他 $((DOC_COUNT - 3))件"
    fi
fi

echo ""
