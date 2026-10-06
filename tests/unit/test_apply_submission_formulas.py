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
    check_row_cap,
    classify_cell,
    col_letter,
    extract_attendance_numbers,
    find_task_column,
    import_cell_has_error,
    independent_submitted_count,
    plan_attendance_writes,
    select_student_rows,
    statuses_for_rows,
    validate_number_mapping,
    validate_roster_keys,
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


class TestCheckRowCap:
    def test_below_cap_ok(self):
        check_row_cap([["N"]] * 10, cap=100)

    def test_at_cap_raises(self):
        # 上限に達したら独立集計が過小になりうるため中断する
        with pytest.raises(ValidationError):
            check_row_cap([["N"]] * 100, cap=100)

    def test_empty_ok(self):
        check_row_cap([], cap=100)


class TestNoDuplicateDefinitions:
    """切り貼りの編集ミスで定義が二重になると、後ろが前を黙って上書きし、構文エラーにも
    通常のテスト失敗にもならずに古い実装が実行され続ける(実際に起きた)。
    トップレベルだけでなく、クラス内(同名のtest_*メソッドは前者が消える)と
    定数の二重代入も検出する。"""

    ROOT = None

    @staticmethod
    def _duplicates(path):
        import ast
        from collections import Counter
        from pathlib import Path

        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        problems = []
        for scope in [tree] + [
            n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)
        ]:
            names = []
            for n in scope.body:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names.append(n.name)
                elif isinstance(n, ast.Assign):
                    names += [t.id for t in n.targets if isinstance(t, ast.Name)]
                elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                    names.append(n.target.id)
            problems += [
                f"{getattr(scope, 'name', '<module>')}.{name}"
                for name, c in Counter(names).items()
                if c > 1 and name != "_"
            ]
        return problems

    @pytest.mark.parametrize(
        "relpath",
        [
            "scripts/apply_submission_formulas.py",
            "scripts/check_rollout_status.py",
            "tests/unit/test_apply_submission_formulas.py",
            "tests/unit/test_check_rollout_status.py",
        ],
    )
    def test_no_duplicate_definitions(self, relpath):
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        assert self._duplicates(root / relpath) == []

    def test_detector_catches_duplicates(self, tmp_path):
        f = tmp_path / "x.py"
        f.write_text(
            "A = 1\nA = 2\ndef f(): pass\ndef f(): pass\nclass T:\n    def t(self): pass\n    def t(self): pass\n"
        )
        found = self._duplicates(f)
        assert {"<module>.A", "<module>.f", "T.t"} <= set(found)


class TestExtractAttendanceNumbers:
    def test_roster_members_and_number_like_values_are_kept(self):
        col = [
            ["A001"],
            [],
            [" A003 "],
            ["ａ００２"],
            ["B12"],
            ["受講者番号"],
            ["Z999"],
        ]
        # 名簿にあるもの(A001,A003)と、受講者番号の形式の余分な値(Z999)。
        # 全角・形式外・見出し・空行は除外される。
        assert extract_attendance_numbers(col, {"A001", "A003"}) == [
            "A001",
            "A003",
            "Z999",
        ]

    def test_empty(self):
        assert extract_attendance_numbers([], {"A001"}) == []


class TestStatusesForRows:
    def test_short_and_empty_columns_yield_empty_string(self):
        # APIは末尾の空セルを省略し、途中の空は[]で返す
        col = [["提出"], [], ["未提出"]]
        assert statuses_for_rows(col, [5, 6, 7, 8]) == ["提出", "", "未提出", ""]

    def test_empty_status_is_flagged_by_verify_results(self):
        issues = verify_results(["提出", ""], 2, 1)
        assert issues

    def test_row_offset_uses_first_row(self):
        assert statuses_for_rows([["a"], ["b"]], [2, 3], first_row=2) == ["a", "b"]


class TestValidateRosterKeys:
    def test_ok(self):
        assert validate_roster_keys(["N1", "N2"], ["A001", "A002"]) == []

    def test_blank_student_number(self):
        assert any("受講者番号が空" in i for i in validate_roster_keys(["N1"], [""]))

    def test_blank_nichikai(self):
        assert any("日介番号が空" in i for i in validate_roster_keys([" "], ["A001"]))

    def test_duplicate_nichikai(self):
        # 重複すると2人目の提出が「未提出」のままになりうる
        assert any(
            "重複" in i for i in validate_roster_keys(["N1", "N1"], ["A001", "A002"])
        )


