# Data gathering

These tools separate discovery, file transfer, and native-frequency extraction. There is no built-in country box, product allowlist, or temperature-only
extractor. Existing data can be re-extracted without any download.

## Setup and configuration

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r data/data_gathering/requirements.txt
```

Keep credentials in a `.env` (ignored by Git), either at the repository root or
beside `.env.example` in this folder; the root file wins if both exist:

```dotenv
EARTHDATA_TOKEN=your_token_here
```

Edit non-secret settings in `data/data_gathering/config.json`:

```json
{
  "BBOX": [-74, -34, -34, 6],
  "THEMES_FILE": "data/data_gathering/themes.json",
  "CMR_PROVIDERS": ["GES_DISC", "LPCLOUD"],
  "DATA_START": "2000-01",
  "DATA_END": "2024-12"
}
```

`BBOX` is west,south,east,north in degrees. It is only a rectangle, not a country
boundary. Set any valid box in `config.json`; `--bbox WEST SOUTH EAST NORTH`
overrides it. `CMR_PROVIDERS` is an editable list; `[]` allows all CMR providers
in discovery. Exported credential environment variables override `.env`;
non-secret settings are read from `config.json`.
The current direct-file downloader authenticates NASA-hosted HTTPS file links.

## Search with any keyword or an editable theme

```sh
.venv/bin/python data/data_gathering/datasets.py --keyword 'air temperature'
.venv/bin/python data/data_gathering/datasets.py --keyword 'snow depth' --start 2024-01 --end 2024-12
.venv/bin/python data/data_gathering/datasets.py --keyword 'rainfall' --bbox -70 -10 -50 2
```

`--keyword` passes your text to NASA CMR. No monthly frequency filter is applied.
Dates accept `YYYY-MM` or `YYYY-MM-DD`; omitted dates come from `DATA_START` and
`DATA_END`. Optional `--region REGION_ID ... --catalog PATH` reads app catalog
boxes instead. There are no special country-name aliases.

Named searches are editable JSON, not a Python dictionary. For example, add a
new entry in `themes.json` without changing code:

```json
{
  "my-snow-search": {"keyword": "snow depth"},
  "air-temperature": {
    "science_keywords[0][term]": "ATMOSPHERIC TEMPERATURE"
  }
}
```

```sh
.venv/bin/python data/data_gathering/datasets.py --list-themes
.venv/bin/python data/data_gathering/datasets.py --theme my-snow-search
.venv/bin/python data/data_gathering/datasets.py --themes-file other-themes.json --theme air-temperature
```

Each result shows its title, collection ID, available dates, native interval if
stated in the title, and estimated source-file size for the selected dates and
box. Up to 20 granule sizes are sampled; the label distinguishes estimates from
metadata totals and unknown sizes. Source-file sizes can exceed the size of a
regional subset. Matching an area/date range does not establish complete
coverage or passing scientific quality checks.

## Download only selected datasets

Copy collection IDs from the search results:

```sh
.venv/bin/python data/data_gathering/datasets.py \
  --keyword temperature --start 2024-01 --end 2024-12 \
  --select C1276812859-GES_DISC C2531963170-GES_DISC --download
```

The IDs above are examples selecting the two previously downloaded products;
they are not baked into the downloader. `--download` requires explicit selection.
Files go to the ignored `downloads/` subfolder unless `--output-dir PATH` is set.
An acquisition manifest records paths, dates, dataset IDs, source URLs, and sizes.
Complete existing files matching NASA's metadata are reused. Downloading a file
does not imply that its format is supported by the extractor. Provider-specific
extraction services such as AppEEARS require a separate service integration.

To download a single known file:

```sh
.venv/bin/python data/data_gathering/download.py 'DIRECT_HTTPS_FILE_URL'
```

Cloud storage still needs a configured provider and destination; these commands
currently write local files. Credentials remain only in `.env`/the environment.

## Extract all readable time series

```sh
.venv/bin/python data/data_gathering/extract_series.py \
  --manifest data/data_gathering/downloads/acquisition-manifest.json \
  --output data/data_gathering/downloads/all-series.json
```

For files that were acquired elsewhere:

```sh
.venv/bin/python data/data_gathering/extract_series.py \
  --files first.nc second.nc --dataset-name my-dataset \
  --output data/data_gathering/downloads/my-series.json
