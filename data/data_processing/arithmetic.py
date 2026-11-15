"""Execute declarative arithmetic recipes without HTTP or engine dependencies."""

import ast
import copy
import keyword
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise

from .units import compound, conversion


class ProcessingError(ValueError):
    """A caller-visible failure; details can be serialized by the owning API."""

    def __init__(self, code: str, message: str, **details):
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict:
        return {"code": self.code, "message": str(self), "details": self.details}


def _number(value) -> bool:
    try:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )
    except OverflowError:
        return False


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


def _timeline(series: Mapping, name: str) -> list:
    timestamps, values = series.get("timestamps"), series.get("values")
    if (
        not isinstance(timestamps, list)
        or not timestamps
        or not all(isinstance(t, str) and t for t in timestamps)
        or not isinstance(values, list)
        or len(timestamps) != len(values)
        or any(v is not None and not _number(v) for v in values)
        or not isinstance(series.get("units"), str)
        or not series["units"].strip()
    ):
        raise ProcessingError(
            "invalid_series",
            "Provide timestamps, finite values/nulls and units.",
            input=name,
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


def _evaluate(node, inputs, length, timestamps, acknowledged, warnings):
    if isinstance(node, ast.Name):
        return _Value(inputs[node.id]["values"], inputs[node.id]["units"])
    if isinstance(node, ast.Constant):
        return _Value([float(node.value)] * length, "1", scalar=True)
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
    values = []
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
    already share timestamps/calendar; alignment and resampling are separate work.
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
    outputs, recipe, warnings = {}, [], []
    for index, step in enumerate(steps):
        if (
            not isinstance(step, Mapping)
            or set(step) - {"id", "expression", "acknowledge_unit_difference"}
            or not _name(step.get("id"))
            or step["id"] in available
            or not isinstance(step.get("acknowledge_unit_difference", False), bool)
        ):
            raise ProcessingError(
                "invalid_operation",
                "Use a new output id and supported parameters.",
                operation=index,
            )
        expression = step.get("expression")
        tree = _parse(expression)
        names = preview_expression(expression)["inputs"]
        if not names:
            raise ProcessingError(
                "invalid_expression", "Reference at least one series."
            )
        missing = [name for name in names if name not in available]
        if missing:
            raise ProcessingError(
                "unknown_input", "Unknown series reference.", inputs=missing
            )
        used = {name: available[name] for name in names}
        timelines = {name: _timeline(series, name) for name, series in used.items()}
        first = used[names[0]]
        calendar = first.get("calendar", "standard")
        if any(
            timelines[name] != timelines[names[0]]
            or used[name].get("calendar", "standard") != calendar
            for name in names
        ):
            raise ProcessingError(
                "unaligned_series",
                "Explicitly align/resample these inputs first.",
                inputs=names,
            )
        step_warnings = []
        result = _evaluate(
            tree.body,
            used,
            len(first["timestamps"]),
            first["timestamps"],
            step.get("acknowledge_unit_difference", False),
            step_warnings,
        )
        normalized_step = dict(step)
        recipe.append(normalized_step)
        # Metadata snapshots preserve source quality and previous processing history.
        provenance = {
            name: {
                key: copy.deepcopy(value)
                for key, value in series.items()
                if key not in ("values", "timestamps")
            }
            for name, series in used.items()
        }
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
        available[step["id"]] = output
        outputs[step["id"]] = output
        warnings.extend({"operation": step["id"], **w} for w in step_warnings)
    return {"series": outputs, "recipe": {"operations": recipe}, "warnings": warnings}
