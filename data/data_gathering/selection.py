"""Select a native-frequency series and gate the requested coverage before delivery."""

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from ..time_steps import utc_instant
from .models import Bbox, Period, SeriesQuality, Source
from .quality_gate import assess_quality, months_in, time_step_coverage


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
            if not all(
                re.fullmatch(r"\d{4}-\d{2}(?:-\d{2})?", value) for value in (start, end)
            ):
                raise ValueError
            first = datetime.strptime(start, "%Y-%m" if len(start) == 7 else "%Y-%m-%d")
            last = datetime.strptime(end, "%Y-%m" if len(end) == 7 else "%Y-%m-%d")
            if first > last:
                raise ValueError
            upper = (
                datetime(
                    last.year + (last.month == 12),
                    1 if last.month == 12 else last.month + 1,
                    1,
                )
                if len(end) == 7
                else last + timedelta(days=1)
            )
            lower_text = f"{first.year:04d}-{first.month:02d}-{first.day:02d}"
            upper_text = f"{upper.year:04d}-{upper.month:02d}-{upper.day:02d}"
            return cls(start, end, lower_text, upper_text)
        except (ValueError, OverflowError):
            raise SeriesSelectionError(
                "invalid_period",
                "Use a valid inclusive period in YYYY-MM or YYYY-MM-DD format, with start no later than end.",
            ) from None

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
    def select(
        self,
        area: Bbox,
        variable: str,
        window: TimeWindow,
        dataset_id: str | None = None,
    ) -> NativeSeries: ...


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


def select_series(
    source: SeriesSource,
    area: Bbox,
    variable: str,
    period: Period,
    dataset_id: str | None = None,
    *,
    time_step: str | None = None,
) -> SelectedSeries:
    """Gate every requested declared Time step while retaining native values.

    Omitting time_step preserves the legacy monthly catalog coverage contract.
    Declared cadence describes already sampled source values; it does not resample.
    """
    bounds = (area.west, area.east, area.south, area.north)
    if not all(math.isfinite(value) for value in bounds) or not (
        -180 <= area.west < area.east <= 180 and -90 <= area.south < area.north <= 90
    ):
        raise SeriesSelectionError(
            "invalid_request",
            "Provide a finite geographic area with west < east and south < north.",
        )
    window = TimeWindow.create(period.start, period.end)
    native = source.select(area, variable, window, dataset_id)
    try:
        lower, upper = utc_instant(window.lower), utc_instant(window.upper)
        observations = {
            stamp: value if value is not None and math.isfinite(value) else None
            for stamp, value in sorted(native.observations.items())
            if (
                lower <= utc_instant(stamp) < upper
                if time_step is not None
                else window.contains(stamp)
            )
        }
    except ValueError as error:
        raise SeriesSelectionError("invalid_timestamp", str(error)) from None
    if time_step is not None:
        if native.calendar not in ("standard", "gregorian", "proleptic_gregorian"):
            raise SeriesSelectionError(
                "unsupported_calendar",
                "Time-step coverage requires a Gregorian calendar.",
            )
        try:
            coverage = time_step_coverage(
                observations, window.lower, window.upper, time_step
            )
        except ValueError as error:
            raise SeriesSelectionError("invalid_time_step", str(error)) from None
    else:
        # Preserve the offline monthly catalog path when no Time step is declared.
        covered = {
            stamp[:7] for stamp, value in observations.items() if value is not None
        }
        coverage = [
            1.0 if month in covered else None
            for month in months_in(Period(period.start[:7], period.end[:7]))
        ]
    try:
        quality = assess_quality(
            coverage,
            land_only=native.land_only,
            valid_land_fraction=native.valid_land_fraction,
            time_step=time_step,
        )
    except ValueError:
        raise SeriesSelectionError(
            "land_mask_unavailable",
            "This Variable requires verified land-mask metadata before its series can be returned.",
        ) from None
    if not quality.included:
        reasons = []
        if "too_many_missing_time_steps" in quality.exclusions:
            reasons.append(
                "more than 20% of the requested Time steps have no valid data"
            )
        if "too_many_missing_months" in quality.exclusions:
            reasons.append(
                "more than 20% of the requested calendar months have no valid data"
            )
        if "insufficient_land_fraction" in quality.exclusions:
            reasons.append("less than 50% of the selected cells are valid land")
        raise SeriesSelectionError(
            "series_quality_excluded",
            "Series excluded: " + "; ".join(reasons) + ".",
            quality,
        )
    return SelectedSeries(
        native.dataset_id,
        native.variable,
        area,
        period,
        tuple(observations),
        tuple(observations.values()),
        native.units,
        native.calendar,
        native.source,
        quality,
    )
