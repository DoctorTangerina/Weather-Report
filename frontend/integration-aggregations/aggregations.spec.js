import { test, expect } from '@playwright/test'

// #78 / BS-002: one Aggregation for the whole Explore My World view. The fake
// grid has two equal-area Sahel cells per Variable:
//   temperature   Jan 2025: 2 and 6   Feb 2025: 10 and 14
//   precipitation Jan 2025: 1 and 5   Feb 2025: 3 and 9
// so means are 4, 12 and 3, 6, and maximums 6, 14 and 5, 9.
const ticks = (page, name) =>
  page.locator('.explore .chart', { hasText: name }).locator('text.chart-tick:not(.chart-time)')

async function openWithTemperatureAndPrecipitation(page) {
  await page.goto('/')
  await page.getByLabel('Region to explore', { exact: true }).selectOption('sahel')
  await expect(page.locator('.explore .chart')).toHaveCount(1)
  await page.getByLabel('From', { exact: true }).fill('2025-01')
  await page.getByLabel('To', { exact: true }).fill('2025-02')
  await page.getByRole('checkbox', { name: 'Precipitation', exact: true }).check()
  await expect(page.locator('.explore .chart')).toHaveCount(2)
}

test('the Aggregation control lists the seven Aggregations and starts at mean', async ({ page }) => {
  await openWithTemperatureAndPrecipitation(page)
  const control = page.getByLabel('Aggregation', { exact: true })
  await expect(control).toHaveValue('mean')
  await expect(control.locator('option')).toHaveText([
    'Mean',
    'Median',
    'Minimum',
    'Maximum',
    'Root mean square',
    'Standard deviation',
    'Mean absolute value',
  ])
  await expect(ticks(page, 'Air temperature')).toHaveText(['12', '4'])
  await expect(ticks(page, 'Precipitation')).toHaveText(['6', '3'])
})

test('choosing the Aggregation "maximum" rebuilds every chart with it', async ({ page }) => {
  await openWithTemperatureAndPrecipitation(page)
  const requested = []
  page.on('request', (request) => {
    if (request.url().includes('/api/explore/series')) {
      requested.push(new URL(request.url()).searchParams)
    }
  })
  await page.getByLabel('Aggregation', { exact: true }).selectOption('maximum')
  await expect(ticks(page, 'Air temperature')).toHaveText(['14', '6'])
  await expect(ticks(page, 'Precipitation')).toHaveText(['9', '5'])
  await expect(page.locator('.explore')).toContainText("highest value among the area's grid cells")
  expect(requested.map((params) => params.get('aggregation'))).toEqual(['maximum'])
  expect(requested[0].getAll('variable_id')).toEqual(['temperature', 'precipitation'])
})
