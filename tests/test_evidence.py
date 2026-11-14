"""BS-002: the engine rates how strongly the data support a Trend.

Driven through `engine`'s public interface only (`estimate_trend`, then
`rate_evidence` over the family of Trends), on synthetic series with no network.
"""

from __future__ import annotations

import math
import random
from dataclasses import replace

import pytest

import engine
from engine import Period, Series, estimate_trend, rate_evidence
from engine.contracts import SeriesQuality, Source, Trend, as_dict, direction_of

MONTHS = 300  # 2000-01 .. 2024-12
Q = 0.05  # the caller chooses the false-discovery rate; the ticket leaves it open
# Flat series whose noise leaves no hint of a slope (least-squares p above 0.2).
FLAT_SEEDS = (0, 3, 4, 5, 6, 7, 9, 10)


def synthetic_series(
    slope_per_decade: float,
    *,
    seed: int,
    noise: float = 0.4,
    autocorrelation: float = 0.0,
    spikes: dict[int, float] | None = None,
) -> Series:
    """A repeating seasonal cycle, a constant slope, seeded noise, optional spikes.

    With `autocorrelation` above zero each month's noise carries over into the
    next, as monthly climate data does.
    """
    rng = random.Random(seed)
    spikes = spikes or {}
    values: list[float | None] = []
    shock = 0.0
    for i in range(MONTHS):
        shock = autocorrelation * shock + rng.gauss(0, noise)
        values.append(
            round(
                290
                + 8.0 * math.sin(2 * math.pi * (i % 12) / 12)
                + slope_per_decade * i / 120
                + shock
                + spikes.get(i, 0.0),
                3,
            )
        )
    return Series(
        region_id="sahel",
        variable_id="temperature",
        period=Period(start="2000-01", end="2024-12"),
        units="K",
        values=tuple(values),
        quality=SeriesQuality(
            included=True, missing_fraction=0.0, valid_land_fraction=1.0
        ),
        source=Source(provider="Synthetic", dataset="TEST", variable="t"),
        engine_version=engine.ENGINE_VERSION,
    )


def method_directions(trend: Trend) -> set[str]:
    """The direction each method reports, the primary fit included."""
    methods = trend.methods
    return {
        direction_of(value)
        for value in (
            trend.rate_per_decade,
            methods.annual_anomaly.slope_per_decade,
            methods.robust.slope_per_decade,
            methods.theil_sen.slope_per_decade,
            methods.mann_kendall.tau,
        )
    }


def test_a_flat_noisy_series_is_not_enough_evidence():
    # Seasonal cycle and noise, no slope.
    trend = estimate_trend(synthetic_series(0.0, seed=0))

    (rated,) = rate_evidence([trend], q=Q)

    assert rated.evidence_label == "Not enough evidence yet"


def test_a_trend_every_method_agrees_on_is_strong_evidence():
    trend = estimate_trend(synthetic_series(0.5, seed=0))
    flat_family = [estimate_trend(synthetic_series(0.0, seed=s)) for s in FLAT_SEEDS]
    # Given the fits and the Mann-Kendall test agree and the Trend survives
    # removing its most extreme month.
    assert method_directions(trend) == {"rising"}
    assert trend.methods.outlier_check.survives

    rated, *_ = rate_evidence([trend, *flat_family], q=Q)

    # ...and it is significant after correction for many comparisons.
    assert rated.multiple_comparisons.family_size == 1 + len(FLAT_SEEDS)
    assert rated.multiple_comparisons.significant
    assert rated.evidence_label == "Strong evidence"


def test_a_robust_fit_that_disagrees_caps_the_label_at_some_evidence():
    # A falling bulk with isolated warm months late in the series: those months
    # drag the least-squares fit upward while the robust fit follows the bulk.
    warm_months = random.Random(1000).sample(range(MONTHS - 120, MONTHS), 30)
    trend = estimate_trend(
        synthetic_series(
            -0.5, seed=0, noise=0.3, spikes={month: 8.0 for month in warm_months}
        )
    )
    # Given the least-squares fit is significant and the robust fit disagrees on
    # the direction. The outlier check passes, so only the disagreement can cap.
    assert trend.methods.least_squares.p_value < 0.05
    assert trend.direction == "rising"
    assert direction_of(trend.methods.robust.slope_per_decade) == "falling"
    assert trend.methods.outlier_check.survives

    (rated,) = rate_evidence([trend], q=Q)

    assert rated.evidence_label == "Some evidence"


def with_opposite_direction(trend: Trend, method: str) -> Trend:
    """The same Trend, but one cross-check reports the opposite direction."""
    methods = trend.methods
    result = getattr(methods, method)
    field = "tau" if method == "mann_kendall" else "slope_per_decade"
    flipped = replace(result, **{field: -getattr(result, field)})
    return replace(trend, methods=replace(methods, **{method: flipped}))


@pytest.mark.parametrize(
    "method", ["annual_anomaly", "robust", "theil_sen", "mann_kendall"]
)
def test_any_cross_check_that_disagrees_caps_the_label_at_some_evidence(method: str):
    strong = estimate_trend(synthetic_series(0.5, seed=0))
    assert rate_evidence([strong], q=Q)[0].evidence_label == "Strong evidence"

    (rated,) = rate_evidence([with_opposite_direction(strong, method)], q=Q)

    assert rated.evidence_label == "Some evidence"


