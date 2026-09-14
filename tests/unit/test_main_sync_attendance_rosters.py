"""
Unit tests for main._sync_students_from_attendance_rosters().

二段階実行(フェーズA: 全クラス収集・検証 → フェーズB: 書込み+reconcile)の
fail-closed設計を、SheetsService/FirestoreServiceをモックして検証する。
plan-crossreview（grip判断モード + codex 2パス）で承認された設計。
"""

import sys
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, "src")

import main  # noqa: E402
from sheets_service import RosterReadResult  # noqa: E402

TEST_FILE_IDS = {"01": "sheet-id-01", "02": "sheet-id-02"}


def _student(student_id, name="山田太郎", class_name="No1"):
    return {
        "student_id": student_id,
        "furigana": "やまだたろう",
        "name": name,
        "group": "Aグループ",
        "service_type": "訪問介護",
        "student_number": "A001",
        "serial_number": 0,
        "class_name": class_name,
    }


@pytest.fixture
def patched_config():
    with patch.dict(main.ATTENDANCE_ROSTER_FILE_IDS, TEST_FILE_IDS, clear=True), patch(
        "main.KNOWN_CLASSES", ["dummy"] * 2
    ):
        yield


class TestPhaseAAbortConditions:
    def test_aborts_on_read_error_without_any_writes(self, patched_config):
        sheets_service = Mock()
        sheets_service.get_attendance_roster_data.side_effect = [
            RosterReadResult(
                class_name="No1", status="ok", students=[_student("N001")]
            ),
            RosterReadResult(
                class_name="No2", status="read_error", error_detail="403 Forbidden"
            ),
        ]
        firestore_service = Mock()

        result = main._sync_students_from_attendance_rosters(
            sheets_service, firestore_service
        )

        assert result["status"] == "aborted"
        assert len(result["error_classes"]) == 1
        assert result["error_classes"][0]["class_name"] == "No2"
        firestore_service.create_student.assert_not_called()

    def test_aborts_on_schema_error(self, patched_config):
        sheets_service = Mock()
        sheets_service.get_attendance_roster_data.side_effect = [
            RosterReadResult(
                class_name="No1", status="ok", students=[_student("N001")]
            ),
            RosterReadResult(class_name="No2", status="schema_error"),
        ]
        firestore_service = Mock()

        result = main._sync_students_from_attendance_rosters(
            sheets_service, firestore_service
        )

        assert result["status"] == "aborted"
        firestore_service.create_student.assert_not_called()

    def test_aborts_on_duplicate_student_id_across_classes(self, patched_config):
        """クラスを跨いだ日介番号重複はフェーズAで検出され、書込み全体が中断される。"""
        sheets_service = Mock()
        sheets_service.get_attendance_roster_data.side_effect = [
            RosterReadResult(
                class_name="No1",
                status="ok",
                students=[_student("N001", class_name="No1")],
            ),
            RosterReadResult(
                class_name="No2",
                status="ok",
                students=[_student("N001", class_name="No2")],
            ),
        ]
        firestore_service = Mock()

        result = main._sync_students_from_attendance_rosters(
            sheets_service, firestore_service
        )

        assert result["status"] == "aborted"
        assert result["duplicate_student_ids"] == [
            {"student_id": "N001", "classes": ["No1", "No2"]}
        ]
        firestore_service.create_student.assert_not_called()

    def test_aborts_on_duplicate_student_id_within_same_class(self, patched_config):
        """クラス内の重複も(クラス横断と区別せず)同じ経路で検出・中断される。"""
        sheets_service = Mock()
        sheets_service.get_attendance_roster_data.side_effect = [
            RosterReadResult(
                class_name="No1",
                status="ok",
                students=[
                    _student("N001", class_name="No1"),
                    _student("N001", class_name="No1"),
                ],
            ),
            RosterReadResult(class_name="No2", status="empty", students=[]),
        ]
        firestore_service = Mock()

        result = main._sync_students_from_attendance_rosters(
            sheets_service, firestore_service
        )

        assert result["status"] == "aborted"
        firestore_service.create_student.assert_not_called()

    def test_aborts_on_malformed_rows(self, patched_config):
        sheets_service = Mock()
        sheets_service.get_attendance_roster_data.side_effect = [
            RosterReadResult(
                class_name="No1",
                status="ok",
                students=[_student("N001")],
                malformed_rows=[{"row": 5, "name": "", "student_id": "N002"}],
            ),
            RosterReadResult(class_name="No2", status="empty", students=[]),
        ]
        firestore_service = Mock()

        result = main._sync_students_from_attendance_rosters(
            sheets_service, firestore_service
        )

        assert result["status"] == "aborted"
        assert result["malformed_rows"][0]["class_name"] == "No1"
        firestore_service.create_student.assert_not_called()

    def test_not_configured_classes_are_reported(self, patched_config):
        sheets_service = Mock()
        sheets_service.get_attendance_roster_data.side_effect = [
            RosterReadResult(class_name="No1", status="empty", students=[]),
            RosterReadResult(class_name="No2", status="empty", students=[]),
        ]
        firestore_service = Mock()
        firestore_service.get_student_ids_by_class_and_source.return_value = {}

        result = main._sync_students_from_attendance_rosters(
            sheets_service, firestore_service
        )

        # patched_config: KNOWN_CLASSESは2クラス分、ATTENDANCE_ROSTER_FILE_IDSは
        # No1/No2の2クラスとも設定済みのため、未設定クラスは0件になるはず
        assert result["not_configured_classes"] == []


