"""Resolve acquired results and named processing instructions for a map request.

No acquisition, engine computation or HTTP concerns live here. The application
supplies its acquired-result inventory, including cached submonthly results.
"""

import copy
from collections.abc import Mapping, Sequence
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..data_gathering.models import Period
from ..data_gathering.quality_gate import months_in
from ..time_steps import normalize_time_step, series_time_step
from .arithmetic import process_series
from .correlation_map import analysis_period_bounds, build_correlation_map
from .errors import ProcessingError
from .validation import validate_series


def _matches(entry, key, name):
    return isinstance(name, str) and name.strip().casefold() in (
        str(entry.get(key, "")).casefold(),
        str(entry.get("name", "")).casefold(),
    )


def _rectangle(value):
    if not isinstance(value, Mapping) or set(value) != {
        "west",
        "east",
        "south",
        "north",
    }:
        raise ProcessingError(
            "invalid_area", "Provide west, east, south and north for each rectangle."
        )
    from .validation import finite_number

    if not all(finite_number(x) for x in value.values()) or not (
        -180 <= value["west"] <= 180
        and -180 <= value["east"] <= 180
        and -90 <= value["south"] < value["north"] <= 90
        and value["west"] != value["east"]
    ):
        raise ProcessingError(
            "invalid_area",
            "Use distinct longitudes within ±180 and ordered latitudes within ±90.",
        )
    return dict(value)


class AcquiredSeriesLoader:
    """Load exact acquired identities, never a nearest area or example fallback."""

    def __init__(self, series: Sequence[Mapping], catalog: Mapping):
        self.series = series
        self.catalog = catalog

    def __call__(self, selection: dict, period: dict) -> dict:
        area = selection["area"]
        rectangles = None
        if isinstance(area, Mapping):
            raw = area.get("rectangles", [area["bbox"]] if "bbox" in area else None)
            if not isinstance(raw, list) or not raw:
                raise ProcessingError("invalid_area", "Choose one or more rectangles.")
            rectangles = [_rectangle(box) for box in raw]
        region = next(
            (
                entry
                for entry in self.catalog["regions"]
                if (
                    _matches(entry, "region_id", area)
                    if rectangles is None
                    else len(rectangles) == 1 and entry["bbox"] == rectangles[0]
                )
            ),
            None,
        )
        variable = next(
            (
                entry
                for entry in self.catalog["variables"]
                if _matches(entry, "variable_id", selection["variable"])
            ),
            None,
        )
        if variable is None:
            raise ProcessingError(
                "variable_unavailable",
                "This Variable is unavailable; choose another Variable.",
            )
        if region is not None and variable["variable_id"] not in region["variable_ids"]:
            raise ProcessingError(
                "variable_unavailable",
                "This Variable does not apply to the selected area.",
            )
        candidates = []
        for item in self.series:
            same_area = (
                item.get("region_id") == region["region_id"]
                if region
                else (
                    rectangles is not None
                    and item.get("area", {}).get("rectangles") == rectangles
                )
            )
            if not same_area or item.get("variable_id") != variable["variable_id"]:
                continue
            dataset = selection.get("dataset_id")
            if dataset and dataset not in (
                item.get("dataset_id"),
                item.get("source", {}).get("dataset"),
            ):
                continue
            try:
                step = series_time_step(item) or "month"
                if (
                    "source_time_step" in selection
                    and normalize_time_step(selection["source_time_step"]) != step
                ):
                    continue
            except ValueError as error:
                raise ProcessingError("invalid_time_step", str(error)) from None
            candidates.append((item, step))
        if not candidates:
            raise ProcessingError(
                "source_unavailable" if region else "area_unavailable",
                "No acquired data covers this selection. Choose another area, period or Variable; the area was not changed.",
            )

        # Covering inventories precede incomplete ones; never stitch, fill, or
        # substitute observations from a different identity or native Time step.
        def covers(candidate):
            interval = candidate[0].get("period", {})
            return (
                interval.get("start", "9999")[:7] <= period["start"][:7]
                and interval.get("end", "0000")[:7] >= period["end"][:7]
            )

        covered = [candidate for candidate in candidates if covers(candidate)]
        candidates = covered or candidates
        if len({step for _, step in candidates}) > 1:
            raise ProcessingError(
                "source_time_step_required",
                "Choose a source Time step for this Variable.",
            )
        item, step = candidates[0]
        result = copy.deepcopy(dict(item))
        if "timestamps" not in result and step == "month":
            try:
                result["timestamps"] = [
                    month + "-01" for month in months_in(Period(**result["period"]))
                ]
            except (TypeError, ValueError, KeyError):
                raise ProcessingError(
                    "invalid_series", "The acquired timeline is invalid."
                ) from None
        if "time_step" not in result and "frequency" not in result:
            result["time_step"] = "monthly"
        result.setdefault("aggregation", "mean")
        if "aggregation" in selection:
            from .resampling import normalize_aggregation

            try:
                chosen = normalize_aggregation(selection["aggregation"])
                own = normalize_aggregation(result["aggregation"])
            except ValueError as error:
                raise ProcessingError("invalid_aggregation", str(error)) from None
            if chosen != own:
                raise ProcessingError(
                    "aggregation_mismatch",
                    "Choose this Series' own Aggregation; it cannot be changed implicitly.",
                )
        result["variable_name"] = variable["name"]
        result["area_name"] = (
            area.get("name", "Selected area")
            if isinstance(area, Mapping)
            else region["name"]
            if region is not None
            else "Selected area"
        )
        return result


