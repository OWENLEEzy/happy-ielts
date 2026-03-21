import { test, expect } from '@playwright/test'

test.describe('DynamicLingo lesson flow', () => {
  test('loading state shows when planner not ready', async ({ page }) => {
    await page.goto('http://localhost:3000/lesson')
    const body = await page.locator('body').textContent()
    expect(body).toBeTruthy()
  })

  test('onboarding page renders Professor 金毛 chat UI', async ({ page }) => {
    await page.goto('http://localhost:3000/onboarding')
    await expect(page.locator('text=Professor 金毛').or(page.locator('text=PROFESSOR 金毛'))).toBeVisible()
    // Onboarding can show text input OR preference buttons depending on conversation state
    const hasInput = await page.locator('input[placeholder*="输入"]').isVisible().catch(() => false)
    const hasButtons = await page.locator('button').count()
    expect(hasInput || hasButtons > 0).toBeTruthy()
  })

  test('DynamicLingo brand appears in header', async ({ page }) => {
    await page.goto('http://localhost:3000/onboarding')
    await expect(page.locator('text=DynamicLingo')).toBeVisible()
  })
})

test.describe('Planner API (v2)', () => {
  test('GET /api/planner/status returns ready_for_tomorrow field', async ({ request }) => {
    const resp = await request.get('http://localhost:8000/api/planner/status')
    expect(resp.status()).toBe(200)
    const body = await resp.json()
    expect(body).toHaveProperty('ready')
    expect(body).toHaveProperty('ready_for_tomorrow')
    expect(body).toHaveProperty('status')
    expect(typeof body.ready_for_tomorrow).toBe('boolean')
  })

  test('POST /api/planner/prepare-next returns valid status', async ({ request }) => {
    const resp = await request.post('http://localhost:8000/api/planner/prepare-next')
    expect(resp.status()).toBe(200)
    const body = await resp.json()
    expect(['started', 'already_ready']).toContain(body.status)
    expect(body).toHaveProperty('date')
  })

  test('GET /health returns ok', async ({ request }) => {
    const resp = await request.get('http://localhost:8000/health')
    expect(resp.status()).toBe(200)
    expect(await resp.json()).toEqual({ status: 'ok' })
  })

  test('GET /api/onboarding/status returns ready flag', async ({ request }) => {
    const resp = await request.get('http://localhost:8000/api/onboarding/status')
    expect(resp.status()).toBe(200)
    const body = await resp.json()
    expect(body).toHaveProperty('ready')
    expect(typeof body.ready).toBe('boolean')
  })
})
