"""
Unit tests for scripts/hide_sensitive_sheets.py の純粋関数(リクエスト組み立て・冪等性判定)。

ネットワーク呼び出し(Drive/Sheets API)を含む関数は対象外。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, "scripts")

from hide_sensitive_sheets import (  # noqa: E402
    COMPANY_OFFICE_COLUMN_RANGE,
    PROJECT_ROOT,
    _find_sheet_entry,
    _is_whole_sheet_protected,
    _scratch_dir,
    check_sa_not_locked_out,
    plan_destination_task1_requests,
    plan_hide_request,
    plan_protect_request,
    plan_roster_requests,
    plan_task1_requests,
)


def _sheet_entry(sheet_id=1, hidden=False, protected_ranges=None):
    return {
        "properties": {"sheetId": sheet_id, "title": "受講者リスト", "hidden": hidden},
        "protectedRanges": protected_ranges or [],
    }


class TestFindSheetEntry:
    def test_finds_matching_title(self):
        sheets = [
            {"properties": {"title": "№01リスト"}},
            {"properties": {"title": "受講者リスト"}, "protectedRanges": []},
        ]
        found = _find_sheet_entry(sheets, "受講者リスト")
        assert found is not None
        assert found["properties"]["title"] == "受講者リスト"

    def test_returns_none_when_not_found(self):
        sheets = [{"properties": {"title": "№01リスト"}}]
        assert _find_sheet_entry(sheets, "課題①") is None

    def test_raises_on_duplicate_title(self):
        sheets = [
            {"properties": {"title": "課題①"}},
            {"properties": {"title": "課題①"}},
        ]
        with pytest.raises(RuntimeError):
            _find_sheet_entry(sheets, "課題①")


class TestIsWholeSheetProtected:
    def test_no_protected_ranges_is_unprotected(self):
        assert _is_whole_sheet_protected(_sheet_entry(protected_ranges=[])) is False

    def test_whole_sheet_range_is_protected(self):
        entry = _sheet_entry(protected_ranges=[{"range": {"sheetId": 1}}])
        assert _is_whole_sheet_protected(entry) is True

    def test_partial_range_protection_does_not_count(self):
        # startRowIndex等が指定されている = セル範囲のみの保護であり、シート全体保護ではない
        entry = _sheet_entry(
            protected_ranges=[
                {"range": {"sheetId": 1, "startRowIndex": 0, "endRowIndex": 5}}
            ]
        )
        assert _is_whole_sheet_protected(entry) is False

    def test_zero_start_index_omitted_partial_range_is_not_whole_sheet(self):
        # Sheets APIはproto3のデフォルト値省略により、start側indexが0の場合
        # レスポンスからstartRowIndex/startColumnIndex自体が欠落しうる(例: A1:E100)。
        # この場合もendRowIndex/endColumnIndexが残っているため、シート全体保護と
        # 誤判定してはならない(4つのindexキー全てが欠落している場合のみ全体保護扱い)。
        entry = _sheet_entry(
            protected_ranges=[
                {"range": {"sheetId": 1, "endRowIndex": 5, "endColumnIndex": 5}}
            ]
        )
        assert _is_whole_sheet_protected(entry) is False

    def test_warning_only_protection_does_not_count(self):
        # warningOnly=Trueは編集時に警告を表示するだけで、誰でも編集できてしまうため
        # 「保護済み」とはみなさない
        entry = _sheet_entry(
            protected_ranges=[{"range": {"sheetId": 1}, "warningOnly": True}]
        )
        assert _is_whole_sheet_protected(entry) is False


class TestPlanHideRequest:
    def test_returns_request_when_not_hidden(self):
        req = plan_hide_request({"sheetId": 1, "hidden": False})
        assert req is not None
        assert req["updateSheetProperties"]["properties"]["hidden"] is True
        assert req["updateSheetProperties"]["properties"]["sheetId"] == 1

    def test_returns_none_when_already_hidden(self):
        assert plan_hide_request({"sheetId": 1, "hidden": True}) is None

    def test_returns_request_when_hidden_key_absent(self):
        # Sheets APIはhidden=Falseのとき、フィールド自体を省略することがある
        req = plan_hide_request({"sheetId": 1})
        assert req is not None


class TestPlanProtectRequest:
    def test_builds_add_protected_range_with_given_editors(self):
        req = plan_protect_request(42, ["a@example.com", "b@example.com"])
        protected = req["addProtectedRange"]["protectedRange"]
        assert protected["range"] == {"sheetId": 42}
        assert protected["editors"]["users"] == ["a@example.com", "b@example.com"]


class TestPlanRosterRequests:
    def test_unhidden_unprotected_sheet_gets_all_three_requests(self):
        entry = _sheet_entry(hidden=False, protected_ranges=[])
        requests = plan_roster_requests(entry, ["a@example.com"])
        kinds = [list(r.keys())[0] for r in requests]
        assert "updateSheetProperties" in kinds
        assert "updateDimensionProperties" in kinds
        assert "addProtectedRange" in kinds

    def test_already_hidden_and_protected_sheet_only_gets_column_hide(self):
        entry = _sheet_entry(hidden=True, protected_ranges=[{"range": {"sheetId": 1}}])
        requests = plan_roster_requests(entry, ["a@example.com"])
        kinds = [list(r.keys())[0] for r in requests]
        assert "updateSheetProperties" not in kinds
        assert "addProtectedRange" not in kinds
        assert kinds == ["updateDimensionProperties"]

    def test_column_range_matches_company_office_constant(self):
        entry = _sheet_entry()
        requests = plan_roster_requests(entry, [])
        dim_req = next(
            r["updateDimensionProperties"]
            for r in requests
            if "updateDimensionProperties" in r
        )
        start, end = COMPANY_OFFICE_COLUMN_RANGE
        assert dim_req["range"]["startIndex"] == start
        assert dim_req["range"]["endIndex"] == end


class TestPlanDestinationTask1Requests:
    def test_unhidden_unprotected_sheet_gets_hide_and_protect(self):
        entry = _sheet_entry(sheet_id=7, hidden=False, protected_ranges=[])
        requests = plan_destination_task1_requests(entry, ["a@example.com"])
        kinds = [list(r.keys())[0] for r in requests]
        assert kinds == ["updateSheetProperties", "addProtectedRange"]

    def test_already_hidden_and_protected_sheet_gets_nothing(self):
        entry = _sheet_entry(
            sheet_id=7, hidden=True, protected_ranges=[{"range": {"sheetId": 7}}]
        )
        requests = plan_destination_task1_requests(entry, ["a@example.com"])
        assert requests == []


class TestCheckSaNotLockedOut:
    def test_raises_when_sa_missing_from_nonempty_editor_list(self):
        with pytest.raises(RuntimeError):
            check_sa_not_locked_out(["someone@example.com"], sa_email="sa@example.com")

    def test_passes_when_sa_present(self):
        check_sa_not_locked_out(
            ["someone@example.com", "sa@example.com"], sa_email="sa@example.com"
        )  # 例外が発生しなければOK

    def test_empty_editor_list_does_not_raise(self):
        # 対象タブが存在せずまだ取得していない場合(呼び出し元でeditor_emails=[]としている)は
        # 判定不能なため何もしない
        check_sa_not_locked_out([], sa_email="sa@example.com")


class TestPlanTask1Requests:
    def test_returns_hide_request_when_not_hidden(self):
        requests = plan_task1_requests({"sheetId": 3, "hidden": False})
        assert len(requests) == 1
        assert requests[0]["updateSheetProperties"]["properties"]["hidden"] is True

    def test_returns_empty_when_already_hidden(self):
        assert plan_task1_requests({"sheetId": 3, "hidden": True}) == []


class TestScratchDir:
    """Issue #36: backup/manifestの出力先がプロジェクト外(ホーム配下)へ逆戻りしないことを保証する回帰テスト。"""

    def test_scratch_dir_is_under_project_root(self):
        scratch_dir = _scratch_dir()
        assert scratch_dir.is_relative_to(PROJECT_ROOT)

    def test_scratch_dir_is_not_under_home_claude(self):
        scratch_dir = _scratch_dir()
        assert not scratch_dir.is_relative_to(Path.home() / ".claude")

    def test_scratch_dir_matches_gitignore_target(self):
        assert (
            _scratch_dir() == PROJECT_ROOT / "var" / "scratch" / "hide_sensitive_sheets"
        )


