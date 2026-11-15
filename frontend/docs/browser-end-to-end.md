# Browser end-to-end suite (#74)

These tests run the React app against FastAPI and the committed seed set. They
do not intercept API responses. The suite covers manual Region selection,
Surprise Me! → Become a Detective → Check the data → How do we know?, and
Explore My World for a catalog Region (`integration/explore.spec.js`, #75).

## Setup and run

From the repository root, install the Python API and test dependencies into a
virtual environment (`python -m venv .venv` if needed):

```sh
python -m pip install -e ".[api,dev]"
cd frontend
npm ci
npx playwright install chromium
```

After setup, one command from `frontend/` starts both servers, waits for their
readiness, runs the browser tests, and stops the servers it started:

```sh
npm run test:integration
```

`npm run test:areas` runs the Selected-area suite (`integration-areas/`, #79) the
same way, with `tests/explore_area_app.py` serving synthetic global grids in
place of NASA.

The runner uses API port **8765** and frontend port **4174**, keeping the normal
development ports separate. Those test ports must be free; the suite refuses to
reuse existing servers so it cannot silently test the wrong configuration.

Python defaults to the repository's `.venv/Scripts/python.exe` on Windows or
`.venv/bin/python` elsewhere, if present; otherwise it uses `python` on Windows
and `python3` elsewhere. The launcher passes arguments directly to Python, so
interpreter paths containing spaces work. Set `WEATHER_REPORT_PYTHON` to override.

The separate `npm run test:e2e` suite uses simulated API responses. It does not
replace this real-server suite. `npm test` runs frontend unit tests.

## Configure the API for later scenarios

Environment variables are passed to the API process. Paths relative to the
repository root are supported; absolute paths are useful in automation.

| Variable | Default | Purpose |
| --- | --- | --- |
| `WEATHER_REPORT_PYTHON` | Repository virtualenv, then platform Python | Python interpreter executable |
| `WEATHER_REPORT_DATA_DIR` | `data/seed` | Alternate result set containing Series and Discoveries |
| `WEATHER_REPORT_CATALOG` | `data/catalog.json` | Alternate Region/Variable catalog |
| `WEATHER_REPORT_CACHE_DIR` | API default | Separate results cache for a scenario |
| `WEATHER_REPORT_E2E_API_APP` | `api.main:app` | Importable ASGI app with scenario-specific acquisition configuration |

For example, run the happy path against the existing synthetic result set. The
API runs from the repository root, so the path is `data/stub` even from `frontend/`:

PowerShell, from `frontend/`:

```powershell
$env:WEATHER_REPORT_DATA_DIR = 'data/stub'
npm run test:integration -- --grep 'real Surprise'
Remove-Item Env:WEATHER_REPORT_DATA_DIR
```

POSIX shell:

```sh
WEATHER_REPORT_DATA_DIR=data/stub npm run test:integration -- --grep 'real Surprise'
```

The full suite's manual-selection test assumes Amazon Basin and Sahel exist,
so arbitrary alternate datasets need their own scenario tests.

For a future fake acquisition source, provide a Python module exporting an ASGI
`app` configured with that source, and set `WEATHER_REPORT_E2E_API_APP` to
`package.module:app`. It runs through the same API/frontend/proxy path; no browser
HTTP interception is necessary. Repository root and `src/` are on `PYTHONPATH`,
with any existing `PYTHONPATH` preserved using the platform's path separator.
This ticket supplies the startup hook, not the future fake's implementation.

The default seed happy path requires no Earthdata token or NASA downloads.
Other scenarios may invoke acquisition if their result set lacks requested
Series. Use a scenario-specific cache and fake app for those tests.
