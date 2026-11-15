# Manual data processing

Public Python methods for issue #46's arithmetic, scaling, simple resampling,
missing-value management and Pearson comparison. Everything in this
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
- `comparisons`: every Pearson comparison, keyed by operation ID (see
  [Pearson comparison](#pearson-comparison)); empty when none was requested.
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

## Scaling

Scaling uses the same `operations` list and can consume Source series or earlier
outputs. It uses every valid value in its immediate input, preserves `None` and
timestamps, and returns dimensionless units (`"1"`). Inputs and their quality
metadata remain unchanged.

```python
response = process_series(
    {
        "series": request["series"],
        "operations": [
            {"id": "normalized", "operation": "minmax", "input": "A"},
            {"id": "standardized", "operation": "zscore", "input": "B", "ddof": 0},
            {"id": "combined", "expression": "normalized + standardized"},
        ],
    }
)
```

- `minmax` scales valid values to [0, 1] by default. Supply `range` to choose
  different bounds:

  ```python
  {"id": "scaled", "operation": "minmax", "input": "A", "range": [-1, 1]}
  ```

  For input `[2, None, 4, 6]`, this produces `[-1, None, 0, 1]`. Bounds must be
  two finite numbers with lower strictly less than upper. Invalid bounds raise
  `invalid_scaling_range`. The chosen range is recorded in scaling metadata and
  instructions for replay. Output units remain dimensionless. `range` is only
  supported for Min–Max, not Z-score.
- `zscore` centres valid values and divides by their standard deviation. The
  convention was left open in the specification, so the caller must explicitly
  choose `ddof: 0` (population) or `ddof: 1` (sample). Missing or invalid `ddof`
  raises `invalid_scaling_parameters`; it is recorded for replay.
- Constant valid values raise `constant_input` with an explanation rather than
  returning invented zeros. All-missing input raises `no_valid_values`.
- Scaling results have `expression: None` and a `scaling` object identifying the
  method and, for Z-score, `ddof`. Inputs, provenance and ordered instructions are
  recorded in the same way as arithmetic results.

## Resampling

Select one input series, its current frequency, the target frequency and an
aggregation method explicitly:

```python
response = process_series(
    {
        "series": {"A": hourly_series},
        "operations": [
            {
                "id": "daily",
                "operation": "resample",
                "input": "A",
                "source_frequency": "hour",
                "frequency": "day",
                "aggregation": "mean",
            }
        ],
    }
)
daily_series = response["series"]["daily"]
```

For hourly values `[1, 5, 9]` within one day, the daily result is `5` with `mean`,
`15` with `sum`, `1` with `min`, `9` with `max`, and `5` with `median`.

- Supported frequencies: `second`, `minute`, `hour`, `3-hourly`, `day`, `month`,
  `year` (plural spellings also work; `daily` and `monthly` are accepted). The target must be the same or coarser; upsampling is
  rejected. Declare the real source frequency; multiple observations in a single
  declared source bucket produce `source_frequency_mismatch`.
- Aggregations: `mean` (`average`/`avg`), `sum`, `min` (`minimum`), `max`
  (`maximum`), `median`, and the remaining Aggregations from `CONTEXT.md`:
  `root mean square` (`rms`), `standard deviation` (`std`, population form) and
  `mean absolute value` (`mean_absolute`).
- If the input declares its own `aggregation` (the rule that built it over the
  Selected area), resampling combines it over time by the same rule: space first,
  then time. The step may then omit `aggregation`; naming a different rule raises
  `aggregation_mismatch`, and an unknown declared rule raises
  `invalid_series_aggregation`. The declared `aggregation` is carried onto the
  resampled and missing-value outputs. Without a declared rule, the step must
  choose one.
- Buckets include their start and exclude their end. Output labels identify the
  start as an ISO timestamp including its UTC offset. `timezone` optionally
  chooses an IANA zone such as `America/Sao_Paulo`; the default is `UTC`.
- Explore My World inputs declaring `time_step` use UTC, including 3-hour buckets
  starting at 00:00, 03:00, 06:00, and so on. A non-UTC override is rejected.
  Legacy native inputs without that field retain the optional time-zone setting.
- Day, month and year boundaries are calendar boundaries in the chosen zone.
  Only Gregorian calendars are supported by this simple resampling operation.
- The output spans the first through last observation's buckets, including empty
  buckets between them. It does not extrapolate to dates outside those bounds.
- Missing values are ignored within a bucket; the aggregation uses valid values
  that are present, without requiring a complete native bucket. Empty and
  all-missing buckets return `None`, including for `sum`; no zero filling occurs.
- Units and source quality assessments remain unchanged. Summing a rate such as
  `mm/day` or `kg m-2 s-1` gives a total for each bucket while the units still
  read as a rate, so that step returns a `sum_of_rate` warning instead of passing
  silently. Summing a quantity that is already a total (for example precipitation
  given in `mm` for each Time step) does not warn.
- Results include `frequency` and `resampling` metadata: source/target frequency,
  aggregation, time zone, sample counts and valid-value counts per bucket.
  Recorded instructions support replay, and output can feed scaling or arithmetic.
  A further resampling step may omit `source_frequency` if the input already has
  that frequency metadata. Explicit conflicting declarations are rejected.

A Series can declare `time_step` (`3-hourly`, `daily`, `monthly`) and `aggregation`:

```python
series_a = {**hourly_series, "time_step": "hourly", "aggregation": "maximum"}
response = process_series({
    "series": {"A": series_a},
    "operations": [{"id": "result", "operation": "resample", "input": "A", "frequency": "daily"}],
})
```

Resampling inherits that Series' Aggregation; an explicit conflicting aggregation
raises `aggregation_mismatch`. Source Time step is inherited from `time_step` or
legacy `frequency`; explicit conflicts are rejected. If no Aggregation metadata
exists, the instruction must choose one. This preserves existing native-input
calls while supporting the amended Series contract. Temporal aggregation consumes
already spatially reduced Series values: cells are not pooled across time. Cell
weighting, on-demand acquisition and precipitation-total construction are owned
by the Series-building work (#72/#78/#80), not this numeric processing method.

Resample different inputs separately to a common timeline before combining them.
This operation does not implicitly align differing coverage periods or fill gaps.

## Missing-value management

Use `operation: "missing"` with one common policy:

```python
{"id": "restored", "operation": "missing", "input": "A", "policy": "zero"}
{"id": "restored", "operation": "missing", "input": "A", "policy": "mean"}
{"id": "restored", "operation": "missing", "input": "A", "policy": "min"}
{"id": "restored", "operation": "missing", "input": "A", "policy": "max"}
{
    "id": "restored",
    "operation": "missing",
    "input": "A",
    "policy": "custom",
    "value": 12.5,
}
{"id": "restored", "operation": "missing", "input": "A", "policy": "remove"}
{
    "id": "restored",
    "operation": "missing",
    "input": "A",
    "policy": "interpolate",
    "max_gap_seconds": 14400,
}
```

`mean`/`average`, `min`/`minimum` and `max`/`maximum` use all valid values in the
immediate input, including earlier explicitly restored values. With no valid
observations, these statistical policies raise `no_valid_values`. Zero and custom
filling can restore an entirely missing input. Custom values must be finite
numbers; booleans, strings, NaN and infinity are rejected.

Linear `interpolate`/`interpolation` uses actual elapsed UTC time. A four-hour
maximum gap means that valid endpoints must be at most four hours apart; a value
at 01:00 between 00:00=0 and 04:00=8 becomes 2. Longer gaps and leading/trailing
missing values stay missing; no extrapolation occurs. The maximum gap must be
explicit, finite and positive. This operation requires Gregorian timestamps.

Restore individual missing observations by their exact input timestamp labels:

```python
{
    "id": "restored",
    "operation": "missing",
    "input": "A",
    "replacements": {
        "2024-01-01T01:00:00Z": 3.5,
        "2024-01-01T04:00:00Z": 8.0,
    },
}
```

Unspecified observations are unchanged. Unknown timestamps and attempts to
replace an already nonmissing observation are rejected. Use either individual
`replacements` or a common `policy` within one instruction; to combine them,
restore individual values first, then apply a common policy in a later step.

Results keep units and source quality unchanged. They include:

- `filled`: a boolean flag per output observation. True means a filled value
  contributed to it; missing positions are false. Flags persist through later
  arithmetic/scaling and mark resampling buckets with filled contributions.
- `missing_values`: policy, newly filled timestamps and removed timestamps.
- Input provenance and replayable instructions, just like other operations.

`remove` deletes only missing observations, without shifting remaining timestamps
or changing the source. Removing all observations returns an empty Derived series;
subsequent numeric operations require nonempty inputs. Failed acquisition quality
cannot be repaired by filling: excluded sources remain excluded.

## Pearson comparison

Compare two named series (Source or Derived) with an exploratory Pearson
correlation:

```python
response = process_series(
    {
        "series": {"A": rainfall, "B": temperature},
        "operations": [
            {"id": "A_filled", "operation": "missing", "input": "A", "policy": "mean"},
            {"id": "AB", "operation": "pearson", "inputs": ["A_filled", "B"]},
        ],
    }
)
comparison = response["comparisons"]["AB"]
```

- Inputs may come from different Regions or Selected areas and different
  Variables and units; there is no geographic pairing restriction and no unit
  acknowledgement, because r does not depend on units.
- Both inputs must have the same declared Time step and calendar; mixed Time steps
  raise `unaligned_series` (resample first). Unlike arithmetic, the inputs may
  cover different periods: observations pair only at **exactly equal** UTC
  instants (`2024-01-02` pairs with `2024-01-01T21:00:00-03:00`; 00:00 never pairs
  with 00:01). Nothing is filled, shifted, interpolated or resampled implicitly.
- A pair is jointly valid when both values are present. Pearson needs at least
  three jointly valid pairs and inputs that vary over those pairs.
- No Mirror preprocessing, thresholds or Evidence labels are applied, and scaling
  is not a prerequisite.

A comparison is reported, not raised, when r is undefined, so its sample stays
visible:

- `method`: `"pearson"`.
- `r`: the correlation in [-1, 1], or `None`.
- `valid_pairs`: jointly valid pairs used; `filled_pairs`: those in which at
  least one value was explicitly filled by an earlier `missing` step (`filled`).
- `analyzed_period`: `{start, end}` of the jointly valid pairs, or `None`.
- `overlap`: `{start, end, timestamps}` over the shared instants (including pairs
  with a missing side), or `None` when no instant is shared.
- `explanation`: `None` when r is returned; otherwise `insufficient_pairs` (with
  `required_pairs: 3`) or `constant_input` (with the constant input IDs).
- `sample`: the shared `timestamps` (labels of the first input), a per-pair
  `valid` flag, and per input its `values`, `filled` flags and `units`, for
  raw-versus-processed overlays.
- `calendar`, `inputs`, `provenance`, `recipe` and `warnings`, as for Derived
  series.

A comparison is not a series: later steps cannot use its ID as an input, and its
ID cannot be reused. Large finite values do not overflow the calculation. No
maximum sample size is enforced; that limit was left open in the specification.

## Input requirements

Each used input needs nonempty, equal-length `timestamps` and `values` lists,
plus a nonempty `units` label. Values must be finite numbers or `None`; booleans,
NaN and infinity are rejected. Optional `quality` metadata must indicate
`included: true` when supplied. Acquisition remains responsible for assessing
source quality; explicit processing does not improve the recorded source assessment.

Inputs used together in arithmetic must have the same declared Time step, calendar and matching,
ordered, distinct timestamps. Standard-calendar ISO dates/times (and YYYY-MM) are compared as exact
UTC instants; date-only and timezone-naive input timestamps mean UTC. The first
referenced input's timestamp labels are retained in the output. Nonstandard
calendars require matching timestamp labels and calendar identifiers. Different
resolutions or timelines raise `unaligned_series`; use explicit resampling where
appropriate, rather than expecting automatic alignment or repair. Conflicting Time-step
metadata is rejected even if the timestamp arrays happen to be identical.
`time_step` and legacy `frequency` aliases must agree when both are supplied.
Time step and a shared Aggregation are retained through arithmetic/scaling and
missing-value operations. Legacy inputs without cadence metadata remain accepted
when their exact timelines match; cadence is not guessed from sparse observations.

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

Tests exercise the public method and preview with deterministic fixtures. No API
or engine implementation is included here.
