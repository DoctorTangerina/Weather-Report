import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'

// #114: one tab per tool, behind the tab registry. Reduced motion keeps the
// globe still, so a Region stays where the pointer found it.
test.use({ reducedMotion: 'reduce' })

const seed = (path) => JSON.parse(readFileSync(new URL(`../../data/${path}`, import.meta.url)))
const catalog = seed('catalog.json')
const discovery = seed('seed/discoveries/amazon-basin--antarctic-peninsula.json')
const TABS = ['Start', 'Surprise Me!', 'Become a Detective', 'Explore My World', 'Compare Regions']

test.beforeEach(async ({ page }) => {
  page.errors = []
  page.on('pageerror', (error) => page.errors.push(error.message))
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    let data
    if (url.pathname === '/api/catalog') data = catalog
    else if (url.pathname === '/api/discoveries') data = [discovery]
    else if (url.pathname === '/api/discoveries/surprise') data = discovery
    else if (url.pathname === '/api/series/available') data = []
    else if (url.pathname === '/api/explore/options') data = { latest_month: null, area_variable_ids: [] }
    else if (url.pathname === '/api/series') {
      data = seed(`seed/series/${url.searchParams.get('region_id')}__${url.searchParams.get('variable_id')}.json`)
    } else if (url.pathname === '/api/comparison') {
      data = {
        series: ['region_a', 'region_b'].map((key) => seed(`seed/series/${url.searchParams.get(key)}__${url.searchParams.get('variable_id')}.json`)),
        trends: discovery.contrasts[0].trends,
      }
    } else return route.fulfill({ status: 404, json: { error: { code: 'unexpected_request' } } })
    await route.fulfill({ json: { data, notice: null } })
  })
})

test.afterEach(async ({ page }) => {
  expect(page.errors).toEqual([])
})

const tab = (page, name) => page.getByRole('tab', { name, exact: true })
const panel = (page, id) => page.locator(`#panel-${id}`)

// Move up from the globe's centre until the hover label names the Region.
async function clickRegionOnGlobe(page, name) {
  const box = await page.locator('.globe-viewport canvas').boundingBox()
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

test('the five tabs show in order with Start open, and no Home button', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('tab')).toHaveText(TABS)
  await expect(tab(page, 'Start')).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByRole('tabpanel')).toHaveCount(1)
  await expect(panel(page, 'start')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Home', exact: true })).toHaveCount(0)
  // Start lists the other tools from the registry and opens them.
  await panel(page, 'start').getByRole('button', { name: /Compare Regions/ }).click()
  await expect(tab(page, 'Compare Regions')).toHaveAttribute('aria-selected', 'true')
  await expect(panel(page, 'compare')).toBeVisible()
})

