"""Extract numeric native-frequency time series using NetCDF/CF metadata.

No product ids, Variable lists, dates, units, or geographic bounds are baked in.
Additional dimensions become separate series. Unsupported fields are reported.
"""

from __future__ import annotations

import json
import math
import re
from itertools import product
from pathlib import Path

import numpy as np
from netCDF4 import Dataset, num2date


def load_manifest(path: Path) -> dict:
    """Resolve source files relative to the manifest, not the working directory."""
    path = Path(path).resolve()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for record in manifest["files"]:
        source = Path(record["file"])
        record["file"] = str(source if source.is_absolute() else path.parent / source)
    return manifest


def inherited_variables(group):
    variables = inherited_variables(group.parent) if group.parent is not None else {}
    return {**variables, **group.variables}


def groups(group, prefix=""):
    yield prefix, group
    for name, child in group.groups.items():
        yield from groups(child, f"{prefix}{name}/")


def coordinate(variables, kind, explicit=None):
    if explicit:
        if explicit not in variables:
            raise ValueError(f"Coordinate {explicit!r} does not exist.")
        return explicit, variables[explicit]
    aliases = {
        "time": ("time", "date", "datetime"),
        "latitude": ("lat", "latitude"),
        "longitude": ("lon", "longitude"),
    }
    for name, variable in variables.items():
        if getattr(variable, "standard_name", "").lower() == kind:
            return name, variable
    for name, variable in variables.items():
        units = getattr(variable, "units", "").lower()
        if (
            (kind == "time" and " since " in units)
            or (
                kind == "latitude"
                and units in ("degrees_north", "degree_north", "degrees_n")
            )
            or (
                kind == "longitude"
                and units in ("degrees_east", "degree_east", "degrees_e")
            )
        ):
            return name, variable
    for name, variable in variables.items():
        if name.lower() in aliases[kind]:
            return name, variable
    return None, None


def widths(variable, variables, latitude=False):
    values = np.asarray(variable[:], dtype=float)
    bounds_name = getattr(variable, "bounds", "")
    if bounds_name in variables:
        bounds = np.asarray(variables[bounds_name][:], dtype=float)
        if bounds.shape != (values.size, 2):
            raise ValueError("Coordinate bounds must have shape (cells, 2).")
        low, high = bounds.min(axis=1), bounds.max(axis=1)
    elif values.size > 1:
        delta = np.diff(values)
        if not (np.all(delta > 0) or np.all(delta < 0)):
            raise ValueError(
                "Coordinates need monotonic centres or explicit cell bounds."
            )
        edges = np.r_[
            values[0] - delta[0] / 2,
            (values[:-1] + values[1:]) / 2,
            values[-1] + delta[-1] / 2,
        ]
        low, high = np.minimum(edges[:-1], edges[1:]), np.maximum(edges[:-1], edges[1:])
    else:
        raise ValueError(
            "A one-cell coordinate requires explicit cell bounds for area weighting; use --aggregation mean."
        )
    if latitude:
        low, high = np.clip(low, -90, 90), np.clip(high, -90, 90)
        return np.abs(np.sin(np.deg2rad(high)) - np.sin(np.deg2rad(low)))
    return np.deg2rad(np.abs(high - low))


