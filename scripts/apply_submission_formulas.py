#!/usr/bin/env python3
"""
{No}_受講者リスト_出欠管理 の「{No}_出欠確認」シートへ、課題①の提出/未提出を
自動表示する数式(IMPORTRANGE + XLOOKUP + COUNTIF)を、検証ゲート付きで書き込む。

クラス№01で行ってきた連携作業(docs/class-rollout-runbook.md)を、全クラスで
同じ結果になるよう再現するためのスクリプト。手作業・使い捨てコードを残さない。

使い方:
    python scripts/apply_submission_formulas.py --class 03            # dry-run
    python scripts/apply_submission_formulas.py --class 03 --commit   # 実書き込み
    python scripts/apply_submission_formulas.py --class 03 --commit \\
        --provision-submission-tab   # 提出記録シート側「課題①」タブを事前作成する

終了コード: 0=成功(dry-run含む) / 1=検証失敗・エラー / 2=保留(提出記録側に「課題①」
タブが無く、--provision-submission-tab も未指定)

認証: 出欠管理側は carewell-automation-sa(閲覧+出欠管理ファイル編集)、提出記録側は
github-actions-sa(Cloud Run実行SAと同一、提出記録シートの編集権限を持つ)を権限借用する。
出力は件数・判定のみ。氏名等のPIIは一切出力しない。
"""

import argparse
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from googleapiclient.errors import HttpError  # noqa: E402

from scripts.hide_sensitive_sheets import (  # noqa: E402
    TARGET_CLASSES,
    TASK1_SUBMISSION_SPREADSHEET_IDS,
    _build_task1_sheets_service,
)
from scripts.merge_student_roster import (  # noqa: E402
    EXPECTED_STUDENT_COUNT_BY_CLASS,
    ROSTER_TARGET_TAB,
    ValidationError,
    _build_sheets_service,
    resolve_attendance_spreadsheet_id,
)
from src.gcp_sa_auth import call_with_reauth  # noqa: E402

TASK_LABEL = "課題①"
HEADER_ROW = 4  # 出欠確認シートの見出し行(「課題①」「課題②」等が並ぶ行)
FIRST_STUDENT_ROW = 5
ATTENDANCE_NUMBER_COL = "C"  # 受講者番号列
MAX_ROW = 500

# 提出記録シートの見出し。src/sheets_service.py の _ensure_headers と同一(8列)。
SUBMISSION_HEADER = [
    "課題ID",
    "複合キー",
    "氏名",
    "日介番号",
    "提出日",
    "ファイル名",
    "ファイルURL",
    "ダウンロード日時",
]

# クラス№01で稼働中の式と同一(tests/unit/test_apply_submission_formulas.py で固定)
XLOOKUP_FORMULA = (
    "=ArrayFormula(XLOOKUP(B:B,'受講者リスト'!C:C,'受講者リスト'!J:J,\"\"))"
)

# 名簿(受講者リスト)の列位置(0-indexed、C列起点で読む)
ROSTER_NICHIKAI_IDX = 0  # C列 日介番号
ROSTER_NUMBER_IDX = 7  # J列 受講者番号

# 提出記録シート側の日介番号列(D列、2行目〜)
SUBMISSION_NICHIKAI_COL = "D"
SUBMISSION_READ_CAP = 5000  # 読取り上限行。到達したら独立集計が過小になるため失敗にする

_ERROR_MARKERS = ("#REF", "#ERROR", "#N/A", "#VALUE", "#NAME", "#DIV")
_CONNECT_MARKERS = ("connect these sheets", "接続する必要")
_STUDENT_NUMBER_LIKE = re.compile(r"[A-Zー]\d{3}")
_VALID_STATUSES = ("提出", "未提出")


# ---------------------------------------------------------------------------
# 純粋関数(ユニットテスト対象)
# ---------------------------------------------------------------------------


def build_import_formula(submission_spreadsheet_id: str) -> str:
    return f'=IMPORTRANGE("{submission_spreadsheet_id}","{TASK_LABEL}!C:D")'


