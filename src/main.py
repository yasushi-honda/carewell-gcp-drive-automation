"""
Carewell File Collector - Cloud Functions Entrypoint
"""
import json
import logging
import os
from playwright_automation import PlaywrightAutomationEngine
from google_drive_service import GoogleDriveService
from firestore_service import FirestoreService
from sheets_service import SheetsService

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main(request):
    """
    Cloud Functions HTTP entrypoint

    Expected request body:
    {
        "class_name": "令和7年度 デジタル中核人材養成研修 №01",
        "task_name": "課題①業務分析　※～11/3〆切",
        "drive_folder_id": "1abc...xyz",
        "spreadsheet_id": "1def...uvw"
    }
    """
    try:
        # Parse request
        request_json = request.get_json(silent=True)
        if not request_json:
            return {"error": "Request body must be JSON"}, 400

        # Validate required parameters
        required_params = ["class_name", "task_name", "drive_folder_id", "spreadsheet_id"]
        missing_params = [p for p in required_params if p not in request_json]
        if missing_params:
            return {
                "error": f"Missing required parameters: {', '.join(missing_params)}"
            }, 400

        class_name = request_json["class_name"]
        task_name = request_json["task_name"]
        drive_folder_id = request_json["drive_folder_id"]
        spreadsheet_id = request_json["spreadsheet_id"]

        logger.info(f"Starting file collection for class={class_name}, task={task_name}")

        # Initialize services
        engine = PlaywrightAutomationEngine()
        drive_service = GoogleDriveService()
        firestore_service = FirestoreService()
        sheets_service = SheetsService()

        try:
            # Navigate to task page
            page = engine.navigate_to_task(class_name, task_name)
            logger.info(f"Successfully navigated to task page: {page.url}")

            # Get submission list
            submissions = engine.get_submission_list()
            logger.info(f"Found {len(submissions)} submissions")

            # Process all submissions
            downloaded_count = 0
            skipped_count = 0
            failed_count = 0

            for submission in submissions:
                file_path = None
                try:
                    if submission.get("download_url") and submission.get("filename") and submission.get("detail_url"):
                        # Check if already uploaded
                        existing_upload = firestore_service.check_already_uploaded(
                            class_name,
                            task_name,
                            submission['student_name'],
                            submission['filename']
                        )

                        if existing_upload:
                            logger.info(f"Skipping already uploaded file: {submission['filename']} (Drive ID: {existing_upload.get('drive_file_id')})")
                            skipped_count += 1
                            continue

                        # Download file
                        logger.info(f"Downloading: {submission['filename']}")
                        file_path = engine.download_file(
                            submission["download_url"],
                            submission["filename"],
                            submission["detail_url"]
                        )
                        logger.info(f"Downloaded to: {file_path}")

                        # Upload to Google Drive
                        drive_file_id = drive_service.upload_file(
                            file_path,
                            submission['filename'],
                            drive_folder_id
                        )
                        logger.info(f"Uploaded to Drive: {drive_file_id}")

                        # Record upload in Firestore
                        metadata = {
                            "log_no": submission.get('log_no'),
                            "score": submission.get('score'),
                            "pass_status": submission.get('pass_status'),
                            "status": submission.get('status'),
                            "submit_date": submission.get('submit_date')
                        }

                        firestore_service.record_upload(
                            class_name,
                            task_name,
                            submission['student_name'],
                            submission['filename'],
                            drive_file_id,
                            drive_folder_id,
                            metadata=metadata
                        )

                        # Record in Google Sheets
                        sheets_service.append_record(
                            spreadsheet_id,
                            submission['student_name'],
                            submission['filename'],
                            drive_file_id,
                            metadata=metadata
                        )

                        downloaded_count += 1
                    else:
                        logger.warning(f"No download link for {submission['student_name']}")
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Failed to download {submission.get('filename', 'unknown')}: {e}")
                    failed_count += 1
                finally:
                    # Clean up temporary file
                    if file_path and os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            logger.info(f"Cleaned up temporary file: {file_path}")
                        except Exception as cleanup_error:
                            logger.warning(f"Failed to clean up {file_path}: {cleanup_error}")

            return {
                "status": "success",
                "message": "File collection completed",
                "submissions_found": len(submissions),
                "processed": downloaded_count,
                "skipped": skipped_count,
                "failed": failed_count
            }, 200

        finally:
            engine.close()

    except Exception as e:
        logger.error(f"Error during execution: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }, 500
