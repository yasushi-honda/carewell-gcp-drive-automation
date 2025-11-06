"""
Playwright Automation Engine for Carewell Web Service
"""

import logging
import os
import re
import time
from typing import Optional

from google.cloud import secretmanager
from playwright.sync_api import Browser, Frame, Page, sync_playwright

logger = logging.getLogger(__name__)


def _format_log_context(class_name: Optional[str], task_id: Optional[str]) -> str:
    """
    Format class/task context for log identification.

    Args:
        class_name: Class name (e.g., "令和7年度 デジタル中核人材養成研修 №01")
        task_id: Task ID (e.g., "課題①")

    Returns:
        Formatted context string (e.g., "[carewell-№01-課題①]")
    """
    if not class_name or not task_id:
        return ""

    # Extract class number from class_name (e.g., "№01" from "令和7年度 デジタル中核人材養成研修 №01")
    import re

    class_match = re.search(r"№(\d+)", class_name)
    class_num = class_match.group(1) if class_match else "XX"

    # Format: [carewell-№01-課題①]
    return f"[carewell-№{class_num}-{task_id}]"


def parse_student_info(student_name_with_id: str) -> tuple[str, str]:
    """
    Parse student name and ID from format: "森平　直樹 <N9902913>"

    Args:
        student_name_with_id: Student name with ID in format "Name <ID>"

    Returns:
        Tuple of (student_name, student_id)
        Example: ("森平　直樹", "N9902913")
    """
    match = re.match(r"^(.+?)\s*<(.+?)>$", student_name_with_id.strip())
    if match:
        student_name = match.group(1).strip()
        student_id = match.group(2).strip()
        return student_name, student_id
    else:
        # If format doesn't match, return original as name and empty ID
        logger.warning(f"Could not parse student ID from: {student_name_with_id}")
        return student_name_with_id.strip(), ""


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
    SUBMISSION_TABLE = "table#ctl00_masterMain_gvwMain"
    SUBMISSION_ROW = "tr.standard_table_tr"

    # Pagination selectors
    PAGINATION_SELECT = 'select[name="ctl00$masterMain$dpgMain$dpgMain$ctl00$ddlPage"]'

    # Frame names
    FRAME_LIST = "list"


class CarewellConfig:
    """Configuration constants for Carewell automation"""

    # Timeouts (in milliseconds)
    PAGE_TIMEOUT = 180000  # 3 minutes for slow network
    NAVIGATION_WAIT = 2000  # Wait after navigation actions
    FRAME_LOAD_WAIT = 15000  # Wait for frames to load (increased from 3000ms for large datasets like №01 with 180+ submissions)
    DATA_LOAD_WAIT = 10000  # Wait for data-heavy pages (increased from 5000ms to handle concurrent job load)

    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY = 1000


class ContextLoggerAdapter(logging.LoggerAdapter):
    """
    Custom LoggerAdapter that prepends context to all log messages.
    This helps identify logs from different class/task executions.
    """

    def process(self, msg, kwargs):
        """Prepend context to log message"""
        context = self.extra.get("context", "")
        if context:
            # Prepend context to message
            return f"{context} {msg}", kwargs
        return msg, kwargs


