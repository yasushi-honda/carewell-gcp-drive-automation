"""
Unit tests for scripts/restore_manual_cells.py の純粋関数。

出欠確認表の課題列で、数式のセルに直接入力された値(講義中の手入力など)を検出し、
「提出」「未提出」だけを数式へ戻す対象にする。それ以外の内容は自動で上書きしない。
ネットワーク呼び出し(Sheets API)を含む関数は対象外。
"""

import sys

sys.path.insert(0, "scripts")

from apply_submission_formulas import build_status_formula  # noqa: E402
import pytest  # noqa: E402

import restore_manual_cells as rmc  # noqa: E402
from restore_manual_cells import (  # noqa: E402
    classify_manual_cells,
    find_display_mismatch,
    find_unexpected_display,
    find_unrestored,
    task_tab_wiring_issues,
)

LABEL = "課題①"


def _f(row):
    return build_status_formula(row, LABEL)


class TestClassifyManualCells:
    def test_no_conflicts_when_all_formulas(self):
        existing = {5: _f(5), 6: _f(6)}
        r = classify_manual_cells(existing, [5, 6], LABEL)
        assert r["restorable"] == [] and r["other"] == []

    def test_empty_cells_are_not_manual_input(self):
        existing = {5: "", 6: _f(6)}
        r = classify_manual_cells(existing, [5, 6], LABEL)
        assert r["restorable"] == [] and r["other"] == []

    def test_submitted_literal_is_restorable(self):
        existing = {5: "提出", 6: _f(6)}
        r = classify_manual_cells(existing, [5, 6], LABEL)
        assert r["restorable"] == [(5, "提出")]
        assert r["other"] == []

    def test_not_submitted_literal_is_restorable(self):
        r = classify_manual_cells({7: "未提出"}, [7], LABEL)
        assert r["restorable"] == [(7, "未提出")]

    def test_literal_with_surrounding_whitespace_is_restorable(self):
        r = classify_manual_cells({7: " 提出 "}, [7], LABEL)
        assert r["restorable"] == [(7, "提出")]

    def test_other_text_is_reported_not_restorable(self):
        r = classify_manual_cells({5: "遅刻のため後日提出"}, [5], LABEL)
        assert r["restorable"] == []
        assert r["other"] == [5]

    def test_different_formula_is_reported_not_restorable(self):
        r = classify_manual_cells({5: '=IF(C5="","","提出")'}, [5], LABEL)
        assert r["restorable"] == []
        assert r["other"] == [5]

    def test_rows_outside_student_rows_are_ignored(self):
        r = classify_manual_cells({5: "提出", 99: "提出"}, [5], LABEL)
        assert r["restorable"] == [(5, "提出")]

    def test_missing_row_in_existing_is_treated_as_empty(self):
        r = classify_manual_cells({}, [5, 6], LABEL)
        assert r["restorable"] == [] and r["other"] == []

    def test_mixed_rows_keep_row_order(self):
        existing = {9: "提出", 5: "メモ", 7: "未提出", 6: _f(6)}
        r = classify_manual_cells(existing, [5, 6, 7, 9], LABEL)
        assert r["restorable"] == [(7, "未提出"), (9, "提出")]
        assert r["other"] == [5]


class TestFindUnrestored:
    def test_all_restored_returns_empty(self):
        after = {5: _f(5), 7: _f(7)}
        assert find_unrestored(after, [5, 7], LABEL) == []

    def test_literal_remaining_is_reported(self):
        after = {5: "提出", 7: _f(7)}
        assert find_unrestored(after, [5, 7], LABEL) == [5]

    def test_cleared_cell_is_reported(self):
        after = {5: "", 7: _f(7)}
        assert find_unrestored(after, [5, 7], LABEL) == [5]

    def test_changed_to_note_is_reported(self):
        after = {5: "メモ", 7: _f(7)}
        assert find_unrestored(after, [5, 7], LABEL) == [5]

    def test_changed_to_other_formula_is_reported(self):
        after = {5: '=IF(C5="","","提出")', 7: _f(7)}
        assert find_unrestored(after, [5, 7], LABEL) == [5]

    def test_missing_row_is_reported(self):
        assert find_unrestored({7: _f(7)}, [5, 7], LABEL) == [5]

    def test_returns_sorted_rows(self):
        assert find_unrestored({}, [9, 5, 7], LABEL) == [5, 7, 9]


