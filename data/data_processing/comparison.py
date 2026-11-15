"""Exploratory Pearson comparison of two series paired at exactly equal instants."""

import math
import statistics

MINIMUM_PAIRS = 3


def _rescaled(values):
    # Pearson's r ignores a positive scale factor, and scaling by a power of two is
    # exact. Without it, large finite values overflow inside the sums of squares and
    # statistics.correlation silently returns 0.0.
    exponent = math.frexp(max(abs(value) for value in values))[1]
    return [math.ldexp(value, -exponent) for value in values]


def pearson(names, inputs, instants):
    """Compare two validated inputs; nothing is filled, shifted or interpolated.

    Observations pair only where their instants are exactly equal. A pair is
    jointly valid when both values are present. Undefined correlations return an
    explanation instead of r rather than raising, so the sample stays visible.
    """
    first, second = names
    position = {instant: index for index, instant in enumerate(instants[second])}
    shared = [
        (index, position[instant])
        for index, instant in enumerate(instants[first])
        if instant in position
    ]
    columns = {}
    for name, side in ((first, 0), (second, 1)):
        series = inputs[name]
        flags = series.get("filled") or [False] * len(series["values"])
        columns[name] = {
            "values": [series["values"][pair[side]] for pair in shared],
            "filled": [flags[pair[side]] for pair in shared],
            "units": series["units"],
        }
    timestamps = [inputs[first]["timestamps"][index] for index, _ in shared]
    valid = [
        a is not None and b is not None
        for a, b in zip(columns[first]["values"], columns[second]["values"])
    ]
    pairs = [
        (a, b)
        for a, b, ok in zip(columns[first]["values"], columns[second]["values"], valid)
        if ok
    ]
    filled_pairs = sum(
        ok and (a or b)
        for a, b, ok in zip(columns[first]["filled"], columns[second]["filled"], valid)
    )
    analyzed = [stamp for stamp, ok in zip(timestamps, valid) if ok]
    r = None
    explanation = None
    if len(pairs) < MINIMUM_PAIRS:
        explanation = {
            "code": "insufficient_pairs",
            "message": (
                f"Pearson correlation needs at least {MINIMUM_PAIRS} jointly valid "
                f"pairs; {len(pairs)} remain."
            ),
            "required_pairs": MINIMUM_PAIRS,
        }
    else:
        a_values, b_values = (list(column) for column in zip(*pairs))
        constant = [
            name
            for name, column in ((first, a_values), (second, b_values))
            if min(column) == max(column)
        ]
        if constant:
            explanation = {
                "code": "constant_input",
                "message": (
                    "Pearson correlation is undefined because an input is constant "
                    "over the jointly valid pairs."
                ),
                "inputs": constant,
            }
        else:
            r = statistics.correlation(_rescaled(a_values), _rescaled(b_values))
            r = max(-1.0, min(1.0, r))
    return {
        "method": "pearson",
        "r": r,
        "valid_pairs": len(pairs),
        "filled_pairs": filled_pairs,
        "analyzed_period": {"start": analyzed[0], "end": analyzed[-1]}
        if analyzed
        else None,
        "overlap": {
            "start": timestamps[0],
            "end": timestamps[-1],
            "timestamps": len(timestamps),
        }
        if timestamps
        else None,
        "explanation": explanation,
        "sample": {"timestamps": timestamps, "valid": valid, "series": columns},
    }
