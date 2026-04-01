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
    await page.goto('http://localhost:3000/')
    await expect(page.locator('[data-dog-role="relationship"][data-dog-emphasis="hero"]')).toBeVisible()
  })

  test('english onboarding keeps a teacher dog for the guide card', async ({ page }) => {
    await page.goto('http://localhost:3000/onboarding')
    await expect(page.locator('[data-dog-role="teacher"]').first()).toBeVisible()
    await expect(page.locator('text=Professor 金毛').first()).toBeVisible()
  })
})
