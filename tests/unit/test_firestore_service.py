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

    @patch("firestore_service.firestore.Client")
    def test_init(self, mock_client):
        """Test FirestoreService initialization."""
        service = self.FirestoreService()

        # Verify Firestore client was created with correct database
        mock_client.assert_called_once_with(database="carewell-native")
        assert service.db is not None

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


# Placeholder test to ensure pytest can run
def test_placeholder():
    """Placeholder test."""
    assert True, "Test framework is working"
