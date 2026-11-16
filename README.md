# Weather-Report

NASA Challenge: Be An Earth System Trend Detective!

An Autonomous Discovery Engine: it reads NASA Earth science time series, finds notable
contrasts between Regions by itself, and turns them into investigations that teach
students about trends and statistical evidence. See `CONTEXT.md` for the vocabulary,
`docs/adr/` for the decisions and `docs/challenge-brief.md` for the original challenge.

## Layout

| Path | What it holds |
| --- | --- |
| `schemas/` | The JSON Schemas all three groups build against |
| `src/engine/` | The engine: statistics, scoring and templates. No web dependency |
| `src/api/` | FastAPI over the engine. No statistics |
| `frontend/` | React: the three screens |
| `data/catalog.json` | The Region and Variable catalog, with confirmed NASA sources |
| `data/stub/` | Synthetic stub set the API contract tests run against |
| `data/seed/` | The seed set: results computed from real NASA data, committed so the demo needs no network |
| `scripts/` | `generate_stub_data.py` regenerates `data/stub/`; `build_seed_set.py` regenerates `data/seed/` |
| `tests/` | Seam 1 (engine interface) and seam 2 (HTTP contract) |

## Running it

Python 3.11 or newer, Node 18 or newer.

```sh
pip install -e ".[api,dev]"
python -m pytest                                  # the whole suite, no network
python -m uvicorn api.main:app --port 8000        # API on :8000
```

```sh
cd frontend && npm install && npm run dev         # UI on :5173, /api proxied to :8000
```

`WEATHER_REPORT_DATA_DIR` points the API at a different result set; it defaults to
`data/seed/`, the committed seed set. The catalog does not move with it: `WEATHER_REPORT_CATALOG` overrides
`data/catalog.json` if needed.

Run the browser suite against the real API and committed seed with
`npm run test:integration` from `frontend/`. It starts and stops both servers.
See [browser end-to-end setup and configuration](frontend/docs/browser-end-to-end.md).

## The seed set

```sh
python scripts/build_seed_set.py                  # from the acquired NASA files
python scripts/build_seed_set.py --series-dir DIR # from Series files already built
python scripts/build_seed_set.py --only-aggregations # only the non-mean Aggregations
```

The command builds the monthly Series for every catalog Region and Variable the
acquired data can provide (see `data/data_gathering/README.md` for acquiring it),
runs the engine over them (Trends rated as one family, Mirrors, Candidate
Discoveries) and writes `data/seed/series/` and `data/seed/discoveries/`. Commit
the result. It refuses to overwrite the seed set when no Candidate carries one of
the three Evidence labels (`--allow-missing-labels` overrides). Rerun it whenever
the engine or the data changes.

From the acquired files it also builds every other Aggregation (median, minimum,
maximum, root mean square, standard deviation, mean absolute value) into
`data/seed/aggregations/<aggregation>/series/`. Explore My World answers from
those directly; only what the seed set does not hold, such as months after it
ends, is fetched from NASA in a background job. A period that runs past the seed
set fetches only its later months and joins them to the seeded ones. The Discovery engine never reads
them. `--skip-aggregations` leaves them out; `--series-dir` implies it.

