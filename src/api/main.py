"""HTTP layer over the engine (seam 2 of the testing plan).

Thin on purpose: it looks results up in the store, checks requests against the
catalog and serializes. Automatic Discovery statistics belong to the engine package; exploratory
correlation processing belongs to data/data_processing/.

Response bodies follow `schemas/responses.schema.json`: a resource under
`data`, a `notice` for live unavailability, and (for Series) `provenance`
that distinguishes live, cached and preloaded data.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from data.data_gathering.config import settings
from engine import (
    ENGINE_VERSION,
    JsonResultStore,
    Period,
    Series,
    applies_to,
    estimate_trend,
    load_catalog,
    rate_evidence,
    select_surprise,
)
from engine.contracts import Discovery, as_dict
from engine.discovery import SessionHistory

from .acquisition import AcquisitionUnavailable, acquire_series
from .area_cache import AreaSeriesCache
from .correlation import router as correlation_router
from .explore import (
    AGGREGATIONS,
    AREA_VARIABLES,
    FIRST_MONTH,
    LIMITS,
    SUB_MONTHLY_VARIABLES,
    TIME_STEPS,
    AcquisitionNeeded,
    Refusal,
    explore_series,
)
from .field_map import FieldCache, FieldJobs, field_view
from .grid_source import GridAcquisitionSource
from .jobs import SeriesJobs
from .processing import run_recipe
from .results import example_response, select_example, usable

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("WEATHER_REPORT_DATA_DIR", str(ROOT / "data" / "seed")))

# The catalog is configuration rather than a result set, so it does not move
# when DATA_DIR points at a different set of results.
CATALOG_PATH = Path(
    os.environ.get("WEATHER_REPORT_CATALOG", str(ROOT / "data" / "catalog.json"))
)

explore_jobs = SeriesJobs()
field_jobs = FieldJobs()
_aggregation_caches: dict[Path, JsonResultStore] = {}
_aggregation_seeds: dict[Path, JsonResultStore] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await explore_jobs.close()
    await field_jobs.close()


app = FastAPI(title="Weather Report", version=ENGINE_VERSION, lifespan=lifespan)

app.include_router(correlation_router)

catalog = load_catalog(CATALOG_PATH)
store = JsonResultStore(DATA_DIR, ENGINE_VERSION)
CACHE_DIR = Path(os.environ.get("WEATHER_REPORT_CACHE_DIR", ".scratch/results-cache"))
live_store = JsonResultStore(CACHE_DIR, ENGINE_VERSION)
# Selected areas (#79) are never Regions, so their Series are cached apart.
area_cache = AreaSeriesCache(CACHE_DIR / "areas")
LIVE_TIMEOUT_SECONDS = float(
    os.environ.get("WEATHER_REPORT_LIVE_TIMEOUT_SECONDS", "120")
)
if not math.isfinite(LIVE_TIMEOUT_SECONDS) or LIVE_TIMEOUT_SECONDS <= 0:
    raise ValueError("WEATHER_REPORT_LIVE_TIMEOUT_SECONDS must be positive and finite")
logger = logging.getLogger(__name__)


class SurpriseRequest(BaseModel):
    shown_discovery_ids: list[str] = []
    shown_region_ids: list[str] = []


def ok(data: Any, notice: dict[str, str] | None = None) -> dict[str, Any]:
    return {"data": data, "notice": notice}


def error(
    status: int, code: str, message: str, details: dict | None = None
) -> JSONResponse:
    body = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status, content={"error": body})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "engine_version": ENGINE_VERSION}


@app.get("/api/catalog")
def get_catalog() -> dict[str, Any]:
    return ok(as_dict(catalog))


def reject_outside_catalog(region_id: str, variable_id: str) -> JSONResponse | None:
    """BS-009: the catalogs are the only thing a client may ask for."""
    if catalog.region(region_id) is None:
        return error(
            422, "region_not_in_catalog", f"{region_id} is not in the Region catalog."
        )
    if catalog.variable(variable_id) is None:
        return error(
            422,
            "variable_not_in_catalog",
            f"{variable_id} is not in the Variable catalog.",
        )
    if not applies_to(catalog, region_id, variable_id):
        return error(
            422,
            "variable_not_available_for_region",
            f"{variable_id} is not offered for {region_id}.",
        )
    return None


@app.get("/api/series/available")
def list_available_series() -> dict[str, Any]:
    """The preloaded series held for each Region and Variable, without values.

    These are exactly the pairs /api/comparison can compare: it reads this store
    only, not the live cache, so a client can tell which pairs will work before
    asking."""
    return ok(store.available_series())


def get_acquisition_source() -> GridAcquisitionSource | None:
    """Override this dependency to supply grids without NASA or server credentials.

    None selects on-demand NASA subsetting inside the cancellable worker.
    """
    return None


@app.get("/api/series")
async def get_series(
    region_id: str,
    variable_id: str,
    period_start: str = "2000-01",
    period_end: str = "2024-12",
    acquisition_source: Annotated[
        GridAcquisitionSource | None, Depends(get_acquisition_source)
    ] = None,
) -> Any:
    rejection = reject_outside_catalog(region_id, variable_id)
    if rejection is not None:
        return rejection

    if (
        any(
            re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", month) is None
            or month[:4] == "0000"
            for month in (period_start, period_end)
        )
        or period_start > period_end
    ):
        return error(
            422, "invalid_period", "Use an inclusive YYYY-MM period with start <= end."
        )
    region = catalog.region(region_id)
    variable = catalog.variable(variable_id)
    assert region is not None and variable is not None
    period = Period(period_start, period_end)
    payload = live_store.series(region_id, variable_id, period)
    if payload is not None and usable(payload, catalog):
        return {**ok(payload), "provenance": "cache"}
    payload = store.series(region_id, variable_id, period)
    if payload is not None and usable(payload, catalog):
        return {**ok(payload), "provenance": "preloaded"}
    try:
        token = settings().get("EARTHDATA_TOKEN")
        if not token and acquisition_source is None:
            raise AcquisitionUnavailable("Server token unavailable")
        source_options: dict[str, Any] = (
            {"source": acquisition_source} if acquisition_source is not None else {}
        )
        acquired = await asyncio.wait_for(
            acquire_series(
                region,
                variable,
                period,
                token=token or "",
                **source_options,
            ),
            timeout=LIVE_TIMEOUT_SECONDS,
        )
        if not usable(acquired, catalog) or (
            acquired["region_id"],
            acquired["variable_id"],
            acquired["period"],
        ) != (region_id, variable_id, {"start": period.start, "end": period.end}):
            raise AcquisitionUnavailable(
                "Acquisition did not yield a usable exact result"
            )
    except (AcquisitionUnavailable, TimeoutError) as exc:
        # Exception text and tracebacks may contain credentials; log the category only.
        logger.warning("Live acquisition unavailable: %s", type(exc).__name__)
    else:
        try:
            live_store.save_series(acquired)
        except OSError:
            logger.error("Live result could not be persisted")
        return {**ok(acquired), "provenance": "live"}
    payload = select_example(store.all_series(), catalog, region_id, variable_id)
    if payload is not None:
        return example_response(payload, region_id, variable_id, period)
    return error(
        503, "live_data_unavailable", "No live data or usable examples available."
    )


@app.get("/api/explore/field-map")
async def get_field_map(
    variable_id: str,
    region_id: str | None = None,
    rectangle: Annotated[list[str] | None, Query()] = None,
    aggregation: str = "mean",
    time_step: str = "monthly",
    period_start: str = FIRST_MONTH,
    period_end: str | None = None,
    acquisition_source: Annotated[
        GridAcquisitionSource | None, Depends(get_acquisition_source)
    ] = None,
) -> Any:
    try:
        view = field_view(
            catalog,
            region_id,
            rectangle,
            variable_id,
            aggregation,
            time_step,
            period_start,
            period_end or explore_latest_month(),
            explore_latest_month(),
        )
    except Refusal as refusal:
        return error(refusal.status, refusal.code, refusal.message)
    cache = FieldCache(live_store.root / "field-maps" / ENGINE_VERSION)
    result = cache.read(view)
    if result is not None:
        return {**ok(result), "provenance": "cache"}
    job = field_jobs.start(
        view,
        catalog,
        cache,
        acquisition_source,
        LIVE_TIMEOUT_SECONDS,
        lambda: cache.read(view),
    )
    return JSONResponse(status_code=202, content=ok({"job": dict(job)}))


@app.get("/api/explore/series")
async def get_explore_series(
    region_id: str | None = None,
    rectangle: Annotated[list[str] | None, Query()] = None,
    variable_id: Annotated[list[str] | None, Query()] = None,
    aggregation: str = "mean",
    time_step: str = "monthly",
    period_start: str = FIRST_MONTH,
    period_end: str | None = None,
    acquisition_source: Annotated[
        GridAcquisitionSource | None, Depends(get_acquisition_source)
    ] = None,
) -> Any:
    """Explore My World: the Series of one catalog Region or one Selected area.

    A Selected area is one or more `rectangle=west,south,east,north` values.
    """
    build = partial(
        explore_series,
        catalog,
        store,
        region_id,
        variable_id or [],
        aggregation,
        time_step,
        period_start,
        period_end,
        rectangles=rectangle,
        cache=explore_cache(aggregation, time_step),
        seed=explore_seed(aggregation),
        area_cache=explore_area_cache(aggregation, time_step),
        latest=explore_latest_month(),
    )
    try:
        data, provenance = build()
    except AcquisitionNeeded as needed:
        cache = explore_cache(aggregation, time_step)
        assert cache is not None, "A validated Explore My World view requires a cache."
        job = explore_jobs.start(
            needed.view,
            catalog,
            cache,
            acquisition_source,
            LIVE_TIMEOUT_SECONDS,
            finish=lambda: build()[0],
            area_cache=explore_area_cache(aggregation, time_step),
        )
        return JSONResponse(status_code=202, content=ok({"job": dict(job)}))
    except Refusal as refusal:
        return error(refusal.status, refusal.code, refusal.message)
    return {**ok(data), "provenance": provenance}


def explore_seed(aggregation: str) -> JsonResultStore | None:
    """The seed set's Series built with `aggregation`; it holds only monthly ones.

    Means are the seed set the Discoveries come from. Every other Aggregation
    lives in its own folder under it, which the Discovery engine never reads.
    """
    if aggregation == "mean":
        return store
    if aggregation not in AGGREGATIONS:
        return None
    root = store.root / "aggregations" / aggregation
    if root not in _aggregation_seeds:
        _aggregation_seeds[root] = JsonResultStore(root, ENGINE_VERSION)
    return _aggregation_seeds[root]


def explore_cache(
    aggregation: str, time_step: str = "monthly"
) -> JsonResultStore | None:
    """Where Explore My World keeps the Series pieces it acquired with `aggregation`.

    One folder per Aggregation beside the live results cache, which is keyed
    without one, and for a sub-monthly Time step one folder per Time step above
    those. A piece keeps its values even when it alone fails the Quality gate,
    so nothing that serves stored Series directly (`/api/series`) reads it.
    """
    if aggregation not in AGGREGATIONS or time_step not in TIME_STEPS:
        # An unknown Aggregation or Time step is refused before any cache is read.
        return None
    root = live_store.root / "explore"
    if time_step != "monthly":
        root = root / time_step
    root = root / aggregation
    if root not in _aggregation_caches:
        _aggregation_caches[root] = JsonResultStore(root, ENGINE_VERSION)
    return _aggregation_caches[root]


def explore_area_cache(
    aggregation: str, time_step: str = "monthly"
) -> AreaSeriesCache | None:
    """Where Explore My World keeps Selected-area Series built with `aggregation`.

    Monthly means live in the area cache itself; every other monthly
    Aggregation in its own folder under it. A sub-monthly Time step has its own
    folder, with one folder per Aggregation under it.
    """
    if aggregation not in AGGREGATIONS or time_step not in TIME_STEPS:
        # An unknown Aggregation or Time step is refused before any cache is read.
        return None
    if time_step != "monthly":
        return AreaSeriesCache(area_cache.root / time_step / aggregation)
    if aggregation == "mean":
        return area_cache
    return AreaSeriesCache(area_cache.root / aggregation)


def explore_latest_month() -> str:
    configured = os.environ.get("WEATHER_REPORT_LATEST_MONTH")
    if configured is not None:
        if (
            re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", configured) is None
            or configured < FIRST_MONTH
        ):
            raise ValueError(
                "WEATHER_REPORT_LATEST_MONTH must be YYYY-MM, from 2000-01."
            )
        return configured
    last = datetime.now(UTC).replace(day=1) - timedelta(days=1)
    return last.strftime("%Y-%m")


@app.get("/api/explore/options")
def get_explore_options() -> Any:
    def variable_ids(allowed: tuple[str, ...] | None) -> list[str]:
        return [
            variable.variable_id
            for variable in catalog.variables
            if allowed is None or variable.variable_id in allowed
        ]

    return ok(
        {
            "latest_month": explore_latest_month(),
            "area_variable_ids": variable_ids(AREA_VARIABLES),
            # Each Time step with the Variables that have data at it and its cap.
            "time_steps": [
                {
                    "time_step": time_step,
                    "variable_ids": variable_ids(
                        None if time_step == "monthly" else SUB_MONTHLY_VARIABLES
                    ),
                    "max_months": LIMITS[time_step][0] if time_step in LIMITS else None,
                    "limit": LIMITS[time_step][1] if time_step in LIMITS else None,
                }
                for time_step in TIME_STEPS
            ],
        }
    )


@app.post("/api/explore/process")
async def process_explore_series(request: Request) -> Any:
    """Apply a Processing recipe to Source or Derived series (#83). Stateless."""
    try:
        body = json.loads(await request.body())
    except ValueError:
        return error(422, "invalid_processing_request", "Send the request as JSON.")
    try:
        return ok(await run_in_threadpool(run_recipe, body))
    except Refusal as refusal:
        return error(refusal.status, refusal.code, refusal.message, refusal.details)


@app.get("/api/explore/jobs/{job_id}")
async def get_explore_job(job_id: str) -> Any:
    job = explore_jobs.jobs.get(job_id) or field_jobs.jobs.get(job_id)
    if job is None:
        return error(404, "job_not_found", "No background job with this reference.")
    return ok({"job": dict(job)})


@app.get("/api/comparison")
def compare_regions(
    region_a: str,
    region_b: str,
    variable_id: str,
    period_start: str = "2000-01",
    period_end: str = "2024-12",
) -> Any:
    """Analyze any catalog pair, whether or not it forms a Discovery.

    The two requested Trends form the multiple-comparison family for this
    analysis. Statistics and Evidence labels are computed by the engine.
    """
    for region_id in (region_a, region_b):
        rejection = reject_outside_catalog(region_id, variable_id)
        if rejection is not None:
            return rejection

    period = Period(period_start, period_end)
    series = []
    for region_id in (region_a, region_b):
        item = store.series(region_id, variable_id, period)
        if item is None:
            return error(
                404,
                "result_not_available",
                "No stored series for this pair and period.",
            )
        series.append(item)
    try:
        trends = rate_evidence(
            [estimate_trend(Series.from_dict(item)) for item in series]
        )
    except ValueError:
        return error(
            404, "result_not_available", "Not enough data to analyze this pair."
        )
    return ok({"trends": [as_dict(trend) for trend in trends], "series": series})


@app.get("/api/discoveries")
def list_discoveries() -> dict[str, Any]:
    return ok(store.discoveries())


@app.get("/api/discoveries/{discovery_id}")
def get_discovery(discovery_id: str) -> Any:
    payload = store.discovery(discovery_id)
    if payload is None:
        return error(
            404, "result_not_available", f"No Discovery with id {discovery_id}."
        )
    return ok(payload)


@app.post("/api/discoveries/surprise")
def surprise(request: SurpriseRequest) -> Any:
    history = SessionHistory(
        shown_discovery_ids=tuple(request.shown_discovery_ids),
        shown_region_ids=tuple(request.shown_region_ids),
    )
    candidates = [Discovery.from_dict(payload) for payload in store.discoveries()]
    chosen = select_surprise(candidates, history)
    if chosen is None:
        return error(
            404,
            "no_discovery_left_in_session",
            "Every Discovery worth headlining has already been shown in this session.",
        )
    return ok(as_dict(chosen))
