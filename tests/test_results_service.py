"""Issue #11: serve exact stored results and enforce the catalog over HTTP."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from api import main
from engine import ENGINE_VERSION, JsonResultStore


@pytest.fixture
def stored_results(tmp_path, stub_dir, monkeypatch):
    """Keep results differing in just one key component in the same store."""
    template = json.loads(
        (stub_dir / "series" / "sahel__temperature.json").read_text(encoding="utf-8")
    )
    keys = [
        ("sahel", "temperature", "2000-01", "2000-03", ENGINE_VERSION),
        ("amazon-basin", "temperature", "2000-01", "2000-03", ENGINE_VERSION),
        ("sahel", "precipitation", "2000-01", "2000-03", ENGINE_VERSION),
        ("sahel", "temperature", "2000-02", "2000-03", ENGINE_VERSION),
        ("sahel", "temperature", "2000-01", "2000-02", ENGINE_VERSION),
        ("sahel", "temperature", "2000-01", "2000-03", "other-version"),
    ]
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    payloads = []
    for index, (region_id, variable_id, start, end, version) in enumerate(keys):
        variable = main.catalog.variable(variable_id)
        payload = {
            **template,
            "region_id": region_id,
            "variable_id": variable_id,
            "period": {"start": start, "end": end},
            "engine_version": version,
            "units": variable.units,
            "source": main.as_dict(variable.source),
            "values": [float(index)] * (int(end[-2:]) - int(start[-2:]) + 1),
            "quality": {
                **template["quality"],
                "missing_fraction": 0.0,
            },
        }
        (series_dir / f"{index}.json").write_text(json.dumps(payload), encoding="utf-8")
        payloads.append(payload)
    monkeypatch.setattr(main, "store", JsonResultStore(tmp_path, ENGINE_VERSION))
    return tmp_path, payloads


@pytest.mark.parametrize("result_index", range(6))
def test_http_returns_the_exact_result_for_each_key_component(
    stored_results, result_index, monkeypatch, validator_for
):
    root, payloads = stored_results
    expected = payloads[result_index]
    monkeypatch.setattr(main, "store", JsonResultStore(root, expected["engine_version"]))

    with TestClient(main.app) as client:
        response = client.get(
            "/api/series",
            params={
                "region_id": expected["region_id"],
                "variable_id": expected["variable_id"],
                "period_start": expected["period"]["start"],
                "period_end": expected["period"]["end"],
            },
        )

    assert response.status_code == 200
    validator_for("responses.schema.json", "#/$defs/seriesResponse").validate(response.json())
    assert response.json() == {"data": expected, "notice": None}


@pytest.mark.parametrize(
    "change",
    [
        {"region_id": "central-india"},
        {"variable_id": "precipitation", "region_id": "amazon-basin"},
        {"period_start": "1999-12"},
        {"period_end": "2000-04"},
        {"engine_version": "version-with-no-results"},
    ],
    ids=["region", "variable", "period-start", "period-end", "engine-version"],
)
def test_http_cache_miss_does_not_return_a_result_with_a_different_key(
    stored_results, change, monkeypatch, validator_for
):
    root, _ = stored_results
    change = dict(change)
    version = change.pop("engine_version", ENGINE_VERSION)
    monkeypatch.setattr(main, "store", JsonResultStore(root, version))

    with TestClient(main.app) as client:
        response = client.get(
            "/api/series",
            params={
                "region_id": "sahel",
                "variable_id": "temperature",
                "period_start": "2000-01",
                "period_end": "2000-03",
                **change,
            },
        )

    assert response.status_code == 404
    validator_for("responses.schema.json", "#/$defs/errorResponse").validate(response.json())
    assert response.json()["error"]["code"] == "result_not_available"


@pytest.mark.parametrize(
    "region_id,variable_id,expected_code",
    [
        ("outside-catalog", "temperature", "region_not_in_catalog"),
        ("sahel", "outside-catalog", "variable_not_in_catalog"),
        ("sahel", "precipitation", "variable_not_available_for_region"),
    ],
)
def test_http_rejects_requests_outside_the_catalog_before_reading_results(
    region_id, variable_id, expected_code, monkeypatch, validator_for
):
    region = replace(main.catalog.region("sahel"), variable_ids=("temperature",))
    monkeypatch.setattr(main, "catalog", replace(main.catalog, regions=(region,)))

    def unexpected_lookup(*args, **kwargs):
        pytest.fail("Requests outside the catalog must not read stored results")

    monkeypatch.setattr(main.store, "series", unexpected_lookup)

    with TestClient(main.app) as client:
        response = client.get(
            "/api/series", params={"region_id": region_id, "variable_id": variable_id}
        )

    assert response.status_code == 422
    validator_for("responses.schema.json", "#/$defs/errorResponse").validate(response.json())
    assert response.json()["error"]["code"] == expected_code
