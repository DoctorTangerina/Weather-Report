"""Seam 2: the HTTP contract the frontend builds against.

Covers the two BS-009 scenarios this ticket is responsible for (a stored result
is returned, a Region outside the catalog is rejected). Live fetch and fallback
are ticket #13.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app

RESPONSES = "responses.schema.json"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_health_reports_the_engine_version(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["engine_version"]


def test_catalog_response_matches_the_contract(client, validator_for):
    response = client.get("/api/catalog")
    assert response.status_code == 200
    validator_for(RESPONSES, "#/$defs/catalogResponse").validate(response.json())


def test_a_stored_series_is_returned(client, validator_for):
    response = client.get("/api/series", params={"region_id": "sahel", "variable_id": "temperature"})
    assert response.status_code == 200
    validator_for(RESPONSES, "#/$defs/seriesResponse").validate(response.json())
    assert response.json()["data"]["region_id"] == "sahel"
    assert response.json()["notice"] is None


def test_a_region_outside_the_catalog_is_rejected(client, validator_for):
    response = client.get(
        "/api/series", params={"region_id": "my-back-garden", "variable_id": "temperature"}
    )
    assert response.status_code == 422
    validator_for(RESPONSES, "#/$defs/errorResponse").validate(response.json())
    assert response.json()["error"]["code"] == "region_not_in_catalog"


def test_a_variable_outside_the_catalog_is_rejected(client):
    response = client.get(
        "/api/series", params={"region_id": "sahel", "variable_id": "chlorophyll"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "variable_not_in_catalog"


def test_a_period_with_no_stored_result_is_reported_as_unavailable(client):
    response = client.get(
        "/api/series",
        params={
            "region_id": "sahel",
            "variable_id": "temperature",
            "period_start": "2010-01",
            "period_end": "2019-12",
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "result_not_available"


def test_discoveries_are_listed_highest_scoring_first(client, validator_for):
    response = client.get("/api/discoveries")
    assert response.status_code == 200
    validator_for(RESPONSES, "#/$defs/discoveryListResponse").validate(response.json())
    scores = [discovery["score"] for discovery in response.json()["data"]]
    assert scores == sorted(scores, reverse=True)


def test_one_discovery_is_served_by_id(client, validator_for):
    response = client.get("/api/discoveries/amazon-basin--sahel")
    assert response.status_code == 200
    validator_for(RESPONSES, "#/$defs/discoveryResponse").validate(response.json())


def test_surprise_me_never_headlines_a_weak_discovery(client, validator_for):
    response = client.post("/api/discoveries/surprise", json={})
    assert response.status_code == 200
    validator_for(RESPONSES, "#/$defs/discoveryResponse").validate(response.json())
    assert response.json()["data"]["headline_eligible"] is True


def test_surprise_me_runs_out_rather_than_repeating_a_region(client):
    first = client.post("/api/discoveries/surprise", json={}).json()["data"]
    second = client.post(
        "/api/discoveries/surprise",
        json={
            "shown_discovery_ids": [first["discovery_id"]],
            "shown_region_ids": first["region_ids"],
        },
    )
    assert second.status_code == 404
    assert second.json()["error"]["code"] == "no_discovery_left_in_session"
