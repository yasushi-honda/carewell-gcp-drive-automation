import { test, expect } from '@playwright/test';

test.describe('Navigation Flow', () => {
  test('should navigate through class → task → files (Happy Path)', async ({ page }) => {
    // Navigate to the application
    await page.goto('/');

    // Verify class list is displayed
    await expect(page.locator('h1')).toContainText('クラス一覧');

    // Click on a class card
    const classCard = page.locator('[role="button"]').first();
    await expect(classCard).toBeVisible();
    await classCard.click();

    // Verify task list is displayed
    await expect(page.locator('h1')).toContainText('課題一覧');

    // Verify breadcrumb navigation
    const breadcrumb = page.locator('nav[aria-label="パンくずリスト"]');
    await expect(breadcrumb).toBeVisible();

    // Click on a task card
    const taskCard = page.locator('[role="button"]').first();
    await expect(taskCard).toBeVisible();
    await taskCard.click();

    // Verify file list is displayed
    await expect(page.locator('h1')).toContainText('提出ファイル一覧');

    // Verify file table or cards are displayed
    const fileContainer = page.locator('table, [class*="space-y-4"]');
    await expect(fileContainer).toBeVisible();
  });

  test('should navigate back using breadcrumb', async ({ page }) => {
    await page.goto('/');

    // Navigate to task list
    await page.locator('[role="button"]').first().click();
    await expect(page.locator('h1')).toContainText('課題一覧');

    // Click on "クラス一覧" in breadcrumb
    const breadcrumbHome = page.locator('nav[aria-label="パンくずリスト"] a').first();
    await breadcrumbHome.click();

    // Verify back to class list
    await expect(page.locator('h1')).toContainText('クラス一覧');
  });

  test('should support keyboard navigation', async ({ page }) => {
    await page.goto('/');

    // Focus and activate class card using keyboard
    await page.keyboard.press('Tab'); // Skip link
    await page.keyboard.press('Tab'); // First class card
    await page.keyboard.press('Enter');

    // Verify navigation occurred
    await expect(page.locator('h1')).toContainText('課題一覧');
  });
});
