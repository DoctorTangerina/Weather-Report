"""Process-local jobs; acquired Series pieces live in a persistent results cache.

A job acquires only the months the seed set does not hold (`view["acquire"]`),
at the view's Time step, keeps each piece in the cache for that Aggregation and
Time step (a Selected area's in its own), then builds the view's result with
`finish`.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from data.data_gathering.config import settings
from engine.contracts import Catalog, Period
from engine.store import ResultStore

from .acquisition import AcquisitionUnavailable, acquire_series
from .area_cache import AreaSeriesCache
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
        finish: Callable[[], dict[str, Any]],
        area_cache: AreaSeriesCache | None = None,
    ) -> dict[str, Any]:
        area = view.get("area")
        key = (
            view.get("region_id") or tuple(tuple(box) for box in area["rectangles"]),
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
            self._run(
                job, key, view, catalog, cache, source, timeout, finish, area_cache
            )
        )
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return job

    async def _run(
        self, job, key, view, catalog, cache, source, timeout, finish, area_cache
    ):
        job["status"] = "running"
        area = view.get("area")
        # A Selected area is never a Region: its Series have their own cache.
        store = cache if area is None else area_cache
        place = view["region_id"] if area is None else area["rectangles"]
        identity = "region_id" if area is None else "area"
        try:
            async with asyncio.timeout(timeout):
                region = None
                if area is None:
                    region = catalog.region(view["region_id"])
                    assert region is not None
                acquire = view["acquire"]
                token = settings().get("EARTHDATA_TOKEN", "")
                for done, (variable_id, months) in enumerate(acquire.items(), 1):
                    period = Period(**months)
                    payload = store.series(place, variable_id, period)
                    if payload is None:
                        if source is None and not token:
                            raise AcquisitionUnavailable("Server token unavailable")
                        variable = catalog.variable(variable_id)
                        assert variable is not None
                        payload = await acquire_series(
                            region,
                            variable,
                            period,
                            token=token,
                            source=source,
                            aggregation=view["aggregation"],
                            # A Region's piece is joined to seeded months and
                            # gated again; a Selected area's is served whole.
                            keep_values=area is None,
                            rectangles=None if area is None else area["rectangles"],
                            time_step=view["time_step"],
                        )
                        if (
                            payload.get(identity) != view[identity]
                            or payload["variable_id"] != variable_id
                            or payload["period"] != months
                        ):
                            raise AcquisitionUnavailable("Unexpected acquired Series")
                        store.save_series(payload)
                    job["progress"] = int(100 * done / len(acquire))
                job["result"] = finish()
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
