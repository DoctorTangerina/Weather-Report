"""Real HTTP/browser harness for #80; only the gridded acquisition source is replaced.

Native grids are hourly, like MERRA-2, over two equal-area Sahel cells:
temperature holds the day of the month (°C) and precipitation falls at 1 mm
per hour (24 mm a day). Each fetch takes a second so progress can be seen. A
fetch for a period starting in 2010-02 fails.
"""

import os
import tempfile
import time
from dataclasses import replace

from api import main
from engine import ENGINE_VERSION, JsonResultStore
from tests.fake_acquisition import NativeGridSource

workspace = tempfile.TemporaryDirectory(prefix="weather-explore-time-steps-")
main.live_store = JsonResultStore(workspace.name, ENGINE_VERSION)
main.area_cache = main.AreaSeriesCache(os.path.join(workspace.name, "areas"))
os.environ["WEATHER_REPORT_LATEST_MONTH"] = "2025-02"

RAIN = {
    "value": lambda stamp, cell: 1 / 3600,
    "units": "kg m-2 s-1",
    "conversion": "rate_per_second_to_per_month",
    "native_units": "kg m-2 s-1",
}


class BrowserSource(NativeGridSource):
    def prepare(self, request, *, fetch=False):
        time.sleep(1)
        if request["period"]["start"] == "2010-02":
            raise OSError("Synthetic acquisition failure")
        grid = (
            replace(self, **RAIN) if request["variable_id"] == "precipitation" else self
        )
        return NativeGridSource.prepare(grid, request, fetch=fetch)


source = BrowserSource(lambda stamp, cell: float(stamp.day), longitudes=[0.0, 1.0])
main.app.dependency_overrides[main.get_acquisition_source] = lambda: source
app = main.app
