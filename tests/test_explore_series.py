"""Seam 1 for #75: Series on demand for a catalog Region, answered from the seed set.

BS-007 (a seed Series is returned directly, and requests outside the limits are
refused) and BS-013 (Discoveries are untouched). The API runs on the stub result
set, whose Series all cover 2000-01 to 2024-12.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app

RESPONSES = "responses.schema.json"
ENDPOINT = "/api/explore/series"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def explore(client, variables=("temperature",), **params):
    query = {"region_id": "sahel", "variable_id": list(variables), **params}
    return client.get(ENDPOINT, params=query)


def stored(client, region_id, variable_id):
    response = client.get(
        "/api/series", params={"region_id": region_id, "variable_id": variable_id}
    )
    assert response.json()["provenance"] == "preloaded"
    return response.json()["data"]


def refused(response, validator_for, code):
    assert response.status_code == 422, response.json()
    validator_for(RESPONSES, "#/$defs/errorResponse").validate(response.json())
    assert response.json()["error"]["code"] == code
    return response.json()["error"]["message"]


def test_a_seed_series_is_returned_directly(client, validator_for):
    response = explore(
        client,
        aggregation="mean",
        time_step="monthly",
        period_start="2000-01",
        period_end="2024-12",
    )
    assert response.status_code == 200
    body = response.json()
    validator_for(RESPONSES, "#/$defs/exploreSeriesResponse").validate(body)
    assert body["provenance"] == "preloaded"
    assert body["data"]["series"] == [stored(client, "sahel", "temperature")]
    assert "job" not in body["data"]


def test_the_view_settings_are_echoed_and_default_to_the_seed(client):
    data = explore(client).json()["data"]
    assert data["region_id"] == "sahel"
    assert data["aggregation"] == "mean"
    assert data["time_step"] == "monthly"
    assert data["period"] == {"start": "2000-01", "end": "2024-12"}


def test_each_variable_gets_its_own_series_in_the_requested_order(client):
    variables = ("precipitation", "temperature")
    series = explore(client, variables).json()["data"]["series"]
    assert [item["variable_id"] for item in series] == list(variables)
    assert series == [stored(client, "sahel", v) for v in variables]


def test_a_shorter_period_is_cut_from_the_seed_series(client, validator_for):
    full = stored(client, "sahel", "temperature")
    body = explore(client, period_start="2010-01", period_end="2010-12").json()
    validator_for(RESPONSES, "#/$defs/exploreSeriesResponse").validate(body)
    (series,) = body["data"]["series"]
    assert series["period"] == {"start": "2010-01", "end": "2010-12"}
    assert series["values"] == full["values"][120:132]
    assert body["data"]["period"] == {"start": "2010-01", "end": "2010-12"}


def test_the_quality_gate_is_applied_to_the_period_shown(client):
    # The stub misses 2003-02..04 and 2012-07..08 of Central India precipitation.
    def quality(start, end):
        params = {"period_start": start, "period_end": end}
        (series,) = explore(
            client, ("precipitation",), region_id="central-india", **params
        ).json()["data"]["series"]
        return series

    kept = quality("2012-01", "2012-12")
    assert kept["quality"]["included"] is True
    assert kept["quality"]["missing_fraction"] == pytest.approx(2 / 12)

    excluded = quality("2003-01", "2003-12")
    assert excluded["quality"]["included"] is False
    assert excluded["quality"]["exclusions"] == ["too_many_missing_months"]
    assert excluded["values"] == [None] * 12


def test_a_period_starting_before_2000_is_refused(client, validator_for):
    message = refused(
        explore(client, period_start="1999-12", period_end="2000-12"),
        validator_for,
        "period_out_of_range",
    )
    assert "2000-01" in message
    assert client.get("/api/explore/options").json()["data"]["latest_month"] in message


def test_a_period_ending_after_the_latest_month_is_refused(client, validator_for):
    refused(
        explore(client, period_start="2024-01", period_end="9999-12"),
        validator_for,
        "period_out_of_range",
    )


@pytest.mark.parametrize(
    "start,end", [("2010-13", "2011-01"), ("2011-01", "2010-12"), ("2010", "2011")]
)
def test_a_malformed_period_is_refused(client, validator_for, start, end):
    refused(
        explore(client, period_start=start, period_end=end),
        validator_for,
        "invalid_period",
    )


def test_six_variables_are_refused(client, validator_for):
    six = ("temperature", "precipitation", "soil-moisture") * 2
    message = refused(explore(client, six), validator_for, "invalid_variable_count")
    assert "five" in message


def test_no_variable_is_refused(client, validator_for):
    response = client.get(ENDPOINT, params={"region_id": "sahel"})
    refused(response, validator_for, "invalid_variable_count")


def test_a_variable_named_twice_is_refused(client, validator_for):
    refused(
        explore(client, ("temperature", "temperature")),
        validator_for,
        "duplicate_variable",
    )


@pytest.mark.parametrize(
    "time_step,start,end,limit",
    [
        ("3-hourly", "2010-01", "2011-01", "1 year"),
        ("daily", "2010-01", "2020-12", "10 years"),
    ],
)
def test_a_period_beyond_the_time_step_limit_is_refused(
    client, validator_for, time_step, start, end, limit
):
    message = refused(
        explore(client, time_step=time_step, period_start=start, period_end=end),
        validator_for,
        "period_too_long",
    )
    assert limit in message


@pytest.mark.parametrize(
    "params,code",
    [
        ({"region_id": "my-back-garden"}, "region_not_in_catalog"),
        ({"variable_id": ["sunshine"]}, "variable_not_in_catalog"),
        (
            {"region_id": "north-atlantic", "variable_id": ["soil-moisture"]},
            "variable_not_available_for_region",
        ),
        ({"aggregation": "mode"}, "invalid_aggregation"),
        ({"time_step": "hourly"}, "invalid_time_step"),
    ],
)
def test_requests_outside_the_catalogs_and_glossary_are_refused(
    client, validator_for, params, code
):
    query = {"region_id": "sahel", "variable_id": ["temperature"], **params}
    refused(client.get(ENDPOINT, params=query), validator_for, code)


@pytest.mark.parametrize(
    "params",
    [
        {"aggregation": "maximum"},
        {"time_step": "daily", "period_start": "2010-01", "period_end": "2010-12"},
    ],
)
def test_series_the_seed_set_cannot_answer_are_not_available_yet(
    client, validator_for, params
):
    response = explore(client, **params)
    assert response.status_code == 501
    validator_for(RESPONSES, "#/$defs/errorResponse").validate(response.json())
    assert response.json()["error"]["code"] == "not_available_yet"


def test_a_variable_without_a_stored_series_starts_a_job(client, validator_for):
    # The stub holds no soil moisture for the Sahel.
    response = explore(client, ("temperature", "soil-moisture"))
    assert response.status_code == 202
    validator_for(RESPONSES, "#/$defs/exploreJobResponse").validate(response.json())


def test_explore_requests_leave_the_discoveries_untouched(client):
    before = client.get("/api/discoveries").json()
    explore(client, ("precipitation", "temperature"), period_start="2005-01")
    explore(client, aggregation="maximum")
    assert client.get("/api/discoveries").json() == before
