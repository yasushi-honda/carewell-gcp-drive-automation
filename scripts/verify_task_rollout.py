#!/usr/bin/env python3
"""
課題の「収集から表示まで」の4段突合を、1コマンドで行う(読み取り専用)。

クラスNN・課題Xについて、次を並べて一致を確かめる(docs/class-rollout-runbook.md 手順5):
  0. 最新の収集に異常なし(ERROR・件数不一致・未完了・課題が見つからない、は一致とは扱わない)
  1. ポータルの件数 = Cloud Run の取得件数   (最新の収集ログの `Count verification`)
  2. Cloud Run の取得件数 = 提出記録シートの行数
  3. Firestore の file_count = 提出記録シートの行数
  4. 提出記録に複合キーの重複なし
  5. 提出記録の提出者は全員名簿内(日介番号の空欄・名簿外の行は、両側の集計から外れて
     一致してしまうため、別に検出する)
  6. 出欠確認の「提出」件数 = 提出記録のユニーク提出者(名簿内)

使い方:
    .venv/bin/python scripts/verify_task_rollout.py --class 01 --task 課題②
    .venv/bin/python scripts/verify_task_rollout.py --class 01 --task 課題② --hours 12

終了コード: 0=全段が一致 / 1=食い違いあり / 2=確定できない(最新の収集が未完了、Firestore等を
取得できない、数式未設定など。「一致」とは扱わない)

注意:
  - 同じ受講者が複数回提出すると、行数は増えるが提出者は1名のまま(1〜3は行数、5は人数で比べる)。
  - 新しい提出の直後は、最新の収集より後の提出で1〜3が食い違ったり、IMPORTRANGEの再計算待ちで
    5が1件少なく見えたりする。数十秒〜数分後に再実行してから原因を調べる。
  - ポータルの件数は、収集コードが画面から読んだ値(人が画面で数えた値の代わり)。
出力は件数と判定のみ。氏名・日介番号・ログの原文は出さない。
"""

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.apply_submission_formulas import (  # noqa: E402
    SUBMISSION_READ_CAP,
    _build_sheets_service,
    _get_values,
    check_row_cap,
)
from scripts.check_collection_status import (  # noqa: E402
    OUTCOME_ABORTED,
    OUTCOME_ERROR,
    OUTCOME_MISMATCH,
    OUTCOME_OK,
    OUTCOME_ZERO,
    count_unattributed_errors,
    fetch_events,
    summarize,
)
from scripts.check_rollout_status import gather_facts  # noqa: E402
from scripts.hide_sensitive_sheets import (  # noqa: E402
    TARGET_CLASSES,
    TASK1_SUBMISSION_SPREADSHEET_IDS,
    TASK_TAB_NAMES,
)
from src.config.classes import (  # noqa: E402
    KNOWN_CLASSES,
    resolve_firestore_database_id,
)

PROJECT = "carewell-automation"

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_UNKNOWN = "UNKNOWN"

NAME_COLLECT = "最新の収集に異常なし"
NAME_PORTAL = "ポータルの件数 = Cloud Run の取得件数"
NAME_ROWS = "Cloud Run の取得件数 = 提出記録の行数"
NAME_FIRESTORE = "Firestore の file_count = 提出記録の行数"
NAME_DUPS = "提出記録に複合キーの重複・空欄なし"
NAME_MEMBERS = "提出記録の提出者は全員名簿内(日介番号の空欄・名簿外なし)"
NAME_DISPLAY = "出欠確認の「提出」件数 = 提出記録のユニーク提出者(名簿内)"


# ---------------------------------------------------------------------------
# 純粋関数(ユニットテスト対象)
# ---------------------------------------------------------------------------


def _compare(name: str, a, b, fail_hint: str, unknown_hint: str) -> dict:
    if a is None or b is None:
        return {
            "name": name,
            "status": STATUS_UNKNOWN,
            "detail": f"{a} / {b}",
            "hint": unknown_hint,
        }
    if a == b:
        return {"name": name, "status": STATUS_PASS, "detail": f"{a} = {b}", "hint": ""}
    return {
        "name": name,
        "status": STATUS_FAIL,
        "detail": f"{a} ≠ {b}",
        "hint": fail_hint,
    }


