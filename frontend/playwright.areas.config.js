import { defineConfig } from '@playwright/test'
import integration from './playwright.integration.config.js'

// #79: Selected areas through the real API, with tests/explore_area_app.py's
// synthetic global grid standing in for NASA.
export default defineConfig({
  ...integration,
  testDir: './integration-areas',
  // Each Variable of a Selected area is acquired in a worker process, and a
  // two-Variable job takes longer than the default 5 s.
  expect: { timeout: 20000 },
  webServer: integration.webServer.map((server, index) => index === 0
    ? { ...server, env: { ...server.env, WEATHER_REPORT_E2E_API_APP: 'tests.explore_area_app:app' } }
    : server),
})
