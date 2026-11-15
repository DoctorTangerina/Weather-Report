import { test, expect } from '@playwright/test'

const catalog = {
  regions: [
    { region_id: 'sahel', name: 'Sahel', bbox: { west: -15, east: 25, south: 12, north: 18 }, variable_ids: ['temperature', 'precipitation'] },
    { region_id: 'amazon-basin', name: 'Amazon Basin', bbox: { west: -70, east: -50, south: -10, north: 2 }, variable_ids: ['temperature', 'soil-moisture'] },
  ],
  variables: [
    { variable_id: 'temperature', name: 'Temperature', definition: 'How warm.', units: 'K' },
    { variable_id: 'precipitation', name: 'Precipitation', definition: 'Rain.', units: 'mm' },
    { variable_id: 'soil-moisture', name: 'Soil moisture', definition: 'Water in soil.', units: '1' },
  ],
}

async function start(page, handler) {
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/correlation-map') return handler(route)
    const data = path === '/api/catalog' ? catalog : path === '/api/series/available' ? [] : { series: [], trends: [] }
    await route.fulfill({ json: { data, notice: null } })
  })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Correlation map', exact: true })).toBeVisible()
}

async function addPair(page) {
  await page.getByLabel('Area with acquired data').selectOption('sahel')
  await page.getByRole('checkbox', { name: 'Temperature', exact: true }).check()
  await page.getByRole('checkbox', { name: 'Precipitation', exact: true }).check()
  await page.getByRole('button', { name: 'Add selected Variables' }).click()
}

function result(request, extra = {}) {
  const inputs = request.variables.map(x => ({ ...x, label: x.label, metadata: { units: 'K' }, filled_count: 0 }))
  return { inputs, matrix: inputs.map((_, i) => inputs.map((_, j) => i === j ? 1 : 0.4)), observation_count: 3, settings: { period: request.period, time_step: 'monthly', timezone: 'UTC' }, excluded: [], warnings: [], ...extra }
}

test('independent selections, removal, duplicate prevention and numeric cell details', async ({ page }) => {
  let sent
  await start(page, async route => {
    sent = route.request().postDataJSON()
    await route.fulfill({ json: { data: result(sent), notice: null } })
  })
  await addPair(page)
  await addPair(page)
  await expect(page.getByRole('list', { name: 'Correlation inputs' }).getByRole('listitem')).toHaveCount(2)
  await page.getByLabel('Area with acquired data').selectOption('amazon-basin')
  await page.getByRole('checkbox', { name: 'Soil moisture', exact: true }).check()
  await page.getByRole('button', { name: 'Add selected Variables' }).click()
  await expect(page.getByRole('list', { name: 'Correlation inputs' }).getByRole('listitem')).toHaveCount(3)
  await page.getByRole('button', { name: 'Remove Soil moisture — Amazon Basin' }).click()
  await page.getByLabel('Analysis start').fill('2024-01-01')
  await page.getByLabel('Analysis end').fill('2024-03-31')
  await page.getByRole('button', { name: 'Build correlation map', exact: true }).click()
  await expect(page.getByRole('table', { name: 'Pearson correlation matrix' })).toBeVisible()
  expect(sent.variables.map(x => x.variable)).toEqual(['temperature', 'precipitation'])
  expect(sent.variables.every(x => !('values' in x))).toBeTruthy()
  expect(sent.period).toEqual({ start: '2024-01-01', end: '2024-03-31' })
  await page.getByRole('button', { name: 'Temperature — Sahel and Precipitation — Sahel: 0.4', exact: true }).click()
  await expect(page.getByRole('status', { name: 'Selected comparison' })).toContainText('0.4')
  await expect(page.getByText('Scale: −1 to +1')).toBeVisible()
})

test('excluded input popup, explanations, undefined cells and two-observation warning', async ({ page }) => {
  await start(page, async route => {
    const req = route.request().postDataJSON()
    await route.fulfill({ json: { data: result(req, {
      excluded: [{ id: 'missing', label: 'Soil moisture — Amazon Basin', code: 'incomplete_output_timeline', message: 'Not enough data. Choose another period or Variable.' }, { id: 'constant', label: 'Constant series', code: 'constant_input', message: 'This Variable is constant.' }],
      matrix: [[1, null], [null, 1]],
      warnings: [{ code: 'two_observations', message: 'Only two observations were used.' }],
    }), notice: null } })
  })
  await addPair(page)
  await page.getByRole('button', { name: 'Build correlation map', exact: true }).click()
  await expect(page.getByRole('alertdialog')).toContainText('Soil moisture — Amazon Basin')
  await page.getByRole('button', { name: 'Dismiss missing-data message' }).click()
  await expect(page.getByRole('region', { name: 'Excluded inputs' })).toContainText('constant')
  await expect(page.getByRole('region', { name: 'Undefined correlations' })).toBeVisible()
  await expect(page.getByText('Only two observations were used.')).toBeVisible()
  await expect(page.getByRole('button', { name: /: 0$/ })).toHaveCount(0)
})

