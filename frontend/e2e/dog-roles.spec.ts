import { test, expect } from '@playwright/test'

test.describe('dog role anchors', () => {
  test.beforeEach(async ({ context }) => {
    await context.addCookies([
      {
        name: 'api_key',
        value: 'playwright-test-key',
        url: 'http://localhost:3000',
      },
    ])
  })

  test('home page uses relationship dog in the hero anchor', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('[data-dog-role="relationship"][data-dog-emphasis="hero"]')).toBeVisible()
  })

  test('english onboarding keeps a teacher dog for the guide card', async ({ page }) => {
    await page.goto('/onboarding')
    const introCard = page.locator('div').filter({ hasText: '你的专属语言学习顾问' }).first()
    await expect(introCard).toContainText('Professor 金毛')
    await expect(introCard.locator('[data-dog-role="teacher"][data-dog-emphasis="card"]')).toBeVisible()
  })
})
