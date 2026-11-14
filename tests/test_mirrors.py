"""BS-004: the engine finds Mirrors between series of different Regions.

Driven through `engine.find_mirrors` and `engine.find_candidate_discoveries` over
synthetic series, with no network.
"""

from __future__ import annotations

import dataclasses
import json
import math

import numpy as np
import pytest
from scipy import stats
from synthetic import (
    Q,
    driven_series,
    driver_signal,
    persistent_signal,
    rated_trends,
)

from engine import Catalog, find_candidate_discoveries, find_mirrors, load_catalog
from engine.contracts import Mirror, Series, SeriesRef, as_dict


def monthly_signal(series: Series, months: int = 300) -> np.ndarray:
    """What the synthetic series holds besides its known seasonal cycle."""
    cycle = [290 + 8.0 * math.sin(2 * math.pi * (i % 12) / 12) for i in range(months)]
    return np.array(series.values) - np.array(cycle)


def test_series_that_move_together_are_a_mirror_even_across_variables():
    driver = driver_signal(seed=1)
    # Given one Variable in one Region and another Variable in another Region that
    # share a month-to-month signal.
    series = [
        driven_series("amazon-basin", "temperature", driver, weight=1.0, seed=2),
        driven_series("sahel", "precipitation", driver, weight=1.0, seed=3),
    ]

    (mirror,) = find_mirrors(series, q=Q)

    assert mirror.series == (
        SeriesRef("amazon-basin", "temperature"),
        SeriesRef("sahel", "precipitation"),
    )
    assert mirror.correlation > 0.3
    assert mirror.significant_after_correction


def test_a_shared_seasonal_cycle_and_trend_are_not_a_mirror():
    flat = [0.0] * 300
    # Given two series with the same seasonal cycle and the same rising trend but
    # noise of their own, so nothing moves together from month to month.
    series = [
        driven_series(
            "amazon-basin", "temperature", flat, weight=0, seed=4, slope_per_decade=2.0
        ),
        driven_series(
            "sahel", "precipitation", flat, weight=0, seed=5, slope_per_decade=2.0
        ),
    ]

    assert find_mirrors(series, q=Q) == []


def test_a_significant_correlation_weaker_than_the_minimum_is_not_a_mirror():
    driver = driver_signal(seed=6)
    series = [
        driven_series(
            "amazon-basin", "temperature", driver, weight=0.5, seed=7, noise=1.0
        ),
        driven_series("sahel", "temperature", driver, weight=0.5, seed=8, noise=1.0),
    ]
    # Given a correlation that 300 months make significant, yet that is weak.
    result = stats.pearsonr(*(monthly_signal(s) for s in series))
    assert 0.1 < result.statistic < 0.3
    assert result.pvalue < 0.05

    assert find_mirrors(series, q=Q) == []


def correlated_pair(seed: int, *, months: int, weight: float = 1.0):
    driver = driver_signal(seed=seed, months=months)
    return [
        driven_series(
            "amazon-basin",
            "temperature",
            driver,
            weight=weight,
            seed=seed + 1,
            noise=1.0,
        ),
        driven_series(
            "sahel", "precipitation", driver, weight=weight, seed=seed + 2, noise=1.0
        ),
    ]


def unrelated_series(count: int, *, months: int):
    flat = [0.0] * months
    return [
        driven_series(
            f"filler-{n}", "temperature", flat, weight=0, seed=100 + n, noise=1.0
        )
        for n in range(count)
    ]


def test_a_correlation_that_chance_explains_across_many_pairs_is_not_a_mirror():
    pair = correlated_pair(seed=10, months=40, weight=0.7)
    # Given a pair that is significant on its own, and weak enough over 40 months
    # that it is the kind of thing many comparisons turn up by chance.
    result = stats.pearsonr(*(monthly_signal(s, 40) for s in pair))
    assert result.statistic >= 0.3
    assert 0.01 < result.pvalue < 0.05
    assert len(find_mirrors(pair, q=Q)) == 1

    among_many = find_mirrors([*pair, *unrelated_series(10, months=40)], q=Q)

    assert among_many == []


def test_series_over_different_periods_are_compared_on_the_months_they_share():
    driver = driver_signal(seed=21)
    # Given a series for 2000-2024 and one for only 2018-2024 that share a signal.
    long = driven_series("amazon-basin", "temperature", driver, weight=1.0, seed=22)
    short = driven_series(
        "sahel", "precipitation", driver, weight=1.0, seed=23, first_month=216
    )

    (mirror,) = find_mirrors([long, short], q=Q)

    assert mirror.correlation > 0.3


def test_series_that_share_too_few_months_are_not_compared():
    driver = driver_signal(seed=24)
    early = driven_series(
        "amazon-basin", "temperature", driver, weight=1.0, seed=25, months=120
    )
    # Given a series that overlaps the first by only a year, and one that is
    # disjoint from it altogether.
    brief_overlap = driven_series(
        "sahel", "precipitation", driver, weight=1.0, seed=26, first_month=108
    )
    disjoint = driven_series(
        "congo-basin", "temperature", driver, weight=1.0, seed=27, first_month=200
    )

    assert find_mirrors([early, brief_overlap], q=Q) == []
    assert find_mirrors([early, disjoint], q=Q) == []


def test_a_series_that_never_changes_is_not_a_mirror():
    driver = driver_signal(seed=28)
    series = [
        driven_series("amazon-basin", "temperature", driver, weight=1.0, seed=29),
        driven_series(
            "sahara", "precipitation", driver, weight=0, seed=30, constant=True
        ),
    ]

    assert find_mirrors(series, q=Q) == []


