"""Shared Time-step vocabulary for data selection and manual processing."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

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


def confirmed_timezones(series: Mapping) -> set[str]:
    """Zones a Series' Time-step boundaries were confirmed in; empty for legacy data.

    Acquired Explore My World Time steps follow UTC. A #48 resampling records the
    zone its buckets used, and later processing carries it in its provenance, so
    a prepared Derived series keeps its own local days and months.
    """
    resampling = series.get("resampling")
    if isinstance(resampling, Mapping) and isinstance(resampling.get("timezone"), str):
        return {resampling["timezone"]}
    provenance = series.get("provenance")
    zones = set()
    if isinstance(provenance, Mapping):
        for parent in provenance.values():
            if isinstance(parent, Mapping):
                zones |= confirmed_timezones(parent)
    if not zones and "time_step" in series:
        zones.add("UTC")
    return zones


def zone_message(zones: set[str]) -> str:
    if zones == {"UTC"}:
        return "Explore My World Time steps follow UTC."
    names = ", ".join(sorted(zones))
    return (
        f"This prepared series uses {names} days and months; "
        "choose that analysis time zone instead of changing them."
    )


def utc_instant(timestamp: str) -> datetime:
    """Interpret ISO dates/times as UTC instants, keeping offset equivalence."""
    text = timestamp + "-01" if len(timestamp) == 7 else timestamp
    value = datetime.fromisoformat(text)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def bucket_start(instant, frequency):
    if frequency == "second":
        return instant.replace(microsecond=0)
    if frequency == "minute":
        return instant.replace(second=0, microsecond=0)
    if frequency in ("hour", "3-hour"):
        hour = instant.hour if frequency == "hour" else (instant.hour // 3) * 3
        return instant.replace(hour=hour, minute=0, second=0, microsecond=0)
    if frequency == "day":
        return instant.replace(hour=0, minute=0, second=0, microsecond=0)
    if frequency == "month":
        return instant.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return instant.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)


def next_bucket(instant, frequency):
    if frequency in ("second", "minute", "hour", "3-hour"):
        seconds = {"second": 1, "minute": 60, "hour": 3600, "3-hour": 10800}[frequency]
        return (instant.astimezone(UTC) + timedelta(seconds=seconds)).astimezone(
            instant.tzinfo
        )
    if frequency == "day":
        return instant + timedelta(days=1)
    if frequency == "month":
        return instant.replace(
            year=instant.year + (instant.month == 12),
            month=1 if instant.month == 12 else instant.month + 1,
        )
    return instant.replace(year=instant.year + 1)