class TestDryRun:
    def test_dry_run_never_writes_even_when_all_ok(self, patched_config):
        sheets_service = Mock()
        sheets_service.get_attendance_roster_data.side_effect = [
            RosterReadResult(
                class_name="No1", status="ok", students=[_student("N001")]
            ),
            RosterReadResult(class_name="No2", status="empty", students=[]),
        ]
        firestore_service = Mock()

        result = main._sync_students_from_attendance_rosters(
            sheets_service, firestore_service, dry_run=True
        )

        assert result["status"] == "success"
        assert result["dry_run"] is True
        firestore_service.create_student.assert_not_called()
        firestore_service.mark_student_withdrawn.assert_not_called()


class TestPhaseBWrite:
    def test_successful_sync_writes_and_returns_class_summary(self, patched_config):
        sheets_service = Mock()
        sheets_service.get_attendance_roster_data.side_effect = [
            RosterReadResult(
                class_name="No1",
                status="ok",
                students=[_student("N001"), _student("N002")],
            ),
            RosterReadResult(class_name="No2", status="empty", students=[]),
        ]
        firestore_service = Mock()
        firestore_service.student_exists.return_value = False
        firestore_service.create_student.return_value = True
        firestore_service.get_student_ids_by_class_and_source.return_value = {
            "N001": "active",
            "N002": "active",
        }

        result = main._sync_students_from_attendance_rosters(
            sheets_service, firestore_service
        )

        assert result["status"] == "success"
        no1_summary = next(c for c in result["classes"] if c["class_name"] == "No1")
        assert no1_summary["created"] == 2
        assert no1_summary["synced"] == 2
        assert no1_summary["write_failed"] == 0
        # create_studentはpreserve_existing_status=True, sync_source="attendance_roster"で
        # 呼ばれること
        for call in firestore_service.create_student.call_args_list:
            assert call.kwargs["preserve_existing_status"] is True
            assert call.kwargs["sync_source"] == "attendance_roster"

    def test_reconcile_marks_students_missing_from_roster_as_withdrawn(
        self, patched_config
    ):
        sheets_service = Mock()
        sheets_service.get_attendance_roster_data.side_effect = [
            RosterReadResult(
                class_name="No1", status="ok", students=[_student("N001")]
            ),
            RosterReadResult(class_name="No2", status="empty", students=[]),
        ]
        firestore_service = Mock()
        firestore_service.student_exists.return_value = True
        firestore_service.create_student.return_value = True
        # N001は今回の名簿にいる。N999は既存だが今回の名簿に含まれない=退会扱い。
        # No2はクラス名が異なるため空のマッピングを返す(No1のみこのシナリオを再現する)。
        firestore_service.get_student_ids_by_class_and_source.side_effect = (
            lambda class_name, sync_source: (
                {"N001": "active", "N999": "active"} if class_name == "No1" else {}
            )
        )
        firestore_service.mark_student_withdrawn.return_value = True

        result = main._sync_students_from_attendance_rosters(
            sheets_service, firestore_service
        )

        firestore_service.mark_student_withdrawn.assert_called_once_with("N999")
        no1_summary = next(c for c in result["classes"] if c["class_name"] == "No1")
        assert no1_summary["withdrawn"] == 1

    def test_reconcile_skips_students_already_withdrawn(self, patched_config):
        sheets_service = Mock()
        sheets_service.get_attendance_roster_data.side_effect = [
            RosterReadResult(
                class_name="No1", status="ok", students=[_student("N001")]
            ),
            RosterReadResult(class_name="No2", status="empty", students=[]),
        ]
        firestore_service = Mock()
        firestore_service.student_exists.return_value = True
        firestore_service.create_student.return_value = True
        firestore_service.get_student_ids_by_class_and_source.side_effect = (
            lambda class_name, sync_source: (
                {"N001": "active", "N999": "withdrawn"} if class_name == "No1" else {}
            )
        )

        main._sync_students_from_attendance_rosters(sheets_service, firestore_service)

        firestore_service.mark_student_withdrawn.assert_not_called()

    def test_class_write_failure_skips_reconcile_but_other_classes_continue(
        self, patched_config
    ):
        """
        1クラス内で書込み失敗が起きた場合、そのクラスのreconcileはスキップし、
        他クラスの処理は継続する（部分的に書けたクラスに対してreconcileを実行し、
        書けなかった人を誤ってwithdrawn扱いにする事故を防ぐ）。
        """
        sheets_service = Mock()
        sheets_service.get_attendance_roster_data.side_effect = [
            RosterReadResult(
                class_name="No1",
                status="ok",
                students=[_student("N001", class_name="No1")],
            ),
            RosterReadResult(
                class_name="No2",
                status="ok",
                students=[_student("N002", class_name="No2")],
            ),
        ]
        firestore_service = Mock()
        firestore_service.student_exists.return_value = False

        def create_student_side_effect(student, **kwargs):
            return student["class_name"] != "No1"  # No1のみ書込み失敗を模擬

        firestore_service.create_student.side_effect = create_student_side_effect
        firestore_service.get_student_ids_by_class_and_source.return_value = {}

        result = main._sync_students_from_attendance_rosters(
            sheets_service, firestore_service
        )

        no1_summary = next(c for c in result["classes"] if c["class_name"] == "No1")
        no2_summary = next(c for c in result["classes"] if c["class_name"] == "No2")

        assert no1_summary["write_failed"] == 1
        assert no1_summary["withdrawn"] == 0
        assert no2_summary["write_failed"] == 0
        assert no2_summary["created"] == 1

        # No1のreconcileはスキップされるため、No1についてget_student_ids_by_class_and_source
        # が呼ばれないこと、No2については呼ばれることを確認する
        called_classes = [
            call.args[0]
            for call in firestore_service.get_student_ids_by_class_and_source.call_args_list
        ]
        assert "No1" not in called_classes
        assert "No2" in called_classes

    def test_reconcile_query_failure_is_recorded_as_write_failed(self, patched_config):
        sheets_service = Mock()
        sheets_service.get_attendance_roster_data.side_effect = [
            RosterReadResult(
                class_name="No1", status="ok", students=[_student("N001")]
            ),
            RosterReadResult(class_name="No2", status="empty", students=[]),
        ]
        firestore_service = Mock()
        firestore_service.student_exists.return_value = False
        firestore_service.create_student.return_value = True
        firestore_service.get_student_ids_by_class_and_source.side_effect = Exception(
            "Firestore unavailable"
        )

        result = main._sync_students_from_attendance_rosters(
            sheets_service, firestore_service
        )

        no1_summary = next(c for c in result["classes"] if c["class_name"] == "No1")
        assert no1_summary["write_failed"] == 1
        assert no1_summary["withdrawn"] == 0
