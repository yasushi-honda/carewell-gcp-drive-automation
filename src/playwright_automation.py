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
    FRAME_LOAD_WAIT = 3000  # Wait for frames to load
    DATA_LOAD_WAIT = 5000  # Wait for data-heavy pages

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
        logger.info("Launching Chromium browser")
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
                if frame.locator(selector).count() > 0:
                    logger.debug(
                        f"Found selector '{selector}' in frame: {frame.name or frame.url}"
                    )
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
        logger.info(f"Selecting class: {class_name}")

        if not self._click_in_any_frame(
            f'text="{class_name}"', f'class "{class_name}"'
        ):
            logger.info(f"Class not found (likely not yet created): {class_name}")
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
        logger.info(f"Selecting task with pattern: {task_pattern}")

        # Use text= selector without quotes for partial match
        if not self._click_in_any_frame(
            f"text={task_pattern}", f'task "{task_pattern}"'
        ):
            logger.info(f"Task not found (likely not yet created): {task_pattern}")
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
            logger.info(f"Class not found, skipping: {class_name}")
            return None

        self._navigate_to_report_grading()

        # Check if task exists
        if not self._select_task(task_pattern):
            logger.info(f"Task not found, skipping: {task_pattern}")
            return None

        self._show_all_submissions()

        logger.info("Successfully navigated to task page")
        return self.page

    def get_submission_list(self) -> dict:
        """
        Extract submission file information from all pages

        Returns:
            Dictionary containing:
            - submissions: List of submission dictionaries with metadata and download links
            - total_count: Total number of submissions (from UI counter)
            - verified: Whether the count matches the extracted submissions
        """
        logger.info("Extracting submission list from all pages")

        # Find the list frame
        list_frame = None
        for frame in self.page.frames:
            if frame.name == CarewellSelectors.FRAME_LIST:
                list_frame = frame
                break

        if not list_frame:
            logger.warning("'list' frame not found, using main page")
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
                    logger.info(f"✓ Total submission count from UI: {total_count}")
                else:
                    logger.warning(f"Could not parse total count from: {count_text}")

        except Exception as e:
            logger.warning(f"Could not extract total count from UI: {e}")

        # Collect submissions from all pages
        all_submissions = []
        current_page = 1

        try:
            # Loop through all pages
            while True:
                logger.info(f"Processing page {current_page}")

                # Refresh frame reference for each page to handle pagination
                # This ensures we always have the latest frame object after page transitions
                list_frame = None
                for frame in self.page.frames:
                    if frame.name == CarewellSelectors.FRAME_LIST:
                        list_frame = frame
                        break

                if not list_frame:
                    logger.warning("'list' frame not found, using main page")
                    list_frame = self.page

                # Save current page URL for navigation back from detail pages
                list_url = list_frame.url
                logger.debug(f"Current list URL for page {current_page}: {list_url}")

                # Wait for table to be fully rendered after frame reload or page transition
                if current_page == 1:
                    # Frame reload after "全て" tab click
                    logger.info("Waiting for table to render after frame reload...")
                    time.sleep(5)
                elif current_page > 1:
                    # Page transition via ASP.NET __doPostBack
                    logger.info("Waiting for table to render after page navigation...")
                    time.sleep(3)

                # Wait for data to load
                logger.info("Waiting for submission table rows...")
                list_frame.wait_for_selector("tr.standard_grid_item", timeout=30000)
                logger.info("✓ Submission table rows found")

                # First pass: Extract all basic submission info from current page
                rows = list_frame.locator("tr.standard_grid_item").all()
                logger.info(f"Found {len(rows)} submission rows on page {current_page}")

                submission_basics = []
                for i, row in enumerate(rows):
                    try:
                        cells = row.locator("td").all()
                        if len(cells) < 6:
                            logger.warning(
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
                        logger.error(
                            f"Could not parse row {i}: {row_error}", exc_info=True
                        )

                logger.info(
                    f"Extracted basic info for {len(submission_basics)} submissions on page {current_page}"
                )

                # Second pass: Get download links for each submission on current page
                for basic in submission_basics:
                    try:
                        logger.info(
                            f"Getting download link for: {basic['student_name']}"
                        )
                        download_info = self._get_download_link(
                            basic["detail_url"], list_url
                        )

                        submission = {
                            **basic,  # Includes detail_url from basic info
                            "download_url": download_info.get("url"),
                            "filename": download_info.get("filename"),
                        }

                        all_submissions.append(submission)
                        logger.info(
                            f"Added: {basic['student_name']} - {download_info.get('filename')}"
                        )

                    except Exception as e:
                        logger.error(
                            f"Error processing {basic['student_name']}: {e}",
                            exc_info=True,
                        )

                # Check for pagination and navigate to next page
                try:
                    pagination_select = list_frame.locator(
                        CarewellSelectors.PAGINATION_SELECT
                    )

                    if pagination_select.count() == 0:
                        logger.info("No pagination control found, assuming single page")
                        break

                    # Get all page options
                    options = pagination_select.locator("option").all()
                    total_pages = len(options)
                    logger.info(f"Total pages available: {total_pages}")

                    # Check if there's a next page
                    if current_page >= total_pages:
                        logger.info(f"Reached last page {current_page}/{total_pages}")
                        break

                    # Navigate to next page
                    next_page = current_page + 1
                    logger.info(f"Navigating to page {next_page}/{total_pages}")

                    # Select next page by value (page numbers are 1-indexed)
                    pagination_select.select_option(str(next_page))

                    current_page = next_page

                except Exception as pe:
                    logger.warning(
                        f"Pagination navigation failed: {pe}, assuming last page"
                    )
                    break

            logger.info(
                f"Successfully extracted {len(all_submissions)} submissions from {current_page} page(s)"
            )

        except Exception as e:
            logger.error(f"Error extracting submissions: {e}", exc_info=True)

        # Verify count matches
        extracted_count = len(all_submissions)
        verified = False

        if total_count is not None:
            verified = extracted_count == total_count
            if verified:
                logger.info(
                    f"✓ Count verification passed: {extracted_count}/{total_count}"
                )
            else:
                logger.warning(
                    f"⚠️ Count mismatch! Extracted {extracted_count} submissions but UI shows {total_count}"
                )
        else:
            logger.warning("Could not verify count: total_count not available from UI")

        return {
            "submissions": all_submissions,
            "total_count": total_count,
            "extracted_count": extracted_count,
            "verified": verified,
        }

    def _get_download_link(self, detail_url: str, list_url: str) -> dict:
        """
        Navigate to detail page and extract download link

        Args:
            detail_url: Relative URL to detail page (e.g., "report.aspx?log_id=XXX")
            list_url: URL of the list page to return to

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

            # Save current URL
            current_url = list_frame.url
            logger.debug(f"Current list URL: {current_url}")

            # Click the detail link
            list_frame.click(f'a[href="{detail_url}"]')
            self._wait_for_navigation(3000)  # Wait longer for detail page

            # Find download link (download.aspx?id=XXX)
            download_link = list_frame.locator('a[href^="download.aspx"]').first

            if download_link.count() > 0:
                download_url = download_link.get_attribute("href")
                filename = download_link.text_content().strip()
                logger.info(f"Found download link: {filename}")

                # Navigate back to list using goto
                self.page.goto(current_url, wait_until="networkidle")
                self._wait_for_navigation()

                return {"url": download_url, "filename": filename}
            else:
                logger.warning(f"No download link found for {detail_url}")
                # Navigate back to list
                self.page.goto(current_url, wait_until="networkidle")
                self._wait_for_navigation()

                return {"url": None, "filename": None}

        except Exception as e:
            logger.error(
                f"Error getting download link from {detail_url}: {e}", exc_info=True
            )
            # Try to go back to list URL
            try:
                if list_frame and current_url:
                    self.page.goto(current_url, wait_until="networkidle")
                    self._wait_for_navigation()
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

            logger.info(f"Starting download: {filename}")

            # Navigate to detail page first (download link is there)
            logger.debug(f"Navigating to detail page: {detail_url}")

            # Strategy: Try multiple approaches to click the link
            detail_link_selector = f'a[href="{detail_url}"]'
            clicked = False

            # Attempt 1: Standard click with short timeout
            try:
                logger.debug(f"Attempt 1: Standard click")
                list_frame.wait_for_selector(
                    detail_link_selector, state="attached", timeout=5000
                )
                list_frame.click(detail_link_selector, timeout=5000)
                clicked = True
                self._wait_for_navigation(2000)
            except Exception as e1:
                logger.debug(f"Attempt 1 failed: {e1}")

                # Attempt 2: Scroll into view and force click
                try:
                    logger.debug(f"Attempt 2: Scroll and force click")
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
                    logger.debug(f"Attempt 2 failed: {e2}")

                    # Attempt 3: Direct navigation
                    try:
                        logger.debug(f"Attempt 3: Direct navigation")
                        current_url = list_frame.url
                        base_url = current_url.split("?")[0].rsplit("/", 1)[0]
                        full_detail_url = f"{base_url}/{detail_url}"
                        logger.debug(f"Navigating to: {full_detail_url}")
                        list_frame.goto(
                            full_detail_url,
                            timeout=10000,
                            wait_until="domcontentloaded",
                        )
                        clicked = True
                        self._wait_for_navigation(2000)
                    except Exception as e3:
                        logger.error(f"All navigation attempts failed: {e3}")
                        raise Exception(
                            f"Cannot navigate to detail page after 3 attempts"
                        )

            # Set up download handler and click download link
            logger.debug(f"Initiating download: {download_url}")
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
            logger.debug(f"Saving file to: {download_path}")
            download.save_as(download_path)

            # Verify file exists and has size
            if os.path.exists(download_path):
                file_size = os.path.getsize(download_path)
                logger.info(
                    f"Downloaded successfully: {download_path} ({file_size} bytes)"
                )
                return download_path
            else:
                raise Exception(f"Download failed: file not found at {download_path}")

        except Exception as e:
            logger.error(f"Error downloading {filename}: {e}", exc_info=True)
            raise

    def close(self):
        """Close browser and cleanup resources"""
        logger.info("Closing browser")
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
