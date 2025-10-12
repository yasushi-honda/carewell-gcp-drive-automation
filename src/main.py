"""
Carewell File Collector - Cloud Functions Entrypoint
"""

import json
import logging
import os

from flask import Request

from firestore_service import FirestoreService
from google_drive_service import GoogleDriveService
from playwright_automation import PlaywrightAutomationEngine
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

        # Initialize services
        engine = PlaywrightAutomationEngine()
        drive_service = GoogleDriveService()
        firestore_service = FirestoreService()
        sheets_service = SheetsService()

        try:
            # Navigate to task page
            page = engine.navigate_to_task(class_name, task_pattern)
            logger.info(f"Successfully navigated to task page: {page.url}")

            # Get submission list
            submission_data = engine.get_submission_list()
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
                    if (
                        submission.get("download_url")
                        and submission.get("filename")
                        and submission.get("detail_url")
                    ):
                        # Check if already uploaded
                        existing_upload = firestore_service.check_already_uploaded(
                            class_name,
                            task_id,
                            submission.get("student_id", ""),
                            submission["filename"],
                            submission.get("submit_date", ""),
                        )

                        if existing_upload:
                            logger.info(
                                f"Skipping already uploaded file: {submission['filename']} (Drive ID: {existing_upload.get('drive_file_id')})"
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

                        # Record upload in Firestore
                        metadata = {
                            "student_id": submission.get("student_id"),
                            "log_no": submission.get("log_no"),
                            "score": submission.get("score"),
                            "pass_status": submission.get("pass_status"),
                            "status": submission.get("status"),
                            "submit_date": submission.get("submit_date"),
                        }

                        firestore_service.record_upload(
                            class_name,
                            task_id,
                            submission["student_name"],
                            submission.get("student_id", ""),
                            submission["filename"],
                            drive_file_id,
                            drive_folder_id,
                            submission.get("submit_date", ""),
                            metadata=metadata,
                        )

                        # Record in Google Sheets
                        sheets_service.append_record(
                            spreadsheet_id,
                            task_id,
                            submission["student_name"],
                            submission.get("student_id", ""),
                            submission.get("submit_date", ""),
                            submission["filename"],
                            drive_file_id,
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

        # Get document count first
        collection_ref = (
            firestore_service.db.collection(class_name)
            .document(task_id)
            .collection("documents")
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


def app(request):
    """
    Main entrypoint with routing

    Routes:
    - POST /         → File collection (main)
    - POST /cleanup  → Firestore cleanup (administrative)
    - GET  /health   → Health check
    """
    path = request.path
    method = request.method

    logger.info(f"Request: {method} {path}")

    if path == "/cleanup" and method == "POST":
        return cleanup_firestore(request)
    elif path == "/health" and method == "GET":
        return health_check(request)
    elif path == "/" and method == "POST":
        return main(request)
    else:
        return {
            "error": f"Not found: {method} {path}",
            "available_endpoints": ["POST /", "POST /cleanup", "GET /health"],
        }, 404
