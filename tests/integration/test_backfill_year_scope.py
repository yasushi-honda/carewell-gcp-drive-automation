"""
Integration tests for _backfill_all_files year-scoping (Issue #5 Phase 2).

_backfill_all_files scans the live "submissions" collection without any
year filter, so triggering it via the Dashboard sync button could overwrite
denormalized student fields on files belonging to a prior academic year's
class (still retained in Firestore) with the current year's roster data.
These tests verify that only classes in the current year's KNOWN_CLASSES
are touched.
"""

import sys

import pytest

sys.path.insert(0, "src")


class TestBackfillYearScope:
    """Integration tests for year-scoped backfill."""

    @pytest.fixture(autouse=True)
    def setup(self, emulator_client):
        """Set up test fixtures."""
        from firestore_service import FirestoreService

        self.db = emulator_client
        self.service = FirestoreService()
        self.service.db = emulator_client

    def _create_file(self, class_name, task_id, student_id, composite_key, group):
        files_ref = (
            self.db.collection("submissions")
            .document(class_name)
            .collection("tasks")
            .document(task_id)
            .collection("files")
        )
        files_ref.document(composite_key).set(
            {
                "student_id": student_id,
                "filename": "test.pdf",
                "student_group": group,
            }
        )
        return files_ref.document(composite_key)

    def test_backfill_skips_classes_outside_known_classes(self):
        """
        Scenario:
        1. A file exists under a current-year class (in KNOWN_CLASSES) and
           under a prior-year class (retained in Firestore, NOT in
           KNOWN_CLASSES), both referencing the same student_id.
        2. The students collection holds the current roster's group value.
        3. After _backfill_all_files runs, the current-year file is updated
           to the current group, but the prior-year file's group is
           untouched (proves prior-year data is not silently overwritten).
        """
        from config.classes import KNOWN_CLASSES
        from main import _backfill_all_files

        current_class = KNOWN_CLASSES[0]
        prior_class = "令和7年度 デジタル中核人材養成研修 №01"
        assert prior_class not in KNOWN_CLASSES, (
            "test fixture must use a class name absent from the current "
            "year's KNOWN_CLASSES to exercise the year-scoping guard"
        )
        task_id = "課題①"
        student_id = "N9902913"

        self.db.collection("students").document(student_id).set(
            {
                "student_id": student_id,
                "furigana": "テストタロウ",
                "name": "テスト太郎",
                "group": "今年度グループ",
                "status": "active",
                "company": "",
                "office": "",
                "service_type": "",
                "serial_number": 1,
                "student_number": "S001",
                "class_name": current_class,
            }
        )

        current_file_ref = self._create_file(
            current_class, task_id, student_id, "current_key", "旧グループ"
        )
        prior_file_ref = self._create_file(
            prior_class, task_id, student_id, "prior_key", "旧グループ"
        )

        result = _backfill_all_files(self.service)

        assert result["status"] == "success"
        assert result["files_updated"] == 1, (
            "only the current-year class's file should be updated, "
            f"got result={result}"
        )

        current_file = current_file_ref.get().to_dict()
        assert (
            current_file["student_group"] == "今年度グループ"
        ), "current-year file should be backfilled with current roster data"

        prior_file = prior_file_ref.get().to_dict()
        assert (
            prior_file["student_group"] == "旧グループ"
        ), "prior-year file must remain untouched by a current-year sync"
