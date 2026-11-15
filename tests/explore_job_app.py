"""Real HTTP/browser harness; only the gridded acquisition source is replaced."""

import os
import tempfile
import time

from api import main
from engine import ENGINE_VERSION, JsonResultStore
from tests.fake_acquisition import FakeGridAcquisitionSource

workspace = tempfile.TemporaryDirectory(prefix="weather-explore-e2e-")
main.live_store = JsonResultStore(workspace.name, ENGINE_VERSION)
os.environ["WEATHER_REPORT_LATEST_MONTH"] = "2025-02"


class BrowserSource(FakeGridAcquisitionSource):
    def prepare(self, request, *, fetch=False):
        time.sleep(1)
        if request["variable_id"] == "precipitation":
            raise OSError("Synthetic acquisition failure")
        return super().prepare(request, fetch=fetch)


source = BrowserSource(
    timestamps=["2025-01-01T00:00:00", "2025-02-01T00:00:00"],
    latitudes=[12.0],
    longitudes=[0.0, 1.0],
    values=[[[2.0, 6.0]], [[10.0, 14.0]]],
    units="°C",
)
main.app.dependency_overrides[main.get_acquisition_source] = lambda: source
app = main.app