test('the URL hash opens a tab, an unknown one opens Start, and switching adds no history', async ({ page }) => {
  await page.goto('/#compare')
  await expect(tab(page, 'Compare Regions')).toHaveAttribute('aria-selected', 'true')
  const entries = await page.evaluate(() => history.length)
  await tab(page, 'Explore My World').click()
  await expect(page).toHaveURL(/#explore$/)
  await tab(page, 'Become a Detective').click()
  await expect(page).toHaveURL(/#detective$/)
  expect(await page.evaluate(() => history.length)).toBe(entries)
  await page.goto('/#nope')
  await expect(tab(page, 'Start')).toHaveAttribute('aria-selected', 'true')
})

test('the tab bar follows the WAI-ARIA tabs keyboard pattern', async ({ page }) => {
  await page.goto('/')
  await tab(page, 'Start').focus()
  await page.keyboard.press('ArrowDown')
  await expect(tab(page, 'Surprise Me!')).toBeFocused()
  await expect(tab(page, 'Surprise Me!')).toHaveAttribute('aria-selected', 'true')
  await page.keyboard.press('End')
  await expect(tab(page, 'Compare Regions')).toBeFocused()
  await page.keyboard.press('ArrowDown')
  await expect(tab(page, 'Start')).toBeFocused()
  await page.keyboard.press('ArrowUp')
  await expect(tab(page, 'Compare Regions')).toBeFocused()
  await page.keyboard.press('Home')
  await expect(tab(page, 'Start')).toBeFocused()
  // Only the selected tab is in the Tab order, so Tab moves into its panel.
  await page.keyboard.press('Tab')
  await expect(panel(page, 'start')).toBeFocused()
})

test('each tab keeps its state when switching away and back, until reload', async ({ page }) => {
  await page.goto('/#compare')
  await panel(page, 'compare').getByLabel('First Region', { exact: true }).selectOption('amazon-basin')
  await panel(page, 'compare').getByLabel('Second Region', { exact: true }).selectOption('antarctic-peninsula')
  await expect(panel(page, 'compare').locator('.chart')).toHaveCount(2)
  await tab(page, 'Surprise Me!').click()
  await panel(page, 'surprise').getByRole('button', { name: /Surprise Me!/ }).click()
  await expect(page.getByRole('heading', { name: discovery.narrative.question, exact: true })).toBeVisible()
  await expect(page.locator('.session-count')).toHaveText('1 Discovery seen')
  await tab(page, 'Compare Regions').click()
  await expect(panel(page, 'compare').getByLabel('First Region', { exact: true })).toHaveValue('amazon-basin')
  await expect(panel(page, 'compare').locator('.chart')).toHaveCount(2)
  await tab(page, 'Surprise Me!').click()
  await expect(page.getByRole('heading', { name: discovery.narrative.question, exact: true })).toBeVisible()
  await page.reload()
  await expect(tab(page, 'Surprise Me!')).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByRole('heading', { name: discovery.narrative.question, exact: true })).toHaveCount(0)
  await expect(page.locator('.session-count')).toHaveCount(0)
})

test('the globe and timeline show only the active tab', async ({ page }) => {
  await page.goto('/#compare')
  await panel(page, 'compare').getByLabel('First Region', { exact: true }).selectOption('amazon-basin')
  await panel(page, 'compare').getByLabel('Second Region', { exact: true }).selectOption('antarctic-peninsula')
  await expect(page.locator('.globe-label')).toHaveCount(2)
  await expect(page.locator('.timeline-panel')).toHaveCount(1)
  await tab(page, 'Start').click()
  await expect(page.locator('.globe-label')).toHaveCount(0)
  await expect(page.locator('.timeline-panel')).toHaveCount(0)
  await expect(page.locator('.globe-hint')).toHaveText('Drag to turn · Scroll or pinch to zoom')
  await tab(page, 'Explore My World').click()
  await expect(page.locator('.globe-hint')).toHaveText('Click a Region to explore it · Drag to turn · Scroll or pinch to zoom')
  await tab(page, 'Compare Regions').click()
  await expect(page.locator('.globe-label')).toHaveText(['Amazon Basin', 'Antarctic Peninsula'])
})

test('clicking a Region fills the next empty slot in Become a Detective', async ({ page }) => {
  await page.goto('/#detective')
  const first = panel(page, 'detective').getByLabel('First Region', { exact: true })
  await expect(first).toHaveValue('')
  await page.waitForTimeout(1500)
  await clickRegionOnGlobe(page, 'Sahel')
  await expect(first).toHaveValue('sahel')
  await expect(panel(page, 'detective').getByLabel('Second Region', { exact: true })).toHaveValue('')
  await expect(page.locator('.globe-label')).toHaveText(['Sahel'])
})

test('Regions are not clickable in Start', async ({ page }) => {
  await page.goto('/')
  await page.waitForTimeout(1500)
  await expect(clickRegionOnGlobe(page, 'Sahel')).rejects.toThrow('Sahel was not found on the globe')
})

test('loading and an unreachable API replace the sidebar with no tab bar', async ({ page }) => {
  let answer
  await page.route('**/api/catalog', (route) => { answer = route })
  await page.goto('/')
  await expect(page.locator('.sidebar')).toHaveAttribute('aria-busy', 'true')
  await expect(page.getByRole('tablist')).toHaveCount(0)
  await answer.fulfill({ status: 500, json: { error: { code: 'internal' } } })
  await expect(page.getByRole('heading', { name: 'The Discovery engine is not answering.' })).toBeVisible()
  await expect(page.getByRole('tablist')).toHaveCount(0)
  await page.unroute('**/api/catalog')
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(page.getByRole('tab')).toHaveCount(TABS.length)
})

test('the tab bar is a horizontal row at mobile width', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  const tablist = page.getByRole('tablist')
  await expect(tablist).toHaveAttribute('aria-orientation', 'horizontal')
  const [start, surprise] = await Promise.all([tab(page, 'Start').boundingBox(), tab(page, 'Surprise Me!').boundingBox()])
  expect(Math.abs(start.y - surprise.y)).toBeLessThan(1)
  expect(surprise.x).toBeGreaterThan(start.x)
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBe(0)
})
