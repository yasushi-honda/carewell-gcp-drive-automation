#!/usr/bin/env python3
"""
欠落スプレッドシートレコードを一括修正

⚠️ 既知の不具合を修正済み（2026-08-26 codex review指摘、PR #3）:
- ハードコードされた絶対パスをsys.pathに追加していたが誤ったパスだった
  （リポジトリ名のtypo）→ __file__基準の相対パスに修正
- 冪等性がなく、タイムアウト・中断・曖昧な結果の後に再実行すると同じレコードが
  重複してappendされていた → 実行前に対象シートの既存composite_keyを読み取り、
  既に存在するレコードはスキップするよう修正
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.sheets_service import SheetsService

# 欠落レコード一覧
MISSING_RECORDS = [
    {
        "spreadsheet_id": "1R1bsr24uyFf67p7_0I0yUA47ap5uIrJE7n89A9NbRYI",
        "task_id": "課題②",
        "student_name": "大谷 里奈",
        "student_id": "N9903359",
        "submit_date": "2025/12/02 11:33:31",
        "filename": "01_D005_大谷里奈_進捗管理シート.xlsx",
        "drive_file_id": "1j0o330uE-yAwuQm_-Yu5uaNmAKgtoJGp",
        "class": "No1",
    },
    {
        "spreadsheet_id": "12Xg8Edrtloct-jk_IBVApnqLVz6fPeQFTxxQDPXxi_Q",
        "task_id": "課題①",
        "student_name": "リス マン",
        "student_id": "N9904311",
        "submit_date": "2025/11/27 21:17:47",
        "filename": "宿題・改善方針シート (1).xlsx.xlsx",
        "drive_file_id": "1ibFMRQVClcmecmrXDty67-pOZuF05725",
        "class": "No4",
    },
    {
        "spreadsheet_id": "1CPVDaX4E3AX3xl5I_sm-DjRVr7SfYKz4DjoBSS-h74o",
        "task_id": "課題②",
        "student_name": "日髙 敬介",
        "student_id": "N9903600",
        "submit_date": "2026/01/12 19:02:34",
        "filename": "05_H127_日髙敬介_進捗管理シート.xlsx",
        "drive_file_id": "1mQMlLbeIXcTxZwPsvedMfyWSiV-9d3DM",
        "class": "No5",
    },
    {
        "spreadsheet_id": "1Zm2ePE2gbKm8Yw_4B6vuO8HP3kfN2wZpFCQaNFHfcsk",
        "task_id": "課題①",
        "student_name": "八島 泰浩",
        "student_id": "N9904120",
        "submit_date": "2025/12/02 15:54:49",
        "filename": "セットNo.8　N9904120　八島泰浩　改善方針シート.xlsx",
        "drive_file_id": "16mJcXY_JTqUe-lv9tQLIaN7p1RbpGBv5",
        "class": "No8",
    },
    {
        "spreadsheet_id": "1O8S3w3F8RvLJp0LrS-eZtX0sZW5HcjOgMhyWJ_e8YPA",
        "task_id": "課題①",
        "student_name": "山口 華恵",
        "student_id": "N9904389",
        "submit_date": "2025/12/19 14:17:26",
        "filename": "09-H138-山口華恵　業務改善シート.xlsx",
        "drive_file_id": "1QXx4fbu-kgVngE3ZxfcbvLr7wy2dJIgC",
        "class": "No9",
    },
]


def get_existing_composite_keys(
    service: SheetsService, spreadsheet_id: str, task_id: str
) -> set:
    """対象シートに既に存在するcomposite_key（B列）の集合を取得（冪等性チェック用）"""
    keys = set()
    try:
        escaped_name = task_id.replace("'", "''")
        result = (
            service.service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=f"'{escaped_name}'!B:B")
            .execute()
        )
        values = result.get("values", [])
        for row in values[1:]:  # ヘッダー行をスキップ
            if row:
                keys.add(row[0])
    except Exception as e:
        print(f"  ⚠️  既存レコード読み取りエラー（{task_id}）: {e}")
    return keys


def main():
    print("=" * 60)
    print("欠落スプレッドシートレコード一括修正")
    print("=" * 60)
    print()
    print(f"修正対象: {len(MISSING_RECORDS)} 件")
    print()

    for i, rec in enumerate(MISSING_RECORDS, 1):
        print(f"{i}. {rec['class']} / {rec['task_id']}")
        print(f"   {rec['student_name']} ({rec['student_id']})")

    print()

    print("SheetsService を初期化中...")
    service = SheetsService()
    print()

    # 冪等性チェック: (spreadsheet_id, task_id) の組み合わせごとに既存キーをキャッシュ
    existing_keys_cache: dict = {}

    success_count = 0
    skipped_count = 0
    failed = []

    for rec in MISSING_RECORDS:
        cache_key = (rec["spreadsheet_id"], rec["task_id"])
        if cache_key not in existing_keys_cache:
            existing_keys_cache[cache_key] = get_existing_composite_keys(
                service, rec["spreadsheet_id"], rec["task_id"]
            )

        composite_key = service._generate_composite_key(
            rec["student_id"], rec["filename"], rec["submit_date"]
        )

        if composite_key in existing_keys_cache[cache_key]:
            print(f"スキップ（既存）: {rec['class']} - {rec['student_name']}")
            skipped_count += 1
            continue

        print(f"追加中: {rec['class']} - {rec['student_name']}...", end=" ")

        result = service.append_record(
            spreadsheet_id=rec["spreadsheet_id"],
            task_id=rec["task_id"],
            student_name=rec["student_name"],
            student_id=rec["student_id"],
            submit_date=rec["submit_date"],
            filename=rec["filename"],
            drive_file_id=rec["drive_file_id"],
        )

        if result:
            print("✅")
            success_count += 1
            existing_keys_cache[cache_key].add(composite_key)
        else:
            print("❌")
            failed.append(rec)

    print()
    print("=" * 60)
    print(
        f"結果: {success_count} 件追加 / {skipped_count} 件スキップ（既存） / {len(MISSING_RECORDS)} 件中"
    )

    if failed:
        print()
        print("失敗したレコード:")
        for rec in failed:
            print(f"  - {rec['class']} / {rec['student_name']}")
    else:
        print("✅ 追加対象のレコードをすべて正常に処理しました！")

    print("=" * 60)


if __name__ == "__main__":
    main()
