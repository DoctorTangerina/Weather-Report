# Catalog sources

Where each Variable in `data/catalog.json` comes from, how its NASA units become
the units students see, and how each fact was checked. Written for ticket #23;
the fetching layer (#6) is the main reader.

All four products were confirmed against NASA's Common Metadata Repository (CMR)
collection and variable records, which are public and need no Earthdata login:
the three GES DISC products on 2026-11-14, and the vegetation index on
2026-11-15, when #41 moved it to MOD13C2. A MOD13C2 file was also downloaded and
its NDVI layer read, to confirm the attributes below.

## The four Variables

| Variable | Product (CMR concept id) | Field | NASA units | Shown as | Conversion |
| --- | --- | --- | --- | --- | --- |
| Air temperature | MERRA-2 `M2TMNXSLV` v5.12.4 (`C1276812859-GES_DISC`) | `T2M`, 2-metre air temperature | K | °C | subtract 273.15 |
| Precipitation | MERRA-2 `M2TMNXFLX` v5.12.4 (`C1276812868-GES_DISC`) | `PRECTOTCORR`, total precipitation, bias-corrected | kg m⁻² s⁻¹ | mm/month | multiply by the seconds in that month (1 kg m⁻² of water is 1 mm) |
| Soil moisture | GLDAS `GLDAS_NOAH025_M` v2.1 (`C1342986036-GES_DISC`) | `SoilMoi0_10cm_inst`, soil moisture 0–10 cm | kg m⁻² | mm | none: 1 kg m⁻² of water is 1 mm |
| Vegetation index | MODIS/Terra `MOD13C2` v061 from **LP DAAC** (`C2565788914-LPCLOUD`) | `CMG 0.05 Deg Monthly NDVI` | NDVI, stored as scaled integers | NDVI | divide by 10000; fill value −3000 |

Precipitation is a rate, not a monthly total. Multiplying by a fixed 30 days would
make February about 7% too wet and 31-day months about 3% too dry, so the
conversion has to use each month's own length.

`engine.precipitation_rate_to_monthly_total(rates, start, units)` does this, and
the fetch layer should call it rather than redo the arithmetic. Each value is
multiplied by its own month's length, with leap Februaries. A missing month
stays missing: MERRA-2's fill value, NaN and infinity all come back as None. It
refuses, with an error, anything that cannot be a precipitation rate:
- units other than `kg m-2 s-1`, so a series cannot be converted twice;
- a negative rate;
- a monthly total wetter than any month ever recorded, which catches, for
  example, millimetres per day labelled as a rate.

Source URLs in the catalog are DOIs (`https://doi.org/...`), which resolve to the
product pages. Don't copy the "landing page" links from the CMR records for the
three GES DISC products: when checked, they pointed at unrelated datasets (GPM and
TOVS products), while the DOIs resolved correctly.

## Coverage of 2000-01 to 2024-12

- MERRA-2 (temperature, precipitation): from 1980, so the whole period is covered.
- GLDAS v2.1 (soil moisture): from 2000-01, so the whole period is covered.
- MOD13C2 (vegetation index): from **2000-02**, because Terra's MODIS began
  observing that month. January 2000 is always missing: 1 month in 300, well
  under the quality gate's 20%.
- Polar night: the Siberian Arctic Region (67–73°N) has weeks of darkness around
  December, when MODIS cannot see the ground. Expect missing winter months in its
  vegetation index. The quality gate decides whether too many are missing; the
  catalog still lists the Variable, because NDVI applies to tundra.

## The vegetation index: MOD13C2 from LP DAAC

#23 first chose MOD13A3 (1 km) through AppEEARS. #41 replaced it with **MOD13C2
v061**, the same monthly NDVI on a 0.05° global grid, downloaded as one HDF4 file
per month from LP DAAC. The files download the same way as the GES DISC
products: one HTTPS request with the `EARTHDATA_TOKEN` bearer header, using
`data/data_gathering/download.py`. That needs no AppEEARS task API, no username
or password, and no separate place to store task results.

Checked on 2026-11-15:

- CMR lists MOD13C2 v061 only at LP DAAC. GES DISC has no MOD13C2. Its nearest
  product, `MODVI` v005 (`C1239898023-GES_DISC`), is a 1° coarsening of the older
  collection 5 and ends in 2015-12, so it cannot cover 2000–2024.
- Every candidate download, at LP DAAC and at GES DISC, redirects a request
  without credentials to the Earthdata login. With the bearer token, LP DAAC
  served the June 2024 file (`MOD13C2.A2024153.061.2024198104950.hdf`, 106 MB).
- Granule URLs follow
  `https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected/MOD13C2.061/<granule>/<granule>.hdf`.
  The granule name holds a production timestamp, so find each month's URL with
  a CMR granule search rather than building it by hand.

What the file's `CMG 0.05 Deg Monthly NDVI` layer holds:

- An int16 grid of 3600 rows by 7200 columns, covering 90°N to 90°S and 180°W to
  180°E at 0.05°. Ocean cells are fill, about three quarters of the grid.
- `_FillValue` −3000 and `valid_range` −2000 to 10000, so NDVI from −0.2 to 1.0.
- `scale_factor` 10000 with `add_offset` 0. MODIS HDF4 files **divide** by the
  scale factor (NDVI = stored value / 10000). A reader that applies the
  CF convention and multiplies gives values 10⁸ too large.

The extractor's NetCDF reader cannot open HDF4, and the installed netCDF4 library
is built without HDF4 support. So acquisition converts each granule, with
`pyhdf`, into a NetCDF-4 file holding the NDVI layer with CF time and coordinates
(`data/data_gathering/mod13c2.py`). It keeps the stored integers and writes the
CF `scale_factor` 0.0001, so the reader gets NDVI without knowing the MODIS
convention.

The vegetation index is land-only, and MOD13C2 has no separate land mask. The
mask comes from bits 11–13 of the `CMG 0.05 Deg Monthly VI Quality` layer, the
Land/Water flag. Only flag 1, "Land (Nothing else but land)", counts as land.
Coastlines, shorelines and inland water do not. A land cell with no data, as in
polar night, is fill, and its flag then reads as deep ocean. In the June 2024
file every cell south of 60°S is fill, so none of Antarctica is flagged land. The reader refuses a mask that changes
from file to file, so acquisition writes one static mask: a cell is land if any
acquired granule flags it land.

## Regions and the land-only gate

The quality gate (BS-003) drops a land-only Variable for any Region where less
than half the cells are land. So the catalog lists soil moisture and the
vegetation index only where the gate would keep them.

Each bounding box was measured against an equirectangular land/water mask: the
`earth-water.png` texture shipped with `three-globe`, at 0.225° per pixel. That is
finer than the GES DISC grids, though coarser than MOD13C2's 0.05°, and amply
fine for the land share of boxes several degrees across.

- Every Region that lists the land-only Variables is at least 67% land. The lowest
  are California (67%), Western Europe (72%) and the Canadian boreal forest (76%).
- Both ocean Regions are 0% land and list neither.
- The Greenland coast (70% land) and the Antarctic Peninsula (47%) list neither,
  because their land is mostly ice, which land models such as GLDAS don't
  simulate.

**Climate zones.** Each Region is placed by the latitude of its bounding box's
centre: tropical within the tropics, polar beyond the polar circles, temperate in
between. The catalog had no northern polar Region, so #23 added the Siberian Arctic
(Taymyr tundra, 99% land). Every zone is now covered in both hemispheres;
`tests/test_catalog.py` checks this.

## Method citation

Acker, J. G., McMahon, E., Shen, S., Hearty, T. and Casey, N. (2009).
Time-series analysis of remotely-sensed SeaWiFS chlorophyll in river-influenced
coastal regions. *EARSeL eProceedings* 8(2), 114–139. Confirmed on the
proceedings' own page:
https://eproceedings.uni-oldenburg.de/website/vol08_2/08_2_acker1.html

## Re-checking

These are the public endpoints used. None needs an Earthdata login:

- Collections: `https://cmr.earthdata.nasa.gov/search/collections.umm_json?short_name=<name>&version=<version>`
- Variables: `https://cmr.earthdata.nasa.gov/search/variables.umm_json?concept_id[]=<id>`,
  using the variable concept ids listed in the collection's `associations`
- Granules: `https://cmr.earthdata.nasa.gov/search/granules.umm_json?collection_concept_id=C2565788914-LPCLOUD&temporal=<start>,<end>`,
  whose `RelatedUrls` give each month's download URL

Downloading a granule itself does need the `EARTHDATA_TOKEN`.
