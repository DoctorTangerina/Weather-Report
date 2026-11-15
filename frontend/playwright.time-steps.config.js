import { defineConfig } from '@playwright/test'
import integration from './playwright.integration.config.js'

export default defineConfig({
  ...integration,
  testDir: './integration-time-steps',
  // Sub-monthly Series come from background jobs that reduce hourly grids.
  expect: { timeout: 20000 },
  timeout: 60000,
  webServer: integration.webServer.map((server, index) => index === 0
    ? { ...server, env: { ...server.env, WEATHER_REPORT_E2E_API_APP: 'tests.explore_time_step_app:app' } }
    : server),
})