test('resampling-required and resource errors preserve choices and clear old results', async ({ page }) => {
  let count = 0
  await start(page, async route => {
    const req = route.request().postDataJSON()
    count++
    if (count === 1) return route.fulfill({ status: 422, json: { error: { code: 'resampling_required', message: 'Choose an explicit common Time step or change the selected inputs.', details: {} } } })
    if (count === 2) return route.fulfill({ json: { data: result(req), notice: null } })
    await route.fulfill({ status: 503, json: { error: { code: 'resource_exhausted', message: 'Reduce the number of inputs and try again.', details: {} } } })
  })
  await addPair(page)
  await page.getByRole('button', { name: 'Build correlation map', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('common Time step')
  await page.getByLabel('Common output Time step').selectOption('monthly')
  await page.getByRole('button', { name: 'Build correlation map', exact: true }).click()
  await expect(page.getByRole('table', { name: 'Pearson correlation matrix' })).toBeVisible()
  await page.getByRole('button', { name: 'Build correlation map', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Reduce the number')
  await expect(page.getByRole('table', { name: 'Pearson correlation matrix' })).toHaveCount(0)
  await expect(page.getByRole('list', { name: 'Correlation inputs' }).getByRole('listitem')).toHaveCount(2)
})

test('joined antimeridian rectangles and prepared calculations send identifiers and instructions', async ({ page }) => {
  let sent
  await start(page, async route => {
    sent = route.request().postDataJSON()
    await route.fulfill({ json: { data: result(sent), notice: null } })
  })
  await addPair(page)
  await page.getByText('Add a prepared calculation', { exact: true }).click()
  await page.getByLabel('Calculation name').fill('Twice temperature')
  await page.getByLabel('Expression or input ID').fill('2 * input_0')
  await page.getByRole('button', { name: 'Add prepared calculation', exact: true }).click()
  await page.getByLabel('Choose my own rectangles').check()
  for (const [name, value] of Object.entries({ West: '170', East: '-170', South: '-10', North: '10' })) await page.getByRole('spinbutton', { name, exact: true }).fill(value)
  await page.getByRole('button', { name: 'Add rectangle', exact: true }).click()
  for (const [name, value] of Object.entries({ West: '10', East: '20', South: '-5', North: '5' })) await page.getByRole('spinbutton', { name, exact: true }).fill(value)
  await page.getByRole('button', { name: 'Add rectangle', exact: true }).click()
  await page.getByRole('checkbox', { name: 'Soil moisture', exact: true }).check()
  await page.getByRole('button', { name: 'Add selected Variables' }).click()
  await page.getByRole('button', { name: 'Build correlation map', exact: true }).click()
  await expect(page.getByRole('table', { name: 'Pearson correlation matrix' })).toBeVisible()
  expect(sent.derived[0].operations[0].expression).toBe('2 * input_0')
  expect(sent.variables.at(-1).area.rectangles).toEqual([{ west: 170, east: -170, south: -10, north: 10 }, { west: 10, east: 20, south: -5, north: 5 }])
  expect(sent.variables[2].label).toBe('Twice temperature')
})

test('too few retained inputs show reasons and no empty heatmap', async ({ page }) => {
  await start(page, route => route.fulfill({ status: 422, json: { error: { code: 'insufficient_inputs', message: 'Choose at least two usable inputs.', details: { excluded: [{ id: 'no-coverage', label: 'Temperature — missing area', code: 'area_unavailable', message: 'No coverage; redraw or choose another area.' }] } } } }))
  await addPair(page)
  await page.getByRole('button', { name: 'Build correlation map', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('two usable inputs')
  await expect(page.getByRole('region', { name: 'Excluded inputs' })).toContainText('redraw')
  await expect(page.getByRole('table', { name: 'Pearson correlation matrix' })).toHaveCount(0)
})

test('browser connects to the real API and computes a map from acquired catalog data', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Area with acquired data').selectOption('sahel')
  await page.getByRole('checkbox', { name: 'Air temperature', exact: true }).check()
  await page.getByRole('checkbox', { name: 'Precipitation', exact: true }).check()
  await page.getByRole('button', { name: 'Add selected Variables' }).click()
  await page.getByLabel('Analysis start').fill('2010-01-01')
  await page.getByLabel('Analysis end').fill('2010-12-31')
  const responsePromise = page.waitForResponse(response => response.url().endsWith('/api/correlation-map') && response.request().method() === 'POST')
  await page.getByRole('button', { name: 'Build correlation map', exact: true }).click()
  const response = await responsePromise
  expect(response.status()).toBe(200)
  const body = await response.json()
  expect(body.data.observation_count).toBe(12)
  expect(body.data.matrix[0][1]).toBeGreaterThan(-1)
  expect(body.data.matrix[0][1]).toBeLessThan(1)
  await expect(page.getByRole('table', { name: 'Pearson correlation matrix' })).toBeVisible()
  await expect(page.getByText('12 observations · monthly · UTC')).toBeVisible()
})

test('loading is visible and changing analysis settings cancels the pending map', async ({ page }) => {
  let pending
  await start(page, route => { pending = route })
  await addPair(page)
  await page.getByRole('button', { name: 'Build correlation map', exact: true }).click()
  await expect(page.getByText('Loading selected series and calculating correlations…')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Building correlation map…' })).toBeDisabled()
  await expect.poll(() => Boolean(pending)).toBeTruthy()
  const cancelled = page.waitForEvent('requestfailed', req => req.url().endsWith('/api/correlation-map'))
  await page.getByLabel('Analysis end').fill('2023-12-31')
  await cancelled
  await expect(page.getByRole('button', { name: 'Build correlation map', exact: true })).toBeEnabled()
  await expect(page.getByRole('table', { name: 'Pearson correlation matrix' })).toHaveCount(0)
  await expect(page.getByRole('list', { name: 'Correlation inputs' }).getByRole('listitem')).toHaveCount(2)
})
