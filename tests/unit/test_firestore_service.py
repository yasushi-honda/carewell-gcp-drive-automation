"""
Unit tests for FirestoreService class.

These tests use mocking to avoid actual Firestore operations.
"""

from unittest.mock import Mock, patch

import pytest
from google.cloud import firestore as firestore_module


class TestFirestoreService:
    """Test suite for FirestoreService class."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        # Import here to avoid circular imports
        import sys

        sys.path.insert(0, "src")
        from firestore_service import FirestoreService

        self.FirestoreService = FirestoreService

    @patch("firestore_service.resolve_firestore_database_id")
    @patch("firestore_service.firestore.Client")
    def test_init(self, mock_client, mock_resolve_db_id):
        """Test FirestoreService initialization."""
        # 2026-09-14 year-separation change: FirestoreService no longer hardcodes
        # a database literal, it resolves it via resolve_firestore_database_id().
        # Mocking the resolver here (rather than calling the real function to
        # build the expectation) keeps this a correctness check on the wiring:
        # it would fail if firestore_service.py stopped calling the resolver,
        # independent of whatever value the real resolver happens to return.
        mock_resolve_db_id.return_value = "mocked-database-id"

        service = self.FirestoreService()

        mock_resolve_db_id.assert_called_once()
        mock_client.assert_called_once_with(database="mocked-database-id")
        assert service.db is not None

    def test_init_propagates_error_when_no_database_for_current_year(self):
        """
        resolve_firestore_database_id()がValueErrorを送出した場合、FirestoreService
        の初期化もそのまま失敗すること（途中で握りつぶされないこと）を確認する。
        """
        with patch(
            "firestore_service.resolve_firestore_database_id",
            side_effect=ValueError("no database configured for this year"),
        ):
            with pytest.raises(ValueError, match="no database configured"):
                self.FirestoreService()

    def test_update_task_metadata_creates_new_document(self):
        """Test that _update_task_metadata creates a new parent document."""
        with patch("firestore_service.firestore.Client") as mock_client:
            # Setup - New path: submissions/{class_name}/tasks/{task_id}
            mock_db = Mock()
            mock_client.return_value = mock_db

            mock_submissions_collection = Mock()
            mock_class_doc = Mock()
            mock_tasks_collection = Mock()
            mock_task_doc = Mock()

            mock_db.collection.return_value = mock_submissions_collection
            mock_submissions_collection.document.return_value = mock_class_doc
            mock_class_doc.collection.return_value = mock_tasks_collection
            mock_tasks_collection.document.return_value = mock_task_doc

            service = self.FirestoreService()

            # Execute
            class_name = "テストクラス"
            task_id = "課題①"
            task_pattern = "課題①業務分析　※～11/3〆切"

            result = service._update_task_metadata(class_name, task_id, task_pattern)

            # Assert
            assert result is True
            mock_db.collection.assert_called_once_with("submissions")
            mock_submissions_collection.document.assert_called_once_with(class_name)
            mock_class_doc.collection.assert_called_once_with("tasks")
            mock_tasks_collection.document.assert_called_once_with(task_id)

            # Verify set() was called with correct parameters
            mock_task_doc.set.assert_called_once()
            call_args = mock_task_doc.set.call_args

            # Check the data dictionary
            data = call_args[0][0]
            assert data["task_id"] == task_id
            assert data["task_pattern"] == task_pattern
            assert isinstance(data["file_count"], firestore_module.Increment)
            assert data["file_count"]._value == 1
            assert data["last_updated"] == firestore_module.SERVER_TIMESTAMP

            # Check merge=True is specified
            assert call_args[1]["merge"] is True

    def test_update_task_metadata_increments_file_count(self):
        """Test that _update_task_metadata uses Increment(1) for file_count."""
        with patch("firestore_service.firestore.Client") as mock_client:
            # Setup - New path: submissions/{class_name}/tasks/{task_id}
            mock_db = Mock()
            mock_client.return_value = mock_db

            mock_submissions_collection = Mock()
            mock_class_doc = Mock()
            mock_tasks_collection = Mock()
            mock_task_doc = Mock()

            mock_db.collection.return_value = mock_submissions_collection
            mock_submissions_collection.document.return_value = mock_class_doc
            mock_class_doc.collection.return_value = mock_tasks_collection
            mock_tasks_collection.document.return_value = mock_task_doc

            service = self.FirestoreService()

            # Execute
            result = service._update_task_metadata(
                "テストクラス", "課題①", "課題①パターン"
            )

            # Assert
            assert result is True

            # Verify Increment(1) was used for file_count
            call_args = mock_task_doc.set.call_args
            data = call_args[0][0]

            assert isinstance(data["file_count"], firestore_module.Increment)
            assert data["file_count"]._value == 1
            assert data["last_updated"] == firestore_module.SERVER_TIMESTAMP

    def test_update_task_metadata_fails_gracefully(self):
        """Test fail-open behavior: returns False on error without raising exception."""
        with patch("firestore_service.firestore.Client") as mock_client:
            # Setup - New path: submissions/{class_name}/tasks/{task_id}
            mock_db = Mock()
            mock_client.return_value = mock_db

            mock_submissions_collection = Mock()
            mock_class_doc = Mock()
            mock_tasks_collection = Mock()
            mock_task_doc = Mock()

            mock_db.collection.return_value = mock_submissions_collection
            mock_submissions_collection.document.return_value = mock_class_doc
            mock_class_doc.collection.return_value = mock_tasks_collection
            mock_tasks_collection.document.return_value = mock_task_doc

            # Simulate Firestore error
            mock_task_doc.set.side_effect = Exception("Firestore connection error")

            service = self.FirestoreService()

            # Execute
            result = service._update_task_metadata(
                "テストクラス", "課題①", "課題①パターン"
            )

            # Assert
            assert result is False
            # No exception should be raised (fail-open)

    def test_record_upload_updates_parent_and_adds_file(self):
        """Test that record_upload calls _update_task_metadata and creates file document."""
        with patch("firestore_service.firestore.Client") as mock_client:
            mock_db = Mock()
            mock_client.return_value = mock_db

            service = self.FirestoreService()

            # Patch _update_task_metadata to verify it's called
            with patch.object(
                service, "_update_task_metadata", return_value=True
            ) as mock_update:
                # Setup mock for file document creation
                # New path: submissions/{class_name}/tasks/{task_id}/files/{composite_key}
                mock_submissions_collection = Mock()
                mock_class_doc = Mock()
                mock_tasks_collection = Mock()
                mock_task_doc = Mock()
                mock_files_collection = Mock()
                mock_file_doc = Mock()

                mock_db.collection.return_value = mock_submissions_collection
                mock_submissions_collection.document.return_value = mock_class_doc
                mock_class_doc.collection.return_value = mock_tasks_collection
                mock_tasks_collection.document.return_value = mock_task_doc
                mock_task_doc.collection.return_value = mock_files_collection
                mock_files_collection.document.return_value = mock_file_doc

                # Execute
                result = service.record_upload(
                    class_name="テストクラス",
                    task_id="課題①",
                    student_name="テスト太郎",
                    student_id="N9902913",
                    filename="test.pdf",
                    drive_file_id="file123",
                    drive_folder_id="folder456",
                    submit_date="2025-10-12 10:00:00",
                    task_pattern="課題①業務分析",
                )

                # Assert
                assert result is True
                # Verify _update_task_metadata was called
                mock_update.assert_called_once_with(
                    "テストクラス", "課題①", "課題①業務分析"
                )
                # Verify file document was created
                mock_file_doc.set.assert_called_once()

    def test_record_upload_with_default_task_pattern(self):
        """Test that if task_pattern is None, task_id is used as default."""
        with patch("firestore_service.firestore.Client") as mock_client:
            # Setup - New path: submissions/{class_name}/tasks/{task_id}/files/{composite_key}
            mock_db = Mock()
            mock_client.return_value = mock_db

            mock_submissions_collection = Mock()
            mock_class_doc = Mock()
            mock_tasks_collection = Mock()
            mock_task_doc = Mock()
            mock_files_collection = Mock()
            mock_file_doc = Mock()

            mock_db.collection.return_value = mock_submissions_collection
            mock_submissions_collection.document.return_value = mock_class_doc
            mock_class_doc.collection.return_value = mock_tasks_collection
            mock_tasks_collection.document.return_value = mock_task_doc
            mock_task_doc.collection.return_value = mock_files_collection
            mock_files_collection.document.return_value = mock_file_doc

            service = self.FirestoreService()

            # Execute without task_pattern
            result = service.record_upload(
                class_name="テストクラス",
                task_id="課題①",
                student_name="テスト太郎",
                student_id="N9902913",
                filename="test.pdf",
                drive_file_id="file123",
                drive_folder_id="folder456",
                submit_date="2025-10-12 10:00:00",
            )

            # Assert
            assert result is True
            # Verify task_id was used as task_pattern
            # The task doc's set() is called by _update_task_metadata
            call_args = mock_task_doc.set.call_args_list[0]
            data = call_args[0][0]
            assert data["task_pattern"] == "課題①"

    def test_record_upload_continues_on_parent_update_failure(self):
        """Test fail-open: file document is created even if parent update fails."""
        with patch("firestore_service.firestore.Client") as mock_client:
            mock_db = Mock()
            mock_client.return_value = mock_db

            service = self.FirestoreService()

            # Patch _update_task_metadata to simulate failure (returns False)
            with patch.object(
                service, "_update_task_metadata", return_value=False
            ) as mock_update:
                # Setup mock for file document creation
                # New path: submissions/{class_name}/tasks/{task_id}/files/{composite_key}
                mock_submissions_collection = Mock()
                mock_class_doc = Mock()
                mock_tasks_collection = Mock()
                mock_task_doc = Mock()
                mock_files_collection = Mock()
                mock_file_doc = Mock()

                mock_db.collection.return_value = mock_submissions_collection
                mock_submissions_collection.document.return_value = mock_class_doc
                mock_class_doc.collection.return_value = mock_tasks_collection
                mock_tasks_collection.document.return_value = mock_task_doc
                mock_task_doc.collection.return_value = mock_files_collection
                mock_files_collection.document.return_value = mock_file_doc

                # Execute
                result = service.record_upload(
                    class_name="テストクラス",
                    task_id="課題①",
                    student_name="テスト太郎",
                    student_id="N9902913",
                    filename="test.pdf",
                    drive_file_id="file123",
                    drive_folder_id="folder456",
                    submit_date="2025-10-12 10:00:00",
                    task_pattern="課題①業務分析",
                )

                # Assert
                assert result is True  # Should still return True (fail-open)
                # Verify _update_task_metadata was called
                mock_update.assert_called_once()
                # Verify file document was still created despite parent update failure
                mock_file_doc.set.assert_called_once()

    def test_check_already_uploaded_unchanged(self):
        """Test that check_already_uploaded logic is unchanged and doesn't touch parent documents."""
        with patch("firestore_service.firestore.Client") as mock_client:
            # Setup - New path: submissions/{class_name}/tasks/{task_id}/files/{composite_key}
            mock_db = Mock()
            mock_client.return_value = mock_db

            mock_submissions_collection = Mock()
            mock_class_doc = Mock()
            mock_tasks_collection = Mock()
            mock_task_doc = Mock()
            mock_files_collection = Mock()
            mock_file_doc = Mock()
            mock_file_snapshot = Mock()

            mock_db.collection.return_value = mock_submissions_collection
            mock_submissions_collection.document.return_value = mock_class_doc
            mock_class_doc.collection.return_value = mock_tasks_collection
            mock_tasks_collection.document.return_value = mock_task_doc
            mock_task_doc.collection.return_value = mock_files_collection
            mock_files_collection.document.return_value = mock_file_doc
            mock_file_doc.get.return_value = mock_file_snapshot

            # Simulate file exists
            mock_file_snapshot.exists = True
            mock_file_snapshot.to_dict.return_value = {"filename": "test.pdf"}

            service = self.FirestoreService()

            # Execute
            result = service.check_already_uploaded(
                class_name="テストクラス",
                task_id="課題①",
                student_id="N9902913",
                filename="test.pdf",
                submit_date="2025-10-12 10:00:00",
            )

            # Assert
            assert result is not None
            assert result["filename"] == "test.pdf"
            # Verify only files subcollection was accessed, not parent document
            mock_task_doc.collection.assert_called_once_with("files")
            # Parent document should not be updated
            mock_task_doc.set.assert_not_called()
            mock_task_doc.update.assert_not_called()

    def test_update_sheets_sync_status_success(self):
        """Test update_sheets_sync_status successfully updates status to 'success'."""
        with patch("firestore_service.firestore.Client") as mock_client:
            mock_db = Mock()
            mock_client.return_value = mock_db

            mock_submissions_collection = Mock()
            mock_class_doc = Mock()
            mock_tasks_collection = Mock()
            mock_task_doc = Mock()
            mock_files_collection = Mock()
            mock_file_doc = Mock()

            mock_db.collection.return_value = mock_submissions_collection
            mock_submissions_collection.document.return_value = mock_class_doc
            mock_class_doc.collection.return_value = mock_tasks_collection
            mock_tasks_collection.document.return_value = mock_task_doc
            mock_task_doc.collection.return_value = mock_files_collection
            mock_files_collection.document.return_value = mock_file_doc

            service = self.FirestoreService()

            # Execute
            result = service.update_sheets_sync_status(
                class_name="テストクラス",
                task_id="課題①",
                student_id="N9902913",
                filename="test.pdf",
                submit_date="2025-10-12 10:00:00",
                status="success",
            )

            # Assert
            assert result is True
            mock_file_doc.update.assert_called_once()
            call_args = mock_file_doc.update.call_args[0][0]
            assert call_args["sheets_sync_status"] == "success"
            assert "sheets_sync_error" not in call_args

    def test_update_sheets_sync_status_failed_with_error_message(self):
        """Test update_sheets_sync_status records error message on failure."""
        with patch("firestore_service.firestore.Client") as mock_client:
            mock_db = Mock()
            mock_client.return_value = mock_db

            mock_submissions_collection = Mock()
            mock_class_doc = Mock()
            mock_tasks_collection = Mock()
            mock_task_doc = Mock()
            mock_files_collection = Mock()
            mock_file_doc = Mock()

            mock_db.collection.return_value = mock_submissions_collection
            mock_submissions_collection.document.return_value = mock_class_doc
            mock_class_doc.collection.return_value = mock_tasks_collection
            mock_tasks_collection.document.return_value = mock_task_doc
            mock_task_doc.collection.return_value = mock_files_collection
            mock_files_collection.document.return_value = mock_file_doc

            service = self.FirestoreService()

            # Execute
            result = service.update_sheets_sync_status(
                class_name="テストクラス",
                task_id="課題①",
                student_id="N9902913",
                filename="test.pdf",
                submit_date="2025-10-12 10:00:00",
                status="failed",
                error_message="API rate limit exceeded",
            )

            # Assert
            assert result is True
            mock_file_doc.update.assert_called_once()
            call_args = mock_file_doc.update.call_args[0][0]
            assert call_args["sheets_sync_status"] == "failed"
            assert call_args["sheets_sync_error"] == "API rate limit exceeded"

    def test_update_sheets_sync_status_handles_error(self):
        """Test update_sheets_sync_status returns False on Firestore error."""
        with patch("firestore_service.firestore.Client") as mock_client:
            mock_db = Mock()
            mock_client.return_value = mock_db

            mock_submissions_collection = Mock()
            mock_class_doc = Mock()
            mock_tasks_collection = Mock()
            mock_task_doc = Mock()
            mock_files_collection = Mock()
            mock_file_doc = Mock()

            mock_db.collection.return_value = mock_submissions_collection
            mock_submissions_collection.document.return_value = mock_class_doc
            mock_class_doc.collection.return_value = mock_tasks_collection
            mock_tasks_collection.document.return_value = mock_task_doc
            mock_task_doc.collection.return_value = mock_files_collection
            mock_files_collection.document.return_value = mock_file_doc

            # Simulate Firestore error
            mock_file_doc.update.side_effect = Exception("Firestore error")

            service = self.FirestoreService()

            # Execute
            result = service.update_sheets_sync_status(
                class_name="テストクラス",
                task_id="課題①",
                student_id="N9902913",
                filename="test.pdf",
                submit_date="2025-10-12 10:00:00",
                status="success",
            )

            # Assert
            assert result is False

    def test_record_upload_includes_sheets_sync_status(self):
        """Test that record_upload includes sheets_sync_status field."""
        with patch("firestore_service.firestore.Client") as mock_client:
            mock_db = Mock()
            mock_client.return_value = mock_db

            mock_submissions_collection = Mock()
            mock_class_doc = Mock()
            mock_tasks_collection = Mock()
            mock_task_doc = Mock()
            mock_files_collection = Mock()
            mock_file_doc = Mock()

            mock_db.collection.return_value = mock_submissions_collection
            mock_submissions_collection.document.return_value = mock_class_doc
            mock_class_doc.collection.return_value = mock_tasks_collection
            mock_tasks_collection.document.return_value = mock_task_doc
            mock_task_doc.collection.return_value = mock_files_collection
            mock_files_collection.document.return_value = mock_file_doc

            service = self.FirestoreService()

            # Execute
            result = service.record_upload(
                class_name="テストクラス",
                task_id="課題①",
                student_name="テスト太郎",
                student_id="N9902913",
                filename="test.pdf",
                drive_file_id="file123",
                drive_folder_id="folder456",
                submit_date="2025-10-12 10:00:00",
            )

            # Assert
            assert result is True
            mock_file_doc.set.assert_called_once()
            call_args = mock_file_doc.set.call_args[0][0]
            assert call_args["sheets_sync_status"] == "pending"


