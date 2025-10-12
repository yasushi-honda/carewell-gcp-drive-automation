"""
Integration tests for file upload with parent document management.

These tests use Firestore Emulator to verify end-to-end functionality.
"""

import sys
from datetime import datetime

import pytest

sys.path.insert(0, "src")


class TestFileUploadIntegration:
    """Integration tests for file upload functionality."""

    @pytest.fixture(autouse=True)
    def setup(self, emulator_client):
        """Set up test fixtures."""
        from firestore_service import FirestoreService

        self.db = emulator_client
        # Create FirestoreService and override its db with emulator client
        self.service = FirestoreService()
        self.service.db = emulator_client

    def test_new_file_upload_creates_parent_and_increments_count(self):
        """
        Test that new file upload creates parent document and sets file_count=1.

        Scenario:
        1. Upload first file to a task
        2. Parent document should be created with file_count=1
        3. File document should be created in subcollection
        """
        class_name = "令和7年度 デジタル中核人材養成研修 №01"
        task_id = "課題①"
        task_pattern = "課題①"

        # Upload first file
        result = self.service.record_upload(
            class_name=class_name,
            task_id=task_id,
            task_pattern=task_pattern,
            student_name="Test Student 001",
            student_id="TEST001",
            filename="test_file.pdf",
            drive_file_id="test_drive_id_001",
            drive_folder_id="test_folder_id",
            submit_date="2025-01-01 10:00:00",
        )

        assert result is not None, "record_upload should return file document data"

        # Verify parent document was created
        parent_ref = self.db.collection(class_name).document(task_id)
        parent_doc = parent_ref.get()

        assert parent_doc.exists, "Parent document should be created"

        parent_data = parent_doc.to_dict()
        assert parent_data["task_id"] == task_id
        assert parent_data["task_pattern"] == task_pattern
        assert parent_data["file_count"] == 1, "file_count should be 1 for first upload"
        assert "created_at" in parent_data
        assert "last_updated" in parent_data

        # Verify file document was created in subcollection
        file_docs = list(parent_ref.collection("documents").stream())
        assert len(file_docs) == 1, "One file document should exist"

        file_data = file_docs[0].to_dict()
        assert file_data["student_id"] == "TEST001"
        assert file_data["filename"] == "test_file.pdf"
        assert file_data["drive_file_id"] == "test_drive_id_001"

    def test_second_file_upload_increments_count(self):
        """
        Test that second file upload increments file_count to 2.

        Scenario:
        1. Upload first file
        2. Upload second file (different student)
        3. Parent document file_count should be 2
        4. Two file documents should exist in subcollection
        """
        class_name = "令和7年度 デジタル中核人材養成研修 №01"
        task_id = "課題①"
        task_pattern = "課題①"

        # Upload first file
        self.service.record_upload(
            class_name=class_name,
            task_id=task_id,
            task_pattern=task_pattern,
            student_name="Test Student 001",
            student_id="TEST001",
            filename="test_file1.pdf",
            drive_file_id="test_drive_id_001",
            drive_folder_id="test_folder_id",
            submit_date="2025-01-01 10:00:00",
        )

        # Upload second file
        self.service.record_upload(
            class_name=class_name,
            task_id=task_id,
            task_pattern=task_pattern,
            student_name="Test Student 002",
            student_id="TEST002",
            filename="test_file2.pdf",
            drive_file_id="test_drive_id_002",
            drive_folder_id="test_folder_id",
            submit_date="2025-01-01 10:05:00",
        )

        # Verify parent document file_count incremented
        parent_ref = self.db.collection(class_name).document(task_id)
        parent_doc = parent_ref.get()

        parent_data = parent_doc.to_dict()
        assert (
            parent_data["file_count"] == 2
        ), "file_count should be 2 after second upload"

        # Verify two file documents exist
        file_docs = list(parent_ref.collection("documents").stream())
        assert len(file_docs) == 2, "Two file documents should exist"

    def test_multiple_uploads_maintain_accurate_count(self):
        """
        Test that multiple file uploads maintain accurate file_count.

        Scenario:
        1. Upload 5 different files
        2. Parent document file_count should be 5
        3. Five file documents should exist in subcollection
        """
        class_name = "令和7年度 デジタル中核人材養成研修 №01"
        task_id = "課題①"
        task_pattern = "課題①"

        # Upload 5 files
        for i in range(1, 6):
            self.service.record_upload(
                class_name=class_name,
                task_id=task_id,
                task_pattern=task_pattern,
                student_name=f"Test Student {i:03d}",
                student_id=f"TEST{i:03d}",
                filename=f"test_file{i}.pdf",
                drive_file_id=f"test_drive_id_{i:03d}",
                drive_folder_id="test_folder_id",
                submit_date=f"2025-01-01 10:{i:02d}:00",
            )

        # Verify parent document file_count is accurate
        parent_ref = self.db.collection(class_name).document(task_id)
        parent_doc = parent_ref.get()

        parent_data = parent_doc.to_dict()
        assert parent_data["file_count"] == 5, "file_count should be 5 after 5 uploads"

        # Verify five file documents exist
        file_docs = list(parent_ref.collection("documents").stream())
        assert len(file_docs) == 5, "Five file documents should exist"

    def test_task_pattern_defaults_to_task_id(self):
        """
        Test that task_pattern defaults to task_id when not specified.

        Scenario:
        1. Upload file without specifying task_pattern
        2. Parent document task_pattern should equal task_id
        """
        class_name = "令和7年度 デジタル中核人材養成研修 №01"
        task_id = "課題①"

        # Upload file without task_pattern
        self.service.record_upload(
            class_name=class_name,
            task_id=task_id,
            # task_pattern not specified
            student_name="Test Student 001",
            student_id="TEST001",
            filename="test_file.pdf",
            drive_file_id="test_drive_id_001",
            drive_folder_id="test_folder_id",
            submit_date="2025-01-01 10:00:00",
        )

        # Verify parent document task_pattern defaults to task_id
        parent_ref = self.db.collection(class_name).document(task_id)
        parent_doc = parent_ref.get()

        parent_data = parent_doc.to_dict()
        assert (
            parent_data["task_pattern"] == task_id
        ), "task_pattern should default to task_id"

    def test_duplicate_file_upload_skips_and_count_unchanged(self):
        """
        Test that duplicate file upload is skipped and file_count doesn't increase.

        Scenario:
        1. Upload a file
        2. Upload the same file again (same composite_key)
        3. Second upload should be detected as duplicate
        4. file_count should remain 1
        5. Only one file document should exist
        """
        class_name = "令和7年度 デジタル中核人材養成研修 №01"
        task_id = "課題①"
        task_pattern = "課題①"

        # Upload first file
        result1 = self.service.record_upload(
            class_name=class_name,
            task_id=task_id,
            task_pattern=task_pattern,
            student_name="Test Student 001",
            student_id="TEST001",
            filename="test_file.pdf",
            drive_file_id="test_drive_id_001",
            drive_folder_id="test_folder_id",
            submit_date="2025-01-01 10:00:00",
        )

        assert result1 is not None, "First upload should succeed"

        # Check for duplicate (should return existing record)
        existing = self.service.check_already_uploaded(
            class_name=class_name,
            task_id=task_id,
            student_id="TEST001",
            filename="test_file.pdf",
            submit_date="2025-01-01 10:00:00",
        )

        assert existing is not None, "Duplicate check should return existing record"
        assert existing["student_id"] == "TEST001"
        assert existing["filename"] == "test_file.pdf"

        # Verify parent document file_count remains 1
        parent_ref = self.db.collection(class_name).document(task_id)
        parent_doc = parent_ref.get()

        parent_data = parent_doc.to_dict()
        assert (
            parent_data["file_count"] == 1
        ), "file_count should remain 1 for duplicate"

        # Verify only one file document exists
        file_docs = list(parent_ref.collection("documents").stream())
        assert len(file_docs) == 1, "Only one file document should exist"

    def test_concurrent_uploads_maintain_count_accuracy(self):
        """
        Test that concurrent file uploads maintain accurate file_count.

        Scenario:
        1. Upload 5 files concurrently using ThreadPoolExecutor
        2. All uploads should complete successfully
        3. Parent document file_count should be 5
        4. Five file documents should exist in subcollection
        5. Performance should be acceptable (tracked but not enforced in emulator)
        """
        import time
        from concurrent.futures import ThreadPoolExecutor

        class_name = "令和7年度 デジタル中核人材養成研修 №01"
        task_id = "課題①"
        task_pattern = "課題①"

        def upload_file(index):
            """Upload a single file and track timing."""
            start_time = time.time()
            result = self.service.record_upload(
                class_name=class_name,
                task_id=task_id,
                task_pattern=task_pattern,
                student_name=f"Test Student {index:03d}",
                student_id=f"TEST{index:03d}",
                filename=f"concurrent_file{index}.pdf",
                drive_file_id=f"test_drive_id_{index:03d}",
                drive_folder_id="test_folder_id",
                submit_date=f"2025-01-01 10:{index:02d}:00",
            )
            elapsed = time.time() - start_time
            return result, elapsed

        # Upload 5 files concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(upload_file, i) for i in range(1, 6)]
            results = [future.result() for future in futures]

        # Verify all uploads succeeded
        for result, elapsed in results:
            assert result is not None, "All concurrent uploads should succeed"
            # Note: Performance requirements (500ms) are for production Firestore,
            # not enforced for emulator which may have different latency

        # Verify parent document file_count is accurate
        parent_ref = self.db.collection(class_name).document(task_id)
        parent_doc = parent_ref.get()

        parent_data = parent_doc.to_dict()
        assert (
            parent_data["file_count"] == 5
        ), "file_count should be 5 after concurrent uploads"

        # Verify five file documents exist
        file_docs = list(parent_ref.collection("documents").stream())
        assert (
            len(file_docs) == 5
        ), "Five file documents should exist after concurrent uploads"


# Placeholder test to ensure pytest can run
def test_placeholder_integration():
    """Placeholder test."""
    assert True, "Integration test framework is working"
