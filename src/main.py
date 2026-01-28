"""
Carewell File Collector - Cloud Functions Entrypoint
"""

import json
import logging
import os
import time  # ✅ 追加: 診断ログで使用（将来の拡張用に追加）

from flask import Request

from firestore_service import FirestoreService
from google_drive_service import GoogleDriveService
from playwright_automation import PlaywrightAutomationEngine
from sheets_retry import append_record_with_retry
from sheets_service import SheetsService

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main(request):
    """
    Cloud Functions HTTP entrypoint

    Expected request body:
    {
        "class_name": "令和7年度 デジタル中核人材養成研修 №01",
        "task_id": "課題①",
        "task_pattern": "課題①",
        "drive_folder_id": "1abc...xyz",
        "spreadsheet_id": "1def...uvw"
    }

    Returns:
    {
        "status": "success",
        "message": "File collection completed",
        "submissions_found": 12,
        "processed": 10,
        "skipped": 2,
        "failed": 0,
        "total_count_from_ui": 12,
        "count_verified": true
    }
    """
    try:
        # Parse request
        request_json = request.get_json(silent=True)
        if not request_json:
            return {"error": "Request body must be JSON"}, 400

        # Validate required parameters
        required_params = [
            "class_name",
            "task_id",
            "task_pattern",
            "drive_folder_id",
            "spreadsheet_id",
        ]
        missing_params = [p for p in required_params if p not in request_json]
        if missing_params:
            return {
                "error": f"Missing required parameters: {', '.join(missing_params)}"
            }, 400

        class_name = request_json["class_name"]
        task_id = request_json["task_id"]
        task_pattern = request_json["task_pattern"]
        drive_folder_id = request_json["drive_folder_id"]
        spreadsheet_id = request_json["spreadsheet_id"]

        logger.info(
            f"Starting file collection for class={class_name}, task_id={task_id}, task_pattern={task_pattern}"
        )

        # Initialize services with class/task context for better log identification
        engine = PlaywrightAutomationEngine(class_name=class_name, task_id=task_id)
        drive_service = GoogleDriveService()
        firestore_service = FirestoreService()
        sheets_service = SheetsService()

        try:
            # Navigate to task page
            page = engine.navigate_to_task(class_name, task_pattern)

            # If class or task not found (likely not yet created), return success with zero counts
            if page is None:
                logger.info(
                    f"Class or task not yet created, skipping: {class_name}/{task_pattern}"
                )
                return {
                    "status": "success",
                    "message": "Task not yet created",
                    "submissions_found": 0,
                    "processed": 0,
                    "skipped": 0,
                    "failed": 0,
                }, 200

            logger.info(f"Successfully navigated to task page: {page.url}")

            # Get submission list with early duplicate checking
            submission_data = engine.get_submission_list(
                class_name=class_name,
                task_id=task_id,
                firestore_service=firestore_service,
            )
            submissions = submission_data["submissions"]
            total_count = submission_data.get("total_count")
            verified = submission_data.get("verified", False)

            logger.info(f"Found {len(submissions)} submissions")
            if total_count is not None:
                logger.info(f"Total count from UI: {total_count}, Verified: {verified}")

            # Process all submissions
            downloaded_count = 0
            skipped_count = 0
            failed_count = 0

            for submission in submissions:
                file_path = None
                try:
                    # Check early duplicate flag first (set during get_submission_list)
                    if submission.get("is_duplicate", False):
                        # Backfill grading info if available
                        grading_metadata = {
                            "pass_status": submission.get("pass_status"),
                            "score": submission.get("score"),
                            "grading_status": submission.get("status"),
                            "log_no": submission.get("log_no"),
                        }
                        # Remove None values
                        grading_metadata = {
                            k: v for k, v in grading_metadata.items() if v is not None
                        }

                        # Only update if we have grading info to backfill
                        if grading_metadata:
                            # Get composite_key from early duplicate check result
                            composite_key = submission.get("existing_composite_key")

                            if composite_key:
                                logger.info(
                                    f"Backfilling grading info for existing file: student_id={submission.get('student_id')}, submit_date={submission.get('submit_date')}, composite_key={composite_key}"
                                )

                                success = firestore_service.update_file_metadata(
                                    class_name, task_id, composite_key, grading_metadata
                                )

                                if success:
                                    logger.info(
                                        f"Successfully backfilled grading info: {composite_key}"
                                    )
                                else:
                                    logger.warning(
                                        f"Failed to backfill grading info: {composite_key}"
                                    )
                            else:
                                logger.warning(
                                    "Cannot backfill: existing_composite_key not available"
                                )

                        logger.info(
                            f"Skipping already uploaded file (early check): student_id={submission.get('student_id')}, submit_date={submission.get('submit_date')}"
                        )
                        skipped_count += 1
                        continue

                    # ✅ 診断ログ: Phase 2条件チェック（download_url/filename/detail_url の有無確認）
                    logger.info(
                        f"[PHASE 2] Checking submission: {submission.get('student_name', 'UNKNOWN')} - "
                        f"download_url={'SET' if submission.get('download_url') else 'NONE'}, "
                        f"filename={'SET' if submission.get('filename') else 'NONE'}, "
                        f"detail_url={'SET' if submission.get('detail_url') else 'NONE'}"
                    )

                    if (
                        submission.get("download_url")
                        and submission.get("filename")
                        and submission.get("detail_url")
                    ):
                        # For non-early-duplicates, perform full check with filename
                        # (defense-in-depth: catch any edge cases)
                        existing_upload = firestore_service.check_already_uploaded(
                            class_name,
                            task_id,
                            submission.get("student_id", ""),
                            submission["filename"],
                            submission.get("submit_date", ""),
                        )

                        if existing_upload:
                            logger.info(
                                f"Skipping already uploaded file (filename check): {submission['filename']} (Drive ID: {existing_upload.get('drive_file_id')})"
                            )
                            skipped_count += 1
                            continue

                        # Download file
                        logger.info(f"Downloading: {submission['filename']}")
                        file_path = engine.download_file(
                            submission["download_url"],
                            submission["filename"],
                            submission["detail_url"],
                        )
                        logger.info(f"Downloaded to: {file_path}")

                        # Upload to Google Drive
                        drive_file_id = drive_service.upload_file(
                            file_path, submission["filename"], drive_folder_id
                        )
                        logger.info(f"Uploaded to Drive: {drive_file_id}")

                        # Get student data for denormalization (Phase 3: Student metadata integration)
                        student_id = submission.get("student_id", "")
                        student = None
                        student_furigana = ""
                        student_group = "未分類"
                        student_status = "active"
                        student_company = ""
                        student_office = ""
                        student_service_type = ""
                        student_serial_number = 0
                        student_number = ""

                        if student_id:
                            student = firestore_service.get_student(student_id)
                            if student:
                                student_furigana = student.get("furigana", "")
                                student_group = student.get("group", "未分類")
                                student_status = student.get("status", "active")
                                student_company = student.get("company", "")
                                student_office = student.get("office", "")
                                student_service_type = student.get("service_type", "")
                                student_serial_number = student.get("serial_number", 0)
                                student_number = student.get("student_number", "")
                            else:
                                logger.warning(
                                    f"Student not found in students collection: {student_id}"
                                )

                        # Record upload in Firestore
                        # Build metadata with grading information (excluding fields already in parent doc)
                        metadata = {
                            "pass_status": submission.get("pass_status"),
                            "score": submission.get("score"),
                            "grading_status": submission.get(
                                "status"
                            ),  # Renamed from "status" for clarity
                            "log_no": submission.get("log_no"),
                        }
                        # Remove None values to keep metadata clean
                        metadata = {k: v for k, v in metadata.items() if v is not None}

                        firestore_service.record_upload(
                            class_name,
                            task_id,
                            submission["student_name"],
                            student_id,
                            submission["filename"],
                            drive_file_id,
                            drive_folder_id,
                            submission.get("submit_date", ""),
                            metadata=metadata,
                            task_pattern=task_pattern,
                            # Denormalized student fields (Phase 3)
                            student_furigana=student_furigana,
                            student_group=student_group,
                            student_status=student_status,
                            student_company=student_company,
                            student_office=student_office,
                            student_service_type=student_service_type,
                            student_serial_number=student_serial_number,
                            student_number=student_number,
                        )

                        # Record in Google Sheets with retry
                        sheets_success = append_record_with_retry(
                            sheets_service,
                            spreadsheet_id,
                            task_id,
                            submission["student_name"],
                            submission.get("student_id", ""),
                            submission.get("submit_date", ""),
                            submission["filename"],
                            drive_file_id,
                        )

                        # Update sheets_sync_status in Firestore
                        if sheets_success:
                            firestore_service.update_sheets_sync_status(
                                class_name,
                                task_id,
                                student_id,
                                submission["filename"],
                                submission.get("submit_date", ""),
                                status="success",
                            )
                        else:
                            firestore_service.update_sheets_sync_status(
                                class_name,
                                task_id,
                                student_id,
                                submission["filename"],
                                submission.get("submit_date", ""),
                                status="failed",
                                error_message="All retry attempts failed",
                            )
                            logger.error(
                                f"SHEETS_SYNC_FAILED: {submission['student_name']} "
                                f"({student_id}) - {submission['filename']}"
                            )

                        downloaded_count += 1
                    else:
                        logger.warning(
                            f"No download link for {submission['student_name']}"
                        )
                        failed_count += 1
                except Exception as e:
                    logger.error(
                        f"Failed to download {submission.get('filename', 'unknown')}: {e}"
                    )
                    failed_count += 1
                finally:
                    # Clean up temporary file
                    if file_path and os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            logger.info(f"Cleaned up temporary file: {file_path}")
                        except Exception as cleanup_error:
                            logger.warning(
                                f"Failed to clean up {file_path}: {cleanup_error}"
                            )

            response = {
                "status": "success",
                "message": "File collection completed",
                "submissions_found": len(submissions),
                "processed": downloaded_count,
                "skipped": skipped_count,
                "failed": failed_count,
            }

            # Add count verification info if available
            if total_count is not None:
                response["total_count_from_ui"] = total_count
                response["count_verified"] = verified
                if not verified:
                    response["warning"] = (
                        f"Count mismatch: UI shows {total_count} but found {len(submissions)}"
                    )

            return response, 200

        finally:
            engine.close()

    except Exception as e:
        logger.error(f"Error during execution: {str(e)}", exc_info=True)
        return {"status": "error", "error": str(e)}, 500


