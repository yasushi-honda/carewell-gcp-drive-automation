#!/usr/bin/env python3
"""
課題の収集(Cloud Run + Cloud Scheduler)の直近の実行結果を、クラス×課題ごとに一覧する。
読み取り専用。ジョブの再開・実行・書込みは一切しない。

使い方:
    python scripts/check_collection_status.py                    # 全対象クラス×課題①②、直近3時間
    python scripts/check_collection_status.py --class 01 --task 課題②
    python scripts/check_collection_status.py --hours 6

見るもの(クラス×課題ごとに、直近の1回の実行だけ):
    OK=Count verification passed / 提出0件を確認 / 課題が見つからない(未作成または
    task_patternの表記違い) / 課題ページに到達せず中断(曖昧一致・例外の可能性) /
    件数不一致 / 件数を確認できない / ERRORあり

課題が見つからない場合も、収集の応答はHTTP 200「未作成」になり、Cloud Schedulerは緑のまま
0件が続く(課題①から続く仕様)。公開済みの課題でこの行が出たら、task_patternを確認する。

終了コード: 0=ENABLEDのジョブに問題なし / 1=ENABLEDのジョブに「中断・不一致・確認不能・
ERROR」がある / 2=ログやジョブ一覧を取得できなかった

出力はログの原文を一切含まない(固定のパターンから取り出した件数・時刻・分類のみ)。
ダウンロード行など氏名を含みうるログは、そもそも取得しない。
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.hide_sensitive_sheets import TARGET_CLASSES, TASK_TAB_NAMES  # noqa: E402

PROJECT = "carewell-automation"
REGION = "asia-northeast1"
SERVICE = "carewell-file-collector"
LOG_LIMIT = 2000
RUNNING_WINDOW_SEC = 600  # 最後のログがこれより新しく、結果が未確定なら「実行中」

OUTCOME_OK = "OK"
OUTCOME_ZERO = "ZERO_CONFIRMED"
OUTCOME_NOT_FOUND = "NOT_FOUND"
OUTCOME_ABORTED = "ABORTED"
OUTCOME_MISMATCH = "MISMATCH"
OUTCOME_UNVERIFIED = "UNVERIFIED"
OUTCOME_ERROR = "ERROR"
OUTCOME_NO_RUN = "NO_RUN"
OUTCOME_RUNNING = "RUNNING"

# ENABLEDのジョブでこの結果なら、終了コード1(要対応)
PROBLEM_OUTCOMES = (
    OUTCOME_ABORTED,
    OUTCOME_MISMATCH,
    OUTCOME_UNVERIFIED,
    OUTCOME_ERROR,
)

_MESSAGES = {
    OUTCOME_OK: "収集OK",
    OUTCOME_ZERO: "提出0件を確認",
    OUTCOME_NOT_FOUND: "課題が見つからない(未作成、または公開済みならtask_patternを確認)",
    OUTCOME_ABORTED: "課題ページに到達せず中断(曖昧一致・例外の可能性。ログを確認)",
    OUTCOME_MISMATCH: "件数不一致(ポータルと取得行数が違う)",
    OUTCOME_UNVERIFIED: "件数を確認できない",
    OUTCOME_ERROR: "ERRORあり",
    OUTCOME_NO_RUN: "対象期間に実行なし",
    OUTCOME_RUNNING: "実行中",
}

_TASK = r"(課題[①②③])"
_PREFIX_RE = re.compile(rf"\[carewell-№(\d+)-{_TASK}\]")
_START_RE = re.compile(
    rf"Starting file collection for class=.*?№(\d+), task_id={_TASK}"
)
_NOT_CREATED_RE = re.compile(rf"not yet created, skipping: .*?№(\d+)/{_TASK}")
_VERIFIED_RE = re.compile(r"Count verification passed: (\d+)/(\d+)")
_MISMATCH_RE = re.compile(r"Extracted (\d+) submissions but UI shows (\d+)")


def _parse_ts(value: str) -> datetime:
    """gcloudのタイムスタンプ(ナノ秒まである)をdatetimeにする。"""
    v = value.rstrip("Z")
    if "." in v:
        head, frac = v.split(".", 1)
        v = f"{head}.{frac[:6]}"
    return datetime.fromisoformat(v).replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 純粋関数(ユニットテスト対象)
# ---------------------------------------------------------------------------


def parse_event(entry: dict) -> dict | None:
    """ログ1件から、クラス・課題・種別・件数だけを取り出す。原文は返さない。"""
    text = entry.get("textPayload") or ""
    ts = entry.get("timestamp", "")
    severity = (entry.get("severity") or "INFO").upper()

    m = _START_RE.search(text)
    if m:
        return {"ts": ts, "class": m.group(1), "task": m.group(2), "kind": "start"}
    m = _NOT_CREATED_RE.search(text)
    if m:
        return {"ts": ts, "class": m.group(1), "task": m.group(2), "kind": "not_found"}
    m = _PREFIX_RE.search(text)
    if not m:
        return None
    base = {"ts": ts, "class": m.group(1), "task": m.group(2)}
    if severity in ("ERROR", "CRITICAL", "ALERT", "EMERGENCY"):
        return {**base, "kind": "error"}
    v = _VERIFIED_RE.search(text)
    if v:
        return {**base, "kind": "verified", "extracted": int(v[1]), "total": int(v[2])}
    mm = _MISMATCH_RE.search(text)
    if mm:
        return {
            **base,
            "kind": "mismatch",
            "extracted": int(mm[1]),
            "total": int(mm[2]),
        }
    if "Could not verify count" in text:
        return {**base, "kind": "unverified"}
    if "Task not found" in text or "Class not found" in text:
        return {**base, "kind": "not_found"}
    if "Selecting task with pattern" in text:
        return {**base, "kind": "selecting"}
    if "Successfully navigated to task page" in text:
        return {**base, "kind": "reached"}
    if "提出されたレポートはありません" in text:
        return {**base, "kind": "zero"}
    return {**base, "kind": "other"}


def summarize(
    events: list[dict | None],
    class_no: str,
    task: str,
    now: datetime | None = None,
) -> dict:
    """指定クラス×課題の「直近の1回の実行」の結果を分類する。"""
    mine = [e for e in events if e and e["class"] == class_no and e["task"] == task]
    if not mine:
        return {"outcome": OUTCOME_NO_RUN, "started": None, "errors": 0}
    mine.sort(key=lambda e: _parse_ts(e["ts"]))
    starts = [i for i, e in enumerate(mine) if e["kind"] == "start"]
    segment = mine[starts[-1] :] if starts else mine
    started = mine[starts[-1]]["ts"] if starts else None
    kinds = {e["kind"] for e in segment}
    errors = sum(1 for e in segment if e["kind"] == "error")

    def last(kind):
        return next((e for e in reversed(segment) if e["kind"] == kind), None)

    result = {"started": started, "errors": errors, "extracted": None, "total": None}
    terminal = last("verified") or last("mismatch")
    if terminal:
        result["extracted"], result["total"] = terminal["extracted"], terminal["total"]

    if errors:
        outcome = OUTCOME_ERROR
    elif "mismatch" in kinds:
        outcome = OUTCOME_MISMATCH
    elif "not_found" in kinds and "reached" not in kinds:
        outcome = OUTCOME_NOT_FOUND
    elif "verified" in kinds:
        outcome = OUTCOME_OK
    elif "zero" in kinds:
        outcome = OUTCOME_ZERO
    elif "unverified" in kinds:
        outcome = OUTCOME_UNVERIFIED
    else:
        outcome = OUTCOME_ABORTED
        if now is not None:
            age = (now - _parse_ts(segment[-1]["ts"])).total_seconds()
            if age < RUNNING_WINDOW_SEC:
                outcome = OUTCOME_RUNNING
    result["outcome"] = outcome
    return result


def render_row(class_no: str, task: str, job_state: str, summary: dict) -> str:
    outcome = summary["outcome"]
    when = "-"
    if summary.get("started"):
        when = _parse_ts(summary["started"]).strftime("%m-%d %H:%M UTC")
    count = "-"
    if summary.get("extracted") is not None:
        count = f"{summary['extracted']}/{summary['total']}"
    note = _MESSAGES[outcome]
    if outcome == OUTCOME_ERROR:
        note = f"ERRORあり({summary.get('errors', 0)}件)"
    if job_state == "PAUSED" and outcome == OUTCOME_NO_RUN:
        note = "ジョブ停止中"
    return f"№{class_no} | {task} | {job_state} | {when} | {count} | {note}"


def exit_code(rows: list[tuple[str, dict]]) -> int:
    """ENABLEDのジョブに問題のある結果があれば1。PAUSEDのジョブは見ない。"""
    return int(
        any(
            state == "ENABLED" and summary["outcome"] in PROBLEM_OUTCOMES
            for state, summary in rows
        )
    )


# ---------------------------------------------------------------------------
# gcloud呼び出し層
# ---------------------------------------------------------------------------


def _gcloud_json(args: list[str]) -> list[dict]:
    proc = subprocess.run(
        ["gcloud", *args, "--format=json", f"--project={PROJECT}"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"gcloud失敗(終了コード{proc.returncode}): {proc.stderr[:200]}"
        )
    return json.loads(proc.stdout or "[]")


def fetch_job_states() -> dict[str, str]:
    jobs = _gcloud_json(["scheduler", "jobs", "list", f"--location={REGION}"])
    return {j["name"].rsplit("/", 1)[-1]: j.get("state", "?") for j in jobs}


def fetch_events(hours: int) -> list[dict | None]:
    patterns = " OR ".join(
        f'textPayload:"{p}"'
        for p in (
            "Starting file collection",
            "Selecting task with pattern",
            "Successfully navigated to task page",
            "Count verification",
            "Count mismatch",
            "Could not verify count",
            "not yet created",
            "Task not found",
            "Class not found",
            "提出されたレポートはありません",
        )
    )
    flt = (
        'resource.type="cloud_run_revision" '
        f'AND resource.labels.service_name="{SERVICE}" '
        f'AND ({patterns} OR (severity>=ERROR AND textPayload:"[carewell-"))'
    )
    entries = _gcloud_json(
        ["logging", "read", flt, f"--freshness={hours}h", f"--limit={LOG_LIMIT}"]
    )
    return [parse_event(e) for e in entries]


def job_name(class_no: str, task: str) -> str:
    return f"carewell-class{class_no}-task{'01' if task == '課題①' else '02'}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--class", dest="class_num", default=None)
    parser.add_argument("--task", choices=TASK_TAB_NAMES, default=None)
    parser.add_argument("--hours", type=int, default=3, help="ログを見る期間(時間)")
    args = parser.parse_args()
    if args.class_num and args.class_num not in TARGET_CLASSES:
        print(f"[エラー] クラス{args.class_num}は対象外です(対象: {TARGET_CLASSES})")
        return 2
    classes = [args.class_num] if args.class_num else TARGET_CLASSES
    tasks = [args.task] if args.task else list(TASK_TAB_NAMES)

    try:
        states = fetch_job_states()
        events = fetch_events(args.hours)
    except Exception as e:  # noqa: BLE001 取得失敗は「問題なし」にしない
        print(f"[取得失敗] {type(e).__name__}: {str(e)[:200]}")
        return 2

    now = datetime.now(timezone.utc)
    print("クラス | 課題 | ジョブ | 直近の開始 | 件数 | 結果")
    rows = []
    for cn in classes:
        for task in tasks:
            state = states.get(job_name(cn, task), "(ジョブなし)")
            summary = summarize(events, cn, task, now)
            rows.append((state, summary))
            print(render_row(cn, task, state, summary))
    print(
        f"\n[注意] 直近{args.hours}時間のログのみ。ジョブが停止中・期間内に実行がなければ"
        "「実行なし」と表示します。ERRORはクラス・課題を特定できる行だけ数えます。"
    )
    return exit_code(rows)


if __name__ == "__main__":
    sys.exit(main())
