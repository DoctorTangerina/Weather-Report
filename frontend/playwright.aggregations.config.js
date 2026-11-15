import { defineConfig } from '@playwright/test'
import integration from './playwright.integration.config.js'

// #78: the real API with only its gridded acquisition source replaced.
export default defineConfig({
  ...integration,
  testDir: './integration-aggregations',
  // Each Series is acquired in a worker process, which takes a few seconds.
  expect: { timeout: 20000 },
  webServer: integration.webServer.map((server, index) => index === 0
    ? { ...server, env: { ...server.env, WEATHER_REPORT_E2E_API_APP: 'tests.explore_aggregation_app:app' } }
    : server),
})
