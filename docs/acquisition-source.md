# Gridded acquisition source

`api.grid_source.GridAcquisitionSource.prepare(request, fetch=False)` returns a
path to a data-gathering configuration. It identifies raw NetCDF grids through
`SERIES_MANIFEST`, plus field names, unit conversions and land-mask rules in
`CATALOG_SERIES` and `VARIABLE_RULES`. Reduction stays in the shared data layer.

The request carries `region_id` (an identifier for the consumer), `variable_id`,
`bbox` (west, south, east, north), `dataset`, inclusive `period.start/end`,
`time_step` and `workspace`. New files belong in that workspace; the API owns
and removes it. The source also accepts `rectangles`, a list of bounding boxes,
for Selected areas. Crossing boxes split at the antimeridian. Returned grids
retain native timestamps, cell centres, bounds and units. Consumers of joined
rectangles must select the union of cells, counting overlapping cells once.

## NASA source

The live worker uses `api.nasa_source.NasaGridAcquisitionSource`. It searches
CMR for the requested product, period and extent, discovers each granule's
current cloud OPeNDAP service, reads coordinate metadata, and downloads only
the requested field and indexed cells/timestamps via DAP4 NetCDF responses.
It never reads the offline downloads or acquisition config. Those files remain
inputs to the offline seed build. There is no full-file download fallback.

| Variable | Monthly product | Sub-monthly product | Field |
| --- | --- | --- | --- |
| Temperature | M2TMNXSLV 5.12.4 | M2T1NXSLV 5.12.4 (hourly) | T2M |
| Precipitation | M2TMNXFLX 5.12.4 | M2T1NXFLX 5.12.4 (hourly) | PRECTOTCORR |
| Soil moisture | GLDAS_NOAH025_M 2.1 | GLDAS_NOAH025_3H 2.1 (3-hourly) | SoilMoi0_10cm_inst |

`time_step="monthly"` selects monthly products. `"daily"` or `"3-hourly"`
selects the native sub-monthly products; acquisition does not resample them.
The consumer performs Aggregation, conversion and temporal reduction. The
config retains the existing monthly conversions for the current Series endpoint.
GLDAS's valid-cell footprint supplies the land mask; missing cells remain masked.
Cell bounds preserve native cell areas even for one-cell subsets. An extent
without any cell centre returns `series_source_unavailable`.

The token uses the existing `data.data_gathering.download.load_token` loader
(exported `EARTHDATA_TOKEN`, then the existing `.env` configuration). The HTTP
route keeps its existing server environment credential check, cancellable worker,
results cache and fallback responses. Results have no expiry or size cap.
Sub-monthly HTTP requests, jobs and Selected area reduction are subsequent
Explore My World tickets; this ticket implements their acquisition source.

The OPeNDAP form follows the [NASA cloud access tutorial](https://github.com/nasa/gesdisc-tutorials)
and [DAP4 constraint expressions](https://pydap.github.io/pydap/en/notebooks/MERRA2.html).
Collection and service URLs are discovered from CMR rather than obsolete archive
hosts. GLDAS 2.1 is selected explicitly because its coverage starts in 2000 and
continues to the present; 2.0 ends in 2014.

## HTTP tests

Override the FastAPI dependency before opening the test client:

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

The fake writes actual NetCDF grids, with optional `land_mask` for land-only
Variables. No token is needed. Injected files go through the same reduction
worker; unavailable injected grids never fall through to NASA. The current HTTP
endpoint still returns monthly Series. Automated tests never query NASA.
