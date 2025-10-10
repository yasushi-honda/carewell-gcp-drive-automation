#!/bin/bash
set -e

DATABASE="carewell-native"
PROJECT="carewell-automation"
CLASS_NAME="令和7年度 デジタル中核人材養成研修 №01"
TASK_ID="課題①"

echo "Firestore削除スクリプト"
echo "========================"
echo "データベース: ${DATABASE}"
echo "プロジェクト: ${PROJECT}"
echo "クラス: ${CLASS_NAME}"
echo "課題: ${TASK_ID}"
echo ""

# URLエンコード関数
urlencode() {
    python3 -c "import urllib.parse; print(urllib.parse.quote('''$1'''))"
}

CLASS_ENCODED=$(urlencode "${CLASS_NAME}")
TASK_ENCODED=$(urlencode "${TASK_ID}")

COLLECTION_PATH="${CLASS_ENCODED}/${TASK_ENCODED}/documents"

echo "コレクションパス: ${COLLECTION_PATH}"
echo ""

# ドキュメント一覧を取得
echo "ドキュメント一覧を取得中..."
DOCS=$(gcloud firestore documents list \
    --database="${DATABASE}" \
    --project="${PROJECT}" \
    --format="value(name)" \
    2>/dev/null | grep "${CLASS_NAME}/${TASK_ID}/documents" || echo "")

if [ -z "$DOCS" ]; then
    echo "削除するドキュメントが見つかりませんでした"
    exit 0
fi

DOC_COUNT=$(echo "$DOCS" | wc -l | tr -d ' ')
echo "見つかったドキュメント: ${DOC_COUNT}件"
echo ""

# 削除実行
echo "削除を開始します..."
DELETED=0
while IFS= read -r doc_name; do
    if [ -n "$doc_name" ]; then
        echo "  削除中: ${doc_name}"
        gcloud firestore documents delete "${doc_name}" \
            --database="${DATABASE}" \
            --project="${PROJECT}" \
            --quiet 2>/dev/null
        DELETED=$((DELETED + 1))
    fi
done <<< "$DOCS"

echo ""
echo "✓ 削除完了: ${DELETED}件"
