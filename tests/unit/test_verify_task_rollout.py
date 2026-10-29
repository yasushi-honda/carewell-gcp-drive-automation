"""
Unit tests for scripts/verify_task_rollout.py（4段突合の自動化）。

ネットワーク呼び出し(gcloud / Sheets / Firestore)は差し替える。核は「取得できなかった値・
異常な収集を『一致』にしない」こと。0 と None の区別、収集の outcome、名簿外の提出行を固定する。
出力に氏名を含めないこと。
"""

import io
import json
import sys
import urllib.error

import pytest

sys.path.insert(0, "scripts")

from verify_task_rollout import (  # noqa: E402
    NAME_COLLECT,
    NAME_DISPLAY,
    NAME_DUPS,
    NAME_FIRESTORE,
    NAME_MEMBERS,
    NAME_PORTAL,
    NAME_ROWS,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_UNKNOWN,
    compare_stages,
    exit_code,
    find_class_name,
    render,
)

T = "課題②"


def _s(**over):
    base = {
        "collect_outcome": "OK",
        "overlap_suspected": False,
        "portal_total": 7,
        "extracted": 7,
        "sheet_rows": 7,
        "key_dups": 0,
        "unique_all": 7,
        "blank_nichikai": 0,
        "firestore_count": 7,
        "submitted_display": 7,
        "independent": 7,
    }
    base.update(over)
    return base


def _by(results):
    return {r["name"]: r for r in results}


class TestCompareStages:
    def test_everything_matches(self):
        results = compare_stages(_s())
        assert all(r["status"] == STATUS_PASS for r in results)
        assert len(results) == 7
        assert exit_code(results) == 0

    def test_extracted_differs_from_sheet_rows_points_at_sheets_append(self):
        r = _by(compare_stages(_s(sheet_rows=6)))[NAME_ROWS]
        assert r["status"] == STATUS_FAIL
        assert "Sheets追記" in r["hint"]

    def test_portal_differs_from_extracted_points_at_collection_gap(self):
        results = compare_stages(_s(portal_total=8, collect_outcome="MISMATCH"))
        r = _by(results)[NAME_PORTAL]
        assert r["status"] == STATUS_FAIL
        assert "収集漏れ" in r["hint"]

    def test_firestore_differs_from_sheet_rows(self):
        r = _by(compare_stages(_s(firestore_count=6)))[NAME_FIRESTORE]
        assert r["status"] == STATUS_FAIL

    def test_displayed_submitted_differs_from_independent_points_at_formulas(self):
        r = _by(compare_stages(_s(submitted_display=6)))[NAME_DISPLAY]
        assert r["status"] == STATUS_FAIL
        assert "再計算" in r["hint"]  # IMPORTRANGEの再計算待ちも疑う

    def test_composite_key_duplicates_fail_with_a_hint(self):
        r = _by(compare_stages(_s(key_dups=2)))[NAME_DUPS]
        assert r["status"] == STATUS_FAIL and "重複追記" in r["hint"]

    def test_a_failure_wins_over_unknown_in_the_exit_code(self):
        results = compare_stages(_s(sheet_rows=6, firestore_count=None))
        assert exit_code(results) == 1

    def test_zero_submissions_everywhere_is_a_pass(self):
        results = compare_stages(
            _s(
                portal_total=0,
                extracted=0,
                sheet_rows=0,
                firestore_count=0,
                unique_all=0,
                submitted_display=0,
                independent=0,
            )
        )
        assert exit_code(results) == 0

    def test_rows_and_people_are_compared_separately(self):
        # 同じ受講者が2回提出: 行数は増えるが、提出者(人数)は7名のまま
        results = compare_stages(
            _s(
                portal_total=8,
                extracted=8,
                sheet_rows=8,
                firestore_count=8,
                unique_all=7,
                submitted_display=7,
                independent=7,
            )
        )
        assert exit_code(results) == 0


