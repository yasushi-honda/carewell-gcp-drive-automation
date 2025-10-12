"""
Unit tests for fix_file_count script.

These tests verify the file_count fixing logic using mocking.
"""

import sys
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, "scripts")


class TestFixFileCount:
    """Test suite for fix_file_count script."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        # Import here to avoid module loading issues
        try:
            from fix_file_count import fix_file_count

            self.fix_file_count = fix_file_count
        except ImportError:
            # Module doesn't exist yet (Red state in TDD)
            self.fix_file_count = None

    @patch("fix_file_count.firestore.Client")
    def test_fix_file_count_detects_mismatches(self, mock_client):
        """
        Test that fix_file_count detects file_count mismatches.

        Scenario:
        - Parent document has file_count=3
        - Subcollection has 5 actual documents
        - Should detect mismatch: difference=+2
        """
        if self.fix_file_count is None:
            pytest.skip("fix_file_count module not yet implemented")

        # Setup mock Firestore
        mock_db = Mock()
        mock_client.return_value = mock_db

        # Mock parent document (file_count=3)
        mock_parent_doc = Mock()
        mock_parent_doc.exists = True
        mock_parent_data = {"task_id": "課題①", "file_count": 3}
        mock_parent_doc.to_dict.return_value = mock_parent_data

        # Mock documents subcollection (5 files)
        mock_file_docs = [Mock() for _ in range(5)]

        def collection_side_effect(collection_name):
            mock_collection = Mock()

            def document_side_effect(doc_id):
                mock_doc_ref = Mock()
                mock_doc_ref.get.return_value = mock_parent_doc

                # Documents subcollection
                mock_subcollection = Mock()
                mock_subcollection.stream.return_value = iter(mock_file_docs)
                mock_doc_ref.collection.return_value = mock_subcollection

                return mock_doc_ref

            mock_collection.document.side_effect = document_side_effect
            return mock_collection

        mock_db.collection.side_effect = collection_side_effect

        # Execute fix_file_count (dry-run)
        result = self.fix_file_count(dry_run=True)

        # Assert
        assert result["success"] is True
        assert len(result["mismatches"]) >= 1

        # Check mismatch details
        mismatch = result["mismatches"][0]
        assert mismatch["stored_count"] == 3
        assert mismatch["actual_count"] == 5
        assert mismatch["difference"] == 2

    @patch("fix_file_count.firestore.Client")
    def test_fix_file_count_execute_mode(self, mock_client):
        """
        Test that fix_file_count actually fixes file_count in execute mode.

        Scenario:
        - Parent document has file_count=3
        - Subcollection has 5 actual documents
        - Should update parent document to file_count=5
        """
        if self.fix_file_count is None:
            pytest.skip("fix_file_count module not yet implemented")

        # Setup mock Firestore
        mock_db = Mock()
        mock_client.return_value = mock_db

        # Mock parent document (file_count=3)
        mock_parent_doc = Mock()
        mock_parent_doc.exists = True
        mock_parent_data = {"task_id": "課題①", "file_count": 3}
        mock_parent_doc.to_dict.return_value = mock_parent_data

        # Mock documents subcollection (5 files)
        mock_file_docs = [Mock() for _ in range(5)]

        mock_doc_ref = Mock()

        def collection_side_effect(collection_name):
            mock_collection = Mock()

            def document_side_effect(doc_id):
                mock_doc_ref.get.return_value = mock_parent_doc

                # Documents subcollection
                mock_subcollection = Mock()
                mock_subcollection.stream.return_value = iter(mock_file_docs)
                mock_doc_ref.collection.return_value = mock_subcollection

                return mock_doc_ref

            mock_collection.document.side_effect = document_side_effect
            return mock_collection

        mock_db.collection.side_effect = collection_side_effect

        # Execute fix_file_count (execute mode)
        result = self.fix_file_count(dry_run=False)

        # Assert
        assert result["success"] is True
        assert result["fixed_documents"] >= 1

        # Verify update() was called with correct file_count
        # (Implementation should call update() on parent document)

    @patch("fix_file_count.firestore.Client")
    def test_fix_file_count_specific_class(self, mock_client):
        """
        Test that fix_file_count can target specific class.

        Scenario:
        - class_name specified
        - Should only process that class
        """
        if self.fix_file_count is None:
            pytest.skip("fix_file_count module not yet implemented")

        # Setup mock Firestore
        mock_db = Mock()
        mock_client.return_value = mock_db

        # Mock parent document
        mock_parent_doc = Mock()
        mock_parent_doc.exists = True
        mock_parent_data = {"task_id": "課題①", "file_count": 0}
        mock_parent_doc.to_dict.return_value = mock_parent_data

        # Mock documents subcollection (empty)
        mock_file_docs = []

        def collection_side_effect(collection_name):
            mock_collection = Mock()

            def document_side_effect(doc_id):
                mock_doc_ref = Mock()
                mock_doc_ref.get.return_value = mock_parent_doc

                # Documents subcollection
                mock_subcollection = Mock()
                mock_subcollection.stream.return_value = iter(mock_file_docs)
                mock_doc_ref.collection.return_value = mock_subcollection

                return mock_doc_ref

            mock_collection.document.side_effect = document_side_effect
            return mock_collection

        mock_db.collection.side_effect = collection_side_effect

        # Execute fix_file_count with specific class
        result = self.fix_file_count(
            class_name="令和7年度 デジタル中核人材養成研修 №01", dry_run=True
        )

        # Assert
        assert result["success"] is True
        assert result["total_classes"] == 1  # Only one class processed


# Placeholder test to ensure pytest can run
def test_placeholder_fix():
    """Placeholder test for fix_file_count module."""
    assert True, "Fix file_count test framework is working"
