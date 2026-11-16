"""Reusable acquisition fake: real, small NetCDF grids, never canned Series.

Coordinates, timestamps, units and values are supplied by each test. Native
frequency is encoded by the timestamps, so hourly, 3-hourly and monthly grids
use the same fake. Files live in the acquisition workspace owned by the API.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from netCDF4 import Dataset, date2num


@dataclass
class FakeGridAcquisitionSource:
    timestamps: list[str]
    latitudes: list[float]
    longitudes: list[float]
    values: list[list[list[float | None]]]
    units: str
    land_mask: list[list[int]] | None = None
    # Explicit [low, high] cell bounds; one degree around each centre by default.
    latitude_bounds: list[list[float]] | None = None
    longitude_bounds: list[list[float]] | None = None
    # A unit conversion the config declares, as the NASA source does for its
    # products (for example a rate in kg m-2 s-1 to a precipitation total).
    conversion: str | None = None
    native_units: str | None = None

    def prepare(self, request: dict, *, fetch: bool = False) -> Path:
        directory = Path(request["workspace"])
        path = directory / "synthetic.nc"
        field_name = "synthetic_field"
        with Dataset(path, "w") as data:
            data.createDimension("bounds", 2)
            for name, coordinates, units, explicit in (
                ("lat", self.latitudes, "degrees_north", self.latitude_bounds),
                ("lon", self.longitudes, "degrees_east", self.longitude_bounds),
            ):
                data.createDimension(name, len(coordinates))
                axis = data.createVariable(name, "f8", (name,))
                axis.units = units
                axis[:] = coordinates
                # Fixed one-degree cell bounds keep separated synthetic cells equal-area.
                axis.bounds = name + "_bounds"
                bounds = data.createVariable(axis.bounds, "f8", (name, "bounds"))
                bounds[:] = explicit or [
                    [centre - 0.5, centre + 0.5] for centre in coordinates
                ]
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
            if self.land_mask is not None:
                mask = data.createVariable("land", "i1", ("lat", "lon"))
                mask[:] = self.land_mask
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
                    "VARIABLE_RULES": {
                        "TEST": {
                            field_name: {
                                "land_only": True,
                                "land_mask": {"variable": "land"},
                            }
                        }
                    }
                    if self.land_mask is not None
                    else {},
                    "CATALOG_SERIES": {
                        request["variable_id"]: {
                            "dataset_id": "TEST",
                            "variable": field_name,
                            **(
                                {
                                    "conversion": self.conversion,
                                    "native_units": self.native_units,
                                }
                                if self.conversion
                                else {}
                            ),
                        }
                    },
                }
            )
        )
        return config


@dataclass
class NativeGridSource:
    """Hourly (or `hours`-hourly) grids over the requested months, like MERRA-2.

    `value(stamp, cell)` gives cell `cell`'s value at native time `stamp` (UTC),
    or None. Hourly stamps fall on the half hour, as MERRA-2's do. One latitude
    row with one-degree bounds keeps the cells equal-area.
    """

    value: object
    longitudes: list = field(default_factory=lambda: [0.0, 1.0, 2.0])
    latitude: float = 15.0
    hours: int = 1
    units: str = "°C"
    conversion: str | None = None
    native_units: str | None = None
    # Per Variable replacements for units, conversion and native_units.
    overrides: dict = field(default_factory=dict)
    calls: int = 0
    requests: list = field(default_factory=list)

    def prepare(self, request, *, fetch=False):
        self.calls += 1
        self.requests.append(dict(request))
        start = datetime.fromisoformat(request["period"]["start"] + "-01")
        last = datetime.fromisoformat(request["period"]["end"] + "-01")
        end = (last + timedelta(days=32)).replace(day=1)
        stamps = []
        stamp = start + timedelta(minutes=30 if self.hours == 1 else 0)
        while stamp < end:
            stamps.append(stamp)
            stamp += timedelta(hours=self.hours)
        grid = FakeGridAcquisitionSource(
            timestamps=[item.isoformat() for item in stamps],
            latitudes=[self.latitude],
            longitudes=self.longitudes,
            values=[
                [[self.value(item, cell) for cell in range(len(self.longitudes))]]
                for item in stamps
            ],
            **{
                "units": self.units,
                "conversion": self.conversion,
                "native_units": self.native_units,
                **self.overrides.get(request["variable_id"], {}),
            },
        )
        return grid.prepare(request, fetch=fetch)
