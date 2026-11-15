"""Field map values at native spatial resolution; no spatial reduction."""

import math
from pathlib import Path

from .catalog_series import (
    _cell_conversion,
    _load_catalog,
    _months,
    _step_key,
    _step_value,
    _steps,
    units_at,
)
from .models import Bbox, Period, SelectedArea
from .selection import TimeWindow
from .series import load_series_config, open_source


def get_field_map(request: dict, config: Path, catalog_path: Path) -> dict:
    catalog = _load_catalog(catalog_path)
    variable = next(
        v for v in catalog["variables"] if v["variable_id"] == request["variable_id"]
    )
    entry = load_series_config(config)["CATALOG_SERIES"][request["variable_id"]]
    period = Period(**request["period"])
    time_step = request["time_step"]
    timestamps = _steps(_months(period), time_step)
    rectangles = request.get("rectangles")
    area = (
        SelectedArea(tuple(map(tuple, rectangles)))
        if rectangles
        else Bbox(**dict(zip(("west", "south", "east", "north"), request["bbox"])))
    )
    fields = open_source(config).select_cells(
        area,
        entry.get("variable", variable["source"]["variable"]),
        TimeWindow.create(period.start, period.end),
        entry.get("dataset_id"),
        _cell_conversion(entry, variable["units"], time_step),
        land_only=variable["land_only"],
    )
    cells, values = [], []
    for dataset in fields.values():
        for field in dataset.values():
            cells.append({"bbox": field["bbox"]})
            buckets = {}
            for stamp, value in field["observations"].items():
                if value is not None and math.isfinite(value):
                    buckets.setdefault(_step_key(stamp, time_step), []).append(value)
            values.append(
                [
                    _step_value(buckets.get(step), request["aggregation"])
                    for step in timestamps
                ]
            )
    frames = [list(frame) for frame in zip(*values)]
    valid = [value for frame in frames for value in frame if value is not None]
    identity = (
        {"area": {"rectangles": rectangles}}
        if rectangles
        else {"region_id": request["region_id"]}
    )
    return {
        **identity,
        "variable_id": variable["variable_id"],
        "aggregation": request["aggregation"],
        "time_step": time_step,
        "period": request["period"],
        "units": units_at(variable["units"], time_step),
        "cells": cells,
        "timestamps": timestamps,
        "frames": frames,
        "minimum": min(valid) if valid else None,
        "maximum": max(valid) if valid else None,
    }
