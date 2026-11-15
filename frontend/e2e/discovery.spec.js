import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'

const seed = (path) => JSON.parse(readFileSync(new URL(`../../data/${path}`, import.meta.url)))
const catalog = seed('catalog.json')
const discovery = seed('seed/discoveries/amazon-basin--antarctic-peninsula.json')
const selectedDiscovery = seed('seed/discoveries/amazon-basin--sahel.json')

test.beforeEach(async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    let data
    if (url.pathname === '/api/catalog') data = catalog
    else if (url.pathname === '/api/discoveries') data = [discovery, selectedDiscovery]
    else if (url.pathname === '/api/series/available') data = []
    else if (url.pathname === '/api/discoveries/surprise') {
      await new Promise((resolve) => setTimeout(resolve, 300))
      data = discovery
    } else if (url.pathname === '/api/series') {
      data = seed(`seed/series/${url.searchParams.get('region_id')}__${url.searchParams.get('variable_id')}.json`)
    } else if (url.pathname === '/api/comparison') {
      data = {
        series: ['region_a', 'region_b'].map((key) => seed(`seed/series/${url.searchParams.get(key)}__${url.searchParams.get('variable_id')}.json`)),
        trends: (url.searchParams.get('region_b') === 'sahel' ? selectedDiscovery : discovery).contrasts[0].trends,
      }
    } else return route.fulfill({ status: 404, json: { error: { code: 'unexpected_request' } } })
    await route.fulfill({ json: { data, notice: null } })
  })
})

test('welcome waits for the student to select Regions', async ({ page }) => {
  const comparisons = []
  page.on('request', (request) => {
    if (request.url().includes('/api/comparison')) comparisons.push(request.url())
  })
  await page.goto('/')
  await expect(page.getByLabel('First Region', { exact: true })).toHaveValue('')
  await expect(page.getByLabel('Second Region', { exact: true })).toHaveValue('')
  await expect(page.locator('.globe-label')).toHaveCount(0)
  expect(comparisons).toEqual([])
  await page.getByLabel('First Region', { exact: true }).selectOption('amazon-basin')
  await expect(page.locator('.globe-label')).toHaveCount(1)
  await expect(page.getByLabel('Second Region', { exact: true })).toHaveValue('')
  await page.getByLabel('Second Region', { exact: true }).selectOption('antarctic-peninsula')
  await page.getByLabel('Variable', { exact: true }).selectOption('temperature')
  await expect(page.locator('.explorer .chart')).toHaveCount(2)
  await expect(page.locator('.globe-label')).toHaveCount(2)
})

test('Become a Detective can start directly from welcome', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /Become a Detective/ }).click()
  await expect(page.getByRole('heading', { name: discovery.narrative.investigation.steps[0].question, exact: true })).toBeVisible()
  await expect(page.locator('.globe-label')).toHaveCount(2)
  await expect(page.getByLabel('Select month', { exact: true })).toBeDisabled()
})

test('Become a Detective investigates the selected Regions instead of drawing a random pair', async ({ page }) => {
  const randomDraws = []
  page.on('request', (request) => {
    if (request.url().includes('/api/discoveries/surprise')) randomDraws.push(request.url())
  })
  await page.goto('/')
  await page.getByLabel('First Region', { exact: true }).selectOption('amazon-basin')
  await page.getByLabel('Second Region', { exact: true }).selectOption('sahel')
  await page.getByRole('button', { name: /Become a Detective/ }).click()
  await expect(page.getByRole('heading', { name: selectedDiscovery.narrative.investigation.steps[0].question, exact: true })).toBeVisible()
  await expect(page.locator('.globe-label')).toHaveText(['Amazon Basin', 'Sahel'])
  expect(randomDraws).toEqual([])
})

test('a pair without a Discovery stays selected and explains why the investigation cannot start', async ({ page }) => {
  await page.route('**/api/discoveries', (route) => route.fulfill({ json: { data: [], notice: null } }))
  await page.goto('/')
  await page.getByLabel('First Region', { exact: true }).selectOption('amazon-basin')
  await page.getByLabel('Second Region', { exact: true }).selectOption('sahel')
  await page.getByRole('button', { name: /Become a Detective/ }).click()
  await expect(page.getByRole('alert')).toHaveText(/There is no Discovery to investigate for these Regions yet/)
  await expect(page.getByLabel('First Region', { exact: true })).toHaveValue('amazon-basin')
  await expect(page.getByLabel('Second Region', { exact: true })).toHaveValue('sahel')
})

