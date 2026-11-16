"""Requested-window coverage, not cached whole-series quality, governs delivery."""

import pytest

from data.data_gathering.models import Bbox, Period, Source
from data.data_gathering.selection import (
    NativeSeries,
    SeriesSelectionError,
    TimeWindow,
    select_series,
)

AREA = Bbox(west=-10, east=10, south=-5, north=5)


class SourceFixture:
    def __init__(self, observations, *, land_only=False, fraction=None):
        self.native = NativeSeries(
            "test",
            "field",
            "K",
            "standard",
            observations,
            Source("test", "test", "field"),
            land_only,
            fraction,
        )

    def select(self, area, variable, window, dataset_id=None):
        return self.native


def test_short_requested_window_is_rechecked_even_if_whole_year_would_pass():
    values = {
        f"2024-{month:02d}-01T00:00:00": (None if month < 3 else 10.0)
        for month in range(1, 13)
    }
    source = SourceFixture(values)
    assert select_series(
        source, AREA, "field", Period("2024-01", "2024-12")
    ).quality.included
    with pytest.raises(SeriesSelectionError) as rejected:
        select_series(source, AREA, "field", Period("2024-01", "2024-03"))
    assert rejected.value.code == "series_quality_excluded"
    assert rejected.value.quality.missing_fraction == pytest.approx(2 / 3)


def test_absent_leading_trailing_and_internal_months_are_counted():
    source = SourceFixture({"2024-02-01T00:00:00": 1.0, "2024-04-01T00:00:00": 2.0})
    with pytest.raises(SeriesSelectionError) as rejected:
        select_series(source, AREA, "field", Period("2024-01", "2024-05"))
    assert rejected.value.quality.missing_fraction == 0.6


def test_native_timestamps_units_and_requested_dates_are_preserved():
    observations = {
        "2024-01-01T00:00:00": 2.0,
        "2024-01-02T01:00:00": 3.0,
        "2024-01-02T06:00:00": 4.0,
        "2024-01-03T00:00:00": 5.0,
    }
    selected = select_series(
        SourceFixture(observations), AREA, "field", Period("2024-01-02", "2024-01-02")
    )
    assert selected.timestamps == ("2024-01-02T01:00:00", "2024-01-02T06:00:00")
    assert selected.values == (3.0, 4.0)
    assert selected.units == "K"


@pytest.mark.parametrize("fraction,passes", [(0.49, False), (0.5, True)])
def test_land_fraction_is_verified_before_returning(fraction, passes):
    source = SourceFixture(
        {"2024-01-01T00:00:00": 1.0}, land_only=True, fraction=fraction
    )
    if passes:
        assert select_series(
            source, AREA, "field", Period("2024-01", "2024-01")
        ).quality.included
    else:
        with pytest.raises(SeriesSelectionError) as rejected:
            select_series(source, AREA, "field", Period("2024-01", "2024-01"))
        assert rejected.value.quality.exclusions == ("insufficient_land_fraction",)


def test_land_only_without_verified_mask_is_not_returned():
    with pytest.raises(SeriesSelectionError, match="land-mask") as rejected:
        select_series(
            SourceFixture({"2024-01-01T00:00:00": 1}, land_only=True),
            AREA,
            "field",
            Period("2024-01", "2024-01"),
        )
    assert rejected.value.code == "land_mask_unavailable"


@pytest.mark.parametrize(
    "start,end",
    [
        ("2024-02", "2024-01"),
        ("2024-13", "2025-01"),
        ("2024-02-30", "2024-03-01"),
        ("2024-1", "2024-12"),
    ],
)
def test_invalid_period_is_rejected(start, end):
    with pytest.raises(SeriesSelectionError) as rejected:
        TimeWindow.create(start, end)
    assert rejected.value.code == "invalid_period"
