"""Browser harness for #60-#62: the real API with deterministic correlation inputs.

The committed seed set supplies the catalog Regions' monthly series. These
acquired-result fixtures add the cases the Correlation map must explain: an
input missing one month, a constant input, an input that failed the acquisition
Quality gate, daily inputs with their own Aggregation, and one acquired Selected
area across the antimeridian. Nothing is downloaded.
"""

import math
import tempfile
from datetime import date, timedelta

from api import main
from engine import ENGINE_VERSION, JsonResultStore

YEAR = "2010"
MONTHS = [f"{YEAR}-{month:02d}-01" for month in range(1, 13)]
DAYS = [
    (date(2010, 1, 1) + timedelta(days=offset)).isoformat() for offset in range(365)
]
PACIFIC = [{"west": 170, "east": -170, "south": -10, "north": 10}]


def acquired(variable, values, *, region=None, timestamps=MONTHS, **metadata):
    series = {
        "engine_version": ENGINE_VERSION,
        "variable_id": variable,
        "period": {"start": f"{YEAR}-01", "end": f"{YEAR}-12"},
        "timestamps": timestamps,
        "values": values,
        "units": "1",
        "time_step": "monthly" if timestamps is MONTHS else "daily",
        "aggregation": "mean",
        "quality": {"included": True, "missing_fraction": 0.0},
        "source": {"provider": "Fixture", "dataset": "Correlation fixture"},
        **metadata,
    }
    if region is not None:
        series["region_id"] = region
    return series


def wave(count, phase=0.0, scale=1.0):
    return [round(scale * (2 + math.sin(i / 3 + phase)), 6) for i in range(count)]


FIXTURES = [
    # One month without a value: incomplete on the output timeline.
    acquired(
        "vegetation-index",
        [0.3, None, *wave(10, scale=0.1)],
        region="amazon-basin",
    ),
    # The same value every month: Pearson is undefined.
    acquired("vegetation-index", [0.5] * 12, region="congo-basin"),
    # Rejected by the acquisition Quality gate.
    acquired(
        "soil-moisture",
        wave(12),
        region="sahara",
        quality={
            "included": False,
            "missing_fraction": 0.6,
            "exclusions": ["missing_fraction"],
        },
    ),
    # Daily inputs, with their own spatial Aggregation.
    acquired(
        "temperature",
        wave(365, scale=10),
        region="iberia",
        timestamps=DAYS,
        aggregation="maximum",
        units="K",
    ),
    acquired(
        "precipitation",
        wave(365, phase=1.0),
        region="iberia",
        timestamps=DAYS,
        aggregation="sum",
        units="mm",
    ),
    # An acquired Selected area crossing 180°.
    acquired("temperature", wave(12, scale=5), area={"rectangles": PACIFIC}, units="K"),
    acquired("precipitation", wave(12, phase=2.0), area={"rectangles": PACIFIC}),
]


class CorrelationStore(JsonResultStore):
    def all_series(self):
        return [*FIXTURES, *super().all_series()]


workspace = tempfile.TemporaryDirectory(prefix="weather-correlation-e2e-")
main.live_store = CorrelationStore(workspace.name, ENGINE_VERSION)
app = main.app
