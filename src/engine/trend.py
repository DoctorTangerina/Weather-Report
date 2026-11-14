"""Trend estimation and Evidence labels (ADR 0002).

Two seams, because the correction for many comparisons is a property of the
whole family of tests the engine runs and not of a single Trend:

- `estimate_trend` runs the fits for one series.
- `rate_evidence` sees every Trend at once, applies Benjamini-Hochberg across
  the family and settles each Evidence label.

A Trend returned by `estimate_trend` alone carries the conservative label
"Not enough evidence yet" until `rate_evidence` has judged the family.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy import stats

from .contracts import (
    NOT_ENOUGH_EVIDENCE,
    Autocorrelation,
    Fit,
    LeastSquaresFit,
    MannKendallTest,
    MultipleComparisons,
    OutlierCheck,
    Series,
    TheilSenFit,
    Trend,
    TrendMethods,
    direction_of,
)
from .version import ENGINE_VERSION

METHOD_CITATION = (
    "Time-series analysis of remotely sensed SeaWiFS chlorophyll in "
    "river-influenced coastal regions (see docs/challenge-brief.md)."
)

MONTHS_PER_DECADE = 120.0
SIGNIFICANCE = 0.05
# The family-wide correction belongs to `rate_evidence`; until it runs, a lone
# Trend carries this placeholder and is never called significant.
PLACEHOLDER_Q = 0.05
MIN_MONTHS = 36


def _month_index(month: str) -> int:
    year, number = month.split("-")
    return int(year) * 12 + int(number) - 1


def _deseasonalize(values: np.ndarray, calendar_month: np.ndarray) -> np.ndarray:
    """Subtract each calendar month's mean over the months that were observed."""
    anomalies = values.copy()
    for month in range(12):
        in_month = (calendar_month == month) & ~np.isnan(values)
        if in_month.any():
            anomalies[in_month] -= values[in_month].mean()
    return anomalies


def _huber_fit(t: np.ndarray, y: np.ndarray) -> Fit:
    """Robust regression: Huber's M-estimator by iteratively reweighted LS."""
    design = np.column_stack([np.ones_like(t), t])
    weights = np.ones_like(t)
    beta = np.linalg.lstsq(design, y, rcond=None)[0]
    for _ in range(50):
        residual = y - design @ beta
        scale = np.median(np.abs(residual - np.median(residual))) / 0.6745
        if scale == 0:
            break
        cutoff = 1.345 * scale
        weights = np.where(np.abs(residual) <= cutoff, 1.0, cutoff / np.abs(residual))
        root = np.sqrt(weights)
        updated = np.linalg.lstsq(design * root[:, None], y * root, rcond=None)[0]
        converged = np.allclose(updated, beta, atol=1e-10)
        beta = updated
        if converged:
            break
    root = np.sqrt(weights)
    weighted = design * root[:, None]
    residual = (y - design @ beta) * root
    dof = len(t) - 2
    sigma2 = float(residual @ residual) / dof
    covariance = sigma2 * np.linalg.inv(weighted.T @ weighted)
    statistic = beta[1] / np.sqrt(covariance[1, 1])
    p_value = 2 * stats.t.sf(abs(statistic), dof)
    return Fit(slope_per_decade=float(beta[1]), p_value=float(p_value))


def _lag1(residual: np.ndarray) -> float:
    centred = residual - residual.mean()
    denominator = float(centred @ centred)
    if denominator == 0:
        return 0.0
    return float(np.clip(centred[1:] @ centred[:-1] / denominator, -1.0, 1.0))


def estimate_trend(series: Series) -> Trend:
    """Rate of change per decade with a 95% interval (ADR 0002, primary fit).

    The seasonal cycle is removed by subtracting each calendar month's mean,
    then a least-squares line is fitted with its F-test and R². The interval
    is widened for lag-1 autocorrelation through an effective sample size.
    Missing months (None) stay in the calendar but out of every fit. The
    Evidence label is left at "Not enough evidence yet" for `rate_evidence`.
    """
    start = _month_index(series.period.start)
    raw = np.array([np.nan if v is None else v for v in series.values], dtype=float)
    index = np.arange(len(raw))
    observed = ~np.isnan(raw)
    if observed.sum() < MIN_MONTHS:
        raise ValueError(
            f"need at least {MIN_MONTHS} observed months to estimate a Trend, "
            f"got {int(observed.sum())}"
        )

    anomalies = _deseasonalize(raw, (start + index) % 12)
    t = index[observed] / MONTHS_PER_DECADE
    y = anomalies[observed]
    n = len(t)

    fit = stats.linregress(t, y)
    slope = float(fit.slope)
    residual = y - (fit.intercept + slope * t)

    lag1 = _lag1(residual)
    # Positive serial correlation shrinks the information in n months; negative
    # correlation is not allowed to claim more than n.
    n_eff = float(np.clip(n * (1 - lag1) / (1 + lag1), 3.0, n))
    standard_error = float(fit.stderr) * np.sqrt(n / n_eff)
    margin = float(stats.t.ppf(0.975, n_eff - 2)) * standard_error
    interval = (slope - margin, slope + margin)

    years = (start + index[observed]) // 12
    year_list = np.unique(years)
    annual = np.array([y[years == year].mean() for year in year_list])
    annual_fit = stats.linregress(year_list / 10.0, annual)

    theil = stats.theilslopes(y, t)
    tau = stats.kendalltau(t, y)

    worst = int(np.argmax(np.abs(residual)))
    kept = np.arange(n) != worst
    rerun = stats.linregress(t[kept], y[kept])
    removed = start + int(index[observed][worst])
    removed_month = f"{removed // 12:04d}-{removed % 12 + 1:02d}"

    methods = TrendMethods(
        least_squares=LeastSquaresFit(
            slope_per_decade=slope,
            p_value=float(fit.pvalue),
            r_squared=float(fit.rvalue**2),
        ),
        annual_anomaly=Fit(
            slope_per_decade=float(annual_fit.slope), p_value=float(annual_fit.pvalue)
        ),
        robust=_huber_fit(t, y),
        theil_sen=TheilSenFit(slope_per_decade=float(theil.slope)),
        mann_kendall=MannKendallTest(
            tau=float(tau.statistic), p_value=float(tau.pvalue)
        ),
        outlier_check=OutlierCheck(
            survives=bool(rerun.pvalue < SIGNIFICANCE),
            removed_month=removed_month,
            slope_per_decade=float(rerun.slope),
            p_value=float(rerun.pvalue),
        ),
    )
    return Trend(
        region_id=series.region_id,
        variable_id=series.variable_id,
        period=series.period,
        rate_per_decade=slope,
        units_per_decade=f"{series.units}/decade",
        confidence_interval_95=interval,
        direction=direction_of(slope),
        evidence_label=NOT_ENOUGH_EVIDENCE,
        methods=methods,
        multiple_comparisons=MultipleComparisons(
            q=PLACEHOLDER_Q,
            family_size=1,
            adjusted_p_value=float(fit.pvalue),
            significant=False,
        ),
        autocorrelation=Autocorrelation(lag1=lag1, effective_sample_size=n_eff),
        source=series.source,
        method_citation=METHOD_CITATION,
        engine_version=ENGINE_VERSION,
    )


def rate_evidence(trends: Sequence[Trend], q: float) -> list[Trend]:
    """Ticket #5. Returns the same Trends with their Evidence labels settled."""
    raise NotImplementedError("evidence labels: ticket #5")