def _collect_stage(
    outcome: str,
    overlap: bool,
    repeated_unfinished: bool = False,
    unattributed_errors: int = 0,
) -> dict:
    """最新の収集に異常がないか。件数が揃っていても、ERROR・件数不一致・重なった実行・
    クラス/課題を特定できないERRORがあれば、一致(PASS)とは扱わない。"""
    note = "(手動実行と定期実行が重なった可能性あり)" if overlap else ""
    if outcome == OUTCOME_ABORTED and repeated_unfinished:
        return {
            "name": NAME_COLLECT,
            "status": STATUS_FAIL,
            "detail": outcome + "(繰り返し)",
            "hint": "毎回、課題ページに着く前に中断している(曖昧一致・task_patternの誤り・例外)。ログを確認",
        }
    if outcome in (OUTCOME_OK, OUTCOME_ZERO):
        if overlap:
            return {
                "name": NAME_COLLECT,
                "status": STATUS_UNKNOWN,
                "detail": outcome + note,
                "hint": "実行が重なり、片方の結果が他方に混ざった可能性がある。次の実行の後に再実行",
            }
        if unattributed_errors:
            return {
                "name": NAME_COLLECT,
                "status": STATUS_UNKNOWN,
                "detail": f"{outcome}(この実行以降に帰属不明のERROR {unattributed_errors}件)",
                "hint": "ダウンロード失敗・保存/同期の失敗など、クラス・課題を特定できないERROR。"
                "他のクラスのものかもしれない。ログを手で確認",
            }
        return {
            "name": NAME_COLLECT,
            "status": STATUS_PASS,
            "detail": outcome,
            "hint": "",
        }
    if outcome == OUTCOME_ERROR:
        return {
            "name": NAME_COLLECT,
            "status": STATUS_FAIL,
            "detail": outcome + note,
            "hint": "収集のログにERROR(ダウンロード失敗・保存/同期の失敗など)。"
            "check_collection_status.pyとログで原因を確認",
        }
    if outcome == OUTCOME_MISMATCH:
        return {
            "name": NAME_COLLECT,
            "status": STATUS_FAIL,
            "detail": outcome + note,
            "hint": "ポータルの件数と取得行数が違った実行がある(収集漏れの可能性)",
        }
    return {
        "name": NAME_COLLECT,
        "status": STATUS_UNKNOWN,
        "detail": outcome + note,
        "hint": "最新の収集が完了していない、課題が見つからない、件数を確認できない、または期間内に実行がない",
    }


def _members_stage(blank, unique_all, independent) -> dict:
    """提出者が全員名簿内か。日介番号の空欄・名簿外の行は、独立集計と出欠確認の両方から外れて
    一致してしまう(その受講者は表示上「未提出」のまま)ため、別に検出する。"""
    if blank is None or unique_all is None:
        return {
            "name": NAME_MEMBERS,
            "status": STATUS_UNKNOWN,
            "detail": "取得不可",
            "hint": "提出記録を読めない",
        }
    if blank:
        return {
            "name": NAME_MEMBERS,
            "status": STATUS_FAIL,
            "detail": f"日介番号が空欄の行 {blank}",
            "hint": "日介番号が空欄の提出行がある(その受講者は出欠確認で「未提出」のまま)",
        }
    if independent is None:
        return {
            "name": NAME_MEMBERS,
            "status": STATUS_UNKNOWN,
            "detail": f"{unique_all} / ?",
            "hint": "名簿内の提出者数を取得できない(連携が未設定)",
        }
    if unique_all != independent:
        return {
            "name": NAME_MEMBERS,
            "status": STATUS_FAIL,
            "detail": f"提出者 {unique_all} / 名簿内 {independent}",
            "hint": "名簿外の日介番号の提出がある(誤入力・別クラス・異動の可能性。その受講者は「未提出」のまま)",
        }
    return {
        "name": NAME_MEMBERS,
        "status": STATUS_PASS,
        "detail": f"{unique_all} = {independent}",
        "hint": "",
    }


