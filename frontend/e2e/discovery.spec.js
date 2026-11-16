import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'

const seed = (path) => JSON.parse(readFileSync(new URL(`../../data/${path}`, import.meta.url)))
const catalog = seed('catalog.json')
const discovery = seed('seed/discoveries/amazon-basin--antarctic-peninsula.json')
const selectedDiscovery = seed('seed/discoveries/amazon-basin--sahel.json')

test.beforeEach(async ({ page }) => {
  page.globeErrors = []
  page.on('pageerror', (error) => page.globeErrors.push(error.message))
  page.on('console', (message) => {
    if (/Maximum update depth|Too many re-renders|WebGL.*CONTEXT_LOST/i.test(message.text())) {
      page.globeErrors.push(message.text())
    }
  })
  await page.addInitScript(() => {
    window.globeContextLosses = 0
    document.addEventListener('webglcontextlost', () => { window.globeContextLosses += 1 }, true)
  })
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    let data
    if (url.pathname === '/api/catalog') data = catalog
    else if (url.pathname === '/api/discoveries') data = [discovery, selectedDiscovery]
    else if (url.pathname === '/api/series/available') data = []
    else if (url.pathname === '/api/explore/options') data = { latest_month: null, area_variable_ids: [] }
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

test.afterEach(async ({ page }) => {
  expect(page.globeErrors).toEqual([])
  expect(await page.evaluate(() => window.globeContextLosses)).toBe(0)
})

// #114: every tool has its own tab; the same field labels appear in more than
// one tab, so each flow scopes its fields to its tab's panel.
const compare = (page) => page.locator('#panel-compare')
const detective = (page) => page.locator('#panel-detective')
const surprise = (page) => page.locator('#panel-surprise')

test('Compare waits for the student to select Regions', async ({ page }) => {
  const comparisons = []
  page.on('request', (request) => {
    if (request.url().includes('/api/comparison')) comparisons.push(request.url())
  })
  await page.goto('/#compare')
  await expect(compare(page).getByLabel('First Region', { exact: true })).toHaveValue('')
  await expect(compare(page).getByLabel('Second Region', { exact: true })).toHaveValue('')
  await expect(page.locator('.globe-label')).toHaveCount(0)
  expect(comparisons).toEqual([])
  await compare(page).getByLabel('First Region', { exact: true }).selectOption('amazon-basin')
  await expect(page.locator('.globe-label')).toHaveCount(1)
  await expect(compare(page).getByLabel('Second Region', { exact: true })).toHaveValue('')
  await compare(page).getByLabel('Second Region', { exact: true }).selectOption('antarctic-peninsula')
  await compare(page).getByLabel('Variable', { exact: true }).selectOption('temperature')
  await expect(page.locator('.explorer .chart')).toHaveCount(2)
  await expect(page.locator('.globe-label')).toHaveCount(2)
})

test('Become a Detective lets the engine pick a pair when none is chosen', async ({ page }) => {
  await page.goto('/#detective')
  await detective(page).getByRole('button', { name: /Become a Detective/ }).click()
  await expect(page.getByRole('heading', { name: discovery.narrative.investigation.steps[0].question, exact: true })).toBeVisible()
  await expect(page.locator('.globe-label')).toHaveCount(2)
  await expect(page.getByLabel('Select month', { exact: true })).toBeDisabled()
})

test('Become a Detective investigates the selected Regions instead of drawing a random pair', async ({ page }) => {
  const randomDraws = []
  page.on('request', (request) => {
    if (request.url().includes('/api/discoveries/surprise')) randomDraws.push(request.url())
  })
  await page.goto('/#detective')
  await detective(page).getByLabel('First Region', { exact: true }).selectOption('amazon-basin')
  await detective(page).getByLabel('Second Region', { exact: true }).selectOption('sahel')
  await detective(page).getByRole('button', { name: /Become a Detective/ }).click()
  await expect(page.getByRole('heading', { name: selectedDiscovery.narrative.investigation.steps[0].question, exact: true })).toBeVisible()
  await expect(page.locator('.globe-label')).toHaveText(['Amazon Basin', 'Sahel'])
  expect(randomDraws).toEqual([])
})

test('a pair without a Discovery stays selected and explains why the investigation cannot start', async ({ page }) => {
  await page.route('**/api/discoveries', (route) => route.fulfill({ json: { data: [], notice: null } }))
  await page.goto('/#detective')
  await detective(page).getByLabel('First Region', { exact: true }).selectOption('amazon-basin')
  await detective(page).getByLabel('Second Region', { exact: true }).selectOption('sahel')
  await detective(page).getByRole('button', { name: /Become a Detective/ }).click()
  await expect(page.getByRole('alert')).toHaveText(/There is no Discovery to investigate for these Regions yet/)
  await expect(detective(page).getByLabel('First Region', { exact: true })).toHaveValue('amazon-basin')
  await expect(detective(page).getByLabel('Second Region', { exact: true })).toHaveValue('sahel')
})

test('checking an unavailable Discovery keeps the Detective panel mounted', async ({ page }) => {
  await page.route('**/api/discoveries', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 400))
    await route.fulfill({ json: { data: [], notice: null } })
  })
  await page.goto('/#detective')
  await detective(page).getByLabel('First Region', { exact: true }).selectOption('amazon-basin')
  await detective(page).getByLabel('Second Region', { exact: true }).selectOption('sahel')
  const panel = detective(page).locator('.welcome')
  await panel.evaluate((node) => { window.originalDetective = node })
  await detective(page).getByRole('button', { name: /Become a Detective/ }).click()
  expect(await page.evaluate(() => window.originalDetective.isConnected)).toBe(true)
  await expect(detective(page).getByLabel('First Region', { exact: true })).toBeDisabled()
  await expect(page.getByRole('alert')).toHaveText(/There is no Discovery to investigate/)
  expect(await panel.evaluate((node) => node === window.originalDetective)).toBe(true)
  await expect(detective(page).getByLabel('First Region', { exact: true })).toBeEnabled()
})

