# Selecting a time series from Python

The API owner can call this method directly. This feature does not add HTTP
routes or change the frontend.

```python
from data.data_gathering import get_time_series, SeriesSelectionError

try:
    series = get_time_series(
        area={"west": -70, "east": -50, "south": -10, "north": 2},
        variable="T2M",
        period={"start": "2024-01", "end": "2024-12"},
    )
except SeriesSelectionError as error:
    # The API decides how to expose the error. There are no series values here.
    reason = error.code
    explanation = str(error)
    quality = error.quality  # SeriesQuality, or None if no assessment was possible
else:
    # Plain dict, ready for the API's chosen response serializer.
    timestamps = series["timestamps"]
    values = series["values"]
```

Install dependencies with `pip install -r data/data_gathering/requirements.txt`. Run from the repository root so the `data` package is importable. The method reads acquired
files; it never starts NASA downloads or reads the Earthdata token.

## Parameters

- `area`: a dict with `west`, `east`, `south`, `north`, or an `data.data_gathering.models.Bbox`.
  Coordinates are degrees and must form a valid rectangle. Grid-cell centres
  inside it are selected; this does not apply national-boundary polygons.
- `variable`: the native field name, including a layer suffix when needed.
  No product or Variable list is built into the method.
- `period`: inclusive `start`/`end` strings in `YYYY-MM` or `YYYY-MM-DD`, or an
  `data.data_gathering.models.Period`. Values are selected by their native timestamps.
- `dataset_id` (optional keyword argument): selects a collection when the same
  field occurs in multiple acquired datasets. A unique field needs no id.
- `time_step` (optional keyword argument): `3-hourly`, `daily` or `monthly`.
  Declares the cadence of an already sampled Source series and assesses every
  requested UTC Time step, including absent slots. It does not aggregate a finer
  native dataset; explicitly resample/reduce that source first. Contradictory
  native cadence is rejected. Without this argument the legacy monthly catalog
  coverage contract remains unchanged.
- `config_path` (optional keyword argument): defaults to
  `data/data_gathering/config.json`.

`list_available_series()` returns acquired dataset ids and field descriptions,
units, and land-only flags for the API owner's selector. It accepts the same
optional `config_path`.

## Return value

The returned plain dict contains `dataset_id`, `variable`, `area`, `period`,
`timestamps`, `values`, `units`, `calendar`, `source`, and `quality`.
`timestamps` and `values` are equally sized lists in chronological order. Masked
or invalid observations are represented by `None`. Units and cadence stay native;
the method does not silently convert units or resample to months. When a Time
step is declared, the payload additionally records canonical `time_step` and
`aggregation: "mean"` (this selector's spatial reduction is area-weighted mean).

All selection, file reading and quality validation happen inside
`data/data_gathering/`. The API owner receives only a validated native-frequency
selection and chooses the HTTP response envelope. There are no engine imports
or engine/API changes in this implementation.

## Quality gate

Quality is calculated **after the requested area and period are selected**.
The method returns nothing unless the selection passes. For Explore My World,
pass `time_step` explicitly: more than 20% missing requested Time steps excludes
and exactly 20% passes, using reason `too_many_missing_time_steps`. For example,
21 missing daily slots out of 100 excludes even if every calendar month contains
some data. Three-hour intervals and days follow UTC; the full requested window,
including absent leading/trailing/internal slots, forms the denominator.

The legacy call without a declared Time step preserves the monthly catalog rule:

- More than 20% missing calendar months: excluded. Exactly 20% passes.
- For land-only Variables, less than 50% valid land cells: excluded. Exactly
  50% passes. The fraction counts cells, not their area weights.
- A land-only Variable without verified mask metadata is blocked, rather than
  assumed to contain enough land.

A month is missing when it has no finite, unmasked observation in the requested
window. Leading, trailing, absent and all-invalid months count. This is a monthly
coverage check; it does not promise complete daily/hourly sampling within a month.
For a partial-month date request, only observations within those dates count.

Regional values are area-weighted. Land-only values exclude water cells before
averaging. The land mask must align with the selected source grid; external
rectilinear masks are aligned by coordinates, not array position or guessed
resolution. Unsupported or unreadable selections are reported explicitly.

## Server configuration

In the existing gathering `config.json`:

```json
{
  "SERIES_MANIFEST": "data/data_gathering/downloads/acquisition-manifest.json",
  "VARIABLE_RULES": {}
}
```

Paths are resolved against the repository root unless absolute. The manifest's
relative source-file paths are resolved against its own directory. The config
and manifest are server-controlled; callers cannot provide arbitrary file paths
or turn off a Variable's land-only classification.

Newly acquired manifests store relative source-file paths, so moving a repository
and its downloaded data together does not depend on the original computer's home
directory. Python 3.11+ and the dependencies in `requirements.txt` are required.
Downloaded files are ignored by Git: another person must download them or receive
a copy of the downloads directory. Downloads require that person's Earthdata
token; reading already downloaded files does not.

For a land-only Variable, declare trusted metadata and a mask in `VARIABLE_RULES`:

```json
{
  "VARIABLE_RULES": {
    "your-collection-id": {
      "your-soil-field": {
        "land_only": true,
        "land_mask": {
          "variable": "land_classification",
          "land_values": [1]
        }
      }
    }
  }
}
```

The mask variable may be in each source file. For a separate mask file, add
`"file": "path/to/mask.nc"` inside `land_mask`. An external mask needs readable
latitude/longitude coordinates matching source cell centres. Its ordering may
differ; its resolution may not. A native NetCDF `land_only` attribute also marks
a Variable as land-only, and cannot be disabled by setting a config rule to false.
Semantic land-only classification must be declared in this trusted metadata; it
cannot be inferred reliably for arbitrary unknown scientific field names.

## Errors

`SeriesSelectionError` has `.code`, a readable message, and optional `.quality`:

| Code | Meaning |
| --- | --- |
| `series_quality_excluded` | Coverage or land fraction failed; quality includes reasons and fractions. |
| `land_mask_unavailable` | Required mask is missing, invalid, or misaligned. |
| `invalid_request` | Area, Variable, or period argument shape is invalid. |
| `invalid_period` | Dates are invalid or reversed. |
| `dataset_not_available` | The selected dataset has not been acquired. |
| `variable_not_available` | The requested field is unavailable. |
| `series_selection_ambiguous` | Choose a dataset or a specific field/layer. |
| `series_source_unavailable` | Manifest, files, or selected layout cannot be read reliably. |

Mapping these errors to HTTP responses belongs to the API implementation.