# --- 課題②対応: process_class の課題ラベル指定と、失敗判定 ---------------------------


class _FakeSheets:
    """process_class のAPI層を差し替える偽環境。batchUpdateで状態を実際に変える。"""

    def __init__(self, monkeypatch, label):
        import hide_sensitive_sheets as m

        self.m = m
        self.label = label
        self.calls = []
        self.att_task_hidden = False
        self.att_task_protected = False
        self.sub_task_hidden = False
        sa = m.SA_EMAIL
        self.editors = [sa, "someone@example.com"]
        monkeypatch.setattr(m, "resolve_attendance_spreadsheet_id", lambda c: "ATT")
        monkeypatch.setattr(m, "_get_full_sheets_list", self._full)
        monkeypatch.setattr(m, "_get_writer_emails", lambda fid: self.editors)
        monkeypatch.setattr(m, "TASK1_SUBMISSION_SPREADSHEET_IDS", {"01": "SUB"})
        monkeypatch.setattr(m, "_get_sheet_properties_list", self._props)
        monkeypatch.setattr(m, "_batch_update", self._batch)

    def _full(self, sid, build_service_fn=None):
        roster = {
            "properties": {"sheetId": 1, "title": "受講者リスト", "hidden": True},
            "protectedRanges": [{"range": {"sheetId": 1}}],
        }
        task = {
            "properties": {
                "sheetId": 2,
                "title": self.label,
                "hidden": self.att_task_hidden,
            },
            "protectedRanges": (
                [{"range": {"sheetId": 2}}] if self.att_task_protected else []
            ),
        }
        return [roster, task]

    def _props(self, sid, build_service_fn=None):
        return [{"sheetId": 3, "title": self.label, "hidden": self.sub_task_hidden}]

    def task_calls(self):
        """課題タブ(管理側sheetId=2・提出記録側)に触れた呼び出しだけ(受講者リストの列非表示は除く)。"""
        out = []
        for sid, reqs in self.calls:
            for r in reqs:
                prop = r.get("updateSheetProperties", {}).get("properties", {})
                if sid == "SUB" or prop.get("sheetId") == 2 or "addProtectedRange" in r:
                    out.append((sid, r))
        return out

    def _batch(self, sid, requests, build_service_fn=None):
        self.calls.append((sid, requests))
        for r in requests:
            if "updateSheetProperties" in r:
                sheet_id = r["updateSheetProperties"]["properties"]["sheetId"]
                if sid == "ATT" and sheet_id == 2:
                    self.att_task_hidden = True
                if sid == "SUB":
                    self.sub_task_hidden = True
            if "addProtectedRange" in r:
                self.att_task_protected = True


