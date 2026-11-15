"""The gate belongs to data gathering and passes exact threshold boundaries."""

import pytest

from data.data_gathering.models import Period
from data.data_gathering.quality_gate import assess_quality, months_in


@pytest.mark.parametrize(
    "missing,included", [(1, True), (2, True), (3, False), (10, False)]
)
def test_twenty_percent_missing_boundary(missing, included):
    quality = assess_quality([None] * missing + [1.0] * (10 - missing), land_only=False)
    assert quality.included is included
    assert ("too_many_missing_months" in quality.exclusions) is (not included)


# #49 amendment: the gate counts missing Time steps, whatever the Time step is.
@pytest.mark.parametrize("missing,included", [(6, True), (7, False)])
def test_daily_series_counts_missing_days_against_the_same_threshold(missing, included):
    june = [None] * missing + [1.0] * (30 - missing)
    quality = assess_quality(june, land_only=False)
    assert quality.included is included
    assert quality.missing_fraction == missing / 30


@pytest.mark.parametrize(
    "fraction,included", [(0, False), (0.49, False), (0.5, True), (1, True)]
)
def test_half_land_boundary(fraction, included):
    quality = assess_quality([1.0], land_only=True, valid_land_fraction=fraction)
    assert quality.included is included


def test_both_failures_are_reported():
    quality = assess_quality([None], land_only=True, valid_land_fraction=0.4)
    assert set(quality.exclusions) == {
        "too_many_missing_months",
        "insufficient_land_fraction",
    }


def test_missing_land_metadata_cannot_pass():
    with pytest.raises(ValueError):
        assess_quality([1.0], land_only=True)


def test_period_includes_every_calendar_month_across_year_boundary():
    assert months_in(Period("2023-12", "2024-02")) == ("2023-12", "2024-01", "2024-02")
