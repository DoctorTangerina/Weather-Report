# Correlation map (#56)

`build_correlation_map` receives Variable names and area selections, loads their
series, and returns numeric Pearson correlations. API transport and rendering
belong to the caller. No supplied request or loaded source is modified.

```python
from data.data_processing import build_correlation_map, ProcessingError

try:
    result = build_correlation_map(
        {
            "variables": ["temperature", "precipitation"],
            "area": "sahel",
            "period": {"start": "2010-01", "end": "2010-12"},
        }
    )
except ProcessingError as error:
    problem = error.as_dict()  # code, message, details
```

The default `SeedSeriesLoader` resolves catalog Variable/Region IDs or names,
case-insensitively, and reads checked-in monthly seed series. It does not download
NASA data. Missing cached selections produce exclusion explanations. Paths derive
from the module location, not the working directory.

For selected rectangles, other datasets, on-demand data or saved Derived series,
pass `loader=your_loader`. The synchronous callable receives `(selection, period)`
and returns a series mapping. It resolves names itself; the initial request never
contains timestamps or values. Acquisition and area reduction remain the provider's
responsibility. An unavailable input should raise `ProcessingError` or
`SeriesSelectionError`; resource exhaustion should raise `MemoryError`.

Each selection can override the common area:

```python
request = {
    "variables": [
        {"id": "temperature_a", "variable": "temperature", "area": area_a},
        {"id": "rain_b", "variable": "precipitation", "area": area_b},
    ],
    "period": {"start": "2024-01", "end": "2024-03"},
    "time_step": "monthly",
}
result = build_correlation_map(request, loader=your_loader)
```

Areas may be string identifiers or JSON mappings (including joined rectangles);
they are passed unchanged to the provider. Optional selection fields are `label`,
`area_label`, `dataset_id`, `source_time_step`, and `aggregation`. Different
Variables and different areas can be freely combined. Exact duplicates are
omitted with a warning; distinct inputs need distinct IDs. There is no fixed
selection-count cap.

A loaded series needs ordered `timestamps`, finite numeric or `None` `values`,
`units`, and `time_step` (or legacy `frequency`). Optional `quality`, `filled`,
`provenance`, and processing metadata are retained. Failed acquisition quality
also excludes Derived inputs whose provenance records rejected sources.

The common period includes both specified dates/months. ISO datetime endpoints
are inclusive. Exact timestamps align as UTC instants; nearby times never match
implicitly. Gregorian calendars are required. New `time_step` series use UTC.
Legacy `frequency` inputs may use an explicit IANA `timezone` for bucket creation.

Different native frequencies require an explicit common `time_step`. Only
coarser resampling is supported, using the existing processing method and each
series' own Aggregation. The provider must retain Aggregation metadata or the
selection must specify it. Partial buckets with valid data may aggregate; empty
buckets remain missing. No automatic filling, detrending or seasonal removal is
performed.

The final requested timeline must be complete for each retained input. Missing
observations, constants, unavailable sources and rejected acquisition quality
exclude that input with a reason. At least two usable inputs and two observations
are required. Two observations produce a warning; zero and perfect correlations
are retained without evidence thresholds.

The result contains ordered `inputs` (IDs, labels, source/processing `metadata`,
`filled_count`), symmetric `matrix` with unit diagonal, exact UTC `timestamps`,
`observation_count`, effective `settings`, `excluded` explanations and `warnings`.
`filled_pair_counts[i][j]` counts observations where either input used a filled
value. Matrix rows/columns follow `inputs` order. Resource failure returns a
structured error asking for fewer inputs, never a partial matrix.

## Connected application flow

`POST /api/correlation-map` follows the app's existing resource wrapper:
`{"data": result, "notice": null}`. Processing failures return
`{"error": {"code": ..., "message": ..., "details": ...}}` with HTTP 422;
resource exhaustion returns 503. Exclusions and warnings remain in the details
when no map can be produced. The transport schema is
`schemas/correlation-map.schema.json`. The frontend `getCorrelationMap` client
retains structured details and supports request cancellation.

The API supplies its configured acquired and live-cache inventories to
`correlate_acquired_series` in `correlation_service.py`. No request causes NASA
acquisition, no fallback example is substituted, and no engine statistics are
changed. Named catalog areas and exact matching acquired rectangle identities
are supported. Joined/antimeridian descriptors are preserved, but without an
acquired result for that exact area they return an explicit coverage exclusion.
The globe picker renders antimeridian areas as two longitude intervals.

Optional `derived` instructions let callers name a calculation without sending
series values:

```json
{
  "variables": [
    {"id": "A", "variable": "temperature", "area": "sahel"},
    {"id": "D", "variable": "twice", "area": "derived", "label": "Twice temperature"}
  ],
  "period": {"start": "2010-01", "end": "2010-12"},
  "derived": [{
    "id": "twice",
    "inputs": {"source": {"variable": "temperature", "area": "sahel"}},
    "operations": [{"id": "result", "expression": "2 * source"}],
    "output": "result"
  }]
}
```

Derived inputs are cropped to the common period before operations are replayed;
otherwise scaling statistics could depend on observations outside the requested
analysis. Existing processing rules, unit acknowledgement, source quality and
filled-value provenance apply. Source inputs can be removed from the displayed
map without changing the saved calculation's input references.

The Correlation map panel in Explore My World adds independent area/Variable
batches, removes duplicates, manages Derived calculations, and renders a labeled
heatmap with a fixed −1 to +1 scale. Cells show scores and both labels. Excluded
inputs appear below; missing data also opens a dismissible message. New selections
clear stale results, and superseded HTTP responses are ignored.
