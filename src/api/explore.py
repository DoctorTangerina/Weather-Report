"""Explore My World Series: seed/cache lookup, validation and acquisition requests.

A view is a catalog Region or a Selected area (#79), never both. Monthly means
absent from the stores are built by #77's background jobs; a Selected area is
always built that way. Other Aggregations and Time steps remain owned by their
follow-up tickets.
"""

from __future__ import annotations

import math
import re
from typing import Any

from data.data_gathering.quality_gate import assess_quality
from engine import Period, applies_to
from engine.contracts import Catalog
from engine.store import ResultStore

from .area_cache import AreaSeriesCache
from .products import PRODUCTS

FIRST_MONTH = "2000-01"
MAX_VARIABLES = 5
AGGREGATIONS = (
    "mean",
    "median",
    "minimum",
    "maximum",
    "root_mean_square",
    "standard_deviation",
    "mean_absolute_value",
)
TIME_STEPS = ("3-hourly", "daily", "monthly")
# ADR 0004: how many months a sub-monthly request may span.
LIMITS = {"3-hourly": (12, "1 year"), "daily": (120, "10 years")}
_MONTH = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])")
# A Selected area can only have Variables NASA can subset on demand (ADR 0004).
AREA_VARIABLES = tuple(PRODUCTS)


class AcquisitionNeeded(Exception):
    def __init__(self, view: dict[str, Any]) -> None:
        self.view = view