class PreparedSeriesLoader:
    """Resolve named Derived instructions against acquired identifiers, not arrays."""

    def __init__(self, source, definitions, timezone="UTC"):
        try:
            self.zone = ZoneInfo(timezone)
        except (TypeError, ValueError, ZoneInfoNotFoundError):
            raise ProcessingError(
                "invalid_timezone", "Choose an IANA time zone such as UTC."
            ) from None
        self.source = source
        self.definitions: dict[str, Mapping] = {}
        if not isinstance(definitions, list):
            raise ProcessingError(
                "invalid_derived", "Provide a list of prepared calculations."
            )
        for item in definitions:
            if (
                not isinstance(item, Mapping)
                or set(item) - {"id", "inputs", "operations", "output"}
                or not all(
                    key in item for key in ("id", "inputs", "operations", "output")
                )
            ):
                raise ProcessingError(
                    "invalid_derived",
                    "Provide a name, input identifiers, operations and output for each calculation.",
                )
            name = item["id"]
            if not isinstance(name, str) or not name or name in self.definitions:
                raise ProcessingError(
                    "invalid_derived",
                    "Prepared calculation names must be distinct and nonempty.",
                )
            if not isinstance(item["inputs"], Mapping) or not isinstance(
                item["output"], str
            ):
                raise ProcessingError(
                    "invalid_derived",
                    "Prepared inputs must identify acquired selections and a named output.",
                )
            self.definitions[name] = item
        self.active: set[str] = set()

    def __call__(self, selection, period):
        if selection["area"] != "derived":
            return self.source(selection, period)
        name = selection["variable"]
        if name not in self.definitions or name in self.active:
            raise ProcessingError(
                "invalid_derived",
                "This calculation is unavailable or refers to itself.",
            )
        item = self.definitions[name]
        self.active.add(name)
        try:
            inputs = {}
            for key, value in item["inputs"].items():
                if (
                    not isinstance(value, Mapping)
                    or "variable" not in value
                    or "area" not in value
                    or set(value)
                    - {
                        "variable",
                        "area",
                        "id",
                        "label",
                        "area_label",
                        "dataset_id",
                        "source_time_step",
                        "aggregation",
                    }
                ):
                    raise ProcessingError(
                        "invalid_derived",
                        "Calculation inputs must be Variable/area identifiers, not data values.",
                    )
                loaded = self(dict(value), period)
                instants = validate_series(loaded, key)
                lower, upper = analysis_period_bounds(period, self.zone)
                if not all(isinstance(stamp, datetime) for stamp in instants):
                    raise ProcessingError(
                        "unsupported_calendar",
                        "Correlation requires Gregorian timestamps.",
                    )
                order = [
                    i for i, stamp in enumerate(instants) if lower <= stamp < upper
                ]
                cropped = copy.deepcopy(loaded)
                for field in ("timestamps", "values", "filled"):
                    if field in cropped:
                        cropped[field] = [loaded[field][i] for i in order]
                cropped["period"] = dict(period)
                inputs[key] = cropped
            response = process_series(
                {"series": inputs, "operations": item["operations"]}
            )
            if item["output"] not in response["series"]:
                raise ProcessingError(
                    "invalid_derived",
                    "The requested calculation output does not exist.",
                )
            return response["series"][item["output"]]
        finally:
            self.active.remove(name)


def correlate_acquired_series(
    request: Mapping, *, series: Sequence[Mapping], catalog: Mapping
) -> dict:
    """Application boundary: select acquired inputs and replay named calculations."""
    if not isinstance(request, Mapping):
        raise ProcessingError("invalid_request", "Provide a correlation-map request.")
    parameters = dict(request)
    definitions = parameters.pop("derived", [])
    loader = PreparedSeriesLoader(
        AcquiredSeriesLoader(series, catalog),
        definitions,
        parameters.get("timezone", "UTC"),
    )
    return build_correlation_map(parameters, loader=loader)
