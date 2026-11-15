"""Seam 1 for #83: the stateless Processing recipe endpoint (spec #72, BS-011).

Source series are built here exactly as /api/explore/series returns them, and
validated against the Series schema before use; the data-layer processing of
#46 (#47-#53) runs for real behind the endpoint.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from api.main import app

RESPONSES = "responses.schema.json"
ENDPOINT = "/api/explore/process"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def days_in(year):
    start = date(year, 1, 1)
    return [
        start + timedelta(days=n) for n in range((date(year + 1, 1, 1) - start).days)
    ]


def source_series(values, period=("2010-01", "2010-12"), **place):
    """A Source series as /api/explore/series returns it (no timestamps)."""
    return {
        **(place or {"region_id": "sahel"}),
        "variable_id": "temperature",
        "period": {"start": period[0], "end": period[1]},
        "units": "°C",
        "values": values,
        "quality": {
            "included": True,
            "missing_fraction": 0.0,
            "valid_land_fraction": None,
            "exclusions": [],
        },
        "source": {
            "provider": "GES DISC",
            "dataset": "MERRA-2 M2T1NXSLV v5.12.4",
            "variable": "T2M",
            "url": "https://doi.org/10.5067/VJAFPLI1CSIV",
        },
        "engine_version": "test",
    }


def sahel_daily_2010():
    # Warm in the middle of the year: a smooth, known shape.
    return [20.0 + 10.0 * (1 - abs(day.month - 6.5) / 5.5) for day in days_in(2010)]


def daily_input(values=None, aggregation="mean", **series):
    return {
        "time_step": "daily",
        "aggregation": aggregation,
        "series": series.get("series") or source_series(values or sahel_daily_2010()),
    }


RECIPE = [
    {"id": "anomaly", "operation": "zscore", "input": "temperature", "ddof": 0},
    {
        "id": "monthly",
        "operation": "resample",
        "input": "anomaly",
        "frequency": "month",
    },
]


def process(client, series, operations=RECIPE):
    return client.post(ENDPOINT, json={"series": series, "operations": operations})


def refused(response, validator_for, code="processing_refused"):
    assert response.status_code == 422, response.json()
    validator_for(RESPONSES, "#/$defs/errorResponse").validate(response.json())
    assert response.json()["error"]["code"] == code
    return response.json()["error"]


def test_the_source_series_used_here_match_the_series_contract(validator_for):
    validator_for("series.schema.json").validate(source_series(sahel_daily_2010()))
    area = source_series([1.0] * 365, area={"rectangles": [[170, -5, -170, 5]]})
    validator_for("series.schema.json", "#/$defs/areaSeries").validate(area)


def test_replaying_a_recipe_returns_an_identical_derived_series(client, validator_for):
    # BS-011: the same Source series and Processing recipe give the same result.
    request = {"series": {"temperature": daily_input()}, "operations": RECIPE}
    validator_for(RESPONSES, "#/$defs/processingRequest").validate(request)
    first = client.post(ENDPOINT, json=request)
    assert first.status_code == 200, first.json()
    validator_for(RESPONSES, "#/$defs/processingResponse").validate(first.json())
    second = client.post(ENDPOINT, json=request)
    assert second.json() == first.json()
    monthly = first.json()["data"]["series"]["monthly"]
    assert len(monthly["values"]) == 12
    assert monthly["time_step"] == "monthly"


def test_a_derived_series_keeps_its_recipe_and_input_provenance(client):
    # BS-011: the Derived series carries the recipe and the source's provenance.
    data = process(client, {"temperature": daily_input()}).json()["data"]
    anomaly = data["series"]["anomaly"]
    assert anomaly["recipe"] == {"operations": RECIPE[:1]}
    assert data["series"]["monthly"]["recipe"] == {"operations": RECIPE}
    assert data["recipe"] == {"operations": RECIPE}
    provenance = anomaly["provenance"]["temperature"]
    assert provenance["region_id"] == "sahel"
    assert provenance["variable_id"] == "temperature"
    assert provenance["period"] == {"start": "2010-01", "end": "2010-12"}
    assert provenance["time_step"] == "daily"
    assert provenance["source"]["dataset"] == "MERRA-2 M2T1NXSLV v5.12.4"
    assert data["series"]["monthly"]["provenance"]["anomaly"]["recipe"] == {
        "operations": RECIPE[:1]
    }


def test_source_timestamps_follow_the_time_step(client):
    data = process(
        client,
        {"temperature": daily_input()},
        [{"id": "same", "operation": "minmax", "input": "temperature"}],
    ).json()["data"]
    stamps = data["series"]["same"]["timestamps"]
    assert len(stamps) == 365
    assert stamps[0].startswith("2010-01-01") and stamps[-1].startswith("2010-12-31")


def test_a_3_hourly_source_series_resamples_to_daily_means(client):
    values = [float(n % 8) for n in range(31 * 8)]  # 0..7 within each UTC day
    data = process(
        client,
        {
            "t": {
                "time_step": "3-hourly",
                "aggregation": "mean",
                "series": source_series(values, period=("2010-01", "2010-01")),
            }
        },
        [{"id": "daily", "operation": "resample", "input": "t", "frequency": "day"}],
    ).json()["data"]
    assert data["series"]["daily"]["values"] == pytest.approx([3.5] * 31)


def test_a_monthly_source_series_is_processed_too(client):
    series = source_series([float(month) for month in range(1, 13)])
    data = process(
        client,
        {"t": {"time_step": "monthly", "aggregation": "mean", "series": series}},
        [{"id": "scaled", "operation": "minmax", "input": "t"}],
    ).json()["data"]
    scaled = data["series"]["scaled"]
    assert [stamp[:7] for stamp in scaled["timestamps"]] == [
        f"2010-{month:02d}" for month in range(1, 13)
    ]
    assert scaled["values"] == pytest.approx([n / 11 for n in range(12)])
    assert scaled["time_step"] == "monthly"


def test_a_resampled_derived_series_reports_its_sample_counts(client):
    data = process(client, {"temperature": daily_input()}).json()["data"]
    resampling = data["series"]["monthly"]["resampling"]
    assert resampling["sample_counts"][:3] == [31, 28, 31]
    assert resampling["valid_counts"][:3] == [31, 28, 31]
    assert data["warnings"] == []


def test_the_view_aggregation_travels_into_resampling(client):
    # #48: a daily maximum Series is combined over time by maximum too.
    values = [float(day.day) for day in days_in(2010)]
    data = process(
        client,
        {"t": daily_input(values, aggregation="maximum")},
        [
            {
                "id": "monthly",
                "operation": "resample",
                "input": "t",
                "frequency": "month",
            }
        ],
    ).json()["data"]
    assert data["series"]["monthly"]["values"][:3] == [31.0, 28.0, 31.0]
    assert data["series"]["monthly"]["resampling"]["aggregation"] == "max"


def test_a_derived_series_can_be_sent_back_as_an_input(client):
    first = process(client, {"temperature": daily_input()}).json()["data"]
    again = process(
        client,
        {"monthly": {"derived": first["series"]["monthly"]}},
        [{"id": "scaled", "operation": "minmax", "input": "monthly"}],
    )
    assert again.status_code == 200, again.json()
    scaled = again.json()["data"]["series"]["scaled"]
    assert min(scaled["values"]) == 0.0 and max(scaled["values"]) == 1.0
    assert scaled["provenance"]["monthly"]["recipe"] == {"operations": RECIPE}


def test_a_selected_area_source_series_keeps_its_area(client):
    area = {"rectangles": [[170, -5, -170, 5]]}
    series = source_series(sahel_daily_2010(), area=area)
    data = process(client, {"temperature": daily_input(series=series)}).json()["data"]
    assert data["series"]["anomaly"]["provenance"]["temperature"]["area"] == area


def test_nothing_is_kept_between_requests(client, validator_for):
    # A later request cannot refer to an earlier request's output by name.
    process(client, {"temperature": daily_input()})
    error = refused(
        process(
            client,
            {"temperature": daily_input()},
            [{"id": "again", "operation": "minmax", "input": "monthly"}],
        ),
        validator_for,
    )
    assert error["details"]["reason"] == "unknown_input"


@pytest.mark.parametrize(
    "operation",
    [
        {"id": "x", "operation": "fourier", "input": "temperature"},
        {"id": "x", "operation": "zscore", "input": "temperature", "ddof": 2},
        {"id": "x", "operation": "minmax", "input": "temperature", "smooth": True},
    ],
)
def test_a_step_the_data_layer_does_not_provide_is_refused(
    client, validator_for, operation
):
    error = refused(
        process(client, {"temperature": daily_input()}, [operation]), validator_for
    )
    assert error["details"]["reason"] in {
        "invalid_operation",
        "invalid_scaling_parameters",
    }
    assert error["details"]["operation"] == 0
    assert error["message"]


def test_an_excluded_source_series_is_refused(client, validator_for):
    series = source_series([None] * 365)
    series["quality"] = {
        "included": False,
        "missing_fraction": 1.0,
        "valid_land_fraction": None,
        "exclusions": ["too_many_missing_time_steps"],
    }
    error = refused(
        process(client, {"temperature": daily_input(series=series)}), validator_for
    )
    assert error["details"]["reason"] == "excluded_series"


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        [],
        {"operations": RECIPE},
        {"series": {}, "operations": RECIPE},
        {"series": {"temperature": {"derived": {}}}, "operations": []},
        {"series": {"temperature": {"series": {}}}, "operations": RECIPE},
        {"series": {"t": {"time_step": "hourly", "aggregation": "mean", "series": {}}}},
    ],
)
def test_a_malformed_request_is_refused(client, validator_for, body):
    if isinstance(body, str):
        response = client.post(
            ENDPOINT, content=body, headers={"Content-Type": "application/json"}
        )
    else:
        response = client.post(ENDPOINT, json=body)
    refused(response, validator_for, "invalid_processing_request")


def test_a_source_series_whose_length_does_not_fit_its_period_is_refused(
    client, validator_for
):
    error = refused(
        process(client, {"temperature": daily_input([1.0] * 364)}),
        validator_for,
        "invalid_processing_request",
    )
    assert "365" in error["message"]
