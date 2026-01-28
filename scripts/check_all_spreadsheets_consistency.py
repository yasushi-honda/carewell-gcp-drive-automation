#!/usr/bin/env python3
"""
全クラス Firestore - スプレッドシート 整合性チェック

各クラスのスプレッドシートとFirestoreの整合性を確認する
"""

import sys
sys.path.insert(0, "/Users/yyyhhh/carewell-gcp-drive-automation")

from google.cloud import firestore
from src.sheets_service import SheetsService

# 設定
DATABASE_NAME = "carewell-native"
PROJECT_ID = "carewell-automation"

# クラス別スプレッドシートID と Firestoreクラス名のマッピング
CLASS_CONFIG = {
    "No1": {
        "spreadsheet_id": "1R1bsr24uyFf67p7_0I0yUA47ap5uIrJE7n89A9NbRYI",
        "firestore_name": "令和7年度 デジタル中核人材養成研修 №01",
    },
    "No2": {
        "spreadsheet_id": "1qmczJQo2f3rSsZxhRWF3XfjCVc5Y3yW7K4wrk7bAcnc",
        "firestore_name": "令和7年度 デジタル中核人材養成研修 №02",
    },
    "No3": {
        "spreadsheet_id": "1kzDATIoQ1hOM9KYuYloCPsbmGn-tSDHSwYxK9pYQkwA",
        "firestore_name": "令和7年度 デジタル中核人材養成研修 №03",
    },
    "No4": {
        "spreadsheet_id": "12Xg8Edrtloct-jk_IBVApnqLVz6fPeQFTxxQDPXxi_Q",
        "firestore_name": "令和7年度 デジタル中核人材養成研修 №04",
    },
    "No5": {
        "spreadsheet_id": "1CPVDaX4E3AX3xl5I_sm-DjRVr7SfYKz4DjoBSS-h74o",
        "firestore_name": "令和7年度 デジタル中核人材養成研修 №05",
    },
    "No8": {
        "spreadsheet_id": "1Zm2ePE2gbKm8Yw_4B6vuO8HP3kfN2wZpFCQaNFHfcsk",
        "firestore_name": "令和7年度 デジタル中核人材養成研修 №08",
    },
    "No9": {
        "spreadsheet_id": "1O8S3w3F8RvLJp0LrS-eZtX0sZW5HcjOgMhyWJ_e8YPA",
        "firestore_name": "令和7年度 デジタル中核人材養成研修 №09",
    },
    "No10": {
        "spreadsheet_id": "1KPEj6LpE6gF76S3jdvADdWKlZeF-9nQ_BfhYi2dlkYA",
        "firestore_name": "令和7年度 デジタル中核人材養成研修 №10",
    },
}

TASKS = ["課題①", "課題②"]


def get_firestore_records(db, class_name: str, task_id: str) -> dict:
    """Firestoreから指定クラス・課題のレコードを取得"""
    records = {}
    try:
        files_ref = db.collection("submissions").document(class_name).collection("tasks").document(task_id).collection("files")
        docs = files_ref.stream()

        for doc in docs:
            data = doc.to_dict()
            student_id = data.get("student_id", "")
            if student_id:
                key = f"{student_id}_{data.get('filename', '')}"
                records[key] = {
                    "student_id": student_id,
                    "student_name": data.get("student_name", ""),
                    "filename": data.get("filename", ""),
                    "submit_date": data.get("submit_date", ""),
                    "drive_file_id": data.get("drive_file_id", ""),
                    "composite_key": doc.id,
                }
    except Exception as e:
        pass

    return records


