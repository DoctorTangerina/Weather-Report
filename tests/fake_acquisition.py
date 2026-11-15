"""Reusable acquisition fake: real, small NetCDF grids, never canned Series.

Coordinates, timestamps, units and values are supplied by each test. Native
frequency is encoded by the timestamps, so hourly, 3-hourly and monthly grids
use the same fake. Files live in the acquisition workspace owned by the API.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from netCDF4 import Dataset, date2num


@dataclass
class FakeGridAcquisitionSource:
    timestamps: list[str]
    latitudes: list[float]
    longitudes: list[float]
    values: list[list[list[float | None]]]
    units: str

    def prepare(self, request: dict, *, fetch: bool = False) -> Path:
        directory = Path(request["workspace"])
        path = directory / "synthetic.nc"
        field_name = "synthetic_field"
        with Dataset(path, "w") as data:
            data.createDimension("bounds", 2)
            for name, coordinates, units in (
                ("lat", self.latitudes, "degrees_north"),
                ("lon", self.longitudes, "degrees_east"),
            ):
                data.createDimension(name, len(coordinates))
                axis = data.createVariable(name, "f8", (name,))
                axis.units = units
                axis[:] = coordinates
                # Fixed one-degree cell bounds keep separated synthetic cells equal-area.
                axis.bounds = name + "_bounds"
                bounds = data.createVariable(axis.bounds, "f8", (name, "bounds"))
                bounds[:] = [[centre - 0.5, centre + 0.5] for centre in coordinates]
            data.createDimension("time", len(self.timestamps))
            time = data.createVariable("time", "f8", ("time",))
            time.units = "hours since 2000-01-01 00:00:00"
            time[:] = date2num(
                [datetime.fromisoformat(stamp) for stamp in self.timestamps], time.units
            )
            field = data.createVariable(
                field_name, "f8", ("time", "lat", "lon"), fill_value=-9999
            )
            field.units = self.units
            field[:] = [
                [[-9999 if cell is None else cell for cell in row] for row in grid]
                for grid in self.values
            ]
        manifest = directory / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "files": [
                        {
                            "file": str(path),
                            "dataset": "synthetic",
                            "collection_id": "TEST",
                        }
                    ]
                }
            )
        )
        config = directory / "config.json"
        config.write_text(
            json.dumps(
                {
                    "SERIES_MANIFEST": str(manifest),
                    "CATALOG_SERIES": {
                        request["variable_id"]: {
                            "dataset_id": "TEST",
                            "variable": field_name,
                        }
                    },
                }
            )
        )
        return config