def geography(
    variables, area, aggregation, latitude=None, longitude=None, area_variable=None
):
    if not area_variable:
        named_areas = {
            match.group(1)
            for variable in variables.values()
            if (
                match := re.search(
                    r"\barea:\s*(\S+)", getattr(variable, "cell_measures", "")
                )
            )
        }
        area_variable = next(iter(named_areas)) if len(named_areas) == 1 else None
    lat_name, lat = coordinate(variables, "latitude", latitude)
    lon_name, lon = coordinate(variables, "longitude", longitude)
    if lat is None and lon is None:
        return None
    if lat is None or lon is None:
        raise ValueError(
            "Both latitude and longitude coordinates are required to select a box."
        )
    boxes = _split_at_antimeridian(getattr(area, "boxes", ()) or (area.bbox,))
    lat_values = np.asarray(lat[:], dtype=float)
    lon_values = (np.asarray(lon[:], dtype=float) + 180) % 360 - 180

    def centres_in(lat_part, lon_part):
        # A cell belongs to the area when its centre lies in any of the boxes.
        return np.any(
            [
                (lat_part >= south)
                & (lat_part <= north)
                & (lon_part >= west)
                & (lon_part <= east)
                for west, south, east, north in boxes
            ],
            axis=0,
        )

    if lat.ndim == lon.ndim == 1 and lat.dimensions != lon.dimensions:
        inside = centres_in(lat_values[:, None], lon_values[None, :])
        rows = np.flatnonzero(inside.any(axis=1))
        cols = np.flatnonzero(inside.any(axis=0))
        if not rows.size or not cols.size:
            raise ValueError("No grid-cell centres lie inside the configured box.")
        inside = inside[np.ix_(rows, cols)]
        # One box selects whole rows and columns; joined boxes may not.
        inside = None if inside.all() else inside
        dims = (lat.dimensions[0], lon.dimensions[0])
        weights = np.ones((rows.size, cols.size))
        if aggregation == "area-mean":
            if area_variable:
                if area_variable not in variables:
                    raise ValueError(
                        f"Cell-area variable {area_variable!r} is missing."
                    )
                source = variables[area_variable]
                raw = np.asarray(source[:], dtype=float)
                if source.dimensions == dims[::-1]:
                    raw = raw.T
                elif source.dimensions != dims:
                    raise ValueError(
                        "Cell-area axes must match latitude/longitude axes."
                    )
                weights = raw[np.ix_(rows, cols)]
                if not np.all(np.isfinite(weights) & (weights > 0)):
                    raise ValueError("Selected cell areas must be finite and positive.")
            else:
                weights = (
                    widths(lat, variables, True)[rows, None]
                    * widths(lon, variables)[None, cols]
                )
        return {
            "dims": dims,
            "indices": {dims[0]: rows, dims[1]: cols},
            "weights": weights,
            "coords": {dims[0]: lat_values, dims[1]: lon_values},
            "names": {lat_name, lon_name},
            "inside": inside,
        }
    if lat.dimensions != lon.dimensions or lat_values.shape != lon_values.shape:
        raise ValueError("Latitude and longitude must describe the same cells.")
    inside = centres_in(lat_values, lon_values)
    if not inside.any():
        raise ValueError("No coordinate points lie inside the configured box.")
    weights = np.ones(lat_values.shape)
    if aggregation == "area-mean":
        if not area_variable or area_variable not in variables:
            raise ValueError(
                "Curvilinear/point grids need --area-variable for area weighting; use --aggregation mean otherwise."
            )
        weights = np.asarray(variables[area_variable][:], dtype=float)
        if weights.shape != inside.shape or not np.all(
            np.isfinite(weights) & (weights > 0)
        ):
            raise ValueError(
                "Cell areas must match the grid and be finite and positive."
            )
    if aggregation == "none" and lat.ndim != 1:
        raise ValueError(
            "Per-cell extraction on curvilinear grids is not supported; choose mean/area-mean."
        )
    indices = {
        dim: np.arange(size) for dim, size in zip(lat.dimensions, lat_values.shape)
    }
    if lat.ndim == 1:
        indices[lat.dimensions[0]] = np.flatnonzero(inside)
        weights = weights[inside]
        inside = None
    return {
        "dims": lat.dimensions,
        "indices": indices,
        "weights": weights,
        "coords": {},
        "names": {lat_name, lon_name},
        "inside": inside,
    }


def _split_at_antimeridian(boxes):
    """(west, south, east, north) boxes, each crossing box cut in two at 180°."""
    result = []
    for west, south, east, north in boxes:
        if west > east:
            result += [(west, south, 180.0, north), (-180.0, south, east, north)]
        else:
            result.append((west, south, east, north))
    return result


def extract(
    records: list[dict],
    area,
    *,
    aggregation="area-mean",
    variables=None,
    time_coordinate=None,
    latitude=None,
    longitude=None,
    area_variable=None,
    max_series=10000,
    time_window=None,
    land_mask_provider=None,
    verbose=True,
) -> dict:
    """Series for one area. See `extract_many`, which reads each file once for many."""
    result = extract_many(
        records,
        {"": area},
        aggregation=aggregation,
        variables=variables,
        time_coordinate=time_coordinate,
        latitude=latitude,
        longitude=longitude,
        area_variable=area_variable,
        max_series=max_series,
        time_window=time_window,
        land_mask_provider=land_mask_provider,
        on_file=(lambda done, total, path: print(f"Read {path.name}", flush=True))
        if verbose
        else None,
    )[""]
    if isinstance(result, Exception):
        raise result
    return result