def cleanup_firestore(request):
    """
    Firestore cleanup endpoint for administrative operations

    Expected request body:
    {
        "class_name": "令和7年度 デジタル中核人材養成研修 №01",
        "task_id": "課題①",
        "confirm": true
    }
    """
    try:
        # Parse request
        request_json = request.get_json(silent=True)
        if not request_json:
            return {"error": "Request body must be JSON"}, 400

        # Validate required parameters
        required_params = ["class_name", "task_id", "confirm"]
        missing_params = [p for p in required_params if p not in request_json]
        if missing_params:
            return {
                "error": f"Missing required parameters: {', '.join(missing_params)}"
            }, 400

        class_name = request_json["class_name"]
        task_id = request_json["task_id"]
        confirm = request_json.get("confirm", False)

        if not confirm:
            return {"error": "Set 'confirm': true to execute cleanup"}, 400

        logger.warning(
            f"Starting Firestore cleanup for class={class_name}, task_id={task_id}"
        )

        # Initialize Firestore service
        firestore_service = FirestoreService()

        # Get document count first (NEW SCHEMA)
        collection_ref = (
            firestore_service.db.collection("submissions")
            .document(class_name)
            .collection("tasks")
            .document(task_id)
            .collection("files")
        )
        docs = list(collection_ref.stream())
        doc_count = len(docs)

        logger.info(f"Found {doc_count} documents to delete")

        if doc_count == 0:
            return {
                "status": "success",
                "message": "No documents found to delete",
                "deleted_count": 0,
            }, 200

        # Delete all documents
        deleted_count = 0
        failed_count = 0

        for doc in docs:
            try:
                doc.reference.delete()
                deleted_count += 1
                if deleted_count % 10 == 0:
                    logger.info(f"Deleted {deleted_count}/{doc_count} documents")
            except Exception as e:
                logger.error(f"Failed to delete document {doc.id}: {e}")
                failed_count += 1

        logger.warning(
            f"Cleanup completed: deleted={deleted_count}, failed={failed_count}"
        )

        # Verify cleanup
        remaining_docs = list(collection_ref.stream())
        remaining_count = len(remaining_docs)

        return {
            "status": "success",
            "message": f"Deleted {deleted_count} documents",
            "deleted_count": deleted_count,
            "failed_count": failed_count,
            "remaining_count": remaining_count,
        }, 200

    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}", exc_info=True)
        return {"status": "error", "error": str(e)}, 500


