"""
Playwright Automation Engine for Carewell Web Service
"""
import logging
import time
from playwright.sync_api import sync_playwright, Browser, Page

logger = logging.getLogger(__name__)


class PlaywrightAutomationEngine:
    """
    Handles browser automation for Carewell web service
    """

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None

    def _launch_browser(self) -> Browser:
        """Launch Chromium browser in headless mode"""
        logger.info("Launching Chromium browser")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        return self.browser

    def _login(self) -> Page:
        """
        Login to Carewell web service

        Retrieves credentials from Secret Manager
        """
        import os
        from google.cloud import secretmanager

        # Get credentials from Secret Manager
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

        logger.info("Navigating to Carewell login page")
        context = self.browser.new_context()
        self.page = context.new_page()

        # Set timeout for slow network
        self.page.set_default_timeout(180000)  # 180 seconds

        # Navigate to login page
        logger.info("Accessing login URL: https://jaccw-carewel.study.jp/")
        self.page.goto("https://jaccw-carewel.study.jp/", wait_until="networkidle")

        # Debug: Log page title and URL
        logger.info(f"Page loaded - Title: {self.page.title()}, URL: {self.page.url}")

        # Wait for frames to load
        time.sleep(2)

        # Find the frame containing login form
        login_frame = None
        for frame in self.page.frames:
            try:
                if frame.locator('input[name="ctl00$masterMain$txtUserID"]').count() > 0:
                    logger.info(f"Found login form in frame: {frame.name or frame.url}")
                    login_frame = frame
                    break
            except:
                continue

        if not login_frame:
            logger.error("Could not find login form in any frame")
            # Fallback to main page
            login_frame = self.page

        # Fill login form
        logger.info("Filling login credentials")
        login_frame.fill('input[name="ctl00$masterMain$txtUserID"]', user_id)
        login_frame.fill('input[name="ctl00$masterMain$txtPassword"]', password)

        # Click login button
        logger.info("Clicking login button")
        login_frame.click('input[name="ctl00$masterMain$btnSubmit"]')

        # Wait for navigation after login
        self.page.wait_for_load_state("networkidle")

        # Additional wait for potential page redirect
        time.sleep(3)
        self.page.wait_for_load_state("networkidle")

        logger.info(f"Login successful, current URL: {self.page.url}")

        try:
            logger.info(f"Page title after login: {self.page.title()}")
        except:
            pass

        # Log all frames after login with URLs
        try:
            for i, frame in enumerate(self.page.frames):
                try:
                    frame_name = frame.name
                    frame_url = frame.url
                    logger.info(f"Frame {i} after login: name={frame_name}, url={frame_url}")
                except:
                    pass
        except:
            pass

        return self.page

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

        # Navigate to class management
        logger.info("Navigating to class management")

        # Wait for frames to fully load after login
        time.sleep(3)

        # Find 'list' frame (known to contain home.aspx after login)
        list_frame = None
        for frame in self.page.frames:
            if frame.name == 'list':
                list_frame = frame
                logger.info(f"Found 'list' frame with URL: {frame.url}")
                break

        if not list_frame:
            # Fallback: search all frames
            logger.warning("'list' frame not found, searching all frames")
            for frame in self.page.frames:
                try:
                    if frame.locator('text="クラス管理"').count() > 0:
                        list_frame = frame
                        logger.info(f"Found 'クラス管理' in frame: {frame.name or frame.url}")
                        break
                except:
                    continue

        if not list_frame:
            raise Exception("Could not find 'list' frame or 'クラス管理' link")

        # Wait for list frame content to load
        logger.info("Waiting for list frame content to load")
        try:
            # Wait for body element to have content
            list_frame.wait_for_selector("body", state="attached", timeout=10000)
            time.sleep(2)  # Additional wait for dynamic content
        except Exception as e:
            logger.warning(f"Could not wait for body selector: {e}")

        # Debug: Log frame content details
        try:
            # Log all text content in the frame
            text_content = list_frame.text_content("body")
            logger.info(f"List frame text content (first 1000 chars): {text_content[:1000] if text_content else 'None'}")

            # Log all links in the frame
            links = list_frame.locator("a").all_text_contents()
            logger.info(f"All links in list frame: {links}")

            # Log inner HTML to see structure
            inner_html = list_frame.inner_html("body")
            logger.info(f"List frame HTML (first 1000 chars): {inner_html[:1000] if inner_html else 'None'}")
        except Exception as e:
            logger.error(f"Failed to debug list frame: {e}")

        # Click "クラス管理" in the list frame
        if list_frame.locator('text="クラス管理"').count() > 0:
            logger.info("Clicking 'クラス管理'")
            list_frame.click('text="クラス管理"')
        else:
            raise Exception("'クラス管理' link not found in list frame")

        time.sleep(2)

        # Click "教科クラス一覧"
        logger.info("Clicking '教科クラス一覧'")
        for frame in self.page.frames:
            try:
                if frame.locator('text="教科クラス一覧"').count() > 0:
                    frame.click('text="教科クラス一覧"')
                    break
            except:
                continue

        # Wait for data to load
        time.sleep(5)

        # Find and click target class
        logger.info(f"Looking for class: {class_name}")
        clicked = False
        for frame in self.page.frames:
            try:
                class_link = frame.locator(f'text="{class_name}"')
                if class_link.count() > 0:
                    logger.info(f"Found class link in frame: {frame.name}")
                    class_link.click()
                    clicked = True
                    break
            except Exception as e:
                logger.debug(f"Could not find class in frame {frame.name}: {e}")
                continue

        if not clicked:
            raise Exception(f"Could not find class: {class_name}")

        time.sleep(2)

        # Click "レポート採点"
        logger.info("Clicking 'レポート採点'")
        for frame in self.page.frames:
            try:
                if frame.locator('text="レポート採点"').count() > 0:
                    frame.click('text="レポート採点"')
                    break
            except:
                continue

        time.sleep(2)

        # Find and click target task
        logger.info(f"Looking for task: {task_name}")
        clicked = False
        for frame in self.page.frames:
            try:
                task_link = frame.locator(f'text="{task_name}"')
                if task_link.count() > 0:
                    logger.info(f"Found task link in frame: {frame.name}")
                    task_link.click()
                    clicked = True
                    break
            except Exception as e:
                logger.debug(f"Could not find task in frame {frame.name}: {e}")
                continue

        if not clicked:
            raise Exception(f"Could not find task: {task_name}")

        time.sleep(2)

        # Click "全て" tab
        logger.info("Clicking '全て' tab")
        for frame in self.page.frames:
            try:
                if frame.locator('text="全て"').count() > 0:
                    frame.click('text="全て"')
                    break
            except:
                continue

        time.sleep(3)

        logger.info(f"Successfully navigated to task page")
        return self.page

    def close(self):
        """Close browser and cleanup"""
        logger.info("Closing browser")
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
