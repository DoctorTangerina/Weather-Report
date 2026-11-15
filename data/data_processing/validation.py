"""Shared validation of loaded Source/Derived series at data-method boundaries."""

import math
from collections.abc import Mapping
from datetime import UTC, datetime
from itertools import pairwise

from .errors import ProcessingError


def finite_number(value) -> bool:
    try:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )
    except OverflowError:
        return False


def validate_series(series: Mapping, name: str) -> list:
    timestamps, values = series.get("timestamps"), series.get("values")
    if (
        not isinstance(timestamps, list)
        or not timestamps
        or not all(isinstance(t, str) and t for t in timestamps)
        or not isinstance(values, list)
        or len(timestamps) != len(values)
        or any(v is not None and not finite_number(v) for v in values)
        or not isinstance(series.get("units"), str)
        or not series["units"].strip()
    ):
        raise ProcessingError(
            "invalid_series",
            "Provide timestamps, finite values/nulls and units.",
            input=name,
        )
    flags = series.get("filled")
    if "filled" in series and (
        not isinstance(flags, list)
        or len(flags) != len(values)
        or any(
            not isinstance(flag, bool) or (flag and value is None)
            for flag, value in zip(flags, values)
        )
    ):
        raise ProcessingError(
            "invalid_series", "Filled flags must match the observations.", input=name
        )
    quality = series.get("quality")
    if quality is not None and (
        not isinstance(quality, Mapping) or quality.get("included") is not True
    ):
        raise ProcessingError(
            "excluded_series",
            "An input failed the source Quality gate.",
            input=name,
        )
    calendar = series.get("calendar", "standard")
    if not isinstance(calendar, str):
        raise ProcessingError(
            "invalid_series", "Calendar must be a string.", input=name
        )
    try:
        if calendar in ("standard", "gregorian", "proleptic_gregorian"):
            instants = []
            for stamp in timestamps:
                text = stamp + "-01" if len(stamp) == 7 else stamp
                value = datetime.fromisoformat(text)
                instants.append(
                    value.replace(tzinfo=UTC)
                    if value.tzinfo is None
                    else value.astimezone(UTC)
                )
        else:
            instants = timestamps
        if any(a >= b for a, b in pairwise(instants)):
            raise ValueError
    except (ValueError, OverflowError):
        raise ProcessingError(
            "invalid_timestamps",
            "Use ordered, distinct timestamps.",
            input=name,
        ) from None
    return instants
