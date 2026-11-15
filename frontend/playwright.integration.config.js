import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../', import.meta.url))
const python = process.env.WEATHER_REPORT_PYTHON ?? 'python3'
const quotedPython = `'${python.replaceAll("'", "'\\''")}'`

export default defineConfig({
  testDir: './integration',
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:4173', viewport: { width: 1440, height: 1000 } },
  webServer: [
    {
      command: `${quotedPython} -m uvicorn api.main:app --host 127.0.0.1 --port 8000`,
      cwd: root,
      env: {
        PYTHONPATH: `${root}/src:${root}`,
        WEATHER_REPORT_DATA_DIR: `${root}/data/seed`,
      },
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: false,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 4173 --strictPort',
      url: 'http://127.0.0.1:4173',
      reuseExistingServer: false,
    },
  ],
})
