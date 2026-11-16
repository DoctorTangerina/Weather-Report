"""How an area's grid cells, and then a Time step's values, become one value.

Spec #72 names seven Aggregations. Every one except minimum and maximum counts
each value in proportion to its weight, which for grid cells is the cell's
area; minimum and maximum ignore weights. Standard deviation is the population
standard deviation. Missing (masked or non-finite) values are left out together
with their weights.
"""

from __future__ import annotations

import numpy as np

AGGREGATIONS = (
    "mean",
    "median",
    "minimum",
    "maximum",
    "root_mean_square",
    "standard_deviation",
    "mean_absolute_value",
)


def combine(values, weights=None, aggregation: str = "mean") -> float | None:
    """One value from `values`, or None when nothing valid remains.

    `weights` defaults to equal weights and must broadcast to `values`.
    """
    if aggregation not in AGGREGATIONS:
        raise ValueError(f"Unknown Aggregation {aggregation!r}.")
    data = np.ma.masked_invalid(np.ma.asarray(values, dtype=float))
    keep = ~np.ma.getmaskarray(data)
    x = np.ma.getdata(data)[keep]
    if x.size == 0:
        return None
    if aggregation == "minimum":
        result = x.min()
    elif aggregation == "maximum":
        result = x.max()
    else:
        w = (
            np.ones(data.shape)
            if weights is None
            else np.broadcast_to(np.asarray(weights, dtype=float), data.shape)
        )[keep]
        if not w.sum() > 0:
            return None
        mean = np.average(x, weights=w)
        if aggregation == "mean":
            result = mean
        elif aggregation == "median":
            result = _weighted_median(x, w)
        elif aggregation == "root_mean_square":
            result = np.sqrt(np.average(x * x, weights=w))
        elif aggregation == "standard_deviation":
            result = np.sqrt(np.average((x - mean) ** 2, weights=w))
        else:
            result = np.average(np.abs(x), weights=w)
    return float(result) if np.isfinite(result) else None


def _weighted_median(x: np.ndarray, w: np.ndarray) -> float:
    """The value with half the weight on each side; the midpoint on a tie.

    With equal weights this is the ordinary median.
    """
    order = np.argsort(x, kind="stable")
    x, w = x[order], w[order]
    share = np.cumsum(w) / w.sum()
    index = int(np.searchsorted(share, 0.5))
    if index >= x.size:
        index = x.size - 1
    if np.isclose(share[index], 0.5) and index + 1 < x.size:
        return (x[index] + x[index + 1]) / 2
    if index > 0 and np.isclose(share[index - 1], 0.5):
        return (x[index - 1] + x[index]) / 2
    return x[index]
