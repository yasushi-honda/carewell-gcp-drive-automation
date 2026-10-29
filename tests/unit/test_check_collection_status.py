"""
Unit tests for scripts/check_collection_status.py の純粋関数(ログ分類・表示・終了コード)。

gcloud 呼び出しは対象外。ログの原文(氏名を含みうる)を出力に出さないことを固定する。
"""

import sys
from datetime import datetime, timezone

sys.path.insert(0, "scripts")

from check_collection_status import (  # noqa: E402
    OUTCOME_ABORTED,
    OUTCOME_ERROR,
    OUTCOME_MISMATCH,
    OUTCOME_NO_RUN,
    OUTCOME_NOT_FOUND,
    OUTCOME_OK,
    OUTCOME_RUNNING,
    OUTCOME_UNVERIFIED,
    OUTCOME_ZERO,
    count_unattributed_errors,
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

    def test_not_found_is_not_a_failure_by_default(self):
        # 未公開の課題は「見つからない」が正常。公開済みの課題では --strict-not-found を使う
        assert exit_code([("ENABLED", {"outcome": OUTCOME_NOT_FOUND})]) == 0

    def test_each_problem_outcome_fails_an_enabled_job(self):
        for o in (OUTCOME_ABORTED, OUTCOME_MISMATCH, OUTCOME_UNVERIFIED, OUTCOME_ERROR):
            assert exit_code([("ENABLED", {"outcome": o})]) == 1


# --- codex review の指摘への対応 -----------------------------------------------


class TestErrorDetectionFromTextLevel:
    """収集コードはテキスト形式のログで、logger.error()の重大度はDEFAULT(空)になる。"""

    def test_text_error_line_without_severity_is_an_error(self):
        entry = {
            "timestamp": "2026-10-29T01:05:10Z",
            "textPayload": "2026-10-29 01:05:10,000 - playwright_automation - ERROR - "
            f"[carewell-№01-{T}] Error downloading x",
        }
        assert parse_event(entry)["kind"] == "error"

    def test_critical_text_line_is_an_error(self):
        entry = {
            "timestamp": "2026-10-29T01:05:10Z",
            "textPayload": f"x - CRITICAL - [carewell-№01-{T}] boom",
        }
        assert parse_event(entry)["kind"] == "error"

    def test_info_line_mentioning_error_word_is_not_an_error(self):
        p = parse_event(_ev("05:10", "Handled ERROR page gracefully"))
        assert p["kind"] != "error"

    def test_run_with_a_text_error_is_reported_as_error(self):
        err = {
            "timestamp": "2026-10-29T01:05:25Z",
            "textPayload": f"x - ERROR - [carewell-№01-{T}] Failed to download x",
        }
        r = _run(
            _start("05:00"),
            _ev("05:10", "Successfully navigated to task page"),
            _ev("05:20", "✓ Count verification passed: 7/7"),
            err,
        )
        assert r["outcome"] == OUTCOME_ERROR


class TestLongRunningAndOverlap:
    NOW = datetime(2026, 10, 29, 1, 35, 0, tzinfo=timezone.utc)

    def test_unfinished_run_younger_than_the_request_timeout_is_running(self):
        # 課題ページに着いたあと、リンク取得に10分以上かかる大きな課題でも中断とは断定しない
        r = summarize(
            [
                parse_event(e)
                for e in (
                    _start("05:00"),
                    _ev("06:00", "Successfully navigated to task page"),
                )
            ],
            "01",
            T,
            now=self.NOW,
        )
        assert r["outcome"] == OUTCOME_RUNNING

    def test_unfinished_run_older_than_the_request_timeout_is_aborted(self):
        r = summarize(
            [
                parse_event(e)
                for e in (
                    _start("05:00"),
                    _ev("05:10", "Selecting task with pattern: 課題②"),
                )
            ],
            "01",
            T,
            now=datetime(2026, 10, 29, 2, 30, 0, tzinfo=timezone.utc),
        )
        assert r["outcome"] == OUTCOME_ABORTED

    def test_overlap_is_flagged_but_does_not_change_the_outcome(self):
        # 手動実行(A)と定期実行(B)が重なり、Aの検証結果がBの区間に入る
        r = _run(
            _start("05:00"),
            _start("10:00"),
            _ev("10:30", "✓ Count verification passed: 7/7"),
        )
        assert r["overlap_suspected"] is True
        assert r["outcome"] == OUTCOME_OK

    def test_repeated_aborts_are_not_masked_by_the_overlap_flag(self):
        # 毎回、課題ページに着く前に中断する場合も、結果は中断のまま
        r = summarize(
            [
                parse_event(e)
                for e in (
                    _start("05:00"),
                    _ev("05:10", "Selecting task with pattern: 課題②"),
                    _start("35:00"),
                    _ev("35:10", "Selecting task with pattern: 課題②"),
                )
            ],
            "01",
            T,
            now=datetime(2026, 10, 29, 3, 0, 0, tzinfo=timezone.utc),
        )
        assert r["outcome"] == OUTCOME_ABORTED

    def test_sequential_finished_runs_are_not_flagged(self):
        r = _run(
            _start("05:00"),
            _ev("05:20", "✓ Count verification passed: 7/7"),
            _start("35:00"),
            _ev("35:20", "✓ Count verification passed: 7/7"),
        )
        assert r["overlap_suspected"] is False

    def test_render_notes_the_overlap(self):
        r = _run(
            _start("05:00"),
            _start("10:00"),
            _ev("10:30", "✓ Count verification passed: 7/7"),
        )
        assert "重なった" in render_row("01", T, "ENABLED", r)


class TestRepeatedFailuresAreNotHiddenByTheRunningWindow:
    """30分ごとの新しい開始が猶予をリセットし、毎回の中断が『実行中』に見え続けてはいけない。"""

    NOW = datetime(2026, 10, 29, 1, 36, 0, tzinfo=timezone.utc)

    def _summarize(self, *events):
        return summarize([parse_event(e) for e in events], "01", T, now=self.NOW)

    def test_two_unfinished_attempts_in_a_row_are_aborted_not_running(self):
        r = self._summarize(
            _start("00:00"),
            _ev("01:30", "Selecting task with pattern: 課題②"),
            _start("30:00"),
            _ev("31:30", "Selecting task with pattern: 課題②"),
        )
        assert r["outcome"] == OUTCOME_ABORTED
        assert r["repeated_unfinished"] is True

    def test_a_finished_previous_attempt_keeps_the_new_one_running(self):
        r = self._summarize(
            _start("00:00"),
            _ev("04:00", "✓ Count verification passed: 7/7"),
            _start("30:00"),
            _ev("31:30", "Selecting task with pattern: 課題②"),
        )
        assert r["outcome"] == OUTCOME_RUNNING
        assert r["repeated_unfinished"] is False

    def test_an_overlapping_start_is_not_counted_as_a_failed_attempt(self):
        # 手動実行の途中で、10分後に定期実行が始まった(前の実行はまだ動いているかもしれない)
        r = self._summarize(
            _start("22:00"),
            _ev("23:00", "Successfully navigated to task page"),
            _start("32:00"),
            _ev("33:00", "Selecting task with pattern: 課題②"),
        )
        assert r["outcome"] == OUTCOME_RUNNING
        assert r["repeated_unfinished"] is False

    def test_render_says_the_previous_attempt_also_did_not_finish(self):
        r = self._summarize(
            _start("00:00"),
            _ev("01:30", "Selecting task with pattern: 課題②"),
            _start("30:00"),
            _ev("31:30", "Selecting task with pattern: 課題②"),
        )
        assert "繰り返し" in render_row("01", T, "ENABLED", r)

    def test_exit_code_is_1_for_the_repeated_failure(self):
        r = self._summarize(
            _start("00:00"),
            _ev("01:30", "Selecting task with pattern: 課題②"),
            _start("30:00"),
            _ev("31:30", "Selecting task with pattern: 課題②"),
        )
        assert exit_code([("ENABLED", r)]) == 1


# --- PR #88 のレビュー指摘への対応 ---------------------------------------------


class TestUnattributedErrors:
    """main.pyのロガーのERRORには[carewell-...]の接頭辞が付かない(ダウンロード失敗・500など)。"""

    def test_unprefixed_error_is_kept_as_unattributed(self):
        entry = {
            "timestamp": "2026-10-29T01:05:10Z",
            "textPayload": "2026-10-29 01:05:10,000 - __main__ - ERROR - "
            "Failed to download 山田　太郎.xlsx: boom",
        }
        p = parse_event(entry)
        assert p["kind"] == "error_unattributed" and p["class"] is None
        assert "山田" not in str(p)  # 原文(氏名を含みうる)は保持しない

    def test_unprefixed_info_line_is_still_ignored(self):
        entry = {"timestamp": "2026-10-29T01:05:10Z", "textPayload": "main - INFO - hi"}
        assert parse_event(entry) is None

    def test_count_unattributed_errors(self):
        events = [
            parse_event(
                {
                    "timestamp": f"2026-10-29T01:0{i}:00Z",
                    "textPayload": "x - __main__ - ERROR - Error during execution: boom",
                }
            )
            for i in (1, 2)
        ] + [parse_event(_start("05:00"))]
        n, latest = count_unattributed_errors(events)
        assert n == 2 and latest == "2026-10-29T01:02:00Z"

    def test_none_when_there_are_no_unattributed_errors(self):
        assert count_unattributed_errors([parse_event(_start("05:00")), None]) == (
            0,
            None,
        )

    def test_summarize_ignores_unattributed_errors(self):
        err = parse_event(
            {"timestamp": "2026-10-29T01:05:10Z", "textPayload": "x - ERROR - boom"}
        )
        r = summarize([parse_event(_start("05:00")), err], "01", T)
        assert r["errors"] == 0


class TestExitCodeStrictness:
    def test_enabled_job_with_no_run_is_a_problem(self):
        assert exit_code([("ENABLED", {"outcome": OUTCOME_NO_RUN})]) == 1

    def test_paused_job_with_no_run_is_fine(self):
        assert exit_code([("PAUSED", {"outcome": OUTCOME_NO_RUN})]) == 0

    def test_missing_job_is_a_problem(self):
        assert exit_code([("(ジョブなし)", {"outcome": OUTCOME_NO_RUN})]) == 1

    def test_not_found_is_a_problem_only_when_strict(self):
        row = [("ENABLED", {"outcome": OUTCOME_NOT_FOUND})]
        assert exit_code(row) == 0
        assert exit_code(row, strict_not_found=True) == 1
        assert exit_code([("PAUSED", row[0][1])], strict_not_found=True) == 0

    def test_unattributed_errors_make_the_exit_code_1(self):
        ok = [("ENABLED", {"outcome": OUTCOME_OK})]
        assert exit_code(ok, unattributed_errors=0) == 0
        assert exit_code(ok, unattributed_errors=1) == 1


class TestRepeatedUnfinishedUsesTheLastAttemptOnly:
    NOW = datetime(2026, 10, 29, 1, 10, 0, tzinfo=timezone.utc)

    def test_old_unfinished_then_finished_then_running_is_running(self):
        def at(ts, text):
            return {
                "timestamp": f"2026-10-29T{ts}Z",
                "severity": "INFO",
                "textPayload": text,
            }

        start = _start("00:00")["textPayload"]
        events = [
            at("00:05:00", start),  # 古い実行: 未完了
            at("00:35:00", start),  # 次の実行: 完了
            at("00:36:00", _prefix() + "✓ Count verification passed: 7/7"),
            at("01:05:00", start),  # いまの実行: 進行中
            at("01:06:00", _prefix() + "Selecting task with pattern: 課題②"),
        ]
        r = summarize([parse_event(e) for e in events], "01", T, now=self.NOW)
        assert r["outcome"] == OUTCOME_RUNNING
        assert r["repeated_unfinished"] is False


class TestLogLimit:
    def test_hitting_the_limit_is_an_error_not_a_silent_truncation(self, monkeypatch):
        import check_collection_status as c

        monkeypatch.setattr(
            c, "_gcloud_json", lambda args: [{"textPayload": "x"}] * c.LOG_LIMIT
        )
        import pytest

        with pytest.raises(RuntimeError, match="上限"):
            c.fetch_events(3)

    def test_below_the_limit_is_fine(self, monkeypatch):
        import check_collection_status as c

        monkeypatch.setattr(c, "_gcloud_json", lambda args: [{"textPayload": "x"}])
        assert c.fetch_events(3) == [None]


class TestMainWiring:
    def _run(self, monkeypatch, capsys, argv, states, events):
        import check_collection_status as c

        monkeypatch.setattr(sys, "argv", ["check_collection_status.py", *argv])
        monkeypatch.setattr(c, "fetch_job_states", lambda: states)
        monkeypatch.setattr(c, "fetch_events", lambda hours: events)
        code = c.main()
        return code, capsys.readouterr().out

    def test_unattributed_error_fails_and_is_reported_without_text(
        self, monkeypatch, capsys
    ):
        err = parse_event(
            {
                "timestamp": "2026-10-29T01:05:10Z",
                "textPayload": "x - __main__ - ERROR - Failed to download 山田.xlsx",
            }
        )
        code, out = self._run(
            monkeypatch,
            capsys,
            ["--class", "01", "--task", T],
            {"carewell-class01-task02": "PAUSED"},
            [err],
        )
        assert code == 1
        assert "帰属不明のERROR" in out and "山田" not in out

    def test_strict_not_found_flag_is_wired(self, monkeypatch, capsys):
        events = [
            parse_event(_start("05:00")),
            parse_event(_ev("05:10", "Task not found (likely not yet created): 課題②")),
        ]
        states = {"carewell-class01-task02": "ENABLED"}
        argv = ["--class", "01", "--task", T]
        code, _ = self._run(monkeypatch, capsys, argv, states, events)
        assert code == 0
        code, _ = self._run(
            monkeypatch, capsys, [*argv, "--strict-not-found"], states, events
        )
        assert code == 1

    def test_fetch_failure_is_exit_2(self, monkeypatch, capsys):
        import check_collection_status as c

        def boom():
            raise RuntimeError("gcloud失敗")

        monkeypatch.setattr(
            sys, "argv", ["check_collection_status.py", "--class", "01"]
        )
        monkeypatch.setattr(c, "fetch_job_states", boom)
        assert c.main() == 2


class TestLogMessageContract:
    """スクリプトが前提にするログ文言が、収集コード(src/)に実在すること。
    文言が変わると、このスクリプトが静かに「実行なし」や「中断」へ偏るため、ここで検知する。"""

    @staticmethod
    def _src():
        from pathlib import Path

        root = Path(__file__).resolve().parents[2] / "src"
        return (root / "main.py").read_text() + (
            root / "playwright_automation.py"
        ).read_text()

    def test_phrases_exist_in_the_collector(self):
        src = self._src()
        for phrase in (
            "Starting file collection for class=",
            "Class or task not yet created, skipping:",
            "✓ Count verification passed:",
            "Count mismatch! Extracted",
            "submissions but UI shows",
            "Could not verify count",
            "Task not found",
            "Class not found",
            "Selecting task with pattern",
            "Successfully navigated to task page",
            "提出されたレポートはありません",
        ):
            assert phrase in src, f"収集コードにログ文言が見つかりません: {phrase}"

    def test_log_format_has_the_level_and_the_context_prefix(self):
        src = self._src()
        assert "%(asctime)s - %(name)s - %(levelname)s - %(message)s" in src
        assert 'return f"[carewell-' in src or "[carewell-" in src
