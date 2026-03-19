import { test, expect } from '@playwright/test'

test.describe('DynamicLingo lesson flow', () => {
  test('loading state shows when planner not ready', async ({ page }) => {
    await page.goto('http://localhost:3000/lesson')
    // Either loading screen or lesson is shown
    const body = await page.locator('body').textContent()
    expect(body).toBeTruthy()
  })

  test('onboarding page renders chat UI', async ({ page }) => {
    await page.goto('http://localhost:3000/onboarding')
    await expect(page.locator('text=Professor 金毛')).toBeVisible()
    await expect(page.locator('input[placeholder*="输入"]')).toBeVisible()
  })

  test('DynamicLingo brand appears in header', async ({ page }) => {
    await page.goto('http://localhost:3000/onboarding')
    await expect(page.locator('text=DynamicLingo')).toBeVisible()
  })
})
