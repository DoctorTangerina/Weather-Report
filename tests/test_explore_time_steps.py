"""Issue #80: Time steps through spec #72's HTTP seam (BS-007, BS-008, BS-010).

Only the gridded acquisition source is replaced. Its synthetic grids are hourly
or 3-hourly like MERRA-2 and GLDAS, so the reduction to a Time step is the real
one. Cells on one latitude row with one-degree bounds have equal areas.
"""

import time
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from api import main
from engine import ENGINE_VERSION, JsonResultStore
from tests.fake_acquisition import NativeGridSource

RESPONSES = "responses.schema.json"
# MERRA-2 precipitation, a rate in kg m-2 s-1.
RATE = {
    "units": "kg m-2 s-1",
    "conversion": "rate_per_second_to_per_month",
    "native_units": "kg m-2 s-1",
}


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("WEATHER_REPORT_LATEST_MONTH", "2025-02")
    monkeypatch.setattr(main, "live_store", JsonResultStore(tmp_path, ENGINE_VERSION))
    monkeypatch.setattr(main, "area_cache", main.AreaSeriesCache(tmp_path / "areas"))
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


def explore(
    client,
    time_step,
    *,
    aggregation="mean",
    start="2010-01",
    end="2010-01",
    variables=("temperature",),
    **place,
):
    if not place:
        place = {"region_id": "sahel"}
    return client.get(
        "/api/explore/series",
        params={
            **place,
            "variable_id": list(variables),
            "aggregation": aggregation,
            "time_step": time_step,
            "period_start": start,
            "period_end": end,
        },
    )


def job_of(client, response, validator_for):
    assert response.status_code == 202, response.json()
    validator_for(RESPONSES, "#/$defs/exploreJobResponse").validate(response.json())
    url = response.json()["data"]["job"]["url"]
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        body = client.get(url).json()
        validator_for(RESPONSES, "#/$defs/exploreJobResponse").validate(body)
        job = body["data"]["job"]
        if job["status"] in {"succeeded", "failed"}:
            return job
        time.sleep(0.02)
    pytest.fail("Job did not finish")


def series_of(client, response, validator_for):
    job = job_of(client, response, validator_for)
    assert job["status"] == "succeeded", job
    return job["result"]


def constant(number):
    return lambda stamp, cell: number


