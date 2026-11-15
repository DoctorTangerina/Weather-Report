import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// /api is proxied to the FastAPI layer, so the browser sees one origin.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': process.env.WEATHER_REPORT_API_URL ?? 'http://127.0.0.1:8000',
    },
  },
})
