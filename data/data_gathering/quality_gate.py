"""Coverage validation performed before returning a selected series."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime

from .models import Period, SeriesQuality


def months_in(period: Period) -> tuple[str, ...]:
    """Every calendar month in an inclusive requested period."""
    for month in (period.start, period.end):
        if len(month) != 7:
            raise ValueError("Periods must use YYYY-MM.")
        datetime.strptime(month, "%Y-%m")
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
) -> SeriesQuality:
    if len(values) == 0:
        raise ValueError("A series must contain at least one calendar month.")
    if land_only and (
        valid_land_fraction is None
        or not math.isfinite(valid_land_fraction)
        or not 0 <= valid_land_fraction <= 1
    ):
        raise ValueError("Land-only Variables require a valid land-cell fraction.")
    missing = sum(value is None or not math.isfinite(value) for value in values)
    exclusions = []
    if missing * 5 > len(values):
        exclusions.append("too_many_missing_months")
    if land_only and valid_land_fraction < 0.5:
        exclusions.append("insufficient_land_fraction")
    return SeriesQuality(
        included=not exclusions,
        missing_fraction=missing / len(values),
        valid_land_fraction=valid_land_fraction if land_only else None,
        exclusions=tuple(exclusions),
    )
