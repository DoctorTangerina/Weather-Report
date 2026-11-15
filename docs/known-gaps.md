# Known gaps (issue #17)

State of the repo at `4044420` (2026-11-15). Each gap was checked in the repo or by a command; where something was not checked, it says so.

## Backend follow-up (#65)

The current backend reads `EARTHDATA_TOKEN` from the exported environment or
`.env` (repository root, then `data/data_gathering/`), and its default live-fetch
timeout is 120 seconds. Automated HTTP tests cover credential precedence and a
12-month synthetic fetch lasting longer than 15 seconds; authenticated NASA
performance has not been remeasured in this change.

The reported four missing soil-moisture Series are outside the current catalog:
those ocean/ice Regions offer only temperature and precipitation. The 71 seed
Series cover every offered pair with acquired data (NDVI remains #41), as checked
by `test_the_committed_seed_set_has_a_series_for_each_offered_pair`. See
`docs/catalog-sources.md` for the prior catalog decision. No Quality gate
fractions or exclusion records have been invented for unavailable products.

The historical findings below describe the revision above, not this follow-up.

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
| 4 Region-Variable pairs missing from the seed | Soil moisture for `greenland-coast`, `antarctic-peninsula`, `equatorial-pacific` and `north-atlantic`. The seed has 92 series, not 96. |
| One period only | Every seed series covers 2000-01 to 2024-12. The UI has no period control. |
| Seed contains many weak results | Of 264 Discoveries, 177 are "Not enough evidence yet"; only the 87 rated Strong (69) or Some (18) evidence are eligible as Surprise Me! headlines. |

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
| Stale README | `README.md` says `python -m pytest  # 30 tests`; the suite now has 258. Its layout table also has a broken row for `data/seed/`. |
| Formatting, type checking, static analysis | Not run for this ticket. |
| Open feature work | Correlation map (#56, #60–#62) now connects the frontend to acquired data through the API. Arbitrary-area/submonthly acquisition remains separate work; unavailable selections are explained. Manual-processing methods (#46–#53) remain reusable data methods. |
