# Issue #65: frontend/backend integration after syncing dev

The frontend branch now incorporates dev's backend fixes from PR #87 together
with the frontend fixes from PR #88. The merge had no conflicts.

The existing seven Chromium tests use simulated API responses. Two additional
checks exercise the actual React app, Vite proxy, FastAPI server and committed
NASA seed, with no HTTP interception:

- Initially no Regions are selected. Choosing Amazon Basin and Sahel returns a
  successful comparison for exactly those two Regions, renders two charts and
  opens that pair's investigation with Predict still hiding timeline values.
- Surprise Me → Become a Detective → Check the data → How do we know displays
  the actual API Discovery's period and method citation, uses `preloaded`
  Series, keeps the same globe canvas and produces no browser exceptions.

## Reproduce

Install the API/dev Python dependencies and run `npm ci` in `frontend/`.
Install Chromium with `npx playwright install chromium`. Then, from `frontend/`:

```sh
npm test
npm run test:e2e -- --workers=1
WEATHER_REPORT_PYTHON=/absolute/path/to/.venv/bin/python npm run test:integration
npm run build
```

The current harness uses the repository virtualenv by default and starts its
own API on port 8765 and Vite on port 4174; those ports must be free.
It defaults to the committed seed and requires no NASA token or downloads.
See [current setup and configurable sources](browser-end-to-end.md) for #74's
cross-platform command and environment overrides.
Use `PLAYWRIGHT_BROWSERS_PATH` if Chromium is installed in a custom directory.
Run the complete Python suite with `python -m pytest -q` from the repo root.

## Verification results

- Complete merged Python suite: 607 passed, including backend credential and
  timeout regressions.
- Frontend unit command, all seven existing browser tests and production build
  passed.
- Both real-API integration tests passed.
- Ruff, formatting of the integrated backend Python files and whitespace checks
  passed.
- Mutation check: changing the frontend comparison URL to a nonexistent route
  made the selected-Regions integration test fail on the non-success HTTP
  response. The URL was restored before the final integration run.

No integration defect was found in these flows. The production bundle retains
its existing size warning and Python reports a Starlette TestClient deprecation
warning. `npm ci` reports two dependency advisories (one moderate, one high);
no dependency upgrade was included in this synchronization. Type checking and
live NASA acquisition were not repeated here: these browser checks deliberately
exercise the committed seed, while the earlier authenticated NASA result is
recorded in the backend evidence pack.