test('checking an unavailable Discovery keeps the welcome page and charts mounted', async ({ page }) => {
  await page.route('**/api/discoveries', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 400))
    await route.fulfill({ json: { data: [], notice: null } })
  })
  await page.goto('/')
  await page.getByLabel('First Region', { exact: true }).selectOption('amazon-basin')
  await page.getByLabel('Second Region', { exact: true }).selectOption('sahel')
  await expect(page.locator('.explorer .chart')).toHaveCount(2)
  await page.locator('.welcome').evaluate((node) => { window.originalWelcome = node })
  await page.getByRole('button', { name: /Become a Detective/ }).click()
  expect(await page.evaluate(() => window.originalWelcome.isConnected)).toBe(true)
  await expect(page.getByLabel('First Region', { exact: true })).toBeDisabled()
  await expect(page.locator('.explorer .chart')).toHaveCount(2)
  await expect(page.getByRole('alert')).toHaveText(/There is no Discovery to investigate/)
  expect(await page.locator('.welcome').evaluate((node) => node === window.originalWelcome)).toBe(true)
  await expect(page.getByLabel('First Region', { exact: true })).toBeEnabled()
})

test('one selected Region asks for a second Region before investigating', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('First Region', { exact: true }).selectOption('amazon-basin')
  await page.getByRole('button', { name: /Become a Detective/ }).click()
  await expect(page.getByRole('alert')).toHaveText('Choose a second Region to investigate this pair.')
  await expect(page.getByLabel('First Region', { exact: true })).toHaveValue('amazon-basin')
})

test('Surprise Me! → Become a Detective → How do we know? keeps the globe mounted', async ({ page }) => {
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  const canvas = page.locator('.globe-viewport canvas')
  await expect(canvas).toBeVisible()
  await canvas.evaluate((node) => { window.originalGlobeCanvas = node })
  await page.getByRole('button', { name: /Surprise Me!/ }).click()
  await expect(page.getByRole('heading', { name: discovery.narrative.question, exact: true })).toBeVisible()
  await expect(page.locator('.globe-label')).toHaveCount(2)
  await page.getByRole('button', { name: 'Become a Detective', exact: true }).click()
  await page.getByRole('button', { name: discovery.narrative.investigation.steps[0].options[0].label, exact: true }).click()
  await page.getByRole('button', { name: 'Check the data' }).click()
  await page.getByText('How do we know?', { exact: true }).click()
  await expect(page.getByText(`Period analyzed: ${discovery.period.start} to ${discovery.period.end}.`, { exact: true })).toBeVisible()
  await expect(page.getByText(/Method paper:/)).toBeVisible()
  await page.getByRole('button', { name: 'Back', exact: false }).click()
  const globeSize = await canvas.boundingBox()
  await page.evaluate(() => {
    window.lostRegionLabels = false
    window.labelObserver = new MutationObserver(() => {
      if (document.querySelectorAll('.globe-label').length !== 2) window.lostRegionLabels = true
    })
    window.labelObserver.observe(document.querySelector('.globe-viewport'), { childList: true, subtree: true })
  })
  await page.getByRole('button', { name: 'Surprise me again' }).click()
  await expect(page.getByText('Searching the planet', { exact: true })).toBeVisible()
  expect(await canvas.boundingBox()).toEqual(globeSize)
  await expect(page.locator('.globe-label')).toHaveCount(2)
  await expect(page.getByRole('heading', { name: discovery.narrative.question, exact: true })).toBeVisible()
  expect(await page.evaluate(() => {
    window.labelObserver.disconnect()
    return window.lostRegionLabels
  })).toBe(false)
  expect(await canvas.evaluate((node) => node === window.originalGlobeCanvas)).toBe(true)
  expect(errors).toEqual([])
})

test('Earth textures load from the app with external network blocked', async ({ page }) => {
  await page.route(/^https?:\/\/(?!127\.0\.0\.1:4173)/, (route) => route.abort())
  const earth = page.waitForResponse('**/textures/earth-blue-marble.jpg')
  const topology = page.waitForResponse('**/textures/earth-topology.png')
  await page.goto('/')
  expect((await earth).ok()).toBe(true)
  expect((await topology).ok()).toBe(true)
  await expect(page.locator('.globe-viewport canvas')).toBeVisible()
})
