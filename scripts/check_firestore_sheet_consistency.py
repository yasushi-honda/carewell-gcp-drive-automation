#!/usr/bin/env python3
"""
Firestore と スプレッドシート の整合性チェックスクリプト

Firestoreに存在するがスプレッドシートに存在しないレコードを検出する
"""

import sys
sys.path.insert(0, "/Users/yyyhhh/carewell-gcp-drive-automation")

from google.cloud import firestore
from src.sheets_service import SheetsService

# 設定
SPREADSHEET_ID = "1Zm2ePE2gbKm8Yw_4B6vuO8HP3kfN2wZpFCQaNFHfcsk"
DATABASE_NAME = "carewell-native"
PROJECT_ID = "carewell-automation"

# チェック対象のクラスと課題
CLASSES = ["No1", "No2", "No3", "No4", "No5", "No8", "No9", "No10"]
TASKS = ["課題①", "課題②"]


def get_firestore_records(db, class_name: str, task_id: str) -> dict:
    """Firestoreから指定クラス・課題のレコードを取得"""
    records = {}
    try:
        # パス: submissions/{class_name}/tasks/{task_id}/files/{composite_key}
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
        print(f"  Firestore読み取りエラー ({class_name}/{task_id}): {e}")

    return records


def get_spreadsheet_records(sheets_service, task_id: str) -> set:
    """スプレッドシートから指定課題のレコードを取得（student_id_filenameのセット）"""
    records = set()
    try:
        # シート名はtask_id（例: "課題②"）
        escaped_name = task_id.replace("'", "''")
        result = sheets_service.service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{escaped_name}'!A:H"
        ).execute()

        values = result.get("values", [])

        # ヘッダー行をスキップ
        for row in values[1:]:
            if len(row) >= 6:
                # B列: 複合キー, D列: 日介番号, F列: ファイル名
                student_id = row[3] if len(row) > 3 else ""
                filename = row[5] if len(row) > 5 else ""
                if student_id and filename:
                    key = f"{student_id}_{filename}"
                    records.add(key)
    except Exception as e:
        print(f"  スプレッドシート読み取りエラー ({task_id}): {e}")

    return records


def main():
    print("=" * 70)
    print("Firestore - スプレッドシート 整合性チェック")
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
    print("-" * 70)

    total_missing = 0
    missing_records = []

    for task_id in TASKS:
        print(f"\n【{task_id}】チェック中...")

        # スプレッドシートのレコードを取得
        sheet_records = get_spreadsheet_records(sheets_service, task_id)
        print(f"  スプレッドシート: {len(sheet_records)} 件")

        task_missing = 0

        for class_name in CLASSES:
            # Firestoreのレコードを取得
            firestore_records = get_firestore_records(db, class_name, task_id)

            if not firestore_records:
                continue

            # 差分チェック
            for key, record in firestore_records.items():
                if key not in sheet_records:
                    task_missing += 1
                    total_missing += 1
                    missing_records.append({
                        "class": class_name,
                        "task": task_id,
                        **record
                    })
                    print(f"  ⚠️  欠落: {class_name} - {record['student_name']} ({record['student_id']}) - {record['filename']}")

        if task_missing == 0:
            print(f"  ✅ 欠落なし")
        else:
            print(f"  ❌ {task_missing} 件の欠落を検出")

    print()
    print("=" * 70)
    print(f"【結果サマリー】")
    print(f"  合計欠落件数: {total_missing} 件")
    print("=" * 70)

    if missing_records:
        print()
        print("【欠落レコード一覧】")
        for i, rec in enumerate(missing_records, 1):
            print(f"{i}. {rec['class']} / {rec['task']}")
            print(f"   氏名: {rec['student_name']} ({rec['student_id']})")
            print(f"   ファイル: {rec['filename']}")
            print(f"   提出日: {rec['submit_date']}")
            print(f"   Drive ID: {rec['drive_file_id']}")
            print()


if __name__ == "__main__":
    main()
