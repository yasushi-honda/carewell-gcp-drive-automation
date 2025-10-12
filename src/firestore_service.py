"""
Firestore Service for tracking uploaded files
"""

import logging
from typing import Optional

from google.cloud import firestore

logger = logging.getLogger(__name__)


class FirestoreService:
    """
    Handles Firestore operations for file upload tracking
    """

    def __init__(self):
        """Initialize Firestore client with Native Mode database"""
        self.db = firestore.Client(database="carewell-native")
        self.collection_name = "uploaded_files"

    def _generate_composite_key(
        self, student_id: str, filename: str, submit_date: str
    ) -> str:
        """
        Generate composite key for file identification

        Args:
            student_id: Student ID (e.g., N9902913)
            filename: Original filename
            submit_date: Submission date/time

        Returns:
            Composite key string in format: {student_id}_{filename}_{submit_date}
        """
        # Sanitize submit_date to remove special characters
        safe_submit_date = (
            submit_date.replace(" ", "_").replace(":", "-").replace("/", "-")
        )
        composite_key = f"{student_id}_{filename}_{safe_submit_date}"
        return composite_key

    def _update_task_metadata(
        self, class_name: str, task_id: str, task_pattern: str
    ) -> bool:
        """
        Update or create task parent document with metadata.

        This method atomically increments the file_count using Firestore's
        Increment operation to ensure accuracy during concurrent uploads.

        Args:
            class_name: Class name
            task_id: Task ID (e.g., "課題①")
            task_pattern: Task pattern/title for display

        Returns:
            True if successful, False if error occurred (fail-open strategy)

        Note:
            Uses merge=True to create document if it doesn't exist, or update
            only the specified fields if it does exist.
            created_at is only set on first creation.
        """
        try:
            task_ref = self.db.collection(class_name).document(task_id)

            # Check if document exists to determine if created_at should be set
            doc = task_ref.get()

            # Prepare update data with atomic increment
            update_data = {
                "task_id": task_id,
                "task_pattern": task_pattern,
                "file_count": firestore.Increment(1),
                "last_updated": firestore.SERVER_TIMESTAMP,
            }

            # Add created_at only for new documents
            if not doc.exists:
                update_data["created_at"] = firestore.SERVER_TIMESTAMP

            # Use merge=True to create or update
            # If document doesn't exist, all fields will be set
            # If document exists, only specified fields will be updated
            task_ref.set(update_data, merge=True)

            logger.info(f"Updated task document: {class_name}/{task_id}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to update task document {class_name}/{task_id}: {e}",
                exc_info=True,
            )
            # Continue processing (fail-open strategy for high availability)
            return False

    def check_already_uploaded(
        self,
        class_name: str,
        task_id: str,
        student_id: str,
        filename: str,
        submit_date: str,
    ) -> Optional[dict]:
        """
        Check if file has already been uploaded

        Args:
            class_name: Class name
            task_id: Task ID (e.g., "課題①")
            student_id: Student ID (e.g., N9902913)
            filename: Original filename
            submit_date: Submission date/time

        Returns:
            Upload record dict if exists, None otherwise
        """
        try:
            composite_key = self._generate_composite_key(
                student_id, filename, submit_date
            )

            # Collection path: {class_name}/{task_id}/documents
            doc_ref = (
                self.db.collection(class_name)
                .document(task_id)
                .collection("documents")
                .document(composite_key)
            )
            doc = doc_ref.get()

            if doc.exists:
                logger.info(
                    f"File already uploaded: {filename} (student ID: {student_id}, submit_date: {submit_date})"
                )
                return doc.to_dict()
            else:
                return None

        except Exception as e:
            logger.error(f"Error checking duplicate for {filename}: {e}", exc_info=True)
            # Return None to allow upload on error (fail-open for availability)
            return None

    def record_upload(
        self,
        class_name: str,
        task_id: str,
        student_name: str,
        student_id: str,
        filename: str,
        drive_file_id: str,
        drive_folder_id: str,
        submit_date: str,
        metadata: Optional[dict] = None,
        task_pattern: Optional[str] = None,
    ) -> bool:
        """
        Record successful file upload and update parent document metadata.

        Args:
            class_name: Class name
            task_id: Task ID (e.g., "課題①")
            student_name: Student name (without ID)
            student_id: Student ID (e.g., N9902913)
            filename: Original filename
            drive_file_id: Google Drive file ID
            drive_folder_id: Google Drive folder ID
            submit_date: Submission date/time
            metadata: Additional metadata (optional)
            task_pattern: Task pattern/title (optional, defaults to task_id)

        Returns:
            True if recorded successfully, False otherwise

        Note:
            Uses fail-open strategy: even if parent document update fails,
            file document will still be created to ensure high availability.
        """
        try:
            # Default task_pattern to task_id if not provided
            task_pattern = task_pattern or task_id

            # Update parent document metadata (fail-open: continue even if this fails)
            self._update_task_metadata(class_name, task_id, task_pattern)

            # Create file document record
            composite_key = self._generate_composite_key(
                student_id, filename, submit_date
            )

            record = {
                "composite_key": composite_key,
                "task_id": task_id,
                "student_name": student_name,
                "student_id": student_id,
                "filename": filename,
                "drive_file_id": drive_file_id,
                "drive_folder_id": drive_folder_id,
                "submit_date": submit_date,
                "uploaded_at": firestore.SERVER_TIMESTAMP,
                "metadata": metadata or {},
            }

            # Collection path: {class_name}/{task_id}/documents
            doc_ref = (
                self.db.collection(class_name)
                .document(task_id)
                .collection("documents")
                .document(composite_key)
            )
            doc_ref.set(record)

            logger.info(
                f"Recorded upload: {filename} (Student ID: {student_id}, Drive ID: {drive_file_id})"
            )
            return True

        except Exception as e:
            logger.error(f"Error recording upload for {filename}: {e}", exc_info=True)
            # Return True to continue processing even if Firestore fails (fail-open)
            return True

    def get_upload_stats(self, class_name: str, task_id: str) -> dict:
        """
        Get upload statistics for a specific class/task

        NOTE: Currently unused but preserved for future monitoring/operations API

        Args:
            class_name: Class name
            task_id: Task ID (e.g., "課題①")

        Returns:
            Dictionary with upload statistics
        """
        try:
            # Collection path: {class_name}/{task_id}/documents
            docs = (
                self.db.collection(class_name)
                .document(task_id)
                .collection("documents")
                .stream()
            )

            count = 0
            for doc in docs:
                count += 1

            return {
                "class_name": class_name,
                "task_id": task_id,
                "total_uploaded": count,
            }

        except Exception as e:
            logger.error(f"Error getting upload stats: {e}", exc_info=True)
            return {
                "class_name": class_name,
                "task_id": task_id,
                "total_uploaded": 0,
                "error": str(e),
            }