def build_status_formula(row: int) -> str:
    return (
        f'=IF(C{row}="","",IF(COUNTIF(\'{TASK_LABEL}\'!C:C,C{row})=0,'
        f'"未提出","提出"))'
    )


def col_letter(idx: int) -> str:
    """0-indexed列番号をA1記法の列文字に変換する"""
    n = idx + 1
    letters = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def find_task_column(header_row: list, label: str = TASK_LABEL) -> int:
    """見出し行から課題①列を特定する(0-indexed)。0件・複数件は異常として中断する。

    I列決め打ちにしない: 同じ見出し行に課題②が並び、クラスごとに列位置が
    変わりうるため。
    """
    hits = [i for i, v in enumerate(header_row) if str(v).strip() == label]
    if len(hits) != 1:
        raise ValidationError(
            f"見出し行{HEADER_ROW}行目に「{label}」が{len(hits)}件あります(1件である必要があります)"
        )
    return hits[0]


def classify_cell(current, expected: str) -> str:
    """既存セルの値を期待値と比較する: empty / same / conflict"""
    if current is None or str(current).strip() == "":
        return "empty"
    return "same" if str(current) == expected else "conflict"


def validate_number_mapping(
    attendance_numbers: list[str], roster_numbers: list[str]
) -> list[str]:
    """出欠確認シートと受講者リストの受講者番号が一対一で対応しているか検証する"""
    issues = []
    if len(attendance_numbers) != len(set(attendance_numbers)):
        issues.append("出欠確認シートの受講者番号に重複があります")
    if len(roster_numbers) != len(set(roster_numbers)):
        issues.append("受講者リストの受講者番号に重複があります")
    att, ros = set(attendance_numbers), set(roster_numbers)
    missing = ros - att
    extra = att - ros
    if missing:
        issues.append(
            f"受講者リストにあり出欠確認に存在しない番号が{len(missing)}件あります"
        )
    if extra:
        issues.append(
            f"出欠確認にあり受講者リストに存在しない番号が{len(extra)}件あります"
        )
    return issues


def select_student_rows(
    number_col_values: list[list],
    roster_numbers: set[str],
    first_row: int = FIRST_STUDENT_ROW,
) -> list[int]:
    """受講者番号列から、名簿に存在する番号の行(シート行番号)だけを選ぶ。

    見出し行・空行・名簿外の値は対象外。正規表現ではなく検証済み名簿との照合で決める。
    """
    rows = []
    for i, cell in enumerate(number_col_values):
        value = str(cell[0]).strip() if cell else ""
        if value and value in roster_numbers:
            rows.append(first_row + i)
    return rows


def plan_attendance_writes(existing: dict[int, str], student_rows: list[int]) -> dict:
    """課題①列への書込み計画を作る。既存の異なる入力は上書きせず衝突として返す。"""
    writes, conflicts, same = [], [], 0
    for row in student_rows:
        formula = build_status_formula(row)
        kind = classify_cell(existing.get(row, ""), formula)
        if kind == "empty":
            writes.append((row, formula))
        elif kind == "same":
            same += 1
        else:
            conflicts.append(row)
    return {"writes": writes, "same": same, "conflicts": conflicts}


def independent_submitted_count(
    submission_nichikai: list[str], roster_nichikai: set[str]
) -> int:
    """提出記録シート側の独立集計: ユニーク日介番号 ∩ 名簿 の件数"""
    unique = {str(v).strip() for v in submission_nichikai if str(v).strip()}
    return len(unique & roster_nichikai)


