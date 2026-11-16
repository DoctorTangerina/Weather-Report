"""Offline stand-in for NASA's CMR and cloud OPeNDAP, for NasaGridAcquisitionSource.

Granules are monthly, on a global 2-degree grid, and their field is given by a
function of (latitude, longitude), so expected Series values are exact. Every
request is counted; downloads can be slowed to observe concurrency.
"""

import re
import threading
import time
from datetime import datetime
from urllib.parse import parse_qs, urlsplit

import numpy as np
from netCDF4 import Dataset

# netCDF/HDF5 is not thread-safe. The real download is plain HTTP; this fake
# writes netCDF files, so its writes take turns while its delays overlap.
_NETCDF = threading.Lock()
LATITUDES = np.arange(-89.0, 90.0, 2.0)
LONGITUDES = np.arange(-179.0, 180.0, 2.0)


class FakeOpendap:
    def __init__(self, value, delay=0.0):
        self.value = value
        self.delay = delay
        self.granules = {}
        self.cmr_queries = 0
        self.downloads = []
        self.active = 0
        self.most_active = 0
        self._lock = threading.Lock()

    def install(self, monkeypatch):
        from api import nasa_source

        monkeypatch.setattr(nasa_source, "cmr_entries", self.cmr_entries)
        monkeypatch.setattr(nasa_source, "download", self.download)
        monkeypatch.setattr(nasa_source, "load_token", lambda: "offline")
        return self

    def cmr_entries(self, resource, query):
        self.cmr_queries += 1
        first, last = (
            datetime.fromisoformat(part.rstrip("Z"))
            for part in query["temporal"].split(",")
        )
        year, month = first.year, first.month
        while (year, month) <= (last.year, last.month):
            granule_id = f"G{year:04d}{month:02d}"
            url = f"https://opendap.earthdata.nasa.gov/collections/C1/granules/{granule_id}"
            self.granules[url] = datetime(year, month, 15)
            yield {
                "id": granule_id,
                "time_start": f"{year:04d}-{month:02d}-01T00:00:00Z",
                "links": [
                    {
                        "href": url,
                        "rel": "http://esipfed.org/ns/fedsearch/1.1/service#",
                        "title": "OPeNDAP request URL",
                    }
                ],
            }
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)

    def download(self, url, destination, token):
        with self._lock:
            self.active += 1
            self.most_active = max(self.most_active, self.active)
            self.downloads.append(url)
        try:
            time.sleep(self.delay)
            with _NETCDF:
                self._write(url, destination)
        finally:
            with self._lock:
                self.active -= 1
        return destination

    def _write(self, url, destination):
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}{parts.path}".removesuffix(".dap.nc4")
        constraint = parse_qs(parts.query)["dap4.ce"][0]
        stamp = self.granules[base]
        minutes = (stamp - datetime(1980, 1, 1)).total_seconds() / 60
        if constraint == "/time;/lat;/lon":
            rows, cols, field = slice(None), slice(None), None
        else:
            head = constraint.split(";")[0]
            field = head[1 : head.index("[")]
            bounds = [
                tuple(map(int, b.split(":1:")))
                for b in re.findall(r"\[([^\]]+)\]", head)
            ]
            rows = slice(bounds[1][0], bounds[1][1] + 1)
            cols = slice(bounds[2][0], bounds[2][1] + 1)
        lat, lon = LATITUDES[rows], LONGITUDES[cols]
        with Dataset(destination, "w") as ds:
            for name, values in (("time", [minutes]), ("lat", lat), ("lon", lon)):
                ds.createDimension(name, len(values))
                ds.createVariable(name, "f8", (name,))[:] = values
            ds["time"].units = "minutes since 1980-01-01 00:00:00"
            ds["lat"].units, ds["lon"].units = "degrees_north", "degrees_east"
            if field:
                grid = ds.createVariable(field, "f4", ("time", "lat", "lon"))
                grid.units = "K"
                grid[:] = [[[self.value(a, b) for b in lon] for a in lat]]