def compare_stages(s: dict) -> list[dict]:
    """4段突合の各比較を判定する。取得できなかった値は「確定できない」(一致とは扱わない)。"""
    results = [
        _collect_stage(
            s["collect_outcome"],
            s.get("overlap_suspected", False),
            s.get("repeated_unfinished", False),
            s.get("unattributed_errors", 0),
        ),
        _compare(
            NAME_PORTAL,
            s["portal_total"],
            s["extracted"],
            "収集漏れ(Cloud Runの収集ログを調査)",
            "最新の収集が完了していない、またはログから件数を読めない(次の実行の後に再実行)",
        ),
        _compare(
            NAME_ROWS,
            s["extracted"],
            s["sheet_rows"],
            "Sheets追記の失敗(Firestoreのsheets_sync_status=failedを確認)。"
            "最新の収集より後に新しい提出が入った場合も食い違う(再実行)",
            "取得件数または提出記録の行数を読めない",
        ),
        _compare(
            NAME_FIRESTORE,
            s["firestore_count"],
            s["sheet_rows"],
            "FirestoreとSheetsの記録がずれている(sheets_sync_statusを確認)",
            "Firestoreのfile_countを取得できない(権限・ネットワーク)",
        ),
    ]
    dups = s["key_dups"]
    blank_keys = s.get("blank_keys", 0)
    if dups is None:
        results.append(
            {
                "name": NAME_DUPS,
                "status": STATUS_UNKNOWN,
                "detail": "取得不可",
                "hint": "提出記録を読めない",
            }
        )
    else:
        bad = dups > 0 or blank_keys > 0
        results.append(
            {
                "name": NAME_DUPS,
                "status": STATUS_FAIL if bad else STATUS_PASS,
                "detail": f"重複 {dups}・キー空欄 {blank_keys}",
                "hint": (
                    "同じ複合キーの行が複数ある(重複追記)、または複合キーが空欄の行がある"
                    if bad
                    else ""
                ),
            }
        )
    results.append(
        _members_stage(s["blank_nichikai"], s["unique_all"], s["independent"])
    )
    results.append(
        _compare(
            NAME_DISPLAY,
            s["submitted_display"],
            s["independent"],
            "数式・名簿の問題、またはIMPORTRANGEの再計算待ち(数十秒後に再実行してから調べる)",
            "出欠確認の連携が未設定、または読めない(check_rollout_status.pyで確認)",
        )
    )
    return results


def exit_code(results: list[dict]) -> int:
    if any(r["status"] == STATUS_FAIL for r in results):
        return 1
    if any(r["status"] == STATUS_UNKNOWN for r in results):
        return 2
    return 0


def render(class_no: str, task: str, results: list[dict]) -> str:
    lines = [f"№{class_no} {task} の4段突合"]
    for r in results:
        lines.append(f"[{r['status']}] {r['name']}  ({r['detail']})")
        if r["hint"] and r["status"] != STATUS_PASS:
            lines.append(f"        → {r['hint']}")
    return "\n".join(lines)


def find_class_name(class_no: str) -> str:
    for name in KNOWN_CLASSES:
        if name.endswith(f"№{class_no}"):
            return name
    raise ValueError(f"クラス№{class_no}は KNOWN_CLASSES にありません")


# ---------------------------------------------------------------------------
# 取得層
# ---------------------------------------------------------------------------


class SheetRows(NamedTuple):
    rows: int | None
    key_dups: int | None
    unique_nichikai: int | None
    blank_nichikai: int | None
    note: str
    blank_keys: int = 0


def fetch_sheet_rows(class_no: str, task: str) -> SheetRows:
    """提出記録シートの課題タブの、データ行数・複合キーの重複数・ユニーク日介番号数・日介番号が
    空欄の行数。タブが読めなければ値は None(理由を note に残す)。読取り上限に達したら例外。"""
    sub_id = TASK1_SUBMISSION_SPREADSHEET_IDS[class_no]
    try:
        values = _get_values(
            _build_sheets_service, sub_id, f"'{task}'!A2:H{SUBMISSION_READ_CAP}"
        )
    except Exception as e:  # noqa: BLE001 タブ未作成・権限など。一致とは扱わない
        return SheetRows(
            None, None, None, None, f"提出記録を読めない({type(e).__name__})"
        )
    check_row_cap(values)
    rows = [r for r in values if any(str(c).strip() for c in r)]
    keys = [str(r[1]).strip() for r in rows if len(r) > 1 and str(r[1]).strip()]
    nichikai = [str(r[3]).strip() if len(r) > 3 else "" for r in rows]
    return SheetRows(
        len(rows),
        len(keys) - len(set(keys)),
        len({n for n in nichikai if n}),
        sum(1 for n in nichikai if not n),
        "",
        len(rows) - len(keys),
    )


class FirestoreCount(NamedTuple):
    count: int | None
    note: str


def _http_error_message(e: urllib.error.HTTPError) -> str:
    try:
        return str(
            json.loads(e.read().decode() or "{}").get("error", {}).get("message", "")
        )
    except Exception:  # noqa: BLE001
        return ""


