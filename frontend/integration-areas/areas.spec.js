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
  await expect(page.getByRole('slider', { name: 'Range start', exact: true })).toHaveAttribute('aria-valuetext', '2024-03')
  await expect(page.getByRole('slider', { name: 'Range end', exact: true })).toHaveAttribute('aria-valuetext', '2025-02')
  await expect(page.locator('.timeline-endpoints')).toHaveText('2000-012025-02')
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

// #81: joined and resizable Selected areas.

const problem = (page) => page.locator('.area-problem')
const handle = (page, rectangle, name) =>
  page.locator(`.area-handle[data-rectangle="${rectangle}"][data-handle="${name}"]`)

// The rectangles the summary lists, as [west, south, east, north] in degrees.
async function listed(page) {
  const text = (await summary(page).locator('p').textContent()).replace(/^.*Selected area:\s*/, '')
  const degrees = (value) => {
    const [, number, hemisphere] = value.trim().match(/^([\d.]+)°([NSEW]?)$/)
    return Number(number) * (hemisphere === 'S' || hemisphere === 'W' ? -1 : 1)
  }
  return text.split(';').map((part) => {
    const [lats, lngs] = part.split(',')
    const [south, north] = lats.split(' to ').map(degrees)
    const [west, east] = lngs.split(' to ').map(degrees)
    return [west, south, east, north]
  })
}

async function addEdges(page, [west, south, east, north]) {
  for (const [label, value] of [['West', west], ['South', south], ['East', east], ['North', north]]) {
    await page.getByLabel(label, { exact: true }).fill(String(value))
  }
  await page.getByRole('button', { name: 'Add these edges' }).click()
}

async function dragBy(page, locator, [dx, dy]) {
  const box = await locator.boundingBox()
  const [x, y] = [box.x + box.width / 2, box.y + box.height / 2]
  await page.mouse.move(x, y)
  await page.mouse.down()
  await page.mouse.move(x + dx / 2, y + dy / 2, { steps: 4 })
  await page.mouse.move(x + dx, y + dy, { steps: 4 })
  await page.mouse.up()
}

async function drawAdded(page, from, to) {
  await page.getByRole('button', { name: 'Add a rectangle' }).click()
  const overlay = page.getByTestId('globe-draw')
  const box = await overlay.boundingBox()
  const at = ([dx, dy]) => [box.x + box.width / 2 + dx, box.y + box.height / 2 + dy]
  await page.mouse.move(...at(from))
  await page.mouse.down()
  await page.mouse.move(...at(to), { steps: 6 })
  await page.mouse.up()
}

test('a rectangle drawn over the Selected area joins it into one shape', async ({ page }) => {
  const requests = exploreRequests(page)
  await page.goto('/')
  await page.waitForTimeout(1500)
  await drawOnGlobe(page, [-80, -60], [40, 40])
  await drawAdded(page, [0, -20], [100, 80])
  await expect(problem(page)).toHaveCount(0)
  // One Selected area, one label, made of both rectangles.
  await expect(summary(page)).toHaveCount(1)
  await expect(areaLabel(page)).toHaveCount(1)
  const rectangles = await listed(page)
  expect(rectangles).toHaveLength(2)
  await page.getByRole('button', { name: 'Explore this area' }).click()
  await expect(page.locator('.explore .chart')).toHaveCount(1)
  expect(requests.at(-1).searchParams.getAll('rectangle')).toEqual(rectangles.map((box) => box.join(',')))
})

test('a rectangle that neither touches nor overlaps the Selected area is refused', async ({ page }) => {
  await page.goto('/')
  await page.waitForTimeout(1500)
  await drawOnGlobe(page, [-120, -60], [-60, -10])
  const before = await summary(page).textContent()
  await drawAdded(page, [40, 20], [110, 80])
  await expect(problem(page)).toContainText('Rectangles must touch or overlap')
  await expect(summary(page)).toHaveText(before)
  await expect(summary(page)).not.toContainText(';')
})