def get_spreadsheet_records(sheets_service, spreadsheet_id: str, task_id: str) -> set:
    """スプレッドシートから指定課題のレコードを取得"""
    records = set()
    try:
        escaped_name = task_id.replace("'", "''")
        result = sheets_service.service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{escaped_name}'!A:H"
        ).execute()

        values = result.get("values", [])

        for row in values[1:]:  # ヘッダーをスキップ
            if len(row) >= 6:
                student_id = row[3] if len(row) > 3 else ""
                filename = row[5] if len(row) > 5 else ""
                if student_id and filename:
                    key = f"{student_id}_{filename}"
                    records.add(key)
    except Exception as e:
        pass

    return records


def main():
    print("=" * 70)
    print("全クラス Firestore - スプレッドシート 整合性チェック")
    print("=" * 70)
    print()

    # Firestore初期化
    print("Firestore に接続中...")
    try:
        db = firestore.Client(project=PROJECT_ID, database=DATABASE_NAME)
        print("  ✅ Firestore 接続成功")
    except Exception as e:
        print(f"  ❌ Firestore 接続失敗: {e}")
        return

    # SheetsService初期化
    print("Google Sheets に接続中...")
    try:
        sheets_service = SheetsService()
        print("  ✅ Google Sheets 接続成功")
    except Exception as e:
        print(f"  ❌ Google Sheets 接続失敗: {e}")
        return

    print()

    total_missing = 0
    all_missing_records = []
    class_summary = []

    for class_key in sorted(CLASS_CONFIG.keys(), key=lambda x: int(x.replace("No", ""))):
        config = CLASS_CONFIG[class_key]
        spreadsheet_id = config["spreadsheet_id"]
        firestore_name = config["firestore_name"]

        print(f"\n{'='*70}")
        print(f"【{class_key}】チェック中...")
        print(f"  Firestore: {firestore_name}")
        print(f"  Spreadsheet: {spreadsheet_id}")
        print("-" * 70)

        class_missing = 0

        for task_id in TASKS:
            # Firestoreのレコードを取得
            firestore_records = get_firestore_records(db, firestore_name, task_id)

            # スプレッドシートのレコードを取得
            sheet_records = get_spreadsheet_records(sheets_service, spreadsheet_id, task_id)

            # 差分チェック
            missing_in_sheet = []
            for key, record in firestore_records.items():
                if key not in sheet_records:
                    missing_in_sheet.append(record)
                    all_missing_records.append({
                        "class": class_key,
                        "task": task_id,
                        "spreadsheet_id": spreadsheet_id,
                        **record
                    })

            missing_count = len(missing_in_sheet)
            class_missing += missing_count
            total_missing += missing_count

            if missing_count > 0:
                print(f"  {task_id}: Firestore={len(firestore_records)}, Sheet={len(sheet_records)}, ❌ 欠落={missing_count}")
                for rec in missing_in_sheet:
                    print(f"      - {rec['student_name']} ({rec['student_id']}): {rec['filename']}")
            else:
                print(f"  {task_id}: Firestore={len(firestore_records)}, Sheet={len(sheet_records)}, ✅ OK")

        class_summary.append({
            "class": class_key,
            "missing": class_missing
        })

    # サマリー
    print()
    print("=" * 70)
    print("【結果サマリー】")
    print("=" * 70)

    for summary in class_summary:
        status = "✅" if summary["missing"] == 0 else "❌"
        print(f"  {summary['class']}: {status} 欠落 {summary['missing']} 件")

    print()
    print(f"  合計欠落件数: {total_missing} 件")
    print("=" * 70)

    if all_missing_records:
        print()
        print("【欠落レコード詳細】")
        print("-" * 70)
        for i, rec in enumerate(all_missing_records, 1):
            print(f"{i}. {rec['class']} / {rec['task']}")
            print(f"   氏名: {rec['student_name']} ({rec['student_id']})")
            print(f"   ファイル: {rec['filename']}")
            print(f"   提出日: {rec['submit_date']}")
            print(f"   Drive ID: {rec['drive_file_id']}")
            print(f"   Spreadsheet: {rec['spreadsheet_id']}")
            print()


if __name__ == "__main__":
    main()
