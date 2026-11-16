import { test, expect } from '@playwright/test'

test.use({ reducedMotion: 'reduce' })

async function januaryTwentyTenDaily(page) {
  await page.getByRole('slider', { name: 'Range start', exact: true }).fill('120')
  await page.getByRole('slider', { name: 'Range end', exact: true }).fill('120')
  await page.getByRole('group', { name: 'Time step', exact: true })
    .getByRole('button', { name: 'Daily', exact: true }).click()
}

async function openSahel(page) {
  await page.goto('/')
  await expect(page.locator('.globe-viewport canvas')).toBeVisible()
  await page.getByLabel('Region to explore', { exact: true }).selectOption('sahel')
  await expect(page.locator('.explore .chart')).toHaveCount(1)
  await januaryTwentyTenDaily(page)
  await page.getByRole('checkbox', { name: 'Precipitation', exact: true }).check()
}

// BS-006: native cells, first Variable, UTC slider, stable range, units, switch.
test('the Field map shows native cells on a fixed scale and changes Variable', async ({ page }) => {
  await openSahel(page)
  await page.getByRole('button', { name: 'Open Field map' }).click()
  await expect(page.getByLabel('Field map Variable')).toHaveValue('temperature')
  await expect(page.getByLabel('Field map legend')).toContainText('-3 to 15 °C')
  await expect(page.getByText('2010-01-01', { exact: true })).toBeVisible()
  await page.getByText('Cell values', { exact: true }).click()
  await expect(page.locator('.field-map tbody tr')).toHaveCount(4)
  await expect(page.locator('.field-map tbody tr').first()).toContainText('-3 °C')
  const globe = page.locator('.globe-viewport canvas')
  await expect(globe).toBeVisible()
  const first = await globe.screenshot()
  await page.getByRole('slider', { name: 'Field map time' }).focus()
  await page.keyboard.press('ArrowRight')
  await expect(page.getByText('2010-01-02', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Field map legend')).toContainText('-3 to 15 °C')
  await expect(page.locator('.field-map tbody tr').first()).toContainText('12 °C')
  await page.waitForTimeout(500)
  expect((await globe.screenshot()).equals(first)).toBe(false)
  await page.getByLabel('Field map Variable').selectOption('precipitation')
  await expect(page.getByLabel('Field map legend')).toContainText('24 to 24 mm/day')
})

// BS-014: Selected area over land and ocean, through the same map view.
test('cells without valid data remain uncoloured with a no data swatch', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.globe-viewport canvas')).toBeVisible()
  await page.getByText('Or type its edges in degrees').click()
  for (const [label, value] of [['West', '-1'], ['South', '14'], ['East', '4'], ['North', '16']]) {
    await page.getByLabel(label, { exact: true }).fill(value)
  }
  await page.getByRole('button', { name: 'Use these edges' }).click()
  await page.getByRole('button', { name: 'Explore this area' }).click()
  await januaryTwentyTenDaily(page)
  await page.getByRole('checkbox', { name: 'Air temperature', exact: true }).uncheck()
  await page.getByRole('checkbox', { name: 'Soil moisture', exact: true }).check()
  await page.getByRole('button', { name: 'Open Field map' }).click()
  await expect(page.getByLabel('Field map legend')).toContainText('3 to 5 mm')
  await expect(page.getByLabel('Field map legend')).toContainText('no data')
  await page.getByText('Cell values', { exact: true }).click()
  const rows = page.locator('.field-map tbody tr')
  await expect(rows).toHaveCount(4)
  await expect(rows.nth(2)).toContainText('no data')
  await expect(rows.nth(3)).toContainText('no data')
  await expect(rows.nth(2).locator('.field-cell-swatch')).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)')
  await expect(rows.nth(0)).toContainText('3 mm')
})

// A Field map is drawn from NASA grids; vegetation index has none, so it is not offered.
test('the Field map offers only Variables that have NASA grids', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Region to explore', { exact: true }).selectOption('sahel')
  await expect(page.locator('.explore .chart')).toHaveCount(1)
  await page.getByRole('checkbox', { name: 'Vegetation index (NDVI)', exact: true }).check()
  await page.getByRole('button', { name: 'Open Field map' }).click()
  const offered = await page.getByLabel('Field map Variable').locator('option').evaluateAll(
    (options) => options.map((option) => option.value),
  )
  expect(offered).toEqual(['temperature'])
})
