"""Real HTTP/browser harness for #78; only the gridded acquisition source is replaced.

Both Variables are acquired, so every chart in the view can be rebuilt with the
chosen Aggregation. The cells differ, so each Aggregation draws other values.
"""

import os
import tempfile
from dataclasses import replace

from api import main
from engine import ENGINE_VERSION, JsonResultStore
from tests.fake_acquisition import FakeGridAcquisitionSource

workspace = tempfile.TemporaryDirectory(prefix="weather-explore-aggregations-")
main.live_store = JsonResultStore(workspace.name, ENGINE_VERSION)
os.environ["WEATHER_REPORT_LATEST_MONTH"] = "2025-02"


class BrowserSource(FakeGridAcquisitionSource):
    def prepare(self, request, *, fetch=False):
        grid = self
        if request["variable_id"] == "precipitation":
            grid = replace(self, units="mm/month", values=[[[1.0, 5.0]], [[3.0, 9.0]]])
        return FakeGridAcquisitionSource.prepare(grid, request, fetch=fetch)


source = BrowserSource(
    timestamps=["2025-01-01T00:00:00", "2025-02-01T00:00:00"],
    latitudes=[12.0],
    longitudes=[0.0, 1.0],
    values=[[[2.0, 6.0]], [[10.0, 14.0]]],
    units="°C",
)
main.app.dependency_overrides[main.get_acquisition_source] = lambda: source
app = main.app
