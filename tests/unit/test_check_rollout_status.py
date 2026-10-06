"""
Unit tests for scripts/check_rollout_status.py の純粋関数(状態分類・終了コード)。

ネットワーク呼び出し(Sheets API)を含む関数は対象外。
"""

import sys

sys.path.insert(0, "scripts")

from check_rollout_status import (  # noqa: E402
    STATE_DONE,
    STATE_HOLD,
    STATE_REGRESSION,
    STATE_REVIEW,
    STATE_TODO,
    classify_class,
    compare_source_to_roster,
    exit_code,
)


def _facts(**over):
    base = {
        "class": "03",
        "expected_registered": True,
        "source_count": 254,
        "roster_count": 254,
        "mapping_issues": [],
        "source_issues": [],
        "sub_task_tab": True,
        "admin_task_tab": True,
        "formulas": "all",
        "sub_hidden": True,
        "admin_hidden": True,
        "admin_protected": True,
        "roster_hidden": True,
        "roster_protected": True,
        "tally_issues": [],
        "expected_count": 254,
        "link_issues": [],
    }
    base.update(over)
    return base


class TestClassifyClass:
    def test_all_done(self):
        state, action = classify_class(_facts())
        assert state == STATE_DONE

    def test_roster_not_arrived_is_planned_hold(self):
        state, action = classify_class(
            _facts(source_count=0, roster_count=0, expected_registered=False)
        )
        assert state == STATE_HOLD
        assert "名簿" in action

    def test_source_arrived_but_roster_empty_is_todo(self):
        state, action = classify_class(
            _facts(source_count=254, roster_count=0, expected_registered=False)
        )
        assert state == STATE_TODO
        assert "merge_student_roster" in action

    def test_roster_present_but_expected_count_unregistered_is_todo(self):
        state, action = classify_class(_facts(expected_registered=False))
        assert state == STATE_TODO
        assert "EXPECTED_STUDENT_COUNT_BY_CLASS" in action

    def test_no_submission_tab_is_todo_with_provision_hint(self):
        state, action = classify_class(
            _facts(sub_task_tab=False, admin_task_tab=False, formulas="none")
        )
        assert state == STATE_TODO
        assert "--provision-submission-tab" in action

    def test_submission_tab_present_but_no_formulas_is_todo(self):
        state, action = classify_class(_facts(admin_task_tab=False, formulas="none"))
        assert state == STATE_TODO
        assert "apply_submission_formulas" in action

    def test_partial_formulas_is_todo(self):
        state, _ = classify_class(_facts(formulas="partial"))
        assert state == STATE_TODO

    def test_missing_protection_is_todo(self):
        state, action = classify_class(_facts(admin_protected=False))
        assert state == STATE_TODO
        assert "hide_sensitive_sheets" in action

    def test_submission_tab_visible_is_todo(self):
        state, _ = classify_class(_facts(sub_hidden=False))
        assert state == STATE_TODO

    def test_mapping_issue_is_regression(self):
        state, _ = classify_class(_facts(mapping_issues=["番号が不一致"]))
        assert state == STATE_REGRESSION

    def test_source_updated_after_import_is_review_not_regression(self):
        # 正本リストの取込み後更新は情報的な差分。数式・集計の退行ではない。
        state, action = classify_class(_facts(source_issues=["2件不一致"]))
        assert state == STATE_REVIEW
        assert "正本" in action

    def test_review_is_lower_priority_than_todo(self):
        state, _ = classify_class(_facts(source_issues=["x"], admin_protected=False))
        assert state == STATE_TODO

    def test_roster_count_differs_from_expected_is_regression(self):
        state, action = classify_class(_facts(roster_count=250, expected_count=254))
        assert state == STATE_REGRESSION
        assert "期待人数" in action

    def test_broken_link_is_regression_even_when_all_unsubmitted(self):
        # 提出0件では出欠確認の表示も独立集計も一致してしまうため、A1/C1を直接見る
        state, action = classify_class(
            _facts(link_issues=["A1が期待のIMPORTRANGE式でない"], _submitted=0)
        )
        assert state == STATE_REGRESSION
        assert "連携" in action

    def test_done_with_zero_submissions_says_end_to_end_pending(self):
        state, action = classify_class(_facts(_submitted=0))
        assert state == STATE_DONE
        assert "最初の実提出後" in action

    def test_done_with_submissions_has_no_pending_note(self):
        state, action = classify_class(_facts(_submitted=25))
        assert (state, action) == (STATE_DONE, "-")

    def test_tally_issue_is_regression(self):
        state, _ = classify_class(_facts(tally_issues=["独立集計不一致"]))
        assert state == STATE_REGRESSION

    def test_regression_takes_priority_over_todo(self):
        state, _ = classify_class(_facts(mapping_issues=["x"], admin_protected=False))
        assert state == STATE_REGRESSION


class TestExitCode:
    def test_all_done_or_hold_is_zero(self):
        assert exit_code([STATE_DONE, STATE_HOLD, STATE_HOLD]) == 0

    def test_todo_is_nonzero(self):
        assert exit_code([STATE_DONE, STATE_TODO]) == 1

    def test_regression_is_nonzero(self):
        assert exit_code([STATE_REGRESSION]) == 1

    def test_empty_is_zero(self):
        assert exit_code([]) == 0

    def test_review_only_is_zero(self):
        # 情報的な差分で毎回異常にしない(本物の退行を埋もれさせない)
        assert exit_code([STATE_DONE, STATE_REVIEW]) == 0


class TestCompareSourceToRoster:
    # 正本: [グループ, サブ講師, 受講者番号, 氏名, ふりがな, ...]
    # 名簿: A氏名, B ふりがな, C日介番号, ..., H グループ, I, J 受講者番号
    def _src(self, group="A", number="A001", name="山田 太郎", kana="やまだ たろう"):
        return [group, "先生", number, name, kana, "施設", ""]

    def _ros(self, group="A", number="A001", name="山田 太郎", kana="やまだ たろう"):
        return [name, kana, "N1", "", "", "施設", "入所系居住系", group, number, number]

    def test_identical_is_ok(self):
        assert compare_source_to_roster([self._src()], [self._ros()]) == []

    def test_fullwidth_group_is_equivalent(self):
        assert compare_source_to_roster([self._src(group="Ａ")], [self._ros()]) == []

    def test_group_change_detected(self):
        issues = compare_source_to_roster([self._src(group="B")], [self._ros()])
        assert issues

    def test_name_change_detected(self):
        issues = compare_source_to_roster([self._src(name="別人 花子")], [self._ros()])
        assert issues

    def test_number_added_in_source_detected(self):
        issues = compare_source_to_roster(
            [
                self._src(),
                self._src(number="A002", name="佐藤 一郎", kana="さとう いちろう"),
            ],
            [self._ros()],
        )
        assert issues

    def test_issue_messages_contain_no_names(self):
        issues = compare_source_to_roster([self._src(name="別人 花子")], [self._ros()])
        assert all("花子" not in i and "山田" not in i for i in issues)

    def test_service_type_change_detected(self):
        src = self._src()
        src[5] = "別の施設種別"
        issues = compare_source_to_roster([src], [self._ros()])
        assert any("サービス種別" in i for i in issues)

    def test_service_type_change_message_has_no_values(self):
        src = self._src()
        src[5] = "別の施設種別"
        issues = compare_source_to_roster([src], [self._ros()])
        assert all("別の施設種別" not in i for i in issues)

    def test_blank_rows_are_ignored(self):
        assert (
            compare_source_to_roster(
                [self._src(), ["", "", "", "", "", "", ""]], [self._ros()]
            )
            == []
        )
