"""Issue #65: credential configuration exercised through the HTTP boundary."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from api import main
from data.data_gathering import config
from engine import ENGINE_VERSION, JsonResultStore


@pytest.mark.parametrize("exported", [False, True])
def test_series_acquisition_reads_dotenv_and_preserves_exported_token(
    tmp_path, monkeypatch, stub_dir, validator_for, exported
):
    env_file = tmp_path / ".env"
    env_file.write_text('EARTHDATA_TOKEN="dotenv-test-token"\n')
    monkeypatch.setattr(config, "ENV_PATHS", (env_file,))
    monkeypatch.delenv("EARTHDATA_TOKEN", raising=False)
    if exported:
        monkeypatch.setenv("EARTHDATA_TOKEN", "exported-test-token")
    payload = json.loads((stub_dir / "series/sahel__temperature.json").read_text())
    payload.update(period={"start": "2025-01", "end": "2025-12"}, values=[29.3] * 12)
    payload["quality"]["missing_fraction"] = 0.0

    async def acquire(region, variable, period, *, token):
        assert token == ("exported-test-token" if exported else "dotenv-test-token")
        return payload

    monkeypatch.setattr(main, "acquire_series", acquire)
    monkeypatch.setattr(
        main, "live_store", JsonResultStore(tmp_path / "cache", ENGINE_VERSION)
    )
    with TestClient(main.app) as client:
        response = client.get(
            "/api/series",
            params={
                "region_id": "sahel",
                "variable_id": "temperature",
                "period_start": "2025-01",
                "period_end": "2025-12",
            },
        )
    assert response.status_code == 200
    validator_for("responses.schema.json", "#/$defs/seriesResponse").validate(
        response.json()
    )
    assert response.json() == {"data": payload, "notice": None, "provenance": "live"}
    assert "test-token" not in response.text
    assert env_file.read_text() == 'EARTHDATA_TOKEN="dotenv-test-token"\n'


def test_twelve_month_fetch_can_finish_after_fifteen_seconds(
    tmp_path, monkeypatch, stub_dir
):
    monkeypatch.setenv("EARTHDATA_TOKEN", "test-token")
    payload = json.loads((stub_dir / "series/sahel__temperature.json").read_text())
    payload.update(period={"start": "2025-01", "end": "2025-12"}, values=[28.7] * 12)
    payload["quality"]["missing_fraction"] = 0.0

    async def acquire(*args, **kwargs):
        await asyncio.sleep(16)
        return payload

    monkeypatch.setattr(main, "acquire_series", acquire)
    monkeypatch.setattr(
        main, "live_store", JsonResultStore(tmp_path / "cache", ENGINE_VERSION)
    )
    with TestClient(main.app) as client:
        response = client.get(
            "/api/series",
            params={
                "region_id": "sahel",
                "variable_id": "temperature",
                "period_start": "2025-01",
                "period_end": "2025-12",
            },
        )
    assert response.status_code == 200
    assert response.json() == {"data": payload, "notice": None, "provenance": "live"}


@pytest.mark.parametrize(
    "region_id",
    [
        "greenland-coast",
        "antarctic-peninsula",
        "equatorial-pacific",
        "north-atlantic",
    ],
)
def test_soil_moisture_is_not_offered_for_ocean_and_ice_regions(
    region_id, validator_for
):
    # #65 regression: these pairs are outside the catalog, not missing seed data.
    with TestClient(main.app) as client:
        response = client.get(
            "/api/series",
            params={
                "region_id": region_id,
                "variable_id": "soil-moisture",
            },
        )
    assert response.status_code == 422
    validator_for("responses.schema.json", "#/$defs/errorResponse").validate(
        response.json()
    )
    assert response.json()["error"]["code"] == "variable_not_available_for_region"
