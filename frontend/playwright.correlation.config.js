import { defineConfig } from '@playwright/test'
import integration from './playwright.integration.config.js'

// #60–#62: the Correlation map through the real API, with tests/correlation_app.py's
// deterministic acquired results added to the committed seed set.
export default defineConfig({
  ...integration,
  testDir: './integration-correlation',
  webServer: integration.webServer.map((server, index) => index === 0
    ? { ...server, env: { ...server.env, WEATHER_REPORT_E2E_API_APP: 'tests.correlation_app:app' } }
    : server),
})