def fetch_firestore_file_count(class_no: str, task: str) -> FirestoreCount:
    """Firestoreの課題の親ドキュメントの file_count。取得できなければ count=None(理由を note に)。

    404は「ドキュメント不在」(=まだ記録なし、0件)と確認できたときだけ0とする。データベースや
    パスの誤りも404になるため、それ以外の404は「確定できない」(誤ったDBで0=0が一致しないように)。
    """
    try:
        token = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        ).stdout.strip()
        path = "/".join(
            urllib.parse.quote(p, safe="")
            for p in ["submissions", find_class_name(class_no), "tasks", task]
        )
        url = (
            "https://firestore.googleapis.com/v1/projects/"
            f"{PROJECT}/databases/{resolve_firestore_database_id()}/documents/{path}"
            "?mask.fieldPaths=file_count"
        )
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            fields = json.load(resp).get("fields", {})
    except urllib.error.HTTPError as e:
        if e.code == 404:
            msg = _http_error_message(e)
            if msg.startswith("Document ") and "not found" in msg:
                return FirestoreCount(0, "")
            return FirestoreCount(
                None, "Firestore HTTP 404(データベースまたはパスが違う可能性)"
            )
        return FirestoreCount(None, f"Firestore HTTP {e.code}")
    except Exception as e:  # noqa: BLE001
        return FirestoreCount(None, f"Firestoreを取得できない({type(e).__name__})")
    value = fields.get("file_count", {}).get("integerValue")
    try:
        return FirestoreCount(int(value), "")
    except (TypeError, ValueError):
        return FirestoreCount(None, "file_countを整数として取得できない")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--class", dest="class_num", required=True)
    parser.add_argument("--task", choices=TASK_TAB_NAMES, required=True)
    parser.add_argument("--hours", type=int, default=6, help="収集ログを見る期間(時間)")
    args = parser.parse_args()
    if args.class_num not in TARGET_CLASSES:
        print(f"[エラー] クラス{args.class_num}は対象外です(対象: {TARGET_CLASSES})")
        return 2

    try:
        events = fetch_events(args.hours)
        summary = summarize(
            events, args.class_num, args.task, datetime.now(timezone.utc)
        )
        sheet = fetch_sheet_rows(args.class_num, args.task)
        facts = gather_facts(args.class_num, args.task)
    except Exception as e:  # noqa: BLE001 取得失敗は「一致」にしない
        # 自作の例外(gcloud失敗・ログ上限・読取り上限)だけ文面を出す。それ以外は、URLや
        # スプレッドシートID等を含みうるため、型名だけにする
        detail = f": {str(e)[:200]}" if isinstance(e, RuntimeError) else ""
        print(f"[取得失敗] {type(e).__name__}{detail}")
        return 2

    if summary["outcome"] == OUTCOME_ZERO:
        portal_total = extracted = 0
    else:
        portal_total, extracted = summary.get("total"), summary.get("extracted")

    firestore = fetch_firestore_file_count(args.class_num, args.task)
    # クラス・課題を特定できないERROR(main.pyのダウンロード失敗・保存/同期の失敗など)のうち、
    # この実行の開始以降のもの。他のクラスのものかもしれないので、確定できない扱いにする
    unattributed, _latest = count_unattributed_errors(events, summary.get("started"))
    results = compare_stages(
        {
            "collect_outcome": summary["outcome"],
            "overlap_suspected": summary.get("overlap_suspected", False),
            "repeated_unfinished": summary.get("repeated_unfinished", False),
            "unattributed_errors": unattributed,
            "portal_total": portal_total,
            "extracted": extracted,
            "sheet_rows": sheet.rows,
            "key_dups": sheet.key_dups,
            "blank_keys": sheet.blank_keys,
            "unique_all": sheet.unique_nichikai,
            "blank_nichikai": sheet.blank_nichikai,
            "firestore_count": firestore.count,
            "submitted_display": facts.get("_submitted"),
            "independent": facts.get("_independent"),
        }
    )
    started = summary.get("started") or "-"
    print(f"[収集] 直近の実行: {summary['outcome']}(開始 {started})")
    for note in (sheet.note, firestore.note):
        if note:
            print(f"[取得] {note}")
    print(render(args.class_num, args.task, results))
    return exit_code(results)


if __name__ == "__main__":
    sys.exit(main())
