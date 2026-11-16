"""Issue #78: Aggregations through spec #72's HTTP seam (BS-008).

Only the gridded acquisition source is replaced. Its synthetic grids give exact
expected values: cells on one latitude row with equal one-degree bounds have
equal areas, and explicit longitude bounds make one cell three times another.
"""

import json
import math
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import main
from engine import ENGINE_VERSION, JsonResultStore, Period
from tests.fake_acquisition import FakeGridAcquisitionSource

RESPONSES = "responses.schema.json"
SEED = Path(__file__).resolve().parents[1] / "data" / "seed"


class CountingSource(FakeGridAcquisitionSource):
    calls = 0

    def prepare(self, request, *, fetch=False):
        self.calls += 1
        self.__dict__.setdefault("periods", []).append(request["period"])
        return super().prepare(request, fetch=fetch)


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("WEATHER_REPORT_LATEST_MONTH", "2025-02")
    monkeypatch.setattr(main, "live_store", JsonResultStore(tmp_path, ENGINE_VERSION))
    sources = {}

    def use(source):
        sources["current"] = source
        return source

    main.app.dependency_overrides[main.get_acquisition_source] = lambda: sources.get(
        "current"
    )
    with TestClient(main.app) as client:
        yield client, use
    main.app.dependency_overrides.clear()


def two_cells(first, second, **grid):
    """One native (monthly) time step, January 2025, over two Sahel cells."""
    return CountingSource(
        timestamps=["2025-01-01T00:00:00"],
        latitudes=[15.0],
        longitudes=grid.pop("longitudes", [0.0, 1.0]),
        values=[[[first, second]]],
        units="°C",
        **grid,
    )


def explore(client, aggregation, *, start="2025-01", end="2025-01", variables=None):
    return client.get(
        "/api/explore/series",
        params={
            "region_id": "sahel",
            "variable_id": variables or ["temperature"],
            "aggregation": aggregation,
            "period_start": start,
            "period_end": end,
        },
    )


def series_of(client, response, validator_for):
    """The view's data, waiting for its background job if one was started."""
    body = response.json()
    if response.status_code == 200:
        validator_for(RESPONSES, "#/$defs/exploreSeriesResponse").validate(body)
        return body["data"]
    assert response.status_code == 202, body
    url = body["data"]["job"]["url"]
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        body = client.get(url).json()
        validator_for(RESPONSES, "#/$defs/exploreJobResponse").validate(body)
        job = body["data"]["job"]
        if job["status"] == "succeeded":
            return job["result"]
        assert job["status"] != "failed", job
        time.sleep(0.02)
    pytest.fail("Job did not finish")


@pytest.mark.parametrize(
    "aggregation,value",
    [
        ("mean", 1),
        ("median", 1),
        ("minimum", -1),
        ("maximum", 3),
        ("root_mean_square", math.sqrt(5)),
        ("standard_deviation", 2),
        ("mean_absolute_value", 2),
    ],
)
def test_each_aggregation_combines_two_equal_area_cells(
    api, validator_for, aggregation, value
):
    # BS-008: two equal-area cells holding -1 and 3 at one native time step.
    client, use = api
    use(two_cells(-1.0, 3.0))
    data = series_of(client, explore(client, aggregation), validator_for)
    assert data["aggregation"] == aggregation
    assert data["series"][0]["values"] == [pytest.approx(value)]


def test_cells_count_in_proportion_to_their_area(api, validator_for):
    # BS-008: the second cell spans 3 degrees of longitude, the first 1.
    client, use = api
    use(
        two_cells(
            -4.0,
            0.0,
            longitudes=[0.5, 2.5],
            longitude_bounds=[[0.0, 1.0], [1.0, 4.0]],
        )
    )
    data = series_of(client, explore(client, "mean_absolute_value"), validator_for)
    assert data["series"][0]["values"] == [pytest.approx(1)]


def test_a_mean_in_the_seed_period_is_answered_from_the_seed_set(api, validator_for):
    client, use = api
    source = use(two_cells(-1.0, 3.0))
    response = explore(client, "mean", start="2000-01", end="2024-12")
    assert response.status_code == 200
    assert response.json()["provenance"] == "preloaded"
    assert source.calls == 0


