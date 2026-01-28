"""
Retry utilities for Google Sheets operations.

Provides exponential backoff retry logic for unreliable API calls.
"""

import logging
import time

logger = logging.getLogger(__name__)


def append_record_with_retry(
    sheets_service,
    spreadsheet_id: str,
    task_id: str,
    student_name: str,
    student_id: str,
    submit_date: str,
    filename: str,
    drive_file_id: str,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> bool:
    """
    Append record to Google Sheets with exponential backoff retry.

    Args:
        sheets_service: SheetsService instance
        spreadsheet_id: Google Sheets spreadsheet ID
        task_id: Task ID (sheet name)
        student_name: Student name
        student_id: Student ID
        submit_date: Submission date
        filename: Filename
        drive_file_id: Google Drive file ID
        max_retries: Maximum retry attempts (default: 3)
        base_delay: Base delay in seconds for exponential backoff (default: 1.0)

    Returns:
        True if successful, False if all retries failed
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            result = sheets_service.append_record(
                spreadsheet_id,
                task_id,
                student_name,
                student_id,
                submit_date,
                filename,
                drive_file_id,
            )

            if result:
                if attempt > 0:
                    logger.info(
                        f"Sheets append succeeded on retry {attempt + 1}/{max_retries}: "
                        f"{student_name} ({student_id})"
                    )
                return True

            # append_record returned False (caught exception internally)
            last_error = "append_record returned False"
            logger.warning(
                f"Sheets append failed (attempt {attempt + 1}/{max_retries}): "
                f"{student_name} ({student_id})"
            )

        except Exception as e:
            last_error = str(e)
            logger.warning(
                f"Sheets append exception (attempt {attempt + 1}/{max_retries}): "
                f"{student_name} ({student_id}) - {e}"
            )

        # Exponential backoff: 1s, 2s, 4s
        if attempt < max_retries - 1:
            delay = base_delay * (2 ** attempt)
            logger.info(f"Retrying in {delay}s...")
            time.sleep(delay)

    # All retries failed
    logger.error(
        f"Sheets append failed after {max_retries} attempts: "
        f"{student_name} ({student_id}) - Last error: {last_error}"
    )
    return False
