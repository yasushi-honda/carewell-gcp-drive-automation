"""
Google Sheets Service for recording uploaded files
"""
import logging
from datetime import datetime
from typing import Optional, List
from googleapiclient.discovery import build
from google.auth import default

logger = logging.getLogger(__name__)


class SheetsService:
    """
    Handles Google Sheets operations for file upload records
    """

    def __init__(self):
        """Initialize Google Sheets API client"""
        self.service = None
        self._initialize_service()

    def _initialize_service(self):
        """
        Initialize Google Sheets API service with default credentials

        Uses Application Default Credentials (ADC)
        """
        try:
            credentials, project = default(scopes=[
                'https://www.googleapis.com/auth/spreadsheets'
            ])

            self.service = build('sheets', 'v4', credentials=credentials)
            logger.info("Google Sheets service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets service: {e}", exc_info=True)
            raise

    def _generate_composite_key(self, student_id: str, filename: str, submit_date: str) -> str:
        """
        Generate composite key for file identification (same logic as FirestoreService)

        Args:
            student_id: Student ID (e.g., N9902913)
            filename: Original filename
            submit_date: Submission date/time

        Returns:
            Composite key string in format: {student_id}_{filename}_{submit_date}
        """
        # Sanitize submit_date to remove special characters
        safe_submit_date = submit_date.replace(' ', '_').replace(':', '-').replace('/', '-')
        composite_key = f"{student_id}_{filename}_{safe_submit_date}"
        return composite_key

    def _ensure_headers(self, spreadsheet_id: str, sheet_name: str):
        """
        Ensure spreadsheet has proper headers

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Sheet name (task_id)
        """
        try:
            # Check if headers exist (quote sheet name for special characters)
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_name}'!A1:H1"
            ).execute()

            values = result.get('values', [])

            # If headers don't exist, create them
            if not values or len(values[0]) == 0:
                headers = [
                    "課題ID",
                    "複合キー",
                    "氏名",
                    "日介番号",
                    "提出日",
                    "ファイル名",
                    "ファイルURL",
                    "ダウンロード日時"
                ]

                self.service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"'{sheet_name}'!A1:H1",
                    valueInputOption="RAW",
                    body={"values": [headers]}
                ).execute()

                logger.info(f"Created headers in {sheet_name}")

        except Exception as e:
            logger.error(f"Error ensuring headers: {e}", exc_info=True)
            # Continue even if header check fails

    def append_record(
        self,
        spreadsheet_id: str,
        task_id: str,
        student_name: str,
        student_id: str,
        submit_date: str,
        filename: str,
        drive_file_id: str
    ) -> bool:
        """
        Append a new record to the spreadsheet

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            task_id: Task ID (e.g., "課題①") - used as sheet name
            student_name: Student name (without ID)
            student_id: Student ID (e.g., N9902913)
            submit_date: Submission date/time
            filename: Uploaded filename
            drive_file_id: Google Drive file ID

        Returns:
            True if successful, False otherwise
        """
        try:
            # Use task_id as sheet name
            sheet_name = task_id

            # Generate composite key
            composite_key = self._generate_composite_key(student_id, filename, submit_date)

            # Ensure headers exist
            self._ensure_headers(spreadsheet_id, sheet_name)

            # Prepare row data
            drive_link = f"https://drive.google.com/file/d/{drive_file_id}/view"
            upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            row = [
                task_id,
                composite_key,
                student_name,
                student_id,
                submit_date,
                filename,
                drive_link,
                upload_time
            ]

            # Append row (quote sheet name for special characters)
            result = self.service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_name}'!A:H",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]}
            ).execute()

            logger.info(f"Appended record to spreadsheet: {student_name} ({student_id}) - {filename}")
            return True

        except Exception as e:
            logger.error(f"Error appending record to spreadsheet: {e}", exc_info=True)
            return False

    def check_record_exists(
        self,
        spreadsheet_id: str,
        student_name: str,
        filename: str,
        sheet_name: str = "シート1"
    ) -> bool:
        """
        Check if a record already exists in the spreadsheet

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            student_name: Student name
            filename: Filename to check
            sheet_name: Sheet name (default: "シート1")

        Returns:
            True if record exists, False otherwise
        """
        try:
            # Get all records
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A:B"
            ).execute()

            values = result.get('values', [])

            # Skip header row and check each record
            for row in values[1:]:
                if len(row) >= 2:
                    if row[0] == student_name and row[1] == filename:
                        logger.info(f"Record already exists in spreadsheet: {student_name} - {filename}")
                        return True

            return False

        except Exception as e:
            logger.error(f"Error checking record existence: {e}", exc_info=True)
            # Return False on error to allow retry
            return False

    def get_stats(self, spreadsheet_id: str, sheet_name: str = "Sheet1") -> dict:
        """
        Get statistics from spreadsheet

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Sheet name (default: "シート1")

        Returns:
            Dictionary with statistics
        """
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A:A"
            ).execute()

            values = result.get('values', [])

            # Subtract 1 for header row
            total_records = len(values) - 1 if len(values) > 0 else 0

            return {
                "total_records": total_records,
                "sheet_name": sheet_name
            }

        except Exception as e:
            logger.error(f"Error getting spreadsheet stats: {e}", exc_info=True)
            return {
                "total_records": 0,
                "sheet_name": sheet_name,
                "error": str(e)
            }
