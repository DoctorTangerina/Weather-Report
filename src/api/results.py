"""Result selection and validation; acquisition is a server-side boundary."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from engine import ENGINE_VERSION, applies_to
from engine.contracts import Catalog, Period

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
registry = Registry().with_resources(
    (schema["$id"], Resource.from_contents(schema))
    for path in SCHEMA_DIR.glob("*.schema.json")
    for schema in [json.loads(path.read_text(encoding="utf-8"))]
)
validator = Draft202012Validator(
    {"$ref": "https://weather-report.local/schemas/series.schema.json"},
    registry=registry,
)


def usable(payload: dict[str, Any], catalog: Catalog) -> bool:
    if not (
        validator.is_valid(payload)
        and payload["engine_version"] == ENGINE_VERSION
        and catalog.variable(payload["variable_id"]) is not None
        and applies_to(catalog, payload["region_id"], payload["variable_id"])
        and payload["quality"]["included"]
    ):
        return False
    start, end = payload["period"]["start"], payload["period"]["end"]
    if start > end or start[:4] == "0000" or end[:4] == "0000":
        return False
    if any(re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", m) is None for m in (start, end)):
        return False
    months = (int(end[:4]) - int(start[:4])) * 12 + int(end[5:]) - int(start[5:]) + 1
    return len(payload["values"]) == months and all(
        value is None or math.isfinite(value) for value in payload["values"]
    )


def example_response(
    payload: dict[str, Any], region_id: str, variable_id: str, period: Period
) -> dict[str, Any]:
    different = (
        payload["region_id"] != region_id
        or payload["variable_id"] != variable_id
        or payload["period"] != {"start": period.start, "end": period.end}
    )
    message = "Live data unavailable. Showing a preloaded example (dado pré-carregado)."
    if different:
        message += " This example is different from the requested data."
    return {
        "data": payload,
        "provenance": "preloaded",
        "notice": {"code": "live_data_unavailable", "message": message},
    }


def select_example(
    examples: list[dict[str, Any]],
    catalog: Catalog,
    region_id: str,
    variable_id: str,
) -> dict[str, Any] | None:
    candidates = [payload for payload in examples if usable(payload, catalog)]
    return min(
        candidates,
        key=lambda p: (
            0
            if (p["region_id"], p["variable_id"]) == (region_id, variable_id)
            else 1
            if p["variable_id"] == variable_id
            else 2,
            p["region_id"],
            p["variable_id"],
            p["period"]["start"],
            p["period"]["end"],
        ),
        default=None,
    )
