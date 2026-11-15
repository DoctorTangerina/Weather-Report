# Demo script (issue #17)

A five-minute walkthrough of Surprise Me!, Become a Detective and "How do we know?". It runs offline from the committed seed set (`data/seed/`: real NASA GES DISC series: MERRA-2 for temperature and precipitation, GLDAS for soil moisture; 2000-01 to 2024-12). Known limits are in `docs/known-gaps.md`.

## Setup (once, before the audience arrives)

Needs Python 3.11+ and Node 18+.

```sh
pip install -e ".[api,dev]"
cd frontend && npm install && cd ..
```

Start both servers, each in its own terminal, from the repo root:

```sh
# 1. API on :8000. Leave EARTHDATA_TOKEN unset to demo offline.
python -m uvicorn api.main:app --port 8000

# 2. UI on :5173, proxies /api to :8000
cd frontend && npm run dev
```

Open http://127.0.0.1:5173 in a WebGL-capable browser. The globe loads its Earth textures from external URLs, so the machine needs internet for the globe image. The data does not need it.

Pre-flight check (should print `200` and a Discovery id):

```sh
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/api/health
```

A page reload starts a new in-memory session, so Surprise Me! forgets what it has shown. Reload (or use **Start a new session**) between runs.

## Walkthrough

### 1. Start screen (about 30 s)

Say: "A student can compare any two Regions, but the engine can also find something surprising by itself."

- The globe shows the Earth with a Region and Variable selector. No Discovery is selected yet.

### 2. Surprise Me! (about 1 min)

1. Click **Surprise Me!**.
2. Two Regions are highlighted on the globe. The sidebar shows the question, an Evidence label, the Region descriptions, the Variable definition and one chart per Region.
3. Drag the timeline. Both charts follow the selected month.

Say: "The engine found this pair on its own. These are real NASA monthly values, averaged over each Region."

Click **Surprise me again**. It picks a different pair and avoids Regions already shown in this session. If every worthwhile Discovery has been shown, the sidebar shows "Session complete" with a **Start a new session** button.

### 3. Become a Detective (about 2 min)

1. Click **Become a Detective**.
2. **Predict:** choose one answer to the question, then click **Check the data**.
3. **Check:** the screen says whether the guess matches the computed Trends, shows the comparison text and both series with their rates per decade. Click **Why might this happen?**.
4. **Reason:** possible causes appear, each tagged "Context from scientists". The page states that the data show change but do not establish cause.

Say: "The student commits to a prediction before seeing the answer. The engine never claims a cause."

### 4. How do we know? (about 1 min)

On the Check or Reason step, open **How do we know?**. It shows the Evidence label, the period analyzed, each rate with its 95% interval, the NASA source for each series with a link, and the method citation.

Say: "Strong, Some or Not enough evidence is rated from the data, with corrections for comparing many pairs."

Click **Back** to return to the main screen with the Discovery still selected.

### 5. Fallback (optional, about 30 s)

With `EARTHDATA_TOKEN` unset, request a series the seed set does not hold (not reachable from the UI; use the API):

```sh
curl -s "localhost:8000/api/series?region_id=sahel&variable_id=temperature&period_start=1990-01&period_end=1995-12"
```

Expected: `provenance: "preloaded"` and a `live_data_unavailable` notice saying the example differs from the requested data. This is what the UI shows when live data fails.

### 6. Live fetch (optional, needs a token)

Needs an Earthdata token. The API reads only the `EARTHDATA_TOKEN` environment variable; it does **not** load `.env` (the `.env` in `data/data_gathering/` is read by the gathering scripts only). Export it before starting the API, without echoing it:

```sh
set -a; . data/data_gathering/.env; set +a      # bash/zsh; in fish use `export EARTHDATA_TOKEN=...`
python -m uvicorn api.main:app --port 8000
curl -s "localhost:8000/api/series?region_id=sahel&variable_id=temperature&period_start=2000-01&period_end=2000-12"
```

Expected: `provenance: "live"`, 12 values, source `MERRA-2 M2TMNXSLV v5.12.4`. A repeat of the same request returns `provenance: "cache"`. Verified on 2026-11-15 (one 12-month request took 11.3 s, with the limit set to 120 s). The server's default limit is 15 s (`WEATHER_REPORT_LIVE_TIMEOUT_SECONDS`), so longer periods may time out and fall back to step 5. Stay with a 12-month period on stage.

## If something goes wrong

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Blank globe | No WebGL, or the Earth texture URL is unreachable | Use another browser or connect to the internet |
| Sidebar shows an error | API not running on :8000 | Start the API; check `/api/health` |
| "Session complete" screen | Every worthwhile Discovery shown this session | Click **Start a new session** |
| A "preloaded example" notice | Live data unavailable or not requested from the seed | Expected offline; see step 5 |
