import { test, expect } from '@playwright/test'

// #79, Selected areas, against the real API. tests/explore_area_app.py stands in
// for NASA with a synthetic global grid. Reduced motion keeps the globe still, so
// a drag lands where it is aimed.
test.use({ reducedMotion: 'reduce' })

const summary = (page) => page.locator('.area-summary')
const areaLabel = (page) => page.locator('.globe-label-area')

async function drawOnGlobe(page, from, to) {
  await page.getByRole('button', { name: /Draw (an|a new) area/ }).click()
  const overlay = page.getByTestId('globe-draw')
  const box = await overlay.boundingBox()
  const at = ([dx, dy]) => [box.x + box.width / 2 + dx, box.y + box.height / 2 + dy]
  await page.mouse.move(...at(from))
  await page.mouse.down()
  await page.mouse.move(...at([(from[0] + to[0]) / 2, (from[1] + to[1]) / 2]), { steps: 4 })
  await page.mouse.move(...at(to), { steps: 4 })
  await page.mouse.up()
}

async function typeEdges(page, [west, south, east, north]) {
  await page.getByText('Or type its edges in degrees').click()
  for (const [label, value] of [['West', west], ['South', south], ['East', east], ['North', north]]) {
    await page.getByLabel(label, { exact: true }).fill(String(value))
  }
  await page.getByRole('button', { name: 'Use these edges' }).click()
}

const exploreRequests = (page) => {
  const urls = []
  page.on('request', (request) => {
    if (request.url().includes('/api/explore/series')) urls.push(new URL(request.url()))
  })
  return urls
}

test('drawing a rectangle on the globe creates a Selected area', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.welcome')).toBeVisible()
  await page.waitForTimeout(1500)
  await drawOnGlobe(page, [-80, -60], [80, 40])
  await expect(areaLabel(page)).toHaveText('Selected area')
  await expect(summary(page)).toContainText(/Selected area: \d+(\.\d+)?°[NS]? to \d+(\.\d+)?°[NS]?, /)
  await expect(page.getByTestId('globe-draw')).toHaveCount(0)
  // Distinguishable from catalog Regions, and never one of them.
  const regions = await page.getByLabel('Region to explore', { exact: true }).locator('option').allTextContents()
  expect(regions).not.toContain('Selected area')
})

test('drawing a new Selected area replaces the existing one', async ({ page }) => {
  await page.goto('/')
  await page.waitForTimeout(1500)
  await drawOnGlobe(page, [-80, -60], [80, 40])
  const first = await summary(page).textContent()
  await drawOnGlobe(page, [-30, -20], [30, 20])
  await expect(areaLabel(page)).toHaveCount(1)
  await expect(summary(page)).toHaveCount(1)
  await expect(summary(page)).not.toHaveText(first)
  // One rectangle, not the old one joined to the new: rectangles are listed with ';'.
  await expect(summary(page)).not.toContainText(';')
})

test('Escape stops drawing without making an area', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Draw an area' }).click()
  await expect(page.getByTestId('globe-draw')).toHaveCount(1)
  await page.keyboard.press('Escape')
  await expect(page.getByTestId('globe-draw')).toHaveCount(0)
  await expect(summary(page)).toHaveCount(0)
})

test('a Selected area does not survive a page reload', async ({ page }) => {
  await page.goto('/')
  await typeEdges(page, [0, 0, 20, 10])
  await expect(areaLabel(page)).toHaveCount(1)
  await page.reload()
  await expect(page.locator('.welcome')).toBeVisible()
  await expect(areaLabel(page)).toHaveCount(0)
  await expect(summary(page)).toHaveCount(0)
})

test('a Selected area may cross the antimeridian from 170°E to 170°W', async ({ page }) => {
  const requests = exploreRequests(page)
  await page.goto('/')
  await typeEdges(page, [170, -10, -170, 10])
  await expect(summary(page)).toContainText('Selected area: 10°S to 10°N, 170°E to 170°W')
  await expect(areaLabel(page)).toHaveText('Selected area')
  await page.getByRole('button', { name: 'Explore this area' }).click()
  await expect(page.locator('.explore .chart')).toHaveCount(1)
  expect(requests.at(-1).searchParams.getAll('rectangle')).toEqual(['170,-10,-170,10'])
})

test('a Selected area opens the same view as a Region, with stacked charts', async ({ page }) => {
  const requests = exploreRequests(page)
  await page.goto('/')
  await typeEdges(page, [0, 0, 30, 20])
  await page.getByRole('button', { name: 'Explore this area' }).click()
  await expect(page.getByRole('heading', { name: 'Selected area', exact: true })).toBeVisible()
  await page.getByRole('checkbox', { name: 'Precipitation', exact: true }).check()
  await expect(page.locator('.explore .chart')).toHaveCount(2)
  const last = requests.at(-1)
  expect(last.searchParams.getAll('variable_id')).toEqual(['temperature', 'precipitation'])
  expect(last.searchParams.get('region_id')).toBeNull()
  const axes = await page.locator('.explore .chart svg').evaluateAll((charts) =>
    charts.map((chart) => [...chart.querySelectorAll('.chart-time')].map((tick) => tick.textContent)),
  )
  expect(axes[0].length).toBeGreaterThan(0)
  expect(axes[1]).toEqual(axes[0])
  // The same choices as a Region's view: Variables, a period and its limits.
  await expect(page.getByLabel('From', { exact: true })).toHaveValue('2024-03')
  await expect(page.getByLabel('To', { exact: true })).toHaveValue('2025-02')
  await page.getByLabel('From', { exact: true }).fill('1999-12')
  await expect(page.locator('.explore [role="status"]').first()).toHaveText(
    'Periods run from 2000-01 to 2025-02, the latest available month.',
  )
  await expect(page.getByRole('checkbox', { name: /vegetation/i })).toHaveCount(0)
})

test('soil moisture over open ocean is shown as an Excluded series with its reason', async ({ page }) => {
  await page.goto('/')
  await typeEdges(page, [-40, -10, -20, 10])
  await page.getByRole('button', { name: 'Explore this area' }).click()
  await page.getByRole('checkbox', { name: 'Air temperature', exact: true }).uncheck()
  await page.getByRole('checkbox', { name: 'Soil moisture', exact: true }).check()
  // With no land there are no values either, so the gate gives both reasons.
  await expect(page.locator('.explore .notice').filter({ hasText: 'excluded' })).toContainText(
    'Soil moisture is excluded by the Quality gate for this period:',
  )
  await expect(page.locator('.explore .notice').filter({ hasText: 'excluded' })).toContainText(
    'less than half of the area is valid land',
  )
  await expect(page.locator('.explore .chart')).toHaveCount(0)
})
