"""Min–Max and Z-score calculations, preserving missing observations."""

import math
import statistics

from .errors import ProcessingError


def scale_values(values, method, ddof, output_range=(0.0, 1.0)):
    """Scale validated observations; instruction validation belongs to the caller."""
    if method == "minmax":
        try:
            if (
                not isinstance(output_range, (list, tuple))
                or len(output_range) != 2
                or any(
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    for value in output_range
                )
                or output_range[0] >= output_range[1]
            ):
                raise ValueError
        except (ValueError, OverflowError):
            raise ProcessingError(
                "invalid_scaling_range",
                "Provide two finite numeric bounds with lower < upper.",
            ) from None
    valid = [value for value in values if value is not None]
    if not valid:
        raise ProcessingError(
            "no_valid_values", "Scaling requires at least one valid observation."
        )
    lower, upper = min(valid), max(valid)
    if lower == upper:
        raise ProcessingError(
            "constant_input", "Scaling is undefined because the input is constant."
        )
    span = upper - lower
    try:
        finite_span = math.isfinite(span)
    except OverflowError:
        finite_span = False
    if finite_span:
        # Subtract before scaling to retain small differences on a large baseline.
        normalized = [(value - lower) / span for value in valid]
    else:
        # Opposite-sign finite extremes can have an infinite unscaled range.
        magnitude = max(abs(lower), abs(upper))
        normalized = [value / magnitude for value in valid]
        lower, upper = min(normalized), max(normalized)
        normalized = [(value - lower) / (upper - lower) for value in normalized]
    if method == "minmax":
        target_lower, target_upper = output_range
        # Interpolate without overflowing target_upper - target_lower.
        transformed = [
            (1 - value) * target_lower + value * target_upper for value in normalized
        ]
    else:
        mean = statistics.fmean(normalized)
        deviation = (
            statistics.pstdev(normalized) if ddof == 0 else statistics.stdev(normalized)
        )
        transformed = [(value - mean) / deviation for value in normalized]
    iterator = iter(transformed)
    return [None if value is None else next(iterator) for value in values]
