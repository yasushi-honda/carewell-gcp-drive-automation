#!/usr/bin/env python3
"""
課題の「収集から表示まで」の4段突合を、1コマンドで行う(読み取り専用)。

クラスNN・課題Xについて、次を並べて一致を確かめる(docs/class-rollout-runbook.md 手順5):
  1. ポータルの件数 = Cloud Run の取得件数   (最新の収集ログの `Count verification`)
  2. Cloud Run の取得件数 = 提出記録シートの行数
  3. Firestore の file_count = 提出記録シートの行数
  4. 提出記録に複合キーの重複なし
  5. 出欠確認の「提出」件数 = 提出記録のユニーク提出者(名簿内)

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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.apply_submission_formulas import (  # noqa: E402
    SUBMISSION_READ_CAP,
    _build_sheets_service,
    _get_values,
    check_row_cap,
)
from scripts.check_collection_status import (  # noqa: E402
    OUTCOME_ZERO,
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

NAME_PORTAL = "ポータルの件数 = Cloud Run の取得件数"
NAME_ROWS = "Cloud Run の取得件数 = 提出記録の行数"
NAME_FIRESTORE = "Firestore の file_count = 提出記録の行数"
NAME_DUPS = "提出記録に複合キーの重複なし"
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


def compare_stages(s: dict) -> list[dict]:
    """4段突合の各比較を判定する。取得できなかった値は「確定できない」(一致とは扱わない)。"""
    results = [
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
        results.append(
            {
                "name": NAME_DUPS,
                "status": STATUS_PASS if dups == 0 else STATUS_FAIL,
                "detail": f"重複 {dups}",
                "hint": "" if dups == 0 else "同じ複合キーの行が複数ある(重複追記)",
            }
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


def fetch_sheet_rows(class_no: str, task: str) -> tuple[int | None, int | None]:
    """提出記録シートの課題タブの (データ行数, 複合キー重複数)。タブが読めなければ (None, None)。"""
    sub_id = TASK1_SUBMISSION_SPREADSHEET_IDS[class_no]
    try:
        values = _get_values(
            _build_sheets_service, sub_id, f"'{task}'!A2:H{SUBMISSION_READ_CAP}"
        )
    except Exception:  # noqa: BLE001 タブ未作成・権限など。一致とは扱わない
        return None, None
    check_row_cap(values)
    rows = [r for r in values if any(str(c).strip() for c in r)]
    keys = [str(r[1]).strip() for r in rows if len(r) > 1 and str(r[1]).strip()]
    return len(rows), len(keys) - len(set(keys))


def fetch_firestore_file_count(class_no: str, task: str) -> int | None:
    """Firestoreの課題の親ドキュメントの file_count。取得できなければ None。"""
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
        return int(next(iter(fields["file_count"].values())))
    except urllib.error.HTTPError as e:
        # 親ドキュメントが無い(404)=まだ1件も記録されていない
        return 0 if e.code == 404 else None
    except Exception:  # noqa: BLE001
        return None


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
        sheet_rows, key_dups = fetch_sheet_rows(args.class_num, args.task)
        facts = gather_facts(args.class_num, args.task)
    except Exception as e:  # noqa: BLE001 取得失敗は「一致」にしない
        print(f"[取得失敗] {type(e).__name__}: {str(e)[:200]}")
        return 2

    if summary["outcome"] == OUTCOME_ZERO:
        portal_total = extracted = 0
    else:
        portal_total, extracted = summary.get("total"), summary.get("extracted")

    results = compare_stages(
        {
            "collect_outcome": summary["outcome"],
            "portal_total": portal_total,
            "extracted": extracted,
            "sheet_rows": sheet_rows,
            "key_dups": key_dups,
            "firestore_count": fetch_firestore_file_count(args.class_num, args.task),
            "submitted_display": facts.get("_submitted"),
            "independent": facts.get("_independent"),
        }
    )
    started = summary.get("started") or "-"
    print(f"[収集] 直近の実行: {summary['outcome']}(開始 {started})")
    print(render(args.class_num, args.task, results))
    return exit_code(results)


if __name__ == "__main__":
    sys.exit(main())