@pytest.fixture
def seed_with_maximum(tmp_path, monkeypatch):
    """The committed mean seed set plus a maximum Series of Sahel temperature.

    The maximum values (1000 + month index) differ from any mean in the seed.
    """
    root = tmp_path / "seed"
    shutil.copytree(SEED / "series", root / "series")
    mean = json.loads((SEED / "series" / "sahel__temperature.json").read_text())
    maximum = {**mean, "values": [1000.0 + i for i in range(len(mean["values"]))]}
    folder = root / "aggregations" / "maximum" / "series"
    folder.mkdir(parents=True)
    (folder / "sahel__temperature.json").write_text(json.dumps(maximum))
    monkeypatch.setattr(main, "store", JsonResultStore(root, ENGINE_VERSION))
    return maximum


def test_a_seeded_aggregation_is_answered_from_the_seed_set(
    api, seed_with_maximum, validator_for
):
    client, use = api
    source = use(two_cells(-1.0, 3.0))
    response = explore(client, "maximum", start="2000-01", end="2024-12")
    assert response.status_code == 200, response.json()
    validator_for(RESPONSES, "#/$defs/exploreSeriesResponse").validate(response.json())
    assert response.json()["provenance"] == "preloaded"
    assert response.json()["data"]["series"][0]["values"] == seed_with_maximum["values"]
    assert source.calls == 0


def test_a_shorter_period_is_cut_from_the_seeded_aggregation(
    api, seed_with_maximum, validator_for
):
    client, use = api
    use(two_cells(-1.0, 3.0))
    response = explore(client, "maximum", start="2024-11", end="2024-12")
    assert response.status_code == 200, response.json()
    assert (
        response.json()["data"]["series"][0]["values"]
        == (seed_with_maximum["values"][-2:])
    )


def test_a_period_beyond_the_seed_set_is_acquired_in_a_job(
    api, seed_with_maximum, validator_for
):
    # The seed set ends in 2024-12; later months are not on this computer.
    client, use = api
    source = use(two_cells(-1.0, 3.0))
    response = explore(client, "maximum")
    assert response.status_code == 202
    assert series_of(client, response, validator_for)["series"][0]["values"] == [
        pytest.approx(3)
    ]
    assert source.calls == 1


def test_a_period_partly_in_the_seed_set_acquires_only_the_missing_months(
    api, seed_with_maximum, validator_for
):
    # 2024-11 and 2024-12 come from the seed set; only 2025-01 is fetched.
    client, use = api
    source = use(two_cells(-1.0, 3.0))
    response = explore(client, "maximum", start="2024-11", end="2025-01")
    assert response.status_code == 202, response.json()
    data = series_of(client, response, validator_for)
    assert data["period"] == {"start": "2024-11", "end": "2025-01"}
    assert data["series"][0]["period"] == {"start": "2024-11", "end": "2025-01"}
    assert data["series"][0]["values"] == [
        *seed_with_maximum["values"][-2:],
        pytest.approx(3),
    ]
    assert source.periods == [{"start": "2025-01", "end": "2025-01"}]


def test_a_repeated_partial_request_is_answered_from_the_seed_and_the_cache(
    api, seed_with_maximum, validator_for
):
    client, use = api
    source = use(two_cells(-1.0, 3.0))
    first = series_of(
        client,
        explore(client, "maximum", start="2024-11", end="2025-01"),
        validator_for,
    )
    again = explore(client, "maximum", start="2024-11", end="2025-01")
    assert again.status_code == 200, again.json()
    assert again.json()["provenance"] == "cache"
    assert again.json()["data"] == first
    assert source.calls == 1


