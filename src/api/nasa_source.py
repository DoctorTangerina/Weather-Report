"""On-demand NASA grids through cloud OPeNDAP, never full-file downloads.

Only coordinate vectors are read globally. Science fields are requested using
server-side index constraints over the requested time and cell centres.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast
from urllib.parse import urlencode, urlsplit

import numpy as np
from netCDF4 import Dataset, num2date

from data.data_gathering.datasets import cmr_entries, temporal_range
from data.data_gathering.download import download, load_token
from data.data_gathering.selection import SeriesSelectionError, TimeWindow

from .products import PRODUCTS


# Parallel downloads per acquisition; Earthdata accepts this many comfortably.
DOWNLOAD_WORKERS = 8


def _download_all(jobs, token):
    """Download (url, path) pairs concurrently; the first failure is raised."""
    if not jobs:
        return
    with ThreadPoolExecutor(max_workers=min(DOWNLOAD_WORKERS, len(jobs))) as pool:
        for future in [pool.submit(download, url, path, token) for url, path in jobs]:
            future.result()


_DROPPED_ATTRIBUTES = {
    "_FillValue",
    "missing_value",
    "scale_factor",
    "add_offset",
    "valid_range",
    "valid_min",
    "valid_max",
}


def _merge_longitude_runs(paths, target, field):
    """One grid file from subsets that differ only in their longitude columns."""
    parts = [Dataset(path) for path in paths]
    try:
        first = parts[0]
        with Dataset(target, "w") as out:
            out.createDimension("time", len(first["time"]))
            out.createDimension("lat", len(first["lat"]))
            out.createDimension("lon", sum(len(part["lon"]) for part in parts))
            for name, values in (
                ("time", first["time"][:]),
                ("lat", first["lat"][:]),
                ("lon", np.concatenate([np.asarray(part["lon"][:]) for part in parts])),
            ):
                variable = out.createVariable(name, "f8", (name,))
                variable.setncatts(
                    {key: first[name].getncattr(key) for key in first[name].ncattrs()}
                )
                variable[:] = values
            source = first[field]
            merged = out.createVariable(
                field, "f4", ("time", "lat", "lon"), fill_value=np.float32(1e15)
            )
            merged.setncatts(
                {
                    key: source.getncattr(key)
                    for key in source.ncattrs()
                    if key not in _DROPPED_ATTRIBUTES
                }
            )
            merged[:] = np.ma.concatenate([part[field][:] for part in parts], axis=-1)
    finally:
        for part in parts:
            part.close()


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
        granules = self._granules(product, version, boxes, period)
        # Downloads are independent, so they overlap; every netCDF read and write
        # stays on this thread, because netCDF/HDF5 is not thread-safe.
        coordinates = [directory / f"coordinates-{n}.nc4" for n in range(len(granules))]
        _download_all(
            [
                (self._subset(self._url(granule), "/time;/lat;/lon"), path)
                for granule, path in zip(granules, coordinates)
            ],
            token,
        )
        plans = []
        for n, (granule, path) in enumerate(zip(granules, coordinates)):
            plan = self._plan(path, window, boxes)
            if plan is None:
                continue
            url = self._url(granule)
            runs = [
                (
                    self._subset(url, self._constraint(field, plan, run)),
                    directory / f"grid-{n}-{part}.nc4",
                )
                for part, run in enumerate(plan["runs"])
            ]
            plans.append((granule, url, plan, runs))
        _download_all([run for *_, runs in plans for run in runs], token)
        records = []
        for granule, url, plan, runs in plans:
            if len(runs) == 1:
                path = runs[0][1]
            else:
                # One file per granule: separate files would repeat its timestamps.
                path = directory / f"grid-{len(records)}.nc4"
                _merge_longitude_runs([run_path for _, run_path in runs], path, field)
            self._finish_grid(path, plan, field, variable)
            records.append(
                {
                    "collection_id": product,
                    "dataset": product,
                    "granule_id": granule["id"],
                    "file": str(path.resolve()),
                    "url": runs[0][0] if len(runs) == 1 else url,
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
    def _granules(product, version, boxes, period):
        """Each granule once, in time order, whichever boxes it was found for."""
        found = {}
        for box in boxes:
            query = {
                "short_name": product,
                "version": version,
                "bounding_box": ",".join(map(str, box)),
                "temporal": temporal_range(period["start"], period["end"]),
                "sort_key[]": ["start_date", "producer_granule_id"],
            }
            for granule in cmr_entries("granules", query):
                found.setdefault(granule["id"], granule)
        return sorted(
            found.values(),
            key=lambda granule: (granule.get("time_start") or "", granule["id"]),
        )

    @staticmethod
    def _plan(coordinates, window, boxes):
        """Time, latitude and longitude indices covering every box, or None.

        Boxes that touch or overlap span one block of latitudes; their
        longitudes may form several runs (always two across the antimeridian).
        """
        with Dataset(coordinates) as ds:
            lat = np.asarray(ds["lat"][:])
            lon = (np.asarray(ds["lon"][:]) + 180) % 360 - 180
            time = ds["time"]
            dates = cast(
                np.ndarray,
                num2date(time[:], time.units, getattr(time, "calendar", "standard")),
            )
        timestamps = np.array([date.isoformat() for date in np.atleast_1d(dates)])
        times = np.flatnonzero(
            (timestamps >= window.lower) & (timestamps < window.upper)
        )
        rows = np.flatnonzero(
            np.any(
                [(lat >= south) & (lat <= north) for _, south, _, north in boxes],
                axis=0,
            )
        )
        cols = np.flatnonzero(
            np.any(
                [(lon >= west) & (lon <= east) for west, _, east, _ in boxes], axis=0
            )
        )
        if not (times.size and rows.size and cols.size):
            return None
        rows = np.arange(rows[0], rows[-1] + 1)
        runs = np.split(cols, np.flatnonzero(np.diff(cols) != 1) + 1)
        return {"lat": lat, "lon": lon, "times": times, "rows": rows, "runs": runs}

    @staticmethod
    def _constraint(field, plan, run):
        slices = [
            f"[{int(axis[0])}:1:{int(axis[-1])}]"
            for axis in (plan["times"], plan["rows"], run)
        ]
        names = ("time", "lat", "lon")
        return (
            f"/{field}"
            + "".join(slices)
            + ";"
            + ";".join(f"/{name}{part}" for name, part in zip(names, slices))
        )

    @staticmethod
    def _finish_grid(path, plan, field, variable):
        """Add native cell bounds (and GLDAS's land footprint) to a grid file."""
        cols = np.concatenate(plan["runs"])
        with Dataset(path, "a") as ds:
            # Keep native cell areas even when the subset has one cell.
            ds.createDimension("weather_bounds", 2)
            for name, values, indices in (
                ("lat", plan["lat"], plan["rows"]),
                ("lon", plan["lon"], cols),
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
                bounds = ds.createVariable(bounds_name, "f8", (name, "weather_bounds"))
                bounds[:] = np.column_stack((edges[indices], edges[indices + 1]))
                ds[name].bounds = bounds_name
            if variable == "soil-moisture":
                # GLDAS has a static land-only footprint; keep it for the Quality gate.
                data = ds[field][:]
                valid = np.any(~np.ma.getmaskarray(data) & np.isfinite(data), axis=0)
                mask = ds.createVariable("weather_land", "i1", ("lat", "lon"))
                mask[:] = valid

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