def verify_results(
    statuses: list[str], n_students: int, independent_submitted: int
) -> list[str]:
    """書込み後の検証: エラーなし・件数一致・独立集計一致"""
    issues = []
    errors = [s for s in statuses if str(s).startswith("#")]
    if errors:
        issues.append(f"課題①列にエラーセルが{len(errors)}件あります")
    unexpected = [s for s in statuses if s not in _VALID_STATUSES and s not in errors]
    if unexpected:
        issues.append(
            f"課題①列に「提出」「未提出」以外の値が{len(unexpected)}件あります"
        )
    judged = [s for s in statuses if s in _VALID_STATUSES]
    if len(statuses) != n_students or len(judged) != n_students:
        issues.append(
            f"判定された行数({len(judged)})が受講者行数({n_students})と一致しません"
        )
    submitted = sum(1 for s in statuses if s == "提出")
    if submitted != independent_submitted:
        issues.append(
            f"「提出」件数({submitted})が独立集計({independent_submitted})と一致しません"
        )
    return issues


def import_cell_has_error(value) -> bool:
    """IMPORTRANGEセルがエラー/接続未許可の表示になっていないか"""
    if value is None:
        return False
    text = str(value)
    return any(m in text for m in _ERROR_MARKERS) or any(
        m in text for m in _CONNECT_MARKERS
    )


def validate_submission_header(values: list[list]) -> list[str]:
    """提出記録側「課題①」タブのA1:H1がシステムの見出しと一致するか"""
    if not values or not values[0]:
        return ["提出記録側「課題①」タブの見出し行(A1:H1)が空です"]
    if [str(v) for v in values[0]] != SUBMISSION_HEADER:
        return ["提出記録側「課題①」タブの見出しがシステムの定義と一致しません"]
    return []


def check_row_cap(rows: list, cap: int = SUBMISSION_READ_CAP - 1) -> None:
    """読取り上限に達した場合、独立集計が過小になるため中断する"""
    if len(rows) >= cap:
        raise ValidationError(
            f"提出記録シートの読取り行数が上限({cap}行)に達しました。"
            "SUBMISSION_READ_CAPの引き上げが必要です(独立集計が過小になります)"
        )


def build_provision_requests(sheet_id: int, header: list[str]) -> list[dict]:
    """タブ作成と見出し書込みを1回のbatchUpdateで原子的に行うリクエスト"""
    return [
        {
            "addSheet": {
                "properties": {"sheetId": sheet_id, "title": TASK_LABEL, "hidden": True}
            }
        },
        {
            "updateCells": {
                "rows": [
                    {
                        "values": [
                            {"userEnteredValue": {"stringValue": h}} for h in header
                        ]
                    }
                ],
                "fields": "userEnteredValue",
                "start": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 0},
            }
        },
    ]


# ---------------------------------------------------------------------------
# API呼び出し層
# ---------------------------------------------------------------------------


def _scratch_dir() -> Path:
    """backupの出力先(プロジェクトローカル、gitignore済み)。ホーム配下には書かない。"""
    return PROJECT_ROOT / "var" / "scratch" / "apply_submission_formulas"


def _get_values(build_fn, spreadsheet_id: str, range_: str, render="FORMATTED_VALUE"):
    return call_with_reauth(
        build_fn,
        lambda svc: svc.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_, valueRenderOption=render)
        .execute(),
    ).get("values", [])


def _list_titles(build_fn, spreadsheet_id: str) -> list[str]:
    meta = call_with_reauth(
        build_fn,
        lambda svc: svc.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets.properties.title")
        .execute(),
    )
    return [s["properties"]["title"] for s in meta.get("sheets", [])]


def _batch_update(build_fn, spreadsheet_id: str, requests: list[dict]):
    return call_with_reauth(
        build_fn,
        lambda svc: svc.spreadsheets()
        .batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests})
        .execute(),
    )


def _update_values(build_fn, spreadsheet_id: str, range_: str, values, raw=False):
    return call_with_reauth(
        build_fn,
        lambda svc: svc.spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=range_,
            valueInputOption="RAW" if raw else "USER_ENTERED",
            body={"values": values},
        )
        .execute(),
    )