```

The extractor discovers numeric time-varying fields from NetCDF/CF metadata,
including groups. It does not assume a variable name, unit, dataset ID, monthly
cadence, calendar, or fixed dimension order. CF scale factors, offsets and fill
values are decoded by NetCDF; invalid numeric values become JSON `null`. Native
timestamps, calendars and physical units are preserved, including kelvin.
Additional dimensions such as altitude become separately labeled series.

Options:

- `--variables NAME ...`: extract only named fields; omit for all readable fields.
- `--aggregation area-mean`: area-weighted mean inside the configured box (default).
- `--aggregation mean`: unweighted mean of selected cells or points.
- `--aggregation none`: one series per selected cell and extra-dimension combination.
- `--time-coordinate NAME`, `--latitude-coordinate NAME`,
  `--longitude-coordinate NAME`: override ambiguous/nonstandard coordinate names.
- `--area-variable NAME`: supply cell areas for curvilinear or point grids.
- `--max-series N`: raise the default 10,000-series limit for intentional large
  per-cell extractions. Exceeding it fails explicitly rather than truncating.

For regular geographic grids, area weights use provided coordinate bounds or
edges inferred from coordinate centres. Curvilinear/point grids need a cell-area
field for area weighting; CF `cell_measures` is used when unambiguous. Otherwise
choose an unweighted mean. Box selection uses grid-cell centres. It does not
apply country masks, mosaicking, land masks or product-specific QA rules.
Fields with no geographic axes retain their values without spatial averaging.

The output records each field's units, calendar, extra coordinates, spatial
aggregation and timestamp/value pairs. Unsupported fields/groups are reported in
`skipped`; no readable series, overlapping timestamps, inconsistent units or
excessive series counts produce a clear error. Tiled products should be mosaicked
before extraction. CSV, GeoTIFF and HDF files lacking readable CF coordinates
need additional format readers or conversion first; those layouts are not guessed.

## Monthly series for catalog Regions and Variables (DS-001)

`get_catalog_series(region_id, variable_id, period)` returns one monthly series
in the shape of `schemas/series.schema.json`, ready for the engine's
`Series.from_dict`. The Region's box, the Variable's units, source and land-only
flag, and the engine version all come from the catalog (`data/catalog.json`).
Which acquired dataset holds each Variable is set in `config.json`:

- `CATALOG_SERIES`: per Variable id, optional `dataset_id` (collection id) and
  `variable` (field name; defaults to the catalog's source variable). When the
  file's units differ from the catalog's, declare `native_units` and a
  `conversion`: `identity` (soil moisture: 1 kg m-2 of water is 1 mm),
  `kelvin_to_celsius`, or `rate_per_second_to_per_month` (precipitation, done by
  `engine.precipitation_rate_to_monthly_total`, which refuses values that cannot
  be a rate: `implausible_values`). Units that do not match are refused
  (`units_mismatch`), never relabelled. The precipitation conversion imports the
  engine, so run from the repository root with `pip install -e .` or
  `PYTHONPATH=src`.
- `VARIABLE_RULES`: land-only fields and their land mask, by collection id.
  The vegetation index's mask is written by its acquisition (below). Soil
  moisture uses the official GLDAS land mask, which is not committed:

```sh
mkdir -p data/data_gathering/downloads/masks
curl -L -o data/data_gathering/downloads/masks/GLDASp5_landmask_025d.nc4 \
  https://ldas.gsfc.nasa.gov/sites/default/files/ldas/gldas/VEG/GLDASp5_landmask_025d.nc4
```

Native observations become one mean per calendar month. A month with no valid
value is `null`. The quality gate (BS-003) then runs: more than 20% missing months,
or under 50% valid land cells for a land-only Variable, returns the series with
`quality.included: false`, its reasons in `quality.exclusions` and every value
withheld (`null`). The engine skips such a series (`engine.usable_series`).
Ids outside the catalogs, a Variable the catalog does not offer for the Region,
unacquired data, a missing land mask and unit mismatches raise
`SeriesSelectionError`.

Build files for chosen Regions and Variables from acquired data:

```sh
python -m data.data_gathering.build_series \
  --regions amazon-basin sahel --variables temperature precipitation soil-moisture \
  --start 2000-01 --end 2024-12   # these are the defaults
```

Acquire a product first (each run adds to `acquisition-manifest.json`; it no
longer replaces products acquired earlier). Full 2000-2024 files are large
(about 15 GB each for MERRA-2 temperature and precipitation, 7 GB for GLDAS,
about 29 GB of HDF4 for MOD13C2):

```sh
python data/data_gathering/datasets.py --keyword M2TMNXSLV --select C1276812859-GES_DISC --download   # temperature
python data/data_gathering/datasets.py --keyword M2TMNXFLX --select C1276812868-GES_DISC --download   # precipitation
python data/data_gathering/datasets.py --keyword GLDAS_NOAH025_M --select C1342986036-GES_DISC --download   # soil moisture
python data/data_gathering/datasets.py --keyword MOD13C2 --select C2565788914-LPCLOUD --download   # vegetation index
```

The vegetation index comes from MODIS MOD13C2 (see `docs/catalog-sources.md`),
whose granules are HDF4, which the extractor cannot read. Acquisition handles
this (`mod13c2.py`, which needs `pyhdf`):

- Each granule is converted to a NetCDF-4 file beside it, holding its NDVI with
  CF time and coordinates. The manifest records that file, and the `.hdf` as
  `source_file`. The `.hdf` is not read again unless the `.nc` is deleted.
- `downloads/masks/MOD13C2_landmask_005d.nc` is created, or added to, from the
  granules' VI Quality Land/Water flag. A cell is land if any acquired granule
  flags it "Land"; coastlines and inland water are not land. Acquire whole
  years, so that land in polar night (no data, flagged as ocean) is counted from
  its summer months.

## Callable method and quality gate

The implementation, models, reader, quality gate, configuration, tests and
integration documentation are all contained in this folder. No engine, API or
frontend implementation is needed to call the method.

```python
from data.data_gathering import get_time_series

series = get_time_series(
    area={"west": -70, "east": -50, "south": -10, "north": 2},
    variable="T2M",
    period={"start": "2024-01", "end": "2024-12"},
)
```

The method selects the requested dataset/field, box and period, validates that
selection, and returns a JSON-ready dict. More than 20% missing calendar months
or less than 50% valid land cells for a land-only Variable raises
`SeriesSelectionError` instead of returning values. Exactly 20% missing and
exactly 50% land pass. Land-only Variables require a configured, aligned land
mask; water cells are removed before averaging. Native timestamps and units
are preserved.

See [SERIES_ACCESS.md](SERIES_ACCESS.md) for the API developer's integration
contract and trusted land-mask configuration. The caller owns HTTP handling.

Run the self-contained data tests from the repository root:

```sh
.venv/bin/python -m pip install -r data/data_gathering/requirements-dev.txt
MPLCONFIGDIR=/tmp/weather-report-matplotlib \
  .venv/bin/python -m pytest data/data_gathering/tests -q
```