class TestFindUnexpectedDisplay:
    def test_expected_values_return_empty(self):
        assert find_unexpected_display({5: "提出", 7: "未提出"}, [5, 7]) == []

    def test_error_value_is_reported(self):
        assert find_unexpected_display({5: "#REF!", 7: "提出"}, [5, 7]) == [5]

    def test_empty_display_is_reported(self):
        assert find_unexpected_display({5: "", 7: "提出"}, [5, 7]) == [5]

    def test_missing_row_is_reported(self):
        assert find_unexpected_display({7: "提出"}, [5, 7]) == [5]

    def test_whitespace_around_expected_value_is_accepted(self):
        assert find_unexpected_display({5: " 提出 "}, [5]) == []

    def test_returns_sorted_rows(self):
        assert find_unexpected_display({}, [9, 5]) == [5, 9]


class TestValueShapes:
    """Sheets APIが実際に返しうる値(全角空白・数値・None・長い文)の扱いを固定する。"""

    @pytest.mark.parametrize("value", ["　提出", "提出　", "提出\n", " 未提出 "])
    def test_whitespace_variants_of_literal_are_restorable(self, value):
        r = classify_manual_cells({5: value}, [5], LABEL)
        assert r["restorable"] == [(5, value.strip())]

    @pytest.mark.parametrize(
        "value",
        [
            "提出済",
            "提出。",
            "提 出",
            "✓",
            '="提出"',
            "'提出",
            "未提出のため後日",
            1,
            0,
            True,
        ],
    )
    def test_non_exact_values_are_reported_not_restored(self, value):
        r = classify_manual_cells({5: value}, [5], LABEL)
        assert r["restorable"] == []
        assert r["other"] == [5]

    @pytest.mark.parametrize("value", [None, "", " ", "　"])
    def test_blank_values_are_not_detected(self, value):
        r = classify_manual_cells({5: value}, [5], LABEL)
        assert r == {"restorable": [], "other": []}

    def test_unsorted_student_rows_give_sorted_result(self):
        r = classify_manual_cells(
            {5: "提出", 7: "未提出", 9: "メモ", 8: "メモ"}, [9, 7, 8, 5], LABEL
        )
        assert r["restorable"] == [(5, "提出"), (7, "未提出")]
        assert r["other"] == [8, 9]

    def test_empty_student_rows(self):
        assert classify_manual_cells({5: "提出"}, [], LABEL) == {
            "restorable": [],
            "other": [],
        }

    def test_formula_of_other_label_is_a_conflict(self):
        other = build_status_formula(5, "課題②")
        assert classify_manual_cells({5: other}, [5], "課題①")["other"] == [5]
        assert classify_manual_cells({5: other}, [5], "課題②") == {
            "restorable": [],
            "other": [],
        }

    def test_expected_formula_literal_is_fixed(self):
        assert _f(5) == (
            '=IF(C5="","",IF(COUNTIF(\'課題①\'!C:C,C5)=0,"未提出","提出"))'
        )


class TestFindUnrestoredShapes:
    def test_leading_space_formula_is_unrestored(self):
        assert find_unrestored({5: " " + _f(5)}, [5], LABEL) == [5]

    def test_formula_of_other_label_is_unrestored(self):
        assert find_unrestored({5: build_status_formula(5, "課題②")}, [5], "課題①") == [
            5
        ]

    def test_empty_targets_pass(self):
        assert find_unrestored({5: "メモ"}, [], LABEL) == []


class TestFindUnexpectedDisplayShapes:
    @pytest.mark.parametrize(
        "value", ["#N/A", "#REF!", "Loading...", "✓", "提出済み", 1, None]
    )
    def test_unexpected_values_are_reported(self, value):
        assert find_unexpected_display({5: value}, [5]) == [5]

    def test_fullwidth_space_around_expected_is_accepted(self):
        assert find_unexpected_display({5: "提出　"}, [5]) == []

    def test_empty_targets_pass(self):
        assert find_unexpected_display({}, []) == []


class TestFindDisplayMismatch:
    """復元後の表示が、手入力の元の値と同じかを行ごとに比べる。"""

    def test_same_values_return_empty(self):
        assert (
            find_display_mismatch(
                {5: "提出", 7: "未提出"}, [(5, "提出"), (7, "未提出")]
            )
            == []
        )

    def test_changed_value_is_reported(self):
        assert find_display_mismatch({5: "未提出"}, [(5, "提出")]) == [5]

    def test_whitespace_is_ignored(self):
        assert find_display_mismatch({5: "提出　"}, [(5, "提出")]) == []

    def test_missing_row_is_reported(self):
        assert find_display_mismatch({}, [(5, "提出")]) == [5]

    def test_returns_sorted_rows(self):
        out = find_display_mismatch({}, [(9, "提出"), (5, "提出")])
        assert out == [5, 9]


