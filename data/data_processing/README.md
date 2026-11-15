# Manual data processing

Public Python methods for issue #46's arithmetic slice (#47). Everything in this
package is independent of the API and automatic engine. It performs no downloads
or file reads, needs no Earthdata token, and adds no third-party dependencies.

## Execute a request

```python
from data.data_processing import ProcessingError, process_series

# Real callers can supply get_time_series(...) results directly as A and B.
request = {
    "series": {
        "A": {
            "timestamps": ["2024-01-01", "2024-02-01", "2024-03-01"],
            "values": [1, 2, 3],
            "units": "mm",
        },
        "B": {
            "timestamps": ["2024-01-01", "2024-02-01", "2024-03-01"],
            "values": [4, 5, 6],
            "units": "mm",
        },
    },
    "operations": [
        {"id": "weighted", "expression": "2 * A + 3 * B"},
        {"id": "adjusted", "expression": "(weighted - A) / 2"},
    ],
}

try:
    response = process_series(request)
    final_series = response["series"]["adjusted"]
    assert final_series["values"] == [6.5, 8.5, 10.5]
except ProcessingError as error:
    problem = error.as_dict()  # code, message, details; HTTP handling is external
```

The returned object contains:

- `series`: every new output, keyed by operation ID. Each has `timestamps`,
  `values`, `units`, `calendar`, `expression`, `inputs`, `provenance`, `recipe`
  and `warnings`.
- `recipe`: ordered instructions under `operations`, ready to replay with
  compatible replacement inputs.
- `warnings`: unit warnings/conversions, tagged with the producing operation ID.

Input/output IDs must be Python-style identifiers such as `A`, `rainfall_a` or
`weighted`; output IDs cannot overwrite inputs or earlier outputs. Instructions
execute in order and may reference earlier outputs. Expressions support `+`, `-`,
`*`, `/`, unary signs, finite numeric constants and parentheses. Any number of
named series may participate; weights are used exactly as entered. Calls,
attributes, indexing, powers and arbitrary Python execution are not supported.

No supplied object is changed. A failure raises `ProcessingError` rather than
returning partially executed outputs. `None` values stay missing and propagate
through calculations, including zero-weight terms; nothing is filled with zero.
Source metadata and prior processing history are retained in provenance snapshots;
Derived series may be passed into later requests just like acquired inputs.

## Input requirements

Each used input needs nonempty, equal-length `timestamps` and `values` lists,
plus a nonempty `units` label. Values must be finite numbers or `None`; booleans,
NaN and infinity are rejected. Optional `quality` metadata must indicate
`included: true` when supplied. Acquisition remains responsible for assessing
source quality; this method never downloads, fills gaps or improves its result.

Used inputs must already have the same calendar and matching, ordered, distinct
timestamps. Standard-calendar ISO dates/times (and YYYY-MM) are compared as exact
UTC instants; date-only and timezone-naive input timestamps mean UTC. The first
referenced input's timestamp labels are retained in the output. Nonstandard
calendars require matching timestamp labels and calendar identifiers. Different
resolutions or timelines raise `unaligned_series`; resampling/alignment belong
to separate processing work.

## Units and zero denominators

Addition/subtraction between different unit labels requires explicit
acknowledgement for that instruction:

```python
{"id": "total", "expression": "A + B", "acknowledge_unit_difference": True}
```

Without it, `unit_confirmation_required` supplies the warning in error details.
With acknowledgement, supported compatible units convert the right operand into
the left operand's units; the result records conversion factor and offset.
Unsupported or incompatible combinations continue with a `Mixed units: ...`
label and warning. Multiplication/division always permit different units and
retain compound labels. They do not require additive-unit acknowledgement.

The explicit registry currently supports common length, time, temperature,
pressure and fraction units; unknown labels remain opaque. It does not infer
relationships such as rainfall mass per area to depth, or simplify/convert
arbitrary compound unit expressions. Unit labels are case-sensitive. An explicit
numeric constant used in addition/subtraction is an offset in the series' units;
constant multiplication/division leaves those units unchanged. Constant-only
expressions are rejected because no input timeline is defined.

A zero denominator blocks the entire request, including when its numerator is
missing. The `zero_denominator` error identifies affected timestamps. The caller
must explicitly correct the input (for example, `A / (B + 1)`) or remove the
observation before retrying. A zero numerator with a nonzero denominator is valid.

## Preview and replay

```python
from data.data_processing import preview_expression

preview = preview_expression("(A + 2 * B) / C")
# expression preserves parentheses; inputs are ["A", "B", "C"], constants [2].

replayed = process_series({"series": replacement_inputs, **response["recipe"]})
```

Replay recalculates using supplied compatible replacements; metadata records the
replacement sources. A result's own recipe contains the executed prefix required
to reach it. Prior Derived-series recipes remain in its input provenance.

## Verification

From the repository root with the project's local environment:

```sh
.venv/bin/python -m pytest data/data_processing/tests -q
.venv/bin/ruff check data/data_processing
```

Tests exercise the public method and preview with deterministic fixtures. No API,
engine, correlation, scaling, resampling or missing-value repair is implemented
by this arithmetic slice.
