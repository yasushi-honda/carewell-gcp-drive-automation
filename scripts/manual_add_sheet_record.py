#!/usr/bin/env python3
"""
手動でスプレッドシートにレコードを追加するスクリプト

Usage:
    python scripts/manual_add_sheet_record.py
"""

import sys
sys.path.insert(0, "/Users/yyyhhh/carewell-gcp-drive-automation")

from datetime import datetime
from src.sheets_service import SheetsService

# 追加するレコードの情報
SPREADSHEET_ID = "1Zm2ePE2gbKm8Yw_4B6vuO8HP3kfN2wZpFCQaNFHfcsk"
TASK_ID = "課題②"
STUDENT_NAME = "高野 文佳"
STUDENT_ID = "N9904620"
SUBMIT_DATE = "2026/01/23 01:31:31"
FILENAME = "08_L190_高野文佳_進捗管理シート.xlsx"
DRIVE_FILE_ID = "1tv9f5YilJ33ubN2xd2ACeCql-afbH6Hy"


def main():
    print("=" * 60)
    print("手動スプレッドシートレコード追加")
    print("=" * 60)
    print()
    print("追加するレコード:")
    print(f"  Spreadsheet ID: {SPREADSHEET_ID}")
    print(f"  シート名: {TASK_ID}")
    print(f"  氏名: {STUDENT_NAME}")
    print(f"  日介番号: {STUDENT_ID}")
    print(f"  提出日: {SUBMIT_DATE}")
    print(f"  ファイル名: {FILENAME}")
    print(f"  Drive File ID: {DRIVE_FILE_ID}")
    print()

    # 確認
    confirm = input("このレコードを追加しますか？ [y/N]: ")
    if confirm.lower() != 'y':
        print("キャンセルしました")
        return

    print()
    print("SheetsService を初期化中...")
    service = SheetsService()

    print("レコードを追加中...")
    result = service.append_record(
        spreadsheet_id=SPREADSHEET_ID,
        task_id=TASK_ID,
        student_name=STUDENT_NAME,
        student_id=STUDENT_ID,
        submit_date=SUBMIT_DATE,
        filename=FILENAME,
        drive_file_id=DRIVE_FILE_ID,
    )

    if result:
        print()
        print("✅ レコードを正常に追加しました！")
        print()
        print("確認用URL:")
        print(f"  https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")
    else:
        print()
        print("❌ レコードの追加に失敗しました")
        print("ログを確認してください")


if __name__ == "__main__":
    main()