def provision_submission_tab(submission_id: str) -> str:
    """提出記録側に非表示の「課題①」タブを見出しつきで作る。

    Cloud Run(毎時、_ensure_sheet_exists/_ensure_headers)と同時に動いても壊さない:
    タブ作成と見出しは1回のbatchUpdateで原子的に行い、「既に存在」で失敗した場合は
    読み直して見出し一致を確認して続行する(二重作成・上書きはしない)。
    """
    sheet_id = random.randint(10**8, 2**31 - 2)
    try:
        _batch_update(
            _build_task1_sheets_service,
            submission_id,
            build_provision_requests(sheet_id, SUBMISSION_HEADER),
        )
        outcome = "created"
    except HttpError as e:
        if "already exists" not in str(e):
            raise
        outcome = "already_exists"
        header = _get_values(
            _build_task1_sheets_service, submission_id, f"'{TASK_LABEL}'!A1:H1"
        )
        if not header or not header[0]:
            # システムがタブだけ作って見出し書込み前の状態。システムと同じ内容を書く。
            _update_values(
                _build_task1_sheets_service,
                submission_id,
                f"'{TASK_LABEL}'!A1:H1",
                [SUBMISSION_HEADER],
                raw=True,
            )
    readback = _get_values(
        _build_task1_sheets_service, submission_id, f"'{TASK_LABEL}'!A1:H1"
    )
    issues = validate_submission_header(readback)
    if issues:
        raise ValidationError("; ".join(issues))
    return outcome


