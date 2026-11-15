# Issue #65: frontend verification

Scope: frontend fixes and browser verification only. API, seed data, README and
Python lint fixes remain outside this change.

Run from `frontend/`:

```sh
npm ci
npx playwright install chromium
npm test
npm run test:e2e -- --workers=1
npm run build
```

The Playwright tests run the real React app and WebGL globe in Chromium, with
HTTP responses backed by the checked-in catalog and seed JSON. They do not need
a running API or Earthdata credentials.

- Welcome has empty Region controls and sends no automatic comparison request.
  Selecting one Region highlights only that Region; completing a pair loads charts.
- Direct Become a Detective opens Predict with no timeline values revealed.
- Become a Detective uses the selected Region pair when it has a Discovery.
  A missing Discovery or incomplete pair produces an explanation and retains
  the selected Regions instead of silently drawing a different pair.
- Surprise Me! → Become a Detective → Check the data → How do we know? displays
  the analyzed period and method citation without browser errors.
- Drawing another Discovery retains both Region labels, the same canvas node,
  and its dimensions while the response is pending. Previously the canvas grew
  from 825 to 924 pixels high as the timeline was removed, restarting the camera.
- Both Earth textures return successfully from the app with external HTTP
  requests blocked. These assets were already committed before this change;
  the production build copies them byte-for-byte into `dist/textures/`.

All seven browser tests and four existing unit tests passed. The production build
passed with the existing large-bundle warning. Reintroducing highlight clearing
made the transition test fail; the mutation was restored afterward.

Limitations: this is a deterministic frontend smoke test, not a live NASA/API
integration test or a fully disconnected reload of the app. No typecheck script
is configured. The repository Python suite could not run because the active
environment has no pytest installed.
