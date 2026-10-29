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
    count_company_office_filled,
    describe_error,
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
        "company_office_filled": 0,
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


class TestCompanyOfficeColumns:
    """受講者リストの会社・事業所欄(D・E列)は個人情報保護のため常に空欄でなければならない。
    2026-09-18: 取込みスクリプトの仕様で実データが復活していたのに「対応完了」と報告していた。"""

    def test_filled_columns_are_regression(self):
        state, action = classify_class(_facts(company_office_filled=3))
        assert state == STATE_REGRESSION
        assert "会社・事業所" in action
        assert "3" in action

    def test_pii_regression_wins_over_everything_else(self):
        state, action = classify_class(
            _facts(
                company_office_filled=1,
                mapping_issues=["番号不一致"],
                roster_count=250,
                expected_count=254,
            )
        )
        assert "会社・事業所" in action

    def test_detected_even_when_roster_is_not_imported_yet(self):
        # 受講者番号が空(未取込み)でも、D・E列に値があれば「予定された保留」にしない
        state, action = classify_class(
            _facts(
                roster_count=0,
                source_count=0,
                expected_registered=False,
                company_office_filled=2,
            )
        )
        assert state == STATE_REGRESSION
        assert "会社・事業所" in action

    def test_empty_columns_do_not_affect_a_done_class(self):
        assert classify_class(_facts(company_office_filled=0))[0] == STATE_DONE

    def test_missing_key_defaults_to_clean(self):
        facts = _facts()
        facts.pop("company_office_filled")
        assert classify_class(facts)[0] == STATE_DONE

    def test_action_does_not_contain_values(self):
        _, action = classify_class(_facts(company_office_filled=2))
        assert "社会福祉法人" not in action


class TestCountCompanyOfficeFilled:
    def test_counts_rows_with_any_value_in_d_or_e(self):
        rows = [
            ["山田", "やまだ", "N1", "社会福祉法人", "", "施設"],
            ["佐藤", "さとう", "N2", "", "A事業所", "施設"],
            ["鈴木", "すずき", "N3", "", "", "施設"],
            ["高橋", "たかはし", "N4", "  ", " ", "施設"],
        ]
        assert count_company_office_filled(rows) == 2

    def test_short_rows_are_clean(self):
        assert count_company_office_filled([["山田", "やまだ", "N1"]]) == 0

    def test_empty(self):
        assert count_company_office_filled([]) == 0


class TestClassifyPriorityAndGaps:
    def test_registered_class_with_emptied_roster_is_regression(self):
        state, action = classify_class(
            _facts(roster_count=0, source_count=0, expected_registered=True)
        )
        assert state == STATE_REGRESSION
        assert "空" in action

    def test_registered_class_with_emptied_roster_even_if_source_remains(self):
        state, _ = classify_class(
            _facts(roster_count=0, source_count=254, expected_registered=True)
        )
        assert state == STATE_REGRESSION

    def test_mapping_issue_wins_over_expected_count_mismatch(self):
        state, action = classify_class(
            _facts(mapping_issues=["番号不一致"], roster_count=250, expected_count=254)
        )
        assert "受講者番号が不一致" in action

    def test_expected_count_wins_over_link_issue(self):
        state, action = classify_class(
            _facts(roster_count=250, expected_count=254, link_issues=["A1"])
        )
        assert "期待人数" in action

    def test_link_issue_wins_over_tally_issue(self):
        state, action = classify_class(
            _facts(link_issues=["A1が期待のIMPORTRANGE式でない"], tally_issues=["x"])
        )
        assert "連携" in action

    def test_unregistered_expected_count_is_todo_not_regression(self):
        state, action = classify_class(
            _facts(expected_registered=False, expected_count=None)
        )
        assert state == STATE_TODO
        assert "EXPECTED_STUDENT_COUNT_BY_CLASS" in action

    def test_each_hide_protect_flag_alone_is_todo(self):
        for flag in (
            "admin_hidden",
            "admin_protected",
            "roster_hidden",
            "roster_protected",
            "sub_hidden",
        ):
            state, action = classify_class(_facts(**{flag: False}))
            assert state == STATE_TODO, flag
            assert "hide_sensitive_sheets.py --class 03" in action

    def test_multiple_missing_items_are_all_listed(self):
        _, action = classify_class(
            _facts(sub_hidden=False, admin_protected=False, roster_hidden=False)
        )
        assert action.count("; ") >= 2

    def test_formulas_all_but_admin_tab_missing_is_todo(self):
        state, action = classify_class(_facts(admin_task_tab=False))
        assert state == STATE_TODO
        assert "apply_submission_formulas" in action

    def test_review_wins_over_zero_submission_note(self):
        state, action = classify_class(_facts(source_issues=["x"], _submitted=0))
        assert state == STATE_REVIEW
        assert "最初の実提出後" not in action

    def test_commands_carry_the_class_number(self):
        _, action = classify_class(_facts(**{"class": "07"}, admin_protected=False))
        assert "--class 07" in action


