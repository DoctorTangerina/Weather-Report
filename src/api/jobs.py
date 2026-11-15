"""Process-local jobs; finished Series live in the existing persistent results cache."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import uuid4

from data.data_gathering.config import settings
from engine.contracts import Catalog, Period
from engine.store import ResultStore

from .acquisition import AcquisitionUnavailable, acquire_series
from .grid_source import GridAcquisitionSource

logger = logging.getLogger(__name__)


class SeriesJobs:
    def __init__(self) -> None:
        self.jobs: dict[str, dict[str, Any]] = {}
        self.tasks: set[asyncio.Task] = set()
        self.pending: dict[tuple, str] = {}

    def start(
        self,
        view: dict[str, Any],
        catalog: Catalog,
        cache: ResultStore,
        source: GridAcquisitionSource | None,
        timeout: float,
    ) -> dict[str, Any]:
        key = (
            view["region_id"],
            tuple(view["variable_ids"]),
            view["aggregation"],
            view["time_step"],
            view["period"]["start"],
            view["period"]["end"],
        )
        if key in self.pending:
            return self.jobs[self.pending[key]]
        job_id = uuid4().hex
        job = {
            "id": job_id,
            "url": f"/api/explore/jobs/{job_id}",
            "status": "queued",
            "progress": 0,
            "result": None,
            "error": None,
        }
        self.jobs[job_id] = job
        self.pending[key] = job_id
        task = asyncio.create_task(
            self._run(job, key, view, catalog, cache, source, timeout)
        )
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return job

    async def _run(self, job, key, view, catalog, cache, source, timeout):
        job["status"] = "running"
        try:
            async with asyncio.timeout(timeout):
                region = catalog.region(view["region_id"])
                period = Period(**view["period"])
                series = []
                token = settings().get("EARTHDATA_TOKEN", "")
                for variable_id in view["variable_ids"]:
                    payload = cache.series(view["region_id"], variable_id, period)
                    if payload is None:
                        if source is None and not token:
                            raise AcquisitionUnavailable("Server token unavailable")
                        variable = catalog.variable(variable_id)
                        assert region is not None and variable is not None
                        payload = await acquire_series(
                            region, variable, period, token=token, source=source
                        )
                        if (
                            payload["region_id"] != view["region_id"]
                            or payload["variable_id"] != variable_id
                            or payload["period"] != view["period"]
                        ):
                            raise AcquisitionUnavailable("Unexpected acquired Series")
                        cache.save_series(payload)
                    series.append(payload)
                    job["progress"] = int(100 * len(series) / len(view["variable_ids"]))
                job["result"] = {
                    k: v for k, v in view.items() if k != "variable_ids"
                } | {"series": series}
                job["status"] = "succeeded"
        except asyncio.CancelledError:
            self._fail(job)
            raise
        except Exception:
            logger.exception("Explore Series job failed")
            self._fail(job)
        finally:
            self.pending.pop(key, None)

    @staticmethod
    def _fail(job):
        job["status"] = "failed"
        job["error"] = {
            "code": "acquisition_failed",
            "message": "The Series could not be obtained. Please try again.",
        }

    async def close(self):
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