The seed contains 71 Series: temperature and precipitation for all 25 Regions,
and soil moisture for the 21 Regions that offer it. Soil moisture is not offered
for `greenland-coast`, `antarctic-peninsula`, `equatorial-pacific` or
`north-atlantic`: GLDAS does not simulate ice sheets or open ocean. These four
pairs are outside the current catalog. Vegetation index
remains unavailable (#41). See `docs/catalog-sources.md` for the catalog rationale.

## The contracts

`schemas/` is the contract. Everything the API returns and everything the engine
produces validates against it, and `tests/test_contracts.py` proves the committed
fixtures still do.

- **`series.schema.json`** — one monthly, area-weighted series per Region-Variable
  pair. `values` has one entry per calendar month from `period.start`, with `null`
  for a missing month, so the index always matches the calendar. `quality` carries
  the gate from BS-003.
- **`trend.schema.json`** — the rate per decade with its 95% interval, the Evidence
  label, and every fit ADR 0002 calls for: the primary least-squares fit, the
  annual-anomaly and robust fits, the outlier check, Theil-Sen and Mann-Kendall as
  cross-checks, plus the Benjamini-Hochberg and autocorrelation corrections.
- **`discovery.schema.json`** — a Region pair with its contrasts, Mirrors, score and
  narrative. `contrasts[].trends` is ordered to match `region_ids`. The investigation
  steps are positional, so Predict, Check and Reason cannot come out of order.
- **`catalog.schema.json`** — the fixed Region and Variable catalogs.
- **`variable.schema.json`** — one Variable with its plain-language definition,
  units, NASA source and labeled possible causes. Kept separate so the definition
  can be reused outside the catalog; the catalog references it.
- **`responses.schema.json`** — every HTTP body: a resource under `data` plus a
  `notice` for live-data unavailability. Series responses also identify their
  provenance as live, cached or preloaded.
- **`common.schema.json`** — the shared pieces: ids, periods, sources, Evidence
  labels.

### Endpoints

| Endpoint | Returns |
| --- | --- |
| `GET /api/health` | status and engine version |
| `GET /api/catalog` | `catalogResponse` |
| `GET /api/series?region_id=&variable_id=&period_start=&period_end=` | `seriesResponse` |
| `GET /api/comparison?region_a=&region_b=&variable_id=&period_start=&period_end=` | `comparisonResponse`: two computed Trends and their monthly series, in requested Region order |
| `GET /api/explore/series?region_id=&variable_id=…&aggregation=&time_step=&period_start=&period_end=` | `exploreSeriesResponse` (200) or `exploreJobResponse` (202): Explore My World, one Series per Variable (1–5, `variable_id` repeated) for a catalog Region, or for a Selected area given as `rectangle=west,south,east,north` (repeatable) instead of `region_id`, over 2000-01 to the latest month, at a `time_step` of `3-hourly` (at most 1 year), `daily` (at most 10 years) or `monthly`. A Variable without data at the Time step is refused with 422 `variable_not_available_at_time_step` |
| `GET /api/explore/jobs/{id}` | `exploreJobResponse`: status, progress, result or failure |
| `GET /api/explore/options` | `exploreOptionsResponse`: latest requestable month, the Variables a Selected area can have, and each Time step's Variables and period cap |
| `POST /api/explore/process` | body `processingRequest`, answer `processingResponse`: applies a Processing recipe to Source or Derived series. Stateless; see below |
| `GET /api/discoveries` | `discoveryListResponse`, highest score first |
| `GET /api/discoveries/{discovery_id}` | `discoveryResponse` |
| `POST /api/discoveries/surprise` | `discoveryResponse`; body carries the session history |

A Region or Variable outside the catalog is rejected with `422` and an
`errorResponse`. A Series cache miss attempts acquisition and then uses a labelled
preloaded fallback; if neither is available it returns `503 live_data_unavailable`.

The welcome screen lets students compare two catalog Regions using a Variable
offered for both. The comparison endpoint analyzes their stored series with the
engine's Trend methods and rates the two Trends together as the family for
multiple-comparison correction. A pair does not need to be a stored Discovery.
The default period is 2000-01 through 2024-12. Missing series or insufficient
observations return `404 result_not_available`; the UI clears the old analysis
and displays the error. The bundled synthetic data used by the contract tests covers only four Regions
and two Variables; the API serves the real seed set by default.

## The stub set

`data/stub/` is synthetic, not NASA data: its `source.provider` says so. Each series
is generated from an explicit slope and each Trend reports the slope its series was
built from, so no statistics are implied. It covers all three Evidence labels, an
opposite-sign contrast, a multi-Variable contrast, a Mirror and a series with missing
months. The API serves the seed set from real data (`data/seed/`) by default; the
stub is kept for the contract tests, which pin to it through `WEATHER_REPORT_DATA_DIR`.

The generator reads the real catalog in `data/catalog.json` and takes every
series' units from it. The catalog holds 25 Regions and the four Variables, but the
stub series and discoveries exist only for four Regions and two Variables. Where each
Variable comes from, and how its NASA units convert to the units students see, is in
`docs/catalog-sources.md`.

The fixtures are built through `engine.contracts`, so the committed JSON cannot drift
from the Python contract objects.

## Engine interfaces

The implemented engine functions are exercised through these public seams:

| Seam | Ticket |
| --- | --- |
| `engine.trend.estimate_trend` | #4 trend estimation |
| `engine.discovery.find_candidate_discoveries` | #7 contrasts |
| `engine.discovery.find_mirrors` | #8 Mirrors |
| `engine.discovery.build_narrative` | #10 explanations and investigation content (built; ticket #7 calls it with each Discovery's Contrasts, period and Evidence label) |

## Surprise Me! selection

`engine.discovery.select_surprise` draws the next headline Discovery from the top
`TOP_N` eligible Candidates, weighted by score. It never repeats a Discovery within a
session and never headlines a Candidate labeled "Not enough evidence yet".

Two numbers the spec left open are answered here, and both are easy to change:

- **`TOP_N = 5`.** Enough to vary between sessions while keeping the headline genuinely
  top-ranked. Because the draw is weighted, raising it costs little quality.
- **A session that runs out of fresh Regions relaxes the Region rule** rather than
  returning nothing. BS-005 words its two rules with different force — a Discovery is
  *never* repeated, a Region is *avoided* — so only a session that has seen every
  eligible Discovery gets nothing back, and the API answers `404
  no_discovery_left_in_session`.

Candidates are filtered for eligibility before they are ranked, so a long session works
its way down the list instead of running dry the moment it has seen a fixed top N.


### Live results and preloaded fallback (#13)

`GET /api/series` checks the persistent live cache, then the preloaded Series
(a period inside one is cut from it and gated again on its own months), before
attempting acquisition. Series responses add `provenance`:
`live`, `cache`, or `preloaded`. A fallback also sets
`notice.code = "live_data_unavailable"`; a normal cache hit does not.
The UI labels preloaded and cached data separately. Different examples retain
their actual Region, Variable and period and cannot answer the original investigation.

- `WEATHER_REPORT_DATA_DIR`: preloaded Series and Discoveries (default `data/seed`).
- `WEATHER_REPORT_CACHE_DIR`: writable live-result storage (default `.scratch/results-cache`).
- `WEATHER_REPORT_LIVE_TIMEOUT_SECONDS`: positive finite acquisition deadline (default `120` seconds).
- `EARTHDATA_TOKEN`: server-only acquisition credential, read from the exported
  environment, then the repository-root `.env`, then `data/data_gathering/.env`
  (in that precedence order); never send it from the client.

Malformed/inverted periods return `422` (`invalid_period`). Expected acquisition
failures use a deterministic fallback: same Region/Variable, then same Variable,
then another example, with identity/period ordering to break ties. Examples must
match the schema, current engine and catalog, have aligned finite monthly values,
and pass their quality record. Without an example the API returns `503`
(`live_data_unavailable`). Fallbacks are never cached under the requested key.
Cache writes are atomic; a failed write still returns successfully acquired data.

The acquisition bridge uses the #6 pipeline; see the integration update below.

The #38 globe UI is integrated through `data-engineering`. DiscoveryPanel uses
the returned identity, period and provenance; substituted examples update the
globe highlights and cannot enter the original investigation. The #16 comparison
endpoint and Region/Variable pickers remain available.

### Acquisition integration update

The #6 pipeline is now connected through `api.acquisition_worker`. The worker
first attempts `get_catalog_series` on configured acquired files. If the source
is unavailable, it downloads the explicitly configured collection with #6's
`acquire`, then computes the monthly Series. Temporary downloads are isolated per
request; cancellation kills and reaps the worker before removing its workspace.
Only the computed Series is persisted in the result cache. Land-only products
still require the trusted mask configured by #6; vegetation remains #41.

`WEATHER_REPORT_ACQUISITION_CONFIG` selects the server-controlled gathering JSON
(default `data/data_gathering/config.json`). Run the API from this repository with
its `data/` package available. The resolved `EARTHDATA_TOKEN` is passed only in
the child environment. Worker diagnostics are suppressed to avoid leaking token
or download URLs. Missing sources/authentication errors trigger fallback;
unexpected worker failures propagate as server errors.

Integration tests use synthetic NetCDF files with the actual #6 reader and
quality gate. They do not constitute a real authenticated NASA download.

## Processing recipes

`POST /api/explore/process` (#83) applies an ordered Processing recipe with the
data-layer processing of #46 (`data/data_processing/README.md` lists the
operations). Each named input is either a Source series exactly as
`/api/explore/series` returned it, sent as `{"time_step", "aggregation",
"series"}` with that view's settings, or a Derived series from an earlier answer,
sent back as `{"derived": ...}`. The answer holds every Derived series with its
recipe, its inputs' provenance and its warnings. Nothing is stored: replaying a
recipe means sending the same request again. A step the data layer does not
provide is refused with 422 `processing_refused`, whose `details.reason` is the
data layer's code; a body that does not match `processingRequest` gets 422
`invalid_processing_request`.

## Explore My World background Series

`GET /api/explore/series` returns monthly catalog Region means immediately when
covered by the seed or results cache (`exploreSeriesResponse`). Otherwise it
returns HTTP 202 with `data.job` (`exploreJobResponse`). Poll the job's `url`
(`/api/explore/jobs/{id}`) for `queued`, `running`, `succeeded` or `failed`, and
`progress` from 0 to 100 (completed Variables). A successful job includes its
view in `result`; a failed job includes a safe `error` message and can be retried.
Explore My World displays progress, then the chart or acquisition failure.

`GET /api/explore/options` exposes `latest_month`. Set
`WEATHER_REPORT_LATEST_MONTH=YYYY-MM` to the source's known availability; by
default it is the last complete UTC calendar month. This default is a request
limit, not a guarantee NASA has published every Variable: unavailable months
produce an acquisition failure. The view still opens on the seed period.

A Selected area (#79) replaces `region_id` with one or more
`rectangle=west,south,east,north` values that touch or overlap; west > east
crosses the antimeridian. A grid cell belongs to the area when its centre lies in
any rectangle. Its Series are always built by a job (only Variables listed in
`area_variable_ids`), carry `area` where a Region's carry `region_id`, and are
cached under `WEATHER_REPORT_CACHE_DIR/areas`, apart from every Region Series,
so they never reach the catalog or a Discovery.

Jobs use `EARTHDATA_TOKEN`, `WEATHER_REPORT_LIVE_TIMEOUT_SECONDS` and
`WEATHER_REPORT_CACHE_DIR` as described above. Completed Series persist in the
existing cache without expiry; an identical request returns them without
acquiring again. Job references live in one API process and do not survive a
restart; run one worker (or use sticky routing). Discoveries and comparisons
use their existing seed-only paths.

A daily or 3-hourly Time step (#80) is always built by a job, since the seed set
is monthly. The job asks NASA for the native hourly (MERRA-2) or 3-hourly
(GLDAS) grids of the period, combines each native time step's cells with the
Aggregation, then each UTC day or 3-hour interval's values with the same
Aggregation. A Series holds one value per Time step from the first day of its
start month; precipitation is the total that fell in each (`mm/day`, `mm/3h`).
The Quality gate counts missing Time steps (`too_many_missing_time_steps`) with
the same one-in-five limit; monthly Series keep `too_many_missing_months`.
Results are cached per Time step under `WEATHER_REPORT_CACHE_DIR/explore/<time
step>/<aggregation>` (and `areas/<time step>/<aggregation>`). Vegetation index
has no sub-monthly product, so `/api/explore/options` lists the Variables of
each Time step and the view offers only those.

Run the browser checks with the real API and synthetic acquisition grids:
`cd frontend && npx playwright test --config playwright.jobs.config.js`, and for
Time steps `--config playwright.time-steps.config.js`.