class Refusal(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def latest_month(store: ResultStore) -> str:
    """The last month any preloaded Series covers."""
    return max(
        (item["period"]["end"] for item in store.available_series()),
        default=FIRST_MONTH,
    )


def _months(start: str, end: str) -> int:
    """Calendar months from start to end, counting both."""
    return (int(end[:4]) - int(start[:4])) * 12 + int(end[5:]) - int(start[5:]) + 1


def _invalid_area(message: str) -> Refusal:
    return Refusal(422, "invalid_area", message)


def _longitudes(box: list[float]) -> tuple[float, float]:
    """A box's longitude span, unwrapped so that east > west."""
    west, _, east, _ = box
    return west, east if east > west else east + 360


def _touch(a: list[float], b: list[float]) -> bool:
    if max(a[1], b[1]) > min(a[3], b[3]):
        return False
    (a_west, a_east), (b_west, b_east) = _longitudes(a), _longitudes(b)
    return any(
        max(a_west, b_west + turn) <= min(a_east, b_east + turn)
        for turn in (-360, 0, 360)
    )


def parse_area(texts: list[str]) -> list[list[float]]:
    """Rectangles given as "west,south,east,north" in degrees, joined into one area."""
    boxes = []
    for text in texts:
        try:
            west, south, east, north = (float(part) for part in text.split(","))
        except ValueError:
            raise _invalid_area(
                "Give each rectangle as west,south,east,north in degrees."
            ) from None
        if not (
            all(math.isfinite(value) for value in (west, south, east, north))
            and -180 <= west <= 180
            and -180 <= east <= 180
            and west != east
            and -90 <= south < north <= 90
        ):
            raise _invalid_area(
                "Longitudes run from -180 to 180 and latitudes from -90 to 90, "
                "with south below north and west different from east."
            )
        boxes.append([west, south, east, north])
    joined, waiting = boxes[:1], boxes[1:]
    while waiting:
        reached = [box for box in waiting if any(_touch(box, j) for j in joined)]
        if not reached:
            raise _invalid_area(
                "The rectangles of a Selected area must touch or overlap. "
                "Move the new rectangle against the area, or start a new one."
            )
        joined += reached
        waiting = [box for box in waiting if box not in reached]
    return boxes


def _validate_geometry(
    catalog: Catalog,
    region_id: str | None,
    rectangles: list[str],
    variable_ids: list[str],
) -> list[list[float]] | None:
    """The Selected area's rectangles, or None for a valid catalog Region."""
    if (region_id is None) == (not rectangles):
        raise _invalid_area("Choose either a catalog Region or a Selected area.")
    if region_id is not None and catalog.region(region_id) is None:
        raise Refusal(
            422, "region_not_in_catalog", f"{region_id} is not in the Region catalog."
        )
    area = parse_area(rectangles) if rectangles else None
    _validate_variables(catalog, region_id, variable_ids)
    return area


def _validate_variables(
    catalog: Catalog, region_id: str | None, variable_ids: list[str]
) -> None:
    if not 1 <= len(variable_ids) <= MAX_VARIABLES:
        raise Refusal(
            422,
            "invalid_variable_count",
            "Choose between one and five Variables.",
        )
    if len(set(variable_ids)) != len(variable_ids):
        raise Refusal(422, "duplicate_variable", "Choose each Variable only once.")
    for variable_id in variable_ids:
        if catalog.variable(variable_id) is None:
            raise Refusal(
                422,
                "variable_not_in_catalog",
                f"{variable_id} is not in the Variable catalog.",
            )
        if region_id is None and variable_id not in AREA_VARIABLES:
            raise Refusal(
                422,
                "variable_not_available_for_area",
                f"{variable_id} cannot be fetched for a Selected area yet.",
            )
        if region_id is not None and not applies_to(catalog, region_id, variable_id):
            raise Refusal(
                422,
                "variable_not_available_for_region",
                f"{variable_id} is not offered for {region_id}.",
            )


def _validate_view(
    aggregation: str, time_step: str, start: str, end: str, latest: str
) -> None:
    if aggregation not in AGGREGATIONS:
        raise Refusal(
            422,
            "invalid_aggregation",
            "Choose an Aggregation from " + ", ".join(AGGREGATIONS) + ".",
        )
    if time_step not in TIME_STEPS:
        raise Refusal(
            422,
            "invalid_time_step",
            "Choose a Time step from " + ", ".join(TIME_STEPS) + ".",
        )
    if not (_MONTH.fullmatch(start) and _MONTH.fullmatch(end)) or start > end:
        raise Refusal(
            422, "invalid_period", "Use an inclusive YYYY-MM period with start <= end."
        )
    if start < FIRST_MONTH or end > latest:
        raise Refusal(
            422,
            "period_out_of_range",
            f"Periods run from {FIRST_MONTH} to {latest}, the latest available month.",
        )
    if time_step in LIMITS:
        months, label = LIMITS[time_step]
        if _months(start, end) > months:
            raise Refusal(
                422,
                "period_too_long",
                f"{time_step.capitalize()} periods are limited to {label}.",
            )


def _cut(payload: dict[str, Any], start: str, end: str) -> dict[str, Any]:
    """The stored Series for [start, end], with the Quality gate re-applied."""
    stored = payload["period"]
    if stored == {"start": start, "end": end}:
        return payload
    offset = _months(stored["start"], start) - 1
    values = payload["values"][offset : offset + _months(start, end)]
    land_fraction = payload["quality"]["valid_land_fraction"]
    quality = assess_quality(
        values,
        land_only=land_fraction is not None,
        valid_land_fraction=land_fraction,
    )
    return {
        **payload,
        "period": {"start": start, "end": end},
        # An excluded Series carries no values anything could use.
        "values": values if quality.included else [None] * len(values),
        "quality": {
            "included": quality.included,
            "missing_fraction": quality.missing_fraction,
            "valid_land_fraction": quality.valid_land_fraction,
            "exclusions": list(quality.exclusions),
        },
    }


def explore_series(
    catalog: Catalog,
    store: ResultStore,
    region_id: str | None,
    variable_ids: list[str],
    aggregation: str,
    time_step: str,
    start: str,
    end: str | None,
    *,
    rectangles: list[str] | None = None,
    cache: ResultStore | None = None,
    area_cache: AreaSeriesCache | None = None,
    latest: str | None = None,
) -> dict[str, Any]:
    """The view's Series, or a Refusal saying why it cannot be given."""
    latest = latest or latest_month(store)
    end = latest_month(store) if end is None else end
    area = _validate_geometry(catalog, region_id, rectangles or [], variable_ids)
    _validate_view(aggregation, time_step, start, end, latest)
    if (aggregation, time_step) != ("mean", "monthly"):
        raise Refusal(
            501,
            "not_available_yet",
            "Only monthly mean Series are available so far. Other Aggregations "
            "and Time steps need data fetched from NASA, which is not built yet.",
        )
    geometry = (
        {"region_id": region_id} if area is None else {"area": {"rectangles": area}}
    )
    view = {
        **geometry,
        "aggregation": aggregation,
        "time_step": time_step,
        "period": {"start": start, "end": end},
    }
    if area is not None:
        stored = [
            area_cache.series(area, v, Period(start, end)) if area_cache else None
            for v in variable_ids
        ]
        if any(payload is None for payload in stored):
            raise AcquisitionNeeded({**view, "variable_ids": variable_ids})
        return {**view, "series": stored}
    covering = {
        item["variable_id"]: item["period"]
        for item in store.available_series()
        if item["region_id"] == region_id
        and item["period"]["start"] <= start
        and item["period"]["end"] >= end
    }
    cached = {
        v: cache.series(region_id, v, Period(start, end)) if cache else None
        for v in variable_ids
    }
    missing = [v for v in variable_ids if v not in covering and cached[v] is None]
    if missing:
        raise AcquisitionNeeded({**view, "variable_ids": variable_ids})
    series = []
    for variable_id in variable_ids:
        if cached[variable_id] is not None:
            series.append(cached[variable_id])
            continue
        period = Period(**covering[variable_id])
        payload = store.series(region_id, variable_id, period)
        assert payload is not None
        series.append(_cut(payload, start, end))
    return {**view, "series": series}
