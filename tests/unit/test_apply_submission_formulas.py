"""
Unit tests for scripts/apply_submission_formulas.py の純粋関数。

ネットワーク呼び出し(Sheets API)を含む関数は対象外。数式文字列は
クラス№01で実際に使われている式(2026-09-11以降稼働中)と同一であることを固定する。
"""

import sys

import pytest

sys.path.insert(0, "scripts")

from apply_submission_formulas import (  # noqa: E402
    SUBMISSION_HEADER,
    TASK_LABEL,
    XLOOKUP_FORMULA,
    ValidationError,
    build_import_formula,
    build_provision_requests,
    build_status_formula,
    classify_cell,
    col_letter,
    find_task_column,
    import_cell_has_error,
    independent_submitted_count,
    plan_attendance_writes,
    select_student_rows,
    validate_number_mapping,
    validate_submission_header,
    verify_results,
)

# クラス№01で稼働中の実数式(基準フィクスチャ)
NO01_STATUS_FORMULA_ROW5 = (
    '=IF(C5="","",IF(COUNTIF(\'課題①\'!C:C,C5)=0,"未提出","提出"))'
)
NO01_IMPORT_FORMULA = (
    '=IMPORTRANGE("1sg4YWQ1hHgzFWFXNbOVFXiWTXUhzvjPpejaMArwLQRc","課題①!C:D")'
)
NO01_XLOOKUP_FORMULA = (
    "=ArrayFormula(XLOOKUP(B:B,'受講者リスト'!C:C,'受講者リスト'!J:J,\"\"))"
)


class TestFormulas:
    def test_status_formula_matches_no01(self):
        assert build_status_formula(5) == NO01_STATUS_FORMULA_ROW5

    def test_status_formula_uses_row_number(self):
        assert "C123" in build_status_formula(123)
        assert "C5" not in build_status_formula(123)

    def test_import_formula_matches_no01(self):
        sid = "1sg4YWQ1hHgzFWFXNbOVFXiWTXUhzvjPpejaMArwLQRc"
        assert build_import_formula(sid) == NO01_IMPORT_FORMULA

    def test_xlookup_formula_matches_no01(self):
        assert XLOOKUP_FORMULA == NO01_XLOOKUP_FORMULA


class TestFindTaskColumn:
    def test_finds_unique_label(self):
        header = [
            "",
            "Ａグループ",
            "受講者番号",
            "名前",
            "ふりがな",
            "自己紹介",
            "ｹｰｽｽﾀﾃﾞｨ1",
            "自職場ﾜｰｸ",
            "課題①",
            "9:35",
            "課題②",
        ]
        assert find_task_column(header) == 8

    def test_column_moves_with_layout(self):
        header = ["", "", "課題①", "x"]
        assert find_task_column(header) == 2

    def test_missing_label_raises(self):
        with pytest.raises(ValidationError):
            find_task_column(["", "課題②"])

    def test_duplicate_label_raises(self):
        with pytest.raises(ValidationError):
            find_task_column(["課題①", "x", "課題①"])

    def test_label_with_surrounding_whitespace_is_matched(self):
        assert find_task_column(["", " 課題① "]) == 1

    def test_default_label_is_task1(self):
        assert TASK_LABEL == "課題①"


class TestColLetter:
    @pytest.mark.parametrize(
        "idx,expected", [(0, "A"), (8, "I"), (25, "Z"), (26, "AA"), (27, "AB")]
    )
    def test_zero_indexed_to_letter(self, idx, expected):
        assert col_letter(idx) == expected


class TestClassifyCell:
    def test_empty_is_empty(self):
        assert classify_cell("", "=X") == "empty"
        assert classify_cell(None, "=X") == "empty"

    def test_same_is_same(self):
        assert classify_cell("=X", "=X") == "same"

    def test_other_is_conflict(self):
        assert classify_cell("=Y", "=X") == "conflict"
        assert classify_cell("提出", "=X") == "conflict"

    def test_whitespace_only_is_empty(self):
        assert classify_cell("  ", "=X") == "empty"


