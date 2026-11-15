"""Browser harness for #79: the real API, with a synthetic global grid as NASA.

Cells every 10 degrees cover any rectangle a test draws. Soil moisture has no
valid land anywhere, as over open ocean, so it comes back as an Excluded series.
"""

import os
import tempfile
from dataclasses import replace

from api import main
from engine import ENGINE_VERSION, JsonResultStore
from tests.fake_acquisition import FakeGridAcquisitionSource

workspace = tempfile.TemporaryDirectory(prefix="weather-area-e2e-")
main.live_store = JsonResultStore(workspace.name, ENGINE_VERSION)
main.area_cache = main.AreaSeriesCache(os.path.join(workspace.name, "areas"))
os.environ["WEATHER_REPORT_LATEST_MONTH"] = "2025-02"

UNITS = {"temperature": "°C", "precipitation": "mm/month", "soil-moisture": "mm"}
LATITUDES = [float(lat) for lat in range(-85, 90, 10)]
LONGITUDES = [float(lng) for lng in range(-175, 180, 10)]
MONTHS = [f"2024-{month:02d}-01T00:00:00" for month in range(3, 13)] + [
    "2025-01-01T00:00:00",
    "2025-02-01T00:00:00",
]


class GlobalSource(FakeGridAcquisitionSource):
    def prepare(self, request, *, fetch=False):
        variable = request["variable_id"]
        grid = replace(
            self,
            units=UNITS[variable],
            land_mask=[[0] * len(LONGITUDES) for _ in LATITUDES]
            if variable == "soil-moisture"
            else None,
        )
        return FakeGridAcquisitionSource.prepare(grid, request, fetch=fetch)


source = GlobalSource(
    timestamps=MONTHS,
    latitudes=LATITUDES,
    longitudes=LONGITUDES,
    values=[
        [[20 + month + lat / 10 for _ in LONGITUDES] for lat in LATITUDES]
        for month in range(len(MONTHS))
    ],
    units="°C",
)
main.app.dependency_overrides[main.get_acquisition_source] = lambda: source
app = main.app