class TestDescribeError:
    def test_http_error_shows_status_only(self):
        from googleapiclient.errors import HttpError

        class R:
            status = 429
            reason = "Too Many Requests"

        e = HttpError(R(), '{"error":{"message":"氏名 山田 太郎 を含みうる"}}'.encode())
        text = describe_error(e)
        assert "429" in text and "山田" not in text

    def test_validation_error_message_is_shown_and_truncated(self):
        from merge_student_roster import ValidationError

        text = describe_error(
            ValidationError("見出し行に「課題①」が0件あります" + "x" * 500)
        )
        assert "課題①" in text and len(text) < 220

    def test_unexpected_error_is_labelled_as_possible_bug(self):
        assert "想定外" in describe_error(TypeError("boom"))


class TestExitCode:
    def test_all_done_or_hold_is_zero(self):
        assert exit_code([STATE_DONE, STATE_HOLD, STATE_HOLD]) == 0

    def test_todo_is_nonzero(self):
        assert exit_code([STATE_DONE, STATE_TODO]) == 1

    def test_regression_is_nonzero(self):
        assert exit_code([STATE_REGRESSION]) == 1

    def test_empty_is_zero(self):
        assert exit_code([]) == 0

    def test_unknown_state_fails_closed(self):
        # 新しい状態を足して分岐を書き忘れても、異常を成功終了にしない
        assert exit_code(["未知の状態"]) == 1

    def test_review_only_is_zero(self):
        # 情報的な差分で毎回異常にしない(本物の退行を埋もれさせない)
        assert exit_code([STATE_DONE, STATE_REVIEW]) == 0


class TestCompareSourceToRoster:
    # 正本: [グループ, サブ講師, 受講者番号, 氏名, ふりがな, ...]
    # 名簿: A氏名, B ふりがな, C日介番号, ..., H グループ, I, J 受講者番号
    def _src(self, group="A", number="A001", name="山田 太郎", kana="やまだ たろう"):
        return [group, "先生", number, name, kana, "施設", ""]

    def _ros(self, group="A", number="A001", name="山田 太郎", kana="やまだ たろう"):
        # I列(index 8)には、J列(受講者番号, index 9)と別の値を入れ、列の読み違えを検出する
        return [
            name,
            kana,
            "N1",
            "",
            "",
            "施設",
            "入所系居住系",
            group,
            "X" + number,
            number,
        ]

    def test_identical_is_ok(self):
        assert compare_source_to_roster([self._src()], [self._ros()]) == []

    def test_fullwidth_group_is_equivalent(self):
        assert compare_source_to_roster([self._src(group="Ａ")], [self._ros()]) == []

    def test_group_change_detected(self):
        issues = compare_source_to_roster([self._src(group="B")], [self._ros()])
        assert issues == ["グループまたは氏名が取込み後に変わった受講者が1件"]

    def test_name_change_detected(self):
        issues = compare_source_to_roster([self._src(name="別人 花子")], [self._ros()])
        assert issues == ["グループまたは氏名が取込み後に変わった受講者が1件"]

    def test_number_only_in_roster_detected(self):
        issues = compare_source_to_roster([], [self._ros()])
        assert any("名簿にあり正本に無い" in i for i in issues)
        assert any("0件" in i for i in issues)  # 正本が空になった

    def test_number_only_in_source_detected(self):
        extra = self._src(number="A002", name="佐藤 一郎", kana="さとう いちろう")
        issues = compare_source_to_roster([self._src(), extra], [self._ros()])
        assert issues == ["正本にあり名簿に無い受講者番号が1件"]

    def test_duplicate_numbers_in_source_detected(self):
        issues = compare_source_to_roster([self._src(), self._src()], [self._ros()])
        assert any("重複" in i for i in issues)

    def test_row_without_number_in_source_detected(self):
        blank_number = self._src(number="", name="新規 太郎", kana="しんき たろう")
        issues = compare_source_to_roster([self._src(), blank_number], [self._ros()])
        assert any("受講者番号が空" in i for i in issues)

    def test_counts_are_reported_for_multiple_changes(self):
        s1 = self._src(group="B")
        s2 = self._src(
            number="A002", name="佐藤 一郎", kana="さとう いちろう", group="C"
        )
        r2 = self._ros(number="A002", name="佐藤 一郎", kana="さとう いちろう")
        issues = compare_source_to_roster([s1, s2], [self._ros(), r2])
        assert issues == ["グループまたは氏名が取込み後に変わった受講者が2件"]

    def test_name_normalization_makes_spacing_and_script_equivalent(self):
        src = self._src(name="山田　太郎", kana="ヤマダ タロウ")  # 全角空白・カタカナ
        assert compare_source_to_roster([src], [self._ros()]) == []

    def test_both_empty_is_ok(self):
        assert compare_source_to_roster([], []) == []

    def test_short_rows_are_padded(self):
        assert (
            compare_source_to_roster(
                [["A", "", "A001", "山田 太郎", "やまだ たろう"]],
                [["山田 太郎", "やまだ たろう", "N1", "", "", "", "", "A", "", "A001"]],
            )
            == []
        )

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


