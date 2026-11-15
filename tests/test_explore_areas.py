"""Seam 1 for #79: Series on demand for a Selected area, through background jobs.

BS-009 (geometry: cell centres, joined rectangles, the antimeridian), BS-005
(an area gets the same Series as a Region would), BS-003's Excluded series, and
the rule that a Selected area never becomes a Region or feeds a Discovery. Only
the acquisition source is replaced; the reduction to Series is the real one.
"""

import time
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from api import main
from engine import ENGINE_VERSION, JsonResultStore
from tests.fake_acquisition import FakeGridAcquisitionSource

UNITS = {"temperature": "°C", "precipitation": "mm/month", "soil-moisture": "mm"}
# Four equal-area cells on the equator, two on each side of the antimeridian.
LONGITUDES = [165.0, 175.0, -175.0, -165.0]


class AreaSource(FakeGridAcquisitionSource):
    calls = 0

    def prepare(self, request, *, fetch=False):
        self.calls += 1
        grid = replace(self, units=UNITS[request["variable_id"]])
        return FakeGridAcquisitionSource.prepare(grid, request, fetch=fetch)


def grid(row, land=None):
    """One latitude row, the same values in January and February 2025."""
    return AreaSource(
        timestamps=["2025-01-01T00:00:00", "2025-02-01T00:00:00"],
        latitudes=[0.0],
        longitudes=LONGITUDES,
        values=[[row], [row]],
        units="°C",
        land_mask=land,
    )


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("WEATHER_REPORT_LATEST_MONTH", "2025-02")
    monkeypatch.setattr(main, "live_store", JsonResultStore(tmp_path, ENGINE_VERSION))
    monkeypatch.setattr(main, "area_cache", main.AreaSeriesCache(tmp_path / "areas"))
    sources = {"current": grid([0.0, 1.0, 1.0, 0.0])}
    main.app.dependency_overrides[main.get_acquisition_source] = lambda: sources[
        "current"
    ]
    with TestClient(main.app) as client:
        yield client, sources
    main.app.dependency_overrides.clear()


def ask(client, rectangles, variables=("temperature",), **params):
    return client.get(
        "/api/explore/series",
        params={
            "rectangle": [",".join(map(str, box)) for box in rectangles],
            "variable_id": list(variables),
            "period_start": "2025-01",
            "period_end": "2025-02",
            **params,
        },
    )


def finished(client, response, validator_for):
    assert response.status_code == 202, response.json()
    job = response.json()["data"]["job"]
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        body = client.get(job["url"]).json()
        validator_for("responses.schema.json", "#/$defs/exploreJobResponse").validate(
            body
        )
        job = body["data"]["job"]
        if job["status"] in {"succeeded", "failed"}:
            assert job["status"] == "succeeded", job
            return job["result"]
        time.sleep(0.02)
    pytest.fail("Job did not finish")


def values(client, rectangles, validator_for, variable="temperature"):
    result = finished(client, ask(client, rectangles, (variable,)), validator_for)
    return result["series"][0]


def test_an_area_crossing_the_antimeridian_covers_cells_on_both_sides(
    api, validator_for
):
    # BS-009: cells between 170°E and 170°W hold 1, the others 0.
    client, _ = api
    series = values(client, [(170, -5, -170, 5)], validator_for)
    assert series["values"] == pytest.approx([1.0, 1.0])


def test_a_cell_counts_only_when_its_centre_is_inside(api, validator_for):
    client, sources = api
    sources["current"] = grid([10.0, 20.0, 30.0, 40.0])
    # 175.2°E–174°W overlaps the 175°E cell's edge but holds only the 175°W centre.
    series = values(client, [(175.2, -5, -174, 5)], validator_for)
    assert series["values"] == pytest.approx([30.0, 30.0])


def test_joined_rectangles_count_a_shared_cell_once(api, validator_for):
    client, sources = api
    sources["current"] = grid([0.0, 1.0, 3.0, 0.0])
    # Both rectangles hold the 175°E cell; the union is 165°E, 175°E and 175°W.
    series = values(client, [(164, -5, 176, 5), (174, -5, -174, 5)], validator_for)
    assert series["values"] == pytest.approx([4 / 3, 4 / 3])


