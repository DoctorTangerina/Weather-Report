"""Explicit calendar-bucket aggregation of a single validated series."""

import math
import statistics
from collections import defaultdict
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..time_steps import bucket_start as _floor
from ..time_steps import next_bucket as _next
from ..time_steps import normalize_time_step, series_time_step, time_step_label
from .errors import ProcessingError

_AGGREGATIONS = {
    "mean": "mean",
    "average": "mean",
    "avg": "mean",
    "sum": "sum",
    "min": "min",
    "minimum": "min",
    "max": "max",
    "maximum": "max",
    "median": "median",
    "root mean square": "rms",
    "root_mean_square": "rms",
    "rms": "rms",
    "standard deviation": "std",
    "standard_deviation": "std",
    "std": "std",
    "mean absolute value": "mav",
    "mean_absolute_value": "mav",
    "mean_absolute": "mav",
    "mav": "mav",
}


def normalize_aggregation(value):
    """Return the public canonical aggregation name, without changing semantics."""
    result = _AGGREGATIONS.get(value) if isinstance(value, str) else None
    if result is None:
        raise ValueError("Choose a supported Aggregation.")
    return result


_ORDER = {
    name: index
    for index, name in enumerate(
        ("second", "minute", "hour", "3-hour", "day", "month", "year")
    )
}


def require_coarser_time_step(source, target):
    """Reject upsampling before callers allocate the target timeline."""
    if _ORDER[target] < _ORDER[source]:
        raise ProcessingError(
            "upsampling_not_supported", "Choose the same or a coarser frequency."
        )


def _aggregate(values, aggregation, timestamp):
    if not values:
        return None
    try:
        if aggregation == "mean":
            value = statistics.mean(values)
        elif aggregation == "sum":
            value = math.fsum(values)
        elif aggregation == "min":
            value = min(values)
        elif aggregation == "max":
            value = max(values)
        elif aggregation == "rms":
            magnitude = max(abs(value) for value in values)
            value = (
                magnitude
                * math.sqrt(
                    statistics.mean((value / magnitude) ** 2 for value in values)
                )
                if magnitude
                else 0.0
            )
        elif aggregation == "std":
            value = statistics.pstdev(values)
        elif aggregation == "mav":
            value = statistics.mean(abs(value) for value in values)
        else:
            value = statistics.median(values)
            if not math.isfinite(value):
                ordered = sorted(values)
                middle = len(ordered) // 2
                value = ordered[middle - 1] / 2 + ordered[middle] / 2
        if not math.isfinite(value):
            raise OverflowError
        return float(value)
    except OverflowError:
        raise ProcessingError(
            "nonfinite_result",
            "Aggregation produced a nonfinite value.",
            timestamp=timestamp,
        ) from None


def resample_series(
    series, *, source_frequency, frequency, aggregation, timezone="UTC"
):
    """Aggregate into [start, end) buckets from first through last observation.

    The caller validates values and ordered timestamps. This simple operation
    supports standard Gregorian calendars and explicit coarsening, not interpolation.
    """
    try:
        declared_step = series_time_step(series)
        source = (
            normalize_time_step(source_frequency)
            if source_frequency is not None
            else declared_step
        )
        target = normalize_time_step(frequency)
    except ValueError as error:
        raise ProcessingError("invalid_resampling_parameters", str(error)) from None
    # Preserve the Series' spatial Aggregation when combining its values over time.
    declared_name = series.get("aggregation")
    declared_aggregation = (
        _AGGREGATIONS.get(declared_name) if isinstance(declared_name, str) else None
    )
    if declared_name is not None and declared_aggregation is None:
        raise ProcessingError(
            "invalid_series_aggregation",
            "The input declares an Aggregation this operation does not know.",
        )
    requested = _AGGREGATIONS.get(aggregation) if isinstance(aggregation, str) else None
    reducer = requested if aggregation is not None else declared_aggregation
    if source is None or reducer is None:
        raise ProcessingError(
            "invalid_resampling_parameters",
            "Provide a source Time step and an Aggregation (on the Series or instruction).",
        )
    if declared_aggregation is not None and reducer != declared_aggregation:
        raise ProcessingError(
            "aggregation_mismatch",
            f"This Series was built with the {declared_name} Aggregation; "
            "resampling over time must use the same rule.",
        )
    if declared_step is not None and source != declared_step:
        raise ProcessingError(
            "source_frequency_mismatch",
            "Source frequency contradicts the input's Time step.",
        )
    if "time_step" in series and timezone != "UTC":
        raise ProcessingError(
            "invalid_timezone", "Explore My World Time steps follow UTC."
        )
    require_coarser_time_step(source, target)
    if series.get("calendar", "standard") not in (
        "standard",
        "gregorian",
        "proleptic_gregorian",
    ):
        raise ProcessingError(
            "unsupported_calendar",
            "Resampling currently requires a Gregorian calendar.",
        )
    try:
        zone = ZoneInfo(timezone) if isinstance(timezone, str) else None
        if zone is None:
            raise ValueError
    except (ZoneInfoNotFoundError, ValueError):
        raise ProcessingError(
            "invalid_timezone", "Choose an IANA time zone such as UTC."
        ) from None
    groups = defaultdict(list)
    source_buckets = set()
    filled = series.get("filled", [False] * len(series["values"]))
    try:
        for stamp, value, was_filled in zip(
            series["timestamps"], series["values"], filled
        ):
            text = stamp + "-01" if len(stamp) == 7 else stamp
            instant = datetime.fromisoformat(text)
            instant = instant.replace(tzinfo=UTC) if instant.tzinfo is None else instant
            local = instant.astimezone(zone)
            source_key = _floor(local, source).astimezone(UTC)
            if source_key in source_buckets:
                raise ProcessingError(
                    "source_frequency_mismatch",
                    "More than one observation occupies a declared source-frequency bucket.",
                    timestamp=stamp,
                )
            source_buckets.add(source_key)
            groups[_floor(local, target).astimezone(UTC)].append((value, was_filled))
        first, last = min(groups), max(groups)
        output_times, output_values, counts, valid_counts = [], [], [], []
        output_filled = []
        cursor = first.astimezone(zone)
        while cursor.astimezone(UTC) <= last:
            key = cursor.astimezone(UTC)
            bucket = groups.get(key, [])
            valid = [value for value, _ in bucket if value is not None]
            label = cursor.isoformat()
            output_times.append(label)
            output_values.append(_aggregate(valid, reducer, label))
            counts.append(len(bucket))
            valid_counts.append(len(valid))
            output_filled.append(
                any(flag for value, flag in bucket if value is not None)
            )
            if key == last:
                break
            cursor = _next(cursor, target)
    except ProcessingError:
        raise
    except (ValueError, OverflowError):
        raise ProcessingError(
            "invalid_resampling_timestamps",
            "Timestamps cannot be resampled in the chosen time zone.",
        ) from None
    travelling = {} if declared_name is None else {"aggregation": declared_name}
    return {
        **travelling,
        "time_step": time_step_label(target),
        "timestamps": output_times,
        "values": output_values,
        "frequency": target,
        "filled": output_filled,
        "resampling": {
            "source_frequency": source,
            "frequency": target,
            "aggregation": reducer,
            "timezone": timezone,
            "sample_counts": counts,
            "valid_counts": valid_counts,
        },
    }
