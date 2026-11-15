"""Issue #76: acquisition requests at the agreed HTTP seam use only fake grids."""

import pytest
from fastapi.testclient import TestClient

from api import main
from engine import ENGINE_VERSION, JsonResultStore
from tests.fake_acquisition import FakeGridAcquisitionSource


@pytest.mark.parametrize(
    "variable,units",
    [("temperature", "°C"), ("precipitation", "mm/month"), ("soil-moisture", "mm")],
)
def test_requested_variable_period_and_cache(tmp_path, monkeypatch, variable, units):
    requests = []

    class RecordingSource(FakeGridAcquisitionSource):
        def prepare(self, request, *, fetch=False):
            requests.append(request.copy())
            assert request["time_step"] == "monthly"
            return super().prepare(request, fetch=fetch)

    source = RecordingSource(
        timestamps=["2025-01-01T00:00:00", "2025-01-01T03:00:00"],
        latitudes=[12.0],
        longitudes=[0.0, 1.0],
        values=[[[3.0, 7.0]], [[11.0, 15.0]]],
        units=units,
        land_mask=[[1, 1]] if variable == "soil-moisture" else None,
    )
    monkeypatch.setattr(
        main, "live_store", JsonResultStore(tmp_path / "cache", ENGINE_VERSION)
    )
    monkeypatch.delenv("EARTHDATA_TOKEN", raising=False)
    main.app.dependency_overrides[main.get_acquisition_source] = lambda: source
    try:
        with TestClient(main.app) as client:
            params = {
                "region_id": "sahel",
                "variable_id": variable,
                "period_start": "2025-01",
                "period_end": "2025-01",
            }
            first = client.get("/api/series", params=params)
            assert first.status_code == 200
            assert first.json()["data"]["values"] == pytest.approx([9.0])
            assert (
                client.get("/api/series", params=params).json()["provenance"] == "cache"
            )
        assert len(requests) == 1
        assert requests[0]["variable_id"] == variable
        assert requests[0]["period"] == {"start": "2025-01", "end": "2025-01"}
        assert requests[0]["bbox"] == [-15, 12, 25, 18]
    finally:
        main.app.dependency_overrides.clear()