class TestEdgeCases:
    @pytest.mark.parametrize(
        "idx,expected", [(51, "AZ"), (52, "BA"), (701, "ZZ"), (702, "AAA")]
    )
    def test_col_letter_carry(self, idx, expected):
        assert col_letter(idx) == expected

    def test_find_task_column_rejects_partial_labels(self):
        for cell in ("課題①②", "課題1", "課題①（再提出）"):
            with pytest.raises(ValidationError):
                find_task_column(["", cell])

    def test_find_task_column_empty_header(self):
        with pytest.raises(ValidationError):
            find_task_column([])

    def test_find_task_column_tolerates_non_string_cells(self):
        assert find_task_column([None, 0, "課題①"]) == 2

    def test_planned_formula_is_for_its_own_row(self):
        plan = plan_attendance_writes({}, [5, 9])
        assert plan["writes"] == [
            (5, build_status_formula(5)),
            (9, build_status_formula(9)),
        ]

    def test_trailing_space_difference_is_a_conflict(self):
        plan = plan_attendance_writes({5: build_status_formula(5) + " "}, [5])
        assert plan["conflicts"] == [5]

    def test_verify_results_flags_value_with_padding(self):
        assert verify_results(["提出 "], 1, 1)

    def test_verify_results_reports_error_and_count_together(self):
        issues = verify_results(["#REF!", "未提出"], 3, 0)
        assert len(issues) >= 2

    @pytest.mark.parametrize("v", ["#DIV/0!", "#NAME?"])
    def test_import_error_variants(self, v):
        assert import_cell_has_error(v) is True

    @pytest.mark.parametrize("n", [7, 9])
    def test_header_with_wrong_column_count_is_rejected(self, n):
        assert validate_submission_header([SUBMISSION_HEADER[:7] + ["x"] * (n - 7)])

    def test_header_with_short_row(self):
        assert validate_submission_header([["課題ID"]])

    def test_provision_requests_fields_and_origin(self):
        reqs = build_provision_requests(1, SUBMISSION_HEADER)
        upd = reqs[1]["updateCells"]
        assert upd["fields"] == "userEnteredValue"
        assert upd["start"] == {"sheetId": 1, "rowIndex": 0, "columnIndex": 0}


class _Env:
    """process_class のAPI層を差し替える偽環境。書込み系の呼び出しを順に記録する。"""

    def __init__(self, m, monkeypatch, tmp_path, **kw):
        self.m = m
        self.log = []
        self.sleeps = 0
        self.roster = kw.get(
            "roster",
            [
                ["N1", "", "", "", "", "", "", "A001"],
                ["N2", "", "", "", "", "", "", "A002"],
                ["N3", "", "", "", "", "", "", "A003"],
            ],
        )
        self.number_col = kw.get("number_col", [["A001"], ["A002"], [], ["A003"]])
        self.existing_col = kw.get("existing_col", [])
        self.sub_titles = kw.get("sub_titles", ["シート1", "課題①"])
        self.att_titles = kw.get("att_titles", ["受講者リスト", "課題①"])
        self.a1 = kw.get("a1", m.build_import_formula("SUB"))
        self.c1 = kw.get("c1", m.XLOOKUP_FORMULA)
        self.import_cells = kw.get("import_cells", [["氏名", "日介番号", "受講者番号"]])
        # 事後検証の読取り(FORMATTED)が返す表示値を、呼び出し順に使う
        self.after = list(kw.get("after", [[["未提出"], ["提出"], [], ["未提出"]]]))
        self.sub_d = kw.get("sub_d", [["N2"]])
        monkeypatch.setattr(
            m, "EXPECTED_STUDENT_COUNT_BY_CLASS", {"03": kw.get("expected", 3)}
        )
        monkeypatch.setattr(m, "TASK1_SUBMISSION_SPREADSHEET_IDS", {"03": "SUB"})
        monkeypatch.setattr(m, "resolve_attendance_spreadsheet_id", lambda c: "ATT")
        monkeypatch.setattr(m, "_scratch_dir", lambda: tmp_path)
        monkeypatch.setattr(m.time, "sleep", self._sleep)
        monkeypatch.setattr(m, "_get_values", self._get)
        monkeypatch.setattr(m, "_list_titles", self._titles)
        monkeypatch.setattr(m, "_batch_update", self._batch)
        monkeypatch.setattr(m, "_update_values", self._update)
        monkeypatch.setattr(m, "_write_status_formulas", self._write)
        monkeypatch.setattr(m, "provision_submission_tab", self._provision)

    def _sleep(self, _s):
        self.sleeps += 1

    def _titles(self, build_fn, sid):
        return self.sub_titles if sid == "SUB" else self.att_titles

    def _get(self, build_fn, sid, rng, render="FORMATTED_VALUE"):
        if sid == "SUB":
            if rng.endswith("A1:H1"):
                return [self.m.SUBMISSION_HEADER]
            return self.sub_d
        if "受講者リスト" in rng:
            return self.roster
        if rng.endswith("A4:AZ4"):
            return [[""] * 8 + ["課題①"]]
        if rng.endswith("C5:C500"):
            return self.number_col
        if rng == "'課題①'!A1":
            return [[self.a1]] if self.a1 else []
        if rng == "'課題①'!C1":
            return [[self.c1]] if self.c1 else []
        if rng.endswith("A1:C1"):
            return self.import_cells
        if rng.endswith("I5:I500"):
            if render == "FORMULA":
                return self.existing_col
            return self.after.pop(0) if len(self.after) > 1 else self.after[0]
        raise AssertionError(f"想定外の読取り: {rng}")

    def _batch(self, build_fn, sid, reqs):
        self.log.append(("addSheet", sid))

    def _update(self, build_fn, sid, rng, values, raw=False):
        self.log.append(("update", rng))

    def _write(self, att_id, att_tab, task_col, writes):
        self.log.append(("write_formulas", task_col, len(writes)))

    def _provision(self, sid):
        self.log.append(("provision", sid))
        return "created"

    def writes(self):
        return [e for e in self.log if e[0] != "provision"] if False else self.log