def test_task2_hides_and_protects_only_the_task2_tabs(monkeypatch, tmp_path):
    fake = _FakeSheets(monkeypatch, "課題②")

    result = fake.m.process_class("01", True, tmp_path, "課題②")

    assert result["task"] == "課題②"
    assert result["dest_task1"]["status"] == "applied"
    assert result["dest_task1"]["after_hidden"] is True
    assert result["dest_task1"]["after_protected"] is True
    # 提出記録シート側は非表示だけ(保護はしない)
    assert result["task1"]["status"] == "applied"
    assert result["task1"]["after_hidden"] is True
    sub_calls = [reqs for sid, reqs in fake.calls if sid == "SUB"]
    assert sub_calls and not any("addProtectedRange" in r for r in sub_calls[0])
    assert fake.m.failed_results([result]) == []


def test_task2_dry_run_changes_nothing(monkeypatch, tmp_path):
    fake = _FakeSheets(monkeypatch, "課題②")

    result = fake.m.process_class("01", False, tmp_path, "課題②")

    assert fake.calls == []  # dry-runは受講者リストを含め何も書かない
    assert result["dest_task1"]["status"] == "dry-run"
    assert result["task1"]["status"] == "dry-run"


def test_task2_rerun_is_idempotent(monkeypatch, tmp_path):
    fake = _FakeSheets(monkeypatch, "課題②")
    fake.m.process_class("01", True, tmp_path, "課題②")
    fake.calls.clear()

    result = fake.m.process_class("01", True, tmp_path, "課題②")

    assert fake.task_calls() == []
    assert result["dest_task1"]["status"] == "already_applied"
    assert result["task1"]["status"] == "already_hidden"


def test_default_task_is_task1_and_does_not_touch_task2_tab(monkeypatch, tmp_path):
    fake = _FakeSheets(monkeypatch, "課題②")  # 課題②タブしか無い環境で課題①を処理する

    result = fake.m.process_class("01", True, tmp_path)

    assert result["task"] == "課題①"
    assert result["dest_task1"]["status"] == "skipped"
    assert result["task1"]["status"] == "skipped"
    assert fake.task_calls() == []


class TestFailedResults:
    def test_ok_results_have_no_failures(self):
        from hide_sensitive_sheets import failed_results

        ok = {
            "class": "01",
            "task": "課題②",
            "roster": {"status": "already_applied"},
            "task1": {"status": "applied", "after_hidden": True},
            "dest_task1": {
                "status": "applied",
                "after_hidden": True,
                "after_protected": True,
            },
        }
        assert failed_results([ok]) == []

    @pytest.mark.parametrize(
        "slot,value",
        [
            ("roster", {"status": "error", "detail": "x"}),
            ("task1", {"status": "error", "detail": "x"}),
            ("dest_task1", {"status": "applied_verification_failed"}),
            ("task1", {"status": "applied", "after_hidden": False}),
            ("task1", {"status": "applied", "after_hidden": None}),
            (
                "dest_task1",
                {"status": "applied", "after_hidden": True, "after_protected": False},
            ),
        ],
    )
    def test_error_or_unverified_results_are_failures(self, slot, value):
        from hide_sensitive_sheets import failed_results

        result = {
            "class": "01",
            "task": "課題②",
            "roster": {"status": "already_applied"},
            "task1": {"status": "already_hidden"},
            "dest_task1": {"status": "already_applied"},
        }
        result[slot] = value
        failures = failed_results([result])
        assert len(failures) == 1
        assert "01" in failures[0] and "課題②" in failures[0]

    def test_skipped_and_dry_run_are_not_failures(self):
        from hide_sensitive_sheets import failed_results

        result = {
            "class": "01",
            "task": "課題②",
            "roster": {"status": "skipped"},
            "task1": {"status": "dry-run"},
            "dest_task1": {"status": "skipped"},
        }
        assert failed_results([result]) == []
