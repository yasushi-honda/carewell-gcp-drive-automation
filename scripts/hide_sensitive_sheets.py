#!/usr/bin/env python3
"""
クライアント要望(2026-09-12)対応: 「受講者リスト」タブの会社・事業所列とタブ自体、
「課題①」タブを非表示化するワンオフスクリプト。

背景: サブ講師が確認する`{No}_受講者リスト_出欠管理`スプレッドシートについて、
個人情報保護(会社名・事業所名の非掲載)と誤操作防止(課題①タブの非表示)をクライアントから
依頼された。データそのものは削除せず(将来的な復元・別用途利用に備える)、UI上の非表示化のみ行う。
今後新規作成される課題タブの非表示化はコード側で対応済み(src/sheets_service.py の
_ensure_sheet_exists)。本スクリプトは既存タブへの一括適用のみを担う。

対象: №01, 02, 03, 04, 05, 06, 07, 09 の8クラス
  - `{No}_受講者リスト_出欠管理`ファイルの「受講者リスト」タブ: D・E列(会社・事業所)を列非表示 + タブ自体を非表示
  - 課題①提出記録シートの「課題①」タブ: タブ自体を非表示(存在する場合のみ)

使い方:
    python scripts/hide_sensitive_sheets.py            # dry-run(現状確認のみ)
    python scripts/hide_sensitive_sheets.py --commit   # 実際に非表示化を適用
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.gcp_sa_auth import call_with_reauth, get_impersonated_service  # noqa: E402
from scripts.merge_student_roster import (  # noqa: E402
    ROSTER_TARGET_TAB,
    _build_sheets_service,
    resolve_attendance_spreadsheet_id,
)

TARGET_CLASSES = ["01", "02", "03", "04", "05", "06", "07", "09"]

# 課題①提出記録シートは、merge_student_roster.py用SA(carewell-automation-sa)には
# 編集権限がなく(anyone:readerのみの共有設定)、403で失敗することを実機確認済み(2026-09-12)。
# Cloud Run実行用SA(github-actions-sa)は当該シートへの書込み権限を実際に持っているため、
# 課題①タブの操作にはこちらを使う。
TASK1_SA_EMAIL = "github-actions-sa@carewell-automation.iam.gserviceaccount.com"
TASK1_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _build_task1_sheets_service():
    return get_impersonated_service("sheets", "v4", TASK1_SA_EMAIL, TASK1_SCOPES)

TASK1_SUBMISSION_SPREADSHEET_IDS = {
    "01": "1sg4YWQ1hHgzFWFXNbOVFXiWTXUhzvjPpejaMArwLQRc",
    "02": "1M-QhWSBxHleF0f65AHZofzdysCBZREkgC6XGiwnrgFo",
    "03": "1fELsGrr7CKuEuEQaHk2w8meZXzd5xqHo6IHSQOjWVKI",
    "04": "1J-QbRHo0ffuxIUwkicRg6iRtw6EUjF3dNvr3I27YyAY",
    "05": "1D7GDi0Waem0g07se-MBO1AHa0nH2E8wblAcHIm16_2s",
    "06": "1cDV03woQ1tNur1n0XEmMJRxMPKAwl6V2FosGHzG0KA8",
    "07": "1OCX-7mLjFScEwcLx5A0tYMI8YkTNcCKE8C2vh-wQkU8",
    "09": "15tbkPsitAVjr65xThn5869Ve6l5evvPv4avd28fAV9U",
}

TASK1_TAB_NAME = "課題①"
COMPANY_OFFICE_COLUMN_RANGE = (3, 5)  # 0-indexed [start, end) = D,E列


def _get_sheet_properties_list(spreadsheet_id: str, build_service_fn=_build_sheets_service) -> list[dict]:
    meta = call_with_reauth(
        build_service_fn,
        lambda svc: svc.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets.properties")
        .execute(),
    )
    return [s["properties"] for s in meta.get("sheets", [])]


def _find_sheet(properties_list: list[dict], title: str) -> dict | None:
    matches = [p for p in properties_list if p.get("title") == title]
    if len(matches) > 1:
        raise RuntimeError(f"タブ「{title}」が複数見つかりました: {matches}")
    return matches[0] if matches else None


def _batch_update(spreadsheet_id: str, requests: list[dict], build_service_fn=_build_sheets_service) -> None:
    call_with_reauth(
        build_service_fn,
        lambda svc: svc.spreadsheets()
        .batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests})
        .execute(),
    )


def plan_roster_requests(sheet_props: dict) -> list[dict]:
    """「受講者リスト」タブ用のbatchUpdateリクエストを組み立てる。"""
    sheet_id = sheet_props["sheetId"]
    requests = []
    if not sheet_props.get("hidden", False):
        requests.append(
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": sheet_id, "hidden": True},
                    "fields": "hidden",
                }
            }
        )
    start, end = COMPANY_OFFICE_COLUMN_RANGE
    requests.append(
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": start,
                    "endIndex": end,
                },
                "properties": {"hiddenByUser": True},
                "fields": "hiddenByUser",
            }
        }
    )
    return requests


def plan_task1_requests(sheet_props: dict) -> list[dict]:
    """「課題①」タブ用のbatchUpdateリクエストを組み立てる。"""
    if sheet_props.get("hidden", False):
        return []
    return [
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_props["sheetId"], "hidden": True},
                "fields": "hidden",
            }
        }
    ]


def process_class(class_num: str, commit: bool, backup_dir: Path) -> dict:
    result = {"class": class_num, "roster": None, "task1": None}

    # --- 「受講者リスト」タブ ---
    try:
        attendance_id = resolve_attendance_spreadsheet_id(class_num)
    except Exception as e:  # noqa: BLE001
        result["roster"] = {"status": "error", "detail": f"ID解決失敗: {e}"}
    else:
        roster_props_list = _get_sheet_properties_list(attendance_id)
        roster_sheet = _find_sheet(roster_props_list, ROSTER_TARGET_TAB)
        if roster_sheet is None:
            result["roster"] = {
                "status": "skipped",
                "detail": f"「{ROSTER_TARGET_TAB}」タブが存在しません(spreadsheet_id={attendance_id})",
            }
        else:
            backup_path = backup_dir / f"class{class_num}_roster_before.json"
            backup_path.write_text(
                json.dumps(roster_sheet, ensure_ascii=False, indent=2)
            )
            requests = plan_roster_requests(roster_sheet)
            if not commit:
                result["roster"] = {
                    "status": "dry-run",
                    "spreadsheet_id": attendance_id,
                    "before_hidden": roster_sheet.get("hidden", False),
                    "planned_requests": len(requests),
                }
            else:
                _batch_update(attendance_id, requests)
                after_props_list = _get_sheet_properties_list(attendance_id)
                after_sheet = _find_sheet(after_props_list, ROSTER_TARGET_TAB)
                result["roster"] = {
                    "status": "applied",
                    "spreadsheet_id": attendance_id,
                    "after_hidden": after_sheet.get("hidden", False) if after_sheet else None,
                }

    # --- 「課題①」タブ ---
    task1_id = TASK1_SUBMISSION_SPREADSHEET_IDS.get(class_num)
    if task1_id is None:
        result["task1"] = {"status": "skipped", "detail": "spreadsheet_id未登録"}
    else:
        task1_props_list = _get_sheet_properties_list(
            task1_id, build_service_fn=_build_task1_sheets_service
        )
        task1_sheet = _find_sheet(task1_props_list, TASK1_TAB_NAME)
        if task1_sheet is None:
            result["task1"] = {
                "status": "skipped",
                "detail": f"「{TASK1_TAB_NAME}」タブが未作成(spreadsheet_id={task1_id})",
            }
        else:
            backup_path = backup_dir / f"class{class_num}_task1_before.json"
            backup_path.write_text(
                json.dumps(task1_sheet, ensure_ascii=False, indent=2)
            )
            requests = plan_task1_requests(task1_sheet)
            if not commit:
                result["task1"] = {
                    "status": "dry-run",
                    "spreadsheet_id": task1_id,
                    "before_hidden": task1_sheet.get("hidden", False),
                    "planned_requests": len(requests),
                }
            elif not requests:
                result["task1"] = {"status": "already_hidden", "spreadsheet_id": task1_id}
            else:
                _batch_update(
                    task1_id, requests, build_service_fn=_build_task1_sheets_service
                )
                after_props_list = _get_sheet_properties_list(
                    task1_id, build_service_fn=_build_task1_sheets_service
                )
                after_sheet = _find_sheet(after_props_list, TASK1_TAB_NAME)
                result["task1"] = {
                    "status": "applied",
                    "spreadsheet_id": task1_id,
                    "after_hidden": after_sheet.get("hidden", False) if after_sheet else None,
                }

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--commit", action="store_true", help="実際に非表示化を適用する(省略時はdry-run)"
    )
    parser.add_argument(
        "--class",
        dest="class_num",
        default=None,
        help="対象クラスを1件に限定する場合に指定(例: 01)。省略時は対象8クラス全件",
    )
    args = parser.parse_args()

    classes = [args.class_num] if args.class_num else TARGET_CLASSES

    scratch_dir = Path.home() / ".claude" / "scratch" / "hide_sensitive_sheets"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = scratch_dir / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    print(f"[バックアップ先] {backup_dir}")

    all_results = []
    for class_num in classes:
        print(f"\n=== クラス{class_num} ===")
        result = process_class(class_num, args.commit, backup_dir)
        all_results.append(result)
        print(f"  受講者リスト: {result['roster']}")
        print(f"  課題①      : {result['task1']}")

    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2))
    print(f"\n[結果一覧] {manifest_path}")

    if not args.commit:
        print("\n[DRY-RUN] --commitが指定されていないため変更は行いませんでした。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
