"""Load named selections and return an exploratory numeric Correlation map."""

import copy
import json
import math
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..data_gathering.selection import SeriesSelectionError, TimeWindow
from ..time_steps import (
    bucket_start,
    next_bucket,
    normalize_time_step,
    series_time_step,
    time_step_label,
    utc_instant,
)
from .arithmetic import process_series
from .errors import ProcessingError
from .resampling import require_coarser_time_step
from .scaling import scale_values
from .validation import validate_series

SeriesLoader = Callable[[dict, dict], Mapping]


def _matrix(series):
    centered, squares = [], []
    for item in series:
        normalized = scale_values(item["values"], "minmax", None)
        mean = math.fsum(normalized) / len(normalized)
        vector = [value - mean for value in normalized]
        centered.append(vector)
        squares.append(math.fsum(value * value for value in vector))
    result = [
        [1.0 if i == j else 0.0 for j in range(len(series))] for i in range(len(series))
    ]
    for i, left in enumerate(centered):
        for j in range(i):
            score = math.fsum(a * b for a, b in zip(left, centered[j])) / math.sqrt(
                squares[i] * squares[j]
            )
            result[i][j] = result[j][i] = max(-1.0, min(1.0, score))
    return result


def analysis_period_bounds(period, zone):
    """Return half-open UTC bounds for inclusive caller-selected dates/instants."""
    if not isinstance(period, Mapping) or not all(
        isinstance(period.get(k), str) for k in ("start", "end")
    ):
        raise ProcessingError("invalid_period", "Choose a common start/end period.")
    try:
        if all(len(period[k]) in (7, 10) for k in ("start", "end")):
            window = TimeWindow.create(period["start"], period["end"])
            lower = (
                datetime.fromisoformat(window.lower)
                .replace(tzinfo=zone)
                .astimezone(UTC)
            )
            upper = (
                datetime.fromisoformat(window.upper)
                .replace(tzinfo=zone)
                .astimezone(UTC)
            )
        else:
            lower = utc_instant(period["start"])
            upper = utc_instant(period["end"]) + timedelta(microseconds=1)
        if lower >= upper:
            raise ValueError
    except (ValueError, OverflowError) as error:
        raise ProcessingError(
            "invalid_period", "Use an ordered ISO start/end period."
        ) from error
    return lower, upper


def _grid(lower, upper, frequency, zone):
    cursor = bucket_start(lower.astimezone(zone), frequency)
    grid = []
    while cursor.astimezone(UTC) < upper:
        grid.append(cursor.astimezone(UTC))
        following = next_bucket(cursor, frequency)
        cursor = following
    return grid


def _complete(item, instants, grid, frequency, zone):
    slots = {}
    for i, stamp in enumerate(instants):
        key = bucket_start(stamp.astimezone(zone), frequency).astimezone(UTC)
        if key in slots:
            raise ProcessingError(
                "invalid_series",
                "More than one observation occupies a declared Time step.",
            )
        slots[key] = i
    missing = [
        stamp.isoformat()
        for stamp in grid
        if stamp not in slots or item["values"][slots[stamp]] is None
    ]
    if missing:
        raise ProcessingError(
            "incomplete_output_timeline",
            "Not enough data for this Variable. Choose another period or Variable.",
            missing_timestamps=missing,
        )
    order = [slots[stamp] for stamp in grid]
    prepared = dict(item)
    prepared["timestamps"] = [item["timestamps"][i] for i in order]
    prepared["values"] = [item["values"][i] for i in order]
    flags = item.get("filled", [False] * len(instants))
    prepared["filled"] = [flags[i] for i in order]
    if min(prepared["values"]) == max(prepared["values"]):
        raise ProcessingError(
            "constant_input",
            "This Variable is constant in the chosen period; Pearson correlation is undefined.",
        )
    return prepared, [instants[i] for i in order]


def build_correlation_map(
    request: Mapping, *, loader: SeriesLoader | None = None
) -> dict:
    """Load Variable-name selections; return numbers or a structured ProcessingError."""
    try:
        return _build(request, loader)
    except MemoryError:
        raise ProcessingError(
            "resource_exhausted",
            "Not enough resources. Reduce the number of inputs and try again.",
        ) from None


def _label(selection, series=None):
    series = series or {}
    area = selection["area"]
    if isinstance(area, Mapping):
        area = area.get("name", area.get("id", "Selected area"))
    area = selection.get("area_label", series.get("area_name", area))
    variable = series.get("variable_name", selection["variable"])
    return selection.get("label", f"{variable} — {area}")


def _exclusion(selection, error):
    details = copy.deepcopy(getattr(error, "details", {}))
    quality = getattr(error, "quality", None)
    if quality is not None and is_dataclass(quality) and not isinstance(quality, type):
        details["quality"] = asdict(quality)
    return {
        **selection,
        "label": _label(selection),
        "code": error.code,
        "message": str(error),
        "details": details,
    }


