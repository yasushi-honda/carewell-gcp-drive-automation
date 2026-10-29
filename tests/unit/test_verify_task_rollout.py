"""
Unit tests for scripts/verify_task_rollout.py（4段突合の自動化）。

ネットワーク呼び出し(gcloud / Sheets / Firestore)は対象外。比較ロジックと、
食い違いの「読み方」を固定する。出力に氏名を含めないこと。
"""

import sys

sys.path.insert(0, "scripts")

from verify_task_rollout import (  # noqa: E402
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_UNKNOWN,
    compare_stages,
    exit_code,
    find_class_name,
    render,
)


def _s(**over):
    base = {
        "collect_outcome": "OK",
        "portal_total": 7,
        "extracted": 7,
        "sheet_rows": 7,
        "key_dups": 0,
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
        assert exit_code(results) == 0

    def test_extracted_differs_from_sheet_rows_points_at_sheets_append(self):
        r = _by(compare_stages(_s(sheet_rows=6)))[
            "Cloud Run の取得件数 = 提出記録の行数"
        ]
        assert r["status"] == STATUS_FAIL
        assert "Sheets追記" in r["hint"]

    def test_portal_differs_from_extracted_points_at_collection_gap(self):
        results = compare_stages(
            _s(portal_total=8, extracted=7, collect_outcome="MISMATCH")
        )
        r = _by(results)["ポータルの件数 = Cloud Run の取得件数"]
        assert r["status"] == STATUS_FAIL
        assert "収集漏れ" in r["hint"]

    def test_firestore_differs_from_sheet_rows(self):
        r = _by(compare_stages(_s(firestore_count=6)))[
            "Firestore の file_count = 提出記録の行数"
        ]
        assert r["status"] == STATUS_FAIL

    def test_displayed_submitted_differs_from_independent_points_at_formulas(self):
        r = _by(compare_stages(_s(submitted_display=6)))[
            "出欠確認の「提出」件数 = 提出記録のユニーク提出者(名簿内)"
        ]
        assert r["status"] == STATUS_FAIL
        assert "再計算" in r["hint"]  # IMPORTRANGEの再計算待ちも疑う

    def test_composite_key_duplicates_fail(self):
        r = _by(compare_stages(_s(key_dups=2)))["提出記録に複合キーの重複なし"]
        assert r["status"] == STATUS_FAIL

    def test_unfinished_latest_run_makes_portal_comparison_unknown(self):
        results = compare_stages(
            _s(collect_outcome="RUNNING", portal_total=None, extracted=None)
        )
        r = _by(results)["ポータルの件数 = Cloud Run の取得件数"]
        assert r["status"] == STATUS_UNKNOWN
        assert exit_code(results) == 2

    def test_firestore_unavailable_is_unknown_not_pass(self):
        results = compare_stages(_s(firestore_count=None))
        r = _by(results)["Firestore の file_count = 提出記録の行数"]
        assert r["status"] == STATUS_UNKNOWN
        assert exit_code(results) == 2

    def test_formulas_not_set_makes_the_display_comparison_unknown(self):
        results = compare_stages(_s(submitted_display=None, independent=None))
        r = _by(results)["出欠確認の「提出」件数 = 提出記録のユニーク提出者(名簿内)"]
        assert r["status"] == STATUS_UNKNOWN

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
                submitted_display=0,
                independent=0,
            )
        )
        assert exit_code(results) == 0

    def test_multiple_submissions_by_one_person_rows_vs_people_are_separate(self):
        # 同じ受講者が2回提出: 行数は増えるが、提出者(人数)は1名のまま
        results = compare_stages(
            _s(
                portal_total=8,
                extracted=8,
                sheet_rows=8,
                firestore_count=8,
                submitted_display=7,
                independent=7,
            )
        )
        assert exit_code(results) == 0


class TestRenderAndHelpers:
    def test_render_shows_numbers_and_no_free_text(self):
        out = render("01", "課題②", compare_stages(_s()))
        assert "№01" in out and "課題②" in out and "PASS" in out

    def test_render_includes_the_hint_for_failures(self):
        out = render("01", "課題②", compare_stages(_s(sheet_rows=6)))
        assert "FAIL" in out and "Sheets追記" in out

    def test_find_class_name_uses_the_known_class_list(self):
        assert find_class_name("01").endswith("№01")
        assert "研修" in find_class_name("01")

    def test_find_class_name_unknown_raises(self):
        import pytest

        with pytest.raises(ValueError):
            find_class_name("99")


