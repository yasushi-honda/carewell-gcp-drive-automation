"""
Google Sheets Service for recording uploaded files
"""

import logging
from datetime import datetime
from typing import List, Optional

from google.auth import default
from googleapiclient.discovery import build

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
            credentials, project = default(
                scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )

            self.service = build("sheets", "v4", credentials=credentials)
            logger.info("Google Sheets service initialized successfully")

        except Exception as e:
            logger.error(
                f"Failed to initialize Google Sheets service: {e}", exc_info=True
            )
            raise

    def _generate_composite_key(
        self, student_id: str, filename: str, submit_date: str
    ) -> str:
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
        safe_submit_date = (
            submit_date.replace(" ", "_").replace(":", "-").replace("/", "-")
        )
        composite_key = f"{student_id}_{filename}_{safe_submit_date}"
        return composite_key

    def _ensure_sheet_exists(self, spreadsheet_id: str, sheet_name: str):
        """
        Ensure sheet exists, create if it doesn't

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Sheet name to create
        """
        try:
            # Get all sheets in the spreadsheet
            spreadsheet = (
                self.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            )

            # Check if sheet already exists
            for sheet in spreadsheet.get("sheets", []):
                if sheet.get("properties", {}).get("title") == sheet_name:
                    logger.info(f"Sheet '{sheet_name}' already exists")
                    return

            # Sheet doesn't exist, create it
            logger.info(f"Creating new sheet: {sheet_name}")
            request_body = {
                "requests": [{"addSheet": {"properties": {"title": sheet_name}}}]
            }

            self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id, body=request_body
            ).execute()

            logger.info(f"Successfully created sheet: {sheet_name}")

        except Exception as e:
            logger.error(f"Error ensuring sheet exists: {e}", exc_info=True)
            raise

    def _ensure_headers(self, spreadsheet_id: str, sheet_name: str):
        """
        Ensure spreadsheet has proper headers

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Sheet name (task_id)
        """
        try:
            # Escape single quotes in sheet name for A1 notation
            escaped_name = sheet_name.replace("'", "''")

            # Check if headers exist
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range=f"'{escaped_name}'!A1:H1")
                .execute()
            )

            values = result.get("values", [])

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
                    "ダウンロード日時",
                ]

                self.service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"'{escaped_name}'!A1:H1",
                    valueInputOption="RAW",
                    body={"values": [headers]},
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
        drive_file_id: str,
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
            composite_key = self._generate_composite_key(
                student_id, filename, submit_date
            )

            # Ensure sheet exists
            self._ensure_sheet_exists(spreadsheet_id, sheet_name)

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
                upload_time,
            ]

            # Escape single quotes in sheet name for A1 notation
            escaped_name = sheet_name.replace("'", "''")

            # Append row (sheet name with single quotes for special characters)
            result = (
                self.service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=spreadsheet_id,
                    range=f"'{escaped_name}'!A:H",
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": [row]},
                )
                .execute()
            )

            logger.info(
                f"Appended record to spreadsheet: {student_name} ({student_id}) - {filename}"
            )
            return True

        except Exception as e:
            logger.error(f"Error appending record to spreadsheet: {e}", exc_info=True)
            return False

    # NOTE: check_record_exists() was removed as duplicate checking is handled by Firestore
    # Firestore provides O(1) lookups vs Sheets O(n) full table scan
    # See: maintenance-report.md section 3

    def get_student_data(
        self, spreadsheet_id: str, sheet_name: str = "統合_受講者リスト"
    ) -> List[dict]:
        """
        受講生マスター情報をGoogle Sheetsから読み取る

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Sheet name (default: "統合_受講者リスト")

        Returns:
            List of student data dictionaries with keys:
            - 日介番号 (student_id)
            - ふりがな (furigana)
            - 氏名 (name)
            - グループ (group)
            - ステータス (status)
            - 勤務先 (company)
            - 事業所 (office)
            - サービス種別 (service_type)
            - Serial No. (serial_number)

        Note:
            - Skips header row (row 1)
            - Handles empty rows gracefully
            - Returns empty list on error (fail-open strategy)
            - L列「無効」チェックボックスがTRUEの場合、statusは"inactive"
        """
        try:
            logger.info(
                f"Reading student data from spreadsheet: {spreadsheet_id}, sheet: {sheet_name}"
            )

            # Escape single quotes in sheet name for A1 notation
            escaped_name = sheet_name.replace("'", "''")

            # Read A～L columns (all student master data including 無効 flag)
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range=f"'{escaped_name}'!A:L")
                .execute()
            )

            values = result.get("values", [])

            if not values:
                logger.warning(
                    f"No data found in spreadsheet: {spreadsheet_id}, sheet: {sheet_name}"
                )
                return []

            # Skip header row (first row)
            data_rows = values[1:]

            students = []
            for row_index, row in enumerate(data_rows, start=2):  # Start from row 2
                # Skip empty rows (all columns empty)
                if not any(row):
                    logger.debug(f"Skipping empty row: {row_index}")
                    continue

                # Handle rows with fewer than 12 columns (pad with empty strings)
                while len(row) < 12:
                    row.append("")

                # Check L列「無効」flag (checkbox returns "TRUE" or "FALSE" as string)
                is_inactive = (
                    row[11].strip().upper() == "TRUE" if row[11] else False
                )

                # Extract student data (correct column mapping)
                # A:氏名, B:ふりがな, C:日介番号, D:勤務先法人名称, E:勤務先名称,
                # F:種別サービス, G:種別サービス（手動）, H:グループ, I:通し番号, J:受講生番号, K:クラス, L:無効
                student_data = {
                    "student_id": row[2].strip() if row[2] else "",  # C列: 日介番号
                    "furigana": row[1].strip() if row[1] else "",  # B列: ふりがな
                    "name": row[0].strip() if row[0] else "",  # A列: 氏名
                    "group": row[7].strip() if row[7] else "未分類",  # H列: グループ
                    "status": "inactive" if is_inactive else "active",  # L列に基づく
                    "company": row[3].strip() if row[3] else "",  # D列: 勤務先法人名称
                    "office": row[4].strip() if row[4] else "",  # E列: 勤務先名称
                    # G列優先、空ならF列（手動→自動フォールバック）
                    "service_type": (
                        row[6].strip() if row[6] else (row[5].strip() if row[5] else "")
                    ),
                    "serial_number": (
                        int(row[8]) if row[8] and row[8].isdigit() else 0
                    ),  # I列: 通し番号
                    "student_number": (
                        row[9].strip() if row[9] else ""
                    ),  # J列: 受講生番号
                    "class_name": row[10].strip() if row[10] else "",  # K列: クラス
                }

                # Validate required fields
                if not student_data["student_id"]:
                    logger.warning(
                        f"Skipping row {row_index}: missing student_id (日介番号)"
                    )
                    continue

                students.append(student_data)

            logger.info(
                f"Successfully read {len(students)} student records from spreadsheet"
            )
            return students

        except Exception as e:
            logger.error(
                f"Error reading student data from spreadsheet: {e}", exc_info=True
            )
            # Return empty list on error (fail-open strategy)
            return []

    def get_stats(self, spreadsheet_id: str, sheet_name: str = "Sheet1") -> dict:
        """
        Get statistics from spreadsheet

        NOTE: Currently unused but preserved for future monitoring/operations API

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Sheet name (default: "シート1")

        Returns:
            Dictionary with statistics
        """
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range=f"{sheet_name}!A:A")
                .execute()
            )

            values = result.get("values", [])

            # Subtract 1 for header row
            total_records = len(values) - 1 if len(values) > 0 else 0

            return {"total_records": total_records, "sheet_name": sheet_name}

        except Exception as e:
            logger.error(f"Error getting spreadsheet stats: {e}", exc_info=True)
            return {"total_records": 0, "sheet_name": sheet_name, "error": str(e)}
