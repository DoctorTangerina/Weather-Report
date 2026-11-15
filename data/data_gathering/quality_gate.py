"""Coverage validation performed before returning a selected series."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime

from ..time_steps import normalize_time_step, utc_instant
from .models import Period, SeriesQuality


def months_in(period: Period) -> tuple[str, ...]:
    """Every calendar month in an inclusive requested period."""
    for month_text in (period.start, period.end):
        if len(month_text) != 7:
            raise ValueError("Periods must use YYYY-MM.")
        datetime.strptime(month_text, "%Y-%m")
    if period.start > period.end:
        raise ValueError("Period start must not be later than its end.")
    year, month = map(int, period.start.split("-"))
    result = []
    while f"{year:04d}-{month:02d}" <= period.end:
        result.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return tuple(result)


def assess_quality(
    values: Sequence[float | None],
    *,
    land_only: bool,
    valid_land_fraction: float | None = None,
    time_step: str | None = None,
) -> SeriesQuality:
    if len(values) == 0:
        raise ValueError("A series must contain at least one Time step.")
    if time_step is not None:
        normalize_time_step(time_step)
    if land_only and (
        valid_land_fraction is None
        or not math.isfinite(valid_land_fraction)
        or not 0 <= valid_land_fraction <= 1
    ):
        raise ValueError("Land-only Variables require a valid land-cell fraction.")
    missing = sum(value is None or not math.isfinite(value) for value in values)
    exclusions = []
    if missing * 5 > len(values):
        exclusions.append(
            "too_many_missing_time_steps"
            if time_step is not None
            else "too_many_missing_months"
        )
    if land_only and valid_land_fraction is not None and valid_land_fraction < 0.5:
        exclusions.append("insufficient_land_fraction")
    return SeriesQuality(
        included=not exclusions,
        missing_fraction=missing / len(values),
        valid_land_fraction=valid_land_fraction if land_only else None,
        exclusions=tuple(exclusions),
    )


def time_step_coverage(observations, lower: str, upper: str, time_step: str):
    """Coverage of every requested UTC bucket, including absent timestamps."""
    from datetime import UTC, timedelta

    frequency = normalize_time_step(time_step)
    if frequency not in ("3-hour", "day", "month"):
        raise ValueError("Select a 3-hourly, daily or monthly Time step.")
    start = utc_instant(lower)
    end = utc_instant(upper)

    def bucket(value):
        value = value.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
        if frequency == "month":
            return value.replace(day=1, hour=0)
        return value.replace(hour=(value.hour // 3) * 3 if frequency == "3-hour" else 0)

    buckets = {}
    for stamp, value in observations.items():
        instant = utc_instant(stamp)
        if not start <= instant < end:
            continue
        key = bucket(instant)
        if key in buckets:
            raise ValueError(
                "Resample observations to the declared Time step before assessing coverage."
            )
        buckets[key] = value
    coverage = []
    cursor = bucket(start)
    while cursor < end:
        coverage.append(buckets.get(cursor))
        if frequency == "month":
            if cursor.year == 9999 and cursor.month == 12:
                break
            cursor = cursor.replace(
                year=cursor.year + (cursor.month == 12),
                month=1 if cursor.month == 12 else cursor.month + 1,
            )
        else:
            cursor += timedelta(hours=3) if frequency == "3-hour" else timedelta(days=1)
    return coverage
