"""Processing recipes for Explore My World (#83, spec #72 BS-011).

Stateless: a request carries its inputs and its Processing recipe, the
data-layer processing of #46 (#47-#53) applies it, and nothing is kept, so
replaying a recipe means sending the same request again. A Source series from
/api/explore/series holds one value per Time step from the first day of
period.start and no timestamps; they are laid out here for the data layer.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from data.data_processing import ProcessingError, process_series

from .explore import Refusal

_SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"
_REQUEST = Draft202012Validator(
    {
        "$ref": "https://weather-report.local/schemas/responses.schema.json"
        "#/$defs/processingRequest"
    },
    registry=Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema))
        for path in _SCHEMAS.glob("*.schema.json")
        for schema in [json.loads(path.read_text(encoding="utf-8"))]
    ),
)
_STEPS = {
    "daily": (timedelta(days=1), "%Y-%m-%d"),
    "3-hourly": (timedelta(hours=3), "%Y-%m-%dT%H:00:00Z"),
}


def _timestamps(period: dict[str, str], time_step: str) -> list[str]:
    """One timestamp per Time step in the whole months of `period`, in order."""
    cursor = datetime.strptime(period["start"], "%Y-%m")
    year, month = map(int, period["end"].split("-"))
    end = datetime(year + (month == 12), 1 if month == 12 else month + 1, 1)
    stamps = []
    while cursor < end:
        if time_step == "monthly":
            stamps.append(cursor.strftime("%Y-%m"))
            cursor = cursor.replace(
                year=cursor.year + (cursor.month == 12),
                month=1 if cursor.month == 12 else cursor.month + 1,
            )
        else:
            step, pattern = _STEPS[time_step]
            stamps.append(cursor.strftime(pattern))
            cursor += step
    return stamps


def _source(name: str, item: dict[str, Any]) -> dict[str, Any]:
    """A Source series in the data layer's form, keeping all its metadata."""
    series, time_step = item["series"], item["time_step"]
    period = series["period"]
    stamps = _timestamps(period, time_step)
    if len(stamps) != len(series["values"]):
        raise Refusal(
            422,
            "invalid_processing_request",
            f"Input {name} has {len(series['values'])} values, but a {time_step} "
            f"Series from {period['start']} to {period['end']} has {len(stamps)}.",
        )
    return {
        **series,
        "timestamps": stamps,
        "time_step": time_step,
        # The view's Aggregation: resampling then combines over time by it (#48).
        "aggregation": item["aggregation"],
    }


def _malformed(body: Any) -> Refusal:
    error = next(iter(_REQUEST.iter_errors(body)))
    where = list(error.absolute_path)
    if len(where) >= 2 and where[0] == "series":
        message = (
            f"Input {where[1]} must be a Source series as /api/explore/series "
            "returned it, sent as {time_step, aggregation, series}, or a Derived "
            "series from an earlier response, sent as {derived}."
        )
    elif where and where[0] == "operations":
        message = "operations must be a non-empty list of steps, each with an id."
    else:
        message = (
            "Send an object with `series` (named inputs) and `operations` "
            "(the Processing recipe)."
        )
    return Refusal(422, "invalid_processing_request", message)


def run_recipe(body: Any) -> dict[str, Any]:
    """The Derived series, comparisons, recipe and warnings for one request."""
    if not _REQUEST.is_valid(body):
        raise _malformed(body)
    inputs = {
        name: item["derived"] if "derived" in item else _source(name, item)
        for name, item in body["series"].items()
    }
    try:
        return process_series({"series": inputs, "operations": body["operations"]})
    except ProcessingError as refusal:
        raise Refusal(
            422,
            "processing_refused",
            str(refusal),
            {"reason": refusal.code, **refusal.details},
        ) from None
