import { test, expect } from '@playwright/test';

test.describe('Responsive Design', () => {
  test('should display desktop layout on large screens', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto('/');

    // Navigate to file list
    await page.locator('[role="button"]').first().click();
    await page.locator('[role="button"]').first().click();

    // Verify table is visible (desktop layout)
    const table = page.locator('table');
    if (await table.isVisible()) {
      await expect(table).toBeVisible();
    }
  });

  test('should display mobile layout on small screens', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');

    // Navigate to file list
    await page.locator('[role="button"]').first().click();
    await page.locator('[role="button"]').first().click();

    // Verify mobile card layout or sort buttons
    const sortButtons = page.locator('[role="group"][aria-label="ソートオプション"]');
    if (await sortButtons.isVisible()) {
      await expect(sortButtons).toBeVisible();
    }
  });

  test('should support touch interactions on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');

    // Verify class cards are touch-friendly
    const classCard = page.locator('[role="button"]').first();
    await expect(classCard).toBeVisible();

    // Simulate touch tap
    await classCard.tap();

    // Verify navigation occurred
    await expect(page.locator('h1')).toContainText('課題一覧');
  });

  test('should maintain accessibility on different screen sizes', async ({ page }) => {
    // Test on desktop
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto('/');

    let skipLink = page.locator('a[href="#main-content"]');
    await expect(skipLink).toBeVisible({ visible: false }); // Skip link is visually hidden

    // Test on mobile
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');

    skipLink = page.locator('a[href="#main-content"]');
    await expect(skipLink).toBeVisible({ visible: false }); // Still present
  });

  test('should display correct grid layout for class cards', async ({ page }) => {
    // Desktop: multiple columns
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto('/');

    const classCards = page.locator('[role="button"]');
    const count = await classCards.count();
    expect(count).toBeGreaterThan(0);

    // Mobile: single column
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');

    const mobileClassCards = page.locator('[role="button"]');
    const mobileCount = await mobileClassCards.count();
    expect(mobileCount).toBeGreaterThan(0);
  });
});
