"""#60–#62 S2: identifiers through HTTP into real data-layer correlation."""

import pytest
from fastapi.testclient import TestClient

from api import main
from engine import ENGINE_VERSION


def payload(variable, values, *, region="sahel", step="monthly", **metadata):
    return {
        "engine_version": ENGINE_VERSION,
        "region_id": region,
        "variable_id": variable,
        "period": {"start": "2024-01", "end": "2024-03"},
        "timestamps": ["2024-01-01", "2024-02-01", "2024-03-01"],
        "values": values,
        "units": "K",
        "time_step": step,
        "aggregation": "mean",
        "quality": {"included": True, "missing_fraction": 0},
        **metadata,
    }


@pytest.fixture
def client(monkeypatch):
    class Store:
        def all_series(self):
            return [
                payload("temperature", [1, 2, 3]),
                payload("precipitation", [2, 4, 6]),
            ]

    monkeypatch.setattr(main, "store", Store())
    monkeypatch.setattr(
        main, "live_store", type("Empty", (), {"all_series": lambda self: []})()
    )
    return TestClient(main.app)


def request(**changes):
    return {
        "variables": ["temperature", "precipitation"],
        "area": "sahel",
        "period": {"start": "2024-01", "end": "2024-03"},
        **changes,
    }


def test_named_series_through_http_returns_numeric_matrix(client, validator_for):
    response = client.post("/api/correlation-map", json=request())
    assert response.status_code == 200
    body = response.json()
    validator_for("correlation-map.schema.json", "#/$defs/response").validate(body)
    assert body["notice"] is None
    assert body["data"]["matrix"] == [[1, 1], [1, 1]]
    assert body["data"]["observation_count"] == 3
    assert [x["variable"] for x in body["data"]["inputs"]] == [
        "temperature",
        "precipitation",
    ]


def test_unavailable_input_is_excluded_without_losing_valid_map(client):
    response = client.post(
        "/api/correlation-map",
        json=request(variables=["temperature", "vegetation-index", "precipitation"]),
    )
    assert response.status_code == 200
    assert response.json()["data"]["excluded"][0]["variable"] == "vegetation-index"
    assert len(response.json()["data"]["matrix"]) == 2


def test_failure_details_reach_frontend_not_just_message(client, validator_for):
    response = client.post(
        "/api/correlation-map",
        json=request(variables=["temperature", "vegetation-index"]),
    )
    assert response.status_code == 422
    validator_for("correlation-map.schema.json", "#/$defs/error").validate(
        response.json()
    )
    error = response.json()["error"]
    assert error["code"] == "insufficient_inputs"
    assert error["details"]["excluded"][0]["variable"] == "vegetation-index"