def extract_many(
    records: list[dict],
    areas: dict,
    *,
    aggregation="area-mean",
    variables=None,
    time_coordinate=None,
    latitude=None,
    longitude=None,
    area_variable=None,
    max_series=10000,
    time_window=None,
    land_mask_provider=None,
    on_file=None,
) -> dict:
    """Series for several named areas, opening each file once.

    Each area gets the result `extract` would give it alone, or, when `extract`
    would have raised for it (a conflict, a limit, a land mask that cannot be
    aligned, nothing readable), that exception as its value; the other areas are
    unaffected. `on_file(done, total, path)` is called after each file.
    """
    outputs = {
        name: {
            "bbox": list(area.bbox),
            "aggregation": aggregation,
            "datasets": {},
            "skipped": [],
        }
        for name, area in areas.items()
    }
    totals = dict.fromkeys(areas, 0)
    failures: dict[str, Exception] = {}
    for position, record in enumerate(records, 1):
        path = Path(record["file"])
        label = record.get("dataset") or "data"
        try:
            dataset = Dataset(path)
        except OSError as error:
            for output in outputs.values():
                output["skipped"].append(
                    {
                        "file": str(path),
                        "reason": f"Not a readable NetCDF/CF file: {error}",
                    }
                )
            continue
        with dataset:
            for prefix, group in groups(dataset):
                available = inherited_variables(group)
                try:
                    time_name, time = coordinate(available, "time", time_coordinate)
                    if time is None or time.ndim != 1:
                        raise ValueError(
                            "A one-dimensional time coordinate is required."
                        )
                    time.set_auto_mask(False)
                    calendar = getattr(time, "calendar", "standard")
                    if " since " not in getattr(time, "units", ""):
                        raise ValueError(
                            "Time coordinate needs CF '<unit> since <date>' units."
                        )
                    dates = num2date(time[:], time.units, calendar)
                    timestamps = [date.isoformat() for date in dates]
                    if len(timestamps) != len(set(timestamps)):
                        raise ValueError("Duplicate timestamps in one time coordinate.")
                except ValueError as error:
                    for name, output in outputs.items():
                        if name not in failures:
                            output["skipped"].append(
                                {
                                    "file": str(path),
                                    "group": prefix,
                                    "reason": str(error),
                                }
                            )
                    continue
                for name, area in areas.items():
                    if name in failures:
                        continue
                    output = outputs[name]
                    try:
                        geo = geography(
                            available,
                            area,
                            aggregation,
                            latitude,
                            longitude,
                            area_variable,
                        )
                    except ValueError as error:
                        output["skipped"].append(
                            {"file": str(path), "group": prefix, "reason": str(error)}
                        )
                        continue
                    excluded = {time_name}
                    if geo:
                        excluded |= geo["names"]
                    excluded |= {getattr(v, "bounds", "") for v in available.values()}
                    for var_name, variable in group.variables.items():
                        full_name = prefix + var_name
                        if (
                            variables
                            and var_name not in variables
                            and full_name not in variables
                        ):
                            continue
                        if var_name in excluded or var_name in variable.dimensions:
                            continue
                        if (
                            np.dtype(variable.dtype).kind not in "iuf"
                            or time.dimensions[0] not in variable.dimensions
                        ):
                            continue
                        try:
                            totals[name] = _read_field(
                                output,
                                totals[name],
                                record,
                                available,
                                geo,
                                variable,
                                full_name,
                                var_name,
                                time,
                                calendar,
                                timestamps,
                                aggregation,
                                max_series,
                                time_window,
                                land_mask_provider,
                                label,
                            )
                        except (ValueError, TypeError) as error:
                            # Conflicts and resource limits must never silently yield partial series.
                            if (
                                hasattr(error, "code")
                                or "Duplicate/overlapping" in str(error)
                                or "Series limit" in str(error)
                                or "changed between files" in str(error)
                            ):
                                failures[name] = error
                                break
                            output["skipped"].append(
                                {
                                    "file": str(path),
                                    "variable": full_name,
                                    "reason": str(error),
                                }
                            )
        if on_file is not None:
            on_file(position, len(records), path)
    results = {}
    for name, output in outputs.items():
        if name in failures:
            results[name] = failures[name]
        elif not any(output["datasets"].values()):
            reasons = "; ".join(sorted({item["reason"] for item in output["skipped"]}))
            results[name] = ValueError(f"No readable numeric time series. {reasons}")
        else:
            results[name] = output
    return results


