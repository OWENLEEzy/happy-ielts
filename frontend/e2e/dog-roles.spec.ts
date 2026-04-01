import { test, expect, type Page } from '@playwright/test'

function collectHydrationNoise(page: Page) {
  const hydrationMessages: string[] = []

  page.on('console', (message) => {
    if (message.type() === 'error' || message.type() === 'warning') {
      hydrationMessages.push(message.text())
    }
  })
  page.on('pageerror', (error) => {
    hydrationMessages.push(error.message)
  })

  return hydrationMessages
}

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

  test('home page uses relationship dog in the hero anchor and hydrates cleanly', async ({
    page,
  }) => {
    const hydrationMessages = collectHydrationNoise(page)

    await page.goto('/')
    await expect(page.locator('[data-dog-role="relationship"][data-dog-emphasis="hero"]')).toBeVisible()

    const hydrationNoise = hydrationMessages.filter((text) =>
      /hydration|did not match|server-rendered html|text content does not match/i.test(text),
    )
    expect(hydrationNoise, hydrationMessages.join('\n')).toEqual([])
  })

  test('english onboarding keeps a teacher dog for the guide card', async ({ page }) => {
    const hydrationMessages = collectHydrationNoise(page)

    await page.goto('/onboarding')
    const introCard = page.locator('[data-testid="teacher-intro-card"]')
    await expect(introCard).toContainText('Professor 金毛')
    await expect(introCard.locator('[data-dog-role="teacher"][data-dog-emphasis="card"]')).toBeVisible()

    const hydrationNoise = hydrationMessages.filter((text) =>
      /hydration|did not match|server-rendered html|text content does not match/i.test(text),
    )
    expect(hydrationNoise, hydrationMessages.join('\n')).toEqual([])
  })
})
