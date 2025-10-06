"""
Playwright Automation Engine for Carewell Web Service
"""
import logging
import os
import time
from typing import Optional
from playwright.sync_api import sync_playwright, Browser, Page, Frame
from google.cloud import secretmanager

logger = logging.getLogger(__name__)


class CarewellSelectors:
    """CSS selectors and URLs for Carewell web service"""
    # URLs
    BASE_URL = "https://jaccw-carewel.study.jp/"

    # Login form selectors
    LOGIN_USER_ID = 'input[name="ctl00$masterMain$txtUserID"]'
    LOGIN_PASSWORD = 'input[name="ctl00$masterMain$txtPassword"]'
    LOGIN_SUBMIT = 'input[name="ctl00$masterMain$btnSubmit"]'

    # Navigation selectors
    CLASS_MANAGEMENT = 'a[href="course/default.aspx"]'

    # Submission list selectors
    SUBMISSION_TABLE = 'table#ctl00_masterMain_gvwMain'
    SUBMISSION_ROW = 'tr.standard_table_tr'

    # Frame names
    FRAME_LIST = 'list'


class CarewellConfig:
    """Configuration constants for Carewell automation"""
    # Timeouts (in milliseconds)
    PAGE_TIMEOUT = 180000  # 3 minutes for slow network
    NAVIGATION_WAIT = 2000  # Wait after navigation actions
    FRAME_LOAD_WAIT = 3000  # Wait for frames to load
    DATA_LOAD_WAIT = 5000   # Wait for data-heavy pages

    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY = 1000


