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
    response = client.get(
        "/api/series", params={"region_id": "sahel", "variable_id": "temperature"}
    )
    assert response.status_code == 200
    validator_for(RESPONSES, "#/$defs/seriesResponse").validate(response.json())
    assert response.json()["data"]["region_id"] == "sahel"
    assert response.json()["notice"] is None
    assert response.json()["provenance"] == "preloaded"


def test_a_region_outside_the_catalog_is_rejected(client, validator_for):
    response = client.get(
        "/api/series",
        params={"region_id": "my-back-garden", "variable_id": "temperature"},
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


def test_a_period_with_no_stored_result_returns_a_labelled_example(client):
    response = client.get(
        "/api/series",
        params={
            "region_id": "sahel",
            "variable_id": "temperature",
            "period_start": "2010-01",
            "period_end": "2019-12",
        },
    )
    assert response.status_code == 200
    assert response.json()["notice"]["code"] == "live_data_unavailable"
    assert response.json()["provenance"] == "preloaded"


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


def test_surprise_me_keeps_answering_when_only_a_shared_region_is_left(client):
    """Both headline-eligible stub Candidates involve the Sahel, so the Region
    rule has to give way rather than dead-end the session."""
    first = client.post("/api/discoveries/surprise", json={}).json()["data"]
    second = client.post(
        "/api/discoveries/surprise",
        json={
            "shown_discovery_ids": [first["discovery_id"]],
            "shown_region_ids": first["region_ids"],
        },
    )
    assert second.status_code == 200
    assert second.json()["data"]["discovery_id"] != first["discovery_id"]


def test_surprise_me_returns_nothing_once_every_eligible_discovery_is_shown(client):
    shown = [
        discovery["discovery_id"]
        for discovery in client.get("/api/discoveries").json()["data"]
        if discovery["headline_eligible"]
    ]
    response = client.post(
        "/api/discoveries/surprise", json={"shown_discovery_ids": shown}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "no_discovery_left_in_session"


def test_surprise_me_never_serves_the_weak_discovery_however_often_it_is_asked(client):
    served = {
        client.post("/api/discoveries/surprise", json={}).json()["data"]["discovery_id"]
        for _ in range(40)
    }
    assert served == {"amazon-basin--sahel", "central-india--sahel"}


def test_the_service_lists_the_series_it_holds(client, validator_for):
    response = client.get("/api/series/available")
    assert response.status_code == 200
    validator_for(RESPONSES, "#/$defs/availableSeriesResponse").validate(
        response.json()
    )
    pairs = {(s["region_id"], s["variable_id"]) for s in response.json()["data"]}
    assert ("amazon-basin", "temperature") in pairs


def test_every_listed_series_can_actually_be_fetched(client):
    for item in client.get("/api/series/available").json()["data"]:
        response = client.get(
            "/api/series",
            params={
                "region_id": item["region_id"],
                "variable_id": item["variable_id"],
                "period_start": item["period"]["start"],
                "period_end": item["period"]["end"],
            },
        )
        assert response.status_code == 200, item


def test_a_pair_missing_from_the_list_cannot_be_compared(client):
    pairs = {
        (s["region_id"], s["variable_id"])
        for s in client.get("/api/series/available").json()["data"]
    }
    assert ("congo-basin", "temperature") not in pairs
    response = client.get(
        "/api/comparison",
        params={
            "region_a": "amazon-basin",
            "region_b": "congo-basin",
            "variable_id": "temperature",
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "result_not_available"