class TestUnknownIsNeverAPass:
    """取得できなかった値(None)は『一致』にしない。0 とは区別する。"""

    @pytest.mark.parametrize(
        "over,name",
        [
            ({"portal_total": None}, NAME_PORTAL),
            ({"extracted": None}, NAME_PORTAL),
            ({"extracted": None}, NAME_ROWS),
            ({"sheet_rows": None}, NAME_ROWS),
            ({"sheet_rows": None}, NAME_FIRESTORE),
            ({"firestore_count": None}, NAME_FIRESTORE),
            ({"key_dups": None}, NAME_DUPS),
            ({"unique_all": None}, NAME_MEMBERS),
            ({"blank_nichikai": None}, NAME_MEMBERS),
            ({"submitted_display": None}, NAME_DISPLAY),
            ({"independent": None}, NAME_DISPLAY),
        ],
    )
    def test_a_single_missing_value_makes_that_stage_unknown(self, over, name):
        results = compare_stages(_s(**over))
        assert _by(results)[name]["status"] == STATUS_UNKNOWN
        assert exit_code(results) == 2

    def test_unfinished_latest_run_makes_portal_comparison_unknown(self):
        results = compare_stages(
            _s(collect_outcome="RUNNING", portal_total=None, extracted=None)
        )
        assert _by(results)[NAME_PORTAL]["status"] == STATUS_UNKNOWN
        assert exit_code(results) == 2

    def test_zero_is_a_value_not_a_missing_value(self):
        results = compare_stages(_s(firestore_count=0, sheet_rows=7))
        assert (
            _by(results)[NAME_FIRESTORE]["status"] == STATUS_FAIL
        )  # 0 ≠ 7(UNKNOWNではない)


class TestCollectOutcomeIsNotIgnored:
    """件数が揃っていても、収集に異常があれば全段PASSにしない(ERROR・件数不一致の実行)。"""

    def test_error_outcome_fails_even_when_every_count_matches(self):
        results = compare_stages(_s(collect_outcome="ERROR"))
        assert _by(results)[NAME_COLLECT]["status"] == STATUS_FAIL
        assert exit_code(results) == 1

    def test_mismatch_outcome_fails_even_when_the_retry_counts_match(self):
        results = compare_stages(_s(collect_outcome="MISMATCH"))
        assert _by(results)[NAME_COLLECT]["status"] == STATUS_FAIL
        assert exit_code(results) == 1

    @pytest.mark.parametrize(
        "outcome",
        ["ABORTED", "NOT_FOUND", "UNVERIFIED", "NO_RUN", "RUNNING"],
    )
    def test_other_non_ok_outcomes_are_unknown_never_exit_0(self, outcome):
        results = compare_stages(_s(collect_outcome=outcome))
        assert _by(results)[NAME_COLLECT]["status"] == STATUS_UNKNOWN
        assert exit_code(results) == 2

    @pytest.mark.parametrize("outcome", ["OK", "ZERO_CONFIRMED"])
    def test_ok_and_zero_confirmed_pass(self, outcome):
        results = compare_stages(_s(collect_outcome=outcome))
        assert _by(results)[NAME_COLLECT]["status"] == STATUS_PASS

    def test_overlap_is_noted_in_the_detail(self):
        r = _by(compare_stages(_s(overlap_suspected=True)))[NAME_COLLECT]
        assert r["status"] == STATUS_PASS and "重なった" in r["detail"]


