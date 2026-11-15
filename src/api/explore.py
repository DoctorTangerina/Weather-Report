"""Explore My World Series: seed/cache lookup, validation and acquisition requests.

The seed set answers monthly Series for every Aggregation (#78): means beside
the Discoveries, the other Aggregations in their own folders. Months the seed
set does not hold, such as those after it ends, are acquired by #77's background
jobs, and only those months: the Series joins the seeded months to them.
Sub-monthly Time steps remain owned by their follow-up ticket.
"""

from __future__ import annotations

import re
from typing import Any

from data.data_gathering.aggregation import AGGREGATIONS
from data.data_gathering.quality_gate import assess_quality
from engine import Period, applies_to
from engine.contracts import Catalog
from engine.store import ResultStore

FIRST_MONTH = "2000-01"
MAX_VARIABLES = 5
TIME_STEPS = ("3-hourly", "daily", "monthly")
# ADR 0004: how many months a sub-monthly request may span.
LIMITS = {"3-hourly": (12, "1 year"), "daily": (120, "10 years")}
_MONTH = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])")


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


def _validate(
    catalog: Catalog,
    region_id: str,
    variable_ids: list[str],
    aggregation: str,
    time_step: str,
    start: str,
    end: str,
    latest: str,
) -> None:
    if catalog.region(region_id) is None:
        raise Refusal(
            422, "region_not_in_catalog", f"{region_id} is not in the Region catalog."
        )
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
        if not applies_to(catalog, region_id, variable_id):
            raise Refusal(
                422,
                "variable_not_available_for_region",
                f"{variable_id} is not offered for {region_id}.",
            )
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


def _next_month(month: str) -> str:
    year, number = int(month[:4]), int(month[5:])
    return f"{year + number // 12:04d}-{number % 12 + 1:02d}"


def _values(payload: dict[str, Any], start: str, end: str) -> list[float | None]:
    """The payload's values for the months [start, end] inside its period."""
    offset = _months(payload["period"]["start"], start) - 1
    return payload["values"][offset : offset + _months(start, end)]


def _gated(
    base: dict[str, Any],
    values: list[float | None],
    start: str,
    end: str,
    land_fraction: float | None,
) -> dict[str, Any]:
    """`base` as the Series of `values` over [start, end], judged by the gate."""
    quality = assess_quality(
        values,
        land_only=land_fraction is not None,
        valid_land_fraction=land_fraction,
    )
    return {
        **base,
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


def _cut(payload: dict[str, Any], start: str, end: str) -> dict[str, Any]:
    """The stored Series for [start, end], with the Quality gate re-applied."""
    if payload["period"] == {"start": start, "end": end}:
        return payload
    land_fraction = payload["quality"]["valid_land_fraction"]
    return _gated(payload, _values(payload, start, end), start, end, land_fraction)


def _stitch(
    head: dict[str, Any] | None, piece: dict[str, Any], start: str, end: str
) -> dict[str, Any]:
    """Seeded months from `start`, then the acquired `piece` up to `end`.

    The piece keeps its values even if it alone would fail the gate, so the
    Quality gate judges the whole period at once.
    """
    values = list(piece["values"])
    if head is not None:
        values = _values(head, start, head["period"]["end"]) + values
    base = head or piece
    land_fraction = base["quality"]["valid_land_fraction"]
    return _gated(base, values, start, end, land_fraction)


def _seed_head(
    seed: ResultStore | None, region_id: str, variable_id: str, start: str
) -> dict[str, Any] | None:
    """The seeded Series that holds `start`, reaching furthest past it."""
    periods = [
        item["period"]
        for item in (seed.available_series() if seed is not None else [])
        if item["region_id"] == region_id
        and item["variable_id"] == variable_id
        and item["period"]["start"] <= start <= item["period"]["end"]
    ]
    if not periods:
        return None
    period = max(periods, key=lambda item: item["end"])
    return seed.series(region_id, variable_id, Period(**period))


def explore_series(
    catalog: Catalog,
    store: ResultStore,
    region_id: str,
    variable_ids: list[str],
    aggregation: str,
    time_step: str,
    start: str,
    end: str | None,
    *,
    cache: ResultStore | None = None,
    seed: ResultStore | None = None,
    latest: str | None = None,
) -> tuple[dict[str, Any], str]:
    """The view's Series and their provenance, or a Refusal saying why not.

    `store` is the seed set of means, which also sets the default end month.
    `seed` holds seeded Series built with this `aggregation` (for the mean it
    defaults to `store`). `cache` holds acquired Series pieces built with it,
    with their values kept even when a piece alone fails the gate. Each Series
    takes its first months from the seed set and the rest from a piece. When a
    piece is missing, AcquisitionNeeded names only the months to acquire.
    Provenance is "cache" when any piece was used, otherwise "preloaded".
    """
    latest = latest or latest_month(store)
    end = latest_month(store) if end is None else end
    _validate(
        catalog, region_id, variable_ids, aggregation, time_step, start, end, latest
    )
    if time_step != "monthly":
        raise Refusal(
            501,
            "not_available_yet",
            "Only monthly Series are available so far. Finer Time steps need "
            "data fetched from NASA, which is not built yet.",
        )
    if seed is None and aggregation == "mean":
        seed = store
    parts = {}
    acquire = {}
    for variable_id in variable_ids:
        head = _seed_head(seed, region_id, variable_id, start)
        if head is not None and head["period"]["end"] >= end:
            parts[variable_id] = (head, None)
            continue
        piece_start = _next_month(head["period"]["end"]) if head else start
        piece = (
            cache.series(region_id, variable_id, Period(piece_start, end))
            if cache is not None
            else None
        )
        if piece is None:
            acquire[variable_id] = {"start": piece_start, "end": end}
        parts[variable_id] = (head, piece)
    if acquire:
        raise AcquisitionNeeded(
            {
                "region_id": region_id,
                "variable_ids": variable_ids,
                "aggregation": aggregation,
                "time_step": time_step,
                "period": {"start": start, "end": end},
                "acquire": acquire,
            }
        )
    series = [
        _cut(head, start, end) if piece is None else _stitch(head, piece, start, end)
        for head, piece in (parts[variable_id] for variable_id in variable_ids)
    ]
    data = {
        "region_id": region_id,
        "aggregation": aggregation,
        "time_step": time_step,
        "period": {"start": start, "end": end},
        "series": series,
    }
    used_cache = any(piece is not None for _, piece in parts.values())
    return data, "cache" if used_cache else "preloaded"
