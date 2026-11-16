import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'

const seed = (path) => JSON.parse(readFileSync(new URL(`../../data/${path}`, import.meta.url)))
const catalog = seed('catalog.json')
const source = seed('seed/series/sahel__temperature.json')

test.use({ locale: 'pt-BR' })

for (const width of [1440, 390]) {
test(`Explore timeline stays compact and requests the chosen period at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1000 })
  await page.clock.install()
  const requests = []
  let release
  const pending = new Promise((resolve) => { release = resolve })
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    let data
    if (url.pathname === '/api/catalog') data = catalog
    else if (url.pathname === '/api/discoveries') data = []
    else if (url.pathname === '/api/series/available') data = [source]
    else if (url.pathname === '/api/explore/options') data = { latest_month: '2025-02', area_variable_ids: ['temperature'], time_steps: [
      { time_step: 'monthly', variable_ids: ['temperature'] },
      { time_step: 'daily', variable_ids: ['temperature'], max_months: 120, limit: '10 years' },
      { time_step: '3-hourly', variable_ids: ['temperature'], max_months: 12, limit: '1 year' },
    ] }
    else if (url.pathname === '/api/explore/series') {
      requests.push(url)
      await pending
      if (url.searchParams.get('time_step') !== 'monthly') {
        return route.fulfill({ status: 501, json: { error: { code: 'not_available_yet', message: 'Only monthly Series are available so far.' } } })
      }
      const start = url.searchParams.get('period_start')
      const end = url.searchParams.get('period_end')
      const index = (month) => Number(month.slice(0, 4)) * 12 + Number(month.slice(5))
      data = { series: [{ ...source, period: { start, end }, values: source.values.slice(index(start) - index(source.period.start), index(end) - index(source.period.start) + 1) }] }
    } else return route.fulfill({ status: 404, json: {} })
    await route.fulfill({ json: { data } })
  })
  await page.goto('/#explore')
  await page.getByLabel('Region to explore', { exact: true }).selectOption('sahel')
  await expect.poll(() => requests.length).toBe(1)
  // The Explore tab shows its timeline once a place is open.
  const initialHeight = (await page.locator('.timeline-panel').boundingBox()).height
  await expect(page.getByRole('group', { name: 'Period', exact: true })).toHaveCount(0)
  const start = page.getByRole('slider', { name: 'Range start', exact: true })
  const end = page.getByRole('slider', { name: 'Range end', exact: true })
  await expect(start).toBeEnabled()
  await expect(page.locator('.timeline-endpoints')).toHaveText('2000-012025-02')
  await page.clock.pauseAt(await page.evaluate(() => Date.now() + 10000))
  await start.fill('120')
  await page.clock.runFor(100)
  expect(requests).toHaveLength(1)
  await end.fill('131')
  await page.clock.runFor(350)
  await expect.poll(() => requests.at(-1).searchParams.get('period_end')).toBe('2010-12')
  expect(requests.at(-1).searchParams.get('period_start')).toBe('2010-01')
  expect(requests).toHaveLength(2)
  release()
  await expect(page.locator('.explore .chart')).toHaveCount(1)
  await expect(page.locator('.timeline-endpoints')).toHaveText('2000-012025-02')
  await expect(page.getByLabel('Selected timestamp', { exact: true })).toContainText('2010-01')
  await expect(page.getByRole('button', { name: 'Show full period' })).toHaveCount(0)
  await expect(page.locator('.timeline-panel select')).toHaveCount(0)
  const choices = page.getByRole('group', { name: 'Time step', exact: true })
  const headingBox = await page.getByRole('heading', { name: 'Time series', exact: true }).boundingBox()
  const choicesBox = await choices.boundingBox()
  expect(Math.abs(headingBox.y - choicesBox.y)).toBeLessThan(8)
  expect(choicesBox.x).toBeGreaterThan(headingBox.x + headingBox.width)
  expect((await page.locator('.timeline-panel').boundingBox()).height).toBeLessThanOrEqual(initialHeight + 6)
  await page.locator('.timeline-panel').screenshot({ path: `test-results/explore-timeline-${width}.png` })
  await expect(page.locator('.explore input[type=month]')).toHaveCount(0)
  await expect(page.locator('.explore select')).toHaveCount(1)
  await expect(page.locator('.timeline-start-label')).toHaveText('From 2010-01')
  await expect(page.locator('.timeline-end-label')).toHaveText('To 2010-12')
  const fromBox = await page.locator('.timeline-start-label').boundingBox()
  const toBox = await page.locator('.timeline-end-label').boundingBox()
  const railBox = await page.locator('.timeline-range-rail').boundingBox()
  // "From" ends at the start handle and "To" begins at the end handle, so they never overlap.
  expect(Math.abs(fromBox.x + fromBox.width - (railBox.x + railBox.width * 120 / 301))).toBeLessThan(3)
  expect(Math.abs(toBox.x - (railBox.x + railBox.width * 131 / 301))).toBeLessThan(3)
  expect(fromBox.x + fromBox.width).toBeLessThanOrEqual(toBox.x + 0.5)
  const timestampBox = await page.getByLabel('Selected timestamp', { exact: true }).boundingBox()
  expect(Math.abs(timestampBox.x + timestampBox.width / 2 - width / 2)).toBeLessThan(3)
  expect(choicesBox.x + choicesBox.width <= timestampBox.x || timestampBox.x + timestampBox.width <= choicesBox.x).toBe(true)
  const normalHeight = (await page.locator('.timeline-panel').boundingBox()).height
  await expect(start).toHaveValue('120')
  await expect(end).toHaveValue('131')
  await expect(page.locator('.timeline-endpoints')).toHaveText('2000-012025-02')
  await expect(start).toHaveAttribute('aria-valuetext', '2010-01')
  expect(requests).toHaveLength(2)

  // Both caps are inclusive and are checked before contacting the API.
  await end.fill('120')
  await start.fill('0')
  await choices.getByRole('button', { name: 'Daily', exact: true }).click()
  await expect(page.locator('.timeline-panel [role="status"]')).toHaveText('Daily periods are limited to 10 years.')
  const errorBox = await page.locator('.timeline-period-error').boundingBox()
  const speedBox = await page.getByRole('group', { name: 'Playback speed' }).boundingBox()
  expect(errorBox.x).toBeGreaterThan(speedBox.x + speedBox.width)
  expect(errorBox.y).toBeLessThan(speedBox.y + speedBox.height)
  expect(errorBox.y + errorBox.height).toBeGreaterThan(speedBox.y)
  expect((await page.locator('.timeline-panel').boundingBox()).height).toBe(normalHeight)
  await page.locator('.timeline-panel').screenshot({ path: `test-results/explore-timeline-error-${width}.png` })
  await page.clock.runFor(400)
  expect(requests).toHaveLength(2)
  await end.fill('119')
  await page.clock.runFor(350)
  await expect.poll(() => requests.at(-1).searchParams.get('time_step')).toBe('daily')
  await expect(page.locator('.explore [role="status"]')).toContainText('Only monthly Series are available so far.')
  await expect(page.locator('.explore .chart')).toHaveCount(0)
  await choices.getByRole('button', { name: '3-hourly', exact: true }).click()
  await expect(page.locator('.timeline-panel [role="status"]')).toHaveText('3-hourly periods are limited to 1 year.')
  const before = requests.length
  await page.clock.runFor(400)
  expect(requests).toHaveLength(before)
  await end.fill('12')
  await expect(page.locator('.timeline-panel [role="status"]')).toHaveText('3-hourly periods are limited to 1 year.')
  await page.clock.runFor(400)
  expect(requests).toHaveLength(before)
  await end.fill('11')
  await page.clock.runFor(350)
  await expect.poll(() => requests.at(-1).searchParams.get('time_step')).toBe('3-hourly')
  expect(requests.at(-1).searchParams.get('period_end')).toBe('2000-12')
})
}