def test_the_quality_gate_judges_the_whole_stitched_period(
    api, seed_with_maximum, validator_for
):
    # The fetched months alone (one of two missing) would be excluded; with six
    # seeded months, one missing month in eight passes the gate.
    client, use = api
    source = use(
        CountingSource(
            timestamps=["2025-01-01T00:00:00", "2025-02-01T00:00:00"],
            latitudes=[15.0],
            longitudes=[0.0, 1.0],
            values=[[[-1.0, 3.0]], [[None, None]]],
            units="°C",
        )
    )
    response = explore(client, "maximum", start="2024-07", end="2025-02")
    series = series_of(client, response, validator_for)["series"][0]
    assert series["quality"]["included"] is True
    assert series["quality"]["missing_fraction"] == pytest.approx(1 / 8)
    assert series["values"] == [
        *seed_with_maximum["values"][-6:],
        pytest.approx(3),
        None,
    ]
    assert source.periods == [{"start": "2025-01", "end": "2025-02"}]


def test_an_acquired_piece_is_never_served_as_a_series_of_its_own(api, validator_for):
    # A piece keeps the values the gate would withhold; /api/series must not
    # serve it. Here 2025-01..2025-02 alone (one of two months missing) fails.
    client, use = api
    use(
        CountingSource(
            timestamps=["2025-01-01T00:00:00", "2025-02-01T00:00:00"],
            latitudes=[15.0],
            longitudes=[0.0, 1.0],
            values=[[[-1.0, 3.0]], [[None, None]]],
            units="°C",
        )
    )
    series_of(
        client, explore(client, "mean", start="2024-07", end="2025-02"), validator_for
    )
    body = client.get(
        "/api/series",
        params={
            "region_id": "sahel",
            "variable_id": "temperature",
            "period_start": "2025-01",
            "period_end": "2025-02",
        },
    ).json()
    assert body.get("provenance") != "cache"
    data = body.get("data") or {}
    if data and not data["quality"]["included"]:
        assert data["values"] == [None, None]


def test_a_mean_partly_in_the_seed_set_acquires_only_the_missing_months(
    api, validator_for
):
    client, use = api
    source = use(two_cells(-1.0, 3.0))
    # The API's seed set of means (the stub under test), which ends in 2024-12.
    seeded = main.store.series("sahel", "temperature", Period("2000-01", "2024-12"))
    response = explore(client, "mean", start="2024-12", end="2025-01")
    assert response.status_code == 202, response.json()
    values = series_of(client, response, validator_for)["series"][0]["values"]
    assert values == [seeded["values"][-1], pytest.approx(1)]
    assert source.periods == [{"start": "2025-01", "end": "2025-01"}]


def test_a_variable_missing_from_the_seeded_aggregation_is_acquired_in_a_job(
    api, seed_with_maximum, validator_for
):
    # Only temperature is seeded for maximum; the mean seed has no say in it.
    client, use = api
    source = use(
        CountingSource(
            timestamps=["2024-12-01T00:00:00"],
            latitudes=[15.0],
            longitudes=[0.0, 1.0],
            values=[[[1.0, 5.0]]],
            units="mm/month",
        )
    )
    response = explore(
        client,
        "maximum",
        start="2024-12",
        end="2024-12",
        variables=["precipitation"],
    )
    assert response.status_code == 202
    data = series_of(client, response, validator_for)
    assert data["series"][0]["values"] == [pytest.approx(5)]
    assert source.calls == 1


def test_seeded_aggregations_leave_the_discoveries_untouched(api, seed_with_maximum):
    client, _ = api
    before = client.get("/api/discoveries").json()
    explore(client, "maximum", start="2000-01", end="2024-12")
    assert client.get("/api/discoveries").json() == before
    stored = client.get(
        "/api/series", params={"region_id": "sahel", "variable_id": "temperature"}
    ).json()["data"]
    assert stored["values"] != seed_with_maximum["values"]


def test_a_cached_series_answers_only_its_own_aggregation(api, validator_for):
    client, use = api
    source = use(two_cells(-1.0, 3.0))
    series_of(client, explore(client, "mean"), validator_for)
    maximum = explore(client, "maximum")
    assert maximum.status_code == 202
    assert series_of(client, maximum, validator_for)["series"][0]["values"] == [
        pytest.approx(3)
    ]
    again = explore(client, "maximum")
    assert again.status_code == 200
    assert again.json()["provenance"] == "cache"
    assert again.json()["data"]["series"][0]["values"] == [pytest.approx(3)]
    assert source.calls == 2