class TestSubmittersAreAllInTheRoster:
    """名簿外・日介番号が空欄の提出行は、独立集計でも出欠確認でも除かれて一致してしまう。"""

    def test_blank_nichikai_rows_fail(self):
        r = _by(compare_stages(_s(blank_nichikai=1)))[NAME_MEMBERS]
        assert r["status"] == STATUS_FAIL and "空欄" in r["hint"]

    def test_submitters_outside_the_roster_fail(self):
        # 提出記録のユニーク提出者8名のうち、名簿内は7名
        r = _by(compare_stages(_s(unique_all=8, independent=7)))[NAME_MEMBERS]
        assert r["status"] == STATUS_FAIL and "名簿外" in r["hint"]

    def test_the_display_stage_alone_would_have_missed_it(self):
        results = compare_stages(_s(unique_all=8, independent=7, submitted_display=7))
        assert (
            _by(results)[NAME_DISPLAY]["status"] == STATUS_PASS
        )  # ここだけでは気づけない
        assert exit_code(results) == 1


class TestRenderAndHelpers:
    def test_render_shows_numbers_and_status(self):
        out = render("01", T, compare_stages(_s()))
        assert "№01" in out and T in out and "PASS" in out

    def test_render_includes_the_hint_for_failures(self):
        out = render("01", T, compare_stages(_s(sheet_rows=6)))
        assert "FAIL" in out and "Sheets追記" in out

    def test_find_class_name_uses_the_known_class_list(self):
        assert find_class_name("01").endswith("№01") and "研修" in find_class_name("01")

    def test_find_class_name_unknown_raises(self):
        with pytest.raises(ValueError):
            find_class_name("99")


# --- main の配線 ---------------------------------------------------------------


def _verified(n):
    return {"outcome": "OK", "extracted": n, "total": n, "started": "t"}