def _env(monkeypatch, tmp_path, **kw):
    import apply_submission_formulas as m

    return _Env(m, monkeypatch, tmp_path, **kw)


def _formulas_for_rows(rows):
    import apply_submission_formulas as m

    return [[m.build_status_formula(r)] for r in rows]


class TestProcessClass:
    def test_unregistered_expected_count_holds_without_any_call(
        self, monkeypatch, tmp_path
    ):
        env = _env(monkeypatch, tmp_path)
        env.m.EXPECTED_STUDENT_COUNT_BY_CLASS.clear()
        assert env.m.process_class("03", True, True) == 2
        assert env.log == []

    def test_missing_submission_tab_without_flag_holds_and_writes_nothing(
        self, monkeypatch, tmp_path
    ):
        env = _env(monkeypatch, tmp_path, sub_titles=["シート1"])
        assert env.m.process_class("03", True, False) == 2
        assert env.log == []

    def test_dry_run_with_provision_plans_but_writes_nothing(
        self, monkeypatch, tmp_path
    ):
        env = _env(
            monkeypatch, tmp_path, sub_titles=["シート1"], att_titles=["受講者リスト"]
        )
        assert env.m.process_class("03", False, True) == 0
        assert env.log == []  # provision・addSheet・書込みのいずれも呼ばれない

    def test_dry_run_never_writes_even_when_changes_are_planned(
        self, monkeypatch, tmp_path
    ):
        env = _env(monkeypatch, tmp_path, att_titles=["受講者リスト"], a1="", c1="")
        assert env.m.process_class("03", False, False) == 0
        assert env.log == []

    def test_conflict_in_column_aborts_before_any_write(self, monkeypatch, tmp_path):
        env = _env(monkeypatch, tmp_path, existing_col=[["提出"]])
        with pytest.raises(ValidationError):
            env.m.process_class("03", True, False)
        assert env.log == []

    def test_conflict_in_a1_aborts_before_any_write(self, monkeypatch, tmp_path):
        env = _env(monkeypatch, tmp_path, a1="=別の式")
        with pytest.raises(ValidationError):
            env.m.process_class("03", True, False)
        assert env.log == []

    def test_provision_happens_only_after_admin_side_validation(
        self, monkeypatch, tmp_path
    ):
        # 管理側に衝突があるなら、提出記録側のタブは作らない(本番側の書込みを残さない)
        env = _env(
            monkeypatch, tmp_path, sub_titles=["シート1"], existing_col=[["提出"]]
        )
        with pytest.raises(ValidationError):
            env.m.process_class("03", True, True)
        assert ("provision", "SUB") not in env.log

    def test_number_mismatch_aborts_before_any_write(self, monkeypatch, tmp_path):
        env = _env(monkeypatch, tmp_path, number_col=[["A001"], ["A002"]])
        with pytest.raises(ValidationError):
            env.m.process_class("03", True, False)
        assert env.log == []

    def test_roster_count_mismatch_aborts(self, monkeypatch, tmp_path):
        env = _env(monkeypatch, tmp_path, expected=4)
        with pytest.raises(ValidationError):
            env.m.process_class("03", True, False)
        assert env.log == []

    def test_blank_student_number_in_roster_aborts(self, monkeypatch, tmp_path):
        env = _env(
            monkeypatch,
            tmp_path,
            roster=[
                ["N1", "", "", "", "", "", "", ""],
                ["N2", "", "", "", "", "", "", "A002"],
                ["N3", "", "", "", "", "", "", "A003"],
            ],
        )
        with pytest.raises(ValidationError):
            env.m.process_class("03", True, False)
        assert env.log == []

    def test_commit_writes_in_order_and_backs_up(self, monkeypatch, tmp_path):
        env = _env(
            monkeypatch,
            tmp_path,
            sub_titles=["シート1"],
            att_titles=["受講者リスト"],
            a1="",
            c1="",
        )
        assert env.m.process_class("03", True, True) == 0
        kinds = [e[0] for e in env.log]
        assert kinds == ["provision", "addSheet", "update", "update", "write_formulas"]
        assert env.log[-1] == ("write_formulas", "I", 3)
        backups = list(tmp_path.rglob("class03_before.json"))
        assert len(backups) == 1
        assert oct(backups[0].stat().st_mode & 0o777) == "0o600"

    def test_rerun_with_everything_in_place_writes_nothing(self, monkeypatch, tmp_path):
        env = _env(monkeypatch, tmp_path, existing_col=_formulas_for_rows([5, 6, 7, 8]))
        # 受講者行は5,6,8。7行目(空)は既存の空のまま
        env.existing_col = [
            [env.m.build_status_formula(5)],
            [env.m.build_status_formula(6)],
            [],
            [env.m.build_status_formula(8)],
        ]
        assert env.m.process_class("03", True, False) == 0
        assert [e for e in env.log if e[0] == "write_formulas"] == []

    def test_verification_retries_until_recalculated(self, monkeypatch, tmp_path):
        env = _env(
            monkeypatch,
            tmp_path,
            after=[
                [["#REF!"], ["#REF!"], [], ["#REF!"]],
                [["未提出"], ["提出"], [], ["未提出"]],
            ],
        )
        assert env.m.process_class("03", True, False) == 0
        assert env.sleeps == 2

    def test_verification_fails_after_three_attempts(self, monkeypatch, tmp_path):
        env = _env(monkeypatch, tmp_path, after=[[["#REF!"], ["#REF!"], [], ["#REF!"]]])
        assert env.m.process_class("03", True, False) == 1
        assert env.sleeps == 3

    def test_c1_error_is_detected(self, monkeypatch, tmp_path):
        env = _env(monkeypatch, tmp_path, import_cells=[["氏名", "日介番号", "#REF!"]])
        assert env.m.process_class("03", True, False) == 1

    def test_tally_mismatch_fails(self, monkeypatch, tmp_path):
        # 表示は2人提出だが、提出記録の独立集計は1人
        env = _env(monkeypatch, tmp_path, after=[[["提出"], ["提出"], [], ["未提出"]]])
        assert env.m.process_class("03", True, False) == 1


class TestProvisionUsesTheWritingServiceAccount:
    """提出記録シートへの書込みは github-actions-sa、管理側は carewell-automation-sa。
    取り違えは本番で403になるだけで、単体テストが緑のまま見逃される。"""

    def test_provision_builds_with_task1_service(self, monkeypatch):
        import apply_submission_formulas as m

        seen = []
        monkeypatch.setattr(m, "_batch_update", lambda b, sid, reqs: seen.append(b))
        monkeypatch.setattr(
            m,
            "_get_values",
            lambda b, sid, rng, render="FORMATTED_VALUE": (
                seen.append(b),
                [m.SUBMISSION_HEADER],
            )[1],
        )
        m.provision_submission_tab("SUB")
        assert seen and all(b is m._build_task1_sheets_service for b in seen)

    def test_bulk_write_uses_attendance_service(self, monkeypatch):
        import apply_submission_formulas as m

        captured = {}

        def fake_reauth(build_fn, call):
            captured["build_fn"] = build_fn

        monkeypatch.setattr(m, "call_with_reauth", fake_reauth)
        m._write_status_formulas("ATT", "tab", "I", [(5, "=x")])
        assert captured["build_fn"] is m._build_sheets_service
