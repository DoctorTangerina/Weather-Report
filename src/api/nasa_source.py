"""On-demand NASA grids through cloud OPeNDAP, never full-file downloads.

Only coordinate vectors are read globally. Science fields are requested using
server-side index constraints over the requested time and cell centres.
"""

import json
from pathlib import Path
from typing import cast
from urllib.parse import urlencode, urlsplit

import numpy as np
from netCDF4 import Dataset, num2date

from data.data_gathering.datasets import cmr_entries, temporal_range
from data.data_gathering.download import download, load_token
from data.data_gathering.selection import SeriesSelectionError, TimeWindow

# Explicit product versions prevent selecting GLDAS 2.0 (ends in 2014).
PRODUCTS = {
    "temperature": ("M2TMNXSLV", "M2T1NXSLV", "5.12.4", "T2M", "kelvin_to_celsius"),
    "precipitation": (
        "M2TMNXFLX",
        "M2T1NXFLX",
        "5.12.4",
        "PRECTOTCORR",
        "rate_per_second_to_per_month",
    ),
    "soil-moisture": (
        "GLDAS_NOAH025_M",
        "GLDAS_NOAH025_3H",
        "2.1",
        "SoilMoi0_10cm_inst",
        "identity",
    ),
}


class NasaGridAcquisitionSource:
    """Supply manifest-backed native grids for a bbox or joined rectangles.

    time_step chooses monthly products or native hourly/3-hourly products.
    Reduction to a requested Time step belongs to the consumer, not acquisition.
    """

    def prepare(self, request: dict, *, fetch: bool = False) -> Path:
        variable = request["variable_id"]
        if variable not in PRODUCTS:
            raise SeriesSelectionError(
                "variable_not_available", "No NASA product for this Variable."
            )
        monthly, native, version, field, conversion = PRODUCTS[variable]
        step = request.get("time_step", "monthly")
        if step not in {"monthly", "daily", "3-hourly"}:
            raise SeriesSelectionError("invalid_request", "Unsupported Time step.")
        product = monthly if step == "monthly" else native
        period = request["period"]
        window = TimeWindow.create(period["start"], period["end"])
        if window.lower < "2000-01-01":
            raise SeriesSelectionError(
                "invalid_period", "NASA exploration starts in 2000-01."
            )
        boxes = request.get("rectangles", [request["bbox"]])
        boxes = self._boxes(boxes)
        directory = Path(request["workspace"])
        directory.mkdir(parents=True, exist_ok=True)
        token = load_token()
        records = []
        seen = set()
        for box in boxes:
            query = {
                "short_name": product,
                "version": version,
                "bounding_box": ",".join(map(str, box)),
                "temporal": temporal_range(period["start"], period["end"]),
                "sort_key[]": ["start_date", "producer_granule_id"],
            }
            for granule in cmr_entries("granules", query):
                key = (granule["id"], tuple(box))
                if key in seen:
                    continue
                seen.add(key)
                url = self._url(granule)
                index = len(seen)
                coordinates = directory / f"coordinates-{index}.nc4"
                download(self._subset(url, "/time;/lat;/lon"), coordinates, token)
                with Dataset(coordinates) as ds:
                    lat = np.asarray(ds["lat"][:])
                    lon = (np.asarray(ds["lon"][:]) + 180) % 360 - 180
                    time = ds["time"]
                    dates = cast(
                        np.ndarray,
                        num2date(
                            time[:], time.units, getattr(time, "calendar", "standard")
                        ),
                    )
                    timestamps = np.array(
                        [date.isoformat() for date in np.atleast_1d(dates)]
                    )
                west, south, east, north = box
                selectors = [
                    np.flatnonzero(
                        (timestamps >= window.lower) & (timestamps < window.upper)
                    ),
                    np.flatnonzero((lat >= south) & (lat <= north)),
                    np.flatnonzero((lon >= west) & (lon <= east)),
                ]
                if any(len(indices) == 0 for indices in selectors):
                    continue
                # Split discontinuous longitude indices rather than fetching intervening cells.
                longitude_runs = np.split(
                    selectors[2], np.flatnonzero(np.diff(selectors[2]) != 1) + 1
                )
                for run in longitude_runs:
                    slices = [
                        f"[{int(axis[0])}:1:{int(axis[-1])}]"
                        for axis in [*selectors[:2], run]
                    ]
                    constraint = f"/{field}" + "".join(slices)
                    constraint += ";" + ";".join(
                        f"/{name}{part}"
                        for name, part in zip(("time", "lat", "lon"), slices)
                    )
                    path = directory / f"grid-{len(records)}.nc4"
                    subset_url = self._subset(url, constraint)
                    download(subset_url, path, token)
                    with Dataset(path, "a") as ds:
                        # Keep native cell areas even when the subset has one cell.
                        ds.createDimension("weather_bounds", 2)
                        for name, values, indices in (
                            ("lat", lat, selectors[1]),
                            ("lon", lon, run),
                        ):
                            delta = np.diff(values)
                            edges = np.r_[
                                values[0] - delta[0] / 2,
                                (values[:-1] + values[1:]) / 2,
                                values[-1] + delta[-1] / 2,
                            ]
                            if name == "lat":
                                edges = np.clip(edges, -90, 90)
                            bounds_name = name + "_bounds"
                            bounds = ds.createVariable(
                                bounds_name, "f8", (name, "weather_bounds")
                            )
                            bounds[:] = np.column_stack(
                                (edges[indices], edges[indices + 1])
                            )
                            ds[name].bounds = bounds_name
                    if variable == "soil-moisture":
                        # GLDAS has a static land-only footprint; preserve it for the Quality gate.
                        with Dataset(path, "a") as ds:
                            data = ds[field][:]
                            valid = np.any(
                                ~np.ma.getmaskarray(data) & np.isfinite(data), axis=0
                            )
                            mask = ds.createVariable(
                                "weather_land", "i1", ("lat", "lon")
                            )
                            mask[:] = valid
                    records.append(
                        {
                            "collection_id": product,
                            "dataset": product,
                            "granule_id": granule["id"],
                            "file": str(path.resolve()),
                            "url": subset_url,
                            "start": granule.get("time_start"),
                            "end": granule.get("time_end"),
                        }
                    )
        if not records:
            raise SeriesSelectionError(
                "series_source_unavailable",
                "No NASA grid cells match this area and period.",
            )
        manifest = directory / "manifest.json"
        manifest.write_text(json.dumps({"files": records}))
        rules = (
            {
                product: {
                    field: {
                        "land_only": True,
                        "land_mask": {"variable": "weather_land"},
                    }
                }
            }
            if variable == "soil-moisture"
            else {}
        )
        config = directory / "config.json"
        config.write_text(
            json.dumps(
                {
                    "SERIES_MANIFEST": str(manifest.resolve()),
                    "VARIABLE_RULES": rules,
                    "CATALOG_SERIES": {
                        variable: {
                            "dataset_id": product,
                            "variable": field,
                            "conversion": conversion,
                            "native_units": {
                                "temperature": "K",
                                "precipitation": "kg m-2 s-1",
                                "soil-moisture": "kg m-2",
                            }[variable],
                        }
                    },
                }
            )
        )
        return config

    @staticmethod
    def _boxes(boxes):
        result = []
        for west, south, east, north in boxes:
            if not all(np.isfinite([west, south, east, north])) or not (
                -180 <= west <= 180
                and -180 <= east <= 180
                and west != east
                and -90 <= south < north <= 90
            ):
                raise SeriesSelectionError(
                    "invalid_request", "Invalid geographic extent."
                )
            if west > east:
                result.extend([(west, south, 180, north), (-180, south, east, north)])
            else:
                result.append((west, south, east, north))
        return result

    @staticmethod
    def _url(granule):
        for link in granule.get("links", []):
            url = link.get("href", "")
            parsed = urlsplit(url)
            if (
                not link.get("inherited")
                and link.get("rel", "").endswith("/service#")
                and "opendap" in link.get("title", "").lower()
                and parsed.scheme == "https"
                and parsed.hostname == "opendap.earthdata.nasa.gov"
            ):
                return url
        raise SeriesSelectionError(
            "series_source_unavailable",
            "NASA granule has no supported cloud OPeNDAP service.",
        )

    @staticmethod
    def _subset(url, constraint):
        return url + ".dap.nc4?" + urlencode({"dap4.ce": constraint})
