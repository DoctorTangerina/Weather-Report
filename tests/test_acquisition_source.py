"""Issue #73: replace gridded acquisition at the existing HTTP contract seam."""

import pytest
from fastapi.testclient import TestClient

from api import main
from engine import ENGINE_VERSION, JsonResultStore

pytest.importorskip("netCDF4", reason="needs netCDF4: pip install -e '.[api,dev]'")

from tests.fake_acquisition import FakeGridAcquisitionSource


@pytest.mark.parametrize(
    "timestamps,end,expected",
    [
        (["2025-01-01T00:00:00", "2025-01-01T01:00:00"], "2025-01", [8.0]),
        (["2025-01-01T00:00:00", "2025-01-01T03:00:00"], "2025-01", [8.0]),
        (["2025-01-01T00:00:00", "2025-02-01T00:00:00"], "2025-02", [4.0, 12.0]),
    ],
    ids=["hourly", "3-hourly", "monthly"],
)
@pytest.mark.parametrize(
    "region,latitudes,longitudes",
    [
        ("sahel", [12.0], [0.0, 1.0, 100.0]),
        ("amazon-basin", [-2.0], [-60.0, -59.0, 0.0]),
    ],
)
def test_fake_grid_source_builds_monthly_series(
    tmp_path,
    monkeypatch,
    validator_for,
    timestamps,
    end,
    expected,
    region,
    latitudes,
    longitudes,
):
    source = FakeGridAcquisitionSource(
        timestamps=timestamps,
        latitudes=latitudes,
        longitudes=longitudes,
        values=[[[2.0, 6.0, 999.0]], [[10.0, 14.0, 999.0]]],
        units="°C",
    )
    monkeypatch.setattr(
        main, "live_store", JsonResultStore(tmp_path / "cache", ENGINE_VERSION)
    )
    monkeypatch.delenv("EARTHDATA_TOKEN", raising=False)
    main.app.dependency_overrides[main.get_acquisition_source] = lambda: source
    try:
        with TestClient(main.app) as client:
            response = client.get(
                "/api/series",
                params={
                    "region_id": region,
                    "variable_id": "temperature",
                    "period_start": "2025-01",
                    "period_end": end,
                },
            )
        assert response.status_code == 200
        body = response.json()
        validator_for("responses.schema.json", "#/$defs/seriesResponse").validate(body)
        assert body["provenance"] == "live"
        assert body["data"]["values"] == pytest.approx(expected)
        assert body["notice"] is None
    finally:
        main.app.dependency_overrides.clear()
