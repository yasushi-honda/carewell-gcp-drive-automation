#!/usr/bin/env python3
"""
クライアント要望(2026-09-12対応、2026-09-18に保護機能を追加拡張)対応:
「受講者リスト」タブの会社・事業所列とタブ自体、「課題①」タブを非表示化+保護するスクリプト。
Step 2(IMPORTRANGE数式配線)実施後の各クラスで、1コマンドで毎回適用できる想定。

背景: サブ講師が確認する`{No}_受講者リスト_出欠管理`スプレッドシートについて、
個人情報保護(会社名・事業所名の非掲載)と誤操作防止(課題①タブの非表示)をクライアントから
依頼された。データそのものは削除せず(将来的な復元・別用途利用に備える)、UI上の非表示化のみ行う。
2026-09-18: 会社・事業所欄は`merge_student_roster.py`のコード修正により`--commit`実行のたびに
常に空欄で書き込まれるよう恒久対応済み(本スクリプトの列非表示は多層防御として維持)。
また非表示化だけではファイル全体の編集者なら誰でも解除できてしまうため(Google Sheets仕様上の
制約)、同時に「シートを保護」(編集者を名前付きユーザーのみに制限)も適用するよう拡張した。
今後新規作成される「課題①提出記録シート」側タブの非表示化はコード側で対応済み(src/sheets_service.py の
_ensure_sheet_exists)。本スクリプトは既存タブへの一括適用と、`{No}_受講者リスト_出欠管理`ファイル
自身の「受講者リスト」「課題①」タブ(Step 2で新規作成される)への非表示化+保護の両方を担う。

対象: №01, 02, 03, 04, 05, 06, 07, 09 の8クラス
  - `{No}_受講者リスト_出欠管理`ファイルの「受講者リスト」タブ: D・E列(会社・事業所)を列非表示
    + タブ自体を非表示 + シート保護(編集者=ファイルの現在のwriter/owner全員、サービスアカウント含む)
  - 同ファイルの「課題①」タブ(IMPORTRANGE配線先、Step 2で新規作成): タブ自体を非表示
    + シート保護(編集者=同上。存在する場合のみ)
  - 課題①提出記録シート(参照元、別ファイル)の「課題①」タブ: タブ自体を非表示のみ(存在する場合のみ。
    carewell-automation-saに編集権限がないため保護は対象外)

冪等性: 既に非表示/保護済みの場合は再適用しない(何度でも安全に再実行できる)。

使い方:
    python scripts/hide_sensitive_sheets.py            # dry-run(現状確認のみ)
    python scripts/hide_sensitive_sheets.py --commit   # 実際に非表示化+保護を適用
    python scripts/hide_sensitive_sheets.py --class 02 --commit  # 特定クラスのみ
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.merge_student_roster import (  # noqa: E402
    ROSTER_TARGET_TAB,
    _build_drive_service,
    _build_sheets_service,
    resolve_attendance_spreadsheet_id,
)
from src.gcp_sa_auth import call_with_reauth, get_impersonated_service  # noqa: E402

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


def _get_sheet_properties_list(
    spreadsheet_id: str, build_service_fn=_build_sheets_service
) -> list[dict]:
    meta = call_with_reauth(
        build_service_fn,
        lambda svc: svc.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets.properties")
        .execute(),
    )
    return [s["properties"] for s in meta.get("sheets", [])]


def _get_full_sheets_list(
    spreadsheet_id: str, build_service_fn=_build_sheets_service
) -> list[dict]:
    """properties + protectedRanges込みでシート一覧を取得する(保護の冪等性判定用)。"""
    meta = call_with_reauth(
        build_service_fn,
        lambda svc: svc.spreadsheets()
        .get(
            spreadsheetId=spreadsheet_id,
            fields="sheets(properties,protectedRanges)",
        )
        .execute(),
    )
    return meta.get("sheets", [])


def _find_sheet(properties_list: list[dict], title: str) -> dict | None:
    matches = [p for p in properties_list if p.get("title") == title]
    if len(matches) > 1:
        raise RuntimeError(f"タブ「{title}」が複数見つかりました: {matches}")
    return matches[0] if matches else None


def _find_sheet_entry(full_sheets: list[dict], title: str) -> dict | None:
    """_get_full_sheets_listの結果からタイトル一致するシートエントリ(properties+protectedRanges)を探す。"""
    matches = [s for s in full_sheets if s.get("properties", {}).get("title") == title]
    if len(matches) > 1:
        raise RuntimeError(f"タブ「{title}」が複数見つかりました: {matches}")
    return matches[0] if matches else None


def _is_whole_sheet_protected(sheet_entry: dict) -> bool:
    """指定シートに、セル範囲指定なし(=シート全体)の保護が既に存在するか判定する(冪等性用)。"""
    for pr in sheet_entry.get("protectedRanges", []):
        rng = pr.get("range", {})
        if "startRowIndex" not in rng and "startColumnIndex" not in rng:
            return True
    return False


def _get_writer_emails(
    file_id: str, build_drive_service_fn=_build_drive_service
) -> list[str]:
    """ファイルの編集者(writer/owner)のメールアドレス一覧を取得する。

    「リンクを知っている全員」(type=anyone)権限は対象外。シート保護の編集者リストは
    名前付きユーザーのみ指定可能なため、これがGoogle Sheets UI上の「編集者を選択」で
    デフォルト全選択した場合と同じ一覧になる(2026-09-18、№01で実機確認した挙動を再現)。
    """
    perms = call_with_reauth(
        build_drive_service_fn,
        lambda svc: svc.permissions()
        .list(
            fileId=file_id,
            fields="permissions(emailAddress,role,type)",
            supportsAllDrives=True,
        )
        .execute(),
    )
    return sorted(
        {
            p["emailAddress"]
            for p in perms.get("permissions", [])
            if p.get("role") in ("writer", "owner")
            and p.get("type") in ("user", "serviceAccount")
            and p.get("emailAddress")
        }
    )


def plan_protect_request(sheet_id: int, editor_emails: list[str]) -> dict:
    return {
        "addProtectedRange": {
            "protectedRange": {
                "range": {"sheetId": sheet_id},
                "editors": {"users": editor_emails},
                "description": (
                    "個人情報保護・誤操作防止(クライアント要望2026-09-12対応、"
                    "hide_sensitive_sheets.pyで自動適用)"
                ),
            }
        }
    }


def plan_hide_request(sheet_props: dict) -> dict | None:
    if sheet_props.get("hidden", False):
        return None
    return {
        "updateSheetProperties": {
            "properties": {"sheetId": sheet_props["sheetId"], "hidden": True},
            "fields": "hidden",
        }
    }


def _batch_update(
    spreadsheet_id: str, requests: list[dict], build_service_fn=_build_sheets_service
) -> None:
    call_with_reauth(
        build_service_fn,
        lambda svc: svc.spreadsheets()
        .batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests})
        .execute(),
    )


def plan_roster_requests(sheet_entry: dict, editor_emails: list[str]) -> list[dict]:
    """「受講者リスト」タブ用のbatchUpdateリクエストを組み立てる(非表示化+列非表示+保護)。"""
    sheet_props = sheet_entry["properties"]
    sheet_id = sheet_props["sheetId"]
    requests = []
    hide_req = plan_hide_request(sheet_props)
    if hide_req:
        requests.append(hide_req)
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
    if not _is_whole_sheet_protected(sheet_entry):
        requests.append(plan_protect_request(sheet_id, editor_emails))
    return requests


def plan_task1_requests(sheet_props: dict) -> list[dict]:
    """課題①提出記録シート(参照元)側の「課題①」タブ用リクエスト(非表示化のみ)。

    このタブはcarewell-automation-saには編集権限がなく(anyone:readerのみの共有設定)、
    保護対象は`{No}_受講者リスト_出欠管理`ファイル側(plan_destination_task1_requests)。
    """
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


def plan_destination_task1_requests(
    sheet_entry: dict, editor_emails: list[str]
) -> list[dict]:
    """`{No}_受講者リスト_出欠管理`ファイル自身の「課題①」タブ(IMPORTRANGE配線先)用リクエスト。

    課題①提出記録シート側の「課題①」タブ(plan_task1_requests対象)とは別ファイルの別タブ。
    Step 2(数式配線)実施時にこのタブが新規作成されるため、対象は非表示化+保護。
    """
    sheet_props = sheet_entry["properties"]
    sheet_id = sheet_props["sheetId"]
    requests = []
    hide_req = plan_hide_request(sheet_props)
    if hide_req:
        requests.append(hide_req)
    if not _is_whole_sheet_protected(sheet_entry):
        requests.append(plan_protect_request(sheet_id, editor_emails))
    return requests


def process_class(class_num: str, commit: bool, backup_dir: Path) -> dict:
    result = {"class": class_num, "roster": None, "task1": None, "dest_task1": None}

    # --- 「受講者リスト」タブ + `{No}_受講者リスト_出欠管理`ファイル自身の「課題①」タブ ---
    # 同一ファイル内の2タブなので、シート一覧・編集者一覧は1回の取得で両方に使い回す。
    # API呼び出し全体を1つのtry/exceptで保護する。8クラスを順次処理するため、
    # 1クラスでの例外(権限不足・一時的なAPIエラー等)が他クラスの処理や
    # manifest.json書き込みまで止めてしまわないようにする。
    try:
        attendance_id = resolve_attendance_spreadsheet_id(class_num)
        full_sheets = _get_full_sheets_list(attendance_id)
        roster_sheet = _find_sheet_entry(full_sheets, ROSTER_TARGET_TAB)
        dest_task1_sheet = _find_sheet_entry(full_sheets, TASK1_TAB_NAME)
        editor_emails = (
            _get_writer_emails(attendance_id)
            if (roster_sheet is not None or dest_task1_sheet is not None)
            else []
        )

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
            requests = plan_roster_requests(roster_sheet, editor_emails)
            if not commit:
                result["roster"] = {
                    "status": "dry-run",
                    "spreadsheet_id": attendance_id,
                    "before_hidden": roster_sheet["properties"].get("hidden", False),
                    "already_protected": _is_whole_sheet_protected(roster_sheet),
                    "planned_requests": len(requests),
                }
            elif not requests:
                result["roster"] = {
                    "status": "already_applied",
                    "spreadsheet_id": attendance_id,
                }
            else:
                _batch_update(attendance_id, requests)
                after_sheets = _get_full_sheets_list(attendance_id)
                after_sheet = _find_sheet_entry(after_sheets, ROSTER_TARGET_TAB)
                result["roster"] = {
                    "status": "applied",
                    "spreadsheet_id": attendance_id,
                    "after_hidden": (
                        after_sheet["properties"].get("hidden", False)
                        if after_sheet
                        else None
                    ),
                    "after_protected": (
                        _is_whole_sheet_protected(after_sheet)
                        if after_sheet
                        else None
                    ),
                }

        # --- `{No}_受講者リスト_出欠管理`ファイル自身の「課題①」タブ(IMPORTRANGE配線先) ---
        # Step 2(数式配線)実施時に新規作成される。課題①提出記録シート側(下のtask1処理)とは別物。
        if dest_task1_sheet is None:
            result["dest_task1"] = {
                "status": "skipped",
                "detail": f"「{TASK1_TAB_NAME}」タブが未作成(spreadsheet_id={attendance_id})",
            }
        else:
            backup_path = backup_dir / f"class{class_num}_dest_task1_before.json"
            backup_path.write_text(
                json.dumps(dest_task1_sheet, ensure_ascii=False, indent=2)
            )
            requests = plan_destination_task1_requests(dest_task1_sheet, editor_emails)
            if not commit:
                result["dest_task1"] = {
                    "status": "dry-run",
                    "spreadsheet_id": attendance_id,
                    "before_hidden": dest_task1_sheet["properties"].get(
                        "hidden", False
                    ),
                    "already_protected": _is_whole_sheet_protected(dest_task1_sheet),
                    "planned_requests": len(requests),
                }
            elif not requests:
                result["dest_task1"] = {
                    "status": "already_applied",
                    "spreadsheet_id": attendance_id,
                }
            else:
                _batch_update(attendance_id, requests)
                after_sheets = _get_full_sheets_list(attendance_id)
                after_sheet = _find_sheet_entry(after_sheets, TASK1_TAB_NAME)
                result["dest_task1"] = {
                    "status": "applied",
                    "spreadsheet_id": attendance_id,
                    "after_hidden": (
                        after_sheet["properties"].get("hidden", False)
                        if after_sheet
                        else None
                    ),
                    "after_protected": (
                        _is_whole_sheet_protected(after_sheet)
                        if after_sheet
                        else None
                    ),
                }
    except Exception as e:  # noqa: BLE001
        if result["roster"] is None:
            result["roster"] = {"status": "error", "detail": str(e)}
        if result["dest_task1"] is None:
            result["dest_task1"] = {"status": "error", "detail": str(e)}

    # --- 「課題①」タブ ---
    task1_id = TASK1_SUBMISSION_SPREADSHEET_IDS.get(class_num)
    if task1_id is None:
        result["task1"] = {"status": "skipped", "detail": "spreadsheet_id未登録"}
    else:
        try:
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
                    result["task1"] = {
                        "status": "already_hidden",
                        "spreadsheet_id": task1_id,
                    }
                else:
                    _batch_update(
                        task1_id,
                        requests,
                        build_service_fn=_build_task1_sheets_service,
                    )
                    after_props_list = _get_sheet_properties_list(
                        task1_id, build_service_fn=_build_task1_sheets_service
                    )
                    after_sheet = _find_sheet(after_props_list, TASK1_TAB_NAME)
                    result["task1"] = {
                        "status": "applied",
                        "spreadsheet_id": task1_id,
                        "after_hidden": (
                            after_sheet.get("hidden", False) if after_sheet else None
                        ),
                    }
        except Exception as e:  # noqa: BLE001
            result["task1"] = {"status": "error", "detail": str(e)}

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--commit",
        action="store_true",
        help="実際に非表示化を適用する(省略時はdry-run)",
    )
    parser.add_argument(
        "--class",
        dest="class_num",
        default=None,
        help="対象クラスを1件に限定する場合に指定(例: 01)。省略時は対象8クラス全件",
    )
    args = parser.parse_args()

    if args.class_num and args.class_num not in TARGET_CLASSES:
        print(
            f"[エラー] クラス{args.class_num}は対象外です。"
            f"本スクリプトの対象はTARGET_CLASSES={TARGET_CLASSES}のみです。"
        )
        return 1

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
        print(f"  受講者リスト        : {result['roster']}")
        print(f"  課題①(提出記録シート): {result['task1']}")
        print(f"  課題①(出欠管理ファイル): {result['dest_task1']}")

    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2))
    print(f"\n[結果一覧] {manifest_path}")

    if not args.commit:
        print("\n[DRY-RUN] --commitが指定されていないため変更は行いませんでした。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