def test_prepared_expression_loads_inputs_by_identifier_and_keeps_provenance(client):
    response = client.post(
        "/api/correlation-map",
        json=request(
            variables=[
                "temperature",
                {
                    "id": "derived",
                    "variable": "double",
                    "area": "derived",
                    "label": "Twice temperature",
                },
            ],
            derived=[
                {
                    "id": "double",
                    "inputs": {"A": {"variable": "temperature", "area": "sahel"}},
                    "operations": [{"id": "result", "expression": "2 * A"}],
                    "output": "result",
                }
            ],
        ),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["matrix"] == [[1, 1], [1, 1]]
    assert (
        data["inputs"][1]["metadata"]["provenance"]["A"]["variable_id"] == "temperature"
    )


def test_exact_catalog_rectangle_resolves_and_arbitrary_coverage_does_not_substitute(
    client,
):
    region = main.catalog.region("sahel")
    from engine.contracts import as_dict

    area = {"name": "My rectangle", "rectangles": [as_dict(region.bbox)]}
    response = client.post("/api/correlation-map", json=request(area=area))
    assert response.status_code == 200
    area["rectangles"][0]["north"] -= 1
    response = client.post("/api/correlation-map", json=request(area=area))
    assert response.status_code == 422
    assert all(
        x["code"] == "area_unavailable"
        for x in response.json()["error"]["details"]["excluded"]
    )


def test_named_scaling_uses_only_selected_period(client, monkeypatch):
    first = payload(
        "temperature",
        [1, 3, 2, 100],
        timestamps=["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"],
        period={"start": "2024-01", "end": "2024-04"},
    )
    other = payload(
        "precipitation",
        [2, 1, 3, 4],
        timestamps=first["timestamps"],
        period=first["period"],
    )
    monkeypatch.setattr(main.store, "all_series", lambda: [first, other])
    response = client.post(
        "/api/correlation-map",
        json=request(
            variables=[
                "temperature",
                {"id": "scaled", "variable": "scaled", "area": "derived"},
            ],
            derived=[
                {
                    "id": "scaled",
                    "inputs": {
                        "A": {"variable": "temperature", "area": "sahel"},
                        "B": {"variable": "precipitation", "area": "sahel"},
                    },
                    "operations": [
                        {"id": "normalized", "operation": "minmax", "input": "A"},
                        {
                            "id": "result",
                            "expression": "normalized + B",
                            "acknowledge_unit_difference": True,
                        },
                    ],
                    "output": "result",
                }
            ],
        ),
    )
    assert response.status_code == 200
    # Selected-period scaling gives [0, 1, .5] + [2, 1, 3], whose
    # correlation with [1, 3, 2] is zero. April must not affect scaling.
    assert response.json()["data"]["matrix"][0][1] == pytest.approx(0, abs=1e-12)


def test_daily_and_monthly_inputs_require_explicit_common_step(client, monkeypatch):
    daily = payload("temperature", [1, 2, 3], step="daily")
    monkeypatch.setattr(
        main.store, "all_series", lambda: [daily, payload("precipitation", [2, 4, 6])]
    )
    response = client.post("/api/correlation-map", json=request())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "resampling_required"
    response = client.post("/api/correlation-map", json=request(time_step="monthly"))
    assert response.status_code == 200
    assert response.json()["data"]["matrix"] == [[1, 1], [1, 1]]
    assert response.json()["data"]["settings"]["timezone"] == "UTC"


def test_resource_failure_through_http_has_actionable_error(client, monkeypatch):
    def exhausted():
        raise MemoryError

    monkeypatch.setattr(main.store, "all_series", exhausted)
    response = client.post("/api/correlation-map", json=request())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "resource_exhausted"
    assert "Reduce" in response.json()["error"]["message"]


def test_same_variable_in_different_areas_and_dataset_labels_are_distinct(
    client, monkeypatch
):
    inventory = [
        payload("temperature", [1, 2, 3], dataset_id="dataset-a"),
        payload("temperature", [3, 2, 1], dataset_id="dataset-b"),
        payload(
            "temperature", [2, 4, 6], region="amazon-basin", dataset_id="dataset-a"
        ),
    ]
    monkeypatch.setattr(main.store, "all_series", lambda: inventory)
    response = client.post(
        "/api/correlation-map",
        json=request(
            variables=[
                {"variable": "temperature", "area": "sahel", "dataset_id": "dataset-a"},
                {"variable": "temperature", "area": "sahel", "dataset_id": "dataset-b"},
                {
                    "variable": "temperature",
                    "area": "amazon-basin",
                    "dataset_id": "dataset-a",
                },
            ]
        ),
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert len({item["label"] for item in result["inputs"]}) == 3
    assert result["matrix"] == [[1, -1, 1], [-1, 1, -1], [1, -1, 1]]


def test_quality_rejection_and_constant_results_are_explained_over_http(
    client, monkeypatch
):
    monkeypatch.setattr(
        main.store,
        "all_series",
        lambda: [
            payload("temperature", [1, 2, 3]),
            payload("precipitation", [2, 4, 6]),
            payload(
                "soil-moisture",
                [1, 2, 3],
                quality={
                    "included": False,
                    "exclusions": ["insufficient_land_fraction"],
                },
            ),
            payload("vegetation-index", [5, 5, 5]),
        ],
    )
    response = client.post(
        "/api/correlation-map",
        json=request(
            variables=[
                "temperature",
                "soil-moisture",
                "vegetation-index",
                "precipitation",
            ]
        ),
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert [item["variable"] for item in result["inputs"]] == [
        "temperature",
        "precipitation",
    ]
    assert {item["code"] for item in result["excluded"]} == {
        "excluded_series",
        "constant_input",
    }


def test_prepared_calculation_cannot_supply_raw_values(client):
    response = client.post(
        "/api/correlation-map",
        json=request(
            variables=[
                "temperature",
                {"id": "D", "variable": "bad", "area": "derived"},
            ],
            derived=[
                {
                    "id": "bad",
                    "inputs": {
                        "A": {
                            "variable": "temperature",
                            "area": "sahel",
                            "values": [1, 2, 3],
                        }
                    },
                    "operations": [{"id": "result", "expression": "A * 2"}],
                    "output": "result",
                }
            ],
        ),
    )
    assert response.status_code == 422
    assert (
        response.json()["error"]["details"]["excluded"][0]["code"] == "invalid_derived"
    )