def health_check(request):
    """Health check endpoint"""
    return {"status": "healthy", "service": "carewell-file-collector"}, 200


def sync_students_from_sheets(request):
    """
    Admin endpoint for syncing student master data from Google Sheets

    Expected request body:
    {
        "backfill": false  # Optional: Whether to backfill existing files with student data
    }

    Returns:
    {
        "status": "success",
        "students_synced": 2000,
        "students_created": 150,
        "students_updated": 1850,
        "files_backfilled": 4000,  # Only if backfill=true
        "errors": []
    }
    """
    try:
        # Parse request
        request_json = request.get_json(silent=True) or {}
        backfill = request_json.get("backfill", False)

        logger.info(f"Starting student sync from Google Sheets (backfill={backfill})")

        # Initialize services
        sheets_service = SheetsService()
        firestore_service = FirestoreService()

        # Phase 1: Sync students from Google Sheets
        spreadsheet_id = os.environ.get(
            "STUDENT_SPREADSHEET_ID", "1AQ12-h3n_NmN2kWxi4Z_g354X0wmUyMKAPeAsXJwu_w"
        )
        sync_result = _sync_students(sheets_service, firestore_service, spreadsheet_id)

        if sync_result.get("status") != "success":
            return sync_result, 500

        response = {
            "status": "success",
            "students_synced": sync_result["students_synced"],
            "students_created": sync_result["students_created"],
            "students_updated": sync_result["students_updated"],
            "errors": sync_result.get("errors", []),
        }

        # Phase 2: Backfill existing files (optional)
        if backfill:
            logger.info("Starting backfill of existing files...")
            backfill_result = _backfill_all_files(firestore_service)

            response["files_backfilled"] = backfill_result.get("files_updated", 0)
            response["files_skipped"] = backfill_result.get("files_skipped", 0)
            response["backfill_errors"] = backfill_result.get("errors", [])

        logger.info(f"Student sync completed: {response}")
        return response, 200

    except Exception as e:
        logger.error(f"Error during student sync: {str(e)}", exc_info=True)
        return {"status": "error", "error": str(e)}, 500


