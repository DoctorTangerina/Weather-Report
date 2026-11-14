# Issue #14 — local evidence

Validated on 2026-11-14 against the stub API on port 8000 and Vite on port 5173. No automated UI tests were added.

## Implemented flow

MainScreen is the entry screen. Startup loads only the catalog, without selecting a Discovery or populating session history. The initial sidebar shows a single Region and Variable.

Surprise Me! sends session history to the engine, highlights the selected pair on the existing globe, and updates the existing sidebar with the question, Evidence label, Region descriptions, Variable definition and charts. The timeline controls those charts. Become a Detective opens the investigation; Back returns to MainScreen with the selected Discovery.

## Verification

- Production build: `npm run build` passed. Vite retains its large globe bundle warning.
- API checks: `pytest tests/test_api.py -q` passed, 10 tests, including exhaustion instead of repeated Regions.
- Full existing suite: `pytest tests -q` passed, 30 tests. The environment reports a Starlette/httpx deprecation warning. Temporary pytest, jsonschema and httpx dependencies were used because the existing Python environment lacked the test packages.
- No TypeScript/typecheck script is configured in this JavaScript frontend.

## Manual browser smoke test

- Initial page: MainScreen with a globe, catalog selectors and one series; no Discovery question, evidence label or highlighted comparison pair.
- First Surprise Me!: request body contained empty `shown_discovery_ids` and `shown_region_ids`. MainScreen remained mounted and the exact same globe canvas remained in the document. The Amazon Basin and Sahel were highlighted, with the question, Strong evidence label and two precipitation charts in the sidebar.
- Timeline playback: selected timestamp advanced from 2000-01 to 2000-12 and both chart values updated to that month.
- Next Surprise Me!: request contained `amazon-basin--sahel`, `amazon-basin` and `sahel`. The stub returned `no_discovery_left_in_session`; the message was displayed, the existing Discovery stayed visible and Surprise Me! became disabled. Selection rules remain at the engine interface, as required by BS-005/#9.
- Loading: held surprise and series responses in the browser. The sidebar showed the corresponding loading messages, both selection buttons were disabled while selecting, and the page remained MainScreen.
- Fallback: injected a notice into successful surprise and series responses in the browser. Both notices appeared in the sidebar. This verifies display of the #13 contract, not live fetch itself; the current stub returns null notices.
- Investigation: Become a Detective opened Predict; Back returned to MainScreen with the selected pair.
- Desktop: visually inspected at 1440 × 900, including both highlighted Regions and the sidebar charts.
- Mobile: visually inspected at 390 × 844; viewport, page content and MainScreen width were all 390 pixels, with both charts present and no horizontal overflow.

To repeat, start the stub API using the repository README, run `npm run dev` in frontend, and open http://127.0.0.1:5173. Reload starts a new in-memory session. The globe requires WebGL and uses the existing external Earth texture URLs.

All work remains local. No commit, push or issue-tracker publication was performed.
