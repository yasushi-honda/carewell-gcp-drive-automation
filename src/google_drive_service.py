"""
Google Drive Service for uploading files
"""
import logging
from typing import Optional
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

logger = logging.getLogger(__name__)


class GoogleDriveService:
    """
    Handles Google Drive file operations
    """

    def __init__(self):
        """Initialize Google Drive API client with service account credentials"""
        self.service = None
        self._initialize_service()

    def _initialize_service(self):
        """
        Initialize Google Drive API service with domain-wide delegation

        Uses Application Default Credentials (ADC) with subject delegation to:
        - Impersonate user account (system@jaccw.or.jp)
        - Upload files to My Drive folders
        """
        try:
            # Use default credentials (service account from Cloud Run)
            from google.auth import default
            import os

            credentials, project = default(scopes=['https://www.googleapis.com/auth/drive.file'])

            # Apply domain-wide delegation to impersonate user
            # This allows the service account to act as system@jaccw.or.jp
            delegated_user = os.environ.get('DRIVE_DELEGATED_USER', 'system@jaccw.or.jp')

            if hasattr(credentials, 'with_subject'):
                credentials = credentials.with_subject(delegated_user)
                logger.info(f"Using domain-wide delegation with subject: {delegated_user}")
            else:
                logger.warning("Credentials do not support domain-wide delegation, using default")

            self.service = build('drive', 'v3', credentials=credentials)
            logger.info("Google Drive service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {e}", exc_info=True)
            raise

    def upload_file(self, file_path: str, filename: str, folder_id: str) -> str:
        """
        Upload a file to Google Drive

        Args:
            file_path: Local path to the file to upload
            filename: Name for the file in Google Drive
            folder_id: Google Drive folder ID to upload to

        Returns:
            File ID of the uploaded file

        Raises:
            Exception if upload fails
        """
        try:
            logger.info(f"Uploading file to Google Drive: {filename}")

            # File metadata
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }

            # Detect MIME type based on file extension
            mime_type = self._get_mime_type(filename)

            # Create media upload
            media = MediaFileUpload(
                file_path,
                mimetype=mime_type,
                resumable=True
            )

            # Upload file
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink',
                supportsAllDrives=True
            ).execute()

            file_id = file.get('id')
            web_link = file.get('webViewLink')

            logger.info(f"File uploaded successfully: {filename} (ID: {file_id})")
            logger.info(f"Web view link: {web_link}")

            return file_id

        except Exception as e:
            logger.error(f"Failed to upload file {filename}: {e}", exc_info=True)
            raise

    def _get_mime_type(self, filename: str) -> str:
        """
        Determine MIME type from filename

        Args:
            filename: Name of the file

        Returns:
            MIME type string
        """
        import mimetypes

        mime_type, _ = mimetypes.guess_type(filename)

        if mime_type:
            return mime_type

        # Default fallback
        return 'application/octet-stream'

    def check_folder_access(self, folder_id: str) -> bool:
        """
        Check if service account has access to the folder

        Args:
            folder_id: Google Drive folder ID

        Returns:
            True if accessible, False otherwise
        """
        try:
            folder = self.service.files().get(
                fileId=folder_id,
                fields='id, name'
            ).execute()

            logger.info(f"Successfully accessed folder: {folder.get('name')} (ID: {folder_id})")
            return True

        except Exception as e:
            logger.error(f"Cannot access folder {folder_id}: {e}")
            return False