class TestTask2:
    """課題②: 表示ラベルと、案内する復旧コマンドに --task 課題② が付く(既定の課題①は不変)。"""

    def test_default_task_commands_have_no_task_option(self):
        _, action = classify_class(_facts(formulas="none"))
        assert "--task" not in action

    def test_missing_formulas_command_carries_task(self):
        _, action = classify_class(_facts(task="課題②", formulas="none"))
        assert "apply_submission_formulas.py --class 03 --task 課題② --commit" in action

    def test_missing_submission_tab_names_task2_and_carries_task(self):
        _, action = classify_class(_facts(task="課題②", sub_task_tab=False))
        assert "「課題②」" in action
        assert "--class 03 --task 課題② --commit --provision-submission-tab" in action

    def test_missing_hide_command_names_task2_and_carries_task(self):
        _, action = classify_class(_facts(task="課題②", admin_protected=False))
        assert "管理側の課題②が非表示+保護でない" in action
        assert "hide_sensitive_sheets.py --class 03 --task 課題② --commit" in action

    def test_submission_tab_visible_names_task2(self):
        _, action = classify_class(_facts(task="課題②", sub_hidden=False))
        assert "提出記録側の課題②が非表示でない" in action

    def test_broken_link_command_carries_task(self):
        _, action = classify_class(_facts(task="課題②", link_issues=["A1が不正"]))
        assert "apply_submission_formulas.py --class 03 --task 課題②" in action

    def test_done_with_task2(self):
        state, _ = classify_class(_facts(task="課題②"))
        assert state == STATE_DONE


class _GatherEnv:
    """gather_facts のAPI層を差し替える偽環境。読み取った範囲を記録する。"""

    def __init__(self, monkeypatch, task_formulas_in):
        import apply_submission_formulas as a
        import check_rollout_status as m

        self.m = m
        self.reads = []
        self.task_formulas_in = (
            task_formulas_in  # 判定式が入っている列("I"=課題①, "M"=課題②)
        )
        self.roster = [
            ["N1", "k", "D1", "", "", "", "", "A", "", "A001"],
            ["N2", "k", "D2", "", "", "", "", "A", "", "A002"],
            ["N3", "k", "D3", "", "", "", "", "A", "", "A003"],
        ]
        self.a = a
        monkeypatch.setattr(m, "resolve_attendance_spreadsheet_id", lambda c: "ATT")
        monkeypatch.setattr(m, "TASK1_SUBMISSION_SPREADSHEET_IDS", {"03": "SUB"})
        monkeypatch.setitem(m.EXPECTED_STUDENT_COUNT_BY_CLASS, "03", 3)
        monkeypatch.setattr(m, "_get_values", self._get)
        monkeypatch.setattr(m, "_get_full_sheets_list", self._full)

    def _full(self, sid, build_fn=None):
        def tab(title, sheet_id, hidden=True, protected=True):
            return {
                "properties": {"sheetId": sheet_id, "title": title, "hidden": hidden},
                "protectedRanges": (
                    [{"range": {"sheetId": sheet_id}}] if protected else []
                ),
            }

        if sid == "SUB":
            return [tab("課題②", 3, protected=False)]
        return [tab("受講者リスト", 1), tab("課題②", 2)]

    def _get(self, build_fn, sid, rng, render="FORMATTED_VALUE"):
        self.reads.append((sid, rng))
        f = self.a.build_status_formula
        if "リスト'!A2:G" in rng and "受講者" not in rng:
            # 取込み済みの名簿と一致する正本リスト(A=グループ, C=受講者番号, D=氏名, E=ふりがな)
            return [
                ["A", "", "A001", "N1", "k", ""],
                ["A", "", "A002", "N2", "k", ""],
                ["A", "", "A003", "N3", "k", ""],
            ]
        if rng.startswith("'受講者リスト'!A2:J"):
            return self.roster
        if rng.endswith("C5:C500"):
            return [["A001"], ["A002"], [], ["A003"]]
        if rng.endswith("A4:AZ4"):
            header = [""] * 13
            header[8], header[12] = "課題①", "課題②"
            return [header]
        if rng.startswith("'課題②'!A1") and rng.endswith("A1"):
            return [[self.a.build_import_formula("SUB", "課題②")]]
        if rng.endswith("!C1"):
            return [[self.a.XLOOKUP_FORMULA]]
        if rng.endswith("A1:C1"):
            return [["氏名", "日介番号", "受講者番号"]]
        if sid == "SUB":
            return [["D2"]]  # 提出記録の日介番号列(D2:D)
        col = rng.split("!")[1][0]
        if rng.endswith(f"{col}5:{col}500"):
            if col != self.task_formulas_in:
                return []
            label = "課題②" if col == "M" else "課題①"
            if render == "FORMULA":
                return [[f(5, label)], [f(6, label)], [], [f(8, label)]]
            return [["未提出"], ["提出"], [], ["未提出"]]
        raise AssertionError(f"想定外の読取り: {sid} {rng}")


