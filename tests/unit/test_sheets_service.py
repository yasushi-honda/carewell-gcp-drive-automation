"""
Unit tests for SheetsService.get_attendance_roster_data().

クラス別出欠管理ファイル({No}_受講者リスト_出欠管理)の「受講者リスト」タブから
Firestore直接同期する新経路のリーダー。plan-crossreview（grip判断モード + codex
2パス）で承認された設計:
- ヘッダー完全一致検証(schema_error)
- 非連続レンジ(A2:C, F2:J)でD(会社)/E(事業所)列を物理的に取得しない
- read_error(API例外)とempty(正常系の空)を区別する
- 日介番号/氏名欠落行はmalformed_rowsへ退避(サイレントスキップしない)
"""

import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

sys.path.insert(0, "src")

from config.classes import ATTENDANCE_ROSTER_HEADER  # noqa: E402


@pytest.fixture
def sheets_service():
    """google.auth.default/googleapiclient.discovery.buildをモックしたSheetsServiceを返す。"""
    with patch("sheets_service.default") as mock_default, patch(
        "sheets_service.build"
    ) as mock_build:
        mock_default.return_value = (Mock(), "test-project")
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        from sheets_service import SheetsService

        service = SheetsService()
        yield service, mock_service


def _mock_header(mock_service, header):
    mock_service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": [header] if header is not None else []
    }


def _mock_batch_get(mock_service, left_rows, right_rows):
    mock_service.spreadsheets.return_value.values.return_value.batchGet.return_value.execute.return_value = {
        "valueRanges": [
            {"values": left_rows},
            {"values": right_rows},
        ]
    }


class TestGetAttendanceRosterDataHeaderValidation:
    def test_header_mismatch_returns_schema_error(self, sheets_service):
        service, mock_service = sheets_service
        _mock_header(mock_service, ["違う", "ヘッダー"])

        result = service.get_attendance_roster_data("sheet-id", "No1")

        assert result.status == "schema_error"
        assert result.students == []
        mock_service.spreadsheets.return_value.values.return_value.batchGet.assert_not_called()

    def test_missing_header_row_returns_schema_error(self, sheets_service):
        service, mock_service = sheets_service
        _mock_header(mock_service, None)

        result = service.get_attendance_roster_data("sheet-id", "No1")

        assert result.status == "schema_error"

    def test_matching_header_proceeds_to_batch_get(self, sheets_service):
        service, mock_service = sheets_service
        _mock_header(mock_service, ATTENDANCE_ROSTER_HEADER)
        _mock_batch_get(mock_service, [], [])

        result = service.get_attendance_roster_data("sheet-id", "No1")

        assert result.status == "empty"
        mock_service.spreadsheets.return_value.values.return_value.batchGet.assert_called_once()


class TestGetAttendanceRosterDataRangeSelection:
    def test_does_not_request_company_office_columns(self, sheets_service):
        """
        D(会社)・E(事業所)列を範囲指定そのものから除外していることを確認する
        （取得後に捨てるのではなく、そもそも取得しないデータ最小化の検証）。
        """
        service, mock_service = sheets_service
        _mock_header(mock_service, ATTENDANCE_ROSTER_HEADER)
        _mock_batch_get(mock_service, [], [])

        service.get_attendance_roster_data("sheet-id", "No1")

        call_kwargs = (
            mock_service.spreadsheets.return_value.values.return_value.batchGet.call_args.kwargs
        )
        ranges = call_kwargs["ranges"]
        assert ranges == ["'受講者リスト'!A2:C", "'受講者リスト'!F2:J"]
        assert not any("D" in r or "E" in r for r in ranges)