class TestTaskTabWiringIssues:
    """管理側の課題タブのA1(IMPORTRANGE)・C1(XLOOKUP)が期待どおりか。"""

    def _ok(self):
        return (rmc.a.build_import_formula("SUBID", LABEL), rmc.a.XLOOKUP_FORMULA)

    def test_expected_wiring_has_no_issue(self):
        a1, c1 = self._ok()
        assert task_tab_wiring_issues(a1, c1, "SUBID", LABEL) == []

    def test_empty_a1_is_reported(self):
        _, c1 = self._ok()
        assert task_tab_wiring_issues("", c1, "SUBID", LABEL) != []

    def test_empty_c1_is_reported(self):
        a1, _ = self._ok()
        assert task_tab_wiring_issues(a1, "", "SUBID", LABEL) != []

    def test_wrong_source_in_a1_is_reported(self):
        a1 = rmc.a.build_import_formula("OTHER", LABEL)
        _, c1 = self._ok()
        assert task_tab_wiring_issues(a1, c1, "SUBID", LABEL) != []

    def test_none_values_are_reported(self):
        assert task_tab_wiring_issues(None, None, "SUBID", LABEL) != []


@pytest.fixture
def fake(monkeypatch, tmp_path):
    """process_classのI/Oを差し替え、書込みと呼び出しを記録する(Sheets APIには触れない)。"""
    calls = {"write": [], "backup": 0, "displayed": 0}
    state = {
        "existing": {5: "提出"},
        "after": {5: _f(5)},
        "displayed": {5: "提出"},
        "titles": [LABEL],
        "a1c1": None,
        "rows": None,
        "recheck": None,
        "write_error": None,
    }
    reads = {"n": 0}

    def read_state(class_num, label):
        # 1回目=検出、2回目=書込み直前の再確認、3回目以降=書込み後の読み戻し
        reads["n"] += 1
        if reads["n"] == 1:
            existing = state["existing"]
        elif reads["n"] == 2:
            existing = (
                state["recheck"] if state["recheck"] is not None else state["existing"]
            )
        else:
            existing = state["after"]
        rows = state["rows"]
        if rows is None:
            rows = sorted(set(state["existing"]) | set(state["after"]))
        return ("ATT", "TAB", "I", rows, existing)

    def read_displayed(att_id, att_tab, task_col):
        calls["displayed"] += 1
        return state["displayed"]

    def write_backup(class_num, label, att_id, att_tab, task_col, cells):
        calls["backup"] += 1
        return tmp_path / "backup.json"

    def write_formulas(att, tab, col, writes):
        calls["write"].append(writes)
        if state["write_error"]:
            raise state["write_error"]

    ok = (rmc.a.build_import_formula("SUBID", LABEL), rmc.a.XLOOKUP_FORMULA)
    monkeypatch.setattr(rmc, "_read_state", read_state)
    monkeypatch.setattr(rmc, "_read_displayed", read_displayed)
    monkeypatch.setattr(rmc, "_write_backup", write_backup)
    monkeypatch.setattr(
        rmc, "_read_task_tab_a1c1", lambda att_id, label: state["a1c1"] or ok
    )
    monkeypatch.setattr(rmc, "_submission_id", lambda class_num: "SUBID")
    monkeypatch.setattr(rmc.a, "_list_titles", lambda build_fn, sid: state["titles"])
    monkeypatch.setattr(rmc.a, "_write_status_formulas", write_formulas)
    monkeypatch.setattr(rmc.time, "sleep", lambda s: None)
    return calls, state


