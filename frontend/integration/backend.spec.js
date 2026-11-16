import { test, expect } from '@playwright/test'

// These checks use the real FastAPI server and committed NASA seed, without
// intercepting API responses or requiring a NASA download.
// #114: Compare and Become a Detective each have their own Region pickers.
const compare = (page) => page.locator('#panel-compare')
const detective = (page) => page.locator('#panel-detective')

test('selected Regions load real comparisons and open their own investigation', async ({ page, request }) => {
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  const response = await request.get('/api/discoveries')
  expect(response.ok()).toBe(true)
  const { data: discoveries } = await response.json()
  const discovery = discoveries.find((item) =>
    item.region_ids.includes('amazon-basin') && item.region_ids.includes('sahel'),
  )
  expect(discovery).toBeTruthy()
  await page.goto('/#compare')
  await expect(compare(page).getByLabel('First Region', { exact: true })).toHaveValue('')
  await expect(compare(page).getByLabel('Second Region', { exact: true })).toHaveValue('')
  await expect(page.locator('.globe-label')).toHaveCount(0)
  await compare(page).getByLabel('First Region', { exact: true }).selectOption('amazon-basin')
  const comparison = page.waitForResponse((r) => r.url().includes('/api/comparison'))
  await compare(page).getByLabel('Second Region', { exact: true }).selectOption('sahel')
  const comparisonResponse = await comparison
  expect(comparisonResponse.ok()).toBe(true)
  const { data: compared } = await comparisonResponse.json()
  expect(compared.series.map((item) => item.region_id)).toEqual(['amazon-basin', 'sahel'])
  await expect(page.locator('.explorer .chart')).toHaveCount(2)
  await page.getByRole('tab', { name: 'Become a Detective' }).click()
  await detective(page).getByLabel('First Region', { exact: true }).selectOption('amazon-basin')
  await detective(page).getByLabel('Second Region', { exact: true }).selectOption('sahel')
  await detective(page).getByRole('button', { name: /Become a Detective/ }).click()
  await expect(page.getByRole('heading', { name: discovery.narrative.investigation.steps[0].question, exact: true })).toBeVisible()
  await expect(page.locator('.globe-label')).toHaveText(['Amazon Basin', 'Sahel'])
  await expect(page.getByLabel('Select month', { exact: true })).toBeDisabled()
  expect(errors).toEqual([])
})

test('real Surprise Me → Detective → How do we know uses preloaded Series and preserves the globe', async ({ page }) => {
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/#surprise')
  const canvas = page.locator('.globe-viewport canvas')
  await expect(canvas).toBeVisible()
  await canvas.evaluate((node) => { window.integrationGlobeCanvas = node })
  const surprise = page.waitForResponse((r) => r.url().includes('/api/discoveries/surprise'))
  const series = page.waitForResponse((r) => new URL(r.url()).pathname === '/api/series')
  await page.locator('#panel-surprise').getByRole('button', { name: /Surprise Me!/ }).click()
  const response = await surprise
  expect(response.ok()).toBe(true)
  const { data: discovery } = await response.json()
  const seriesResponse = await series
  expect(seriesResponse.ok()).toBe(true)
  expect((await seriesResponse.json()).provenance).toBe('preloaded')
  await expect(page.getByRole('heading', { name: discovery.narrative.question, exact: true })).toBeVisible()
  await expect(page.locator('.globe-label')).toHaveCount(2)
  await page.getByRole('button', { name: 'Become a Detective', exact: true }).click()
  await page.getByRole('button', { name: discovery.narrative.investigation.steps[0].options[0].label, exact: true }).click()
  await page.getByRole('button', { name: 'Check the data' }).click()
  await expect(page.locator('.sidebar .chart')).toHaveCount(2)
  await page.getByText('How do we know?', { exact: true }).click()
  await expect(page.getByText(`Period analyzed: ${discovery.period.start} to ${discovery.period.end}.`, { exact: true })).toBeVisible()
  await expect(page.getByText(/Method paper:/)).toBeVisible()
  expect(await canvas.evaluate((node) => node === window.integrationGlobeCanvas)).toBe(true)
  expect(errors).toEqual([])
})
