"""The quality gate's verdict on a series, as the engine honours it (BS-003).

The data layer decides whether a series has enough valid data and records the
verdict in `Series.quality`. The engine never second-guesses it and never reads
the values of a series the gate excluded, so no Trend, Mirror or Candidate
Discovery can rest on them.
"""

from __future__ import annotations

from collections.abc import Sequence

from .contracts import Series


def usable_series(series: Sequence[Series]) -> list[Series]:
    """The series that passed the gate, in their original order."""
    return [one for one in series if one.quality.included]


def require_usable(series: Series) -> None:
    """Refuse a series the gate excluded, naming why."""
    if not series.quality.included:
        reasons = ", ".join(series.quality.exclusions) or "no reason recorded"
        raise ValueError(
            f"the quality gate excluded {series.region_id} {series.variable_id}: "
            f"{reasons}"
        )
