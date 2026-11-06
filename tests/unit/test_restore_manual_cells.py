"""
Unit tests for scripts/restore_manual_cells.py の純粋関数。

出欠確認表の課題列で、数式のセルに直接入力された値(講義中の手入力など)を検出し、
「提出」「未提出」だけを数式へ戻す対象にする。それ以外の内容は自動で上書きしない。
ネットワーク呼び出し(Sheets API)を含む関数は対象外。
"""

import sys

sys.path.insert(0, "scripts")

from apply_submission_formulas import build_status_formula  # noqa: E402
from restore_manual_cells import classify_manual_cells, find_unrestored  # noqa: E402

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
