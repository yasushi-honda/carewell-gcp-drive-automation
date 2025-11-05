#!/usr/bin/env python3
"""
旧スキーマデータ削除スクリプト

Phase 10: Dashboard が新スキーマに移行完了後、
旧スキーマ {class_name}/{task_id}/documents/ のデータを削除する。

安全のため、削除前に確認プロンプトを表示。
"""

from google.cloud import firestore

# Firestore設定
PROJECT_ID = "carewell-automation"
DATABASE_NAME = "carewell-native"

# 削除対象
CLASS_NAME = "令和7年度 デジタル中核人材養成研修 №01"
TASK_ID = "課題①"


def delete_legacy_schema_data(db, class_name, task_id):
    """旧スキーマのデータを削除"""

    print(f"\n🎯 削除対象:")
    print(f"   パス: {class_name}/{task_id}/")
    print(f"   サブコレクション: documents/")
    print()

    # 親ドキュメント参照
    parent_ref = db.collection(class_name).document(task_id)

    # サブコレクション削除
    print("📁 サブコレクション 'documents/' を削除中...")
    docs_ref = parent_ref.collection("documents")
    deleted_count = 0

    # バッチ削除（最大500件ずつ）
    batch_size = 500
    docs = docs_ref.limit(batch_size).stream()
    deleted = 0

    for doc in docs:
        doc.reference.delete()
        deleted += 1
        deleted_count += 1

        if deleted % 100 == 0:
            print(f"   削除済み: {deleted}件")

    if deleted_count > 0:
        print(f"   ✅ サブコレクション削除完了: {deleted_count}件")
    else:
        print(f"   ⚠️  サブコレクションは空でした")

    # 親ドキュメント削除
    print("\n📄 親ドキュメントを削除中...")
    parent_doc = parent_ref.get()
    if parent_doc.exists:
        parent_ref.delete()
        print(f"   ✅ 親ドキュメント削除完了")
    else:
        print(f"   ⚠️  親ドキュメントは既に存在しません")

    return deleted_count


def main():
    print("=" * 80)
    print("旧スキーマデータ削除スクリプト")
    print("=" * 80)
    print()
    print("⚠️  警告: 以下のデータを削除します:")
    print(f"   - クラス: {CLASS_NAME}")
    print(f"   - 課題: {TASK_ID}")
    print(f"   - パス: {CLASS_NAME}/{TASK_ID}/documents/")
    print()
    print("Dashboard は既に新スキーマに移行済みのため、")
    print("この旧データは使用されていません。")
    print()

    # 確認プロンプト
    confirm = input("削除を実行しますか？ [yes/NO]: ").strip().lower()

    if confirm != "yes":
        print("\n❌ キャンセルしました")
        return

    print("\n🚀 削除を開始します...\n")

    # Firestoreクライアント初期化
    db = firestore.Client(project=PROJECT_ID, database=DATABASE_NAME)

    # 削除実行
    deleted_count = delete_legacy_schema_data(db, CLASS_NAME, TASK_ID)

    # 完了メッセージ
    print("\n" + "=" * 80)
    print("✅ 削除完了")
    print("=" * 80)
    print()
    print(f"削除件数: {deleted_count}件")
    print()
    print("📌 次回の Backend 自動実行時（毎時 :00 と :30）に、")
    print("   新スキーマにデータが再取得され、Dashboard に表示されます。")
    print()


if __name__ == "__main__":
    main()
