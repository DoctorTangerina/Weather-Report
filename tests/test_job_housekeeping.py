"""Background jobs stay bounded in memory and log expected failures quietly."""

import asyncio
import logging
import time

from fastapi.testclient import TestClient

from api import main
from api.jobs import MAX_JOBS, SeriesJobs
from engine import ENGINE_VERSION, JsonResultStore


def test_finished_jobs_beyond_the_limit_are_forgotten_oldest_first():
    jobs = SeriesJobs()

    async def instant(job, *args):
        job["status"] = "succeeded"

    jobs._run = instant

    async def start_many():
        started = []
        for n in range(MAX_JOBS + 25):
            view = {
                "region_id": f"region-{n}",
                "variable_ids": ["temperature"],
                "aggregation": "mean",
                "time_step": "monthly",
                "period": {"start": "2000-01", "end": "2024-12"},
            }
            started.append(jobs.start(view, None, None, None, 1, lambda: None)["id"])
            await asyncio.sleep(0)
        return started

    started = asyncio.run(start_many())
    assert len(jobs.jobs) <= MAX_JOBS
    assert started[-1] in jobs.jobs
    assert started[0] not in jobs.jobs


def test_a_running_job_is_never_forgotten():
    jobs = SeriesJobs()
    jobs.jobs = {
        str(n): {"id": str(n), "status": "running"} for n in range(MAX_JOBS + 5)
    }
    jobs._prune()
    assert len(jobs.jobs) == MAX_JOBS + 5


def test_a_job_without_credentials_fails_with_one_quiet_warning(
    tmp_path, monkeypatch, caplog
):
    monkeypatch.setenv("WEATHER_REPORT_LATEST_MONTH", "2025-02")
    monkeypatch.setenv("EARTHDATA_TOKEN", "")
    monkeypatch.setattr(main, "live_store", JsonResultStore(tmp_path, ENGINE_VERSION))
    caplog.set_level(logging.WARNING, logger="api.jobs")
    with TestClient(main.app) as client:
        response = client.get(
            "/api/explore/series",
            params={
                "region_id": "sahel",
                "variable_id": "temperature",
                "period_start": "2025-01",
                "period_end": "2025-02",
            },
        )
        url = response.json()["data"]["job"]["url"]
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            job = client.get(url).json()["data"]["job"]
            if job["status"] in {"succeeded", "failed"}:
                break
            time.sleep(0.02)
    assert job["status"] == "failed"
    records = [r for r in caplog.records if r.name == "api.jobs"]
    assert records, "the failure is still logged"
    assert all(r.exc_info is None for r in records)
    assert all(r.levelno == logging.WARNING for r in records)
