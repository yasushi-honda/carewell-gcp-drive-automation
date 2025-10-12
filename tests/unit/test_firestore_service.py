"""
Unit tests for FirestoreService class.

These tests use mocking to avoid actual Firestore operations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from google.cloud import firestore as firestore_module


class TestFirestoreService:
    """Test suite for FirestoreService class."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        # Import here to avoid circular imports
        import sys
        sys.path.insert(0, 'src')
        from firestore_service import FirestoreService

        self.FirestoreService = FirestoreService

    @patch('firestore_service.firestore.Client')
    def test_init(self, mock_client):
        """Test FirestoreService initialization."""
        service = self.FirestoreService()

        # Verify Firestore client was created with correct database
        mock_client.assert_called_once_with(database='carewell-native')
        assert service.db is not None

    def test_update_task_metadata_creates_new_document(self):
        """Test that _update_task_metadata creates a new parent document."""
        with patch('firestore_service.firestore.Client') as mock_client:
            # Setup
            mock_db = Mock()
            mock_client.return_value = mock_db
            mock_collection = Mock()
            mock_document = Mock()
            mock_db.collection.return_value = mock_collection
            mock_collection.document.return_value = mock_document

            service = self.FirestoreService()

            # Execute
            class_name = "テストクラス"
            task_id = "課題①"
            task_pattern = "課題①業務分析　※～11/3〆切"

            result = service._update_task_metadata(class_name, task_id, task_pattern)

            # Assert
            assert result is True
            mock_db.collection.assert_called_once_with(class_name)
            mock_collection.document.assert_called_once_with(task_id)

            # Verify set() was called with correct parameters
            mock_document.set.assert_called_once()
            call_args = mock_document.set.call_args

            # Check the data dictionary
            data = call_args[0][0]
            assert data['task_id'] == task_id
            assert data['task_pattern'] == task_pattern
            assert isinstance(data['file_count'], firestore_module.Increment)
            assert data['file_count']._value == 1
            assert data['last_updated'] == firestore_module.SERVER_TIMESTAMP

            # Check merge=True is specified
            assert call_args[1]['merge'] is True

    def test_update_task_metadata_increments_file_count(self):
        """Test that _update_task_metadata uses Increment(1) for file_count."""
        with patch('firestore_service.firestore.Client') as mock_client:
            # Setup
            mock_db = Mock()
            mock_client.return_value = mock_db
            mock_collection = Mock()
            mock_document = Mock()
            mock_db.collection.return_value = mock_collection
            mock_collection.document.return_value = mock_document

            service = self.FirestoreService()

            # Execute
            result = service._update_task_metadata("テストクラス", "課題①", "課題①パターン")

            # Assert
            assert result is True

            # Verify Increment(1) was used for file_count
            call_args = mock_document.set.call_args
            data = call_args[0][0]

            assert isinstance(data['file_count'], firestore_module.Increment)
            assert data['file_count']._value == 1
            assert data['last_updated'] == firestore_module.SERVER_TIMESTAMP

    def test_update_task_metadata_fails_gracefully(self):
        """Test fail-open behavior: returns False on error without raising exception."""
        with patch('firestore_service.firestore.Client') as mock_client:
            # Setup
            mock_db = Mock()
            mock_client.return_value = mock_db
            mock_collection = Mock()
            mock_document = Mock()
            mock_db.collection.return_value = mock_collection
            mock_collection.document.return_value = mock_document

            # Simulate Firestore error
            mock_document.set.side_effect = Exception("Firestore connection error")

            service = self.FirestoreService()

            # Execute
            result = service._update_task_metadata("テストクラス", "課題①", "課題①パターン")

            # Assert
            assert result is False
            # No exception should be raised (fail-open)

    def test_record_upload_updates_parent_and_adds_file(self):
        """Test that record_upload calls _update_task_metadata and creates file document."""
        with patch('firestore_service.firestore.Client') as mock_client:
            # Setup
            mock_db = Mock()
            mock_client.return_value = mock_db
            mock_collection = Mock()
            mock_task_doc = Mock()
            mock_file_doc = Mock()
            mock_db.collection.return_value = mock_collection

            # Mock document references for both parent and file
            def mock_document_side_effect(doc_id):
                if doc_id == "課題①":
                    return mock_task_doc
                else:
                    # File document path
                    mock_subcoll = Mock()
                    mock_task_doc.collection.return_value = mock_subcoll
                    mock_subcoll.document.return_value = mock_file_doc
                    return mock_task_doc

            mock_collection.document.side_effect = mock_document_side_effect

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
                task_pattern="課題①業務分析"
            )

            # Assert
            assert result is True
            # Verify parent document was updated
            mock_task_doc.set.assert_called()
            # Verify file document was created
            mock_file_doc.set.assert_called()

    def test_record_upload_with_default_task_pattern(self):
        """Test that if task_pattern is None, task_id is used as default."""
        with patch('firestore_service.firestore.Client') as mock_client:
            # Setup
            mock_db = Mock()
            mock_client.return_value = mock_db
            mock_collection = Mock()
            mock_task_doc = Mock()
            mock_file_doc = Mock()
            mock_db.collection.return_value = mock_collection

            def mock_document_side_effect(doc_id):
                if doc_id == "課題①":
                    return mock_task_doc
                else:
                    mock_subcoll = Mock()
                    mock_task_doc.collection.return_value = mock_subcoll
                    mock_subcoll.document.return_value = mock_file_doc
                    return mock_task_doc

            mock_collection.document.side_effect = mock_document_side_effect

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
                submit_date="2025-10-12 10:00:00"
            )

            # Assert
            assert result is True
            # Verify task_id was used as task_pattern
            call_args = mock_task_doc.set.call_args_list[0]
            data = call_args[0][0]
            assert data['task_pattern'] == "課題①"

    def test_record_upload_continues_on_parent_update_failure(self):
        """Test fail-open: file document is created even if parent update fails."""
        with patch('firestore_service.firestore.Client') as mock_client:
            # Setup
            mock_db = Mock()
            mock_client.return_value = mock_db
            mock_collection = Mock()
            mock_task_doc = Mock()
            mock_file_doc = Mock()
            mock_db.collection.return_value = mock_collection

            # Simulate parent document update failure
            mock_task_doc.set.side_effect = Exception("Firestore error")

            def mock_document_side_effect(doc_id):
                if doc_id == "課題①":
                    return mock_task_doc
                else:
                    mock_subcoll = Mock()
                    mock_task_doc.collection.return_value = mock_subcoll
                    mock_subcoll.document.return_value = mock_file_doc
                    return mock_task_doc

            mock_collection.document.side_effect = mock_document_side_effect

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
                task_pattern="課題①業務分析"
            )

            # Assert
            assert result is True  # Should still return True (fail-open)
            # File document should still be created
            mock_file_doc.set.assert_called()

    def test_check_already_uploaded_unchanged(self):
        """Test that check_already_uploaded logic is unchanged and doesn't touch parent documents."""
        with patch('firestore_service.firestore.Client') as mock_client:
            # Setup
            mock_db = Mock()
            mock_client.return_value = mock_db
            mock_collection = Mock()
            mock_task_doc = Mock()
            mock_subcoll = Mock()
            mock_file_doc = Mock()
            mock_file_snapshot = Mock()

            mock_db.collection.return_value = mock_collection
            mock_collection.document.return_value = mock_task_doc
            mock_task_doc.collection.return_value = mock_subcoll
            mock_subcoll.document.return_value = mock_file_doc
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
                submit_date="2025-10-12 10:00:00"
            )

            # Assert
            assert result is not None
            assert result["filename"] == "test.pdf"
            # Verify only subcollection was accessed, not parent document
            mock_task_doc.collection.assert_called_once_with('documents')
            # Parent document should not be updated
            mock_task_doc.set.assert_not_called()
            mock_task_doc.update.assert_not_called()


# Placeholder test to ensure pytest can run
def test_placeholder():
    """Placeholder test."""
    assert True, "Test framework is working"