def test_a_cell_shared_by_two_overlapping_rectangles_counts_once(api, validator_for):
    # BS-009 (#81): three equal-area cells, the middle one in both rectangles.
    # The 165°E cell is outside the area; it holds 100 so selecting it shows.
    client, sources = api
    sources["current"] = grid([100.0, 0.0, 6.0, 0.0])
    # The first holds 175°E and 175°W; the second 175°W and 165°W.
    series = values(client, [(170, -5, -170, 5), (-178, -5, -160, 5)], validator_for)
    assert series["values"] == pytest.approx([2.0, 2.0])


def test_joined_rectangles_meeting_at_the_antimeridian_select_both_sides(
    api, validator_for
):
    # #81: an area joined across 180° takes the cells on each side, and no others.
    client, sources = api
    sources["current"] = grid([1.0, 2.0, 4.0, 100.0])
    series = values(client, [(160, -5, 180, 5), (-180, -5, -170, 5)], validator_for)
    assert series["values"] == pytest.approx([7 / 3, 7 / 3])


def test_a_joined_area_crossing_the_antimeridian_selects_both_sides(api, validator_for):
    # #81: one rectangle crossing 180°, joined to one west of 180° along 170°W.
    # Only the first holds the 175°W cell, so it must reach past 180° to get it.
    client, sources = api
    sources["current"] = grid([1.0, 2.0, 4.0, 8.0])
    series = values(client, [(170, -5, -170, 5), (-170, -5, -160, 5)], validator_for)
    assert series["values"] == pytest.approx([14 / 3, 14 / 3])


def two_rows():
    """Equal-area cells at (5°S, 0°)=1, (5°S, 10°E)=2, (5°N, 0°)=3, (5°N, 10°E)=100."""
    return AreaSource(
        timestamps=["2025-01-01T00:00:00", "2025-02-01T00:00:00"],
        latitudes=[-5.0, 5.0],
        longitudes=[0.0, 10.0],
        values=[[[1.0, 2.0], [3.0, 100.0]]] * 2,
        units="°C",
    )


def test_a_cell_whose_edge_but_not_centre_is_inside_is_left_out(api, validator_for):
    client, sources = api
    sources["current"] = two_rows()
    # Up to 4.8°N reaches into the 5°N cells (from 4.5°N) but not their centres.
    series = values(client, [(-1, -6, 11, 4.8)], validator_for)
    assert series["values"] == pytest.approx([1.5, 1.5])


def test_an_l_shaped_area_leaves_out_the_cells_neither_rectangle_holds(
    api, validator_for
):
    client, sources = api
    sources["current"] = two_rows()
    # An L: along 5°S, then up the prime meridian. The 5°N 10°E cell is outside.
    series = values(client, [(-1, -6, 11, -4), (-1, -6, 1, 6)], validator_for)
    assert series["values"] == pytest.approx([2.0, 2.0])


def test_an_area_gets_the_same_view_as_a_region(api, validator_for):
    # BS-005: the response describes the area where a Region's id would be.
    client, _ = api
    rectangles = [(170, -5, -170, 5)]
    result = finished(
        client, ask(client, rectangles, ("temperature", "precipitation")), validator_for
    )
    assert result["area"] == {"rectangles": [[170, -5, -170, 5]]}
    assert "region_id" not in result
    assert [s["variable_id"] for s in result["series"]] == [
        "temperature",
        "precipitation",
    ]
    assert all(s["area"] == result["area"] for s in result["series"])
    assert all("region_id" not in s for s in result["series"])
    assert result["series"][1]["units"] == "mm/month"


def test_soil_moisture_over_open_ocean_is_an_excluded_series(api, validator_for):
    # BS-003: no grid cell in the area is valid land.
    client, sources = api
    sources["current"] = grid([5.0, 5.0, 5.0, 5.0], land=[[0, 0, 0, 0]])
    series = values(client, [(170, -5, -170, 5)], validator_for, "soil-moisture")
    assert series["quality"]["included"] is False
    assert "insufficient_land_fraction" in series["quality"]["exclusions"]
    assert series["quality"]["valid_land_fraction"] == 0
    assert series["values"] == [None, None]


