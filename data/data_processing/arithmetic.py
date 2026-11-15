"""Execute declarative arithmetic recipes without HTTP or engine dependencies."""

import ast
import copy
import keyword
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from ..time_steps import series_time_step, time_step_label
from .comparison import pearson
from .detrending import detrend_values
from .errors import ProcessingError
from .missing_values import manage_missing
from .resampling import resample_series
from .scaling import scale_values
from .temporal_filter import filter_series
from .units import compound, conversion, is_rate
from .validation import finite_number as _number
from .validation import validate_series as _timeline


def _name(value) -> bool:
    return (
        isinstance(value, str) and value.isidentifier() and not keyword.iskeyword(value)
    )


def _parse(expression: str) -> ast.Expression:
    if not isinstance(expression, str) or not expression.strip():
        raise ProcessingError("invalid_expression", "Provide an arithmetic expression.")
    try:
        tree = ast.parse(expression, mode="eval")
        for node in ast.walk(tree):
            if not isinstance(
                node,
                (
                    ast.Expression,
                    ast.BinOp,
                    ast.UnaryOp,
                    ast.Name,
                    ast.Load,
                    ast.Constant,
                    ast.Add,
                    ast.Sub,
                    ast.Mult,
                    ast.Div,
                    ast.UAdd,
                    ast.USub,
                ),
            ):
                raise TypeError
            if isinstance(node, ast.Constant) and not _number(node.value):
                raise ValueError
    except (SyntaxError, TypeError, ValueError, RecursionError):
        raise ProcessingError(
            "invalid_expression",
            "Use named inputs, finite numeric constants, parentheses and +, -, *, /.",
        ) from None
    return tree


def preview_expression(expression: str) -> dict:
    """Validate without executing; retain the expression's explicit parentheses."""
    tree = _parse(expression)
    inputs, constants = [], []

    def visit(node):
        if isinstance(node, ast.Name) and node.id not in inputs:
            inputs.append(node.id)
        if isinstance(node, ast.Constant):
            constants.append(node.value)
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    return {"expression": expression, "inputs": inputs, "constants": constants}


@dataclass
class _Value:
    values: list
    units: str
    scalar: bool = False


def _evaluate(node, inputs, length, timestamps, acknowledged, warnings):
    if isinstance(node, ast.Name):
        return _Value(inputs[node.id]["values"], inputs[node.id]["units"])
    if isinstance(node, ast.Constant):
        return _Value([float(cast(int | float, node.value))] * length, "1", scalar=True)
    if isinstance(node, ast.UnaryOp):
        value = _evaluate(
            node.operand, inputs, length, timestamps, acknowledged, warnings
        )
        sign = -1 if isinstance(node.op, ast.USub) else 1
        return _Value(
            [None if v is None else sign * v for v in value.values],
            value.units,
            value.scalar,
        )
    left = _evaluate(node.left, inputs, length, timestamps, acknowledged, warnings)
    right = _evaluate(node.right, inputs, length, timestamps, acknowledged, warnings)
    divide = isinstance(node.op, ast.Div)
    if divide:
        zeroes = [t for t, v in zip(timestamps, right.values) if v == 0]
        if zeroes:
            raise ProcessingError(
                "zero_denominator",
                "Add a constant or explicitly remove zero denominators before dividing.",
                timestamps=zeroes,
            )
    if isinstance(node.op, (ast.Add, ast.Sub)):
        # An explicit numeric constant is an offset in the other operand's units.
        units = right.units if left.scalar else left.units
        if not left.scalar and not right.scalar and left.units != right.units:
            transform = conversion(right.units, left.units)
            warning = {
                "code": "unit_difference",
                "left": left.units,
                "right": right.units,
                "conversion": None
                if transform is None
                else {
                    "from": right.units,
                    "to": left.units,
                    "factor": transform[0],
                    "offset": transform[1],
                },
            }
            if not acknowledged:
                raise ProcessingError(
                    "unit_confirmation_required",
                    "Units differ; acknowledge the warning to continue.",
                    warning=warning,
                )
            warnings.append(warning)
            if transform is None:
                operator = "+" if isinstance(node.op, ast.Add) else "-"
                units = f"Mixed units: {left.units} {operator} {right.units}"
            else:
                factor, offset = transform
                right.values = [
                    None if v is None else v * factor + offset for v in right.values
                ]
        operation = (
            (lambda a, b: a + b) if isinstance(node.op, ast.Add) else lambda a, b: a - b
        )
    else:
        units = compound(left.units, right.units, divide=divide)
        operation = (lambda a, b: a / b) if divide else lambda a, b: a * b
    values: list[float | None] = []
    for timestamp, a, b in zip(timestamps, left.values, right.values):
        if a is None or b is None:
            values.append(None)
            continue
        try:
            value = operation(a, b)
            if not math.isfinite(value):
                raise OverflowError
        except (OverflowError, ZeroDivisionError):
            raise ProcessingError(
                "nonfinite_result",
                "Arithmetic produced a nonfinite value.",
                timestamp=timestamp,
            ) from None
        values.append(float(value))
    return _Value(values, units, left.scalar and right.scalar)


