"""Mirrors: series of different Regions that move together month to month.

A Mirror is a correlation on the deseasonalized, detrended monthly series, so it
is neither a shared seasonal cycle nor a shared trend. It must be strong enough
to teach something (`MIRROR_MIN_CORRELATION`) and significant after the
Benjamini-Hochberg correction across every pair tested (ADR 0003).
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import combinations

import numpy as np
from scipy import stats

from .contracts import Mirror, Series, SeriesRef
from .quality import usable_series
from .trend import (
    FALSE_DISCOVERY_RATE,
    MIN_MONTHS,
    MONTHS_PER_DECADE,
    _deseasonalize,
    _lag1,
    _month_index,
)

# Weaker than this is not a Mirror however significant it is: with about 300
# months, significance alone accepts correlations too weak to teach anything.
MIRROR_MIN_CORRELATION = 0.3
# A series whose month-to-month residual varies less than this is flat: a
# correlation with it is rounding noise, not a signal.
FLAT = 1e-9


def find_mirrors(
    series: Sequence[Series], q: float = FALSE_DISCOVERY_RATE
) -> list[Mirror]:
    """Every pair of series from different Regions that is a Mirror (ADR 0003).

    Pairs of series from the same Region are not compared: a Mirror is evidence
    about two Regions. A pair is compared on the months both series observed, and
    only when that is at least `MIN_MONTHS`; a series that never varies has no
    correlation to test. The family for the Benjamini-Hochberg correction is every
    pair compared. Each Mirror lists its series in Region order. A series the
    quality gate excluded takes no part (BS-003).
    """
    series = usable_series(series)
    residuals = {_key(one): _residuals(one) for one in series}
    tested = []
    for a, b in combinations(sorted(series, key=_key), 2):
        if a.region_id == b.region_id:
            continue
        x, y = _common_months(residuals[_key(a)], residuals[_key(b)])
        if len(x) >= MIN_MONTHS and x.std() > FLAT and y.std() > FLAT:
            tested.append((a, b, float(np.corrcoef(x, y)[0, 1]), x, y))
    p_values = [_p_value(r, x, y) for _, _, r, x, y in tested]
    adjusted = stats.false_discovery_control(p_values, method="bh")
    return [
        Mirror(
            series=(
                SeriesRef(a.region_id, a.variable_id),
                SeriesRef(b.region_id, b.variable_id),
            ),
            correlation=r,
            p_value=p,
            adjusted_p_value=float(adjusted_p),
            significant_after_correction=True,
        )
        for (a, b, r, _, _), p, adjusted_p in zip(
            tested, p_values, adjusted, strict=True
        )
        if abs(r) >= MIRROR_MIN_CORRELATION and adjusted_p <= q
    ]


def _p_value(r: float, x: np.ndarray, y: np.ndarray) -> float:
    """Two-sided p-value of the correlation `r` under serial correlation.

    Months that remember their predecessors carry less information than months
    that do not, so the test uses an effective sample size (Bretherton et al.,
    1999) built from both series' lag-1 autocorrelation, as the Trend interval
    does (ADR 0002). Without it, two independent slow drifts look related.
    """
    n = len(x)
    product = _lag1(x) * _lag1(y)
    n_eff = float(np.clip(n * (1 - product) / (1 + product), 3.0, n))
    statistic = abs(r) * np.sqrt((n_eff - 2) / max(1 - r * r, 1e-12))
    return float(2 * stats.t.sf(statistic, n_eff - 2))


def _key(series: Series) -> tuple[str, str]:
    return series.region_id, series.variable_id


def _residuals(series: Series) -> dict[int, float]:
    """Month index -> what is left once the seasonal cycle and trend are removed.

    The seasonal cycle is each calendar month's mean over the observed months, as
    in `estimate_trend`; the trend is a least-squares line through what remains.
    Missing months (None) are left out.
    """
    start = _month_index(series.period.start)
    raw = np.array([np.nan if v is None else v for v in series.values], dtype=float)
    index = np.arange(len(raw))
    anomalies = _deseasonalize(raw, (start + index) % 12)
    observed = ~np.isnan(raw)
    t = index[observed] / MONTHS_PER_DECADE
    y = anomalies[observed]
    slope, intercept = np.polyfit(t, y, 1)
    detrended = y - (intercept + slope * t)
    return dict(
        zip((start + index[observed]).tolist(), detrended.tolist(), strict=True)
    )


def _common_months(
    first: dict[int, float], second: dict[int, float]
) -> tuple[np.ndarray, np.ndarray]:
    months = sorted(first.keys() & second.keys())
    return (
        np.array([first[m] for m in months]),
        np.array([second[m] for m in months]),
    )
