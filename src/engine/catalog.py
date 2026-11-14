"""Loading the fixed Region and Variable catalogs.

Catalog content is ticket #3. This module only turns the JSON into contract
objects and answers membership questions about it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import Bbox, Catalog, PossibleCause, Region, Source, Variable


def load_catalog(path: str | Path) -> Catalog:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return catalog_from_dict(payload)


def catalog_from_dict(payload: dict[str, Any]) -> Catalog:
    return Catalog(
        regions=tuple(_region(entry) for entry in payload["regions"]),
        variables=tuple(_variable(entry) for entry in payload["variables"]),
        method_citation=payload["method_citation"],
        engine_version=payload["engine_version"],
    )


def applies_to(catalog: Catalog, region_id: str, variable_id: str) -> bool:
    """Whether a Variable is offered for a Region, e.g. soil moisture over ocean."""
    region = catalog.region(region_id)
    return region is not None and variable_id in region.variable_ids


def _region(entry: dict[str, Any]) -> Region:
    return Region(
        region_id=entry["region_id"],
        name=entry["name"],
        description=entry["description"],
        bbox=Bbox(**entry["bbox"]),
        variable_ids=tuple(entry["variable_ids"]),
    )


def _variable(entry: dict[str, Any]) -> Variable:
    return Variable(
        variable_id=entry["variable_id"],
        name=entry["name"],
        units=entry["units"],
        definition=entry["definition"],
        source=Source(**entry["source"]),
        land_only=entry["land_only"],
        possible_causes=tuple(
            PossibleCause(text=cause["text"]) for cause in entry["possible_causes"]
        ),
    )