def _read_field(
    output,
    total,
    record,
    available,
    geo,
    variable,
    full_name,
    name,
    time,
    calendar,
    timestamps,
    aggregation,
    max_series,
    time_window,
    land_mask_provider,
    label,
):
    """Add one field of one file to one area's output; returns the area's series count."""
    spatial = tuple(
        dim for dim in (geo["dims"] if geo else ()) if dim in variable.dimensions
    )
    if spatial and len(spatial) != len(geo["dims"]):
        raise ValueError("Field contains only part of the geographic coordinate axes.")
    land = land_mask_provider(record, available, geo) if land_mask_provider else None
    if land is not None and not spatial:
        raise ValueError("A land-only field requires geographic axes.")
    remaining = [
        dim
        for dim in variable.dimensions
        if dim != time.dimensions[0] and (aggregation == "none" or dim not in spatial)
    ]
    choices = []
    for dim in remaining:
        choices.append(
            geo["indices"][dim]
            if geo and dim in geo["indices"]
            else range(variable.shape[variable.dimensions.index(dim)])
        )
    fields = output["datasets"].setdefault(label, {})
    if math.prod(len(choice) for choice in choices) > max_series:
        raise ValueError(
            f"Series limit {max_series} exceeded; select --variables or increase --max-series."
        )
    for indices in product(*choices):
        selection = dict(zip(remaining, indices))
        coordinates = {}
        coordinate_units = {}
        for dim, index in selection.items():
            coord = available.get(dim)
            value = (
                geo["coords"][dim][index]
                if geo and dim in geo["coords"]
                else (
                    coord[index]
                    if coord is not None and coord.ndim == 1
                    else int(index)
                )
            )
            if hasattr(value, "item"):
                value = value.item()
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            coordinates[dim] = str(value)
            coordinate_units[dim] = getattr(coord, "units", "unknown")
        suffix = ",".join(f"{key}={value}" for key, value in coordinates.items())
        key = full_name + (f"[{suffix}]" if suffix else "")
        if key not in fields:
            if total >= max_series:
                raise ValueError(
                    f"Series limit {max_series} exceeded; select --variables or increase --max-series."
                )
            total += 1
            fields[key] = {
                "variable": full_name,
                "description": getattr(
                    variable, "long_name", getattr(variable, "standard_name", name)
                ).replace("_", " "),
                "units": getattr(variable, "units", "unknown"),
                "calendar": calendar,
                "coordinates": coordinates,
                "coordinate_units": coordinate_units,
                "spatial_aggregation": aggregation if spatial else "none",
                "observations": {},
            }
        if land is not None:
            inside = geo["inside"]
            fraction = float(np.mean(land if inside is None else land[inside]))
            previous = fields[key].get("valid_land_fraction")
            if previous is not None and not np.isclose(previous, fraction):
                raise ValueError("Land-mask coverage changed between files.")
            fields[key]["valid_land_fraction"] = fraction
        field = fields[key]
        if (
            field["units"] != getattr(variable, "units", "unknown")
            or field["calendar"] != calendar
        ):
            raise ValueError(f"Units or calendar changed between files for {key}.")
        for time_index, timestamp in enumerate(timestamps):
            if time_window is not None and not (
                time_window[0] <= timestamp < time_window[1]
            ):
                continue
            selectors = []
            for dim in variable.dimensions:
                if dim == time.dimensions[0]:
                    selectors.append(time_index)
                elif dim in selection:
                    selectors.append(selection[dim])
                else:
                    selectors.append(geo["indices"][dim])
            raw = variable[tuple(selectors)]
            numeric = np.asarray(np.ma.getdata(raw), dtype=float)
            values = np.ma.array(
                numeric, mask=np.ma.getmaskarray(raw) | ~np.isfinite(numeric)
            )
            if aggregation != "none" and spatial:
                axes = [
                    geo["dims"].index(dim)
                    for dim in variable.dimensions
                    if dim in spatial
                ]
                weights = np.transpose(geo["weights"], axes)
                if geo["inside"] is not None:
                    inside = np.transpose(geo["inside"], axes)
                    values = np.ma.masked_where(~inside, values)
                if land is not None:
                    values = np.ma.masked_where(~np.transpose(land, axes), values)
                reduced = np.ma.average(values, weights=weights)
            else:
                reduced = values.item() if not np.ma.is_masked(values) else np.ma.masked
            value = (
                None
                if np.ma.is_masked(reduced) or not np.isfinite(reduced)
                else float(reduced)
            )
            if timestamp in field["observations"]:
                raise ValueError(
                    f"Duplicate/overlapping timestamp {timestamp} for {key}; mosaic tiles before extraction."
                )
            field["observations"][timestamp] = value
    return total