class TestWiring:
    """main(): 取得層を差し替えて、各段の値が正しい比較に渡ることと終了コードを確認する。"""

    def _run(
        self, monkeypatch, capsys, *, summary, rows=(7, 0), firestore=7, facts=None
    ):
        import verify_task_rollout as v

        monkeypatch.setattr(
            sys, "argv", ["verify_task_rollout.py", "--class", "01", "--task", "課題②"]
        )
        monkeypatch.setattr(v, "fetch_events", lambda hours: [])
        monkeypatch.setattr(v, "summarize", lambda events, c, t, now: summary)
        monkeypatch.setattr(v, "fetch_sheet_rows", lambda c, t: rows)
        monkeypatch.setattr(v, "fetch_firestore_file_count", lambda c, t: firestore)
        monkeypatch.setattr(
            v,
            "gather_facts",
            lambda c, t: facts or {"_submitted": 7, "_independent": 7},
        )
        code = v.main()
        return code, capsys.readouterr().out

    def test_all_stages_match_is_exit_0(self, monkeypatch, capsys):
        code, out = self._run(
            monkeypatch,
            capsys,
            summary={"outcome": "OK", "extracted": 7, "total": 7, "started": "t"},
        )
        assert code == 0 and "FAIL" not in out and "UNKNOWN" not in out

    def test_sheet_rows_mismatch_is_exit_1(self, monkeypatch, capsys):
        code, out = self._run(
            monkeypatch,
            capsys,
            summary={"outcome": "OK", "extracted": 7, "total": 7, "started": "t"},
            rows=(6, 0),
        )
        assert code == 1 and "Sheets追記" in out

    def test_zero_confirmed_compares_as_zero_everywhere(self, monkeypatch, capsys):
        code, _ = self._run(
            monkeypatch,
            capsys,
            summary={"outcome": "ZERO_CONFIRMED", "started": "t"},
            rows=(0, 0),
            firestore=0,
            facts={"_submitted": 0, "_independent": 0},
        )
        assert code == 0

    def test_running_collection_is_unknown_not_a_pass(self, monkeypatch, capsys):
        code, _ = self._run(
            monkeypatch, capsys, summary={"outcome": "RUNNING", "started": "t"}
        )
        assert code == 2

    def test_unreadable_sheet_is_unknown(self, monkeypatch, capsys):
        code, _ = self._run(
            monkeypatch,
            capsys,
            summary={"outcome": "OK", "extracted": 7, "total": 7, "started": "t"},
            rows=(None, None),
        )
        assert code == 2

    def test_fetch_failure_is_exit_2(self, monkeypatch, capsys):
        import verify_task_rollout as v

        monkeypatch.setattr(
            sys, "argv", ["verify_task_rollout.py", "--class", "01", "--task", "課題②"]
        )

        def boom(hours):
            raise RuntimeError("gcloud失敗")

        monkeypatch.setattr(v, "fetch_events", boom)
        assert v.main() == 2

    def test_unknown_class_is_exit_2(self, monkeypatch, capsys):
        import verify_task_rollout as v

        monkeypatch.setattr(
            sys, "argv", ["verify_task_rollout.py", "--class", "99", "--task", "課題②"]
        )
        assert v.main() == 2

    def test_output_never_contains_free_text(self, monkeypatch, capsys):
        _, out = self._run(
            monkeypatch,
            capsys,
            summary={"outcome": "OK", "extracted": 7, "total": 7, "started": "t"},
        )
        assert "№01" in out and "課題②" in out
        assert "山田" not in out


class TestFetchHelpers:
    def test_firestore_404_means_no_records_yet(self, monkeypatch):
        import urllib.error

        import verify_task_rollout as v

        class _Proc:
            stdout = "tok\n"

        monkeypatch.setattr(v.subprocess, "run", lambda *a, **k: _Proc())

        def raise_404(*a, **k):
            raise urllib.error.HTTPError("u", 404, "nf", None, None)

        monkeypatch.setattr(v.urllib.request, "urlopen", raise_404)
        assert v.fetch_firestore_file_count("01", "課題②") == 0

    def test_firestore_other_failure_is_unknown(self, monkeypatch):
        import urllib.error

        import verify_task_rollout as v

        class _Proc:
            stdout = "tok\n"

        monkeypatch.setattr(v.subprocess, "run", lambda *a, **k: _Proc())

        def raise_403(*a, **k):
            raise urllib.error.HTTPError("u", 403, "forbidden", None, None)

        monkeypatch.setattr(v.urllib.request, "urlopen", raise_403)
        assert v.fetch_firestore_file_count("01", "課題②") is None

    def test_sheet_rows_counts_rows_and_duplicate_keys(self, monkeypatch):
        import verify_task_rollout as v

        monkeypatch.setattr(
            v,
            "_get_values",
            lambda b, sid, rng: [
                ["課題②", "k1", "n", "d1"],
                ["課題②", "k2", "n", "d2"],
                ["課題②", "k2", "n", "d2"],
                [],
            ],
        )
        assert v.fetch_sheet_rows("01", "課題②") == (3, 1)

    def test_sheet_rows_unreadable_tab_is_none(self, monkeypatch):
        import verify_task_rollout as v

        def boom(*a, **k):
            raise RuntimeError("no tab")

        monkeypatch.setattr(v, "_get_values", boom)
        assert v.fetch_sheet_rows("01", "課題②") == (None, None)
