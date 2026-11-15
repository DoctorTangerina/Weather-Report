"""Explicit least-squares removal of linear change in elapsed UTC time."""

import math
import statistics
from datetime import datetime

from .errors import ProcessingError


def detrend_values(values, instants, preserve_mean):
    """Fit the immediate input and subtract the fitted linear change."""
    if not all(isinstance(instant, datetime) for instant in instants):
        raise ProcessingError(
            "unsupported_calendar", "Linear detrending requires a Gregorian calendar."
        )
    valid = [
        (instant, value)
        for instant, value in zip(instants, values)
        if value is not None
    ]
    if len(valid) < 2:
        raise ProcessingError(
            "insufficient_observations",
            "Linear detrending requires at least two valid observations at distinct timestamps.",
        )
    start = valid[0][0]
    span = (valid[-1][0] - start).total_seconds()
    elapsed = [(instant - start).total_seconds() / span for instant, _ in valid]
    # A power-of-two scale is exact and bounds sums/products even for finite
    # extremes. Subtract the baseline before averaging to keep small variation.
    exponent = math.frexp(max(abs(value) for _, value in valid))[1]
    scaled = [math.ldexp(value, -exponent) for _, value in valid]
    baseline = scaled[0]
    differences = [value - baseline for value in scaled]
    mean_time = statistics.fmean(elapsed)
    mean_value = statistics.fmean(differences)
    centered = [time - mean_time for time in elapsed]
    slope = math.fsum(
        x * (y - mean_value) for x, y in zip(centered, differences)
    ) / math.fsum(x * x for x in centered)
    try:
        transformed = [
            math.ldexp(
                (value - mean_value)
                - slope * time
                + (baseline + mean_value if preserve_mean else 0),
                exponent,
            )
            for value, time in zip(differences, centered)
        ]
        if not all(math.isfinite(value) for value in transformed):
            raise OverflowError
    except OverflowError:
        raise ProcessingError(
            "nonfinite_result",
            "Linear detrending produced an unrepresentable nonfinite value.",
        ) from None
    iterator = iter(transformed)
    return [None if value is None else next(iterator) for value in values]