class TestSelectStudentRows:
    def test_only_rows_in_roster_are_selected(self):
        # 5行目から。見出し行(受講者番号という文字列)・空行・名簿外の値は除外
        col = [["A001"], ["A002"], [], [""], ["受講者番号"], ["A003"], ["Z999"]]
        assert select_student_rows(col, {"A001", "A002", "A003"}) == [5, 6, 10]

    def test_empty_input(self):
        assert select_student_rows([], {"A001"}) == []

    def test_strips_whitespace(self):
        assert select_student_rows([[" A001 "]], {"A001"}) == [5]

    def test_custom_first_row(self):
        assert select_student_rows([["A001"]], {"A001"}, first_row=2) == [2]

    def test_nonstandard_prefix_char_allowed_when_in_roster(self):
        # 既存の名簿検証は[A-Zー]\d{3}を許容する。正規表現ではなく名簿との照合で決める。
        assert select_student_rows([["ー001"]], {"ー001"}) == [5]


class TestValidateNumberMapping:
    def test_identical_sets_ok(self):
        assert validate_number_mapping(["A001", "A002"], ["A002", "A001"]) == []

    def test_missing_in_attendance(self):
        issues = validate_number_mapping(["A001"], ["A001", "A002"])
        assert any("出欠確認に存在しない" in i for i in issues)

    def test_extra_in_attendance(self):
        issues = validate_number_mapping(["A001", "A002"], ["A001"])
        assert any("受講者リストに存在しない" in i for i in issues)

    def test_duplicate_in_attendance(self):
        issues = validate_number_mapping(["A001", "A001"], ["A001"])
        assert any("重複" in i for i in issues)

    def test_duplicate_in_roster(self):
        issues = validate_number_mapping(["A001"], ["A001", "A001"])
        assert any("重複" in i for i in issues)

    def test_empty_both_is_ok_but_empty_roster_flagged_elsewhere(self):
        assert validate_number_mapping([], []) == []


class TestPlanAttendanceWrites:
    def test_empty_cells_get_written(self):
        plan = plan_attendance_writes({5: "", 6: ""}, [5, 6])
        assert [r for r, _ in plan["writes"]] == [5, 6]
        assert plan["same"] == 0 and plan["conflicts"] == []

    def test_same_formula_is_skipped(self):
        plan = plan_attendance_writes({5: build_status_formula(5)}, [5])
        assert plan["writes"] == [] and plan["same"] == 1

    def test_other_existing_value_is_conflict_and_not_written(self):
        plan = plan_attendance_writes({5: "提出", 6: ""}, [5, 6])
        assert plan["conflicts"] == [5]
        assert [r for r, _ in plan["writes"]] == [6]

    def test_missing_key_treated_as_empty(self):
        plan = plan_attendance_writes({}, [5])
        assert [r for r, _ in plan["writes"]] == [5]

    def test_non_student_rows_not_touched(self):
        # 見出し行(24行目など)は対象外。既存入力は書込み計画に現れない。
        plan = plan_attendance_writes({24: "課題①", 25: ""}, [25])
        assert [r for r, _ in plan["writes"]] == [25]
        assert plan["conflicts"] == []


class TestVerifyResults:
    def test_all_ok(self):
        assert verify_results(["提出", "未提出", "未提出"], 3, 1) == []

    def test_error_cell_detected(self):
        issues = verify_results(["#REF!", "未提出"], 2, 0)
        assert any("エラー" in i for i in issues)

    def test_count_mismatch_detected(self):
        issues = verify_results(["提出"], 2, 1)
        assert any("行数" in i for i in issues)

    def test_tally_mismatch_detected(self):
        issues = verify_results(["提出", "未提出"], 2, 2)
        assert any("独立集計" in i for i in issues)

    def test_all_unsubmitted_zero_ok(self):
        assert verify_results(["未提出"] * 3, 3, 0) == []

    def test_all_submitted_ok(self):
        assert verify_results(["提出"] * 3, 3, 3) == []

    def test_unexpected_value_detected(self):
        issues = verify_results(["たぶん"], 1, 0)
        assert issues


class TestImportCellHasError:
    @pytest.mark.parametrize(
        "v",
        [
            "#REF!",
            "#ERROR!",
            "#N/A",
            "#VALUE!",
            "You need to connect these sheets",
            "これらのシートを接続する必要があります",
        ],
    )
    def test_error_values(self, v):
        assert import_cell_has_error(v) is True

    @pytest.mark.parametrize("v", ["氏名", "日介番号", "", None])
    def test_ok_values(self, v):
        assert import_cell_has_error(v) is False


class TestIndependentSubmittedCount:
    def test_unique_intersection(self):
        sub = ["N1", "N1", "N2", "N9", ""]
        assert independent_submitted_count(sub, {"N1", "N2", "N3"}) == 2

    def test_none_submitted(self):
        assert independent_submitted_count([], {"N1"}) == 0

    def test_whitespace_stripped(self):
        assert independent_submitted_count([" N1 "], {"N1"}) == 1


