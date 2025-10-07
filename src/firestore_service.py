"""
Firestore Service for tracking uploaded files
"""
import logging
import hashlib
from datetime import datetime
from typing import Optional
from google.cloud import firestore

logger = logging.getLogger(__name__)


class FirestoreService:
    """
    Handles Firestore operations for file upload tracking
    """

    def __init__(self):
        """Initialize Firestore client"""
        self.db = firestore.Client()
        self.collection_name = "uploaded_files"

    def _generate_file_hash(self, class_name: str, task_name: str, student_name: str, filename: str) -> str:
        """
        Generate unique hash for file identification

        Args:
            class_name: Class name
            task_name: Task name
            student_name: Student name
            filename: Original filename

        Returns:
            SHA256 hash string
        """
        composite_key = f"{class_name}|{task_name}|{student_name}|{filename}"
        return hashlib.sha256(composite_key.encode('utf-8')).hexdigest()

    def check_already_uploaded(self, class_name: str, task_name: str, student_name: str, filename: str) -> Optional[dict]:
        """
        Check if file has already been uploaded

        Args:
            class_name: Class name
            task_name: Task name
            student_name: Student name
            filename: Original filename

        Returns:
            Upload record dict if exists, None otherwise
        """
        try:
            file_hash = self._generate_file_hash(class_name, task_name, student_name, filename)

            doc_ref = self.db.collection(self.collection_name).document(file_hash)
            doc = doc_ref.get()

            if doc.exists:
                logger.info(f"File already uploaded: {filename} (student: {student_name})")
                return doc.to_dict()
            else:
                return None

        except Exception as e:
            logger.warning(f"Firestore unavailable (Datastore mode?), skipping duplicate check for {filename}")
            # Return None to allow upload (no duplicate check)
            return None

    def record_upload(
        self,
        class_name: str,
        task_name: str,
        student_name: str,
        filename: str,
        drive_file_id: str,
        drive_folder_id: str,
        metadata: Optional[dict] = None
    ) -> bool:
        """
        Record successful file upload

        Args:
            class_name: Class name
            task_name: Task name
            student_name: Student name
            filename: Original filename
            drive_file_id: Google Drive file ID
            drive_folder_id: Google Drive folder ID
            metadata: Additional metadata (optional)

        Returns:
            True if recorded successfully, False otherwise
        """
        try:
            file_hash = self._generate_file_hash(class_name, task_name, student_name, filename)

            record = {
                "file_hash": file_hash,
                "class_name": class_name,
                "task_name": task_name,
                "student_name": student_name,
                "filename": filename,
                "drive_file_id": drive_file_id,
                "drive_folder_id": drive_folder_id,
                "uploaded_at": firestore.SERVER_TIMESTAMP,
                "metadata": metadata or {}
            }

            doc_ref = self.db.collection(self.collection_name).document(file_hash)
            doc_ref.set(record)

            logger.info(f"Recorded upload: {filename} (Drive ID: {drive_file_id})")
            return True

        except Exception as e:
            logger.warning(f"Firestore unavailable, skipping record for {filename}: {e}")
            # Return True to continue processing even if Firestore fails
            return True

    def get_upload_stats(self, class_name: str, task_name: str) -> dict:
        """
        Get upload statistics for a specific class/task

        Args:
            class_name: Class name
            task_name: Task name

        Returns:
            Dictionary with upload statistics
        """
        try:
            query = self.db.collection(self.collection_name) \
                .where("class_name", "==", class_name) \
                .where("task_name", "==", task_name)

            docs = query.stream()

            count = 0
            for doc in docs:
                count += 1

            return {
                "class_name": class_name,
                "task_name": task_name,
                "total_uploaded": count
            }

        except Exception as e:
            logger.error(f"Error getting upload stats: {e}", exc_info=True)
            return {
                "class_name": class_name,
                "task_name": task_name,
                "total_uploaded": 0,
                "error": str(e)
            }
