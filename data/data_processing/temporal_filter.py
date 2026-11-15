"""Explicit inclusion/exclusion of observations by local temporal conditions."""

import copy
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..time_steps import series_time_step, time_step_label
from .errors import ProcessingError

_MODES = ("include", "exclude")
_ORDER = {
    name: index
    for index, name in enumerate(
        ("second", "minute", "hour", "3-hour", "day", "month", "year")
    )
}
_WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


def _clock(value, field):
    try:
        if not isinstance(value, str) or len(value) != 5:
            raise ValueError
        return time.fromisoformat(value)
    except ValueError:
        raise ProcessingError(
            "invalid_filter", f"Give the {field} time of day as HH:MM.", field=field
        ) from None


def _hours(window):
    if not isinstance(window, dict) or set(window) != {"start", "end"}:
        raise ProcessingError(
            "invalid_filter", "Give hours as {start: HH:MM, end: HH:MM}."
        )
    start, end = _clock(window["start"], "start"), _clock(window["end"], "end")
    if start == end:
        raise ProcessingError(
            "invalid_filter", "A time-of-day window needs different start and end."
        )
    # [start, end); a window whose end precedes its start runs over midnight.
    if start < end:
        return lambda local: start <= local.time() < end
    return lambda local: local.time() >= start or local.time() < end


def _weekdays(names):
    if (
        not isinstance(names, list)
        or not names
        or any(not isinstance(name, str) or name not in _WEEKDAYS for name in names)
    ):
        raise ProcessingError(
            "invalid_filter", "Give weekdays as names such as monday or sunday."
        )
    chosen = {_WEEKDAYS.index(name) for name in names}
    return lambda local: local.weekday() in chosen


def _months(numbers):
    if (
        not isinstance(numbers, list)
        or not numbers
        or any(type(number) is not int or not 1 <= number <= 12 for number in numbers)
    ):
        raise ProcessingError(
            "invalid_filter", "Give months as numbers from 1 (January) to 12."
        )
    chosen = set(numbers)
    return lambda local: local.month in chosen


def _dates(window):
    if not isinstance(window, dict) or set(window) != {"start", "end"}:
        raise ProcessingError(
            "invalid_filter", "Give dates as {start: YYYY-MM-DD, end: YYYY-MM-DD}."
        )
    try:
        if not all(isinstance(window[key], str) for key in ("start", "end")):
            raise ValueError
        start, end = (
            date.fromisoformat(window["start"]),
            date.fromisoformat(window["end"]),
        )
    except ValueError:
        raise ProcessingError(
            "invalid_filter", "Give dates as {start: YYYY-MM-DD, end: YYYY-MM-DD}."
        ) from None
    if start > end:
        raise ProcessingError(
            "invalid_filter", "A date window's start must not follow its end."
        )
    # Both dates are inside the window, whole days included.
    return lambda local: start <= local.date() <= end


def filter_series(series, instants, parameters):
    """Keep or drop observations matching every requested condition.

    ``instants`` are the validated UTC instants of ``series``. Timestamps keep
    their input labels, so retained observations keep their UTC identity.
    """
    mode = parameters.get("mode")
    if mode not in _MODES:
        raise ProcessingError(
            "invalid_filter", "Choose mode include or exclude explicitly."
        )
    zone_name = parameters.get("timezone")
    zone = None
    if isinstance(zone_name, str):
        try:
            zone = ZoneInfo(zone_name)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    if zone is None:
        raise ProcessingError(
            "invalid_timezone",
            "Confirm the input's IANA time zone, such as UTC or America/Sao_Paulo.",
        )
    if not all(isinstance(instant, datetime) for instant in instants):
        raise ProcessingError(
            "unsupported_calendar",
            "Temporal filters currently require a Gregorian calendar.",
        )
    conditions = []
    step = series_time_step(series)
    if step is None:
        raise ProcessingError(
            "unknown_time_step",
            "Declare the input's Time step; a filter cannot tell which temporal "
            "detail the observations record without it.",
        )
    for key, build, coarsest in (
        ("hours", _hours, "3-hour"),
        ("weekdays", _weekdays, "day"),
        ("months", _months, "month"),
        ("dates", _dates, "day"),
    ):
        if key not in parameters:
            continue
        if _ORDER[step] > _ORDER[coarsest]:
            label = time_step_label(step)
            raise ProcessingError(
                "unsupported_temporal_resolution",
                f"A {label} input cannot support a {key} filter: its Time step "
                "does not record that temporal detail.",
                time_step=label,
                filter=key,
            )
        conditions.append(build(parameters[key]))
    if not conditions:
        raise ProcessingError(
            "invalid_filter",
            "Choose at least one of hours, weekdays, months or dates.",
        )
    # Daily and monthly Time steps are UTC days and months, so their calendar
    # is the UTC label; only sub-daily observations are read in the local zone.
    reading = zone if _ORDER[step] < _ORDER["day"] else UTC
    keep = []
    for index, instant in enumerate(instants):
        local = instant.astimezone(reading)
        matches = all(condition(local) for condition in conditions)
        if matches == (mode == "include"):
            keep.append(index)
    timestamps = series["timestamps"]
    kept = set(keep)
    filled = series.get("filled", [False] * len(timestamps))
    return {
        "timestamps": [timestamps[i] for i in keep],
        "values": [series["values"][i] for i in keep],
        "filled": [filled[i] for i in keep],
        "temporal_filter": {
            "mode": mode,
            "timezone": zone_name,
            "read_in": "UTC" if reading is UTC else zone_name,
            **{
                key: copy.deepcopy(parameters[key])
                for key in ("hours", "weekdays", "months", "dates")
                if key in parameters
            },
            "excluded_timestamps": [
                stamp for i, stamp in enumerate(timestamps) if i not in kept
            ],
        },
    }