class TestSubmissionHeader:
    def test_expected_header_ok(self):
        assert validate_submission_header([SUBMISSION_HEADER]) == []

    def test_missing_tab_values(self):
        assert validate_submission_header([]) != []

    def test_wrong_header(self):
        bad = list(SUBMISSION_HEADER)
        bad[3] = "違う"
        assert validate_submission_header([bad]) != []

    def test_header_has_eight_columns_like_cloud_run(self):
        assert len(SUBMISSION_HEADER) == 8
        assert SUBMISSION_HEADER[3] == "日介番号"


class TestBuildProvisionRequests:
    def test_single_batch_creates_hidden_sheet_and_header(self):
        reqs = build_provision_requests(123456, SUBMISSION_HEADER)
        assert len(reqs) == 2
        add = reqs[0]["addSheet"]["properties"]
        assert add["title"] == "課題①" and add["hidden"] is True
        assert add["sheetId"] == 123456
        upd = reqs[1]["updateCells"]
        assert upd["start"]["sheetId"] == 123456
        values = upd["rows"][0]["values"]
        assert [
            v["userEnteredValue"]["stringValue"] for v in values
        ] == SUBMISSION_HEADER


class _Resp:
    def __init__(self, status=400, reason="Bad Request"):
        self.status = status
        self.reason = reason


def _already_exists_error():
    from googleapiclient.errors import HttpError

    content = (
        b'{"error":{"code":400,"message":"A sheet with the name '
        b'\\"\xe8\xaa\xb2\xe9\xa1\x8c\xe2\x91\xa0\\" already exists. Please enter another name."}}'
    )
    return HttpError(_Resp(), content)


class TestProvisionSubmissionTab:
    """Cloud Run(毎時、タブ作成→見出しを別呼び出しで行う)との競合パス"""

    def _patch(self, monkeypatch, *, batch_exc=None, readbacks=None):
        import apply_submission_formulas as m

        calls = {"batch": 0, "update": 0}

        def fake_batch(build_fn, sid, reqs):
            calls["batch"] += 1
            if batch_exc:
                raise batch_exc

        def fake_get(build_fn, sid, rng, render="FORMATTED_VALUE"):
            return readbacks.pop(0)

        def fake_update(build_fn, sid, rng, values, raw=False):
            calls["update"] += 1

        monkeypatch.setattr(m, "_batch_update", fake_batch)
        monkeypatch.setattr(m, "_get_values", fake_get)
        monkeypatch.setattr(m, "_update_values", fake_update)
        return m, calls

    def test_created_when_no_conflict(self, monkeypatch):
        m, calls = self._patch(monkeypatch, readbacks=[[SUBMISSION_HEADER]])
        assert m.provision_submission_tab("sid") == "created"
        assert calls == {"batch": 1, "update": 0}

    def test_already_exists_with_header_continues_without_writing(self, monkeypatch):
        m, calls = self._patch(
            monkeypatch,
            batch_exc=_already_exists_error(),
            readbacks=[[SUBMISSION_HEADER], [SUBMISSION_HEADER]],
        )
        assert m.provision_submission_tab("sid") == "already_exists"
        assert calls["update"] == 0

    def test_already_exists_with_empty_header_writes_system_header(self, monkeypatch):
        # システムがタブだけ作り、見出し書込み前の瞬間に当たった場合
        m, calls = self._patch(
            monkeypatch,
            batch_exc=_already_exists_error(),
            readbacks=[[], [SUBMISSION_HEADER]],
        )
        assert m.provision_submission_tab("sid") == "already_exists"
        assert calls["update"] == 1

    def test_already_exists_with_foreign_header_aborts(self, monkeypatch):
        bad = list(SUBMISSION_HEADER)
        bad[0] = "別の見出し"
        m, _ = self._patch(
            monkeypatch,
            batch_exc=_already_exists_error(),
            readbacks=[[bad], [bad]],
        )
        with pytest.raises(ValidationError):
            m.provision_submission_tab("sid")

    def test_other_http_error_is_not_swallowed(self, monkeypatch):
        from googleapiclient.errors import HttpError

        m, _ = self._patch(
            monkeypatch,
            batch_exc=HttpError(
                _Resp(403, "Forbidden"), b'{"error":{"message":"denied"}}'
            ),
            readbacks=[],
        )
        with pytest.raises(HttpError):
            m.provision_submission_tab("sid")