def get_duplicate_students(request):
    """
    Admin endpoint for getting duplicate student_id information

    Returns:
    {
        "status": "success",
        "duplicates": [
            {
                "student_id": "N9903499",
                "name": "山田太郎",
                "kept_class": "No3",
                "kept_status": "active",
                "ignored_class": "No5",
                "ignored_status": "inactive",
                "resolution": "active_inactive"
            },
            ...
        ],
        "total_duplicates": 23
    }
    """
    try:
        logger.info("Getting duplicate student information from Google Sheets")

        # Initialize service
        sheets_service = SheetsService()

        # Get spreadsheet ID
        spreadsheet_id = os.environ.get(
            "STUDENT_SPREADSHEET_ID", "1AQ12-h3n_NmN2kWxi4Z_g354X0wmUyMKAPeAsXJwu_w"
        )

        # Get duplicates (now returns dict with duplicates and class_urls)
        result = sheets_service.get_duplicate_students(spreadsheet_id)

        response = {
            "status": "success",
            "duplicates": result.get("duplicates", []),
            "class_urls": result.get("class_urls", {}),
            "total_duplicates": len(result.get("duplicates", [])),
        }

        return _add_cors_headers(response, 200)

    except Exception as e:
        logger.error(f"Error getting duplicate students: {str(e)}", exc_info=True)
        return _add_cors_headers({"status": "error", "error": str(e)}, 500)