def test_independent_series_that_drift_slowly_are_not_a_mirror():
    # Given two independent series that each remember their last month, which
    # months of chance agreement can make look correlated.
    series = [
        driven_series(
            "amazon-basin",
            "temperature",
            persistent_signal(seed=45),
            weight=1.0,
            seed=1,
            noise=0.0,
        ),
        driven_series(
            "sahel",
            "precipitation",
            persistent_signal(seed=1045),
            weight=1.0,
            seed=2,
            noise=0.0,
        ),
    ]
    months = np.arange(300)
    residual = [
        monthly_signal(s) - np.polyval(np.polyfit(months, monthly_signal(s), 1), months)
        for s in series
    ]
    naive = stats.pearsonr(*residual)
    assert abs(naive.statistic) >= 0.3
    assert naive.pvalue < 0.05

    assert find_mirrors(series, q=Q) == []


def test_series_that_move_in_opposite_directions_are_a_mirror():
    driver = driver_signal(seed=31)
    series = [
        driven_series("amazon-basin", "temperature", driver, weight=1.0, seed=32),
        driven_series("sahel", "precipitation", driver, weight=-1.0, seed=33),
    ]

    (mirror,) = find_mirrors(series, q=Q)

    assert mirror.correlation < -0.3


def test_months_a_series_is_missing_are_left_out_of_the_comparison():
    driver = driver_signal(seed=34)
    first = driven_series("amazon-basin", "temperature", driver, weight=1.0, seed=35)
    second = driven_series("sahel", "precipitation", driver, weight=1.0, seed=36)
    gappy = dataclasses.replace(
        first,
        values=tuple(None if i % 7 == 0 else v for i, v in enumerate(first.values)),
    )

    (mirror,) = find_mirrors([gappy, second], q=Q)

    assert mirror.correlation > 0.3


@pytest.fixture(scope="module")
def catalog(stub_dir) -> Catalog:
    return load_catalog(stub_dir / "catalog.json")


def mirror_between(first: SeriesRef, second: SeriesRef, **overrides) -> Mirror:
    fields = {
        "correlation": 0.6,
        "p_value": 0.001,
        "adjusted_p_value": 0.002,
        "significant_after_correction": True,
    }
    return Mirror((first, second), **{**fields, **overrides})


AMAZON_TEMPERATURE = SeriesRef("amazon-basin", "temperature")
SAHEL_PRECIPITATION = SeriesRef("sahel", "precipitation")
CONTRAST = {("amazon-basin", "temperature"): 0.6, ("sahel", "temperature"): -0.6}


def test_a_pair_of_regions_with_a_contrast_and_a_mirror_lists_the_mirror(catalog):
    driver = driver_signal(seed=41)
    mirrors = find_mirrors(
        [
            driven_series("amazon-basin", "temperature", driver, weight=1.0, seed=42),
            driven_series("sahel", "precipitation", driver, weight=1.0, seed=43),
        ],
        q=Q,
    )
    without = find_candidate_discoveries(rated_trends(CONTRAST), catalog)

    (candidate,) = find_candidate_discoveries(rated_trends(CONTRAST), catalog, mirrors)

    assert candidate.mirrors == tuple(mirrors)
    assert len(candidate.mirrors) == 1
    assert candidate.score_components.mirror == 5.0
    assert candidate.score == without[0].score + 5.0
    # The Evidence label rests on the Trends alone.
    assert candidate.evidence_label == without[0].evidence_label


def test_each_mirror_between_the_regions_adds_to_the_score(catalog):
    mirrors = [
        mirror_between(AMAZON_TEMPERATURE, SAHEL_PRECIPITATION),
        mirror_between(AMAZON_TEMPERATURE, SeriesRef("sahel", "temperature")),
    ]

    (candidate,) = find_candidate_discoveries(rated_trends(CONTRAST), catalog, mirrors)

    assert candidate.score_components.mirror == 10.0


def test_a_mirror_in_another_pair_of_regions_is_not_listed(catalog):
    elsewhere = mirror_between(
        AMAZON_TEMPERATURE, SeriesRef("congo-basin", "temperature")
    )

    (candidate,) = find_candidate_discoveries(
        rated_trends(CONTRAST), catalog, [elsewhere]
    )

    assert candidate.mirrors == ()
    assert candidate.score_components.mirror == 0.0


def test_a_mirror_without_a_contrast_is_not_a_candidate(catalog):
    alike = rated_trends(
        {("amazon-basin", "temperature"): 0.5, ("sahel", "temperature"): 0.6}
    )
    mirror = mirror_between(AMAZON_TEMPERATURE, SAHEL_PRECIPITATION)

    assert find_candidate_discoveries(alike, catalog, [mirror]) == []


def test_a_mirror_that_is_not_significant_after_correction_adds_nothing(catalog):
    chance = mirror_between(
        AMAZON_TEMPERATURE, SAHEL_PRECIPITATION, significant_after_correction=False
    )

    (candidate,) = find_candidate_discoveries(rated_trends(CONTRAST), catalog, [chance])

    assert candidate.mirrors == ()
    assert candidate.score_components.mirror == 0.0


def test_a_candidate_with_a_mirror_follows_the_discovery_schema(catalog, validator_for):
    mirror = mirror_between(SAHEL_PRECIPITATION, AMAZON_TEMPERATURE)

    (candidate,) = find_candidate_discoveries(rated_trends(CONTRAST), catalog, [mirror])

    payload = json.loads(json.dumps(as_dict(candidate)))
    validator_for("discovery.schema.json").validate(payload)
    assert payload["mirrors"][0]["correlation"] == 0.6
