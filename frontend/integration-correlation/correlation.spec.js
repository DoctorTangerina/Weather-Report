import { test, expect } from '@playwright/test'

// #60–#62 S3 against the real API. tests/correlation_app.py adds deterministic
// acquired results (a missing month, a constant input, a failed Quality gate,
// daily inputs and an acquired Selected area across 180°) to the seed set. No
// response is intercepted and nothing is downloaded.
test.use({ reducedMotion: 'reduce' })

const inputs = page => page.getByRole('list', { name: 'Correlation inputs' }).getByRole('listitem')
const matrix = page => page.getByRole('table', { name: 'Pearson correlation matrix' })
const rowLabels = page => matrix(page).locator('tbody th').allTextContents()

async function open(page) {
  await page.goto('/#explore')
  await expect(page.getByRole('heading', { name: 'Correlation map', exact: true })).toBeVisible()
}

async function add(page, area, variables) {
  await page.getByLabel('Area with acquired data').selectOption({ label: area })
  for (const name of variables) await page.getByRole('checkbox', { name, exact: true }).check()
  await page.getByRole('button', { name: 'Add selected Variables' }).click()
}

async function period(page, start, end) {
  await page.getByLabel('Analysis start').fill(start)
  await page.getByLabel('Analysis end').fill(end)
}