class TestWiring:
    def _run(
        self,
        monkeypatch,
        capsys,
        *,
        summary=None,
        events=None,
        sheet=(7, 0, 7, 0),
        firestore=7,
        facts=None,
    ):
        import verify_task_rollout as v

        monkeypatch.setattr(
            sys, "argv", ["verify_task_rollout.py", "--class", "01", "--task", T]
        )
        monkeypatch.setattr(v, "fetch_events", lambda hours: events or [])
        if summary is not None:
            monkeypatch.setattr(v, "summarize", lambda ev, c, t, now: summary)
        monkeypatch.setattr(v, "fetch_sheet_rows", lambda c, t: v.SheetRows(*sheet, ""))
        monkeypatch.setattr(
            v,
            "fetch_firestore_file_count",
            lambda c, t: v.FirestoreCount(firestore, ""),
        )
        monkeypatch.setattr(
            v,
            "gather_facts",
            lambda c, t: facts or {"_submitted": 7, "_independent": 7},
        )
        code = v.main()
        return code, capsys.readouterr().out

    def test_all_stages_match_is_exit_0(self, monkeypatch, capsys):
        code, out = self._run(monkeypatch, capsys, summary=_verified(7))
        assert code == 0 and "FAIL" not in out and "UNKNOWN" not in out

    # 各段に別々の値を与え、取り違えがあれば該当段が落ちないことを確認する
    @pytest.mark.parametrize(
        "kwargs,failing",
        [
            (
                {"summary": {"outcome": "MISMATCH", "extracted": 7, "total": 8}},
                NAME_PORTAL,
            ),
            ({"firestore": 6}, NAME_FIRESTORE),
            ({"sheet": (6, 0, 6, 0)}, NAME_ROWS),
            ({"sheet": (7, 2, 7, 0)}, NAME_DUPS),
            ({"sheet": (7, 0, 7, 1)}, NAME_MEMBERS),
            ({"sheet": (7, 0, 8, 0)}, NAME_MEMBERS),
            ({"facts": {"_submitted": 6, "_independent": 7}}, NAME_DISPLAY),
            ({"facts": {"_submitted": 7, "_independent": 6}}, NAME_DISPLAY),
        ],
    )
    def test_each_stage_is_wired_to_its_own_value(
        self, monkeypatch, capsys, kwargs, failing
    ):
        kwargs.setdefault("summary", _verified(7))
        code, out = self._run(monkeypatch, capsys, **kwargs)
        assert code == 1
        line = next(l for l in out.splitlines() if failing in l)
        assert line.startswith("[FAIL]")

    def test_zero_confirmed_compares_as_zero_everywhere(self, monkeypatch, capsys):
        code, _ = self._run(
            monkeypatch,
            capsys,
            summary={"outcome": "ZERO_CONFIRMED", "started": "t"},
            sheet=(0, 0, 0, 0),
            firestore=0,
            facts={"_submitted": 0, "_independent": 0},
        )
        assert code == 0

    @pytest.mark.parametrize(
        "outcome", ["RUNNING", "ABORTED", "NOT_FOUND", "NO_RUN", "UNVERIFIED"]
    )
    def test_a_non_ok_collection_never_exits_0(self, monkeypatch, capsys, outcome):
        code, _ = self._run(
            monkeypatch, capsys, summary={"outcome": outcome, "started": "t"}
        )
        assert code == 2

    def test_real_summarize_verified_then_error_is_exit_1(self, monkeypatch, capsys):
        """実際の summarize を通す: 件数は揃うが同じ実行にERRORがある → 全段一致でも終了0にならない。"""
        from check_collection_status import parse_event

        def at(ts, text, sev="INFO"):
            return parse_event(
                {
                    "timestamp": f"2026-10-29T01:{ts}Z",
                    "severity": sev,
                    "textPayload": text,
                }
            )

        pre = f"x - playwright_automation - INFO - [carewell-№01-{T}] "
        events = [
            at(
                "05:00",
                "x - main - INFO - Starting file collection for class=令和8年度 デジタル中核人材養成研修 №01, "
                f"task_id={T}, task_pattern={T}",
            ),
            at("05:10", pre + "Successfully navigated to task page"),
            at("05:20", pre + "✓ Count verification passed: 7/7"),
            at(
                "05:30",
                f"x - playwright_automation - ERROR - [carewell-№01-{T}] Failed to download x",
            ),
        ]
        code, out = self._run(monkeypatch, capsys, events=events)
        assert code == 1 and "ERROR" in out

    def test_unreadable_sheet_is_unknown(self, monkeypatch, capsys):
        code, _ = self._run(
            monkeypatch, capsys, summary=_verified(7), sheet=(None, None, None, None)
        )
        assert code == 2

    def test_firestore_failure_note_is_printed(self, monkeypatch, capsys):
        import verify_task_rollout as v

        monkeypatch.setattr(
            sys, "argv", ["verify_task_rollout.py", "--class", "01", "--task", T]
        )
        monkeypatch.setattr(v, "fetch_events", lambda hours: [])
        monkeypatch.setattr(v, "summarize", lambda ev, c, t, now: _verified(7))
        monkeypatch.setattr(
            v, "fetch_sheet_rows", lambda c, t: v.SheetRows(7, 0, 7, 0, "")
        )
        monkeypatch.setattr(
            v,
            "fetch_firestore_file_count",
            lambda c, t: v.FirestoreCount(None, "Firestore HTTP 403"),
        )
        monkeypatch.setattr(
            v, "gather_facts", lambda c, t: {"_submitted": 7, "_independent": 7}
        )
        code = v.main()
        assert code == 2 and "Firestore HTTP 403" in capsys.readouterr().out

    def test_fetch_failure_is_exit_2(self, monkeypatch):
        import verify_task_rollout as v

        monkeypatch.setattr(
            sys, "argv", ["verify_task_rollout.py", "--class", "01", "--task", T]
        )

        def boom(hours):
            raise RuntimeError("gcloud失敗")

        monkeypatch.setattr(v, "fetch_events", boom)
        assert v.main() == 2

    def test_unknown_class_is_exit_2(self, monkeypatch):
        import verify_task_rollout as v

        monkeypatch.setattr(
            sys, "argv", ["verify_task_rollout.py", "--class", "99", "--task", T]
        )
        assert v.main() == 2

    def test_output_does_not_leak_names_even_if_the_sources_carry_them(
        self, monkeypatch, capsys
    ):
        """取得元(summary・notes)に氏名が紛れ込んでも、出力に出ない。"""
        import verify_task_rollout as v

        summary = {
            **_verified(7),
            "raw": "山田　太郎 01_D067_山田.xlsx",
            "name": "山田",
        }
        monkeypatch.setattr(
            sys, "argv", ["verify_task_rollout.py", "--class", "01", "--task", T]
        )
        monkeypatch.setattr(v, "fetch_events", lambda hours: [])
        monkeypatch.setattr(v, "summarize", lambda ev, c, t, now: summary)
        monkeypatch.setattr(
            v, "fetch_sheet_rows", lambda c, t: v.SheetRows(7, 0, 7, 0, "")
        )
        monkeypatch.setattr(
            v, "fetch_firestore_file_count", lambda c, t: v.FirestoreCount(7, "")
        )
        monkeypatch.setattr(
            v,
            "gather_facts",
            lambda c, t: {"_submitted": 7, "_independent": 7, "name": "山田"},
        )
        v.main()
        out = capsys.readouterr().out
        assert "山田" not in out and "D067" not in out


