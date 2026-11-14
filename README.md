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
| `data/stub/` | Synthetic stub set so everything runs before the real pipeline lands |
| `scripts/` | `generate_stub_data.py` regenerates `data/stub/` |
| `tests/` | Seam 1 (engine interface) and seam 2 (HTTP contract) |

## Running it

Python 3.11 or newer, Node 18 or newer.

```sh
pip install -e ".[api,dev]"
python -m pytest                                  # 30 tests, no network
python -m uvicorn api.main:app --port 8000        # API on :8000
```

```sh
cd frontend && npm install && npm run dev         # UI on :5173, /api proxied to :8000
```

`WEATHER_REPORT_DATA_DIR` points the API at a different result set; it defaults to
`data/stub/`. The catalog does not move with it: `WEATHER_REPORT_CATALOG` overrides
`data/catalog.json` if needed.

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
  `notice` that stays null until the service serves something other than a fresh
  result.
- **`common.schema.json`** — the shared pieces: ids, periods, sources, Evidence
  labels.

### Endpoints

| Endpoint | Returns |
| --- | --- |
| `GET /api/health` | status and engine version |
| `GET /api/catalog` | `catalogResponse` |
| `GET /api/series?region_id=&variable_id=&period_start=&period_end=` | `seriesResponse` |
| `GET /api/comparison?region_a=&region_b=&variable_id=&period_start=&period_end=` | `comparisonResponse`: two computed Trends and their monthly series, in requested Region order |
| `GET /api/discoveries` | `discoveryListResponse`, highest score first |
| `GET /api/discoveries/{discovery_id}` | `discoveryResponse` |
| `POST /api/discoveries/surprise` | `discoveryResponse`; body carries the session history |

A Region or Variable outside the catalog is rejected with `422` and an
`errorResponse`. A request with no stored result gets `404 result_not_available`
until ticket #13 adds the live fetch.

The welcome screen lets students compare two catalog Regions using a Variable
offered for both. The comparison endpoint analyzes their stored series with the
engine's Trend methods and rates the two Trends together as the family for
multiple-comparison correction. A pair does not need to be a stored Discovery.
The default period is 2000-01 through 2024-12. Missing series or insufficient
observations return `404 result_not_available`; the UI clears the old analysis
and displays the error. The bundled synthetic data covers only four Regions
and two Variables, so other catalog choices may be unavailable until #12/#13.

## The stub set

`data/stub/` is synthetic, not NASA data: its `source.provider` says so. Each series
is generated from an explicit slope and each Trend reports the slope its series was
built from, so no statistics are implied. It covers all three Evidence labels, an
opposite-sign contrast, a multi-Variable contrast, a Mirror and a series with missing
months. Ticket #12 replaces it with the seed set computed from real data.

The generator reads the real catalog in `data/catalog.json` and takes every
series' units from it. The catalog holds 25 Regions and the four Variables, but the
stub series and discoveries exist only for four Regions and two Variables. Where each
Variable comes from, and how its NASA units convert to the units students see, is in
`docs/catalog-sources.md`.

The fixtures are built through `engine.contracts`, so the committed JSON cannot drift
from the Python contract objects.

## What is not built yet

The engine's statistical and storytelling functions raise `NotImplementedError` with
their ticket number. The seams are in place:

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
