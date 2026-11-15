"""Series on demand for Explore My World (#75, spec #72 BS-007).

One request describes one view: a catalog Region, one to five Variables, one
Aggregation, one Time step and one period. Monthly area-weighted means are cut
from the preloaded Series. Any other Aggregation or Time step needs data fetched
from NASA, which arrives with background jobs (#77), so it is refused for now.
"""

from __future__ import annotations

import re
from typing import Any

from data.data_gathering.quality_gate import assess_quality
from engine import Period, applies_to
from engine.contracts import Catalog
from engine.store import ResultStore

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
    region_id: str,
    variable_ids: list[str],
    aggregation: str,
    time_step: str,
    start: str,
    end: str | None,
) -> dict[str, Any]:
    """The view's Series, or a Refusal saying why it cannot be given."""
    latest = latest_month(store)
    end = latest if end is None else end
    _validate(
        catalog, region_id, variable_ids, aggregation, time_step, start, end, latest
    )
    if (aggregation, time_step) != ("mean", "monthly"):
        raise Refusal(
            501,
            "not_available_yet",
            "Only monthly mean Series are available so far. Other Aggregations "
            "and Time steps need data fetched from NASA, which is not built yet.",
        )
    covering = {
        item["variable_id"]: item["period"]
        for item in store.available_series()
        if item["region_id"] == region_id
        and item["period"]["start"] <= start
        and item["period"]["end"] >= end
    }
    missing = [v for v in variable_ids if v not in covering]
    if missing:
        raise Refusal(
            404,
            "result_not_available",
            f"No stored Series for {region_id} and {', '.join(missing)} "
            f"from {start} to {end}.",
        )
    series = []
    for variable_id in variable_ids:
        period = Period(**covering[variable_id])
        payload = store.series(region_id, variable_id, period)
        assert payload is not None
        series.append(_cut(payload, start, end))
    return {
        "region_id": region_id,
        "aggregation": aggregation,
        "time_step": time_step,
        "period": {"start": start, "end": end},
        "series": series,
    }
