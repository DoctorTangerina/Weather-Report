"""BS-009: HTTP uses #6's actual NetCDF-to-monthly-Series pipeline."""

import json

import pytest
from fastapi.testclient import TestClient

from api import main

# The acquisition fixtures read NetCDF files. netCDF4 ships with the `api`
# extra; without it, skip this file with a reason instead of aborting the run.
pytest.importorskip("netCDF4", reason="needs netCDF4: pip install -e '.[api,dev]'")

from data.data_gathering.tests.test_catalog_series import make_setup  # noqa: E402
from engine import ENGINE_VERSION, JsonResultStore, load_catalog


@pytest.mark.parametrize("missing", [(), (0, 1, 2)])
def test_http_integrates_real_data_layer_and_persists(
    tmp_path, monkeypatch, validator_for, missing
):
    paths = make_setup(tmp_path, missing=missing)
    payload = json.loads(paths["catalog_path"].read_text())
    payload["engine_version"] = ENGINE_VERSION
    paths["catalog_path"].write_text(json.dumps(payload))
    monkeypatch.setattr(main, "catalog", load_catalog(paths["catalog_path"]))
    monkeypatch.setattr(
        main, "store", JsonResultStore(tmp_path / "examples", ENGINE_VERSION)
    )
    monkeypatch.setattr(
        main, "live_store", JsonResultStore(tmp_path / "cache", ENGINE_VERSION)
    )
    monkeypatch.setenv("WEATHER_REPORT_CATALOG", str(paths["catalog_path"]))
    monkeypatch.setenv("WEATHER_REPORT_ACQUISITION_CONFIG", str(paths["config_path"]))
    monkeypatch.setenv("EARTHDATA_TOKEN", "synthetic-test-token")
    params = {
        "region_id": "test-region",
        "variable_id": "temperature",
        "period_start": "2020-01",
        "period_end": "2020-10",
    }
    with TestClient(main.app) as client:
        response = client.get("/api/series", params=params)
        if missing:
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "live_data_unavailable"
            return
        assert response.status_code == 200
        body = response.json()
        validator_for("responses.schema.json", "#/$defs/seriesResponse").validate(body)
        assert body["data"]["values"] == pytest.approx(list(range(1, 11)))
        assert body["provenance"] == "live"
        monkeypatch.setattr(
            main, "live_store", JsonResultStore(tmp_path / "cache", ENGINE_VERSION)
        )
        monkeypatch.delenv("EARTHDATA_TOKEN")
        assert client.get("/api/series", params=params).json()["provenance"] == "cache"
