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

    def _ensure_headers(self, spreadsheet_id: str, sheet_name: str = "シート1"):
        """
        Ensure spreadsheet has proper headers

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Sheet name (default: "シート1")
        """
        try:
            # Check if headers exist
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1:J1"
            ).execute()

            values = result.get('values', [])

            # If headers don't exist, create them
            if not values or len(values[0]) == 0:
                headers = [
                    "学生名",
                    "学生ID",
                    "ファイル名",
                    "提出日時",
                    "スコア",
                    "合否",
                    "状態",
                    "Drive File ID",
                    "Drive Link",
                    "アップロード日時"
                ]

                self.service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"{sheet_name}!A1:J1",
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
        student_name: str,
        filename: str,
        drive_file_id: str,
        metadata: Optional[dict] = None,
        sheet_name: str = "シート1"
    ) -> bool:
        """
        Append a new record to the spreadsheet

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            student_name: Student name (without ID)
            filename: Uploaded filename
            drive_file_id: Google Drive file ID
            metadata: Additional metadata (student_id, submit_date, score, etc.)
            sheet_name: Sheet name (default: "シート1")

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure headers exist
            self._ensure_headers(spreadsheet_id, sheet_name)

            # Prepare row data
            metadata = metadata or {}

            drive_link = f"https://drive.google.com/file/d/{drive_file_id}/view"
            upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            row = [
                student_name,
                metadata.get("student_id", ""),
                filename,
                metadata.get("submit_date", ""),
                metadata.get("score", ""),
                metadata.get("pass_status", ""),
                metadata.get("status", ""),
                drive_file_id,
                drive_link,
                upload_time
            ]

            # Append row
            result = self.service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A:J",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]}
            ).execute()

            logger.info(f"Appended record to spreadsheet: {student_name} ({metadata.get('student_id', '')}) - {filename}")
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