class TestGatherFactsTask2:
    def test_task2_reads_task2_tabs_and_column_and_reports_all(self, monkeypatch):
        env = _GatherEnv(monkeypatch, task_formulas_in="M")

        facts = env.m.gather_facts("03", "課題②")

        assert facts["task"] == "課題②"
        assert facts["formulas"] == "all"
        assert facts["admin_task_tab"] and facts["sub_task_tab"]
        assert (
            facts["sub_hidden"] and facts["admin_hidden"] and facts["admin_protected"]
        )
        assert facts["tally_issues"] == []
        assert (facts["_submitted"], facts["_unsubmitted"]) == (1, 2)
        # 課題②の判定: 課題名つきの範囲だけを読み、課題①のタブは一切読まない
        assert not any("'課題①'" in rng for _sid, rng in env.reads)
        assert ("SUB", "'課題②'!D2:D5000") in env.reads
        assert env.m.classify_class(facts)[0] == STATE_DONE

    def test_task1_formulas_in_the_task1_column_do_not_count_for_task2(
        self, monkeypatch
    ):
        env = _GatherEnv(monkeypatch, task_formulas_in="I")  # M列(課題②)は空

        facts = env.m.gather_facts("03", "課題②")

        assert facts["formulas"] == "none"
        state, action = env.m.classify_class(facts)
        assert state == STATE_TODO
        assert "--task 課題②" in action


class TestMainTaskOption:
    def _run(self, monkeypatch, argv):
        import check_rollout_status as m

        calls = []
        monkeypatch.setattr(sys, "argv", ["check_rollout_status.py", *argv])
        monkeypatch.setattr(
            m,
            "gather_facts",
            lambda cn, task="課題①": calls.append((cn, task))
            or _facts(**{"class": cn}),
        )
        return m, calls

    def test_task_option_is_passed_to_gather_facts(self, monkeypatch):
        m, calls = self._run(monkeypatch, ["--class", "01", "--task", "課題②"])
        m.main()
        assert calls == [("01", "課題②")]

    def test_default_task_is_task1(self, monkeypatch):
        m, calls = self._run(monkeypatch, ["--class", "01"])
        m.main()
        assert calls == [("01", "課題①")]

    def test_rate_limit_retry_keeps_the_task(self, monkeypatch):
        from unittest.mock import Mock

        import check_rollout_status as m
        from googleapiclient.errors import HttpError

        calls = []

        def flaky(cn, task="課題①"):
            calls.append((cn, task))
            if len(calls) == 1:
                raise HttpError(Mock(status=429), b"quota")
            return _facts(**{"class": cn})

        monkeypatch.setattr(
            sys, "argv", ["check_rollout_status.py", "--class", "01", "--task", "課題②"]
        )
        monkeypatch.setattr(m, "gather_facts", flaky)
        monkeypatch.setattr(m.time, "sleep", lambda _s: None)
        m.main()
        assert calls == [("01", "課題②"), ("01", "課題②")]

    def test_invalid_task_is_rejected(self, monkeypatch):
        import pytest

        m, _ = self._run(monkeypatch, ["--class", "01", "--task", "課題③"])
        with pytest.raises(SystemExit):
            m.main()
