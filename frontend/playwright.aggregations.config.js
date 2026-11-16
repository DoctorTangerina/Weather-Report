import { defineConfig } from '@playwright/test'
import integration from './playwright.integration.config.js'

// #78: the real API with only its gridded acquisition source replaced.
export default defineConfig({
  ...integration,
  testDir: './integration-aggregations',
  // Rebuilding two Variables starts two acquisition workers.
  timeout: 120000,
  expect: { timeout: 60000 },
  webServer: integration.webServer.map((server, index) => index === 0
    ? { ...server, env: { ...server.env, WEATHER_REPORT_E2E_API_APP: 'tests.explore_aggregation_app:app' } }
    : server),
})
