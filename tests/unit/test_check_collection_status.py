"""
Unit tests for scripts/check_collection_status.py の純粋関数(ログ分類・表示・終了コード)。

gcloud 呼び出しは対象外。ログの原文(氏名を含みうる)を出力に出さないことを固定する。
"""

import sys

sys.path.insert(0, "scripts")

from check_collection_status import (  # noqa: E402
    OUTCOME_ABORTED,
    OUTCOME_ERROR,
    OUTCOME_MISMATCH,
    OUTCOME_NO_RUN,
    OUTCOME_NOT_FOUND,
    OUTCOME_OK,
    OUTCOME_UNVERIFIED,
    OUTCOME_ZERO,
    exit_code,
    parse_event,
    render_row,
    summarize,
)

T = "課題②"


def _e(ts, text, severity="INFO"):
    return {
        "timestamp": f"2026-10-29T01:{ts}Z",
        "severity": severity,
        "textPayload": text,
    }


def _prefix(no="01", task=T):
    return f"2026-10-29 01:05:00,000 - playwright_automation - INFO - [carewell-№{no}-{task}] "


def _start(ts, no="01", task=T):
    return _e(
        ts,
        "2026-10-29 01:05:00,000 - main - INFO - Starting file collection for "
        f"class=令和8年度 デジタル中核人材養成研修 №{no}, task_id={task}, task_pattern={task}",
    )


def _ev(ts, msg, no="01", task=T, severity="INFO"):
    return _e(ts, _prefix(no, task) + msg, severity)


def _run(*events):
    return summarize([parse_event(e) for e in events], "01", T)


class TestParseEvent:
    def test_start_line_identifies_class_and_task(self):
        p = parse_event(_start("05:00"))
        assert (p["class"], p["task"], p["kind"]) == ("01", T, "start")

    def test_prefixed_line_identifies_class_and_task(self):
        p = parse_event(_ev("05:30", "✓ Count verification passed: 7/7"))
        assert (p["class"], p["task"], p["kind"]) == ("01", T, "verified")
        assert (p["extracted"], p["total"]) == (7, 7)

    def test_not_yet_created_line_from_main(self):
        p = parse_event(
            _e(
                "05:10",
                "main - INFO - Class or task not yet created, skipping: "
                "令和8年度 デジタル中核人材養成研修 №03/課題①",
            )
        )
        assert (p["class"], p["task"], p["kind"]) == ("03", "課題①", "not_found")

    def test_unrelated_line_is_ignored(self):
        assert parse_event(_e("05:10", "something unrelated")) is None

    def test_download_line_with_a_name_is_not_a_kind_we_keep(self):
        p = parse_event(_ev("05:20", "Added: 山田　太郎 - file.xlsx"))
        assert p is None or p["kind"] == "other"


