"""
Unit tests for scripts/hide_sensitive_sheets.py の純粋関数(リクエスト組み立て・冪等性判定)。

ネットワーク呼び出し(Drive/Sheets API)を含む関数は対象外。
"""

import sys

import pytest

sys.path.insert(0, "scripts")

from hide_sensitive_sheets import (  # noqa: E402
    COMPANY_OFFICE_COLUMN_RANGE,
    _find_sheet_entry,
    _is_whole_sheet_protected,
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