def process_class(class_num: str, commit: bool, provision: bool) -> int:
    expected = EXPECTED_STUDENT_COUNT_BY_CLASS.get(class_num)
    if expected is None:
        print(
            f"[保留] クラス{class_num}は期待人数が未登録です"
            "(merge_student_roster.pyの名簿取込みが先です)"
        )
        return 2

    att_id = resolve_attendance_spreadsheet_id(class_num)
    sub_id = TASK1_SUBMISSION_SPREADSHEET_IDS[class_num]
    att_tab = f"№{class_num}_出欠確認"

    # 1. 事前ゲート: 名簿
    roster = _get_values(
        _build_sheets_service, att_id, f"'{ROSTER_TARGET_TAB}'!C2:J{MAX_ROW}"
    )
    roster = [r + [""] * (8 - len(r)) for r in roster if any(str(c).strip() for c in r)]
    roster_numbers = [r[ROSTER_NUMBER_IDX].strip() for r in roster]
    roster_nichikai = {r[ROSTER_NICHIKAI_IDX].strip() for r in roster}
    if len(roster_numbers) != expected:
        raise ValidationError(
            f"受講者リストの件数({len(roster_numbers)})が期待人数({expected})と一致しません"
        )

    # 出欠確認シート: 課題①列の特定と受講者番号の対応検証
    header = _get_values(
        _build_sheets_service, att_id, f"'{att_tab}'!A{HEADER_ROW}:AZ{HEADER_ROW}"
    )
    task_idx = find_task_column(header[0] if header else [])
    task_col = col_letter(task_idx)
    number_col = _get_values(
        _build_sheets_service,
        att_id,
        f"'{att_tab}'!{ATTENDANCE_NUMBER_COL}{FIRST_STUDENT_ROW}:{ATTENDANCE_NUMBER_COL}{MAX_ROW}",
    )
    roster_set = set(roster_numbers)
    att_numbers = [
        str(c[0]).strip()
        for c in number_col
        if c
        and (
            str(c[0]).strip() in roster_set
            or _STUDENT_NUMBER_LIKE.fullmatch(str(c[0]).strip())
        )
    ]
    issues = validate_number_mapping(att_numbers, roster_numbers)
    if issues:
        raise ValidationError("事前ゲート失敗: " + "; ".join(issues))
    student_rows = select_student_rows(number_col, roster_set)

    # 2. 提出記録側の「課題①」タブ
    sub_titles = _list_titles(_build_sheets_service, sub_id)
    need_provision = False
    if TASK_LABEL not in sub_titles:
        if not provision:
            print(
                f"[保留] クラス{class_num}: 提出記録側に「{TASK_LABEL}」タブがありません。"
                "最初の提出を待つか、--provision-submission-tab で事前作成してください。"
            )
            return 2
        # 作成は、管理側の検証・計画がすべて通った後(--commit時)に行う
        need_provision = True
        print(f"[計画] 提出記録側に非表示の「{TASK_LABEL}」タブを作成予定")
    else:
        hdr = _get_values(_build_sheets_service, sub_id, f"'{TASK_LABEL}'!A1:H1")
        issues = validate_submission_header(hdr)
        if issues:
            raise ValidationError("; ".join(issues))
        check_row_cap(
            _get_values(
                _build_sheets_service,
                sub_id,
                f"'{TASK_LABEL}'!{SUBMISSION_NICHIKAI_COL}2:{SUBMISSION_NICHIKAI_COL}{SUBMISSION_READ_CAP}",
            )
        )

    # 3. 書込み計画
    att_titles = _list_titles(_build_sheets_service, att_id)
    admin_tab_exists = TASK_LABEL in att_titles
    a1_expected = build_import_formula(sub_id)
    existing_a1 = existing_c1 = ""
    if admin_tab_exists:
        a1 = _get_values(_build_sheets_service, att_id, f"'{TASK_LABEL}'!A1", "FORMULA")
        c1 = _get_values(_build_sheets_service, att_id, f"'{TASK_LABEL}'!C1", "FORMULA")
        existing_a1 = a1[0][0] if a1 and a1[0] else ""
        existing_c1 = c1[0][0] if c1 and c1[0] else ""
    a1_kind = classify_cell(existing_a1, a1_expected)
    c1_kind = classify_cell(existing_c1, XLOOKUP_FORMULA)
    if "conflict" in (a1_kind, c1_kind):
        raise ValidationError(
            f"管理側「{TASK_LABEL}」タブのA1/C1に期待と異なる既存入力があります"
            f"(A1={a1_kind}, C1={c1_kind})。上書きせず中断します。"
        )
    existing_col = _get_values(
        _build_sheets_service,
        att_id,
        f"'{att_tab}'!{task_col}{FIRST_STUDENT_ROW}:{task_col}{MAX_ROW}",
        "FORMULA",
    )
    existing = {
        FIRST_STUDENT_ROW + i: (r[0] if r else "") for i, r in enumerate(existing_col)
    }
    plan = plan_attendance_writes(existing, student_rows)
    if plan["conflicts"]:
        raise ValidationError(
            f"課題①列に期待と異なる既存入力が{len(plan['conflicts'])}行あります。"
            "自動修正せず中断します(式の生値・参照先・計算結果を比較して原因を分類してください)。"
        )

    print(
        f"[計画] クラス{class_num}: 受講者{len(student_rows)}行 / 課題①列={task_col}列 / "
        f"書込み{len(plan['writes'])}行・同一式{plan['same']}行・衝突0 / "
        f"管理側タブ={'既存' if admin_tab_exists else '新規作成'}"
        f"(A1:{a1_kind}, C1:{c1_kind})"
    )
    if not commit:
        print("[DRY-RUN] --commitが指定されていないため書き込みは行いません。")
        return 0

    # 4. 提出記録側タブの事前作成(管理側の検証・計画がすべて通った後) → バックアップ → 書込み
    if need_provision:
        outcome = provision_submission_tab(sub_id)
        print(f"[提出記録側タブ] {outcome}(見出し一致を読み戻しで確認)")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = _scratch_dir() / ts
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup_path = backup_dir / f"class{class_num}_before.json"
    fd = os.open(backup_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(
            {
                "task_col": task_col,
                "attendance_column_before": existing_col,
                "admin_A1_before": existing_a1,
                "admin_C1_before": existing_c1,
            },
            f,
            ensure_ascii=False,
        )
    print(f"[バックアップ] {backup_path}")

    if not admin_tab_exists:
        _batch_update(
            _build_sheets_service,
            att_id,
            [{"addSheet": {"properties": {"title": TASK_LABEL, "hidden": True}}}],
        )
    if a1_kind == "empty":
        _update_values(
            _build_sheets_service, att_id, f"'{TASK_LABEL}'!A1", [[a1_expected]]
        )
    if c1_kind == "empty":
        _update_values(
            _build_sheets_service, att_id, f"'{TASK_LABEL}'!C1", [[XLOOKUP_FORMULA]]
        )
    if plan["writes"]:
        call_with_reauth(
            _build_sheets_service,
            lambda svc: svc.spreadsheets()
            .values()
            .batchUpdate(
                spreadsheetId=att_id,
                body={
                    "valueInputOption": "USER_ENTERED",
                    "data": [
                        {"range": f"'{att_tab}'!{task_col}{row}", "values": [[formula]]}
                        for row, formula in plan["writes"]
                    ],
                },
            )
            .execute(),
        )

    # 5. 事後検証(IMPORTRANGEの再計算を待つため、最大3回まで間隔を空けて再確認する)
    for attempt in range(3):
        time.sleep(5)
        problems = []
        import_cells = _get_values(
            _build_sheets_service, att_id, f"'{TASK_LABEL}'!A1:B1"
        )
        if any(import_cell_has_error(v) for row in import_cells for v in row):
            problems.append(
                "管理側「課題①」のIMPORTRANGEがエラー/接続未許可です"
                "(シート上で「アクセスを許可」を1回押す必要があります)"
            )
        col_after = _get_values(
            _build_sheets_service,
            att_id,
            f"'{att_tab}'!{task_col}{FIRST_STUDENT_ROW}:{task_col}{MAX_ROW}",
        )
        statuses = [
            (
                col_after[r - FIRST_STUDENT_ROW][0]
                if r - FIRST_STUDENT_ROW < len(col_after)
                and col_after[r - FIRST_STUDENT_ROW]
                else ""
            )
            for r in student_rows
        ]
        sub_after = _get_values(
            _build_sheets_service,
            sub_id,
            f"'{TASK_LABEL}'!{SUBMISSION_NICHIKAI_COL}2:{SUBMISSION_NICHIKAI_COL}{SUBMISSION_READ_CAP}",
        )
        check_row_cap(sub_after)
        independent = independent_submitted_count(
            [r[0] for r in sub_after if r], roster_nichikai
        )
        problems += verify_results(statuses, len(student_rows), independent)
        if not problems:
            break
        if attempt < 2:
            print(
                f"[再確認] 検証未通過のため再計算を待って再確認します({attempt + 2}/3)"
            )
    submitted = sum(1 for s in statuses if s == "提出")
    print(
        f"[検証] 提出{submitted} / 未提出{sum(1 for s in statuses if s == '未提出')} / "
        f"独立集計(ユニーク提出者∩名簿)={independent} / 判定対象{len(student_rows)}行"
    )
    if problems:
        for p in problems:
            print(f"[検証失敗] {p}")
        return 1
    print("[成功] 事後検証をすべて通過しました。")
    print(
        "[注意] 独立集計は提出記録シート由来のため、収集漏れ(Firestoreの"
        "sheets_sync_status=failed等)は検出できません。"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--class", dest="class_num", required=True, help="対象クラス(例: 03)"
    )
    parser.add_argument(
        "--commit", action="store_true", help="実際に書き込む(省略時はdry-run)"
    )
    parser.add_argument(
        "--provision-submission-tab",
        action="store_true",
        help="提出記録側に「課題①」タブが無い場合、非表示で事前作成する(--commit時のみ実行)",
    )
    args = parser.parse_args()
    if args.class_num not in TARGET_CLASSES:
        print(f"[エラー] クラス{args.class_num}は対象外です(対象: {TARGET_CLASSES})")
        return 1
    try:
        return process_class(args.class_num, args.commit, args.provision_submission_tab)
    except ValidationError as e:
        print(f"[中断] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
