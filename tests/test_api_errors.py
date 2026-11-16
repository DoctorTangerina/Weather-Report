"""Every error the API returns uses the documented envelope (errorResponse).

FastAPI's own errors (request validation, unknown routes, wrong methods) used to
come back as {"detail": ...}, which clients and the schema do not expect.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def envelope(response, validator_for, status, code):
    assert response.status_code == status, response.text
    validator_for("responses.schema.json", "#/$defs/errorResponse").validate(
        response.json()
    )
    assert response.json()["error"]["code"] == code
    return response.json()["error"]["message"]


@pytest.mark.parametrize(
    "body",
    [
        None,
        [],
        {"shown_discovery_ids": "not a list"},
        {"shown_region_ids": [1, 2]},
    ],
)
def test_a_malformed_surprise_body_is_an_envelope_error(client, validator_for, body):
    response = client.post("/api/discoveries/surprise", json=body)
    envelope(response, validator_for, 422, "invalid_request")


def test_a_non_json_surprise_body_is_an_envelope_error(client, validator_for):
    response = client.post(
        "/api/discoveries/surprise",
        content=b"not json",
        headers={"Content-Type": "application/json"},
    )
    envelope(response, validator_for, 422, "invalid_request")


def test_a_missing_required_parameter_names_it(client, validator_for):
    message = envelope(
        client.get("/api/series", params={"variable_id": "temperature"}),
        validator_for,
        422,
        "invalid_request",
    )
    assert "region_id" in message


@pytest.mark.parametrize("path", ["/api/nope", "/api/explore/jobs/", "/elsewhere"])
def test_an_unknown_path_is_an_envelope_error(client, validator_for, path):
    envelope(client.get(path), validator_for, 404, "not_found")


def test_a_wrong_method_is_an_envelope_error(client, validator_for):
    envelope(client.delete("/api/catalog"), validator_for, 405, "method_not_allowed")
