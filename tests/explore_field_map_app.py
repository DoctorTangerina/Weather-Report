"""#82 browser harness; only NASA is replaced with native synthetic grids."""

import os
import tempfile

from api import main
from engine import ENGINE_VERSION, JsonResultStore
from tests.fake_acquisition import FakeGridAcquisitionSource, NativeGridSource

workspace = tempfile.TemporaryDirectory(prefix="weather-field-map-")
main.live_store = JsonResultStore(workspace.name, ENGINE_VERSION)
main.area_cache = main.AreaSeriesCache(os.path.join(workspace.name, "areas"))
os.environ["WEATHER_REPORT_LATEST_MONTH"] = "2025-02"


class BrowserSource:
    def prepare(self, request, *, fetch=False):
        if request["variable_id"] == "soil-moisture":
            return FakeGridAcquisitionSource(
                timestamps=["2010-01-01", "2010-01-02"],
                latitudes=[15],
                longitudes=[0, 1, 2, 3],
                values=[[[3, 5, 7, 9]]] * 2,
                units="mm",
                land_mask=[[1, 1, 0, 0]],
            ).prepare(request, fetch=fetch)
        rain = request["variable_id"] == "precipitation"
        return NativeGridSource(
            lambda stamp, cell: (
                1 / 3600 if rain else (-3.0 if stamp.day == 1 else 12.0) + cell
            ),
            hours=3,
            longitudes=[0, 1, 2, 3],
            units="kg m-2 s-1" if rain else "°C",
            conversion="rate_per_second_to_per_month" if rain else None,
            native_units="kg m-2 s-1" if rain else None,
        ).prepare(request, fetch=fetch)


source = BrowserSource()
main.app.dependency_overrides[main.get_acquisition_source] = lambda: source
app = main.app