class TestGetAttendanceRosterDataRowMapping:
    def test_valid_row_maps_columns_correctly(self, sheets_service):
        service, mock_service = sheets_service
        _mock_header(mock_service, ATTENDANCE_ROSTER_HEADER)
        _mock_batch_get(
            mock_service,
            left_rows=[["山田太郎", "やまだたろう", "N9901234"]],
            right_rows=[["訪問介護", "通所系", "Aグループ", "A001", "A001g"]],
        )

        result = service.get_attendance_roster_data("sheet-id", "No1")

        assert result.status == "ok"
        assert len(result.students) == 1
        student = result.students[0]
        assert student == {
            "student_id": "N9901234",
            "furigana": "やまだたろう",
            "name": "山田太郎",
            "group": "Aグループ",
            "service_type": "訪問介護",
            "student_number": "A001",
            "serial_number": 0,
            "class_name": "No1",
        }
        assert "company" not in student
        assert "office" not in student

    def test_empty_group_defaults_to_未分類(self, sheets_service):
        service, mock_service = sheets_service
        _mock_header(mock_service, ATTENDANCE_ROSTER_HEADER)
        _mock_batch_get(
            mock_service,
            left_rows=[["山田太郎", "やまだたろう", "N9901234"]],
            right_rows=[["訪問介護", "", "", "A001", ""]],
        )

        result = service.get_attendance_roster_data("sheet-id", "No1")

        assert result.students[0]["group"] == "未分類"

    def test_fully_blank_row_is_skipped(self, sheets_service):
        service, mock_service = sheets_service
        _mock_header(mock_service, ATTENDANCE_ROSTER_HEADER)
        _mock_batch_get(
            mock_service,
            left_rows=[["", "", ""], ["山田太郎", "やまだたろう", "N9901234"]],
            right_rows=[
                ["", "", "", "", ""],
                ["訪問介護", "", "Aグループ", "A001", ""],
            ],
        )

        result = service.get_attendance_roster_data("sheet-id", "No1")

        assert len(result.students) == 1
        assert result.malformed_rows == []

    def test_row_with_only_unused_g_or_j_column_is_not_treated_as_blank(
        self, sheets_service
    ):
        """
        G列(入所・居宅系)・J列(受講者番号(グループ付き))はFirestoreへ
        マッピングしないが、空行判定の対象からは除外しない。除外すると、
        A/B/C/F/H/I列が全て空でG列またはJ列にのみ値がある行を「完全空行」
        として誤ってスキップし、malformed_rows検出をすり抜けてしまう
        (codex実装レビュー指摘P2対応)。
        """
        service, mock_service = sheets_service
        _mock_header(mock_service, ATTENDANCE_ROSTER_HEADER)
        _mock_batch_get(
            mock_service,
            left_rows=[["", "", ""]],
            right_rows=[["", "何か入所居宅系データ", "", "", ""]],
        )

        result = service.get_attendance_roster_data("sheet-id", "No1")

        assert result.students == []
        assert result.malformed_rows == [{"row": 2, "name": "", "student_id": ""}]

    def test_missing_student_id_goes_to_malformed_rows(self, sheets_service):
        service, mock_service = sheets_service
        _mock_header(mock_service, ATTENDANCE_ROSTER_HEADER)
        _mock_batch_get(
            mock_service,
            left_rows=[["山田太郎", "やまだたろう", ""]],
            right_rows=[["訪問介護", "", "Aグループ", "A001", ""]],
        )

        result = service.get_attendance_roster_data("sheet-id", "No1")

        assert result.students == []
        assert result.malformed_rows == [
            {"row": 2, "name": "山田太郎", "student_id": ""}
        ]

    def test_missing_name_goes_to_malformed_rows(self, sheets_service):
        service, mock_service = sheets_service
        _mock_header(mock_service, ATTENDANCE_ROSTER_HEADER)
        _mock_batch_get(
            mock_service,
            left_rows=[["", "やまだたろう", "N9901234"]],
            right_rows=[["訪問介護", "", "Aグループ", "A001", ""]],
        )

        result = service.get_attendance_roster_data("sheet-id", "No1")

        assert result.students == []
        assert result.malformed_rows == [
            {"row": 2, "name": "", "student_id": "N9901234"}
        ]

    def test_duplicate_student_id_within_class_is_not_deduplicated(
        self, sheets_service
    ):
        """
        クラス内の日介番号重複は本メソッド内で握りつぶさず、重複を含めてそのまま
        返す。重複の検出・遮断は呼び出し側(main.py、クラス横断分とまとめて統一
        処理)が担う(plan-crossreview codex指摘: クラス内限定の先勝ちは実質的な
        後勝ち事故に繋がるため廃止)。
        """
        service, mock_service = sheets_service
        _mock_header(mock_service, ATTENDANCE_ROSTER_HEADER)
        _mock_batch_get(
            mock_service,
            left_rows=[
                ["山田太郎", "やまだたろう", "N9901234"],
                ["山田次郎", "やまだじろう", "N9901234"],
            ],
            right_rows=[
                ["訪問介護", "", "Aグループ", "A001", ""],
                ["訪問介護", "", "Bグループ", "A002", ""],
            ],
        )

        result = service.get_attendance_roster_data("sheet-id", "No1")

        assert len(result.students) == 2
        assert [s["student_id"] for s in result.students] == ["N9901234", "N9901234"]

    def test_short_rows_are_padded_before_combining(self, sheets_service):
        """
        Sheets APIは行末尾の空セルを省略して返すため、各レンジの各行を期待列数
        までパディングしてから行インデックス基準で結合する（単純な配列zipでは
        右レンジの短い行がずれて別の列にマッピングされてしまう）。
        """
        service, mock_service = sheets_service
        _mock_header(mock_service, ATTENDANCE_ROSTER_HEADER)
        _mock_batch_get(
            mock_service,
            # 左レンジは3列とも埋まっているが、右レンジは末尾セルが空のため
            # APIから1列分しか返らない状況を再現する
            left_rows=[["山田太郎", "やまだたろう", "N9901234"]],
            right_rows=[["訪問介護"]],
        )

        result = service.get_attendance_roster_data("sheet-id", "No1")

        student = result.students[0]
        assert student["service_type"] == "訪問介護"
        assert student["group"] == "未分類"
        assert student["student_number"] == ""


class TestGetAttendanceRosterDataErrorHandling:
    def test_api_exception_returns_read_error_not_empty(self, sheets_service):
        """
        「正常系の0件」(empty)と「取得失敗」(read_error)を同じ空リストとして
        返さない（common-mistakes.md パターン9の再発防止）。
        """
        service, mock_service = sheets_service
        mock_service.spreadsheets.return_value.values.return_value.get.return_value.execute.side_effect = Exception(
            "403 Forbidden"
        )

        result = service.get_attendance_roster_data("sheet-id", "No5")

        assert result.status == "read_error"
        assert result.students == []
        assert "403 Forbidden" in result.error_detail

    def test_batch_get_exception_returns_read_error(self, sheets_service):
        service, mock_service = sheets_service
        _mock_header(mock_service, ATTENDANCE_ROSTER_HEADER)
        batch_get_mock = (
            mock_service.spreadsheets.return_value.values.return_value.batchGet
        )
        batch_get_mock.return_value.execute.side_effect = Exception("network error")

        result = service.get_attendance_roster_data("sheet-id", "No5")

        assert result.status == "read_error"