def test_a_trend_that_needs_its_most_extreme_month_is_capped_at_some_evidence():
    # No real slope, but one extremely warm final month tips the fit over.
    trend = estimate_trend(synthetic_series(0.0, seed=1, spikes={MONTHS - 1: 15.0}))
    # Given the Trend is significant, the methods agree on its direction, and it
    # is no longer significant once the most extreme month is removed.
    assert trend.methods.least_squares.p_value < 0.05
    assert method_directions(trend) == {"rising"}
    assert trend.methods.outlier_check.removed_month == "2024-12"
    assert not trend.methods.outlier_check.survives

    (rated,) = rate_evidence([trend], q=Q)

    assert rated.evidence_label == "Some evidence"


def test_a_trend_significant_only_before_correction_is_some_evidence():
    # A flat series that looks significant by chance, one test among many.
    chance = estimate_trend(synthetic_series(0.0, seed=11))
    flat_family = [estimate_trend(synthetic_series(0.0, seed=s)) for s in FLAT_SEEDS]
    # Given the Trend is significant at the 95% level and nothing else would
    # stop it being Strong evidence: the methods agree and it survives the
    # outlier check, so on its own it passes the correction too.
    assert chance.methods.least_squares.p_value < 0.05
    assert method_directions(chance) == {"falling"}
    assert chance.methods.outlier_check.survives
    assert rate_evidence([chance], q=Q)[0].evidence_label == "Strong evidence"

    rated = rate_evidence([chance, *flat_family], q=Q)

    assert rated[0].evidence_label == "Some evidence"
    assert {trend.evidence_label for trend in rated[1:]} == {"Not enough evidence yet"}


def benjamini_hochberg(p_values: list[float]) -> list[float]:
    """Textbook step-up adjustment, written out so it shares no code with the engine."""
    count = len(p_values)
    order = sorted(range(count), key=lambda i: p_values[i])
    adjusted = [0.0] * count
    smallest = 1.0
    for rank in range(count, 0, -1):
        index = order[rank - 1]
        smallest = min(smallest, p_values[index] * count / rank)
        adjusted[index] = smallest
    return adjusted


def test_each_trend_records_the_correction_applied_across_the_whole_family():
    family = [estimate_trend(synthetic_series(0.5, seed=0))] + [
        estimate_trend(synthetic_series(0.0, seed=seed))
        for seed in (0, 1, 2, 3, 4, 7, 8)
    ]
    # Given no autocorrelation penalty, so each Trend's p-value is its
    # least-squares p-value.
    assert all(t.autocorrelation.effective_sample_size == MONTHS for t in family)
    p_values = [t.methods.least_squares.p_value for t in family]
    expected = benjamini_hochberg(p_values)

    rated = rate_evidence(family, q=Q)

    assert [t.multiple_comparisons.significant for t in rated] == [
        adjusted <= Q for adjusted in expected
    ]
    assert {t.multiple_comparisons.significant for t in rated} == {True, False}
    for trend, adjusted in zip(rated, expected, strict=True):
        correction = trend.multiple_comparisons
        assert correction.method == "benjamini-hochberg"
        assert correction.q == Q
        assert correction.family_size == len(family)
        assert correction.adjusted_p_value == pytest.approx(adjusted)


def test_a_trend_whose_corrected_interval_includes_zero_is_not_enough_evidence():
    # Month-to-month persistence in the noise makes a flat series look as if it
    # has a Trend when every month is counted as independent information.
    trend = estimate_trend(
        synthetic_series(0.0, seed=12, noise=0.3, autocorrelation=0.8)
    )
    # Given the plain least-squares fit looks significant and everything else
    # would support Strong evidence, but the interval, once widened for
    # autocorrelation, includes zero.
    low, high = trend.confidence_interval_95
    assert trend.methods.least_squares.p_value < 0.01
    assert method_directions(trend) == {"falling"}
    assert trend.methods.outlier_check.survives
    assert low < 0 < high

    (rated,) = rate_evidence([trend], q=Q)

    assert rated.evidence_label == "Not enough evidence yet"


def test_rated_trends_of_every_label_follow_the_trend_schema(validator_for):
    family = [
        estimate_trend(synthetic_series(0.5, seed=0)),
        estimate_trend(synthetic_series(0.0, seed=1, spikes={MONTHS - 1: 15.0})),
        estimate_trend(synthetic_series(0.0, seed=0)),
    ]

    rated = rate_evidence(family, q=Q)

    assert [trend.evidence_label for trend in rated] == [
        "Strong evidence",
        "Some evidence",
        "Not enough evidence yet",
    ]
    for trend in rated:
        payload = as_dict(trend)
        payload["confidence_interval_95"] = list(payload["confidence_interval_95"])
        validator_for("trend.schema.json").validate(payload)


def test_the_false_discovery_rate_is_one_value_for_the_whole_engine():
    assert engine.FALSE_DISCOVERY_RATE == 0.05

    family = [estimate_trend(synthetic_series(0.5, seed=0))]
    (by_default,) = rate_evidence(family)

    assert by_default.multiple_comparisons.q == engine.FALSE_DISCOVERY_RATE
