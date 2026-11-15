"""Shared Time-step vocabulary for data selection and manual processing."""

from collections.abc import Mapping
from datetime import UTC, datetime

_ALIASES = {
    alias: name
    for name in ("second", "minute", "hour", "day", "month", "year")
    for alias in (name, name + "s")
}
_ALIASES.update(
    {
        "3-hour": "3-hour",
        "3-hours": "3-hour",
        "3-hourly": "3-hour",
        "3h": "3-hour",
        "daily": "day",
        "monthly": "month",
        "hourly": "hour",
    }
)
_LABELS = {"3-hour": "3-hourly", "day": "daily", "month": "monthly"}


def normalize_time_step(value: object) -> str:
    """Canonical frequency; unknown labels are errors rather than inferred cadence."""
    if not isinstance(value, str) or value not in _ALIASES:
        raise ValueError(
            "Provide a supported Time step, such as 3-hourly, daily or monthly."
        )
    return _ALIASES[value]


def time_step_label(frequency: str) -> str:
    return _LABELS.get(frequency, frequency)


def series_time_step(series: Mapping) -> str | None:
    """Read new or legacy metadata and refuse contradictory declarations."""
    declared = [
        normalize_time_step(series[key])
        for key in ("time_step", "frequency")
        if key in series
    ]
    if declared and any(value != declared[0] for value in declared):
        raise ValueError("Time step conflicts with frequency metadata.")
    return declared[0] if declared else None


def utc_instant(timestamp: str) -> datetime:
    """Interpret ISO dates/times as UTC instants, keeping offset equivalence."""
    text = timestamp + "-01" if len(timestamp) == 7 else timestamp
    value = datetime.fromisoformat(text)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
