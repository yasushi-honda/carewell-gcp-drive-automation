#!/usr/bin/env python3
"""
Firestore重複チェックスクリプト

再構成されたFirestore構造（親ドキュメント + サブコレクション）で
重複ファイルを検出します。

検出項目:
  1. composite_key の重複（同じ student_id + filename + submit_date）
  2. drive_file_id の重複（同じGoogle Driveファイル）
  3. 親ドキュメントとサブコレクションの整合性

⚠️ 既知の不具合（2026-08-26発見、令和8年度対応とは無関係）:
このスクリプトは db.collection(class_name).document(task_id).collection("documents")
という旧スキーマを対象にしている。現行の本番書込み先（src/firestore_service.py）は
submissions/{class_name}/tasks/{task_id}/files/{...} のため、このスクリプトは年度・クラスに
関わらず現行の本番データを対象にできていない。修正されるまで出力結果を信頼しないこと。
詳細: docs/SERVICE_SHUTDOWN_AND_RESUME.md「令和8年度（2026年度）再開ステータス」

Usage:
    python scripts/check_duplicates.py                    # 全クラスをチェック
    python scripts/check_duplicates.py --class-name "..."  # 特定クラスのみ
    python scripts/check_duplicates.py --verbose          # 詳細出力
"""

import argparse
import sys
from collections import defaultdict
from typing import Dict, List

# Add src to path
sys.path.insert(0, "src")

from google.cloud import firestore

from config.classes import KNOWN_CLASSES, KNOWN_TASK_IDS


def check_duplicates(class_name: str = None, verbose: bool = False) -> Dict:
    """
    重複ファイルを検出する。

    Args:
        class_name: 対象クラス名（None=全クラス）
        verbose: 詳細出力

    Returns:
        Dict with results:
        - success: bool
        - total_checked: int
        - total_files: int
        - duplicates: List[Dict]
    """
    db = firestore.Client(database="carewell-native")

    # 検出対象のクラスを決定
    target_classes = [class_name] if class_name else KNOWN_CLASSES

    result = {
        "success": True,
        "total_checked": 0,
        "total_files": 0,
        "composite_key_duplicates": [],
        "drive_file_id_duplicates": [],
        "parent_mismatch": [],
    }

    # 各クラスをスキャン
    for cls_name in target_classes:
        if verbose:
            print(f"\n📚 Checking class: {cls_name}")

        # composite_key と drive_file_id の出現回数を記録
        composite_key_tracker = defaultdict(list)
        drive_file_id_tracker = defaultdict(list)

        for task_id in KNOWN_TASK_IDS:
            # 親ドキュメントの確認
            task_ref = db.collection(cls_name).document(task_id)
            task_doc = task_ref.get()

            if not task_doc.exists:
                continue

            result["total_checked"] += 1
            task_data = task_doc.to_dict()
            stored_file_count = task_data.get("file_count", 0)

            # サブコレクションをスキャン
            documents_ref = task_ref.collection("documents")
            docs = list(documents_ref.stream())
            actual_file_count = len(docs)

            result["total_files"] += actual_file_count

            # 親ドキュメントのfile_countチェック
            if stored_file_count != actual_file_count:
                result["parent_mismatch"].append(
                    {
                        "class_name": cls_name,
                        "task_id": task_id,
                        "stored_count": stored_file_count,
                        "actual_count": actual_file_count,
                        "difference": actual_file_count - stored_file_count,
                    }
                )
                result["success"] = False

            # 各ファイルドキュメントをチェック
            for doc in docs:
                doc_data = doc.to_dict()
                doc_id = doc.id

                # composite_keyの追跡
                composite_key = doc_data.get("composite_key", "")
                if composite_key:
                    composite_key_tracker[composite_key].append(
                        {
                            "class_name": cls_name,
                            "task_id": task_id,
                            "doc_id": doc_id,
                            "student_id": doc_data.get("student_id"),
                            "filename": doc_data.get("filename"),
                            "submit_date": doc_data.get("submit_date"),
                        }
                    )

                # drive_file_idの追跡
                drive_file_id = doc_data.get("drive_file_id", "")
                if drive_file_id:
                    drive_file_id_tracker[drive_file_id].append(
                        {
                            "class_name": cls_name,
                            "task_id": task_id,
                            "doc_id": doc_id,
                            "student_id": doc_data.get("student_id"),
                            "filename": doc_data.get("filename"),
                        }
                    )

            if verbose:
                print(f"  ✓ {task_id}: {actual_file_count} files")

        # 重複を検出
        for composite_key, occurrences in composite_key_tracker.items():
            if len(occurrences) > 1:
                result["composite_key_duplicates"].append(
                    {
                        "composite_key": composite_key,
                        "count": len(occurrences),
                        "occurrences": occurrences,
                    }
                )
                result["success"] = False

        for drive_file_id, occurrences in drive_file_id_tracker.items():
            if len(occurrences) > 1:
                result["drive_file_id_duplicates"].append(
                    {
                        "drive_file_id": drive_file_id,
                        "count": len(occurrences),
                        "occurrences": occurrences,
                    }
                )
                result["success"] = False

    return result