# --- 取得層 --------------------------------------------------------------------


class _FakeResp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self, *a):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Proc:
    stdout = "tok\n"


def _http_error(code, message=None):
    body = json.dumps(
        {"error": {"status": "NOT_FOUND", "message": message or ""}}
    ).encode()
    return urllib.error.HTTPError("u", code, "x", None, io.BytesIO(body))


class TestFirestoreFetch:
    def _patch(self, monkeypatch, urlopen):
        import verify_task_rollout as v

        monkeypatch.setattr(v.subprocess, "run", lambda *a, **k: _Proc())
        monkeypatch.setattr(v.urllib.request, "urlopen", urlopen)
        return v

    def test_success_reads_the_integer_and_builds_the_expected_request(
        self, monkeypatch
    ):
        seen = {}

        def urlopen(req, timeout=None):
            seen["url"] = req.full_url
            seen["auth"] = req.get_header("Authorization")
            return _FakeResp({"fields": {"file_count": {"integerValue": "7"}}})

        v = self._patch(monkeypatch, urlopen)
        r = v.fetch_firestore_file_count("01", T)
        assert (r.count, r.note) == (7, "")
        assert v.resolve_firestore_database_id() in seen["url"]
        assert "/documents/submissions/" in seen["url"]
        assert "%E2%84%9601" in seen["url"]  # №01 がエンコードされている
        assert "%E8%AA%B2%E9%A1%8C%E2%91%A1" in seen["url"]  # 課題②
        assert "mask.fieldPaths=file_count" in seen["url"]
        assert seen["auth"] == "Bearer tok"

    def test_document_not_found_means_nothing_recorded_yet(self, monkeypatch):
        def urlopen(req, timeout=None):
            raise _http_error(
                404, 'Document "projects/p/databases/d/documents/x" not found.'
            )

        v = self._patch(monkeypatch, urlopen)
        assert v.fetch_firestore_file_count("01", T).count == 0

    def test_database_not_found_is_unknown_not_zero(self, monkeypatch):
        def urlopen(req, timeout=None):
            raise _http_error(404, "The database x does not exist for project p")

        v = self._patch(monkeypatch, urlopen)
        r = v.fetch_firestore_file_count("01", T)
        assert r.count is None and "404" in r.note

    @pytest.mark.parametrize("code", [403, 500])
    def test_other_http_errors_are_unknown_with_the_status(self, monkeypatch, code):
        def urlopen(req, timeout=None):
            raise _http_error(code)

        v = self._patch(monkeypatch, urlopen)
        r = v.fetch_firestore_file_count("01", T)
        assert r.count is None and str(code) in r.note

    @pytest.mark.parametrize(
        "payload",
        [
            {"fields": {}},
            {},
            {"fields": {"file_count": {"nullValue": None}}},
            {"fields": {"file_count": {"stringValue": "seven"}}},
            {"fields": {"file_count": {"doubleValue": 7.5}}},
        ],
    )
    def test_missing_or_non_integer_file_count_is_unknown(self, monkeypatch, payload):
        v = self._patch(monkeypatch, lambda req, timeout=None: _FakeResp(payload))
        assert v.fetch_firestore_file_count("01", T).count is None

    def test_network_failure_is_unknown_with_the_error_type(self, monkeypatch):
        def urlopen(req, timeout=None):
            raise urllib.error.URLError("dns")

        v = self._patch(monkeypatch, urlopen)
        r = v.fetch_firestore_file_count("01", T)
        assert r.count is None and "URLError" in r.note

    def test_gcloud_token_failure_is_unknown(self, monkeypatch):
        import subprocess

        import verify_task_rollout as v

        def boom(*a, **k):
            raise subprocess.CalledProcessError(1, "gcloud")

        monkeypatch.setattr(v.subprocess, "run", boom)
        r = v.fetch_firestore_file_count("01", T)
        assert r.count is None and "CalledProcessError" in r.note