class TestProcessClass:
    def test_no_manual_cells_returns_zero(self, fake):
        calls, state = fake
        state["existing"] = {5: _f(5)}
        assert rmc.process_class("07", LABEL, commit=True) == 0
        assert calls["write"] == [] and calls["backup"] == 0

    def test_dry_run_detects_but_never_writes(self, fake):
        calls, _ = fake
        assert rmc.process_class("07", LABEL, commit=False) == 1
        assert calls["write"] == [] and calls["backup"] == 0

    def test_commit_with_only_other_content_holds(self, fake):
        calls, state = fake
        state["existing"] = {5: "メモ"}
        assert rmc.process_class("07", LABEL, commit=True) == 1
        assert calls["write"] == [] and calls["backup"] == 0

    def test_missing_task_tab_holds_before_backup_and_write(self, fake):
        calls, state = fake
        state["titles"] = ["別タブ"]
        assert rmc.process_class("07", LABEL, commit=True) == 1
        assert calls["write"] == [] and calls["backup"] == 0

    def test_unwired_task_tab_holds_before_backup_and_write(self, fake):
        calls, state = fake
        state["a1c1"] = ("", "")
        assert rmc.process_class("07", LABEL, commit=True) == 1
        assert calls["write"] == [] and calls["backup"] == 0

    def test_success_writes_only_restorable_rows(self, fake):
        calls, _ = fake
        assert rmc.process_class("07", LABEL, commit=True) == 0
        assert calls["write"] == [[(5, _f(5))]]
        assert calls["backup"] == 1

    def test_other_content_remaining_returns_one_even_if_restore_succeeds(self, fake):
        calls, state = fake
        state["existing"] = {5: "提出", 6: "メモ"}
        state["after"] = {5: _f(5), 6: "メモ"}
        state["displayed"] = {5: "提出"}
        assert rmc.process_class("07", LABEL, commit=True) == 1
        assert calls["write"] == [[(5, _f(5))]]

    def test_readback_not_formula_fails(self, fake):
        _, state = fake
        state["after"] = {5: "提出"}
        assert rmc.process_class("07", LABEL, commit=True) == 2

    def test_display_that_never_settles_fails_after_three_reads(self, fake):
        calls, state = fake
        state["displayed"] = {5: "Loading..."}
        assert rmc.process_class("07", LABEL, commit=True) == 2
        assert calls["displayed"] == 3

    def test_display_that_settles_on_second_read_succeeds(self, fake, monkeypatch):
        calls, state = fake
        seq = iter([{5: "Loading..."}, {5: "提出"}])

        def read_displayed(att_id, att_tab, task_col):
            calls["displayed"] += 1
            return next(seq)

        monkeypatch.setattr(rmc, "_read_displayed", read_displayed)
        assert rmc.process_class("07", LABEL, commit=True) == 0
        assert calls["displayed"] == 2

    def test_display_that_differs_from_manual_value_fails(self, fake):
        _, state = fake
        state["displayed"] = {
            5: "未提出"
        }  # 手入力は「提出」だったが、数式の結果は「未提出」
        assert rmc.process_class("07", LABEL, commit=True) == 2

    def test_no_student_rows_fails_instead_of_reporting_clean(self, fake):
        calls, state = fake
        state["rows"] = []
        assert rmc.process_class("07", LABEL, commit=False) == 2
        assert calls["write"] == [] and calls["backup"] == 0

    def test_cells_changed_between_reads_hold_without_writing(self, fake):
        calls, state = fake
        state["recheck"] = {5: "メモに書き換えられた"}
        assert rmc.process_class("07", LABEL, commit=True) == 1
        assert calls["write"] == [] and calls["backup"] == 0

    def test_exception_after_write_reports_written_state(self, fake, capsys):
        calls, state = fake
        state["write_error"] = RuntimeError("氏名を含む可能性のある例外メッセージ")
        assert rmc.process_class("07", LABEL, commit=True) == 2
        out = capsys.readouterr().out
        assert "書込み済み" in out and "backup.json" in out
        assert "氏名" not in out
        assert calls["backup"] == 1

    def test_backup_is_written_before_the_sheet_is_changed(self, fake, monkeypatch):
        calls, _ = fake
        order = []
        monkeypatch.setattr(
            rmc, "_write_backup", lambda *args: order.append("backup") or "b"
        )
        monkeypatch.setattr(
            rmc.a, "_write_status_formulas", lambda *args: order.append("write")
        )
        rmc.process_class("07", LABEL, commit=True)
        assert order[:2] == ["backup", "write"]


class TestMain:
    def test_commit_without_class_is_rejected(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["restore_manual_cells.py", "--commit"])
        assert rmc.main() == 1
        assert "--class" in capsys.readouterr().out

    def test_unknown_class_is_rejected(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["restore_manual_cells.py", "--class", "99"])
        assert rmc.main() == 1

    def test_exception_in_one_class_returns_two_and_continues(
        self, monkeypatch, capsys
    ):
        seen = []

        def boom(cn, label, commit):
            seen.append(cn)
            if cn == rmc.a.TARGET_CLASSES[0]:
                raise RuntimeError("氏名を含む可能性のある例外メッセージ")
            return 0

        monkeypatch.setattr(sys, "argv", ["restore_manual_cells.py"])
        monkeypatch.setattr(rmc, "process_class", boom)
        assert rmc.main() == 2
        out = capsys.readouterr().out
        assert "RuntimeError" in out and "氏名" not in out
        assert seen == list(rmc.a.TARGET_CLASSES)

    def test_worst_return_code_is_returned(self, monkeypatch):
        codes = iter([0, 1, 0] + [0] * 20)
        monkeypatch.setattr(sys, "argv", ["restore_manual_cells.py"])
        monkeypatch.setattr(rmc, "process_class", lambda cn, label, commit: next(codes))
        assert rmc.main() == 1
