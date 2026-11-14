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

from .contracts import Series, Trend


def estimate_trend(series: Series) -> Trend:
    """Ticket #4."""
    raise NotImplementedError("trend estimation: ticket #4")


def rate_evidence(trends: Sequence[Trend], q: float) -> list[Trend]:
    """Ticket #5. Returns the same Trends with their Evidence labels settled."""
    raise NotImplementedError("evidence labels: ticket #5")
