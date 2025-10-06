"""
Carewell File Collector - Cloud Functions Entrypoint
"""
import json
import logging
from playwright_automation import PlaywrightAutomationEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
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

        # Initialize Playwright automation
        engine = PlaywrightAutomationEngine()

        try:
            # Navigate to task page
            page = engine.navigate_to_task(class_name, task_name)
            logger.info(f"Successfully navigated to task page: {page.url}")

            # Get submission list
            submissions = engine.get_submission_list()
            logger.info(f"Found {len(submissions)} submissions")

            # Download files (test with first submission only for now)
            downloaded_count = 0
            failed_count = 0

            for submission in submissions[:1]:  # Test with first submission only
                try:
                    if submission.get("download_url") and submission.get("filename"):
                        logger.info(f"Testing download: {submission['filename']}")
                        file_path = engine.download_file(
                            submission["download_url"],
                            submission["filename"]
                        )
                        logger.info(f"Downloaded to: {file_path}")
                        downloaded_count += 1
                    else:
                        logger.warning(f"No download link for {submission['student_name']}")
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Failed to download {submission['filename']}: {e}")
                    failed_count += 1

            return {
                "status": "success",
                "message": "File download test completed",
                "submissions_found": len(submissions),
                "processed": downloaded_count,
                "skipped": 0,
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