class TestSheetRowsFetch:
    def _fetch(self, monkeypatch, values):
        import verify_task_rollout as v

        monkeypatch.setattr(v, "_get_values", lambda b, sid, rng: values)
        return v.fetch_sheet_rows("01", T)

    def test_counts_rows_duplicates_unique_and_blank_nichikai(self, monkeypatch):
        r = self._fetch(
            monkeypatch,
            [
                [T, "k1", "n", "d1"],
                [T, "k2", "n", "d2"],
                [T, "k2", "n", "d2"],
                [T, "k3", "n", ""],
                [],
            ],
        )
        assert (r.rows, r.key_dups, r.unique_nichikai, r.blank_nichikai) == (4, 1, 2, 1)

    def test_all_blank_rows_mean_zero_not_unknown(self, monkeypatch):
        r = self._fetch(monkeypatch, [[], ["", " "]])
        assert (r.rows, r.key_dups, r.unique_nichikai, r.blank_nichikai) == (0, 0, 0, 0)

    def test_blank_keys_do_not_count_as_duplicates(self, monkeypatch):
        r = self._fetch(monkeypatch, [[T, "", "n", "d1"], [T, " ", "n", "d2"]])
        assert r.rows == 2 and r.key_dups == 0

    def test_keys_are_compared_after_stripping(self, monkeypatch):
        r = self._fetch(monkeypatch, [[T, "k1 ", "n", "d1"], [T, "k1", "n", "d2"]])
        assert r.key_dups == 1

    def test_same_key_three_times_is_two_duplicates(self, monkeypatch):
        r = self._fetch(monkeypatch, [[T, "k", "n", "d"]] * 3)
        assert r.key_dups == 2

    def test_short_rows_without_the_nichikai_column_count_as_blank(self, monkeypatch):
        r = self._fetch(monkeypatch, [["x", "k1"]])
        assert r.rows == 1 and r.blank_nichikai == 1

    def test_unreadable_tab_is_unknown_with_a_note(self, monkeypatch):
        import verify_task_rollout as v

        def boom(*a, **k):
            raise RuntimeError("no tab")

        monkeypatch.setattr(v, "_get_values", boom)
        r = v.fetch_sheet_rows("01", T)
        assert r.rows is None and "RuntimeError" in r.note

    def test_hitting_the_read_cap_is_an_error_not_a_silent_undercount(
        self, monkeypatch
    ):
        import verify_task_rollout as v

        rows = [[T, f"k{i}", "n", f"d{i}"] for i in range(v.SUBMISSION_READ_CAP)]
        monkeypatch.setattr(v, "_get_values", lambda b, sid, rng: rows)
        with pytest.raises(Exception, match="上限"):
            v.fetch_sheet_rows("01", T)