def _check_quality(series):
    quality = series.get("quality")
    if isinstance(quality, Mapping) and quality.get("included") is False:
        raise ProcessingError(
            "excluded_series",
            "This Variable failed the source Quality gate.",
            quality=dict(quality),
        )
    provenance = series.get("provenance")
    if isinstance(provenance, Mapping):
        for parent in provenance.values():
            if isinstance(parent, Mapping):
                _check_quality(parent)


def _selections(request):
    if len(request["variables"]) < 2:
        raise ProcessingError(
            "insufficient_inputs", "Choose at least two Variable selections."
        )
    seen, ids = set(), set()
    selections, warnings = [], []
    allowed = {
        "variable",
        "area",
        "id",
        "label",
        "area_label",
        "dataset_id",
        "source_time_step",
        "aggregation",
    }
    for index, value in enumerate(request["variables"]):
        if not isinstance(value, (str, Mapping)):
            raise ProcessingError(
                "invalid_request",
                "Each input identifies a Variable name and area, not series values.",
            )
        item = {"variable": value} if isinstance(value, str) else dict(value)
        if set(item) - allowed:
            raise ProcessingError(
                "invalid_request",
                "Unsupported selection fields; send Variable names and area identifiers, not series values.",
            )
        item.setdefault("area", request.get("area"))
        item.setdefault("id", f"input_{index}")
        if (
            not isinstance(item.get("variable"), str)
            or not item["variable"].strip()
            or not isinstance(item["area"], (str, Mapping))
            or not item["area"]
            or not isinstance(item["id"], str)
            or not item["id"].strip()
            or any(
                key in item
                and (not isinstance(item[key], str) or not item[key].strip())
                for key in (
                    "label",
                    "area_label",
                    "dataset_id",
                    "source_time_step",
                    "aggregation",
                )
            )
        ):
            raise ProcessingError(
                "invalid_request",
                "Provide nonempty Variable/area identifiers and input labels.",
            )
        try:
            identity = json.dumps(
                {
                    key: value
                    for key, value in item.items()
                    if key not in ("id", "label", "area_label")
                },
                sort_keys=True,
                allow_nan=False,
            )
        except (ValueError, TypeError):
            raise ProcessingError(
                "invalid_request", "Area selections must be JSON-compatible."
            ) from None
        if identity in seen:
            warnings.append(
                {
                    "code": "duplicate_selection",
                    "input": item["id"],
                    "message": "The exact same input was selected twice; its duplicate was omitted.",
                }
            )
            continue
        if item["id"] in ids:
            raise ProcessingError(
                "duplicate_input_id", "Use a distinct ID for each different input."
            )
        seen.add(identity)
        ids.add(item["id"])
        selections.append(item)
    return selections, warnings


