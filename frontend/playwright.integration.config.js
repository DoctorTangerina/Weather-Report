import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { delimiter, join } from 'node:path'

const root = fileURLToPath(new URL('../', import.meta.url))
const apiURL = 'http://127.0.0.1:8765'

export default defineConfig({
  testDir: './integration',
  workers: 1,
  // Real acquisition starts a Python worker and can exceed five seconds on Windows.
  timeout: 90000,
  expect: { timeout: 30000 },
  use: { baseURL: 'http://127.0.0.1:4174', viewport: { width: 1440, height: 1000 } },
  webServer: [
    {
      command: 'node frontend/scripts/start-test-api.mjs',
      cwd: root,
      env: {
        WEATHER_REPORT_E2E_API_APP: 'tests.explore_catalog_app:app',
        PYTHONPATH: [join(root, 'src'), root, process.env.PYTHONPATH].filter(Boolean).join(delimiter),
        WEATHER_REPORT_DATA_DIR: process.env.WEATHER_REPORT_DATA_DIR ?? join(root, 'data', 'seed'),
      },
      url: `${apiURL}/api/health`,
      reuseExistingServer: false,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 4174 --strictPort',
      env: { WEATHER_REPORT_API_URL: apiURL },
      url: 'http://127.0.0.1:4174',
      reuseExistingServer: false,
    },
  ],
})
