import { test, expect } from '@playwright/test'

// #75, Explore My World for a catalog Region, against the real API and the
// committed seed set, with Amazon vegetation omitted by the isolated API
// harness to exercise unavailable Variables. Reduced motion keeps the globe
// from turning, so a Region stays where the pointer found it.
test.use({ reducedMotion: 'reduce' })

const exploreRequests = (page) => {
  const urls = []
  page.on('request', (request) => {
    if (request.url().includes('/api/explore/series')) urls.push(new URL(request.url()))
  })
  return urls
}

// Move up from the globe's centre until the hover label names the Region.
async function clickRegionOnGlobe(page, name) {
  const canvas = page.locator('.globe-viewport canvas')
  await expect(canvas).toBeVisible()
  const box = await canvas.boundingBox()
  const tooltip = page.locator('.float-tooltip-kap')
  for (let dy = 0; dy <= 150; dy += 4) {
    const x = box.x + box.width / 2
    const y = box.y + box.height / 2 - dy
    await page.mouse.move(x, y)
    if ((await tooltip.textContent().catch(() => null))?.trim() === name) {
      await page.mouse.click(x, y)
      return
    }
  }
  throw new Error(`${name} was not found on the globe`)
}

async function openFromSidebar(page, regionId) {
  await page.goto('/')
  await page.getByLabel('Region to explore', { exact: true }).selectOption(regionId)
  await expect(page.locator('.explore')).toBeVisible()
}

test('clicking Sahel on the globe opens its Explore My World view', async ({ page }) => {
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  await expect(page.locator('.welcome')).toBeVisible()
  await page.waitForTimeout(1500)
  await clickRegionOnGlobe(page, 'Sahel')
  await expect(page.getByRole('heading', { name: 'Sahel', exact: true })).toBeVisible()
  await expect(page.locator('.explore .eyebrow')).toHaveText('Explore My World')
  await expect(page.locator('.globe-label')).toHaveText(['Sahel'])
  await expect(page.locator('.explore .chart')).toHaveCount(1)
  expect(errors).toEqual([])
})

test('three chosen Variables are three stacked charts on one time axis', async ({ page }) => {
  const requests = exploreRequests(page)
  await openFromSidebar(page, 'sahel')
  for (const name of ['Air temperature', 'Precipitation', 'Soil moisture']) {
    await page.getByRole('checkbox', { name, exact: true }).check()
  }
  await expect(page.locator('.explore .chart')).toHaveCount(3)
  const last = requests.at(-1)
  expect(last.searchParams.getAll('variable_id')).toEqual(['temperature', 'precipitation', 'soil-moisture'])

  const axes = await page.locator('.explore .chart svg').evaluateAll((charts) =>
    charts.map((chart) =>
      [...chart.querySelectorAll('.chart-time')].map((tick) => `${tick.textContent}@${tick.getAttribute('x')}`),
    ),
  )
  expect(axes[0].length).toBeGreaterThan(0)
  expect(axes[1]).toEqual(axes[0])
  expect(axes[2]).toEqual(axes[0])
  // Every value drawn comes from the API: no browser-side smoothing line.
  await expect(page.locator('.explore .chart-mean')).toHaveCount(0)
})

test('a shorter period is requested from the API and shared by every chart', async ({ page }) => {
  const requests = exploreRequests(page)
  await openFromSidebar(page, 'sahel')
  await page.getByRole('checkbox', { name: 'Precipitation', exact: true }).check()
  await expect(page.locator('.explore .chart')).toHaveCount(2)
  await page.getByLabel('From', { exact: true }).fill('2010-01')
  await page.getByLabel('To', { exact: true }).fill('2010-12')
  await expect.poll(() => requests.at(-1)?.searchParams.get('period_end')).toBe('2010-12')
  expect(requests.at(-1).searchParams.get('period_start')).toBe('2010-01')
  await expect(page.locator('.explore .chart')).toHaveCount(2)
  for (const chart of await page.locator('.explore .chart svg').all()) {
    await expect(chart.locator('.chart-time')).toHaveText(['Jan 2010', 'Apr', 'Jul', 'Oct'])
  }
})

test('a period starting before 2000-01 is refused without a request', async ({ page }) => {
  const requests = exploreRequests(page)
  await openFromSidebar(page, 'sahel')
  await expect(page.locator('.explore .chart')).toHaveCount(1)
  const before = requests.length
  await page.getByLabel('From', { exact: true }).fill('1999-12')
  await expect(page.locator('.explore [role="status"]')).toHaveText(
    /Periods run from 2000-01 to \d{4}-\d{2}, the latest available month\./,
  )
  await page.waitForTimeout(500)
  expect(requests.length).toBe(before)
  await expect(page.locator('.explore .chart')).toHaveCount(0)
})

test('Variables without data are not offered, and Back returns to the welcome', async ({ page }) => {
  // The seed set holds every Series the catalog lists, so this test removes one
  // from the real API's answer: the Amazon Basin's vegetation index.
  await page.route('**/api/series/available', async (route) => {
    const response = await route.fetch()
    const body = await response.json()
    body.data = body.data.filter(
      (series) => !(series.region_id === 'amazon-basin' && series.variable_id === 'vegetation-index'),
    )
    await route.fulfill({ response, json: body })
  })
  await openFromSidebar(page, 'amazon-basin')
  await expect(page.getByRole('checkbox')).toHaveCount(3)
  await expect(page.getByRole('checkbox', { name: /vegetation/i })).toHaveCount(0)
  await expect(page.locator('.explore')).toContainText('No data yet for vegetation index (ndvi).')
  await page.getByRole('button', { name: '← Back' }).click()
  await expect(page.locator('.welcome')).toBeVisible()
})