class PlaywrightAutomationEngine:
    """
    Handles browser automation for Carewell web service
    """

    def __init__(self, class_name: Optional[str] = None, task_id: Optional[str] = None):
        self.playwright = None
        self.browser = None
        self.page = None
        self._credentials = None

        # Set up context-aware logger
        self.class_name = class_name
        self.task_id = task_id
        log_context = _format_log_context(class_name, task_id)
        # Use ContextLoggerAdapter to prepend context to all log messages
        self.logger = ContextLoggerAdapter(logger, {"context": log_context})

    def _get_credentials(self) -> tuple[str, str]:
        """
        Retrieve credentials from Secret Manager (cached)

        Returns:
            Tuple of (user_id, password)
        """
        if self._credentials:
            return self._credentials

        project_id = os.getenv("GCP_PROJECT", "carewell-automation")
        client = secretmanager.SecretManagerServiceClient()

        user_id_name = f"projects/{project_id}/secrets/carewell-user-id/versions/latest"
        password_name = (
            f"projects/{project_id}/secrets/carewell-password/versions/latest"
        )

        user_id_response = client.access_secret_version(request={"name": user_id_name})
        password_response = client.access_secret_version(
            request={"name": password_name}
        )

        user_id = user_id_response.payload.data.decode("UTF-8")
        password = password_response.payload.data.decode("UTF-8")

        if not user_id or not password:
            raise ValueError("Failed to retrieve credentials from Secret Manager")

        self._credentials = (user_id, password)
        return self._credentials

    def _launch_browser(self) -> Browser:
        """Launch Chromium browser in headless mode"""
        self.logger.info("Launching Chromium browser")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        return self.browser

    def _find_frame_with_selector(
        self, selector: str, timeout_ms: int = 5000
    ) -> Optional[Frame]:
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
                # Use wait_for_selector instead of immediate count check
                # This allows dynamic content to load before checking
                frame.wait_for_selector(selector, timeout=timeout_ms, state="attached")
                self.logger.debug(
                    f"Found selector '{selector}' in frame: {frame.name or frame.url}"
                )
                return frame
            except Exception as e:
                self.logger.debug(f"Could not find selector in frame {frame.name}: {e}")
                continue
        return None

    def _click_in_any_frame(
        self, selector: str, description: str | None = None, timeout_ms: int = 10000
    ) -> bool:
        """
        Click element in any frame that contains it

        Args:
            selector: CSS selector or text selector
            description: Human-readable description for logging
            timeout_ms: Maximum time to wait for selector (default: 10 seconds)

        Returns:
            True if clicked successfully, False otherwise
        """
        desc = description or selector
        self.logger.info(f"Clicking '{desc}'")

        frame = self._find_frame_with_selector(selector, timeout_ms=timeout_ms)
        if frame:
            frame.click(selector)
            self.logger.info(f"Clicked '{desc}' in frame: {frame.name or 'unnamed'}")
            return True

        self.logger.warning(f"Could not find '{desc}' in any frame")
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

        self.logger.info(f"Navigating to {CarewellSelectors.BASE_URL}")
        context = self.browser.new_context()
        self.page = context.new_page()
        self.page.set_default_timeout(CarewellConfig.PAGE_TIMEOUT)

        self.page.goto(CarewellSelectors.BASE_URL, wait_until="networkidle")
        self.logger.info(f"Page loaded: {self.page.title()}")

        # Wait for frames to load
        self._wait_for_navigation(2000)

        # Find login frame
        login_frame = self._find_frame_with_selector(CarewellSelectors.LOGIN_USER_ID)
        if not login_frame:
            self.logger.warning("Login form not found in frames, using main page")
            login_frame = self.page

        # Fill and submit login form
        self.logger.info("Submitting login credentials")
        login_frame.fill(CarewellSelectors.LOGIN_USER_ID, user_id)
        login_frame.fill(CarewellSelectors.LOGIN_PASSWORD, password)
        login_frame.click(CarewellSelectors.LOGIN_SUBMIT)

        # Wait for post-login navigation
        self.page.wait_for_load_state("networkidle")
        self._wait_for_navigation(CarewellConfig.FRAME_LOAD_WAIT)
        self.page.wait_for_load_state("networkidle")

        self.logger.info(f"Login successful: {self.page.url}")
        return self.page

    def _navigate_to_class_list(self):
        """Navigate to class list page"""
        self.logger.info("Navigating to class management")
        self._wait_for_navigation(CarewellConfig.FRAME_LOAD_WAIT)

        # Click "クラス管理" button (image-based)
        self.page.click(CarewellSelectors.CLASS_MANAGEMENT)
        self._wait_for_navigation()

        # Click "教科クラス一覧"
        if not self._click_in_any_frame('text="教科クラス一覧"', "教科クラス一覧"):
            raise Exception("Could not navigate to '教科クラス一覧'")

        self._wait_for_navigation(CarewellConfig.DATA_LOAD_WAIT)

    def _select_class(self, class_name: str) -> bool:
        """
        Select a specific class

        Args:
            class_name: Name of the class to select

        Returns:
            True if class found and selected, False if not found
        """
        self.logger.info(f"Selecting class: {class_name}")

        # Increase timeout to 10 seconds for class selection
        # (concurrent jobs may cause slower page load)
        if not self._click_in_any_frame(
            f'text="{class_name}"', f'class "{class_name}"'
        ):
            self.logger.info(f"Class not found (likely not yet created): {class_name}")
            return False

        self._wait_for_navigation()
        return True

    def _navigate_to_report_grading(self):
        """Navigate to report grading section"""
        if not self._click_in_any_frame('text="レポート採点"', "レポート採点"):
            raise Exception("Could not navigate to 'レポート採点'")

        self._wait_for_navigation()

    def _select_task(self, task_pattern: str) -> bool:
        """
        Select a specific task using partial text match

        Args:
            task_pattern: Pattern to match task name (e.g., "課題①")

        Returns:
            True if task found and selected, False if not found
        """
        self.logger.info(f"Selecting task with pattern: {task_pattern}")

        # Use text= selector without quotes for partial match
        if not self._click_in_any_frame(
            f"text={task_pattern}", f'task "{task_pattern}"'
        ):
            self.logger.info(f"Task not found (likely not yet created): {task_pattern}")
            return False

        self._wait_for_navigation()
        return True

    def _show_all_submissions(self):
        """Click '全て' tab to show all submissions"""
        if not self._click_in_any_frame('text="全て"', "全て tab"):
            raise Exception("Could not click '全て' tab")

        self._wait_for_navigation(CarewellConfig.FRAME_LOAD_WAIT)

    def navigate_to_task(self, class_name: str, task_pattern: str):
        """
        Navigate to specific task page using partial text match

        Args:
            class_name: Class name (e.g., "令和7年度 デジタル中核人材養成研修 №01")
            task_pattern: Task pattern for partial match (e.g., "課題①")

        Returns:
            Page object at the task page, or None if class/task not found
        """
        # Launch browser and login
        self._launch_browser()
        self._login()

        # Navigate through the pages
        self._navigate_to_class_list()

        # Check if class exists
        if not self._select_class(class_name):
            self.logger.info(f"Class not found, skipping: {class_name}")
            return None

        self._navigate_to_report_grading()

        # Check if task exists
        if not self._select_task(task_pattern):
            self.logger.info(f"Task not found, skipping: {task_pattern}")
            return None

        self._show_all_submissions()

        self.logger.info("Successfully navigated to task page")
        return self.page

    def get_submission_list(
        self,
        class_name: Optional[str] = None,
        task_id: Optional[str] = None,
        firestore_service=None,
    ) -> dict:
        """
        Extract submission file information from all pages

        Args:
            class_name: Class name for early duplicate check (optional)
            task_id: Task ID for early duplicate check (optional)
            firestore_service: FirestoreService instance for early duplicate check (optional)

        Returns:
            Dictionary containing:
            - submissions: List of submission dictionaries with metadata and download links
            - total_count: Total number of submissions (from UI counter)
            - verified: Whether the count matches the extracted submissions
        """
        self.logger.info("Extracting submission list from all pages")

        # Find the list frame
        # Frame may still be reloading after "全て" tab click, so retry
        list_frame = None
        max_frame_retries = 5

        for retry in range(max_frame_retries):
            for frame in self.page.frames:
                if frame.name == CarewellSelectors.FRAME_LIST:
                    # Verify frame is not detached
                    try:
                        _ = frame.url  # This will raise if frame is detached
                        list_frame = frame
                        break
                    except Exception:
                        self.logger.debug(
                            f"Frame found but detached, retry {retry + 1}/{max_frame_retries}"
                        )
                        continue

            if list_frame:
                self.logger.info(
                    f"✓ Frame '{CarewellSelectors.FRAME_LIST}' found for total count extraction"
                )
                break

            if retry < max_frame_retries - 1:
                self.logger.warning(
                    f"'list' frame not found, retrying ({retry + 1}/{max_frame_retries})..."
                )
                time.sleep(2)  # Wait 2 seconds before retry

        if not list_frame:
            self.logger.warning("'list' frame not found after retries, using main page")
            list_frame = self.page

        # Extract total count from UI (must be in list frame after "全て" is selected)
        total_count = None

        try:
            count_selector = "#ctl00_masterMain_dpgMain_dpgMain_ctl00_lblDataCount"

            # Wait for the element to appear in list frame (with timeout)
            list_frame.wait_for_selector(count_selector, timeout=10000, state="visible")

            count_elem = list_frame.locator(count_selector)
            count_text = count_elem.text_content()

            # Parse "19件中 1 - 19件目表示" to extract total count (19)
            if count_text:
                match = re.match(r"(\d+)件中", count_text.strip())
                if match:
                    total_count = int(match.group(1))
                    self.logger.info(f"✓ Total submission count from UI: {total_count}")
                else:
                    self.logger.warning(
                        f"Could not parse total count from: {count_text}"
                    )

        except Exception as e:
            self.logger.warning(f"Could not extract total count from UI: {e}")

        # Collect submissions from all pages
        all_submissions = []
        current_page = 1

        try:
            # Loop through all pages
            while True:
                self.logger.info(f"Processing page {current_page}")

                # Refresh frame reference for each page to handle pagination
                # This ensures we always have the latest frame object after page transitions
                # For page 1, frame may still be reloading after "全て" tab click, so retry
                list_frame = None
                max_frame_retries = 5 if current_page == 1 else 3

                for retry in range(max_frame_retries):
                    for frame in self.page.frames:
                        if frame.name == CarewellSelectors.FRAME_LIST:
                            # Verify frame is not detached
                            try:
                                _ = frame.url  # This will raise if frame is detached
                                list_frame = frame
                                break
                            except Exception:
                                self.logger.debug(
                                    f"Frame found but detached, retry {retry + 1}/{max_frame_retries}"
                                )
                                continue

                    if list_frame:
                        self.logger.info(
                            f"✓ Frame '{CarewellSelectors.FRAME_LIST}' found (page {current_page})"
                        )
                        break

                    if retry < max_frame_retries - 1:
                        self.logger.warning(
                            f"'list' frame not found, retrying ({retry + 1}/{max_frame_retries})..."
                        )
                        time.sleep(2)  # Wait 2 seconds before retry

                if not list_frame:
                    self.logger.warning(
                        "'list' frame not found after retries, using main page"
                    )
                    list_frame = self.page

                # Save current page URL for navigation back from detail pages
                list_url = list_frame.url
                self.logger.debug(
                    f"Current list URL for page {current_page}: {list_url}"
                )

                # Wait for table to be fully rendered after frame reload or page transition
                if current_page == 1:
                    # Frame reload after "全て" tab click
                    # Extended wait time to 15 seconds to ensure table rendering
                    # completes after frame reload (increased from 10s due to timeout issues)
                    self.logger.info(
                        "Waiting for table to render after frame reload (15 seconds)..."
                    )
                    time.sleep(15)
                elif current_page > 1:
                    # Page transition via ASP.NET __doPostBack
                    # Extended wait time to 15 seconds to ensure table rendering
                    # completes after page transition (increased from 10s due to timeout issues)
                    self.logger.info(
                        "Waiting for table to render after page navigation (15 seconds)..."
                    )
                    time.sleep(15)

                # Phase 3.5: Refresh frame reference after sleep
                # Frame may become detached/stale during long sleep periods
                temp_list_frame = None
                for frame in self.page.frames:
                    if frame.name == CarewellSelectors.FRAME_LIST:
                        temp_list_frame = frame
                        break

                if not temp_list_frame:
                    self.logger.warning(
                        "'list' frame not found after sleep, using main page"
                    )
                    list_frame = self.page
                else:
                    list_frame = temp_list_frame
                    self.logger.info(
                        f"✓ Frame refreshed after sleep (page {current_page})"
                    )

                # Phase 4: Step-by-step waiting strategy to identify exact failure point
                # Wait for data to load with detailed logging at each step
                self.logger.info("Waiting for submission table (step-by-step)...")

                try:
                    # Step 1: Wait for table element itself
                    self.logger.info(
                        "Step 1: Waiting for table element (#ctl00_masterMain_gvwMain)..."
                    )
                    list_frame.wait_for_selector(
                        "#ctl00_masterMain_gvwMain", timeout=60000
                    )
                    self.logger.info("✓ Step 1 complete: Table element found")

                    # Step 2: Wait for tbody within table
                    self.logger.info("Step 2: Waiting for tbody element...")
                    list_frame.wait_for_selector(
                        "#ctl00_masterMain_gvwMain tbody", timeout=60000
                    )
                    self.logger.info("✓ Step 2 complete: Table tbody found")

                    # Step 3: Wait for table rows
                    self.logger.info(
                        "Step 3: Waiting for table rows (tr.standard_grid_item)..."
                    )
                    list_frame.wait_for_selector(
                        "#ctl00_masterMain_gvwMain tbody tr.standard_grid_item",
                        timeout=60000,
                    )
                    self.logger.info("✓ Step 3 complete: Table rows found")

                except Exception as wait_error:
                    self.logger.error(
                        f"Table wait failed at one of the steps: {wait_error}"
                    )
                    self.logger.error(
                        f"Frame URL: {list_frame.url if list_frame else 'N/A'}"
                    )
                    self.logger.error(
                        f"Frame name: {list_frame.name if list_frame else 'N/A'}"
                    )
                    raise

                # Wait for table links to become fully interactive
                # After ASP.NET __doPostBack page transition, JavaScript event handlers
                # need time to initialize before links become clickable
                self.logger.info(
                    "Waiting for table links to become fully interactive (10 seconds)..."
                )
                time.sleep(10)
                self.logger.info("✓ Table links should now be interactive")

                # First pass: Extract all basic submission info from current page
                rows = list_frame.locator(
                    "#ctl00_masterMain_gvwMain tbody tr.standard_grid_item"
                ).all()
                self.logger.info(
                    f"Found {len(rows)} submission rows on page {current_page}"
                )

                # Wait for individual row links to become fully interactive
                # After table rendering, JavaScript event handlers need additional time
                # to attach to individual row links (especially for rows later in the table)
                # Extended from 5s to 15s based on production testing results
                # (Phase 1: Timeout resolution - Nov 2025)
                self.logger.info(
                    "Waiting for individual row links to become fully interactive (15 seconds)..."
                )
                time.sleep(15)
                self.logger.info("✓ Individual row links should now be interactive")

                submission_basics = []
                for i, row in enumerate(rows):
                    try:
                        cells = row.locator("td").all()
                        if len(cells) < 6:
                            self.logger.warning(
                                f"Row {i} has only {len(cells)} cells, skipping"
                            )
                            continue

                        # Extract all data while row is still valid
                        student_link_elem = cells[0].locator("a").first
                        student_name_with_id = student_link_elem.text_content()
                        detail_url = student_link_elem.get_attribute("href")
                        log_no = cells[1].text_content().strip()
                        score = cells[2].text_content().strip()
                        pass_status = cells[3].text_content().strip()
                        status = cells[4].text_content().strip()
                        submit_date = cells[5].text_content().strip()

                        # Parse student name and ID
                        student_name, student_id = parse_student_info(
                            student_name_with_id
                        )

                        submission_basics.append(
                            {
                                "student_name": student_name,
                                "student_id": student_id,
                                "detail_url": detail_url,
                                "log_no": log_no,
                                "score": score,
                                "pass_status": pass_status,
                                "status": status,
                                "submit_date": submit_date,
                            }
                        )

                    except Exception as row_error:
                        self.logger.error(
                            f"Could not parse row {i}: {row_error}", exc_info=True
                        )

                self.logger.info(
                    f"Extracted basic info for {len(submission_basics)} submissions on page {current_page}"
                )

                # Early duplicate check: Mark duplicates before download link retrieval
                if firestore_service and class_name and task_id:
                    self.logger.info(
                        f"Performing early duplicate check for {len(submission_basics)} submissions"
                    )

                    for basic in submission_basics:
                        # Check if already uploaded (by student_id + submit_date)
                        try:
                            existing_upload = firestore_service.check_already_uploaded_by_student_date(
                                class_name,
                                task_id,
                                basic.get("student_id", ""),
                                basic.get("submit_date", ""),
                            )

                            if existing_upload:
                                # Mark as duplicate
                                basic["is_duplicate"] = True
                                basic["skip_reason"] = "already_uploaded"
                                self.logger.info(
                                    f"Duplicate detected (early check): {basic['student_name']} (student_id={basic.get('student_id')}, submit_date={basic.get('submit_date')})"
                                )
                            else:
                                basic["is_duplicate"] = False
                        except Exception as e:
                            self.logger.warning(
                                f"Early duplicate check failed for {basic['student_name']}: {e}"
                            )
                            # Fail-open: if check fails, treat as non-duplicate
                            basic["is_duplicate"] = False
                else:
                    # No Firestore service provided, mark all as non-duplicate
                    self.logger.info(
                        "No Firestore service provided, skipping early duplicate check"
                    )
                    for basic in submission_basics:
                        basic["is_duplicate"] = False

                # Second pass: Get download links for non-duplicate submissions only
                for basic in submission_basics:
                    # Skip download link retrieval for duplicates
                    if basic.get("is_duplicate", False):
                        # Add to submissions list with minimal info (no download link needed)
                        submission = {
                            **basic,
                            "download_url": None,
                            "filename": None,
                        }
                        all_submissions.append(submission)
                        self.logger.info(
                            f"Skipped download link retrieval (duplicate): {basic['student_name']}"
                        )
                        continue

                    # Get download link for non-duplicates
                    try:
                        self.logger.info(
                            f"Getting download link for: {basic['student_name']}"
                        )

                        # Wait before each detail link click to reduce server load
                        # and prevent rate limiting
                        time.sleep(2)

                        # Phase 2: Retry logic for detail page access
                        # (Individual file detail page timeouts require multiple retry attempts)
                        max_retries = 3
                        download_info = None
                        last_error = None

                        for retry_attempt in range(max_retries):
                            try:
                                if retry_attempt > 0:
                                    self.logger.info(
                                        f"Retry {retry_attempt}/{max_retries-1} for {basic['student_name']}"
                                    )
                                    # Wait 5 seconds between retries to reduce server load
                                    time.sleep(5)

                                download_info = self._get_download_link(
                                    basic["detail_url"], list_url, current_page
                                )

                                # If successful (got download_info with non-None values), break
                                if download_info and download_info.get("url"):
                                    break

                                # If got None/empty result, treat as temporary failure
                                last_error = "Empty download info returned"

                            except Exception as retry_error:
                                last_error = str(retry_error)
                                self.logger.warning(
                                    f"Attempt {retry_attempt + 1}/{max_retries} failed for {basic['student_name']}: {retry_error}"
                                )
                                # Don't break, continue to next retry

                        # If all retries failed, log and use last result
                        if not download_info or not download_info.get("url"):
                            if last_error:
                                self.logger.error(
                                    f"Failed after {max_retries} retries for {basic['student_name']}: {last_error}"
                                )
                            # Ensure download_info is a dict (even if empty)
                            if not download_info:
                                download_info = {"url": None, "filename": None}

                        # Refresh frame reference after download link retrieval
                        # (frame becomes stale after list_frame.goto() in _get_download_link)
                        temp_list_frame = None
                        for frame in self.page.frames:
                            if frame.name == CarewellSelectors.FRAME_LIST:
                                temp_list_frame = frame
                                break

                        if not temp_list_frame:
                            self.logger.warning(
                                "'list' frame not found after download link retrieval"
                            )
                        else:
                            list_frame = temp_list_frame
                            self.logger.info(
                                f"✓ Frame refreshed after {basic['student_name']}"
                            )

                        submission = {
                            **basic,  # Includes detail_url from basic info
                            "download_url": download_info.get("url"),
                            "filename": download_info.get("filename"),
                        }

                        all_submissions.append(submission)
                        self.logger.info(
                            f"Added: {basic['student_name']} - {download_info.get('filename')}"
                        )

                    except Exception as e:
                        self.logger.error(
                            f"Error processing {basic['student_name']}: {e}",
                            exc_info=True,
                        )

                # Refresh frame reference before pagination check
                # (frame may be detached after 100 page navigations in download link loop)
                list_frame = None
                for frame in self.page.frames:
                    if frame.name == CarewellSelectors.FRAME_LIST:
                        list_frame = frame
                        break

                if not list_frame:
                    self.logger.warning(
                        "'list' frame not found for pagination check, using main page"
                    )
                    list_frame = self.page

                self.logger.info("✓ Frame reference refreshed for pagination check")

                # Check for pagination and navigate to next page
                try:
                    pagination_select = list_frame.locator(
                        CarewellSelectors.PAGINATION_SELECT
                    )

                    if pagination_select.count() == 0:
                        self.logger.info(
                            "No pagination control found, assuming single page"
                        )
                        break

                    # Get all page options
                    options = pagination_select.locator("option").all()
                    total_pages = len(options)
                    self.logger.info(f"Total pages available: {total_pages}")

                    # Check if there's a next page
                    if current_page >= total_pages:
                        self.logger.info(
                            f"Reached last page {current_page}/{total_pages}"
                        )
                        break

                    # Navigate to next page
                    next_page = current_page + 1
                    self.logger.info(f"Navigating to page {next_page}/{total_pages}")

                    # Select next page by value (page numbers are 1-indexed)
                    pagination_select.select_option(str(next_page))

                    # Wait for page transition to complete (ASP.NET __doPostBack)
                    self.logger.info(
                        "Waiting for page transition to complete (15 seconds)..."
                    )
                    time.sleep(15)

                    # Refresh frame reference after page transition
                    # (frame may become stale after ASP.NET postback)
                    self.logger.info(
                        "Refreshing frame reference after page transition..."
                    )
                    list_frame = None
                    for frame in self.page.frames:
                        if frame.name == CarewellSelectors.FRAME_LIST:
                            list_frame = frame
                            break

                    if not list_frame:
                        self.logger.error(
                            "'list' frame not found after pagination, breaking loop"
                        )
                        break

                    self.logger.info(
                        f"✓ Frame reference refreshed for page {next_page}"
                    )

                    # Update list_url after pagination
                    # Note: ASP.NET uses ViewState, so URL remains unchanged across pages
                    # Page state is preserved via browser history (go_back) instead of URL
                    list_url = list_frame.url
                    self.logger.info(
                        f"✓ Page {next_page} loaded (ViewState-based, URL unchanged: {list_url})"
                    )

                    current_page = next_page

                except Exception as pe:
                    self.logger.warning(
                        f"Pagination navigation failed: {pe}, assuming last page"
                    )
                    break

            self.logger.info(
                f"Successfully extracted {len(all_submissions)} submissions from {current_page} page(s)"
            )

        except Exception as e:
            self.logger.error(f"Error extracting submissions: {e}", exc_info=True)

        # Verify count matches
        extracted_count = len(all_submissions)
        verified = False

        if total_count is not None:
            verified = extracted_count == total_count
            if verified:
                self.logger.info(
                    f"✓ Count verification passed: {extracted_count}/{total_count}"
                )
            else:
                self.logger.warning(
                    f"⚠️ Count mismatch! Extracted {extracted_count} submissions but UI shows {total_count}"
                )
        else:
            self.logger.warning(
                "Could not verify count: total_count not available from UI"
            )

        return {
            "submissions": all_submissions,
            "total_count": total_count,
            "extracted_count": extracted_count,
            "verified": verified,
        }

    def _get_download_link(
        self, detail_url: str, list_url: str, current_page: int = 1
    ) -> dict:
        """
        Navigate to detail page and extract download link

        Args:
            detail_url: Relative URL to detail page (e.g., "report.aspx?log_id=XXX")
            list_url: URL of the list page to return to
            current_page: Current pagination page number (default: 1)
                         Used for re-navigation after go_back()

        Returns:
            Dictionary with 'url' and 'filename'
        """
        try:
            # Find list frame
            list_frame = None
            for frame in self.page.frames:
                if frame.name == CarewellSelectors.FRAME_LIST:
                    list_frame = frame
                    break

            if not list_frame:
                list_frame = self.page

            # Use the provided list_url parameter instead of reading from frame
            # This ensures we return to the correct page after detail page navigation
            # (especially important for multi-page processing - e.g., page 2 students)
            current_url = list_url
            self.logger.debug(f"Target list URL (from parameter): {current_url}")

            # Ensure we're on the correct page before searching for links
            # This is critical for multi-page scenarios (e.g., page 2 students)
            # where frame might have navigated away from the target page
            if list_frame.url != current_url:
                self.logger.info(
                    f"Frame URL mismatch detected. Navigating to correct page: {current_url}"
                )
                list_frame.goto(current_url, wait_until="load", timeout=30000)
                self._wait_for_navigation()

                # Refresh frame reference after navigation
                temp_list_frame = None
                for frame in self.page.frames:
                    if frame.name == CarewellSelectors.FRAME_LIST:
                        temp_list_frame = frame
                        break
                if temp_list_frame:
                    list_frame = temp_list_frame
                    self.logger.info("✓ Frame refreshed after page correction")

            # Phase 6: Dynamic link detection without hardcoding URL strings
            # Find detail link dynamically by comparing href attributes
            detail_link_found = False
            try:
                # Find all report links dynamically (not using URL string in selector)
                report_links = list_frame.locator('a[href*="report.aspx"]').all()
                self.logger.info(f"Found {len(report_links)} report links in the page")

                if not report_links:
                    self.logger.warning(f"No report links found for {detail_url}")
                    return {"url": None, "filename": None}

                # Normalize detail_url for comparison (remove &filter= parameter if present)
                # The "全て" tab click adds &filter=all to URLs, which may not be in the extracted detail_url
                detail_url_normalized = detail_url.split("&filter=")[0].split(
                    "?filter="
                )[0]

                # Search for the specific detail link by comparing href attributes
                # This handles HTML entity encoding differences (&amp; vs &)
                for link in report_links:
                    link_href = link.get_attribute("href")
                    if link_href:
                        # Normalize link_href for comparison
                        link_href_normalized = link_href.split("&filter=")[0].split(
                            "?filter="
                        )[0]
                        link_href_decoded = link_href.replace("&amp;", "&")
                        link_href_decoded_normalized = link_href_decoded.split(
                            "&filter="
                        )[0].split("?filter=")[0]

                        # Compare URLs with multiple strategies:
                        # 1. Exact match (original URLs)
                        # 2. Exact match with entity decoding
                        # 3. Match without filter parameter (normalized)
                        # 4. detail_url contained in link_href
                        if (
                            link_href == detail_url
                            or link_href_decoded == detail_url
                            or link_href_normalized == detail_url_normalized
                            or link_href_decoded_normalized == detail_url_normalized
                            or detail_url in link_href
                            or detail_url.replace("&", "&amp;") in link_href
                        ):
                            self.logger.info(
                                f"✓ Found detail link dynamically: {detail_url} (matched with {link_href[:100]})"
                            )
                            # Playwright's auto-waiting handles visibility checks before click
                            link.click()
                            detail_link_found = True
                            break

                if not detail_link_found:
                    self.logger.warning(
                        f"Detail link not found dynamically: {detail_url}"
                    )
                    # Log detailed info about found links for troubleshooting
                    found_links = [
                        link.get_attribute("href") for link in report_links[:3]
                    ]
                    self.logger.warning(f"Sample found links (first 3): {found_links}")
                    self.logger.warning(
                        f"detail_url_normalized: {detail_url_normalized}"
                    )
                    return {"url": None, "filename": None}

                self._wait_for_navigation(3000)  # Wait longer for detail page

            except Exception as e:
                self.logger.warning(
                    f"Error finding detail link dynamically: {detail_url} - {e}"
                )
                return {"url": None, "filename": None}

            # Find download link (download.aspx?id=XXX)
            download_link = list_frame.locator('a[href^="download.aspx"]').first

            if download_link.count() > 0:
                download_url = download_link.get_attribute("href")
                filename = download_link.text_content().strip()
                self.logger.info(f"Found download link: {filename}")

                # Navigate back to list using browser history (page level)
                # Note: Always returns to page 1 due to ASP.NET ViewState behavior
                self.page.go_back(wait_until="load", timeout=30000)
                self._wait_for_navigation()

                # Re-navigate to target page if not page 1
                if current_page > 1:
                    self.logger.info(
                        f"Re-navigating to page {current_page} after go_back()"
                    )

                    # Get frame reference with retry logic (from Common Mistake #6 pattern)
                    list_frame = None
                    max_retries = 3

                    for retry in range(max_retries):
                        for frame in self.page.frames:
                            if frame.name == CarewellSelectors.FRAME_LIST:
                                try:
                                    _ = frame.url  # Verify frame not detached
                                    list_frame = frame
                                    break
                                except Exception:
                                    continue

                        if list_frame:
                            break

                        if retry < max_retries - 1:
                            self.logger.debug(
                                f"Frame not found, retrying ({retry + 1}/{max_retries})..."
                            )
                            time.sleep(2)

                    if not list_frame:
                        self.logger.error(
                            "List frame not found after go_back, cannot re-navigate"
                        )
                        return {"url": None, "filename": None}

                    # Navigate to target page
                    pagination_select = list_frame.locator("#ctl00_masterMain_ddlPage")

                    if pagination_select.count() > 0:
                        pagination_select.select_option(str(current_page))
                        self.logger.info(
                            f"Waiting for page transition to page {current_page} (15 seconds)..."
                        )
                        time.sleep(15)  # Same as existing pagination wait time

                        # Refresh frame reference after re-navigation
                        list_frame = None
                        for retry in range(max_retries):
                            for frame in self.page.frames:
                                if frame.name == CarewellSelectors.FRAME_LIST:
                                    try:
                                        _ = frame.url
                                        list_frame = frame
                                        break
                                    except Exception:
                                        continue

                            if list_frame:
                                break

                            if retry < max_retries - 1:
                                time.sleep(2)

                        self.logger.info(f"✓ Re-navigated to page {current_page}")
                    else:
                        self.logger.warning(
                            "Pagination control not found after go_back"
                        )

                # Phase 3: Refresh frame reference after navigation
                # (frame may be detached after list_frame.goto())
                list_frame = None
                for frame in self.page.frames:
                    if frame.name == CarewellSelectors.FRAME_LIST:
                        list_frame = frame
                        break

                if not list_frame:
                    self.logger.error("'list' frame not found after navigation back")
                    return {"url": None, "filename": None}

                # Phase 3: Wait for table rows to re-render after navigation
                # This ensures the next student's detail link will be available
                try:
                    list_frame.wait_for_selector(
                        "tr.standard_grid_item", timeout=10000, state="visible"
                    )
                    self.logger.debug("✓ Table rows re-rendered after navigation back")
                except Exception as e:
                    self.logger.warning(
                        f"Table rows not immediately visible after navigation: {e}"
                    )

                return {"url": download_url, "filename": filename}
            else:
                self.logger.warning(f"No download link found for {detail_url}")
                # Navigate back to list using browser history (page level)
                # Note: Always returns to page 1 due to ASP.NET ViewState behavior
                self.page.go_back(wait_until="load", timeout=30000)
                self._wait_for_navigation()

                # Re-navigate to target page if not page 1
                if current_page > 1:
                    self.logger.info(
                        f"Re-navigating to page {current_page} after go_back()"
                    )

                    # Get frame reference with retry logic (from Common Mistake #6 pattern)
                    list_frame = None
                    max_retries = 3

                    for retry in range(max_retries):
                        for frame in self.page.frames:
                            if frame.name == CarewellSelectors.FRAME_LIST:
                                try:
                                    _ = frame.url  # Verify frame not detached
                                    list_frame = frame
                                    break
                                except Exception:
                                    continue

                        if list_frame:
                            break

                        if retry < max_retries - 1:
                            self.logger.debug(
                                f"Frame not found, retrying ({retry + 1}/{max_retries})..."
                            )
                            time.sleep(2)

                    if not list_frame:
                        self.logger.error(
                            "List frame not found after go_back, cannot re-navigate"
                        )
                        return {"url": None, "filename": None}

                    # Navigate to target page
                    pagination_select = list_frame.locator("#ctl00_masterMain_ddlPage")

                    if pagination_select.count() > 0:
                        pagination_select.select_option(str(current_page))
                        self.logger.info(
                            f"Waiting for page transition to page {current_page} (15 seconds)..."
                        )
                        time.sleep(15)  # Same as existing pagination wait time

                        # Refresh frame reference after re-navigation
                        list_frame = None
                        for retry in range(max_retries):
                            for frame in self.page.frames:
                                if frame.name == CarewellSelectors.FRAME_LIST:
                                    try:
                                        _ = frame.url
                                        list_frame = frame
                                        break
                                    except Exception:
                                        continue

                            if list_frame:
                                break

                            if retry < max_retries - 1:
                                time.sleep(2)

                        self.logger.info(f"✓ Re-navigated to page {current_page}")
                    else:
                        self.logger.warning(
                            "Pagination control not found after go_back"
                        )

                # Phase 3: Refresh frame reference after navigation
                # (frame may be detached after list_frame.goto())
                list_frame = None
                for frame in self.page.frames:
                    if frame.name == CarewellSelectors.FRAME_LIST:
                        list_frame = frame
                        break

                if not list_frame:
                    self.logger.error("'list' frame not found after navigation back")
                    return {"url": None, "filename": None}

                # Phase 3: Wait for table rows to re-render after navigation
                try:
                    list_frame.wait_for_selector(
                        "tr.standard_grid_item", timeout=10000, state="visible"
                    )
                    self.logger.debug("✓ Table rows re-rendered after navigation back")
                except Exception as e:
                    self.logger.warning(
                        f"Table rows not immediately visible after navigation: {e}"
                    )

                return {"url": None, "filename": None}

        except Exception as e:
            self.logger.error(
                f"Error getting download link from {detail_url}: {e}", exc_info=True
            )
            # Try to go back to list using browser history (page level, error recovery)
            # Note: Always returns to page 1 due to ASP.NET ViewState behavior
            try:
                self.page.go_back(wait_until="load", timeout=30000)
                self._wait_for_navigation()

                # Re-navigate to target page if not page 1
                if current_page > 1:
                    self.logger.info(
                        f"Re-navigating to page {current_page} after go_back()"
                    )

                    # Get frame reference with retry logic (from Common Mistake #6 pattern)
                    list_frame = None
                    max_retries = 3

                    for retry in range(max_retries):
                        for frame in self.page.frames:
                            if frame.name == CarewellSelectors.FRAME_LIST:
                                try:
                                    _ = frame.url  # Verify frame not detached
                                    list_frame = frame
                                    break
                                except Exception:
                                    continue

                        if list_frame:
                            break

                        if retry < max_retries - 1:
                            self.logger.debug(
                                f"Frame not found, retrying ({retry + 1}/{max_retries})..."
                            )
                            time.sleep(2)

                    if not list_frame:
                        self.logger.error(
                            "List frame not found after go_back, cannot re-navigate"
                        )
                        return {"url": None, "filename": None}

                    # Navigate to target page
                    pagination_select = list_frame.locator("#ctl00_masterMain_ddlPage")

                    if pagination_select.count() > 0:
                        pagination_select.select_option(str(current_page))
                        self.logger.info(
                            f"Waiting for page transition to page {current_page} (15 seconds)..."
                        )
                        time.sleep(15)  # Same as existing pagination wait time

                        # Refresh frame reference after re-navigation
                        list_frame = None
                        for retry in range(max_retries):
                            for frame in self.page.frames:
                                if frame.name == CarewellSelectors.FRAME_LIST:
                                    try:
                                        _ = frame.url
                                        list_frame = frame
                                        break
                                    except Exception:
                                        continue

                            if list_frame:
                                break

                            if retry < max_retries - 1:
                                time.sleep(2)

                        self.logger.info(f"✓ Re-navigated to page {current_page}")
                    else:
                        self.logger.warning(
                            "Pagination control not found after go_back"
                        )

                # Phase 3: Refresh frame reference after navigation (error recovery)
                list_frame = None
                for frame in self.page.frames:
                    if frame.name == CarewellSelectors.FRAME_LIST:
                        list_frame = frame
                        break

                if list_frame:
                    # Phase 3: Wait for table rows to re-render
                    try:
                        list_frame.wait_for_selector(
                            "tr.standard_grid_item", timeout=10000, state="visible"
                        )
                        self.logger.debug(
                            "✓ Table rows re-rendered after error recovery"
                        )
                    except:
                        pass
            except:
                pass
            return {"url": None, "filename": None}

    def download_file(self, download_url: str, filename: str, detail_url: str) -> str:
        """
        Download a file from Carewell

        Args:
            download_url: URL to download file (e.g., "download.aspx?id=XXX")
            filename: Suggested filename
            detail_url: Detail page URL where download link exists

        Returns:
            Path to downloaded file in /tmp

        Raises:
            Exception if download fails
        """
        import os
        from pathlib import Path

        try:
            # Find list frame
            list_frame = None
            for frame in self.page.frames:
                if frame.name == CarewellSelectors.FRAME_LIST:
                    list_frame = frame
                    break

            if not list_frame:
                list_frame = self.page

            self.logger.info(f"Starting download: {filename}")

            # Navigate to detail page first (download link is there)
            self.logger.debug(f"Navigating to detail page: {detail_url}")

            # Strategy: Try multiple approaches to click the link
            detail_link_selector = f'a[href="{detail_url}"]'
            clicked = False

            # Attempt 1: Standard click with short timeout
            try:
                self.logger.debug(f"Attempt 1: Standard click")
                list_frame.wait_for_selector(
                    detail_link_selector, state="attached", timeout=5000
                )
                list_frame.click(detail_link_selector, timeout=5000)
                clicked = True
                self._wait_for_navigation(2000)
            except Exception as e1:
                self.logger.debug(f"Attempt 1 failed: {e1}")

                # Attempt 2: Scroll into view and force click
                try:
                    self.logger.debug(f"Attempt 2: Scroll and force click")
                    element = list_frame.query_selector(detail_link_selector)
                    if element:
                        element.scroll_into_view_if_needed()
                        time.sleep(0.5)
                        element.click(force=True, timeout=5000)
                        clicked = True
                        self._wait_for_navigation(2000)
                    else:
                        raise Exception("Element not found")
                except Exception as e2:
                    self.logger.debug(f"Attempt 2 failed: {e2}")

                    # Attempt 3: Direct navigation
                    try:
                        self.logger.debug(f"Attempt 3: Direct navigation")
                        current_url = list_frame.url
                        base_url = current_url.split("?")[0].rsplit("/", 1)[0]
                        full_detail_url = f"{base_url}/{detail_url}"
                        self.logger.debug(f"Navigating to: {full_detail_url}")
                        list_frame.goto(
                            full_detail_url,
                            timeout=10000,
                            wait_until="domcontentloaded",
                        )
                        clicked = True
                        self._wait_for_navigation(2000)
                    except Exception as e3:
                        self.logger.error(f"All navigation attempts failed: {e3}")
                        raise Exception(
                            f"Cannot navigate to detail page after 3 attempts"
                        )

            # Set up download handler and click download link
            self.logger.debug(f"Initiating download: {download_url}")
            download = None
            with self.page.expect_download(timeout=60000) as download_info:
                # Click download link
                list_frame.click(f'a[href="{download_url}"]', timeout=10000)
                download = download_info.value

            # Save to /tmp with sanitized filename
            # Remove unsafe characters from filename
            safe_filename = "".join(
                c
                for c in filename
                if c.isalnum() or c in (" ", ".", "_", "-", "（", "）", "　")
            )
            download_path = f"/tmp/{safe_filename}"

            # Save the file
            self.logger.debug(f"Saving file to: {download_path}")
            download.save_as(download_path)

            # Verify file exists and has size
            if os.path.exists(download_path):
                file_size = os.path.getsize(download_path)
                self.logger.info(
                    f"Downloaded successfully: {download_path} ({file_size} bytes)"
                )
                return download_path
            else:
                raise Exception(f"Download failed: file not found at {download_path}")

        except Exception as e:
            self.logger.error(f"Error downloading {filename}: {e}", exc_info=True)
            raise

    def close(self):
        """Close browser and cleanup resources"""
        self.logger.info("Closing browser")
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