test('one selected Region asks for a second Region before investigating', async ({ page }) => {
  await page.goto('/#detective')
  await detective(page).getByLabel('First Region', { exact: true }).selectOption('amazon-basin')
  await detective(page).getByRole('button', { name: /Become a Detective/ }).click()
  await expect(page.getByRole('alert')).toHaveText('Choose a second Region to investigate this pair.')
  await expect(detective(page).getByLabel('First Region', { exact: true })).toHaveValue('amazon-basin')
})

test('Surprise Me! → Become a Detective → How do we know? keeps the globe mounted', async ({ page }) => {
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/#surprise')
  const canvas = page.locator('.globe-viewport canvas')
  await expect(canvas).toBeVisible()
  await canvas.evaluate((node) => { window.originalGlobeCanvas = node })
  await surprise(page).getByRole('button', { name: /Surprise Me!/ }).click()
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


test('timeline handles filter charts inclusively and constrain playback', async ({ page }) => {
  // With no series yet (Compare before a pair is chosen) the range is disabled.
  await page.goto('/#compare')
  const start = page.getByRole('slider', { name: 'Range start', exact: true })
  const end = page.getByRole('slider', { name: 'Range end', exact: true })
  await expect(start).toBeDisabled()
  await page.getByRole('tab', { name: 'Surprise Me!' }).click()
  await surprise(page).getByRole('button', { name: /Surprise Me!/ }).click()
  await expect(start).toBeEnabled()
  const max = Number(await end.getAttribute('max'))
  const rail = await page.locator('.timeline-range-rail').boundingBox()
  await page.mouse.move(rail.x, rail.y + rail.height / 2)
  await page.mouse.down()
  await page.mouse.move(rail.x + rail.width / 4, rail.y + rail.height / 2, { steps: 8 })
  await page.mouse.up()
  expect(Number(await start.inputValue())).toBeGreaterThan(0)
  await start.press('Home')
  await page.mouse.move(rail.x + rail.width, rail.y + rail.height / 2)
  await page.mouse.down()
  await page.mouse.move(rail.x + rail.width * 3 / 4, rail.y + rail.height / 2, { steps: 8 })
  await page.mouse.up()
  expect(Number(await end.inputValue())).toBeLessThan(max)
  await end.press('End')
  const playhead = page.getByLabel('Select month', { exact: true })
  await page.mouse.click(rail.x + rail.width / 4, rail.y + rail.height / 2)
  expect(Math.abs(Number(await playhead.inputValue()) - max / 4)).toBeLessThanOrEqual(1)
  await page.mouse.move(rail.x + rail.width / 4, rail.y + rail.height / 2)
  await page.mouse.down()
  await page.mouse.move(rail.x + rail.width / 2, rail.y + rail.height / 2, { steps: 8 })
  await page.mouse.up()
  expect(Math.abs(Number(await playhead.inputValue()) - max / 2)).toBeLessThanOrEqual(1)
  await start.focus()
  await start.press('ArrowRight')
  await expect(start).toHaveValue('1')
  const cursorBeforeExpanding = await playhead.inputValue()
  await start.press('ArrowLeft')
  await expect(playhead).toHaveValue(cursorBeforeExpanding)
  await start.press('ArrowRight')
  await expect(playhead).toHaveValue(cursorBeforeExpanding)
  const first = await start.getAttribute('aria-valuetext')
  await end.focus()
  await end.press('ArrowLeft')
  const last = await end.getAttribute('aria-valuetext')
  await expect(end).toHaveValue(String(max - 1))
  for (const chart of await page.locator('.chart svg').all()) {
    await expect(chart).toHaveAttribute('aria-label', new RegExp(`from ${first} to ${last}`))
  }
  const month = page.getByLabel('Select month', { exact: true })
  await expect(month).toHaveAttribute('min', '1')
  await expect(month).toHaveAttribute('max', String(max - 1))
  await end.press('Home')
  await expect(end).toHaveValue('1')
  await expect(month).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Play time series' })).toBeDisabled()
  // Crossing is clamped; either boundary can still expand the range again.
  await start.press('End')
  await expect(start).toHaveValue('1')
  await start.press('Home')
  await expect(start).toHaveValue('0')
  await page.getByRole('button', { name: 'Play time series' }).click()
  await expect(month).toHaveValue('1')
  await expect(page.getByRole('button', { name: 'Play time series' })).toBeVisible()
})


for (const view of ['Surprise Me!', 'Explore', 'Investigation']) {
  test(`timeline updates keep Region labels stable in ${view}`, async ({ page }) => {
    const errors = []
    page.on('console', (message) => {
      if (message.type() === 'error') errors.push(message.text())
    })
    page.on('pageerror', (error) => errors.push(error.message))
    if (view === 'Explore') {
      await page.goto('/#compare')
      await compare(page).getByLabel('First Region', { exact: true }).selectOption('amazon-basin')
      await compare(page).getByLabel('Second Region', { exact: true }).selectOption('antarctic-peninsula')
    } else {
      await page.goto('/#surprise')
      await surprise(page).getByRole('button', { name: /Surprise Me!/ }).click()
      if (view === 'Investigation') {
        await page.getByRole('button', { name: 'Become a Detective', exact: true }).click()
        await page.getByRole('button', { name: discovery.narrative.investigation.steps[0].options[0].label, exact: true }).click()
        await page.getByRole('button', { name: 'Check the data', exact: true }).click()
      }
    }
    const start = page.getByRole('slider', { name: 'Range start', exact: true })
    await expect(start).toBeEnabled()
    await expect(page.locator('.globe-label')).toHaveCount(2)
    await page.evaluate(() => {
      window.timelineLabels = [...document.querySelectorAll('.globe-label')]
      window.labelReplacements = 0
      window.timelineLabelObserver = new MutationObserver((records) => {
        for (const record of records) {
          for (const node of record.removedNodes) {
            if (node.nodeType === 1 && (node.matches('.globe-label') || node.querySelector('.globe-label'))) {
              window.labelReplacements += 1
            }
          }
        }
      })
      window.timelineLabelObserver.observe(document.querySelector('.globe-viewport'), { childList: true, subtree: true })
    })
    const canvas = page.locator('.globe-viewport canvas')
    await canvas.evaluate((node) => { window.stableGlobeCanvas = node })
    // Let the intentional 1600 ms camera flight finish before checking that
    // timeline operations do not redirect or restart it.
    await page.waitForTimeout(1800)
    const labelPositions = () => page.locator('.globe-label').evaluateAll((nodes) =>
      nodes.map((node) => {
        const { x, y } = node.getBoundingClientRect()
        return { x, y, display: getComputedStyle(node).display }
      }),
    )
    const positions = await labelPositions()
    await start.press('ArrowRight')
    await page.getByRole('slider', { name: 'Range end', exact: true }).press('ArrowLeft')
    const month = page.getByLabel('Select month', { exact: true })
    await month.press('ArrowRight')
    await page.getByRole('button', { name: 'Play time series', exact: true }).click()
    for (const rate of ['1', '1.5', '2']) {
      const before = Number(await month.inputValue())
      await page.getByRole('group', { name: 'Playback speed' }).getByRole('button', { name: `${rate}×`, exact: true }).click()
      await expect.poll(async () => Number(await month.inputValue())).toBeGreaterThan(before)
    }
    await page.getByRole('button', { name: 'Pause time series', exact: true }).click()
    const after = await labelPositions()
    expect(after).toHaveLength(positions.length)
    after.forEach((position, index) => {
      expect(position.display).toBe(positions[index].display)
      // OrbitControls damping can settle by tiny fractions of a pixel.
      expect(Math.abs(position.x - positions[index].x)).toBeLessThan(0.5)
      expect(Math.abs(position.y - positions[index].y)).toBeLessThan(0.5)
    })
    expect(await canvas.evaluate((node) => node === window.stableGlobeCanvas)).toBe(true)
    expect(await page.evaluate(() => {
      window.timelineLabelObserver.disconnect()
      return { replacements: window.labelReplacements, connected: window.timelineLabels.every((node) => node.isConnected) }
    })).toEqual({ replacements: 0, connected: true })
    expect(errors).toEqual([])
  })
}


test('playback speed choices change the interval while playing', async ({ page }) => {
  await page.clock.install()
  await page.goto('/#surprise')
  await surprise(page).getByRole('button', { name: /Surprise Me!/ }).click()
  const month = page.getByLabel('Select month', { exact: true })
  await expect(month).toBeEnabled()
  const speed = page.getByRole('group', { name: 'Playback speed' })
  await expect(speed.getByRole('button', { name: '1×', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await page.clock.pauseAt(await page.evaluate(() => Date.now() + 1000))
  await page.getByRole('button', { name: 'Play time series', exact: true }).click()
  await page.clock.runFor(700)
  await expect(month).toHaveValue('1')
  await speed.getByRole('button', { name: '1.5×', exact: true }).click()
  await page.clock.runFor(467)
  await expect(month).toHaveValue('2')
  await speed.getByRole('button', { name: '2×', exact: true }).click()
  await page.clock.runFor(350)
  await expect(month).toHaveValue('3')
  await page.getByRole('button', { name: 'Pause time series', exact: true }).click()
  await page.clock.runFor(1400)
  await expect(month).toHaveValue('3')
})


for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  test(`globe survives loading, navigation, and resize at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.route('**/api/series?*', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 500))
      await route.fallback()
    })
    await page.goto('/#compare')
    const canvas = page.locator('.globe-viewport canvas')
    await expect(canvas).toBeVisible()
    await canvas.evaluate((node) => { window.navigationCanvas = node })
    await compare(page).getByLabel('First Region', { exact: true }).selectOption('amazon-basin')
    await compare(page).getByLabel('Second Region', { exact: true }).selectOption('antarctic-peninsula')
    await expect(page.locator('.chart')).toHaveCount(2)
    const originalLabels = await page.locator('.globe-label').allTextContents()
    // Switching tabs hands the globe to Surprise Me!, which shows nothing until
    // it draws a Discovery; from then on its Region labels must stay put.
    await page.getByRole('tab', { name: 'Surprise Me!' }).click()
    await surprise(page).getByRole('button', { name: /Surprise Me!/ }).click()
    await expect(page.getByRole('heading', { name: discovery.narrative.question, exact: true })).toBeVisible()
    await expect(page.locator('.globe-label')).toHaveCount(2)
    const surpriseLabels = await page.locator('.globe-label').allTextContents()
    await page.evaluate(() => {
      window.navigationLabels = [...document.querySelectorAll('.globe-label')]
      window.navigationLabelRemovals = 0
      window.navigationObserver = new MutationObserver((records) => {
        for (const record of records) {
          for (const node of record.removedNodes) {
            if (window.navigationLabels.some((label) => node === label || node.contains(label))) {
              window.navigationLabelRemovals += 1
            }
          }
        }
      })
      window.navigationObserver.observe(document.querySelector('.globe-viewport'), { childList: true, subtree: true })
    })
    await expect(page.getByLabel('Select month', { exact: true })).toBeEnabled()
    await page.getByRole('button', { name: 'Become a Detective', exact: true }).click()
    await expect(page.getByLabel('Select month', { exact: true })).toBeDisabled()
    await page.getByRole('button', { name: discovery.narrative.investigation.steps[0].options[0].label, exact: true }).click()
    await page.getByRole('button', { name: 'Check the data', exact: true }).click()
    await expect(page.getByLabel('Select month', { exact: true })).toBeEnabled()
    await page.getByRole('button', { name: 'Back', exact: false }).click()
    await page.getByRole('button', { name: 'Surprise me again', exact: true }).click()
    await expect(page.getByText('Searching the planet', { exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: discovery.narrative.question, exact: true })).toBeVisible()
    await expect(page.getByLabel('Select month', { exact: true })).toBeEnabled()
    await page.setViewportSize({ width: viewport.width + 60, height: viewport.height - 80 })
    await expect(canvas).toBeVisible()
    await page.screenshot({ path: `test-results/timeline-${viewport.width}.png` })
    expect(await page.locator('.globe-label').allTextContents()).toEqual(surpriseLabels)
    expect(await page.evaluate(() => {
      window.navigationObserver.disconnect()
      return window.navigationLabelRemovals
    })).toBe(0)
    expect(await canvas.evaluate((node) => node === window.navigationCanvas)).toBe(true)
    // Back to Compare: its pair is still chosen, so its Regions return to the globe.
    await page.getByRole('tab', { name: 'Compare Regions' }).click()
    await expect(page.locator('.globe-label')).toHaveText(originalLabels)
    await compare(page).getByLabel('Second Region', { exact: true }).selectOption('sahel')
    await expect(page.locator('.globe-label')).toHaveText(['Amazon Basin', 'Sahel'])
    await expect(compare(page).locator('.chart')).toHaveCount(2)
    expect(await canvas.evaluate((node) => node === window.navigationCanvas)).toBe(true)
  })
}


test('selecting another Region preserves the existing Region layer during camera flight', async ({ page }) => {
  await page.goto('/#compare')
  await compare(page).getByLabel('First Region', { exact: true }).selectOption('amazon-basin')
  const amazon = page.locator('.globe-label').filter({ hasText: 'Amazon Basin' })
  await expect(amazon).toBeVisible()
  await amazon.evaluate((node) => { window.retainedRegionLabel = node })
  // Change the pair while the camera is still moving.
  await compare(page).getByLabel('Second Region', { exact: true }).selectOption('antarctic-peninsula')
  await expect(page.locator('.globe-label')).toHaveCount(2)
  expect(await amazon.evaluate((node) => node === window.retainedRegionLabel)).toBe(true)
  await compare(page).getByLabel('Second Region', { exact: true }).selectOption('sahel')
  await expect(page.locator('.globe-label')).toHaveText(['Amazon Basin', 'Sahel'])
  expect(await amazon.evaluate((node) => node === window.retainedRegionLabel)).toBe(true)
  await expect(page.locator('.chart')).toHaveCount(2)
})