def process_series(request: Mapping) -> dict:
    """Execute {series: {name: payload}, operations: [{id, expression, ...}]}.

    Each output id becomes a named input for subsequent operations. Inputs must
    share timestamps/calendar for arithmetic; explicit resampling can prepare them.
    Results and recipes are JSON-compatible and no supplied object is modified.
    """
    if not isinstance(request, Mapping):
        raise ProcessingError("invalid_request", "Provide named series and operations.")
    sources, steps = request.get("series"), request.get("operations")
    if (
        not isinstance(sources, Mapping)
        or not sources
        or not all(_name(k) and isinstance(v, Mapping) for k, v in sources.items())
        or not isinstance(steps, Sequence)
        or isinstance(steps, (str, bytes))
        or not steps
    ):
        raise ProcessingError("invalid_request", "Provide named series and operations.")
    available = copy.deepcopy(dict(sources))
    outputs: dict[str, dict] = {}
    comparisons: dict[str, dict] = {}
    recipe: list[dict] = []
    warnings: list[dict] = []
    for index, step in enumerate(steps):
        if (
            not isinstance(step, Mapping)
            or not _name(step.get("id"))
            or step["id"] in available
            or step["id"] in comparisons
        ):
            raise ProcessingError(
                "invalid_operation",
                "Use a new output id and supported parameters.",
                operation=index,
            )
        method = step.get("operation", "arithmetic")
        if method not in (
            "arithmetic",
            "minmax",
            "zscore",
            "resample",
            "missing",
            "filter",
            "pearson",
            "detrend",
        ):
            raise ProcessingError(
                "invalid_operation", "Unsupported operation.", operation=index
            )
        allowed = (
            {"id", "operation", "expression", "acknowledge_unit_difference"}
            if method == "arithmetic"
            else {"id", "operation", "input", "ddof"}
        )
        if method == "pearson":
            allowed = {"id", "operation", "inputs"}
        if method == "detrend":
            allowed = {"id", "operation", "input", "preserve_mean"}
        if method == "resample":
            allowed = {
                "id",
                "operation",
                "input",
                "source_frequency",
                "frequency",
                "aggregation",
                "timezone",
            }
        if method == "missing":
            allowed = {
                "id",
                "operation",
                "input",
                "policy",
                "value",
                "replacements",
                "max_gap_seconds",
            }
        if method == "filter":
            allowed = {
                "id",
                "operation",
                "input",
                "timezone",
                "mode",
                "hours",
                "weekdays",
                "months",
                "dates",
            }
        if method == "minmax":
            allowed.add("range")
        if set(step) - allowed:
            raise ProcessingError(
                "invalid_operation",
                "Unsupported operation parameters.",
                operation=index,
            )
        if method == "detrend" and not isinstance(step.get("preserve_mean"), bool):
            raise ProcessingError(
                "invalid_detrending_parameters",
                "Choose preserve_mean=true or false explicitly for linear detrending.",
                operation=index,
            )
        expression = None
        if method == "arithmetic":
            if not isinstance(step.get("acknowledge_unit_difference", False), bool):
                raise ProcessingError(
                    "invalid_operation",
                    "Acknowledgement must be boolean.",
                    operation=index,
                )
            expression = step.get("expression")
            if not isinstance(expression, str):
                raise ProcessingError(
                    "invalid_expression", "Provide an arithmetic expression."
                )
            tree = _parse(expression)
            names = preview_expression(expression)["inputs"]
            if not names:
                raise ProcessingError(
                    "invalid_expression", "Reference at least one series."
                )
        elif method == "pearson":
            names = step.get("inputs")
            if (
                not isinstance(names, list)
                or len(names) != 2
                or not all(_name(name) for name in names)
                or names[0] == names[1]
            ):
                raise ProcessingError(
                    "invalid_operation",
                    "A comparison requires two different named inputs.",
                    operation=index,
                )
            names = list(names)
        else:
            if not _name(step.get("input")):
                raise ProcessingError(
                    "invalid_operation",
                    "This operation requires one named input.",
                    operation=index,
                )
            if method == "minmax" and "ddof" in step:
                raise ProcessingError(
                    "invalid_operation",
                    "ddof applies only to Z-score scaling.",
                    operation=index,
                )
            if method == "zscore" and (
                type(step.get("ddof")) is not int or step["ddof"] not in (0, 1)
            ):
                raise ProcessingError(
                    "invalid_scaling_parameters",
                    "Choose ddof=0 (population) or ddof=1 (sample) for Z-score scaling.",
                    operation=index,
                )
            names = [step["input"]]
        missing = [name for name in names if name not in available]
        if missing:
            raise ProcessingError(
                "unknown_input", "Unknown series reference.", inputs=missing
            )
        used = {name: available[name] for name in names}
        timelines = {name: _timeline(series, name) for name, series in used.items()}
        first = used[names[0]]
        try:
            declared_steps = {
                name: series_time_step(series) for name, series in used.items()
            }
        except ValueError as error:
            raise ProcessingError("invalid_time_step", str(error)) from None
        known_steps = {value for value in declared_steps.values() if value is not None}
        if len(known_steps) > 1:
            raise ProcessingError(
                "unaligned_series",
                "Inputs have different Time steps; explicitly resample to a common Time step first.",
                inputs=names,
            )
        calendar = first.get("calendar", "standard")
        if any(
            # A comparison pairs only exactly equal instants, so its inputs may
            # cover different periods; everything else needs identical timelines.
            (method != "pearson" and timelines[name] != timelines[names[0]])
            or used[name].get("calendar", "standard") != calendar
            for name in names
        ):
            raise ProcessingError(
                "unaligned_series",
                "Explicitly align/resample these inputs first.",
                inputs=names,
            )
        # Metadata snapshots preserve source quality and previous processing history.
        provenance = {
            name: {
                key: copy.deepcopy(value)
                for key, value in series.items()
                if key not in ("values", "timestamps")
            }
            for name, series in used.items()
        }
        if method == "pearson":
            recipe.append(copy.deepcopy(dict(step)))
            comparisons[step["id"]] = {
                "id": step["id"],
                **copy.deepcopy(pearson(names, used, timelines)),
                "calendar": calendar,
                "inputs": names,
                "provenance": provenance,
                "recipe": {"operations": copy.deepcopy(recipe)},
                "warnings": [],
            }
            continue
        step_warnings: list[dict] = []
        resampled = None
        managed = None
        if method == "arithmetic":
            result = _evaluate(
                tree.body,
                used,
                len(first["timestamps"]),
                first["timestamps"],
                step.get("acknowledge_unit_difference", False),
                step_warnings,
            )
        elif method == "detrend":
            result = _Value(
                detrend_values(
                    first["values"], timelines[names[0]], step.get("preserve_mean")
                ),
                first["units"],
            )
        elif method == "missing":
            managed = manage_missing(
                first,
                timelines[names[0]],
                {
                    key: value
                    for key, value in step.items()
                    if key not in ("id", "operation", "input")
                },
            )
            result = _Value(managed["values"], first["units"])
        elif method == "filter":
            managed = filter_series(
                first,
                timelines[names[0]],
                {
                    key: value
                    for key, value in step.items()
                    if key not in ("id", "operation", "input")
                },
            )
            result = _Value(managed["values"], first["units"])
        elif method == "resample":
            resampled = resample_series(
                first,
                source_frequency=step.get("source_frequency", first.get("frequency")),
                frequency=step.get("frequency"),
                aggregation=step.get("aggregation"),
                timezone=step.get("timezone", "UTC"),
            )
            result = _Value(resampled["values"], first["units"])
            if resampled["resampling"]["aggregation"] == "sum" and is_rate(
                first["units"]
            ):
                # The units are kept, so the warning is what stops a total being
                # read as a rate.
                step_warnings.append(
                    {
                        "code": "sum_of_rate",
                        "units": first["units"],
                        "message": (
                            "Summing rate samples gives a total for each bucket, "
                            "not a rate, although the units still read as a rate."
                        ),
                    }
                )
        else:
            result = _Value(
                scale_values(
                    first["values"],
                    method,
                    step.get("ddof"),
                    step.get("range", (0.0, 1.0)),
                ),
                "1",
            )
        normalized_step = copy.deepcopy(dict(step))
        recipe.append(normalized_step)
        output = {
            "id": step["id"],
            "timestamps": copy.deepcopy(first["timestamps"]),
            "values": result.values,
            "units": result.units,
            "calendar": calendar,
            "expression": expression,
            "inputs": names,
            "provenance": provenance,
            "recipe": {"operations": copy.deepcopy(recipe)},
            "warnings": step_warnings,
        }
        if resampled is not None:
            output.update(resampled)
        elif managed is not None:
            output.update(managed)
            if "aggregation" in first:
                output["aggregation"] = first["aggregation"]
        else:
            input_flags = [series.get("filled") for series in used.values()]
            output["filled"] = [
                value is not None
                and any(flags is not None and flags[i] for flags in input_flags)
                for i, value in enumerate(result.values)
            ]
        common_step = declared_steps[names[0]]
        if (
            resampled is None
            and common_step is not None
            and all(value == common_step for value in declared_steps.values())
        ):
            output["time_step"] = time_step_label(common_step)
        if "aggregation" in first and all(
            series.get("aggregation") == first["aggregation"]
            for series in used.values()
        ):
            output["aggregation"] = copy.deepcopy(first["aggregation"])
        frequency = first.get("frequency")
        if (
            resampled is None
            and frequency is not None
            and all(series.get("frequency") == frequency for series in used.values())
        ):
            output["frequency"] = frequency
        if method in ("minmax", "zscore"):
            output["scaling"] = {"method": method}
            if method == "minmax" and "range" in step:
                output["scaling"]["range"] = list(step["range"])
            if method == "zscore":
                output["scaling"]["ddof"] = step["ddof"]
        if method == "detrend":
            output["detrending"] = {
                "method": "ols",
                "time_basis": "elapsed_utc_seconds",
                "preserve_mean": step["preserve_mean"],
            }
        available[step["id"]] = output
        outputs[step["id"]] = output
        warnings.extend({"operation": step["id"], **w} for w in step_warnings)
    return {
        "series": outputs,
        "comparisons": comparisons,
        "recipe": {"operations": recipe},
        "warnings": warnings,
    }