class TestCreateStudent:
    """Test suite for create_student() (出欠名簿同期の新経路対応、2026-09-14)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        import sys

        sys.path.insert(0, "src")
        from firestore_service import FirestoreService

        self.FirestoreService = FirestoreService

    def test_attendance_roster_sync_excludes_company_office_keys(self):
        """
        sync_source="attendance_roster"の場合、doc_dataにcompany/officeキー自体が
        含まれないこと（値が空文字ではなく、キー自体が無いことを確認する点に注意）。

        plan-crossreview codexレビュー指摘: 従来は入力student_dataのフィルタのみで、
        doc_data構築自体が固定テンプレートでcompany/officeを無条件に含んでいた
        ため機能しなかった。本テストはその再発防止。
        """
        with patch("firestore_service.firestore.Client") as mock_client:
            mock_db = Mock()
            mock_client.return_value = mock_db
            mock_doc_ref = Mock()
            mock_db.collection.return_value.document.return_value = mock_doc_ref

            service = self.FirestoreService()
            result = service.create_student(
                {
                    "student_id": "N001",
                    "name": "山田太郎",
                    # 万一呼び出し元の実装ミスで紛れ込んでも書かれないことを確認する
                    "company": "should-not-be-written",
                    "office": "should-not-be-written",
                },
                sync_source="attendance_roster",
            )

            assert result is True
            doc_data = mock_doc_ref.set.call_args[0][0]
            assert "company" not in doc_data
            assert "office" not in doc_data
            assert doc_data["sync_source"] == "attendance_roster"

    def test_default_sync_source_includes_company_office(self):
        """sync_source未指定(既存の統合_受講者リスト経由)は従来通りcompany/officeを含む回帰テスト。"""
        with patch("firestore_service.firestore.Client") as mock_client:
            mock_db = Mock()
            mock_client.return_value = mock_db
            mock_doc_ref = Mock()
            mock_db.collection.return_value.document.return_value = mock_doc_ref

            service = self.FirestoreService()
            service.create_student(
                {
                    "student_id": "N001",
                    "name": "山田太郎",
                    "company": "テスト株式会社",
                    "office": "本社",
                }
            )

            doc_data = mock_doc_ref.set.call_args[0][0]
            assert doc_data["company"] == "テスト株式会社"
            assert doc_data["office"] == "本社"
            assert "sync_source" not in doc_data

    def test_preserve_existing_status_true_keeps_existing_status(self):
        """
        preserve_existing_status=Trueで既存ドキュメントがあり、それがDashboard
        からの手動操作(auto_withdrawnフィールドなし)の場合、statusを上書きしない。
        """
        with patch("firestore_service.firestore.Client") as mock_client:
            mock_db = Mock()
            mock_client.return_value = mock_db
            mock_doc_ref = Mock()
            mock_db.collection.return_value.document.return_value = mock_doc_ref
            mock_snapshot = Mock()
            mock_snapshot.exists = True
            # auto_withdrawnフィールドが無い = Dashboardからの手動操作を模擬
            mock_snapshot.to_dict.return_value = {"status": "withdrawn"}
            mock_doc_ref.get.return_value = mock_snapshot

            service = self.FirestoreService()
            service.create_student(
                {"student_id": "N001", "name": "山田太郎"},
                preserve_existing_status=True,
                sync_source="attendance_roster",
            )

            doc_data = mock_doc_ref.set.call_args[0][0]
            assert "status" not in doc_data

    def test_preserve_existing_status_true_auto_recovers_auto_withdrawn_student(self):
        """
        reconcile(退会検出)が自動的にwithdrawn化した受講者(auto_withdrawn=True)
        が名簿に再登場した場合、Dashboardからの手動「辞退」操作とは区別し、
        自動的にactiveへ復帰させる。復帰時はauto_withdrawnフラグもFalseに
        戻す（pr-review-toolkit code-reviewer指摘対応: 自動withdrawn化に対する
        自動復帰経路が無いと、誤検出が永久に固定化されるバグがあった）。
        """
        with patch("firestore_service.firestore.Client") as mock_client:
            mock_db = Mock()
            mock_client.return_value = mock_db
            mock_doc_ref = Mock()
            mock_db.collection.return_value.document.return_value = mock_doc_ref
            mock_snapshot = Mock()
            mock_snapshot.exists = True
            mock_snapshot.to_dict.return_value = {
                "status": "withdrawn",
                "auto_withdrawn": True,
            }
            mock_doc_ref.get.return_value = mock_snapshot

            service = self.FirestoreService()
            service.create_student(
                {"student_id": "N001", "name": "山田太郎"},
                preserve_existing_status=True,
                sync_source="attendance_roster",
            )

            doc_data = mock_doc_ref.set.call_args[0][0]
            assert doc_data["status"] == "active"
            assert doc_data["auto_withdrawn"] is False

    def test_preserve_existing_status_true_new_student_gets_active(self):
        """preserve_existing_status=Trueで新規学生の場合、status="active"になる。"""
        with patch("firestore_service.firestore.Client") as mock_client:
            mock_db = Mock()
            mock_client.return_value = mock_db
            mock_doc_ref = Mock()
            mock_db.collection.return_value.document.return_value = mock_doc_ref
            mock_snapshot = Mock()
            mock_snapshot.exists = False
            mock_doc_ref.get.return_value = mock_snapshot

            service = self.FirestoreService()
            service.create_student(
                {"student_id": "N001", "name": "山田太郎"},
                preserve_existing_status=True,
                sync_source="attendance_roster",
            )

            doc_data = mock_doc_ref.set.call_args[0][0]
            assert doc_data["status"] == "active"


class TestGetStudentIdsByClassAndSource:
    """Test suite for get_student_ids_by_class_and_source()（退会検出reconcile用）。"""

    @pytest.fixture(autouse=True)
    def setup(self):
        import sys

        sys.path.insert(0, "src")
        from firestore_service import FirestoreService

        self.FirestoreService = FirestoreService

    def test_returns_student_id_to_status_mapping(self):
        with patch("firestore_service.firestore.Client") as mock_client:
            mock_db = Mock()
            mock_client.return_value = mock_db

            mock_doc1 = Mock()
            mock_doc1.id = "N001"
            mock_doc1.to_dict.return_value = {"status": "active"}
            mock_doc2 = Mock()
            mock_doc2.id = "N002"
            mock_doc2.to_dict.return_value = {"status": "withdrawn"}

            mock_query = Mock()
            mock_query.where.return_value = mock_query
            mock_query.stream.return_value = [mock_doc1, mock_doc2]
            mock_db.collection.return_value = mock_query

            service = self.FirestoreService()
            result = service.get_student_ids_by_class_and_source(
                "No1", "attendance_roster"
            )

            assert result == {"N001": "active", "N002": "withdrawn"}

    def test_propagates_exception_on_query_failure(self):
        """
        呼び出し側(main.py)がreconcileをスキップする判断材料にするため、
        fail-openにせず例外を送出する（class_name+sync_sourceの母集団が
        不明なまま「誰も退会していない」と誤判定させないため）。
        """
        with patch("firestore_service.firestore.Client") as mock_client:
            mock_db = Mock()
            mock_client.return_value = mock_db
            mock_query = Mock()
            mock_query.where.return_value = mock_query
            mock_query.stream.side_effect = Exception("Firestore unavailable")
            mock_db.collection.return_value = mock_query

            service = self.FirestoreService()
            with pytest.raises(Exception, match="Firestore unavailable"):
                service.get_student_ids_by_class_and_source("No1", "attendance_roster")


class TestMarkStudentWithdrawn:
    """Test suite for mark_student_withdrawn()。"""

    @pytest.fixture(autouse=True)
    def setup(self):
        import sys

        sys.path.insert(0, "src")
        from firestore_service import FirestoreService

        self.FirestoreService = FirestoreService

    def test_sets_status_withdrawn(self):
        with patch("firestore_service.firestore.Client") as mock_client:
            mock_db = Mock()
            mock_client.return_value = mock_db
            mock_doc_ref = Mock()
            mock_db.collection.return_value.document.return_value = mock_doc_ref

            service = self.FirestoreService()
            result = service.mark_student_withdrawn("N001")

            assert result is True
            call_args = mock_doc_ref.set.call_args
            assert call_args[0][0]["status"] == "withdrawn"
            # auto_withdrawn=Trueも併せて記録する。手動の「辞退」操作
            # (このフィールドを持たない)と区別し、名簿再登場時の自動復帰を
            # 可能にするため(create_student()のpreserve_existing_status参照)
            assert call_args[0][0]["auto_withdrawn"] is True
            assert call_args[1]["merge"] is True

    def test_returns_false_on_error(self):
        with patch("firestore_service.firestore.Client") as mock_client:
            mock_db = Mock()
            mock_client.return_value = mock_db
            mock_doc_ref = Mock()
            mock_doc_ref.set.side_effect = Exception("Firestore error")
            mock_db.collection.return_value.document.return_value = mock_doc_ref

            service = self.FirestoreService()
            result = service.mark_student_withdrawn("N001")

            assert result is False


# Placeholder test to ensure pytest can run
def test_placeholder():
    """Placeholder test."""
    assert True, "Test framework is working"
