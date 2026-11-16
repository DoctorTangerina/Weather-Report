"""BS-003: the engine excludes series without enough valid data from every Discovery.

The data layer decides whether a series passes the gate and records it in
`Series.quality`. These tests drive the engine's public interface (seam 1) with
synthetic series: a series the gate excluded must reach no Trend, no Mirror and
so no Candidate Discovery, even if it still carries values.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from synthetic import Q, driven_series, driver_signal, series_for

from engine import (
    Series,
    estimate_trend,
    find_candidate_discoveries,
    find_mirrors,
    load_catalog,
    rate_evidence,
    usable_series,
)
from engine.contracts import SeriesQuality

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "catalog.json"

TOO_MANY_MISSING = SeriesQuality(
    included=False,
    missing_fraction=0.25,
    valid_land_fraction=None,
    exclusions=("too_many_missing_months",),
)
TOO_LITTLE_LAND = SeriesQuality(
    included=False,
    missing_fraction=0.0,
    valid_land_fraction=0.4,
    exclusions=("insufficient_land_fraction",),
)


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(CATALOG_PATH)


def excluded(series: Series, quality: SeriesQuality) -> Series:
    """The same series after the data layer's gate rejected it; values untouched."""
    return dataclasses.replace(series, quality=quality)


def candidates_from(series: list[Series], catalog):
    """What the engine can discover from these series: Trends, Mirrors, Candidates."""
    trends = rate_evidence([estimate_trend(one) for one in usable_series(series)], q=Q)
    return find_candidate_discoveries(trends, catalog, find_mirrors(series))


def opposite_trends(variable: str = "temperature") -> list[Series]:
    return [
        series_for("amazon-basin", variable, 3.0, seed=1),
        series_for("sahel", variable, -3.0, seed=2),
    ]


@pytest.mark.parametrize("quality", [TOO_MANY_MISSING, TOO_LITTLE_LAND])
def test_a_series_the_gate_excluded_is_in_no_candidate_discovery(catalog, quality):
    # Given the same two Regions would otherwise be a Candidate Discovery
    amazon, sahel = opposite_trends()
    assert [d.discovery_id for d in candidates_from([amazon, sahel], catalog)] == [
        "amazon-basin--sahel"
    ]
    # When the gate excluded one of the series
    found = candidates_from([amazon, excluded(sahel, quality)], catalog)
    # Then the engine excludes that series from every Candidate Discovery
    assert found == []


def test_an_excluded_series_is_in_no_candidate_even_beside_other_regions(catalog):
    amazon, sahel = opposite_trends()
    india = series_for("central-india", "temperature", 3.0, seed=3)
    found = candidates_from([amazon, excluded(sahel, TOO_MANY_MISSING), india], catalog)
    assert all("sahel" not in d.region_ids for d in found)
    assert [d.discovery_id for d in found] == []


def test_a_land_only_variable_is_dropped_for_a_region_with_too_little_land(catalog):
    amazon, sahel = opposite_trends("soil-moisture")
    found = candidates_from([amazon, excluded(sahel, TOO_LITTLE_LAND)], catalog)
    assert found == []


def test_usable_series_keeps_only_series_that_passed_the_gate():
    amazon, sahel = opposite_trends()
    kept = usable_series([amazon, excluded(sahel, TOO_MANY_MISSING)])
    assert kept == [amazon]


def test_a_trend_is_never_estimated_from_an_excluded_series():
    _, sahel = opposite_trends()
    with pytest.raises(ValueError, match="too_many_missing_months"):
        estimate_trend(excluded(sahel, TOO_MANY_MISSING))


def test_a_series_the_gate_excluded_is_never_part_of_a_mirror():
    driver = driver_signal(seed=1)
    first = driven_series("amazon-basin", "temperature", driver, weight=1.0, seed=2)
    second = driven_series("sahel", "precipitation", driver, weight=1.0, seed=3)
    assert len(find_mirrors([first, second])) == 1
    assert find_mirrors([first, excluded(second, TOO_MANY_MISSING)]) == []


@pytest.mark.parametrize(
    "quality",
    [
        # exactly 20% of the months missing, exactly 50% of the cells valid land
        SeriesQuality(included=True, missing_fraction=0.2, valid_land_fraction=None),
        SeriesQuality(included=True, missing_fraction=0.0, valid_land_fraction=0.5),
    ],
)
def test_a_series_exactly_at_a_threshold_is_not_excluded_from_any_candidate(
    catalog, quality
):
    amazon, sahel = opposite_trends("soil-moisture")
    at_threshold = dataclasses.replace(sahel, quality=quality)
    found = candidates_from([amazon, at_threshold], catalog)
    assert [d.discovery_id for d in found] == ["amazon-basin--sahel"]
