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
            task_ref = (
                self.db.collection("submissions")
                .document(class_name)
                .collection("tasks")
                .document(task_id)
            )

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

    def check_already_uploaded_by_student_date(
        self,
        class_name: str,
        task_id: str,
        student_id: str,
        submit_date: str,
    ) -> Optional[dict]:
        """
        Check if student has already uploaded a file on the given date
        (early duplicate check without filename)

        Args:
            class_name: Class name
            task_id: Task ID (e.g., "課題①")
            student_id: Student ID (e.g., N9902913)
            submit_date: Submission date/time

        Returns:
            Upload record dict if exists, None otherwise
        """
        try:
            # Collection path: submissions/{class_name}/tasks/{task_id}/files
            collection_ref = (
                self.db.collection("submissions")
                .document(class_name)
                .collection("tasks")
                .document(task_id)
                .collection("files")
            )

            # Query by student_id and submit_date fields
            docs = (
                collection_ref.where("student_id", "==", student_id)
                .where("submit_date", "==", submit_date)
                .limit(1)
                .stream()
            )

            for doc in docs:
                logger.info(
                    f"File already uploaded (early check): student_id={student_id}, submit_date={submit_date}"
                )
                return doc.to_dict()

            return None

        except Exception as e:
            logger.error(
                f"Error in early duplicate check for student_id={student_id}, submit_date={submit_date}: {e}",
                exc_info=True,
            )
            # Return None to allow processing on error (fail-open for availability)
            return None

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

            # Collection path: submissions/{class_name}/tasks/{task_id}/files
            doc_ref = (
                self.db.collection("submissions")
                .document(class_name)
                .collection("tasks")
                .document(task_id)
                .collection("files")
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

    def update_file_metadata(
        self,
        class_name: str,
        task_id: str,
        composite_key: str,
        metadata: dict,
    ) -> bool:
        """
        Update metadata field of an existing file document (for backfilling grading info).

        Args:
            class_name: Class name
            task_id: Task ID (e.g., "課題①")
            composite_key: Existing document's composite key
            metadata: Updated metadata dict (grading information)

        Returns:
            True if successful, False if error occurred (fail-open strategy)

        Note:
            Only updates the metadata field. All other fields remain unchanged.
            Existing metadata is overwritten with new values (latest grading info).
        """
        try:
            # Collection path: submissions/{class_name}/tasks/{task_id}/files/{composite_key}
            doc_ref = (
                self.db.collection("submissions")
                .document(class_name)
                .collection("tasks")
                .document(task_id)
                .collection("files")
                .document(composite_key)
            )

            # Update metadata field only (overwrites existing metadata)
            doc_ref.update({"metadata": metadata})

            logger.info(
                f"Backfilled metadata for existing file: {composite_key}, metadata: {metadata}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to update metadata for {composite_key}: {e}", exc_info=True
            )
            # fail-open: continue processing even if metadata update fails
            return False

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
        # Denormalized student fields (新規追加)
        student_furigana: str = "",
        student_group: str = "未分類",
        student_status: str = "active",
        student_company: str = "",
        student_office: str = "",
        student_service_type: str = "",
        student_serial_number: int = 0,
        student_number: str = "",
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
            student_furigana: Student name in furigana (denormalized)
            student_group: Student group (denormalized)
            student_status: Student status (denormalized)
            student_company: Student company (denormalized)
            student_office: Student office (denormalized)
            student_service_type: Student service type (denormalized)
            student_serial_number: Student serial number (denormalized)
            student_number: Student number/受講生番号 (denormalized)

        Returns:
            True if recorded successfully, False otherwise

        Note:
            Uses fail-open strategy: even if parent document update fails,
            file document will still be created to ensure high availability.

            Denormalized student fields are embedded in the file document for
            optimized querying and to avoid 301 queries (1 query per file).
            These fields default to empty/default values if not provided.
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
                # Denormalized student fields (新規追加)
                "student_furigana": student_furigana,
                "student_group": student_group,
                "student_status": student_status,
                "student_company": student_company,
                "student_office": student_office,
                "student_service_type": student_service_type,
                "student_serial_number": student_serial_number,
                "student_number": student_number,
            }

            # Collection path: submissions/{class_name}/tasks/{task_id}/files
            doc_ref = (
                self.db.collection("submissions")
                .document(class_name)
                .collection("tasks")
                .document(task_id)
                .collection("files")
                .document(composite_key)
            )
            doc_ref.set(record)

            logger.info(
                f"Recorded upload: {filename} (Student ID: {student_id}, Group: {student_group}, Drive ID: {drive_file_id})"
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

    # Student Master Data Management Methods

    def student_exists(self, student_id: str) -> bool:
        """
        Check if student exists in students collection

        Args:
            student_id: Student ID (日介番号)

        Returns:
            True if student exists, False otherwise
        """
        try:
            doc_ref = self.db.collection("students").document(student_id)
            doc = doc_ref.get()
            return doc.exists

        except Exception as e:
            logger.error(
                f"Error checking student existence for {student_id}: {e}",
                exc_info=True,
            )
            # Return False on error (fail-open strategy)
            return False

    def create_student(self, student_data: dict) -> bool:
        """
        Create or update student document in students collection

        Args:
            student_data: Dictionary containing student information with keys:
                - student_id (required): 日介番号
                - furigana: ふりがな
                - name: 氏名
                - group: グループ
                - status: ステータス
                - company: 勤務先
                - office: 事業所
                - service_type: サービス種別
                - serial_number: Serial No.
                - student_number: 受講生番号
                - class_name: クラス

        Returns:
            True if successful, False otherwise (fail-open strategy)
        """
        try:
            student_id = student_data.get("student_id")
            if not student_id:
                logger.error("student_id is required but not provided")
                return False

            # Prepare student document
            doc_data = {
                "student_id": student_id,
                "furigana": student_data.get("furigana", ""),
                "name": student_data.get("name", ""),
                "group": student_data.get("group", "未分類"),
                "status": student_data.get("status", "active"),
                "company": student_data.get("company", ""),
                "office": student_data.get("office", ""),
                "service_type": student_data.get("service_type", ""),
                "serial_number": student_data.get("serial_number", 0),
                "student_number": student_data.get("student_number", ""),
                "class_name": student_data.get("class_name", ""),
                "created_at": firestore.SERVER_TIMESTAMP,
                "last_updated": firestore.SERVER_TIMESTAMP,
            }

            doc_ref = self.db.collection("students").document(student_id)
            doc_ref.set(doc_data, merge=True)

            logger.info(f"Created/updated student: {student_id} - {student_data.get('name', '')}")
            return True

        except Exception as e:
            logger.error(
                f"Error creating student {student_data.get('student_id', 'unknown')}: {e}",
                exc_info=True,
            )
            # Return False on error (fail-open strategy)
            return False

    def get_student(self, student_id: str) -> Optional[dict]:
        """
        Get student data from students collection

        Args:
            student_id: Student ID (日介番号)

        Returns:
            Student data dictionary if exists, None otherwise
        """
        try:
            doc_ref = self.db.collection("students").document(student_id)
            doc = doc_ref.get()

            if doc.exists:
                return doc.to_dict()
            else:
                return None

        except Exception as e:
            logger.error(
                f"Error getting student {student_id}: {e}", exc_info=True
            )
            # Return None on error (fail-open strategy)
            return None

    def get_all_students(self) -> list:
        """
        Get all student data from students collection

        Returns:
            List of student data dictionaries
        """
        try:
            students = []
            docs = self.db.collection("students").stream()

            for doc in docs:
                students.append(doc.to_dict())

            logger.info(f"Retrieved {len(students)} students from Firestore")
            return students

        except Exception as e:
            logger.error(f"Error getting all students: {e}", exc_info=True)
            # Return empty list on error (fail-open strategy)
            return []

    def get_students_by_ids(self, student_ids: list) -> list:
        """
        Get student data for multiple student IDs

        Args:
            student_ids: List of student IDs (日介番号)

        Returns:
            List of student data dictionaries

        Note:
            Uses batch get for efficiency (max 500 documents per batch)
        """
        try:
            if not student_ids:
                return []

            students = []

            # Firestore allows max 500 documents per batch get
            # Split into chunks of 500
            chunk_size = 500
            for i in range(0, len(student_ids), chunk_size):
                chunk = student_ids[i : i + chunk_size]

                # Get document references
                doc_refs = [
                    self.db.collection("students").document(student_id)
                    for student_id in chunk
                ]

                # Batch get
                docs = self.db.get_all(doc_refs)

                for doc in docs:
                    if doc.exists:
                        students.append(doc.to_dict())

            logger.info(
                f"Retrieved {len(students)}/{len(student_ids)} students from Firestore"
            )
            return students

        except Exception as e:
            logger.error(
                f"Error getting students by IDs: {e}", exc_info=True
            )
            # Return empty list on error (fail-open strategy)
            return []
