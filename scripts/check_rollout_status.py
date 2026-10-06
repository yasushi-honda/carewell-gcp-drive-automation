#!/usr/bin/env python3
"""
全クラスの「出欠確認表への課題提出連携」の進捗を、読み取り専用で確認する。

クラスごとに、名簿・出欠確認との整合・提出記録側/管理側の「課題①」タブ・数式・
非表示/保護の状態を集め、次のアクションを表示する(運用手順:
docs/class-rollout-runbook.md)。

使い方:
    python scripts/check_rollout_status.py             # 全対象クラス
    python scripts/check_rollout_status.py --class 03  # 1クラスのみ

終了コード: 0=すべて「完了」または「予定された保留」 / 1=「要対応」「退行・検証失敗」あり
出力は件数・判定のみ。氏名等のPIIは一切出力しない。

限界: 独立集計は提出記録シート由来のため、収集漏れ(Firestoreの
sheets_sync_status=failed/pending)は検出できない。
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.apply_submission_formulas import (  # noqa: E402
    FIRST_STUDENT_ROW,
    HEADER_ROW,
    MAX_ROW,
    ROSTER_NUMBER_IDX,
    SUBMISSION_NICHIKAI_COL,
    SUBMISSION_READ_CAP,
    TASK_LABEL,
    XLOOKUP_FORMULA,
    _get_values,
    _list_titles,
    build_import_formula,
    build_status_formula,
    check_row_cap,
    classify_cell,
    col_letter,
    find_task_column,
    import_cell_has_error,
    independent_submitted_count,
    select_student_rows,
    validate_number_mapping,
    verify_results,
)
from scripts.hide_sensitive_sheets import (  # noqa: E402
    TARGET_CLASSES,
    TASK1_SUBMISSION_SPREADSHEET_IDS,
    _find_sheet_entry,
    _get_full_sheets_list,
    _is_whole_sheet_protected,
)
from scripts.merge_student_roster import (  # noqa: E402
    EXPECTED_STUDENT_COUNT_BY_CLASS,
    ROSTER_TARGET_TAB,
    _build_sheets_service,
    normalize_key,
    resolve_attendance_spreadsheet_id,
)

STATE_DONE = "完了"
STATE_HOLD = "予定された保留"
STATE_TODO = "要対応"
STATE_REGRESSION = "退行・検証失敗"
# 正本リストが取込み後に更新された(情報的な差分)。数式・集計の退行ではないため終了コードは0。
STATE_REVIEW = "要確認(名簿差分)"

_NUMBER_ROW_PATTERN_COLS = 7  # 正本リストのA〜G列


# ---------------------------------------------------------------------------
# 純粋関数(ユニットテスト対象)
# ---------------------------------------------------------------------------


def _norm_group(value: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFKC", str(value)).strip()


def compare_source_to_roster(
    source_rows: list[list], roster_rows: list[list]
) -> list[str]:
    """正本リスト(クライアント入力)と取込み済みの受講者リストを番号ごとに比較する。

    取込み後にクライアントが名簿・グループ分けを更新した場合の検出用。
    メッセージに氏名等は含めない(件数のみ)。
    正本: A=グループ, C=受講者番号, D=氏名, E=ふりがな, F=サービス種別
    名簿: A=氏名, B=ふりがな, F=サービス種別, H=グループ, J=受講者番号
    """
    src = {}
    for r in source_rows:
        r = list(r) + [""] * (_NUMBER_ROW_PATTERN_COLS - len(r))
        number = str(r[2]).strip()
        if number:
            src[number] = (
                _norm_group(r[0]),
                normalize_key(str(r[3]), str(r[4])),
                str(r[5]).strip(),
            )
    ros = {}
    for r in roster_rows:
        r = list(r) + [""] * (10 - len(r))
        number = str(r[9]).strip()
        if number:
            ros[number] = (
                _norm_group(r[7]),
                normalize_key(str(r[0]), str(r[1])),
                str(r[5]).strip(),
            )
    issues = []
    only_src = set(src) - set(ros)
    only_ros = set(ros) - set(src)
    if only_src:
        issues.append(f"正本にあり名簿に無い受講者番号が{len(only_src)}件")
    if only_ros:
        issues.append(f"名簿にあり正本に無い受講者番号が{len(only_ros)}件")
    both = set(src) & set(ros)
    changed = [n for n in both if src[n][:2] != ros[n][:2]]
    if changed:
        issues.append(f"グループまたは氏名が取込み後に変わった受講者が{len(changed)}件")
    service = [n for n in both if src[n][2] != ros[n][2]]
    if service:
        issues.append(f"サービス種別が取込み後に変わった受講者が{len(service)}件")
    return issues


def classify_class(f: dict) -> tuple[str, str]:
    """クラスの状態と次のアクションを返す。退行 > 要対応 > 保留 > 完了 の優先順。"""
    cn = f["class"]
    if f["roster_count"] > 0:
        if f["mapping_issues"]:
            return (
                STATE_REGRESSION,
                "出欠確認と受講者リストの受講者番号が不一致: "
                + "; ".join(f["mapping_issues"]),
            )
        expected = f.get("expected_count")
        if expected is not None and f["roster_count"] != expected:
            return (
                STATE_REGRESSION,
                f"受講者リストの件数({f['roster_count']})が期待人数({expected})と不一致",
            )
        if f.get("link_issues"):
            return (
                STATE_REGRESSION,
                "管理側の連携が壊れている: "
                + "; ".join(f["link_issues"])
                + f" → apply_submission_formulas.py --class {cn} (dry-run)で確認",
            )
        if f["tally_issues"]:
            return STATE_REGRESSION, "検証失敗: " + "; ".join(f["tally_issues"])

    if f["roster_count"] == 0:
        if f["source_count"] > 0:
            return (
                STATE_TODO,
                f"正本リストは入力済み。merge_student_roster.py --class {cn} を実行",
            )
        return STATE_HOLD, "名簿データ待ち(正本リスト未入力)"

    if not f["expected_registered"]:
        return (
            STATE_TODO,
            "EXPECTED_STUDENT_COUNT_BY_CLASS に期待人数を登録(人間確認のうえ)",
        )

    if not f["sub_task_tab"]:
        return (
            STATE_TODO,
            f"提出記録側に「{TASK_LABEL}」タブなし → apply_submission_formulas.py "
            f"--class {cn} --commit --provision-submission-tab、または最初の提出を待つ",
        )

    if f["formulas"] != "all" or not f["admin_task_tab"]:
        return (
            STATE_TODO,
            f"数式未設定 → apply_submission_formulas.py --class {cn} --commit",
        )

    missing = []
    if not f["sub_hidden"]:
        missing.append("提出記録側の課題①が非表示でない")
    if not (f["admin_hidden"] and f["admin_protected"]):
        missing.append("管理側の課題①が非表示+保護でない")
    if not (f["roster_hidden"] and f["roster_protected"]):
        missing.append("受講者リストが非表示+保護でない")
    if missing:
        return (
            STATE_TODO,
            "; ".join(missing) + f" → hide_sensitive_sheets.py --class {cn} --commit",
        )
    if f["source_issues"]:
        return (
            STATE_REVIEW,
            "正本リストが取込み後に更新された: "
            + "; ".join(f["source_issues"])
            + f" → 差分を確認し、再取込み(merge_student_roster.py --class {cn})の要否を判断",
        )
    if f.get("_submitted") == 0:
        return (
            STATE_DONE,
            "設定完了。提出0件のため、最初の実提出後に収集〜表示(提出者数＝「提出」件数)を確認",
        )
    return STATE_DONE, "-"


def exit_code(states: list[str]) -> int:
    """「予定された保留」「要確認(名簿差分)」だけなら0。要対応・退行があれば1。

    情報的な差分や予定された待ちで毎回異常にしない(本物の退行を埋もれさせない)。
    """
    return 1 if any(s in (STATE_TODO, STATE_REGRESSION) for s in states) else 0


# ---------------------------------------------------------------------------
# API呼び出し層
# ---------------------------------------------------------------------------


def _hidden_and_protected(full_sheets: list[dict], title: str) -> tuple[bool, bool]:
    entry = _find_sheet_entry(full_sheets, title)
    if entry is None:
        return False, False
    return (
        bool(entry["properties"].get("hidden", False)),
        _is_whole_sheet_protected(entry),
    )


def gather_facts(class_num: str) -> dict:
    att_id = resolve_attendance_spreadsheet_id(class_num)
    sub_id = TASK1_SUBMISSION_SPREADSHEET_IDS[class_num]
    att_tab = f"№{class_num}_出欠確認"

    source = _get_values(
        _build_sheets_service, att_id, f"'№{class_num}リスト'!A2:G{MAX_ROW}"
    )
    source = [r for r in source if any(str(c).strip() for c in r)]
    source_count = sum(1 for r in source if len(r) > 2 and str(r[2]).strip())
    roster = _get_values(
        _build_sheets_service, att_id, f"'{ROSTER_TARGET_TAB}'!A2:J{MAX_ROW}"
    )
    roster = [r for r in roster if any(str(c).strip() for c in r)]
    roster_numbers = [
        str(r[ROSTER_NUMBER_IDX + 2]).strip()
        for r in roster
        if len(r) > ROSTER_NUMBER_IDX + 2 and str(r[ROSTER_NUMBER_IDX + 2]).strip()
    ]
    facts = {
        "class": class_num,
        "expected_registered": class_num in EXPECTED_STUDENT_COUNT_BY_CLASS,
        "expected_count": EXPECTED_STUDENT_COUNT_BY_CLASS.get(class_num),
        "link_issues": [],
        "source_count": source_count,
        "roster_count": len(roster_numbers),
        "mapping_issues": [],
        "source_issues": [],
        "tally_issues": [],
        "sub_task_tab": False,
        "admin_task_tab": False,
        "formulas": "none",
        "sub_hidden": False,
        "admin_hidden": False,
        "admin_protected": False,
        "roster_hidden": False,
        "roster_protected": False,
    }
    if not roster_numbers:
        return facts

    roster_set = set(roster_numbers)
    number_col = _get_values(
        _build_sheets_service,
        att_id,
        f"'{att_tab}'!C{FIRST_STUDENT_ROW}:C{MAX_ROW}",
    )
    import re

    att_numbers = [
        str(c[0]).strip()
        for c in number_col
        if c
        and (
            str(c[0]).strip() in roster_set
            or re.fullmatch(r"[A-Zー]\d{3}", str(c[0]).strip())
        )
    ]
    facts["mapping_issues"] = validate_number_mapping(att_numbers, roster_numbers)
    if source:
        facts["source_issues"] = compare_source_to_roster(source, roster)

    att_full = _get_full_sheets_list(att_id, _build_sheets_service)
    sub_full = _get_full_sheets_list(
        sub_id, _build_sheets_service
    )  # 読取りは閲覧SAで足りる
    facts["roster_hidden"], facts["roster_protected"] = _hidden_and_protected(
        att_full, ROSTER_TARGET_TAB
    )
    facts["admin_hidden"], facts["admin_protected"] = _hidden_and_protected(
        att_full, TASK_LABEL
    )
    facts["admin_task_tab"] = _find_sheet_entry(att_full, TASK_LABEL) is not None
    facts["sub_task_tab"] = _find_sheet_entry(sub_full, TASK_LABEL) is not None
    facts["sub_hidden"], _ = _hidden_and_protected(sub_full, TASK_LABEL)

    header = _get_values(
        _build_sheets_service, att_id, f"'{att_tab}'!A{HEADER_ROW}:AZ{HEADER_ROW}"
    )
    task_col = col_letter(find_task_column(header[0] if header else []))
    student_rows = select_student_rows(number_col, roster_set)
    col = _get_values(
        _build_sheets_service,
        att_id,
        f"'{att_tab}'!{task_col}{FIRST_STUDENT_ROW}:{task_col}{MAX_ROW}",
        "FORMULA",
    )
    same = sum(
        1
        for r in student_rows
        if r - FIRST_STUDENT_ROW < len(col)
        and col[r - FIRST_STUDENT_ROW]
        and col[r - FIRST_STUDENT_ROW][0] == build_status_formula(r)
    )
    facts["formulas"] = (
        "all"
        if same == len(student_rows) and same > 0
        else "partial" if same else "none"
    )

    if facts["admin_task_tab"]:
        a1 = _get_values(_build_sheets_service, att_id, f"'{TASK_LABEL}'!A1", "FORMULA")
        c1 = _get_values(_build_sheets_service, att_id, f"'{TASK_LABEL}'!C1", "FORMULA")
        shown_import = _get_values(
            _build_sheets_service, att_id, f"'{TASK_LABEL}'!A1:B1"
        )
        a1_val = a1[0][0] if a1 and a1[0] else ""
        c1_val = c1[0][0] if c1 and c1[0] else ""
        if classify_cell(a1_val, build_import_formula(sub_id)) != "same":
            facts["link_issues"].append("A1が期待のIMPORTRANGE式でない")
        if classify_cell(c1_val, XLOOKUP_FORMULA) != "same":
            facts["link_issues"].append("C1が期待のXLOOKUP式でない")
        if any(import_cell_has_error(v) for row in shown_import for v in row):
            facts["link_issues"].append("IMPORTRANGEがエラー/接続未許可")

    if facts["formulas"] == "all" and facts["sub_task_tab"] and facts["admin_task_tab"]:
        shown = _get_values(
            _build_sheets_service,
            att_id,
            f"'{att_tab}'!{task_col}{FIRST_STUDENT_ROW}:{task_col}{MAX_ROW}",
        )
        statuses = [
            (
                shown[r - FIRST_STUDENT_ROW][0]
                if r - FIRST_STUDENT_ROW < len(shown) and shown[r - FIRST_STUDENT_ROW]
                else ""
            )
            for r in student_rows
        ]
        sub_rows = _get_values(
            _build_sheets_service,
            sub_id,
            f"'{TASK_LABEL}'!{SUBMISSION_NICHIKAI_COL}2:{SUBMISSION_NICHIKAI_COL}{SUBMISSION_READ_CAP}",
        )
        check_row_cap(sub_rows)
        nichikai = {str(r[2]).strip() for r in roster if len(r) > 2}
        independent = independent_submitted_count(
            [r[0] for r in sub_rows if r], nichikai
        )
        facts["tally_issues"] = verify_results(statuses, len(student_rows), independent)
        facts["_submitted"] = sum(1 for s in statuses if s == "提出")
        facts["_unsubmitted"] = sum(1 for s in statuses if s == "未提出")
    return facts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--class", dest="class_num", default=None, help="対象クラスを1件に限定"
    )
    args = parser.parse_args()
    if args.class_num and args.class_num not in TARGET_CLASSES:
        print(f"[エラー] クラス{args.class_num}は対象外です(対象: {TARGET_CLASSES})")
        return 1
    classes = [args.class_num] if args.class_num else TARGET_CLASSES

    states = []
    print("クラス | 状態 | 正本 | 名簿 | 提出/未提出 | 次のアクション")
    for cn in classes:
        try:
            facts = gather_facts(cn)
            state, action = classify_class(facts)
            counts = (
                f"{facts['_submitted']}/{facts['_unsubmitted']}"
                if "_submitted" in facts
                else "-"
            )
            print(
                f"№{cn} | {state} | {facts['source_count']} | {facts['roster_count']} "
                f"| {counts} | {action}"
            )
        except Exception as e:  # 取得失敗は退行として扱い、他クラスの確認は続ける
            state, action = STATE_REGRESSION, f"取得失敗: {type(e).__name__}"
            print(f"№{cn} | {state} | - | - | - | {action}")
        states.append(state)

    print(
        "\n[限界] 提出/未提出は出欠確認の表示値。独立集計は提出記録シート由来のため、"
        "収集漏れ(Firestore sheets_sync_status=failed等)は検出できません。"
    )
    return exit_code(states)


if __name__ == "__main__":
    sys.exit(main())
