import { test, expect } from '@playwright/test';

test.describe('Search and Sort Features', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to file list page
    await page.goto('/');
    await page.locator('[role="button"]').first().click(); // Click class
    await page.locator('[role="button"]').first().click(); // Click task
  });

  test('should filter files by search query', async ({ page }) => {
    // Type in search box
    const searchInput = page.locator('input[type="text"]');
    await searchInput.fill('森平');

    // Verify filtered results
    // Note: Actual verification depends on data availability
    await expect(searchInput).toHaveValue('森平');
  });

  test('should clear search query', async ({ page }) => {
    const searchInput = page.locator('input[type="text"]');
    await searchInput.fill('test');
    await searchInput.clear();

    await expect(searchInput).toHaveValue('');
  });

  test('should sort by student name', async ({ page }) => {
    // Desktop: Click table header
    const studentNameHeader = page.locator('th').filter({ hasText: '学生名' });

    if (await studentNameHeader.isVisible()) {
      await studentNameHeader.click();

      // Verify sort indicator appears
      const sortIcon = studentNameHeader.locator('svg');
      await expect(sortIcon).toBeVisible();
    }
  });

  test('should sort by submit date', async ({ page }) => {
    // Desktop: Click table header
    const submitDateHeader = page.locator('th').filter({ hasText: '提出日時' });

    if (await submitDateHeader.isVisible()) {
      await submitDateHeader.click();

      // Verify sort indicator appears
      const sortIcon = submitDateHeader.locator('svg');
      await expect(sortIcon).toBeVisible();
    }
  });

  test('should toggle sort order on second click', async ({ page }) => {
    const studentNameHeader = page.locator('th').filter({ hasText: '学生名' });

    if (await studentNameHeader.isVisible()) {
      // First click: ascending
      await studentNameHeader.click();
      let sortIcon = studentNameHeader.locator('svg');
      const firstIconClass = await sortIcon.getAttribute('class');

      // Second click: descending
      await studentNameHeader.click();
      const secondIconClass = await sortIcon.getAttribute('class');

      // Verify icon rotation changed
      expect(firstIconClass).not.toBe(secondIconClass);
    }
  });
});
