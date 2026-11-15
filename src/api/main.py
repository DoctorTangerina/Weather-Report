"""HTTP layer over the engine (seam 2 of the testing plan).

Thin on purpose: it looks results up in the store, checks requests against the
catalog and serializes. Every statistic and every selection rule belongs to the
engine package.

Response bodies follow `schemas/responses.schema.json`: a resource under
`data`, plus a `notice` that stays null until something other than a fresh
result was served (ticket #13).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

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

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("WEATHER_REPORT_DATA_DIR", str(ROOT / "data" / "seed")))

# The catalog is configuration rather than a result set, so it does not move
# when DATA_DIR points at a different set of results.
CATALOG_PATH = Path(
    os.environ.get("WEATHER_REPORT_CATALOG", str(ROOT / "data" / "catalog.json"))
)

app = FastAPI(title="Weather Report", version=ENGINE_VERSION)

catalog = load_catalog(CATALOG_PATH)
store = JsonResultStore(DATA_DIR, ENGINE_VERSION)


class SurpriseRequest(BaseModel):
    shown_discovery_ids: list[str] = []
    shown_region_ids: list[str] = []


def ok(data: Any, notice: dict[str, str] | None = None) -> dict[str, Any]:
    return {"data": data, "notice": notice}


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"error": {"code": code, "message": message}}
    )


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


@app.get("/api/series")
def get_series(
    region_id: str,
    variable_id: str,
    period_start: str = "2000-01",
    period_end: str = "2024-12",
) -> Any:
    rejection = reject_outside_catalog(region_id, variable_id)
    if rejection is not None:
        return rejection

    payload = store.series(region_id, variable_id, Period(period_start, period_end))
    if payload is None:
        # Ticket #13 replaces this with a live fetch and a seed-set fallback.
        return error(
            404,
            "result_not_available",
            f"No stored series for {region_id}/{variable_id} over {period_start}..{period_end}.",
        )
    return ok(payload)


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