def _sync_students(sheets_service, firestore_service, spreadsheet_id):
    """
    Sync student data from Google Sheets to Firestore students collection

    Args:
        sheets_service: SheetsService instance
        firestore_service: FirestoreService instance
        spreadsheet_id: Google Sheets spreadsheet ID

    Returns:
        Dictionary with sync results
    """
    try:
        # Get student data from Google Sheets
        logger.info(f"Reading student data from spreadsheet: {spreadsheet_id}")
        students = sheets_service.get_student_data(spreadsheet_id)

        if not students:
            logger.warning("No student data found in spreadsheet")
            return {
                "status": "success",
                "students_synced": 0,
                "students_created": 0,
                "students_updated": 0,
                "errors": [],
            }

        logger.info(f"Found {len(students)} students in spreadsheet")

        # Batch process students (500 at a time for Firestore batch limit)
        created_count = 0
        updated_count = 0
        error_count = 0
        errors = []

        batch_size = 500
        for i in range(0, len(students), batch_size):
            batch = students[i : i + batch_size]
            logger.info(
                f"Processing student batch {i // batch_size + 1}: {len(batch)} students"
            )

            for student in batch:
                try:
                    # Check if student already exists
                    student_exists = firestore_service.student_exists(
                        student["student_id"]
                    )

                    # Create/update student
                    success = firestore_service.create_student(student)

                    if success:
                        if student_exists:
                            updated_count += 1
                        else:
                            created_count += 1
                    else:
                        error_count += 1
                        errors.append(
                            {
                                "student_id": student["student_id"],
                                "error": "Failed to create/update student",
                            }
                        )

                except Exception as e:
                    error_count += 1
                    error_msg = f"Error syncing student {student.get('student_id', 'unknown')}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(
                        {"student_id": student.get("student_id"), "error": str(e)}
                    )

        logger.info(
            f"Student sync completed: created={created_count}, updated={updated_count}, errors={error_count}"
        )

        return {
            "status": "success",
            "students_synced": created_count + updated_count,
            "students_created": created_count,
            "students_updated": updated_count,
            "errors": errors[:100],  # Limit errors to first 100
        }

    except Exception as e:
        logger.error(f"Error in _sync_students: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "students_synced": 0,
            "students_created": 0,
            "students_updated": 0,
            "errors": [{"error": str(e)}],
        }


