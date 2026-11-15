import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  use: { baseURL: 'http://127.0.0.1:4173', viewport: { width: 1440, height: 1000 } },
  webServer: [
    {
      command: '.venv/bin/python -m uvicorn api.main:app --app-dir src --host 127.0.0.1 --port 8005',
      cwd: '..',
      url: 'http://127.0.0.1:8005/api/health',
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 4173 --strictPort',
      env: { WEATHER_REPORT_API_URL: 'http://127.0.0.1:8005' },
      url: 'http://127.0.0.1:4173',
      reuseExistingServer: !process.env.CI,
    },
  ],
})