test('typed edges can join the Selected area across the antimeridian', async ({ page }) => {
  const requests = exploreRequests(page)
  await page.goto('/')
  await typeEdges(page, [170, -10, -170, 10])
  await addEdges(page, [-170, -10, -160, 10])
  await expect(summary(page)).toContainText(
    'Selected area: 10°S to 10°N, 170°E to 170°W; 10°S to 10°N, 170°W to 160°W',
  )
  await page.getByRole('button', { name: 'Explore this area' }).click()
  await expect(page.locator('.explore .chart')).toHaveCount(1)
  expect(requests.at(-1).searchParams.getAll('rectangle')).toEqual(['170,-10,-170,10', '-170,-10,-160,10'])
})

test('dragging a corner handle resizes that rectangle, and the view follows', async ({ page }) => {
  const requests = exploreRequests(page)
  await page.goto('/')
  await typeEdges(page, [0, 0, 30, 20])
  await page.getByRole('button', { name: 'Explore this area' }).click()
  await expect(page.locator('.explore .chart')).toHaveCount(1)
  await expect(handle(page, 0, 'ne')).toBeVisible()
  await dragBy(page, handle(page, 0, 'ne'), [60, -60])
  const [[west, south, east, north]] = await listed(page)
  expect([west, south]).toEqual([0, 0])
  expect(east).toBeGreaterThan(30)
  expect(north).toBeGreaterThan(20)
  // The Selected area covers the rectangle at its new size.
  await expect.poll(() => requests.at(-1)?.searchParams.getAll('rectangle')).toEqual([
    [west, south, east, north].join(','),
  ])
  await expect(page.locator('.explore .chart')).toHaveCount(1)
})

test('dragging an edge handle moves only that edge', async ({ page }) => {
  await page.goto('/')
  await typeEdges(page, [0, 0, 30, 20])
  await expect(handle(page, 0, 'e')).toBeVisible()
  await dragBy(page, handle(page, 0, 'e'), [60, 30])
  const [[west, south, east, north]] = await listed(page)
  expect([west, south, north]).toEqual([0, 0, 20])
  expect(east).toBeGreaterThan(30)
  await dragBy(page, handle(page, 0, 's'), [-30, 60])
  const [[, lower, right]] = await listed(page)
  expect(lower).toBeLessThan(0)
  expect(right).toEqual(east)
})

test('a resize that would part the Selected area is held back', async ({ page }) => {
  await page.goto('/')
  // Taller than the second, so its east handle is clear of the second's west one.
  await typeEdges(page, [0, 0, 10, 20])
  await addEdges(page, [10, 0, 20, 10])
  const before = await summary(page).textContent()
  await expect(handle(page, 1, 'w')).toBeVisible()
  // Pulling the second rectangle's west edge east of 10°E parts it from the first.
  await dragBy(page, handle(page, 1, 'w'), [40, 0])
  await expect(problem(page)).toContainText('Rectangles must touch or overlap')
  await expect(summary(page)).toHaveText(before)
})

test('a resize handle can be moved with the keyboard and keeps focus', async ({ page }) => {
  await page.goto('/')
  await typeEdges(page, [0, 0, 20, 10])
  await expect(summary(page)).toContainText('0° to 10°N, 0° to 20°E')
  const east = page.getByRole('button', { name: /^Resize the east edge of rectangle 1/ })
  await east.focus()
  await page.keyboard.press('ArrowRight')
  await page.keyboard.press('ArrowRight')
  await page.keyboard.press('Shift+ArrowRight')
  await expect(summary(page)).toContainText('0° to 10°N, 0° to 27°E')
  await expect(page.getByRole('button', { name: /^Resize the east edge of rectangle 1/ })).toBeFocused()
  await page.getByRole('button', { name: /^Resize the north edge of rectangle 1/ }).focus()
  await page.keyboard.press('ArrowDown')
  await expect(summary(page)).toContainText('0° to 9°N, 0° to 27°E')
})
