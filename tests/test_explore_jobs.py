"""Issue #77: monthly BS-007 jobs through spec #72's HTTP seam."""

import time
from dataclasses import replace
from datetime import UTC

import pytest
from fastapi.testclient import TestClient

from api import main
from engine import ENGINE_VERSION, JsonResultStore
from tests.fake_acquisition import FakeGridAcquisitionSource


class ControlledSource(FakeGridAcquisitionSource):
    calls = 0
    fail = False

    def prepare(self, request, *, fetch=False):
        self.calls += 1
        time.sleep(0.15)
        if self.fail:
            raise OSError("Source unavailable; secret token must not reach client")
        # Only the acquisition source is replaced; reduction and units stay real.
        grid = (
            replace(self, units="mm/month")
            if request["variable_id"] == "precipitation"
            else self
        )
        return FakeGridAcquisitionSource.prepare(grid, request, fetch=fetch)


@pytest.fixture
def jobs(tmp_path, monkeypatch):
    monkeypatch.setenv("WEATHER_REPORT_LATEST_MONTH", "2025-02")
    source = ControlledSource(
        timestamps=["2025-01-01T00:00:00", "2025-02-01T00:00:00"],
        latitudes=[12.0],
        longitudes=[0.0, 1.0],
        values=[[[2.0, 6.0]], [[10.0, 14.0]]],
        units="°C",
    )
    monkeypatch.setattr(main, "live_store", JsonResultStore(tmp_path, ENGINE_VERSION))
    main.app.dependency_overrides[main.get_acquisition_source] = lambda: source
    with TestClient(main.app) as client:
        yield client, source
    main.app.dependency_overrides.clear()


def request(client, variables=("temperature",)):
    return client.get(
        "/api/explore/series",
        params={
            "region_id": "sahel",
            "variable_id": list(variables),
            "period_start": "2025-01",
            "period_end": "2025-02",
        },
    )


def finish(client, url, validator_for):
    deadline = time.monotonic() + 60
    progress = []
    while time.monotonic() < deadline:
        response = client.get(url)
        assert response.status_code == 200
        body = response.json()
        validator_for("responses.schema.json", "#/$defs/exploreJobResponse").validate(
            body
        )
        job = body["data"]["job"]
        progress.append(job["progress"])
        if job["status"] in {"succeeded", "failed"}:
            assert progress == sorted(progress)
            return job
        time.sleep(0.02)
    pytest.fail("Job did not finish")


def test_monthly_request_beyond_seed_returns_job_then_series(jobs, validator_for):
    client, source = jobs
    before = client.get("/api/discoveries").json()
    response = request(client)
    assert response.status_code == 202, response.json()
    validator_for("responses.schema.json", "#/$defs/exploreJobResponse").validate(
        response.json()
    )
    job = response.json()["data"]["job"]
    assert job["status"] in {"queued", "running"}
    assert job["progress"] == 0
    done = finish(client, job["url"], validator_for)
    assert done["status"] == "succeeded"
    assert done["progress"] == 100
    assert done["result"]["period"] == {"start": "2025-01", "end": "2025-02"}
    assert done["result"]["series"][0]["values"] == pytest.approx([4.0, 12.0])
    assert source.calls == 1
    assert client.get("/api/discoveries").json() == before


def test_finished_request_uses_persistent_cache_without_acquiring(
    jobs, validator_for, tmp_path, monkeypatch
):
    # BS-007: a repeated request is answered from the cache.
    client, source = jobs
    job = request(client).json()["data"]["job"]
    done = finish(client, job["url"], validator_for)
    source.fail = True
    monkeypatch.setattr(main, "live_store", JsonResultStore(tmp_path, ENGINE_VERSION))
    response = request(client)
    assert response.status_code == 200
    validator_for("responses.schema.json", "#/$defs/exploreSeriesResponse").validate(
        response.json()
    )
    assert response.json()["data"] == done["result"]
    assert response.json()["provenance"] == "cache"
    assert source.calls == 1


def test_failed_job_reports_failure_and_can_be_retried(jobs, validator_for):
    # #77 failure acceptance criterion (BS-003 in the browser).
    client, source = jobs
    source.fail = True
    job = request(client).json()["data"]["job"]
    done = finish(client, job["url"], validator_for)
    assert done["status"] == "failed"
    assert done["result"] is None
    assert done["error"] == {
        "code": "acquisition_failed",
        "message": "The Series could not be obtained. Please try again.",
    }
    source.fail = False
    retried = request(client).json()["data"]["job"]
    assert retried["id"] != job["id"]
    assert finish(client, retried["url"], validator_for)["status"] == "succeeded"


def test_duplicate_pending_request_shares_job(jobs, validator_for):
    client, source = jobs
    first = request(client).json()["data"]["job"]
    second = request(client).json()["data"]["job"]
    assert first["id"] == second["id"]
    finish(client, first["url"], validator_for)
    assert source.calls == 1


def test_unknown_job_is_a_schema_valid_error(jobs, validator_for):
    client, _ = jobs
    response = client.get("/api/explore/jobs/missing")
    assert response.status_code == 404
    validator_for("responses.schema.json", "#/$defs/errorResponse").validate(
        response.json()
    )
    assert response.json()["error"]["code"] == "job_not_found"


def test_latest_month_defaults_to_last_complete_utc_month(
    jobs, monkeypatch, validator_for
):
    from datetime import datetime, timedelta

    client, _ = jobs
    monkeypatch.delenv("WEATHER_REPORT_LATEST_MONTH")
    response = client.get("/api/explore/options")
    validator_for("responses.schema.json", "#/$defs/exploreOptionsResponse").validate(
        response.json()
    )
    last = datetime.now(UTC).replace(day=1) - timedelta(days=1)
    assert response.json()["data"]["latest_month"] == last.strftime("%Y-%m")


def test_latest_month_can_be_configured_and_bounds_requests(jobs, validator_for):
    client, _ = jobs
    response = client.get("/api/explore/options")
    assert response.json()["data"]["latest_month"] == "2025-02"
    response = client.get(
        "/api/explore/series",
        params={
            "region_id": "sahel",
            "variable_id": "temperature",
            "period_end": "2025-03",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "period_out_of_range"
    assert "2025-02" in response.json()["error"]["message"]


def test_polling_shows_partial_progress_for_multiple_variables(jobs, validator_for):
    client, source = jobs
    source.calls = 0
    job = request(client, ("temperature", "precipitation")).json()["data"]["job"]
    deadline = time.monotonic() + 60
    seen = [job["progress"]]
    while time.monotonic() < deadline:
        body = client.get(job["url"]).json()
        validator_for("responses.schema.json", "#/$defs/exploreJobResponse").validate(
            body
        )
        job = body["data"]["job"]
        seen.append(job["progress"])
        if job["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.02)
    assert job["status"] == "succeeded", job
    assert 50 in seen
    assert seen == sorted(seen)
    assert job["progress"] == 100
    assert [s["variable_id"] for s in job["result"]["series"]] == [
        "temperature",
        "precipitation",
    ]
    assert source.calls == 2


def test_job_timeout_reports_failure(jobs, monkeypatch, validator_for):
    client, source = jobs
    monkeypatch.setattr(main, "LIVE_TIMEOUT_SECONDS", 0.01)
    job = request(client).json()["data"]["job"]
    done = finish(client, job["url"], validator_for)
    assert done["status"] == "failed"
    assert done["result"] is None
    assert source.calls == 1
