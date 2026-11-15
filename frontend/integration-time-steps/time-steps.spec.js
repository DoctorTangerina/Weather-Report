import { test, expect } from '@playwright/test'

// #80 / BS-002 and BS-003: one Time step for the whole Explore My World view,
// through the real API. The fake (tests/explore_time_step_app.py) serves hourly
// Sahel grids: temperature is the day of the month, precipitation 1 mm an hour.
// Monthly 2010-01 comes from the seed set; finer Time steps go through a job.
const charts = (page) => page.locator('.explore .chart')
const chart = (page, name) => page.locator('.explore .chart', { hasText: name })
const chooseTimeStep = (page, step) => page.getByRole('group', { name: 'Time step', exact: true })
  .getByRole('button', { name: step === '3-hourly' ? step : step[0].toUpperCase() + step.slice(1), exact: true }).click()
const chooseMonth = (page, boundary, month) => page.getByRole('slider', { name: `Range ${boundary}`, exact: true })
  .fill(String((Number(month.slice(0, 4)) - 2000) * 12 + Number(month.slice(5, 7)) - 1))

async function openSahel(page) {
  await page.goto('/')
  await page.getByLabel('Region to explore', { exact: true }).selectOption('sahel')
  await expect(charts(page)).toHaveCount(1)
}

async function showTemperatureAndPrecipitation(page, start = '2010-01', end = '2010-01') {
  await openSahel(page)
  await chooseMonth(page, 'start', start)
  await chooseMonth(page, 'end', end)
  await page.getByRole('checkbox', { name: 'Precipitation', exact: true }).check()
  await expect(charts(page)).toHaveCount(2)
}

function recordSeriesRequests(page) {
  const requested = []
  page.on('request', (request) => {
    if (request.url().includes('/api/explore/series')) requested.push(new URL(request.url()).searchParams)
  })
  return requested
}

for (const [timeStep, unit, count] of [
  ['3-hourly', '3 hours', 248],
  ['daily', 'day', 31],
  ['monthly', 'month', 1],
]) {
  test(`choosing the Time step "${timeStep}" rebuilds every chart at that Time step`, async ({ page }) => {
    await showTemperatureAndPrecipitation(page)
    if (timeStep === 'monthly') {
      // Leave monthly and come back, so the choice is a real change.
      await chooseTimeStep(page, 'daily')
      await expect(chart(page, 'Air temperature').getByRole('img')).toHaveAttribute('aria-label', /per day/)
    }
    await chooseTimeStep(page, timeStep)
    for (const name of ['Air temperature', 'Precipitation']) {
      await expect(chart(page, name).getByRole('img')).toHaveAttribute(
        'aria-label',
        new RegExp(`one value per ${unit}, ${count} values? `),
      )
    }
  })
}

test('daily values are drawn from the API, with daily totals of precipitation', async ({ page }) => {
  await showTemperatureAndPrecipitation(page)
  await chooseTimeStep(page, 'daily')
  const ticks = (name) => chart(page, name).locator('text.chart-tick:not(.chart-time)')
  await expect(ticks('Air temperature')).toHaveText(['31', '1'])
  await expect(ticks('Precipitation')).toHaveText(['24', '24'])
  await expect(chart(page, 'Precipitation')).toContainText('mm/day')
})

for (const [timeStep, limit, start, end] of [
  ['3-hourly', '1 year', '2010-01', '2011-01'],
  ['daily', '10 years', '2000-01', '2010-12'],
]) {
  test(`a ${timeStep} period longer than ${limit} is refused before any data is requested`, async ({ page }) => {
    await openSahel(page)
    await chooseMonth(page, 'start', '2010-01')
    await chooseMonth(page, 'end', '2010-01')
    await chooseTimeStep(page, timeStep)
    await expect(charts(page)).toHaveCount(1)
    const requested = recordSeriesRequests(page)
    await chooseMonth(page, 'start', start)
    await chooseMonth(page, 'end', end)
    const label = timeStep === 'daily' ? 'Daily' : '3-hourly'
    await expect(page.locator('.timeline-panel [role="status"]')).toContainText(
      `${label} periods are limited to ${limit}.`,
    )
    await page.waitForTimeout(500)
    expect(requested).toEqual([])
    await expect(charts(page)).toHaveCount(0)
  })
}

test('the view explains UTC days and the caps before any data is requested', async ({ page }) => {
  await openSahel(page)
  const view = page.locator('.explore')
  await expect(view).toContainText('Days and 3-hour intervals follow UTC.')
  await expect(view).toContainText('3-hourly periods are limited to 1 year and daily periods to 10 years.')
})

test('a Variable without data at the chosen Time step is not offered', async ({ page }) => {
  await openSahel(page)
  await chooseTimeStep(page, 'daily')
  await expect(page.getByRole('checkbox', { name: /vegetation/i })).toHaveCount(0)
  await expect(page.getByRole('checkbox', { name: 'Air temperature', exact: true })).toBeVisible()
})

test('changing the Time step removes a chosen Variable without data at it, with a note', async ({ page }) => {
  await openSahel(page)
  await chooseMonth(page, 'start', '2010-01')
  await chooseMonth(page, 'end', '2010-01')
  await page.getByRole('checkbox', { name: /vegetation/i }).check()
  await expect(charts(page)).toHaveCount(2)
  await chooseTimeStep(page, 'daily')
  await expect(page.locator('.explore')).toContainText(
    'Vegetation index (NDVI) was removed: it has no daily data.',
  )
  await expect(charts(page)).toHaveCount(1)
  await expect(chart(page, 'Air temperature')).toBeVisible()
  // Removed, not hidden: going back to monthly does not bring it back.
  await chooseTimeStep(page, 'monthly')
  await expect(page.getByRole('checkbox', { name: /vegetation/i })).not.toBeChecked()
  await expect(charts(page)).toHaveCount(1)
})

test('progress is shown while daily data is fetched, until the chart appears', async ({ page }) => {
  await openSahel(page)
  await chooseMonth(page, 'start', '2010-03')
  await chooseMonth(page, 'end', '2010-03')
  await chooseTimeStep(page, 'daily')
  await expect(page.getByRole('progressbar')).toBeVisible()
  await expect(charts(page)).toHaveCount(1)
  await expect(page.getByRole('progressbar')).toHaveCount(0)
  await expect(chart(page, 'Air temperature').getByRole('img')).toHaveAttribute('aria-label', /per day, 31 values/)
})

test('a failed fetch says which Series could not be obtained', async ({ page }) => {
  await openSahel(page)
  await chooseMonth(page, 'start', '2010-02')
  await chooseMonth(page, 'end', '2010-02')
  await chooseTimeStep(page, 'daily')
  await expect(page.getByRole('progressbar')).toBeVisible()
  const status = page.locator('.explore [role="status"]')
  await expect(status).toContainText('The Series could not be obtained')
  await expect(status).toContainText('Not obtained: Air temperature.')
  await expect(charts(page)).toHaveCount(0)
})
