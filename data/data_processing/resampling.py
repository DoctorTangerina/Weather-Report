"""Explicit calendar-bucket aggregation of a single validated series."""

import math
import statistics
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import ProcessingError

_FREQUENCIES = {
    alias: frequency
    for frequency in ("second", "minute", "hour", "day", "month", "year")
    for alias in (frequency, frequency + "s")
}
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
    # The remaining Aggregations from CONTEXT.md, so that any Series' own rule can
    # also combine its values over time (space first, then time).
    "rms": "rms",
    "root_mean_square": "rms",
    "root mean square": "rms",
    "std": "std",
    "standard_deviation": "std",
    "standard deviation": "std",
    "mean_absolute": "mean_absolute",
    "mean_absolute_value": "mean_absolute",
    "mean absolute value": "mean_absolute",
}
_ORDER = {
    name: index
    for index, name in enumerate(("second", "minute", "hour", "day", "month", "year"))
}


def _floor(instant, frequency):
    if frequency == "second":
        return instant.replace(microsecond=0)
    if frequency == "minute":
        return instant.replace(second=0, microsecond=0)
    if frequency == "hour":
        return instant.replace(minute=0, second=0, microsecond=0)
    if frequency == "day":
        return instant.replace(hour=0, minute=0, second=0, microsecond=0)
    if frequency == "month":
        return instant.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return instant.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)


def _next(instant, frequency):
    if frequency in ("second", "minute", "hour"):
        seconds = {"second": 1, "minute": 60, "hour": 3600}[frequency]
        return (instant.astimezone(UTC) + timedelta(seconds=seconds)).astimezone(
            instant.tzinfo
        )
    if frequency == "day":
        return instant + timedelta(days=1)
    if frequency == "month":
        return instant.replace(
            year=instant.year + (instant.month == 12),
            month=1 if instant.month == 12 else instant.month + 1,
        )
    return instant.replace(year=instant.year + 1)


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
            # Scale by the largest magnitude first so squaring cannot overflow.
            largest = max(abs(v) for v in values)
            value = (
                0.0
                if largest == 0
                else largest
                * math.sqrt(statistics.fmean((v / largest) ** 2 for v in values))
            )
        elif aggregation == "std":
            value = statistics.pstdev(values)  # population, per CONTEXT.md
        elif aggregation == "mean_absolute":
            value = statistics.fmean(abs(v) for v in values)
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
    source = (
        _FREQUENCIES.get(source_frequency)
        if isinstance(source_frequency, str)
        else None
    )
    target = _FREQUENCIES.get(frequency) if isinstance(frequency, str) else None
    # A Series built with an Aggregation is combined over time by the same rule,
    # so the step may omit it and may not contradict it.
    declared_name = series.get("aggregation")
    declared = None
    if declared_name is not None:
        declared = (
            _AGGREGATIONS.get(declared_name) if isinstance(declared_name, str) else None
        )
        if declared is None:
            raise ProcessingError(
                "invalid_series_aggregation",
                "The input declares an Aggregation this operation does not know.",
            )
    requested = _AGGREGATIONS.get(aggregation) if isinstance(aggregation, str) else None
    reducer = requested if aggregation is not None else declared
    if source is None or target is None or reducer is None:
        raise ProcessingError(
            "invalid_resampling_parameters",
            "Choose source_frequency and frequency from second, minute, hour, day, "
            "month, year; choose aggregation from mean, sum, min, max, median, "
            "root mean square, standard deviation, mean absolute value.",
        )
    if declared is not None and reducer != declared:
        raise ProcessingError(
            "aggregation_mismatch",
            f"This Series was built with the {declared_name} Aggregation; "
            "resampling over time must use the same rule.",
        )
    if _ORDER[target] < _ORDER[source]:
        raise ProcessingError(
            "upsampling_not_supported", "Choose the same or a coarser frequency."
        )
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
    existing = series.get("frequency")
    if existing is not None and (
        not isinstance(existing, str) or _FREQUENCIES.get(existing) != source
    ):
        raise ProcessingError(
            "source_frequency_mismatch",
            "Source frequency contradicts the input's frequency metadata.",
        )
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
