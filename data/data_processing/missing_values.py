"""Explicit missing-value policies and per-timestamp restoration."""

import math
import statistics
from collections.abc import Mapping
from datetime import datetime
from itertools import pairwise

from .errors import ProcessingError

_POLICIES = {
    "remove": "remove",
    "zero": "zero",
    "mean": "mean",
    "average": "mean",
    "min": "min",
    "minimum": "min",
    "max": "max",
    "maximum": "max",
    "custom": "custom",
    "interpolate": "interpolate",
    "interpolation": "interpolate",
}


def _finite(value):
    try:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )
    except OverflowError:
        return False


def manage_missing(series, instants, parameters):
    """Return new values, timestamps and fill flags for a validated input.

    Choose either a common policy or a mapping of exact input timestamp labels to
    replacement values. Combining the two is explicit through separate steps.
    """
    values = list(series["values"])
    timestamps = list(series["timestamps"])
    filled = list(series.get("filled", [False] * len(values)))
    original_missing = [i for i, value in enumerate(values) if value is None]
    removed = []
    if "replacements" in parameters:
        if set(parameters) != {"replacements"} or not isinstance(
            parameters["replacements"], Mapping
        ):
            raise ProcessingError(
                "invalid_missing_parameters",
                "Use either replacements or a common policy, not both.",
            )
        lookup = {stamp: index for index, stamp in enumerate(timestamps)}
        for stamp, value in parameters["replacements"].items():
            if not isinstance(stamp, str) or stamp not in lookup:
                raise ProcessingError(
                    "unknown_timestamp",
                    "Replacement timestamp does not exist in the input.",
                    timestamp=stamp,
                )
            index = lookup[stamp]
            if values[index] is not None:
                raise ProcessingError(
                    "not_missing",
                    "Individual replacements may only restore missing observations.",
                    timestamp=stamp,
                )
            if not _finite(value):
                raise ProcessingError(
                    "invalid_replacement",
                    "Provide a finite numeric replacement.",
                    timestamp=stamp,
                )
            values[index] = float(value)
            filled[index] = True
        policy = "individual"
    else:
        requested = parameters.get("policy")
        policy = _POLICIES.get(requested) if isinstance(requested, str) else None
        if policy is None:
            raise ProcessingError(
                "invalid_missing_policy",
                "Choose remove, zero, mean, min, max, custom or interpolation.",
            )
        allowed = {"policy"}
        if policy == "custom":
            allowed.add("value")
        if policy == "interpolate":
            allowed.add("max_gap_seconds")
        if set(parameters) - allowed:
            raise ProcessingError(
                "invalid_missing_parameters",
                "Unexpected parameters for this missing-value policy.",
            )
        valid = [value for value in values if value is not None]
        if policy == "remove":
            removed = [timestamps[i] for i in original_missing]
        elif policy == "interpolate":
            gap = parameters.get("max_gap_seconds")
            if not _finite(gap) or gap <= 0:
                raise ProcessingError(
                    "invalid_max_gap",
                    "Provide a positive finite max_gap_seconds for interpolation.",
                )
            if not all(isinstance(value, datetime) for value in instants):
                raise ProcessingError(
                    "unsupported_calendar",
                    "Elapsed-time interpolation requires a Gregorian calendar.",
                )
            anchors = [i for i, value in enumerate(values) if value is not None]
            for left, right in pairwise(anchors):
                duration = (instants[right] - instants[left]).total_seconds()
                if duration > gap:
                    continue
                for index in range(left + 1, right):
                    weight = (
                        instants[index] - instants[left]
                    ).total_seconds() / duration
                    value = (1 - weight) * values[left] + weight * values[right]
                    if not _finite(value):
                        raise ProcessingError(
                            "nonfinite_result",
                            "Interpolation produced a nonfinite value.",
                            timestamp=timestamps[index],
                        )
                    values[index] = float(value)
                    filled[index] = True
        else:
            if policy in ("mean", "min", "max"):
                if not valid:
                    raise ProcessingError(
                        "no_valid_values",
                        "No valid observations exist to calculate the requested statistic.",
                    )
                replacement = {"mean": statistics.mean, "min": min, "max": max}[policy](
                    valid
                )
            elif policy == "custom":
                replacement = parameters.get("value")
                if not _finite(replacement):
                    raise ProcessingError(
                        "invalid_replacement", "Provide a finite numeric custom value."
                    )
            else:
                replacement = 0.0
            for index in original_missing:
                values[index] = float(replacement)
                filled[index] = True
    newly_filled = [timestamps[i] for i in original_missing if values[i] is not None]
    keep = [
        i for i, value in enumerate(values) if policy != "remove" or value is not None
    ]
    return {
        "timestamps": [timestamps[i] for i in keep],
        "values": [values[i] for i in keep],
        "filled": [filled[i] for i in keep],
        "missing_values": {
            "policy": policy,
            "filled_timestamps": newly_filled,
            "removed_timestamps": removed,
        },
    }
