# Known gaps (issue #17)

State of the repo at `4044420` (2026-11-15). Each gap was checked in the repo or by a command; where something was not checked, it says so.

## Not verified

| Gap | Detail |
| --- | --- |
| Live fetch is only lightly tested | One live fetch succeeded on 2026-11-15 (Sahel temperature, 2000-01 to 2000-12, `provenance: "live"`, 11.3 s with the timeout raised to 120 s; the repeat request came from cache). It was run through the API only, not the UI, and only once. At the default 15 s limit a longer period may time out and fall back. |
| API does not read `.env` | `src/api/main.py` reads `EARTHDATA_TOKEN` from the process environment only. A token in `data/data_gathering/.env` is ignored by the API unless exported first, so a demo started without exporting it silently serves preloaded data. |
| Browser smoke test at the current revision | The last browser run is `docs/issue-13-merge-smoke.md` (2026-11-14, earlier revision) and `frontend/docs/issue-14-smoke.md`. Surprise Me! → Become a Detective → "How do we know?" has not been driven in a browser since. Only the API-level path was walked (see the #17 evidence pack). |
| Frontend tests | Only 4 unit tests (number formatting). No automated UI or end-to-end tests. |

## Data coverage

| Gap | Detail |
| --- | --- |
| Vegetation index (NDVI) not in the seed set | Updated by #41: the gathering package now acquires MOD13C2, converts its HDF4 granules and builds `vegetation-index` series, and `config.json` has its `CATALOG_SERIES` entry. But the seed set still has no series for it: the 2000–2024 granules (about 29 GB) have not been acquired for a seed rebuild. |
| 4 Region-Variable pairs missing from the seed | Soil moisture for `greenland-coast`, `antarctic-peninsula`, `equatorial-pacific` and `north-atlantic`. The seed has 71 series, not 75. |
| One period only | Every seed series covers 2000-01 to 2024-12. The UI has no period control. |
| Seed contains many weak results | Of 264 Discoveries, 177 are "Not enough evidence yet"; only the 87 rated Strong (69) or Some (18) evidence are eligible as Surprise Me! headlines. |
| Real catalog content | #23 (real Region and Variable catalog content) is still open. |

## Product and UI

| Gap | Detail |
| --- | --- |
| Fallback is not reachable from the UI | Requesting a series outside the seed (a different period, NDVI) can only be done through the API. |
| Globe needs WebGL and internet | Earth textures load from external URLs. Offline, the globe image is blank; the data and sidebar still work. |
| Large frontend bundle | `npm run build` warns that the JS chunk is about 2.1 MB (globe library). Not split. |
| Session memory is in-page | Surprise Me! history resets on reload or "Start a new session". No accounts. |
| LLM rephrasing | #18 (optional stretch) is not built. Narratives are template text. |

## Repo hygiene

| Gap | Detail |
| --- | --- |
| Lint errors | `ruff check .` reports 13 errors (9 auto-fixable), including a real one: `available_series` is defined twice in `src/engine/store.py` (lines 38 and 77). |
| Stale README | `README.md` says `python -m pytest  # 30 tests`; the suite now has 258. Its layout table also has a broken row for `data/seed/`. |
| Formatting, type checking, static analysis | Not run for this ticket. |
| Open feature work | Correlation map (#56, #60–#62), manual time-series processing (#46–#53) are separate, unbuilt epics and not part of this demo. |
