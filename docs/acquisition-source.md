# Gridded acquisition source

`api.grid_source.GridAcquisitionSource.prepare(request, fetch=False)` returns a
path to a data-gathering configuration. That configuration identifies raw
NetCDF files through `SERIES_MANIFEST` and declares `CATALOG_SERIES` field names,
unit conversions and `VARIABLE_RULES` such as land masks. It supplies grids,
not precomputed Series. The existing data layer performs spatial selection,
area weighting, monthly reduction, conversion and the Quality gate.

The request carries `region_id`, `variable_id`, `bbox` (west, south, east, north),
`dataset`, `period` (inclusive start/end) and `workspace`. New files belong in
that workspace; the API owns and removes it. Timestamps and geographic axes
remain in the NetCDF files, so the boundary does not impose a native frequency
or grid extent.

The live worker uses `MonthlyGridAcquisitionSource`: first the configured files,
then `fetch=True` to download when the data layer reports unavailable files,
fields or datasets. Downloading and reduction stay in the cancellable worker.
This preserves the existing monthly behavior. NASA subsetting, new requested
Time steps and Selected areas belong to later tickets under ADR 0004.

For HTTP tests, override the FastAPI dependency before opening the test client:

```python
from api import main
from tests.fake_acquisition import FakeGridAcquisitionSource

source = FakeGridAcquisitionSource(
    timestamps=["2025-01-01T00:00:00", "2025-01-01T01:00:00"],
    latitudes=[12.0],
    longitudes=[0.0, 1.0],
    values=[[[2.0, 6.0]], [[10.0, 14.0]]],
    units="°C",
)
main.app.dependency_overrides[main.get_acquisition_source] = lambda: source
# Use TestClient(main.app); restore dependency_overrides in fixture teardown.
```

The fake writes actual NetCDF grids into the API workspace. Values are ordered
as time × latitude × longitude; `None` represents a missing cell. Cell bounds
are one degree wide. Supply hourly, 3-hourly or monthly ISO timestamps and any
longitude/latitude coordinates. No token or acquisition configuration is needed.
Injected grids are prepared locally before launching the same reduction worker;
if they are unavailable, the API uses its existing fallback rather than NASA.
The existing HTTP endpoint still returns monthly Series.
