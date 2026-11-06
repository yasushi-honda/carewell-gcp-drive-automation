"""
出欠確認表の課題列に直接入力された値(講義中の手入力など)を検出し、数式へ戻す。

背景: 課題列は数式(IMPORTRANGE+XLOOKUP+COUNTIF)で提出状況を表示するが、現場では
講義中にその場で「提出」と入力されることがある。数式のセルに値を直接入れると、その
受講者の表示は自動で更新されなくなる。`check_rollout_status.py` はこれを「数式未設定」
と表示し、`apply_submission_formulas.py` は既存の異なる入力を上書きせず中断する
(2026-10-29の№01・№04、2026-11-06の№04・№05で発生)。クライアントには入力を止めて
もらわず、こちらで引き受ける。

このスクリプトは、読取り専用の検出と、バックアップ付きの復元を行う。
- 数式に戻す対象は、内容が「提出」または「未提出」だけのセル(手入力の典型)。
- それ以外の内容(メモ、別の数式など)は自動で上書きせず、行番号だけ報告する。
- 氏名・日介番号は出力しない(行番号と内容の区分のみ)。
- 書込み前: 管理側の課題タブとその連携(A1のIMPORTRANGE・C1のXLOOKUP)が期待どおりか確認し、
  読取り直後にセルが変わっていないか再確認する。満たさなければ何も書かない。
- 書込み後: 全対象セルが期待の数式と完全一致し、表示が手入力の元の値と同じであることを確認する。
  食い違えば失敗として報告する(バックアップから元の内容を確認できる)。

使い方:
    python scripts/restore_manual_cells.py                       # 全クラスを検出(dry-run)
    python scripts/restore_manual_cells.py --class 04            # 1クラスを検出
    python scripts/restore_manual_cells.py --class 04 --commit   # 数式へ戻す(バックアップ付き)
    python scripts/restore_manual_cells.py --class 04 --task 課題②

終了コード:
    0 = 手入力なし、または検出した手入力をすべて数式へ戻せた
    1 = 要確認(dry-runで検出あり / 戻せるセルがない / 前提(管理側タブ・連携)が整っていない /
        読取り後にセルが変わった / 戻した後に「提出/未提出」以外のメモ等が残っている)
    2 = 失敗(書込み後の検証が失敗、書込み後の例外、取得失敗、走査対象の行が0件)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import apply_submission_formulas as a  # noqa: E402

RESTORABLE_LITERALS = ("提出", "未提出")
DISPLAY_CHECK_ATTEMPTS = 3
DISPLAY_CHECK_WAIT_SEC = 5


def classify_manual_cells(
    existing: dict[int, str], student_rows: list[int], label: str = a.TASK_LABEL
) -> dict:
    """課題列の手入力を、数式へ戻せるもの(restorable)と、そうでないもの(other)に分ける。

    restorable: 内容が「提出」または「未提出」だけのセル。(行, 内容)の一覧。
    other: 空でも期待の数式でもなく、restorableでもないセルの行番号。
    student_rows以外の行は無視する。結果は行番号の昇順。
    """
    restorable: list[tuple[int, str]] = []
    other: list[int] = []
    for row in sorted(student_rows):
        value = existing.get(row, "")
        kind = a.classify_cell(value, a.build_status_formula(row, label))
        if kind != "conflict":
            continue
        text = str(value).strip()
        if text in RESTORABLE_LITERALS:
            restorable.append((row, text))
        else:
            other.append(row)
    return {"restorable": restorable, "other": other}


def find_unrestored(
    after: dict[int, str], target_rows: list[int], label: str = a.TASK_LABEL
) -> list[int]:
    """復元の読み戻し検証: 対象の全行が、期待の数式と完全一致していることを確かめる。

    空・手入力・メモ・別の数式・行の欠落のいずれも「戻っていない」として返す(行番号の昇順)。
    """
    return sorted(
        row
        for row in target_rows
        if str(after.get(row, "")) != a.build_status_formula(row, label)
    )


def find_unexpected_display(
    displayed: dict[int, str], target_rows: list[int]
) -> list[int]:
    """復元後の表示値の検証: 対象の全行が「提出」または「未提出」を表示していること。

    エラー値(#REF!など)・空・読込み中・行の欠落は「期待外」として返す(行番号の昇順)。
    """
    return sorted(
        row
        for row in target_rows
        if str(displayed.get(row, "")).strip() not in RESTORABLE_LITERALS
    )


def find_display_mismatch(
    displayed: dict[int, str], originals: list[tuple[int, str]]
) -> list[int]:
    """復元後の表示が、手入力の元の値と同じかを行ごとに比べる。食い違う行番号(昇順)を返す。

    管理側の連携が正しければ、手入力が提出記録と合っている限り一致する。食い違うのは、
    手入力が提出記録と違う(紙での提出など)か、連携が壊れているとき。
    """
    return sorted(
        row
        for row, original in originals
        if str(displayed.get(row, "")).strip() != original
    )


def task_tab_wiring_issues(
    a1, c1, submission_id: str, label: str = a.TASK_LABEL
) -> list[str]:
    """管理側の課題タブのA1(IMPORTRANGE)・C1(XLOOKUP)が期待どおりかを検証する。問題の一覧を返す。"""
    issues = []
    if a.classify_cell(a1, a.build_import_formula(submission_id, label)) != "same":
        issues.append("A1(IMPORTRANGE)が期待と異なる、または空です")
    if a.classify_cell(c1, a.XLOOKUP_FORMULA) != "same":
        issues.append("C1(XLOOKUP)が期待と異なる、または空です")
    return issues


def _submission_id(class_num: str) -> str:
    return a.TASK1_SUBMISSION_SPREADSHEET_IDS[class_num]


def _read_task_tab_a1c1(att_id: str, label: str):
    """管理側の課題タブのA1・C1(数式)を読む。読取りのみ。"""
    a1 = a._get_values(a._build_sheets_service, att_id, f"'{label}'!A1", "FORMULA")
    c1 = a._get_values(a._build_sheets_service, att_id, f"'{label}'!C1", "FORMULA")
    return (
        a1[0][0] if a1 and a1[0] else "",
        c1[0][0] if c1 and c1[0] else "",
    )


def _read_displayed(att_id: str, att_tab: str, task_col: str) -> dict[int, str]:
    """課題列の表示値(計算結果)を読む。読取りのみ。"""
    col = a._get_values(
        a._build_sheets_service,
        att_id,
        f"'{att_tab}'!{task_col}{a.FIRST_STUDENT_ROW}:{task_col}{a.MAX_ROW}",
    )
    return {a.FIRST_STUDENT_ROW + i: (r[0] if r else "") for i, r in enumerate(col)}


def _read_state(class_num: str, label: str):
    """課題列の現在値(FORMULA)と受講者行を読む。読取りのみ。"""
    att_id = a.resolve_attendance_spreadsheet_id(class_num)
    att_tab = f"№{class_num}_出欠確認"
    roster = a._get_values(
        a._build_sheets_service, att_id, f"'{a.ROSTER_TARGET_TAB}'!C2:J{a.MAX_ROW}"
    )
    roster = [r + [""] * (8 - len(r)) for r in roster if any(str(c).strip() for c in r)]
    roster_set = {r[a.ROSTER_NUMBER_IDX].strip() for r in roster}
    header = a._get_values(
        a._build_sheets_service, att_id, f"'{att_tab}'!A{a.HEADER_ROW}:AZ{a.HEADER_ROW}"
    )
    task_col = a.col_letter(a.find_task_column(header[0] if header else [], label))
    number_col = a._get_values(
        a._build_sheets_service,
        att_id,
        f"'{att_tab}'!{a.ATTENDANCE_NUMBER_COL}{a.FIRST_STUDENT_ROW}:{a.ATTENDANCE_NUMBER_COL}{a.MAX_ROW}",
    )
    student_rows = a.select_student_rows(number_col, roster_set)
    col = a._get_values(
        a._build_sheets_service,
        att_id,
        f"'{att_tab}'!{task_col}{a.FIRST_STUDENT_ROW}:{task_col}{a.MAX_ROW}",
        "FORMULA",
    )
    existing = {a.FIRST_STUDENT_ROW + i: (r[0] if r else "") for i, r in enumerate(col)}
    return att_id, att_tab, task_col, student_rows, existing


def _write_backup(
    class_num: str, label: str, att_id: str, att_tab: str, task_col: str, cells
) -> Path:
    """書込み前のバックアップ(行番号と手入力の内容のみ。0600、fsync済み)。"""
    backup_dir = a._scratch_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    path = backup_dir / (
        f"restore_manual_cells_class{class_num}_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    )
    body = {
        "class": class_num,
        "task": label,
        "spreadsheet_id": att_id,
        "tab": att_tab,
        "column": task_col,
        "cells": [{"row": r, "before": v} for r, v in cells],
    }
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    return path


def _describe_error(e: Exception) -> str:
    """例外を、氏名を含まない形で説明する(型名と、HttpErrorならstatusのみ)。"""
    status = getattr(getattr(e, "resp", None), "status", None)
    return f"{type(e).__name__}" + (f"(HTTP {status})" if status else "")


def process_class(class_num: str, label: str, commit: bool) -> int:
    att_id, att_tab, task_col, student_rows, existing = _read_state(class_num, label)
    if not student_rows:
        print(
            f"№{class_num} {label}: 走査対象の受講者行が0件です(名簿・受講者番号列の読取りを確認してください)"
        )
        return 2
    result = classify_manual_cells(existing, student_rows, label)
    restorable, other = result["restorable"], result["other"]
    if not restorable and not other:
        print(f"№{class_num} {label}: 手入力なし")
        return 0
    for row, text in restorable:
        print(f"№{class_num} {label}: {task_col}{row} に手入力「{text}」(数式へ戻せる)")
    for row in other:
        print(
            f"№{class_num} {label}: {task_col}{row} に手入力(「提出」「未提出」以外。"
            "自動では戻さない。内容を確認してください)"
        )
    if not commit:
        print("[DRY-RUN] --commit が指定されていないため書き込みは行いません。")
        return 1
    if not restorable:
        print("[保留] 数式へ戻せるセルがありません。")
        return 1

    # 書込み前の前提確認。数式は管理側の課題タブ(IMPORTRANGE+XLOOKUP)を参照する。
    # 未連携のまま戻すと、エラー表示や、全員「未提出」の誤表示になる。
    if label not in a._list_titles(a._build_sheets_service, att_id):
        print(
            f"[保留] 管理側に「{label}」タブがないため、数式へ戻しません。先に "
            f"apply_submission_formulas.py --class {class_num} --task {label} で連携してください。"
        )
        return 1
    issues = task_tab_wiring_issues(
        *_read_task_tab_a1c1(att_id, label), _submission_id(class_num), label
    )
    if issues:
        print(
            f"[保留] 管理側「{label}」タブの連携が整っていないため、数式へ戻しません: "
            + "; ".join(issues)
            + f"。先に apply_submission_formulas.py --class {class_num} --task {label} で連携してください。"
        )
        return 1

    # 読取りから書込みまでの間に人が編集した場合に、別の内容を上書きしない。
    _, _, _, _, existing_again = _read_state(class_num, label)
    if classify_manual_cells(existing_again, student_rows, label) != result:
        print("[保留] 読取り後にセルが変更されました。何も書いていません。もう一度実行してください。")
        return 1

    backup = _write_backup(class_num, label, att_id, att_tab, task_col, restorable)
    print(f"[バックアップ] {backup}")
    targets = [r for r, _ in restorable]
    try:
        a._write_status_formulas(
            att_id,
            att_tab,
            task_col,
            [(row, a.build_status_formula(row, label)) for row in targets],
        )
        # 読み戻し: 復元した全行が期待の数式と完全一致していること
        _, _, _, _, after = _read_state(class_num, label)
        unrestored = find_unrestored(after, targets, label)
        if unrestored:
            print(
                f"[失敗] 復元後に期待の数式になっていない行があります: 行 {unrestored}"
                f"。バックアップ: {backup}"
            )
            return 2
        # 表示: IMPORTRANGEの再計算待ちを考慮して最大3回確認する
        displayed: dict[int, str] = {}
        for attempt in range(DISPLAY_CHECK_ATTEMPTS):
            displayed = _read_displayed(att_id, att_tab, task_col)
            if not find_unexpected_display(displayed, targets):
                break
            if attempt < DISPLAY_CHECK_ATTEMPTS - 1:
                time.sleep(DISPLAY_CHECK_WAIT_SEC)
        bad = find_unexpected_display(displayed, targets)
        if bad:
            print(
                f"[失敗] 数式へ戻した後の表示が「提出/未提出」になっていない行があります: 行 {bad}"
                f"。バックアップ: {backup}"
            )
            return 2
        changed = find_display_mismatch(displayed, restorable)
        if changed:
            print(
                f"[失敗] 数式へ戻した後の表示が、手入力の元の値と食い違う行があります: 行 {changed}"
                "(手入力が提出記録と違うか、連携が壊れている可能性)。元の内容はバックアップで確認できます: "
                f"{backup}"
            )
            return 2
    except Exception as e:  # 書込み後の例外: 書込み済みであることを明示する
        print(
            f"[書込み済み・検証未完了] {_describe_error(e)}。シートは変更されている可能性があります。"
            f"バックアップ: {backup}。`check_rollout_status.py --class {class_num}` で状態を確認してください。"
        )
        return 2
    print(
        f"[成功] {len(restorable)}件を数式へ戻しました(表示は手入力と一致)。"
        f"`check_rollout_status.py --class {class_num}` で「完了」を確認してください。"
    )
    return 1 if other else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--class", dest="class_num", help="対象クラス(例: 04)。省略時は全クラスを検出のみ"
    )
    parser.add_argument("--task", choices=a.TASK_LABELS, default=a.TASK_LABEL)
    parser.add_argument(
        "--commit", action="store_true", help="実際に数式へ戻す(--class が必要)"
    )
    args = parser.parse_args()
    if args.commit and not args.class_num:
        print("[エラー] --commit には --class が必要です(1クラスずつ実行します)")
        return 1
    classes = [args.class_num] if args.class_num else list(a.TARGET_CLASSES)
    if args.class_num and args.class_num not in a.TARGET_CLASSES:
        print(f"[エラー] クラス{args.class_num}は対象外です(対象: {a.TARGET_CLASSES})")
        return 1
    rc = 0
    for cn in classes:
        try:
            rc = max(rc, process_class(cn, args.task, args.commit))
        except Exception as e:  # クラス単位で失敗を示し、他クラスの検出は続ける
            print(f"№{cn} {args.task}: 取得失敗({_describe_error(e)})")
            rc = max(rc, 2)
    return rc


if __name__ == "__main__":
    sys.exit(main())