def print_results(result: Dict, verbose: bool = False) -> None:
    """
    検出結果を出力する。

    Args:
        result: 検出結果
        verbose: 詳細出力
    """
    print("\n" + "=" * 60)
    print("重複チェック結果")
    print("=" * 60 + "\n")

    print(f"✅ チェック済み親ドキュメント: {result['total_checked']}")
    print(f"✅ 総ファイル数: {result['total_files']}\n")

    # composite_key重複
    if result["composite_key_duplicates"]:
        print(f"❌ composite_key 重複: {len(result['composite_key_duplicates'])}件\n")
        for dup in result["composite_key_duplicates"]:
            print(f"  composite_key: {dup['composite_key']}")
            print(f"  出現回数: {dup['count']}")
            for occ in dup["occurrences"]:
                print(f"    - {occ['class_name']}/{occ['task_id']}")
                print(f"      doc_id: {occ['doc_id']}")
                print(
                    f"      student_id: {occ['student_id']}, filename: {occ['filename']}"
                )
            print()
    else:
        print("✅ composite_key 重複: なし")

    # drive_file_id重複
    if result["drive_file_id_duplicates"]:
        print(f"\n❌ drive_file_id 重複: {len(result['drive_file_id_duplicates'])}件\n")
        for dup in result["drive_file_id_duplicates"]:
            print(f"  drive_file_id: {dup['drive_file_id']}")
            print(f"  出現回数: {dup['count']}")
            for occ in dup["occurrences"]:
                print(f"    - {occ['class_name']}/{occ['task_id']}")
                print(f"      doc_id: {occ['doc_id']}")
                print(
                    f"      student_id: {occ['student_id']}, filename: {occ['filename']}"
                )
            print()
    else:
        print("✅ drive_file_id 重複: なし")

    # 親ドキュメントのfile_count不整合
    if result["parent_mismatch"]:
        print(
            f"\n⚠️  親ドキュメント file_count 不整合: {len(result['parent_mismatch'])}件\n"
        )
        for mismatch in result["parent_mismatch"]:
            print(f"  {mismatch['class_name']}/{mismatch['task_id']}")
            print(
                f"    stored: {mismatch['stored_count']}, actual: {mismatch['actual_count']}"
            )
            print(f"    diff: {mismatch['difference']:+d}\n")
        print("💡 修正方法: python scripts/fix_file_count.py --execute")
    else:
        print("\n✅ 親ドキュメント file_count: すべて正確")

    print("\n" + "=" * 60)
    if result["success"]:
        print("✅ すべてのチェックに合格しました")
    else:
        print("❌ 問題が検出されました")
    print("=" * 60 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Firestore重複チェックスクリプト")
    parser.add_argument(
        "--class-name",
        type=str,
        help="特定クラスのみチェック（省略時=全クラス）",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="詳細出力",
    )

    args = parser.parse_args()

    print("🔍 Firestoreデータの重複チェックを開始...")

    try:
        result = check_duplicates(
            class_name=args.class_name,
            verbose=args.verbose,
        )

        print_results(result, verbose=args.verbose)

        # 終了コード
        sys.exit(0 if result["success"] else 1)

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
