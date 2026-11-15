import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../../', import.meta.url))
const virtualenvPython = fileURLToPath(new URL(
  process.platform === 'win32' ? '../../.venv/Scripts/python.exe' : '../../.venv/bin/python',
  import.meta.url,
))
const python = process.env.WEATHER_REPORT_PYTHON
  ?? (existsSync(virtualenvPython) ? virtualenvPython : process.platform === 'win32' ? 'python' : 'python3')
// A later acquisition fake can export a configured ASGI app without replacing
// HTTP responses in the browser or changing this process harness.
const app = process.env.WEATHER_REPORT_E2E_API_APP ?? 'api.main:app'
const child = spawn(python, ['-m', 'uvicorn', app, '--host', '127.0.0.1', '--port', '8765'], {
  cwd: root,
  stdio: 'inherit',
  windowsHide: true,
})
child.on('error', (error) => {
  console.error(`Could not start test API with ${python}: ${error.message}`)
  process.exitCode = 1
})
child.on('exit', (code) => { process.exitCode = code ?? 1 })
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => child.kill(signal))
}