class PlaywrightAutomationEngine:
    """
    Handles browser automation for Carewell web service
    """

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None
        self._credentials = None

    def _get_credentials(self) -> tuple[str, str]:
        """
        Retrieve credentials from Secret Manager (cached)

        Returns:
            Tuple of (user_id, password)
        """
        if self._credentials:
            return self._credentials

        project_id = os.getenv('GCP_PROJECT', 'carewell-automation')
        client = secretmanager.SecretManagerServiceClient()

        user_id_name = f"projects/{project_id}/secrets/carewell-user-id/versions/latest"
        password_name = f"projects/{project_id}/secrets/carewell-password/versions/latest"

        user_id_response = client.access_secret_version(request={"name": user_id_name})
        password_response = client.access_secret_version(request={"name": password_name})

        user_id = user_id_response.payload.data.decode('UTF-8')
        password = password_response.payload.data.decode('UTF-8')

        if not user_id or not password:
            raise ValueError("Failed to retrieve credentials from Secret Manager")

        self._credentials = (user_id, password)
        return self._credentials

    def _launch_browser(self) -> Browser:
        """Launch Chromium browser in headless mode"""
        logger.info("Launching Chromium browser")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        return self.browser

    def _find_frame_with_selector(self, selector: str, timeout_ms: int = 5000) -> Optional[Frame]:
        """
        Find frame containing a specific selector

        Args:
            selector: CSS selector or text selector
            timeout_ms: Maximum time to wait for selector

        Returns:
            Frame object if found, None otherwise
        """
        for frame in self.page.frames:
            try:
                if frame.locator(selector).count() > 0:
                    logger.debug(f"Found selector '{selector}' in frame: {frame.name or frame.url}")
                    return frame
            except Exception as e:
                logger.debug(f"Could not check frame {frame.name}: {e}")
                continue
        return None

    def _click_in_any_frame(self, selector: str, description: str = None) -> bool:
        """
        Click element in any frame that contains it

        Args:
            selector: CSS selector or text selector
            description: Human-readable description for logging

        Returns:
            True if clicked successfully, False otherwise
        """
        desc = description or selector
        logger.info(f"Clicking '{desc}'")

        frame = self._find_frame_with_selector(selector)
        if frame:
            frame.click(selector)
            logger.info(f"Clicked '{desc}' in frame: {frame.name or 'unnamed'}")
            return True

        logger.warning(f"Could not find '{desc}' in any frame")
        return False

    def _wait_for_navigation(self, wait_ms: int = CarewellConfig.NAVIGATION_WAIT):
        """Wait for navigation to complete"""
        time.sleep(wait_ms / 1000)

    def _login(self) -> Page:
        """
        Login to Carewell web service

        Returns:
            Page object after successful login
        """
        user_id, password = self._get_credentials()

        logger.info(f"Navigating to {CarewellSelectors.BASE_URL}")
        context = self.browser.new_context()
        self.page = context.new_page()
        self.page.set_default_timeout(CarewellConfig.PAGE_TIMEOUT)

        self.page.goto(CarewellSelectors.BASE_URL, wait_until="networkidle")
        logger.info(f"Page loaded: {self.page.title()}")

        # Wait for frames to load
        self._wait_for_navigation(2000)

        # Find login frame
        login_frame = self._find_frame_with_selector(CarewellSelectors.LOGIN_USER_ID)
        if not login_frame:
            logger.warning("Login form not found in frames, using main page")
            login_frame = self.page

        # Fill and submit login form
        logger.info("Submitting login credentials")
        login_frame.fill(CarewellSelectors.LOGIN_USER_ID, user_id)
        login_frame.fill(CarewellSelectors.LOGIN_PASSWORD, password)
        login_frame.click(CarewellSelectors.LOGIN_SUBMIT)

        # Wait for post-login navigation
        self.page.wait_for_load_state("networkidle")
        self._wait_for_navigation(CarewellConfig.FRAME_LOAD_WAIT)
        self.page.wait_for_load_state("networkidle")

        logger.info(f"Login successful: {self.page.url}")
        return self.page

    def _navigate_to_class_list(self):
        """Navigate to class list page"""
        logger.info("Navigating to class management")
        self._wait_for_navigation(CarewellConfig.FRAME_LOAD_WAIT)

        # Click "クラス管理" button (image-based)
        self.page.click(CarewellSelectors.CLASS_MANAGEMENT)
        self._wait_for_navigation()

        # Click "教科クラス一覧"
        if not self._click_in_any_frame('text="教科クラス一覧"', '教科クラス一覧'):
            raise Exception("Could not navigate to '教科クラス一覧'")

        self._wait_for_navigation(CarewellConfig.DATA_LOAD_WAIT)

    def _select_class(self, class_name: str):
        """
        Select a specific class

        Args:
            class_name: Name of the class to select
        """
        logger.info(f"Selecting class: {class_name}")

        if not self._click_in_any_frame(f'text="{class_name}"', f'class "{class_name}"'):
            raise Exception(f"Could not find class: {class_name}")

        self._wait_for_navigation()

    def _navigate_to_report_grading(self):
        """Navigate to report grading section"""
        if not self._click_in_any_frame('text="レポート採点"', 'レポート採点'):
            raise Exception("Could not navigate to 'レポート採点'")

        self._wait_for_navigation()

    def _select_task(self, task_name: str):
        """
        Select a specific task

        Args:
            task_name: Name of the task to select
        """
        logger.info(f"Selecting task: {task_name}")

        if not self._click_in_any_frame(f'text="{task_name}"', f'task "{task_name}"'):
            raise Exception(f"Could not find task: {task_name}")

        self._wait_for_navigation()

    def _show_all_submissions(self):
        """Click '全て' tab to show all submissions"""
        if not self._click_in_any_frame('text="全て"', '全て tab'):
            raise Exception("Could not click '全て' tab")

        self._wait_for_navigation(CarewellConfig.FRAME_LOAD_WAIT)

    def navigate_to_task(self, class_name: str, task_name: str) -> Page:
        """
        Navigate to specific task page

        Args:
            class_name: Class name (e.g., "令和7年度 デジタル中核人材養成研修 №01")
            task_name: Task name (e.g., "課題①業務分析　※～11/3〆切")

        Returns:
            Page object at the task page
        """
        # Launch browser and login
        self._launch_browser()
        self._login()

        # Navigate through the pages
        self._navigate_to_class_list()
        self._select_class(class_name)
        self._navigate_to_report_grading()
        self._select_task(task_name)
        self._show_all_submissions()

        logger.info("Successfully navigated to task page")
        return self.page

    def get_submission_list(self) -> list[dict]:
        """
        Extract submission file information from task page

        Returns:
            List of submission dictionaries with metadata
        """
        logger.info("Extracting submission list from page")

        # Log all frames
        logger.info(f"Total frames: {len(self.page.frames)}")
        for i, frame in enumerate(self.page.frames):
            logger.info(f"Frame {i}: name={frame.name or 'unnamed'}, url={frame.url}")

        # Find the frame containing submission list (should be 'list' frame)
        list_frame = None
        for frame in self.page.frames:
            if frame.name == CarewellSelectors.FRAME_LIST:
                list_frame = frame
                logger.info(f"Using frame: {frame.name}")
                break

        if not list_frame:
            logger.warning("'list' frame not found, using main page")
            list_frame = self.page

        # Get submission table
        try:
            submission_table = list_frame.locator(CarewellSelectors.SUBMISSION_TABLE)

            if submission_table.count() == 0:
                logger.warning(f"Submission table '{CarewellSelectors.SUBMISSION_TABLE}' not found")
                return []

            logger.info("Found submission table")

            # Get all rows from the table (skip header row)
            rows = submission_table.locator("tr").all()
            logger.info(f"Found {len(rows)} rows in submission table")

            # Log first few rows for structure analysis
            for i, row in enumerate(rows[:3]):
                try:
                    row_html = row.inner_html()[:500]
                    row_text = row.text_content()[:200]
                    logger.info(f"Row {i} text: {row_text}")
                    logger.info(f"Row {i} HTML: {row_html}")
                except:
                    pass

            # Parse each row to extract submission data
            submissions = []
            for i, row in enumerate(rows):
                try:
                    # Skip header row (first row)
                    if i == 0:
                        continue

                    # Get all cells in the row
                    cells = row.locator("td").all()
                    logger.info(f"Row {i}: {len(cells)} cells")

                    # Extract data from cells
                    # TODO: Determine cell structure
                    # Typically: student name, submission date, status, download link, etc.

                except Exception as re:
                    logger.debug(f"Could not parse row {i}: {re}")

            logger.info(f"Extracted {len(submissions)} submissions")

        except Exception as e:
            logger.error(f"Error extracting submissions: {e}", exc_info=True)

        return submissions

    def close(self):
        """Close browser and cleanup resources"""
        logger.info("Closing browser")
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
