"""
Integration tests for migration script.

These tests use Firestore Emulator to verify migration functionality.
"""

import sys
from datetime import datetime

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")


class TestMigrationIntegration:
    """Integration tests for migration script."""

    @pytest.fixture(autouse=True)
    def setup(self, emulator_client):
        """Set up test fixtures."""
        from firestore_service import FirestoreService

        self.db = emulator_client
        # Create FirestoreService and override its db with emulator client
        self.service = FirestoreService()
        self.service.db = emulator_client

    def test_migration_creates_parent_documents_with_correct_count(self):
        """
        Test that migration creates parent documents with correct file_count.

        Scenario:
        1. Setup test data: Create 20 file documents in subcollection (without parent)
        2. Run migration script
        3. Parent document should be created with file_count=20
        4. Validation should pass without errors
        5. All file documents should still exist
        """
        from migrate_parent_documents import migrate_parent_documents

        class_name = "令和7年度 デジタル中核人材養成研修 №01"
        task_id = "課題①"

        # Setup test data: Create 20 file documents without parent
        task_ref = self.db.collection(class_name).document(task_id)
        documents_ref = task_ref.collection("documents")

        for i in range(1, 21):
            documents_ref.add(
                {
                    "student_id": f"TEST{i:03d}",
                    "student_name": f"Test Student {i:03d}",
                    "filename": f"test_file{i}.pdf",
                    "drive_file_id": f"test_drive_id_{i:03d}",
                    "drive_folder_id": "test_folder_id",
                    "submit_date": f"2025-01-01 10:{i:02d}:00",
                    "composite_key": f"TEST{i:03d}_test_file{i}.pdf_2025-01-01_10-{i:02d}-00",
                    "uploaded_at": datetime.now(),
                }
            )

        # Verify parent doesn't exist yet
        parent_doc = task_ref.get()
        assert (
            not parent_doc.exists
        ), "Parent document should not exist before migration"

        # Run migration (execute mode) with emulator client
        result = migrate_parent_documents(dry_run=False, db=self.db)

        # Verify migration succeeded
        assert result["success"] is True, "Migration should succeed"
        assert result["created_documents"] >= 1, "At least one parent should be created"
        assert len(result["errors"]) == 0, "Migration should have no errors"

        # Verify parent document was created
        parent_doc = task_ref.get()
        assert parent_doc.exists, "Parent document should be created by migration"

        parent_data = parent_doc.to_dict()
        assert parent_data["task_id"] == task_id
        assert (
            parent_data["file_count"] == 20
        ), "file_count should be 20 for 20 existing files"
        assert "created_at" in parent_data
        assert "last_updated" in parent_data

        # Verify all file documents still exist
        file_docs = list(documents_ref.stream())
        assert len(file_docs) == 20, "All 20 file documents should still exist"

    def test_migration_skips_existing_parent_documents(self):
        """
        Test that migration skips parent documents that already exist.

        Scenario:
        1. Create parent document manually
        2. Create file documents in subcollection
        3. Run migration
        4. Parent document should not be overwritten
        5. Original file_count should be preserved
        """
        from migrate_parent_documents import migrate_parent_documents

        class_name = "令和7年度 デジタル中核人材養成研修 №02"
        task_id = "課題①"

        # Setup test data: Create parent document first
        task_ref = self.db.collection(class_name).document(task_id)
        task_ref.set(
            {
                "task_id": task_id,
                "task_pattern": task_id,
                "file_count": 999,  # Deliberately wrong count
                "created_at": datetime.now(),
                "last_updated": datetime.now(),
            }
        )

        # Create file documents
        documents_ref = task_ref.collection("documents")
        for i in range(1, 6):
            documents_ref.add(
                {
                    "student_id": f"TEST{i:03d}",
                    "student_name": f"Test Student {i:03d}",
                    "filename": f"test_file{i}.pdf",
                    "drive_file_id": f"test_drive_id_{i:03d}",
                    "drive_folder_id": "test_folder_id",
                    "submit_date": f"2025-01-01 10:{i:02d}:00",
                    "composite_key": f"TEST{i:03d}_test_file{i}.pdf_2025-01-01_10-{i:02d}-00",
                    "uploaded_at": datetime.now(),
                }
            )

        # Run migration with emulator client
        result = migrate_parent_documents(dry_run=False, db=self.db)

        # Verify migration succeeded but skipped this document
        assert result["success"] is True
        assert result["skipped_documents"] >= 1, "Existing parent should be skipped"

        # Verify parent document was not overwritten
        parent_doc = task_ref.get()
        parent_data = parent_doc.to_dict()
        assert (
            parent_data["file_count"] == 999
        ), "file_count should not be changed by migration"

    def test_migration_dry_run_mode(self):
        """
        Test that migration dry-run mode doesn't write to Firestore.

        Scenario:
        1. Create file documents without parent
        2. Run migration in dry-run mode
        3. Parent document should NOT be created
        4. Preview should show what would be created
        """
        from migrate_parent_documents import migrate_parent_documents

        class_name = "令和7年度 デジタル中核人材養成研修 №03"
        task_id = "課題①"

        # Setup test data: Create 10 file documents without parent
        task_ref = self.db.collection(class_name).document(task_id)
        documents_ref = task_ref.collection("documents")

        for i in range(1, 11):
            documents_ref.add(
                {
                    "student_id": f"TEST{i:03d}",
                    "student_name": f"Test Student {i:03d}",
                    "filename": f"test_file{i}.pdf",
                    "drive_file_id": f"test_drive_id_{i:03d}",
                    "drive_folder_id": "test_folder_id",
                    "submit_date": f"2025-01-01 10:{i:02d}:00",
                    "composite_key": f"TEST{i:03d}_test_file{i}.pdf_2025-01-01_10-{i:02d}-00",
                    "uploaded_at": datetime.now(),
                }
            )

        # Run migration in dry-run mode with emulator client
        result = migrate_parent_documents(dry_run=True, db=self.db)

        # Verify result indicates dry-run
        assert result["success"] is True
        assert result["dry_run"] is True
        assert "preview" in result
        assert result["created_documents"] >= 1, "Dry-run should count would-be creates"

        # Verify parent document was NOT actually created
        parent_doc = task_ref.get()
        assert (
            not parent_doc.exists
        ), "Parent document should NOT be created in dry-run mode"

        # Verify file documents still exist
        file_docs = list(documents_ref.stream())
        assert len(file_docs) == 10, "All file documents should still exist"


# Placeholder test to ensure pytest can run
def test_placeholder_migration_integration():
    """Placeholder test."""
    assert True, "Migration integration test framework is working"
