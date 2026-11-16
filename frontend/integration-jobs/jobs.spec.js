import { test, expect } from '@playwright/test'

// #77 / BS-003: progress and acquisition failure visible through the real API.
async function openBeyondSeed(page) {
  await page.goto('/#explore')
  await page.getByLabel('Region to explore', { exact: true }).selectOption('sahel')
  await expect(page.locator('.explore .chart')).toHaveCount(1)
  await page.getByRole('slider', { name: 'Range end', exact: true }).fill('301')
  await page.getByRole('slider', { name: 'Range start', exact: true }).fill('300')
}

test('monthly acquisition shows progress then draws its Series; repeat uses cache', async ({ page }) => {
  await openBeyondSeed(page)
  await expect(page.getByRole('progressbar')).toBeVisible()
  await expect(page.locator('.explore [role="status"]')).toContainText(/Obtaining the Series/)
  await expect(page.locator('.explore .chart')).toHaveCount(1)
  await expect(page.getByRole('progressbar')).toHaveCount(0)
  await expect(page.locator('.explore .chart-time').first()).toHaveText('Jan 2025')
  await page.getByRole('slider', { name: 'Range start', exact: true }).fill('288')
  await expect(page.locator('.explore .chart-time').first()).toHaveText('Jan 2024')
  const repeat = page.waitForResponse((r) => r.url().includes('/api/explore/series')
    && new URL(r.url()).searchParams.get('period_start') === '2025-01')
  await page.getByRole('slider', { name: 'Range start', exact: true }).fill('300')
  const response = await repeat
  expect(response.status()).toBe(200)
  expect((await response.json()).provenance).toBe('cache')
  await expect(page.locator('.explore .chart')).toHaveCount(1)
})

test('acquisition failure tells the user the Series could not be obtained', async ({ page }) => {
  await openBeyondSeed(page)
  await expect(page.locator('.explore .chart')).toHaveCount(1)
  await page.getByRole('checkbox', { name: 'Air temperature', exact: true }).uncheck()
  await page.getByRole('checkbox', { name: 'Precipitation', exact: true }).check()
  await expect(page.getByRole('progressbar')).toBeVisible()
  await expect(page.locator('.explore [role="status"]')).toContainText('The Series could not be obtained')
  await expect(page.getByRole('progressbar')).toHaveCount(0)
  await expect(page.locator('.explore .chart')).toHaveCount(0)
})
