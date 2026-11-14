"""Select a native-frequency series and gate the requested coverage before delivery."""

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from .models import Bbox, Period, SeriesQuality, Source
from .quality_gate import assess_quality, months_in


class SeriesSelectionError(ValueError):
    def __init__(self, code: str, message: str, quality: SeriesQuality | None = None):
        super().__init__(message)
        self.code = code
        self.quality = quality


@dataclass(frozen=True)
class TimeWindow:
    start: str
    end: str
    lower: str
    upper: str

    @classmethod
    def create(cls, start: str, end: str):
        try:
            if not all(re.fullmatch(r"\d{4}-\d{2}(?:-\d{2})?", value) for value in (start, end)):
                raise ValueError
            first = datetime.strptime(start, "%Y-%m" if len(start) == 7 else "%Y-%m-%d")
            last = datetime.strptime(end, "%Y-%m" if len(end) == 7 else "%Y-%m-%d")
            if first > last:
                raise ValueError
            upper = (datetime(last.year + (last.month == 12), 1 if last.month == 12 else last.month + 1, 1)
                     if len(end) == 7 else last + timedelta(days=1))
            lower_text = f"{first.year:04d}-{first.month:02d}-{first.day:02d}"
            upper_text = f"{upper.year:04d}-{upper.month:02d}-{upper.day:02d}"
            return cls(start, end, lower_text, upper_text)
        except (ValueError, OverflowError):
            raise SeriesSelectionError("invalid_period", "Use a valid inclusive period in YYYY-MM or YYYY-MM-DD format, with start no later than end.") from None

    def contains(self, timestamp: str) -> bool:
        return self.lower <= timestamp < self.upper


@dataclass(frozen=True)
class NativeSeries:
    dataset_id: str
    variable: str
    units: str
    calendar: str
    observations: dict[str, float | None]
    source: Source
    land_only: bool = False
    valid_land_fraction: float | None = None


class SeriesSource(Protocol):
    def select(self, area: Bbox, variable: str, window: TimeWindow,
               dataset_id: str | None = None) -> NativeSeries: ...


@dataclass(frozen=True)
class SelectedSeries:
    dataset_id: str
    variable: str
    area: Bbox
    period: Period
    timestamps: tuple[str, ...]
    values: tuple[float | None, ...]
    units: str
    calendar: str
    source: Source
    quality: SeriesQuality


def select_series(source: SeriesSource, area: Bbox, variable: str, period: Period,
                  dataset_id: str | None = None) -> SelectedSeries:
    """Missing means no valid observation anywhere in a requested calendar month.

    Native timestamps and values are retained. This is a monthly-coverage gate,
    not a guarantee of complete daily/hourly sampling within each month.
    """
    bounds = (area.west, area.east, area.south, area.north)
    if (not all(math.isfinite(value) for value in bounds)
            or not (-180 <= area.west < area.east <= 180 and -90 <= area.south < area.north <= 90)):
        raise SeriesSelectionError("invalid_request", "Provide a finite geographic area with west < east and south < north.")
    window = TimeWindow.create(period.start, period.end)
    native = source.select(area, variable, window, dataset_id)
    observations = {
        stamp: value if value is not None and math.isfinite(value) else None
        for stamp, value in sorted(native.observations.items()) if window.contains(stamp)
    }
    covered = {stamp[:7] for stamp, value in observations.items() if value is not None}
    monthly = [1.0 if month in covered else None
               for month in months_in(Period(period.start[:7], period.end[:7]))]
    try:
        quality = assess_quality(monthly, land_only=native.land_only,
                                 valid_land_fraction=native.valid_land_fraction)
    except ValueError:
        raise SeriesSelectionError("land_mask_unavailable", "This Variable requires verified land-mask metadata before its series can be returned.") from None
    if not quality.included:
        reasons = []
        if "too_many_missing_months" in quality.exclusions:
            reasons.append("more than 20% of the requested calendar months have no valid data")
        if "insufficient_land_fraction" in quality.exclusions:
            reasons.append("less than 50% of the selected cells are valid land")
        raise SeriesSelectionError("series_quality_excluded", "Series excluded: " + "; ".join(reasons) + ".", quality)
    return SelectedSeries(native.dataset_id, native.variable, area, period,
                          tuple(observations), tuple(observations.values()), native.units,
                          native.calendar, native.source, quality)
