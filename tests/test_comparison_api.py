"""Issue #16: chosen catalog pairs through the agreed HTTP seam."""

import json

import pytest
from fastapi.testclient import TestClient
from synthetic import series_for

from api.main import app
from engine import ENGINE_VERSION, JsonResultStore
from engine.contracts import as_dict


@pytest.fixture
def client():
    return TestClient(app)


def test_pair_without_a_discovery_returns_computed_trends_and_series(
    client, validator_for, tmp_path, monkeypatch
):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    for region, rate, seed in [("amazon-basin", 0.73, 1), ("central-india", -0.46, 2)]:
        series = series_for(region, "temperature", rate, seed=seed, noise=0.1)
        (series_dir / f"{region}.json").write_text(json.dumps(as_dict(series)))
    monkeypatch.setattr("api.main.store", JsonResultStore(tmp_path, ENGINE_VERSION))
    response = client.get(
        "/api/comparison",
        params={
            "region_a": "amazon-basin",
            "region_b": "central-india",
            "variable_id": "temperature",
        },
    )
    assert response.status_code == 200
    body = response.json()
    validator_for("responses.schema.json", "#/$defs/comparisonResponse").validate(body)
    assert body["notice"] is None
    data = body["data"]
    assert [trend["region_id"] for trend in data["trends"]] == [
        "amazon-basin",
        "central-india",
    ]
    assert [series["region_id"] for series in data["series"]] == [
        "amazon-basin",
        "central-india",
    ]
    # Independently generated rates, different from every stored stub Trend.
    assert data["trends"][0]["rate_per_decade"] == pytest.approx(0.73, abs=0.03)
    assert data["trends"][1]["rate_per_decade"] == pytest.approx(-0.46, abs=0.03)
    assert all(
        trend["multiple_comparisons"]["family_size"] == 2 for trend in data["trends"]
    )
    assert all(trend["evidence_label"] == "Strong evidence" for trend in data["trends"])


@pytest.mark.parametrize(
    ("params", "code"),
    [
        ({"region_a": "outside"}, "region_not_in_catalog"),
        ({"region_b": "outside"}, "region_not_in_catalog"),
        ({"variable_id": "outside"}, "variable_not_in_catalog"),
        ({"region_b": "congo-basin"}, "result_not_available"),
        ({"period_start": "2010-01"}, "result_not_available"),
    ],
)
def test_invalid_or_unavailable_comparison_is_reported(
    client, validator_for, params, code
):
    query = {
        "region_a": "amazon-basin",
        "region_b": "sahel",
        "variable_id": "temperature",
    }
    response = client.get("/api/comparison", params=query | params)
    assert response.status_code == (404 if code == "result_not_available" else 422)
    validator_for("responses.schema.json", "#/$defs/errorResponse").validate(
        response.json()
    )
    assert response.json()["error"]["code"] == code


def test_variable_must_apply_to_both_regions(client, monkeypatch):
    from dataclasses import replace

    from api import main

    restricted = replace(main.catalog.regions[2], variable_ids=("precipitation",))
    monkeypatch.setattr(
        main,
        "catalog",
        replace(main.catalog, regions=(main.catalog.regions[0], restricted)),
    )
    response = client.get(
        "/api/comparison",
        params={
            "region_a": "amazon-basin",
            "region_b": "sahel",
            "variable_id": "temperature",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "variable_not_available_for_region"


def test_insufficient_data_returns_an_unavailable_analysis(
    client, tmp_path, monkeypatch
):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    for region in ("amazon-basin", "sahel"):
        payload = as_dict(series_for(region, "temperature", 0.73, seed=1))
        payload["values"] = [None] * 300
        (series_dir / f"{region}.json").write_text(json.dumps(payload))
    monkeypatch.setattr("api.main.store", JsonResultStore(tmp_path, ENGINE_VERSION))
    response = client.get(
        "/api/comparison",
        params={
            "region_a": "amazon-basin",
            "region_b": "sahel",
            "variable_id": "temperature",
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "result_not_available"