def test_a_repeated_area_request_is_answered_from_the_cache(api, validator_for):
    client, sources = api
    rectangles = [(170, -5, -170, 5)]
    result = finished(client, ask(client, rectangles), validator_for)
    response = ask(client, rectangles)
    assert response.status_code == 200
    validator_for("responses.schema.json", "#/$defs/exploreSeriesResponse").validate(
        response.json()
    )
    assert response.json()["data"] == result
    assert response.json()["provenance"] == "cache"
    assert sources["current"].calls == 1


def test_a_selected_area_never_becomes_a_region_or_a_discovery(api, validator_for):
    client, _ = api
    before = {
        path: client.get(path).json()
        for path in ("/api/catalog", "/api/discoveries", "/api/series/available")
    }
    finished(client, ask(client, [(170, -5, -170, 5)]), validator_for)
    for path, body in before.items():
        assert client.get(path).json() == body, path


@pytest.mark.xfail(
    strict=True,
    reason="Daily Time steps arrive with #80; until then the API answers 501.",
)
def test_daily_area_series_do_not_change_the_discoveries(api, validator_for):
    # BS-013 (#81): Series for a Selected area at a daily Time step.
    client, _ = api
    before = client.get("/api/discoveries").json()
    response = ask(client, [(170, -5, -170, 5)], time_step="daily")
    finished(client, response, validator_for)
    assert client.get("/api/discoveries").json() == before


def test_the_options_name_the_variables_an_area_can_have(api, validator_for):
    client, _ = api
    body = client.get("/api/explore/options").json()
    validator_for("responses.schema.json", "#/$defs/exploreOptionsResponse").validate(
        body
    )
    assert body["data"]["area_variable_ids"] == [
        "temperature",
        "precipitation",
        "soil-moisture",
    ]


@pytest.mark.parametrize(
    "params",
    [
        {"rectangle": ["1,2,3"]},
        {"rectangle": ["a,b,c,d"]},
        {"rectangle": ["10,-95,20,0"]},
        {"rectangle": ["10,5,20,5"]},
        {"rectangle": ["10,5,10,6"]},
        {"rectangle": ["190,0,200,5"]},
        {"rectangle": ["nan,0,10,5"]},
        # Rectangles that neither touch nor overlap are not one Selected area.
        {"rectangle": ["0,0,10,10", "20,0,30,10"]},
        {"rectangle": ["0,0,10,10"], "region_id": "sahel"},
        {},
    ],
)
def test_a_malformed_area_is_refused(api, validator_for, params):
    client, sources = api
    query = {"variable_id": ["temperature"], "period_start": "2025-01", **params}
    response = client.get("/api/explore/series", params=query)
    assert response.status_code == 422, response.json()
    validator_for("responses.schema.json", "#/$defs/errorResponse").validate(
        response.json()
    )
    assert response.json()["error"]["code"] == "invalid_area"
    assert sources["current"].calls == 0


@pytest.mark.parametrize(
    "rectangles",
    [
        [(160, -5, 170, 5), (170, -5, 180, 5)],
        # They meet at the antimeridian, where 180° and -180° are one line.
        [(170, -5, 180, 5), (-180, -5, -170, 5)],
    ],
)
def test_rectangles_that_only_touch_make_one_area(api, validator_for, rectangles):
    client, _ = api
    assert ask(client, rectangles).status_code == 202


def test_a_variable_without_on_demand_data_is_refused_for_an_area(api, validator_for):
    client, _ = api
    response = ask(client, [(0, 0, 10, 10)], ("vegetation-index",))
    assert response.status_code == 422
    validator_for("responses.schema.json", "#/$defs/errorResponse").validate(
        response.json()
    )
    assert response.json()["error"]["code"] == "variable_not_available_for_area"
