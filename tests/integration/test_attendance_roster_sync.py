"""
Integration tests for _sync_students_from_attendance_rosters() against the
Firestore Emulator.

FirestoreServiceの内部ロジック(create_student/get_student_ids_by_class_and_source/
mark_student_withdrawn)は単体テストでモック済みだが、実際のFirestoreクエリ
(where句の複合条件)が意図通りに動くかはエミュレータでの結合テストでのみ
検証できる。plan-crossreview検証項目(d)(e)に対応。
"""

import sys

import pytest

sys.path.insert(0, "src")


class TestAttendanceRosterSyncPreservesManualStatus:
    """検証項目(d): 手動で「辞退」に設定した学生のstatusが同期で巻き戻らないこと。"""

    @pytest.fixture(autouse=True)
    def setup(self, emulator_client):
        from firestore_service import FirestoreService

        self.db = emulator_client
        self.service = FirestoreService()
        self.service.db = emulator_client

    def test_manually_withdrawn_status_is_not_reverted_by_resync(self):
        from main import _sync_students_from_attendance_rosters
        from sheets_service import RosterReadResult

        student_id = "N9901111"
        self.db.collection("students").document(student_id).set(
            {
                "student_id": student_id,
                "name": "テスト太郎",
                "furigana": "てすとたろう",
                "class_name": "No1",
                "status": "withdrawn",  # Dashboardから手動で「辞退」設定済み
                "sync_source": "attendance_roster",
            }
        )

        sheets_service = _FakeSheetsService(
            {
                "01": RosterReadResult(
                    class_name="No1",
                    status="ok",
                    students=[
                        {
                            "student_id": student_id,
                            "furigana": "てすとたろう",
                            "name": "テスト太郎",
                            "group": "Aグループ",
                            "service_type": "訪問介護",
                            "student_number": "A001",
                            "serial_number": 0,
                            "class_name": "No1",
                        }
                    ],
                ),
            }
        )

        result = _sync_students_from_attendance_rosters(
            sheets_service, self.service, dry_run=False
        )

        assert result["status"] == "success"
        student_doc = (
            self.db.collection("students").document(student_id).get().to_dict()
        )
        assert (
            student_doc["status"] == "withdrawn"
        ), "手動で設定したwithdrawnステータスが再同期で巻き戻ってはならない"

    def test_new_student_gets_active_status(self):
        from main import _sync_students_from_attendance_rosters
        from sheets_service import RosterReadResult

        student_id = "N9901222"
        sheets_service = _FakeSheetsService(
            {
                "01": RosterReadResult(
                    class_name="No1",
                    status="ok",
                    students=[
                        {
                            "student_id": student_id,
                            "furigana": "しんきたろう",
                            "name": "新規太郎",
                            "group": "Aグループ",
                            "service_type": "訪問介護",
                            "student_number": "A002",
                            "serial_number": 0,
                            "class_name": "No1",
                        }
                    ],
                ),
            }
        )

        result = _sync_students_from_attendance_rosters(
            sheets_service, self.service, dry_run=False
        )

        assert result["status"] == "success"
        student_doc = (
            self.db.collection("students").document(student_id).get().to_dict()
        )
        assert student_doc["status"] == "active"
        assert "company" not in student_doc
        assert "office" not in student_doc


class TestAttendanceRosterSyncReconcile:
    """検証項目(e): 名簿から消えた受講者がwithdrawn化されること(reconcile)。"""

    @pytest.fixture(autouse=True)
    def setup(self, emulator_client):
        from firestore_service import FirestoreService

        self.db = emulator_client
        self.service = FirestoreService()
        self.service.db = emulator_client

    def test_student_missing_from_roster_becomes_withdrawn(self):
        from main import _sync_students_from_attendance_rosters
        from sheets_service import RosterReadResult

        stays_id = "N9902001"
        leaves_id = "N9902002"

        for sid, name in [(stays_id, "残留太郎"), (leaves_id, "退会次郎")]:
            self.db.collection("students").document(sid).set(
                {
                    "student_id": sid,
                    "name": name,
                    "class_name": "No1",
                    "status": "active",
                    "sync_source": "attendance_roster",
                }
            )

        # 今回の名簿にはstays_idのみが存在する(leaves_idは名簿から消えた想定)
        sheets_service = _FakeSheetsService(
            {
                "01": RosterReadResult(
                    class_name="No1",
                    status="ok",
                    students=[
                        {
                            "student_id": stays_id,
                            "furigana": "ざんりゅうたろう",
                            "name": "残留太郎",
                            "group": "Aグループ",
                            "service_type": "訪問介護",
                            "student_number": "A001",
                            "serial_number": 0,
                            "class_name": "No1",
                        }
                    ],
                ),
            }
        )

        result = _sync_students_from_attendance_rosters(
            sheets_service, self.service, dry_run=False
        )

        assert result["status"] == "success"
        no1_summary = next(c for c in result["classes"] if c["class_name"] == "No1")
        assert no1_summary["withdrawn"] == 1

        stays_doc = self.db.collection("students").document(stays_id).get().to_dict()
        assert stays_doc["status"] == "active"

        leaves_doc = self.db.collection("students").document(leaves_id).get().to_dict()
        assert leaves_doc["status"] == "withdrawn"

    def test_reconcile_does_not_touch_students_from_other_sync_source(self):
        """
        統合_受講者リスト経由(sync_source未設定)で作成された学生は、
        出欠名簿同期のreconcile対象に含まれないこと(class_name一致だけでなく
        sync_source一致も条件にしているため)。
        """
        from main import _sync_students_from_attendance_rosters
        from sheets_service import RosterReadResult

        legacy_id = "N9902999"
        self.db.collection("students").document(legacy_id).set(
            {
                "student_id": legacy_id,
                "name": "旧経路太郎",
                "class_name": "No1",
                "status": "active",
                # sync_source未設定 = 統合_受講者リスト経由を模擬
            }
        )

        sheets_service = _FakeSheetsService(
            {
                "01": RosterReadResult(class_name="No1", status="empty", students=[]),
            }
        )

        result = _sync_students_from_attendance_rosters(
            sheets_service, self.service, dry_run=False
        )

        assert result["status"] == "success"
        legacy_doc = self.db.collection("students").document(legacy_id).get().to_dict()
        assert (
            legacy_doc["status"] == "active"
        ), "sync_source不一致の学生はreconcileの対象外であるべき"


class _FakeSheetsService:
    """
    ATTENDANCE_ROSTER_FILE_IDSのキー(クラス番号)に対応するRosterReadResultを
    あらかじめ用意しておき、get_attendance_roster_data()呼び出し時に返す
    テスト用ダブル。実Sheets APIへは一切アクセスしない。
    """

    def __init__(self, results_by_class_num):
        self._results_by_class_num = results_by_class_num

    def get_attendance_roster_data(self, spreadsheet_id, class_name):
        for class_num, result in self._results_by_class_num.items():
            if result.class_name == class_name:
                return result
        # 未登録クラス(テストで明示的に用意していないクラス)は空扱いにする
        from sheets_service import RosterReadResult

        return RosterReadResult(class_name=class_name, status="empty", students=[])
