import { defineConfig } from '@playwright/test'
import integration from './playwright.integration.config.js'

export default defineConfig({
  ...integration,
  testDir: './integration-jobs',
  webServer: integration.webServer.map((server, index) => index === 0
    ? { ...server, env: { ...server.env, WEATHER_REPORT_E2E_API_APP: 'tests.explore_job_app:app' } }
    : server),
})
