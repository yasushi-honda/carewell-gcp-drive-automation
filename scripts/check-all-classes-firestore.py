#!/usr/bin/env python3
"""
全クラス・全課題の Firestore データ状況確認スクリプト

Dashboard デプロイ前に、全クラス・全課題のデータが
新スキーマに存在するか確認します。
"""

from collections import defaultdict

from google.cloud import firestore

# Firestore設定
PROJECT_ID = "carewell-automation"
DATABASE_NAME = "carewell-native"

# 全クラス・課題リスト（Cloud Scheduler jobs から）
CLASSES = [
    "令和7年度 デジタル中核人材養成研修 №01",
    "令和7年度 デジタル中核人材養成研修 №02",
    "令和7年度 デジタル中核人材養成研修 №03",
    "令和7年度 デジタル中核人材養成研修 №04",
    "令和7年度 デジタル中核人材養成研修 №05",
    "令和7年度 デジタル中核人材養成研修 №08",
    "令和7年度 デジタル中核人材養成研修 №09",
]

TASKS = ["課題①", "課題②"]


def check_class_task_data(db, class_name, task_id):
    """特定のクラス・課題のデータを確認"""
    result = {
        "class_name": class_name,
        "task_id": task_id,
        "new_schema": {"parent_exists": False, "file_count": 0},
        "old_schema": {"parent_exists": False, "file_count": 0},
    }

    # 新スキーマ確認
    try:
        new_task_ref = (
            db.collection("submissions")
            .document(class_name)
            .collection("tasks")
            .document(task_id)
        )
        new_task_doc = new_task_ref.get()
        new_files_ref = new_task_ref.collection("files")
        new_files_docs = list(new_files_ref.limit(1).stream())

        result["new_schema"]["parent_exists"] = new_task_doc.exists
        if new_task_doc.exists:
            data = new_task_doc.to_dict()
            result["new_schema"]["file_count"] = data.get("file_count", 0)
        else:
            # 親がなくてもサブコレクションがある可能性
            all_files = list(new_files_ref.stream())
            result["new_schema"]["file_count"] = len(all_files)
    except Exception as e:
        print(f"   ⚠️ 新スキーマエラー: {e}")

    # 旧スキーマ確認
    try:
        old_task_ref = db.collection(class_name).document(task_id)
        old_task_doc = old_task_ref.get()
        old_docs_ref = old_task_ref.collection("documents")
        old_docs_docs = list(old_docs_ref.limit(1).stream())

        result["old_schema"]["parent_exists"] = old_task_doc.exists
        if old_task_doc.exists:
            data = old_task_doc.to_dict()
            result["old_schema"]["file_count"] = data.get("file_count", 0)
        else:
            # 親がなくてもサブコレクションがある可能性
            all_docs = list(old_docs_ref.stream())
            result["old_schema"]["file_count"] = len(all_docs)
    except Exception as e:
        print(f"   ⚠️ 旧スキーマエラー: {e}")

    return result


def main():
    print("=" * 80)
    print("全クラス・全課題 Firestore データ状況確認")
    print("=" * 80)
    print()

    # Firestoreクライアント初期化
    db = firestore.Client(project=PROJECT_ID, database=DATABASE_NAME)

    all_results = []
    new_schema_ok = []
    old_schema_only = []
    both_empty = []

    for class_name in CLASSES:
        class_short = class_name.split("№")[1] if "№" in class_name else class_name
        print(f"\n📁 クラス: №{class_short}")
        print("-" * 80)

        for task_id in TASKS:
            result = check_class_task_data(db, class_name, task_id)
            all_results.append(result)

            new_count = result["new_schema"]["file_count"]
            old_count = result["old_schema"]["file_count"]

            status = ""
            if new_count > 0:
                status = f"✅ 新スキーマ: {new_count}件"
                new_schema_ok.append((class_short, task_id, new_count))
            elif old_count > 0:
                status = f"⚠️  旧スキーマのみ: {old_count}件"
                old_schema_only.append((class_short, task_id, old_count))
            else:
                status = f"⭕ データなし"
                both_empty.append((class_short, task_id))

            print(f"   {task_id}: {status}")

    # サマリー
    print("\n" + "=" * 80)
    print("📊 サマリー")
    print("=" * 80)
    print()

    print(
        f"✅ 新スキーマにデータあり（Dashboard で表示される）: {len(new_schema_ok)}件"
    )
    if new_schema_ok:
        for class_short, task_id, count in new_schema_ok:
            print(f"   - №{class_short} / {task_id}: {count}件")

    print()
    print(f"⚠️  旧スキーマのみ（Dashboard で空表示）: {len(old_schema_only)}件")
    if old_schema_only:
        for class_short, task_id, count in old_schema_only:
            print(f"   - №{class_short} / {task_id}: {count}件")

    print()
    print(f"⭕ データなし: {len(both_empty)}件")
    if both_empty:
        for class_short, task_id in both_empty:
            print(f"   - №{class_short} / {task_id}")

    # 結論
    print("\n" + "=" * 80)
    print("🎯 結論")
    print("=" * 80)
    print()

    if len(old_schema_only) == 0:
        print("✅ 全てのクラス・課題が新スキーマにデータあり")
        print("   → Dashboard デプロイ後も正常に表示されます")
    else:
        print(f"⚠️  {len(old_schema_only)}件のクラス・課題が旧スキーマのみにデータあり")
        print("   → Dashboard デプロイ後、これらは空表示になります")
        print()
        print("対応方法:")
        print("  1. 次回自動実行を待つ（新スキーマにデータが蓄積される）")
        print("  2. 手動で Backend を実行して即座にデータ取得")
        print("  3. 旧スキーマデータを新スキーマに移行（複雑、推奨しない）")

    print()


if __name__ == "__main__":
    main()
