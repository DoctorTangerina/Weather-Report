# Catalog sources

Where each Variable in `data/catalog.json` comes from, how its NASA units become
the units students see, and how each fact was checked. Written for ticket #23;
the fetching layer (#6) is the main reader.

All four products were confirmed on 2026-11-14 against NASA's Common Metadata
Repository (CMR) collection and variable records, which are public and need no
Earthdata login. The AppEEARS product API was checked too, for the vegetation
index.

## The four Variables

| Variable | Product (CMR concept id) | Field | NASA units | Shown as | Conversion |
| --- | --- | --- | --- | --- | --- |
| Air temperature | MERRA-2 `M2TMNXSLV` v5.12.4 (`C1276812859-GES_DISC`) | `T2M`, 2-metre air temperature | K | °C | subtract 273.15 |
| Precipitation | MERRA-2 `M2TMNXFLX` v5.12.4 (`C1276812868-GES_DISC`) | `PRECTOTCORR`, total precipitation, bias-corrected | kg m⁻² s⁻¹ | mm/month | multiply by the seconds in that month (1 kg m⁻² of water is 1 mm) |
| Soil moisture | GLDAS `GLDAS_NOAH025_M` v2.1 (`C1342986036-GES_DISC`) | `SoilMoi0_10cm_inst`, soil moisture 0–10 cm | kg m⁻² | mm | none: 1 kg m⁻² of water is 1 mm |
| Vegetation index | MODIS/Terra `MOD13C2` v061 (`C2565788914-LPCLOUD`) | `CMG 0.05 Deg Monthly NDVI` | NDVI, stored as scaled integers | NDVI | multiply by 0.0001; fill value −3000 |

Precipitation is a rate, not a monthly total. Multiplying by a fixed 30 days would
make February about 7% too wet and 31-day months about 3% too dry, so the
conversion has to use each month's own length.

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

## Why the vegetation index comes from LP DAAC, not AppEEARS

The spec and the starting points in #23 assumed MOD13C2 through AppEEARS.
AppEEARS's product API (`/api/product`) lists 193 products and **MOD13C2 is not
among them**. Its monthly MODIS vegetation product is MOD13A3 v061, layer
`_1_km_monthly_NDVI`, at 1 km.

MOD13C2 is in CMR under the `LPCLOUD` provider, which the acquisition code in #6
already searches (`CMR_PROVIDERS: ["GES_DISC", "LPCLOUD"]`). Its 0.05° grid also
suits averages over Regions hundreds of kilometres across far better than 1 km
tiles. So the catalog names LP DAAC.

If the team prefers AppEEARS, swap in MOD13A3 v061 `_1_km_monthly_NDVI`. It uses
the same 0.0001 scale factor and −3000 fill value, starts in 2000-02 as well, and
was confirmed in the AppEEARS product API and in CMR (`C2327962326-LPCLOUD`).

One format note for #6: MOD13C2 granules are HDF-EOS (HDF4), not NetCDF.

## Regions and the land-only gate

The quality gate (BS-003) drops a land-only Variable for any Region where less
than half the cells are land. So the catalog lists soil moisture and the
vegetation index only where the gate would keep them.

Each bounding box was measured against an equirectangular land/water mask: the
`earth-water.png` texture shipped with `three-globe`, at 0.225° per pixel. That is
finer than any of the four products.

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
- AppEEARS products: `https://appeears.earthdatacloud.nasa.gov/api/product`
  and `/api/product/<ProductAndVersion>` for its layers