async function build(page) {
  const response = page.waitForResponse(r => r.url().endsWith('/api/correlation-map') && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Build correlation map', exact: true }).click()
  return response
}

test('several Variables per area and different Variables across areas keep their order', async ({ page }) => {
  await open(page)
  await add(page, 'Sahel', ['Air temperature', 'Precipitation'])
  await add(page, 'Amazon Basin', ['Air temperature', 'Soil moisture'])
  await expect(inputs(page)).toHaveCount(4)
  await period(page, '2010-01-01', '2010-12-31')
  expect((await build(page)).status()).toBe(200)
  await expect(matrix(page)).toBeVisible()
  expect(await rowLabels(page)).toEqual([
    'Air temperature — Sahel',
    'Precipitation — Sahel',
    'Air temperature — Amazon Basin',
    'Soil moisture — Amazon Basin',
  ])
  await expect(page.getByText('12 observations · monthly · UTC')).toBeVisible()
})

test('a prepared Derived series keeps its name and shows its sources and processing history', async ({ page }) => {
  await open(page)
  await add(page, 'Sahel', ['Air temperature', 'Precipitation'])
  await page.getByText('Add a prepared calculation', { exact: true }).click()
  await page.getByLabel('Calculation name').fill('Scaled temperature A')
  await page.getByLabel('Calculation type').selectOption('minmax')
  await page.getByLabel('Expression or input ID').fill('input_0')
  await page.getByRole('button', { name: 'Add prepared calculation', exact: true }).click()
  await period(page, '2010-01-01', '2010-12-31')
  expect((await build(page)).status()).toBe(200)
  expect(await rowLabels(page)).toEqual(['Air temperature — Sahel', 'Precipitation — Sahel', 'Scaled temperature A'])
  const history = page.locator('.correlation-result details')
  await history.getByText('Sources and processing history').click()
  await expect(history).toContainText('"operation": "minmax"')
  await expect(history).toContainText('MERRA-2')
})

test('missing and constant inputs leave the others in the map, with a popup and explanations below it', async ({ page }) => {
  await open(page)
  await add(page, 'Sahel', ['Air temperature', 'Precipitation'])
  await add(page, 'Amazon Basin', ['Vegetation index (NDVI)'])
  await add(page, 'Congo Basin', ['Vegetation index (NDVI)'])
  await add(page, 'Sahara', ['Soil moisture'])
  await period(page, '2010-01-01', '2010-12-31')
  expect((await build(page)).status()).toBe(200)
  const popup = page.getByRole('alertdialog')
  await expect(popup).toContainText('Vegetation index (NDVI) — Amazon Basin')
  await expect(popup).toContainText('Choose another period or Variable')
  await page.getByRole('button', { name: 'Dismiss missing-data message' }).click()
  expect(await rowLabels(page)).toEqual(['Air temperature — Sahel', 'Precipitation — Sahel'])
  const excluded = page.getByRole('region', { name: 'Excluded inputs' })
  await expect(excluded).toContainText('Vegetation index (NDVI) — Amazon Basin: Not enough data')
  await expect(excluded).toContainText('Vegetation index (NDVI) — Congo Basin: This Variable is constant')
  await expect(excluded).toContainText('Soil moisture — Sahara: This Variable failed the source Quality gate')
})

for (const [retained, areas] of [
  [1, [['Sahel', ['Air temperature']], ['Amazon Basin', ['Vegetation index (NDVI)']]]],
  [0, [['Congo Basin', ['Vegetation index (NDVI)']], ['Amazon Basin', ['Vegetation index (NDVI)']]]],
]) {
  test(`${retained} retained input asks for revised selections and shows no heatmap`, async ({ page }) => {
    await open(page)
    for (const [area, variables] of areas) await add(page, area, variables)
    await period(page, '2010-01-01', '2010-12-31')
    expect((await build(page)).status()).toBe(422)
    await expect(page.getByRole('alert')).toContainText('Choose at least two usable inputs.')
    await expect(page.getByRole('region', { name: 'Excluded inputs' })).toContainText('Vegetation index (NDVI) — Amazon Basin')
    await expect(matrix(page)).toHaveCount(0)
  })
}

test('a Selected area without acquired coverage is explained, left unchanged and can be redrawn', async ({ page }) => {
  await open(page)
  await page.getByText('Or type its edges in degrees').click()
  const edges = async (button, values) => {
    for (const [name, value] of Object.entries(values)) await page.getByRole('spinbutton', { name, exact: true }).fill(String(value))
    await page.getByRole('button', { name: button, exact: true }).click()
  }
  await edges('Use these edges', { West: 0, South: 0, East: 10, North: 10 })
  await page.getByLabel('Use my Selected area').check()
  await page.getByLabel('Area name').fill('Gulf of Guinea')
  for (const name of ['Air temperature', 'Precipitation']) await page.getByRole('checkbox', { name, exact: true }).check()
  await page.getByRole('button', { name: 'Add selected Variables' }).click()
  await period(page, '2010-01-01', '2010-12-31')
  expect((await build(page)).status()).toBe(422)
  const excluded = page.getByRole('region', { name: 'Excluded inputs' })
  await expect(excluded).toContainText('Air temperature — Gulf of Guinea: No acquired data covers this selection')
  await expect(excluded).toContainText('the area was not changed')
  await expect(page.locator('.area-summary')).toContainText('0° to 10°N, 0° to 10°E')

  // Redraw across 180°, where data were acquired, and rebuild.
  await edges('Use these edges', { West: 170, South: -10, East: -170, North: 10 })
  await page.getByRole('button', { name: 'Remove Air temperature — Gulf of Guinea' }).click()
  await page.getByRole('button', { name: 'Remove Precipitation — Gulf of Guinea' }).click()
  await page.getByLabel('Area name').fill('Pacific')
  for (const name of ['Air temperature', 'Precipitation']) await page.getByRole('checkbox', { name, exact: true }).check()
  await page.getByRole('button', { name: 'Add selected Variables' }).click()
  expect((await build(page)).status()).toBe(200)
  expect(await rowLabels(page)).toEqual(['Air temperature — Pacific', 'Precipitation — Pacific'])
})

test('a map is not requested without a common analysis period', async ({ page }) => {
  await open(page)
  let requests = 0
  page.on('request', r => { if (r.url().endsWith('/api/correlation-map')) requests++ })
  await add(page, 'Sahel', ['Air temperature', 'Precipitation'])
  await page.getByLabel('Analysis start').fill('')
  await page.getByRole('button', { name: 'Build correlation map', exact: true }).click()
  expect(await page.getByLabel('Analysis start').evaluate(input => input.validity.valueMissing)).toBe(true)
  await page.waitForTimeout(500)
  expect(requests).toBe(0)
  await expect(matrix(page)).toHaveCount(0)
})

test('matching daily inputs keep daily resolution without resampling', async ({ page }) => {
  await open(page)
  await add(page, 'Iberia', ['Air temperature', 'Precipitation'])
  for (const label of ['Air temperature — Iberia', 'Precipitation — Iberia']) {
    await page.getByLabel(`Source Time step for ${label}`).selectOption('daily')
  }
  await period(page, '2010-01-01', '2010-01-31')
  const response = await build(page)
  expect(response.status()).toBe(200)
  expect((await response.json()).data.settings.time_step).toBe('daily')
  await expect(page.getByText('31 observations · daily · UTC')).toBeVisible()
})

test('daily and monthly inputs need an explicit common Time step and keep the Series’ own Aggregation', async ({ page }) => {
  await open(page)
  await add(page, 'Iberia', ['Air temperature'])
  await add(page, 'Sahel', ['Precipitation'])
  await page.getByLabel('Source Time step for Air temperature — Iberia').selectOption('daily')
  await period(page, '2010-01-01', '2010-12-31')

  expect((await build(page)).status()).toBe(422)
  await expect(page.getByRole('alert')).toContainText('Choose an explicit common Time step or change the selected inputs.')
  await expect(matrix(page)).toHaveCount(0)

  // A different Aggregation is refused, not silently applied.
  await page.getByLabel('Aggregation for Air temperature — Iberia').selectOption('mean')
  await page.getByLabel('Common output Time step').selectOption('monthly')
  expect((await build(page)).status()).toBe(422)
  await expect(page.getByRole('region', { name: 'Excluded inputs' })).toContainText("Choose this Series' own Aggregation")

  await page.getByLabel('Aggregation for Air temperature — Iberia').selectOption('maximum')
  const response = await build(page)
  expect(response.status()).toBe(200)
  const { data } = await response.json()
  expect(data.inputs[0].metadata.resampling).toMatchObject({ source_frequency: 'day', frequency: 'month', aggregation: 'max', timezone: 'UTC' })
  await expect(page.getByText('12 observations · monthly · UTC')).toBeVisible()
  expect(await rowLabels(page)).toEqual(['Air temperature — Iberia', 'Precipitation — Sahel'])
})
