"""Synthetic monthly series and rated Trends shared by the engine tests."""

from __future__ import annotations

import math
import random

import engine
from engine import Period, Series, Trend, estimate_trend, rate_evidence
from engine.contracts import SeriesQuality, Source

MONTHS = 300  # 2000-01 .. 2024-12
Q = 0.05


def series_for(
    region_id: str,
    variable_id: str,
    slope_per_decade: float,
    *,
    seed: int,
    noise: float = 0.4,
) -> Series:
    """A repeating seasonal cycle, a constant slope and seeded noise."""
    rng = random.Random(seed)
    values = [
        round(
            290
            + 8.0 * math.sin(2 * math.pi * (i % 12) / 12)
            + slope_per_decade * i / 120
            + rng.gauss(0, noise),
            3,
        )
        for i in range(MONTHS)
    ]
    return Series(
        region_id=region_id,
        variable_id=variable_id,
        period=Period(start="2000-01", end="2024-12"),
        units="K",
        values=tuple(values),
        quality=SeriesQuality(
            included=True, missing_fraction=0.0, valid_land_fraction=1.0
        ),
        source=Source(provider="Synthetic", dataset="TEST", variable="t"),
        engine_version=engine.ENGINE_VERSION,
    )


def rated_trends(
    slopes: dict[tuple[str, str], float], *, filler: int = 6, noise: float = 0.4
) -> list[Trend]:
    """One rated Trend per (region, variable), among `filler` flat comparisons.

    The flat filler series stand for the many other tests the engine runs, so the
    correction for many comparisons is real; they are not returned.
    """
    trends = [
        estimate_trend(series_for(region, variable, slope, seed=index, noise=noise))
        for index, ((region, variable), slope) in enumerate(slopes.items())
    ]
    flat = [
        estimate_trend(series_for("filler", f"flat-{seed}", 0.0, seed=100 + seed))
        for seed in range(filler)
    ]
    return rate_evidence([*trends, *flat], q=Q)[: len(trends)]


def driver_signal(seed: int, months: int = MONTHS) -> list[float]:
    """A unit-variance monthly signal that several series can share."""
    rng = random.Random(seed)
    return [rng.gauss(0, 1) for _ in range(months)]


def _month_label(index: int) -> str:
    return f"{2000 + index // 12:04d}-{index % 12 + 1:02d}"


def driven_series(
    region_id: str,
    variable_id: str,
    driver: list[float],
    *,
    weight: float,
    seed: int,
    noise: float = 0.5,
    slope_per_decade: float = 0.0,
    first_month: int = 0,
    months: int | None = None,
    constant: bool = False,
) -> Series:
    """A seasonal cycle, a slope, `weight` times a shared driver and own noise.

    The series covers `months` months from `first_month` (counted from 2000-01),
    and takes the driver's value for each calendar month, so two series that
    overlap on only some months share the driver exactly there. `constant`
    gives a series that never changes.
    """
    months = len(driver) - first_month if months is None else months
    rng = random.Random(seed)
    values = [
        290.0
        if constant
        else round(
            290
            + 8.0 * math.sin(2 * math.pi * ((first_month + i) % 12) / 12)
            + slope_per_decade * i / 120
            + weight * driver[first_month + i]
            + rng.gauss(0, noise),
            3,
        )
        for i in range(months)
    ]
    return Series(
        region_id=region_id,
        variable_id=variable_id,
        period=Period(
            start=_month_label(first_month), end=_month_label(first_month + months - 1)
        ),
        units="K",
        values=tuple(values),
        quality=SeriesQuality(
            included=True, missing_fraction=0.0, valid_land_fraction=1.0
        ),
        source=Source(provider="Synthetic", dataset="TEST", variable="t"),
        engine_version=engine.ENGINE_VERSION,
    )


def persistent_signal(seed: int, phi: float = 0.9, months: int = MONTHS) -> list[float]:
    """A monthly signal that remembers its last month, as slow climate drifts do."""
    rng = random.Random(seed)
    value, signal = 0.0, []
    for _ in range(months):
        value = phi * value + rng.gauss(0, 1)
        signal.append(value)
    return signal