def _backfill_all_files(firestore_service):
    """
    Backfill existing file documents with denormalized student data

    Args:
        firestore_service: FirestoreService instance

    Returns:
        Dictionary with backfill results

    Note:
        This function ALWAYS updates all files with the latest student data,
        ensuring consistency between students/ and files/ collections.
        Previously existing data is overwritten with current master data.
    """
    try:
        logger.info("Starting backfill of existing files with student data...")

        # Get all students first
        all_students = firestore_service.get_all_students()
        if not all_students:
            logger.warning("No students found in Firestore, skipping backfill")
            return {
                "status": "success",
                "files_updated": 0,
                "files_skipped": 0,
                "errors": [],
            }

        # Create student lookup dictionary
        student_lookup = {s["student_id"]: s for s in all_students}
        logger.info(f"Loaded {len(student_lookup)} students for backfill")

        updated_count = 0
        skipped_count = 0
        error_count = 0
        errors = []

        # Iterate through all class/task combinations
        # NOTE: This is a simple implementation that scans all submissions
        # For large datasets, consider using Firestore collection group queries
        submissions_ref = firestore_service.db.collection("submissions")

        for class_doc in submissions_ref.stream():
            class_name = class_doc.id
            logger.info(f"Processing class: {class_name}")

            tasks_ref = submissions_ref.document(class_name).collection("tasks")

            for task_doc in tasks_ref.stream():
                task_id = task_doc.id
                logger.info(f"Processing task: {class_name}/{task_id}")

                files_ref = tasks_ref.document(task_id).collection("files")

                for file_doc in files_ref.stream():
                    try:
                        file_data = file_doc.to_dict()
                        student_id = file_data.get("student_id")

                        if not student_id:
                            logger.warning(
                                f"File {file_doc.id} has no student_id, skipping"
                            )
                            skipped_count += 1
                            continue

                        # Get student data
                        student = student_lookup.get(student_id)
                        if not student:
                            logger.warning(
                                f"Student not found: {student_id}, skipping file {file_doc.id}"
                            )
                            skipped_count += 1
                            continue

                        # Update file with denormalized student data (always overwrite)
                        update_data = {
                            "student_furigana": student.get("furigana", ""),
                            "student_group": student.get("group", "未分類"),
                            "student_status": student.get("status", "active"),
                            "student_company": student.get("company", ""),
                            "student_office": student.get("office", ""),
                            "student_service_type": student.get("service_type", ""),
                            "student_serial_number": student.get("serial_number", 0),
                            "student_number": student.get("student_number", ""),
                        }

                        file_doc.reference.update(update_data)
                        updated_count += 1

                        if updated_count % 100 == 0:
                            logger.info(f"Backfilled {updated_count} files so far...")

                    except Exception as e:
                        error_count += 1
                        error_msg = f"Error backfilling file {file_doc.id}: {str(e)}"
                        logger.error(error_msg)
                        errors.append({"file_id": file_doc.id, "error": str(e)})

        logger.info(
            f"Backfill completed: updated={updated_count}, skipped={skipped_count}, errors={error_count}"
        )

        return {
            "status": "success",
            "files_updated": updated_count,
            "files_skipped": skipped_count,
            "errors": errors[:100],  # Limit errors to first 100
        }

    except Exception as e:
        logger.error(f"Error in _backfill_all_files: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "files_updated": 0,
            "files_skipped": 0,
            "errors": [{"error": str(e)}],
        }


def _add_cors_headers(response_data, status_code=200):
    """
    Add CORS headers to response for browser requests

    Args:
        response_data: Response data (dict or tuple)
        status_code: HTTP status code

    Returns:
        Tuple of (response_data, status_code, headers)
    """
    headers = {
        "Access-Control-Allow-Origin": "https://carewell-automation.web.app",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Max-Age": "3600",
    }
    return response_data, status_code, headers


def app(request):
    """
    Main entrypoint with routing

    Routes:
    - POST /                              → File collection (main)
    - POST /cleanup                       → Firestore cleanup (administrative)
    - POST /admin/sync-students-from-sheets → Student sync from Google Sheets (administrative)
    - GET  /admin/duplicate-students      → Get duplicate student_id info (administrative)
    - GET  /health                        → Health check
    - OPTIONS /*                          → CORS preflight
    """
    path = request.path
    method = request.method

    logger.info(f"Request: {method} {path}")

    # Handle CORS preflight requests
    if method == "OPTIONS":
        return _add_cors_headers({}, 204)

    if path == "/cleanup" and method == "POST":
        return cleanup_firestore(request)
    elif path == "/admin/sync-students-from-sheets" and method == "POST":
        result = sync_students_from_sheets(request)
        # Add CORS headers for browser requests
        if isinstance(result, tuple):
            return _add_cors_headers(result[0], result[1])
        return _add_cors_headers(result, 200)
    elif path == "/admin/duplicate-students" and method == "GET":
        return get_duplicate_students(request)
    elif path == "/health" and method == "GET":
        return health_check(request)
    elif path == "/" and method == "POST":
        return main(request)
    else:
        return {
            "error": f"Not found: {method} {path}",
            "available_endpoints": [
                "POST /",
                "POST /cleanup",
                "POST /admin/sync-students-from-sheets",
                "GET /admin/duplicate-students",
                "GET /health",
            ],
        }, 404