class TestSummarize:
    def test_no_events_is_no_run(self):
        assert _run()["outcome"] == OUTCOME_NO_RUN

    def test_verified_run_is_ok_with_counts(self):
        r = _run(
            _start("05:00"),
            _ev("05:10", "Selecting task with pattern: 課題②"),
            _ev("05:20", "Successfully navigated to task page"),
            _ev("05:30", "✓ Count verification passed: 7/7"),
        )
        assert (r["outcome"], r["extracted"], r["total"]) == (OUTCOME_OK, 7, 7)
        assert r["started"].endswith("05:00Z")

    def test_zero_submissions_confirmed(self):
        r = _run(
            _start("05:00"),
            _ev("05:10", "Successfully navigated to task page"),
            _ev("05:20", "✓ 「提出されたレポートはありません」を検出。"),
        )
        assert r["outcome"] == OUTCOME_ZERO

    def test_task_not_found(self):
        r = _run(
            _start("05:00"),
            _ev("05:10", "Task not found (likely not yet created): 課題②"),
        )
        assert r["outcome"] == OUTCOME_NOT_FOUND

    def test_not_yet_created_from_main_is_not_found(self):
        r = _run(
            _start("05:00"),
            _e(
                "05:10",
                "main - INFO - Class or task not yet created, skipping: "
                "令和8年度 デジタル中核人材養成研修 №01/課題②",
            ),
        )
        assert r["outcome"] == OUTCOME_NOT_FOUND

    def test_selected_but_never_reached_task_page_is_aborted(self):
        # 曖昧一致の例外などで、課題ページに着く前に止まった
        r = _run(_start("05:00"), _ev("05:10", "Selecting task with pattern: 課題②"))
        assert r["outcome"] == OUTCOME_ABORTED

    def test_count_mismatch(self):
        r = _run(
            _start("05:00"),
            _ev("05:10", "Successfully navigated to task page"),
            _ev("05:20", "⚠️ Count mismatch! Extracted 6 submissions but UI shows 7"),
        )
        assert (r["outcome"], r["extracted"], r["total"]) == (OUTCOME_MISMATCH, 6, 7)

    def test_could_not_verify_count(self):
        r = _run(
            _start("05:00"),
            _ev("05:10", "Successfully navigated to task page"),
            _ev("05:20", "Could not verify count: total_count not available from UI"),
        )
        assert r["outcome"] == OUTCOME_UNVERIFIED

    def test_error_line_with_context_wins(self):
        r = _run(
            _start("05:00"),
            _ev("05:10", "Successfully navigated to task page"),
            _ev("05:20", "✓ Count verification passed: 7/7"),
            _ev("05:25", "Failed to download x", severity="ERROR"),
        )
        assert r["outcome"] == OUTCOME_ERROR
        assert r["errors"] == 1

    def test_only_the_latest_run_counts(self):
        r = _run(
            _start("05:00"),
            _ev("05:10", "Task not found (likely not yet created): 課題②"),
            _start("35:00"),
            _ev("35:10", "Successfully navigated to task page"),
            _ev("35:20", "✓ Count verification passed: 7/7"),
        )
        assert r["outcome"] == OUTCOME_OK
        assert r["started"].endswith("35:00Z")

    def test_other_class_and_task_events_are_ignored(self):
        r = _run(
            _start("05:00"),
            _ev("05:10", "Successfully navigated to task page"),
            _ev("05:20", "✓ Count verification passed: 7/7"),
            _ev("05:21", "Task not found (likely not yet created): 課題②", no="02"),
            _ev(
                "05:22", "Task not found (likely not yet created): 課題①", task="課題①"
            ),
        )
        assert r["outcome"] == OUTCOME_OK


class TestRenderAndExit:
    def test_render_contains_only_extracted_values(self):
        raw_name = "山田　太郎"
        events = [
            _start("05:00"),
            _ev("05:10", "Successfully navigated to task page"),
            _ev("05:15", f"Added: {raw_name} - file.xlsx"),
            _ev("05:20", "✓ Count verification passed: 7/7"),
        ]
        row = render_row("01", T, "ENABLED", _run(*events))
        assert raw_name not in row
        assert "7/7" in row and "ENABLED" in row and "№01" in row

    def test_exit_code_flags_problems_on_enabled_jobs_only(self):
        ok = {"outcome": OUTCOME_OK}
        bad = {"outcome": OUTCOME_ABORTED}
        assert exit_code([("ENABLED", ok), ("PAUSED", bad)]) == 0
        assert exit_code([("ENABLED", ok), ("ENABLED", bad)]) == 1

    def test_not_found_and_no_run_are_not_failures(self):
        assert exit_code([("ENABLED", {"outcome": OUTCOME_NOT_FOUND})]) == 0
        assert exit_code([("ENABLED", {"outcome": OUTCOME_NO_RUN})]) == 0

    def test_each_problem_outcome_fails_an_enabled_job(self):
        for o in (OUTCOME_ABORTED, OUTCOME_MISMATCH, OUTCOME_UNVERIFIED, OUTCOME_ERROR):
            assert exit_code([("ENABLED", {"outcome": o})]) == 1