def _build(request, loader):
    if loader is None:
        from .correlation_source import SeedSeriesLoader

        loader = SeedSeriesLoader()
    if not isinstance(request, Mapping) or not isinstance(
        request.get("variables"), list
    ):
        raise ProcessingError(
            "invalid_request",
            "Provide a list of Variable-name selections, not series values.",
        )
    if set(request) - {"variables", "area", "period", "time_step", "timezone"}:
        raise ProcessingError(
            "invalid_request", "Unsupported correlation-map request fields."
        )
    selections, warnings = _selections(request)
    try:
        zone = ZoneInfo(request.get("timezone", "UTC"))
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise ProcessingError(
            "invalid_timezone", "Choose an IANA time zone such as UTC."
        ) from None
    period = request.get("period")
    if not isinstance(period, Mapping):
        raise ProcessingError("invalid_period", "Choose a common start/end period.")
    lower, upper = analysis_period_bounds(period, zone)
    candidates, excluded = [], []
    for selection in selections:
        try:
            raw = loader(copy.deepcopy(selection), dict(period))
            if not isinstance(raw, Mapping):
                raise ProcessingError(
                    "invalid_series", "The data source did not return a Series."
                )
            item = copy.deepcopy(dict(raw))
            _check_quality(item)
            instants = validate_series(item, selection["id"])
            if not all(isinstance(stamp, datetime) for stamp in instants):
                raise ProcessingError(
                    "unsupported_calendar",
                    "Correlation currently requires Gregorian timestamps.",
                )
            try:
                frequency = series_time_step(item)
            except ValueError as error:
                raise ProcessingError("invalid_time_step", str(error)) from None
            if frequency is None:
                raise ProcessingError(
                    "unknown_time_step", "The loaded series must declare its Time step."
                )
            order = [i for i, stamp in enumerate(instants) if lower <= stamp < upper]
            if not order:
                raise ProcessingError(
                    "incomplete_output_timeline",
                    "No data covers this period. Choose another period or Variable.",
                )
            item["timestamps"] = [item["timestamps"][i] for i in order]
            item["values"] = [item["values"][i] for i in order]
            flags = item.get("filled", [False] * len(instants))
            item["filled"] = [flags[i] for i in order]
            candidates.append(
                (selection, item, [instants[i] for i in order], frequency)
            )
        except (ProcessingError, SeriesSelectionError) as error:
            excluded.append(_exclusion(selection, error))
    if not candidates:
        raise ProcessingError(
            "insufficient_inputs",
            "Choose at least two usable inputs.",
            excluded=excluded,
            warnings=warnings,
        )
    frequencies = {candidate[3] for candidate in candidates}
    requested = request.get("time_step")
    if requested is not None:
        try:
            target = normalize_time_step(requested)
        except ValueError as error:
            raise ProcessingError("invalid_time_step", str(error)) from None
    elif len(frequencies) == 1:
        target = next(iter(frequencies))
    else:
        raise ProcessingError(
            "resampling_required",
            "Choose an explicit common Time step or change the selected inputs.",
        )
    if zone.key != "UTC" and any(
        "time_step" in candidate[1] for candidate in candidates
    ):
        raise ProcessingError(
            "invalid_timezone", "Explore My World Time steps follow UTC."
        )
    for _, _, _, frequency in candidates:
        require_coarser_time_step(frequency, target)
    grid = _grid(lower, upper, target, zone)
    if len(grid) < 2:
        raise ProcessingError(
            "insufficient_observations",
            "Choose a period containing at least two observations.",
            excluded=excluded,
        )
    selections, loaded, timelines = [], [], []
    for selection, item, instants, frequency in candidates:
        try:
            if frequency != target:
                step = {
                    "id": "resampled",
                    "operation": "resample",
                    "input": "source",
                    "source_frequency": frequency,
                    "frequency": target,
                    "timezone": zone.key,
                }
                if "aggregation" in selection:
                    step["aggregation"] = selection["aggregation"]
                response = process_series(
                    {"series": {"source": item}, "operations": [step]}
                )
                item = response["series"]["resampled"]
                instants = validate_series(item, selection["id"])
                warnings.extend(
                    {"input": selection["id"], **warning}
                    for warning in response["warnings"]
                )
            prepared, exact = _complete(item, instants, grid, target, zone)
            descriptor = {**selection, "label": _label(selection, prepared)}
            descriptor["metadata"] = {
                key: copy.deepcopy(value)
                for key, value in prepared.items()
                if key not in ("values", "timestamps", "filled")
            }
            descriptor["filled_count"] = sum(prepared["filled"])
            selections.append(descriptor)
            loaded.append(prepared)
            timelines.append(exact)
        except ProcessingError as error:
            if error.code in {
                "upsampling_not_supported",
                "aggregation_mismatch",
                "invalid_resampling_parameters",
                "source_frequency_mismatch",
                "invalid_timezone",
            }:
                raise ProcessingError(
                    error.code, str(error), input=selection["id"], **error.details
                ) from None
            excluded.append(_exclusion(selection, error))
    if len(loaded) < 2:
        raise ProcessingError(
            "insufficient_inputs",
            "Choose at least two usable inputs.",
            excluded=excluded,
            warnings=warnings,
        )
    if any(timeline != timelines[0] for timeline in timelines[1:]):
        raise ProcessingError(
            "unaligned_series",
            "Timestamps differ; explicitly resample or change the selection.",
        )
    if len(grid) == 2:
        warnings.append(
            {
                "code": "two_observations",
                "message": "Only two observations were used; Pearson is necessarily +1 or -1.",
            }
        )
    labels = Counter(item["label"] for item in selections)
    used_labels = set()
    for item in selections:
        label = item["label"]
        if labels[label] > 1:
            dataset = item.get("dataset_id", item["metadata"].get("dataset_id"))
            label += f" ({dataset or item['id']})"
        while label in used_labels:
            label += f" [{item['id']}]"
        item["label"] = label
        used_labels.add(label)
    filled_pairs = [
        [
            sum(a or b for a, b in zip(left["filled"], right["filled"]))
            for right in loaded
        ]
        for left in loaded
    ]
    return {
        "inputs": selections,
        "matrix": _matrix(loaded),
        "filled_pair_counts": filled_pairs,
        "timestamps": [stamp.isoformat() for stamp in timelines[0]],
        "observation_count": len(grid),
        "settings": {
            "period": dict(period),
            "time_step": time_step_label(target),
            "timezone": zone.key,
        },
        "excluded": excluded,
        "warnings": warnings,
    }