def test_a_daily_median_is_the_median_of_the_areas_medians_over_the_day(
    api, validator_for
):
    # BS-008: three equal-area cells; within 2010-01-01 they hold 0, 0, 10 at the
    # first native time step, 0, 0, 10 at the second and 5, 5, 5 at the third.
    # A median over all nine values would be 5; over the area first it is 0.
    client, use = api
    first_day = {0: [0, 0, 10], 1: [0, 0, 10], 2: [5, 5, 5]}

    def value(stamp, cell):
        if stamp.day == 1:
            return first_day[stamp.hour // 8][cell]
        return 7.0

    use(NativeGridSource(value, hours=8))
    data = series_of(
        client, explore(client, "daily", aggregation="median"), validator_for
    )
    assert data["time_step"] == "daily"
    assert data["series"][0]["values"][0] == pytest.approx(0)


def test_daily_precipitation_is_the_total_that_fell_during_the_day(api, validator_for):
    # BS-008: 1 mm per hour throughout 2010-01-01 UTC, as MERRA-2's rate in
    # kg m-2 s-1 (1 kg m-2 is 1 mm deep).
    client, use = api
    use(NativeGridSource(constant(1 / 3600), overrides={"precipitation": RATE}))
    data = series_of(
        client, explore(client, "daily", variables=("precipitation",)), validator_for
    )
    series = data["series"][0]
    assert series["values"][0] == pytest.approx(24)
    assert series["units"] == "mm/day"


def test_3_hourly_precipitation_is_the_total_that_fell_in_each_3_hours(
    api, validator_for
):
    client, use = api
    use(NativeGridSource(constant(1 / 3600), overrides={"precipitation": RATE}))
    data = series_of(
        client,
        explore(client, "3-hourly", variables=("precipitation",)),
        validator_for,
    )
    series = data["series"][0]
    assert series["values"][0] == pytest.approx(3)
    assert series["units"] == "mm/3h"


def test_a_daily_value_covers_one_utc_day(api, validator_for):
    # BS-008: at 135°E local midnight is 15:00 UTC, so a local day would mix
    # 2010-01-01 UTC (1) with 2010-01-02 UTC (5).
    client, use = api
    use(
        NativeGridSource(
            lambda stamp, cell: 1.0 if stamp.day == 1 else 5.0,
            longitudes=[135.0],
            latitude=0.0,
        )
    )
    data = series_of(
        client,
        explore(client, "daily", rectangle=["134,-1,136,1"]),
        validator_for,
    )
    assert data["series"][0]["values"][:2] == pytest.approx([1, 5])


@pytest.mark.parametrize(
    "time_step,count", [("3-hourly", 31 * 8), ("daily", 31), ("monthly", 1)]
)
def test_a_series_has_one_value_per_time_step(api, validator_for, time_step, count):
    # BS-002 at the HTTP seam: January 2010 holds 248 3-hour intervals, 31 days
    # and one month, whatever the native time step.
    client, use = api
    use(
        NativeGridSource(
            lambda stamp, cell: stamp.day / 86400, overrides={"precipitation": RATE}
        )
    )
    response = explore(
        client,
        time_step,
        variables=("temperature", "precipitation"),
        start="2025-01",
        end="2025-01",
    )
    data = series_of(client, response, validator_for)
    assert data["time_step"] == time_step
    assert [len(item["values"]) for item in data["series"]] == [count, count]


def test_a_daily_request_starts_a_job_that_yields_the_series_then_is_cached(
    api, validator_for
):
    # BS-007: the seed set has no daily temperature for the Sahel.
    client, use = api
    source = use(NativeGridSource(lambda stamp, cell: float(stamp.day)))
    before = client.get("/api/discoveries").json()
    response = explore(client, "daily")
    assert response.json()["data"]["job"]["status"] in {"queued", "running"}
    first = series_of(client, response, validator_for)
    assert first["series"][0]["values"] == pytest.approx(range(1, 32))
    assert source.requests[0]["time_step"] == "daily"
    again = explore(client, "daily")
    assert again.status_code == 200, again.json()
    validator_for(RESPONSES, "#/$defs/exploreSeriesResponse").validate(again.json())
    assert again.json()["provenance"] == "cache"
    assert again.json()["data"] == first
    assert source.calls == 1
    assert client.get("/api/discoveries").json() == before


def test_a_cached_series_answers_only_its_own_time_step(api, validator_for):
    client, use = api
    source = use(NativeGridSource(lambda stamp, cell: float(stamp.day)))
    series_of(
        client, explore(client, "daily", start="2025-01", end="2025-01"), validator_for
    )
    monthly = explore(client, "monthly", start="2025-01", end="2025-01")
    assert monthly.status_code == 202
    assert series_of(client, monthly, validator_for)["series"][0][
        "values"
    ] == pytest.approx([16])
    assert source.calls == 2


@pytest.mark.parametrize(
    "place",
    [{"region_id": "sahel"}, {"rectangle": ["-1,14,3,16"]}],
    ids=["region", "selected-area"],
)
@pytest.mark.parametrize(
    "missing,included", [(24, True), (25, False)], ids=["at-limit", "over-limit"]
)
def test_the_quality_gate_counts_missing_time_steps(
    api, validator_for, missing, included, place
):
    # BS-010: 2010-01..04 has 120 days, so 24 missing days is one in five. A
    # Region's Series and a Selected area's are gated on different paths.
    client, use = api
    use(
        NativeGridSource(
            lambda stamp, cell: (
                None if stamp < datetime(2010, 1, 1) + timedelta(days=missing) else 1.0
            ),
            hours=3,
        )
    )
    data = series_of(
        client, explore(client, "daily", end="2010-04", **place), validator_for
    )
    quality = data["series"][0]["quality"]
    assert quality["included"] is included
    assert quality["missing_fraction"] == pytest.approx(missing / 120)
    assert quality["exclusions"] == (
        [] if included else ["too_many_missing_time_steps"]
    )


def test_a_variable_without_data_at_the_time_step_is_refused(api, validator_for):
    client, use = api
    source = use(NativeGridSource(constant(1.0)))
    response = explore(client, "daily", variables=("vegetation-index",))
    assert response.status_code == 422
    validator_for(RESPONSES, "#/$defs/errorResponse").validate(response.json())
    assert response.json()["error"]["code"] == "variable_not_available_at_time_step"
    assert "daily" in response.json()["error"]["message"]
    assert source.calls == 0


def test_the_options_name_the_variables_and_limits_of_each_time_step(
    api, validator_for
):
    client, _ = api
    body = client.get("/api/explore/options").json()
    validator_for(RESPONSES, "#/$defs/exploreOptionsResponse").validate(body)
    steps = body["data"]["time_steps"]
    assert [step["time_step"] for step in steps] == ["3-hourly", "daily", "monthly"]
    by_step = {step["time_step"]: step for step in steps}
    for name, months, label in (("3-hourly", 12, "1 year"), ("daily", 120, "10 years")):
        assert by_step[name]["max_months"] == months
        assert by_step[name]["limit"] == label
        assert by_step[name]["variable_ids"] == [
            "temperature",
            "precipitation",
            "soil-moisture",
        ]
    assert by_step["monthly"]["max_months"] is None
    assert "vegetation-index" in by_step["monthly"]["variable_ids"]


def test_seed_discoveries_are_unchanged_by_the_time_step_quality_gate():
    # #80 acceptance: the gate that counts missing Time steps, applied to the
    # committed monthly seed Series, gives the same verdicts and Discoveries.
    import dataclasses
    import json
    from pathlib import Path

    from data.data_gathering.quality_gate import assess_quality
    from engine import Series, compute_seed_set, load_catalog
    from engine.contracts import as_dict

    seed = Path(__file__).resolve().parents[1] / "data" / "seed"
    catalog = load_catalog(seed.parent / "catalog.json")
    regated = []
    for path in sorted((seed / "series").glob("*.json")):
        series = Series.from_dict(json.loads(path.read_text()))
        quality = assess_quality(
            list(series.values),
            land_only=series.quality.valid_land_fraction is not None,
            valid_land_fraction=series.quality.valid_land_fraction,
            time_step="monthly",
        )
        assert (quality.included, quality.missing_fraction) == (
            series.quality.included,
            series.quality.missing_fraction,
        ), path.name
        regated.append(dataclasses.replace(series, quality=quality))

    def by_id(discoveries):
        return sorted(discoveries, key=lambda item: item["discovery_id"])

    committed = [
        json.loads(path.read_text()) for path in (seed / "discoveries").glob("*.json")
    ]
    built = [
        json.loads(json.dumps(as_dict(item)))
        for item in compute_seed_set(regated, catalog).discoveries
    ]
    assert committed
    # The seed set may be built on another machine: floats can differ in their
    # last digit. Anything else, or a larger difference, is a real change.
    assert _differences(by_id(built), by_id(committed)) == []


def _differences(built, stored, path="discoveries"):
    import math

    if isinstance(built, float) or isinstance(stored, float):
        same = isinstance(built, (int, float)) and isinstance(stored, (int, float))
        return [] if same and math.isclose(built, stored, rel_tol=1e-9) else [path]
    if isinstance(built, dict) and isinstance(stored, dict):
        if built.keys() != stored.keys():
            return [path + " keys"]
        return [
            found
            for key in built
            for found in _differences(built[key], stored[key], f"{path}.{key}")
        ]
    if isinstance(built, list) and isinstance(stored, list):
        if len(built) != len(stored):
            return [path + " length"]
        return [
            found
            for n, (a, b) in enumerate(zip(built, stored))
            for found in _differences(a, b, f"{path}[{n}]")
        ]
    return [] if built == stored else [path]
