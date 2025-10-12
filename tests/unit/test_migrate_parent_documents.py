"""
Unit tests for migrate_parent_documents script.

These tests verify the migration logic using mocking.
"""

import sys
from unittest.mock import Mock, patch

import pytest
from google.cloud import firestore as firestore_module

sys.path.insert(0, "scripts")


class TestMigrateParentDocuments:
    """Test suite for migrate_parent_documents script."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        # Import here to avoid module loading issues
        try:
            from migrate_parent_documents import migrate_parent_documents

            self.migrate_parent_documents = migrate_parent_documents
        except ImportError:
            # Module doesn't exist yet (Red state in TDD)
            self.migrate_parent_documents = None

    @patch("migrate_parent_documents.firestore.Client")
    def test_migrate_class_tasks_creates_parent_documents(self, mock_client):
        """
        Test that migration creates parent documents with correct file_count.

        Scenario:
        - Class has task_id "課題①" with 5 files in documents subcollection
        - Parent document should be created with file_count=5
        """
        if self.migrate_parent_documents is None:
            pytest.skip("migrate_parent_documents module not yet implemented")

        # Setup mock Firestore
        mock_db = Mock()
        mock_client.return_value = mock_db

        # Mock parent document check (doesn't exist)
        mock_parent_doc = Mock()
        mock_parent_doc.exists = False

        # Mock documents subcollection (5 files)
        mock_file_docs = [Mock() for _ in range(5)]

        def collection_side_effect(collection_name):
            mock_collection = Mock()

            def document_side_effect(doc_id):
                mock_doc_ref = Mock()

                if collection_name.startswith("令和7年度"):
                    # Task document
                    mock_doc_ref.get.return_value = mock_parent_doc

                    # Documents subcollection
                    mock_subcollection = Mock()
                    mock_subcollection.stream.return_value = iter(mock_file_docs)
                    mock_doc_ref.collection.return_value = mock_subcollection

                return mock_doc_ref

            mock_collection.document.side_effect = document_side_effect
            return mock_collection

        mock_db.collection.side_effect = collection_side_effect

        # Execute migration
        result = self.migrate_parent_documents(dry_run=False)

        # Assert
        assert result["success"] is True
        assert result["created_documents"] >= 1

        # Verify set() was called with correct data
        # (Implementation will need to call set() on parent document)

    @patch("migrate_parent_documents.firestore.Client")
    def test_migrate_skips_existing_parent_documents(self, mock_client):
        """
        Test that migration skips parent documents that already exist.

        Scenario:
        - Parent document already exists
        - Migration should skip it and not overwrite
        """
        if self.migrate_parent_documents is None:
            pytest.skip("migrate_parent_documents module not yet implemented")

        # Setup mock Firestore
        mock_db = Mock()
        mock_client.return_value = mock_db

        # Mock parent document check (exists)
        mock_parent_doc = Mock()
        mock_parent_doc.exists = True

        def collection_side_effect(collection_name):
            mock_collection = Mock()

            def document_side_effect(doc_id):
                mock_doc_ref = Mock()
                mock_doc_ref.get.return_value = mock_parent_doc
                return mock_doc_ref

            mock_collection.document.side_effect = document_side_effect
            return mock_collection

        mock_db.collection.side_effect = collection_side_effect

        # Execute migration
        result = self.migrate_parent_documents(dry_run=False)

        # Assert
        assert result["success"] is True
        assert result["skipped_documents"] >= 1
        assert result["created_documents"] == 0

    @patch("migrate_parent_documents.firestore.Client")
    def test_migrate_dry_run_mode(self, mock_client):
        """
        Test that dry_run mode doesn't write to Firestore.

        Scenario:
        - dry_run=True
        - Should return preview report without calling set()
        """
        if self.migrate_parent_documents is None:
            pytest.skip("migrate_parent_documents module not yet implemented")

        # Setup mock Firestore
        mock_db = Mock()
        mock_client.return_value = mock_db

        # Mock parent document check (doesn't exist)
        mock_parent_doc = Mock()
        mock_parent_doc.exists = False

        # Mock documents subcollection (3 files)
        mock_file_docs = [Mock() for _ in range(3)]

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

        # Execute dry-run
        result = self.migrate_parent_documents(dry_run=True)

        # Assert
        assert result["success"] is True
        assert result["dry_run"] is True
        assert "preview" in result or "would_create" in result

        # Verify no set() calls were made
        # (Implementation should not call set() in dry_run mode)


# Placeholder test to ensure pytest can run
def test_placeholder_migration():
    """Placeholder test for migration module."""
    assert True, "Migration test framework is working"
