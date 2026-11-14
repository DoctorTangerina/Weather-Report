"""BS-001: the engine recovers a known slope from a seasonal monthly series.

Driven through `engine`'s public interface only, on synthetic series, with no
network.
"""

from __future__ import annotations

import dataclasses
import math
import random
import socket

import pytest

import engine
from engine import Period, Series, estimate_trend
from engine.contracts import SeriesQuality, Source, as_dict

MONTHS = 300  # 2000-01 .. 2024-12


class NetworkAccessed(AssertionError):
    pass


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any test in this module that tries to reach the network."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise NetworkAccessed("the engine must not use the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def test_the_network_guard_fires():
    # Proves the autouse guard works, so a pass below means no attempt was made.
    with pytest.raises(NetworkAccessed):
        socket.create_connection(("example.com", 80))
    with pytest.raises(NetworkAccessed):
        socket.socket().connect(("127.0.0.1", 9))


def synthetic_series(
    slope_per_decade: float,
    *,
    seed: int,
    noise: float = 0.4,
    missing: frozenset[int] = frozenset(),
    months: int = MONTHS,
) -> Series:
    """A repeating seasonal cycle, a constant slope and seeded noise."""
    rng = random.Random(seed)
    values: list[float | None] = []
    for i in range(months):
        seasonal = 8.0 * math.sin(2 * math.pi * (i % 12) / 12)
        trend = slope_per_decade * i / 120
        values.append(
            None
            if i in missing
            else round(290 + seasonal + trend + rng.gauss(0, noise), 3)
        )
    return Series(
        region_id="sahel",
        variable_id="temperature",
        period=Period(start="2000-01", end="2024-12"),
        units="K",
        values=tuple(values),
        quality=SeriesQuality(
            included=True,
            missing_fraction=len(missing) / months,
            valid_land_fraction=1.0,
        ),
        source=Source(provider="Synthetic", dataset="TEST", variable="t"),
        engine_version=engine.ENGINE_VERSION,
    )


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("slope", [0.35, -0.8, 0.0])
def test_interval_contains_the_constant_slope(slope: float, seed: int):
    trend = estimate_trend(synthetic_series(slope, seed=seed))

    low, high = trend.confidence_interval_95
    assert low <= slope <= high
    assert low <= trend.rate_per_decade <= high


def test_report_names_rate_units_direction_and_period():
    series = synthetic_series(0.5, seed=1)
    trend = estimate_trend(series)

    assert trend.rate_per_decade == pytest.approx(0.5, abs=0.15)
    assert trend.units_per_decade == "K/decade"
    assert trend.direction == "rising"
    assert (trend.region_id, trend.variable_id) == ("sahel", "temperature")
    assert trend.period == series.period
    assert trend.source == series.source
    assert trend.methods.least_squares.slope_per_decade == trend.rate_per_decade
    assert 0.3 < trend.methods.least_squares.r_squared < 0.9
    assert trend.methods.least_squares.p_value < 0.001


def test_falling_series_reports_falling():
    assert estimate_trend(synthetic_series(-0.8, seed=2)).direction == "falling"


def test_seasonal_cycle_does_not_leak_into_the_rate():
    # A strong cycle and no slope: without removing it the fit would pick up
    # whatever phase the series starts and ends on.
    trend = estimate_trend(synthetic_series(0.0, seed=3, noise=0.05, months=294))
    assert abs(trend.rate_per_decade) < 0.05


def test_missing_months_keep_the_calendar_aligned():
    series = synthetic_series(0.6, seed=4, missing=frozenset(range(40, 70)))
    low, high = estimate_trend(series).confidence_interval_95
    assert low <= 0.6 <= high


def test_autocorrelated_noise_widens_the_interval():
    white = estimate_trend(synthetic_series(0.3, seed=7))
    series = synthetic_series(0.3, seed=7)
    rng = random.Random(7)
    ar, shock = [], 0.0
    for _ in range(MONTHS):
        shock = 0.8 * shock + rng.gauss(0, 0.3)
        ar.append(shock)
    correlated = Series(
        **{
            **series.__dict__,
            "values": tuple(
                v + e
                for v, e in zip(series.values, ar, strict=True)  # type: ignore[operator]
            ),
        }
    )
    trend = estimate_trend(correlated)

    assert trend.autocorrelation.lag1 > 0.3
    assert trend.autocorrelation.effective_sample_size < MONTHS / 2
    assert (
        white.autocorrelation.effective_sample_size
        > trend.autocorrelation.effective_sample_size
    )


def test_trend_follows_the_trend_schema(validator_for):
    trend = estimate_trend(synthetic_series(0.35, seed=0))
    payload = as_dict(trend)
    payload["confidence_interval_95"] = list(payload["confidence_interval_95"])

    validator_for("trend.schema.json").validate(payload)


def _numbers(value: object):
    """Every number inside a contract value, however deeply it is nested."""
    if dataclasses.is_dataclass(value):
        for field in dataclasses.fields(value):
            yield from _numbers(getattr(value, field.name))
    elif isinstance(value, tuple | list):
        for item in value:
            yield from _numbers(item)
    elif not isinstance(value, str | None):
        yield value


# Contract: a Trend carries Python numbers only. A NumPy scalar is a float
# subclass, so it serializes, but its repr is "np.float64(0.5)" and it breaks any
# code that formats numbers with repr (the narrative text did).
def test_a_trend_carries_python_numbers_only():
    trend = estimate_trend(synthetic_series(0.35, seed=0))

    numbers = list(_numbers(trend))

    assert numbers  # the walk reached the rate and the interval
    assert {type(number) for number in numbers} <= {float, int, bool}


def test_a_lone_trend_is_not_yet_rated():
    trend = estimate_trend(synthetic_series(0.35, seed=0))
    assert trend.evidence_label == "Not enough evidence yet"
