"""Field map validation, persistent cache and cancellable background jobs."""

import asyncio
import hashlib
import json
import logging
import os
import tempfile
from collections.abc import Callable
from typing import Any

from data.data_gathering.config import settings
from engine.contracts import Period

from .acquisition import AcquisitionUnavailable, acquire_series
from .explore import (
    Refusal,
    _validate_geometry,
    _validate_time_step_variables,
    _validate_view,
)
from .jobs import SeriesJobs
from .products import PRODUCTS

logger = logging.getLogger(__name__)


def field_view(
    catalog,
    region_id,
    rectangles,
    variable_id,
    aggregation,
    time_step,
    start,
    end,
    latest,
):
    area = _validate_geometry(catalog, region_id, rectangles or [], [variable_id])
    if variable_id not in PRODUCTS:
        # A Field map is always built from NASA grids, which this Variable lacks.
        raise Refusal(
            422,
            "variable_not_available_for_field_map",
            f"{variable_id} has no Field map yet: it has no NASA grids to draw.",
        )
    _validate_view(aggregation, time_step, start, end, latest)
    _validate_time_step_variables(catalog, time_step, [variable_id])
    return {
        **(
            {"region_id": region_id} if area is None else {"area": {"rectangles": area}}
        ),
        "variable_ids": [variable_id],
        "aggregation": aggregation,
        "time_step": time_step,
        "period": {"start": start, "end": end},
    }


class FieldCache:
    def __init__(self, root):
        self.root = root

    def path(self, view):
        key = hashlib.sha256(json.dumps(view, sort_keys=True).encode()).hexdigest()
        return self.root / (key + ".json")

    def read(self, view):
        # A missing or unreadable entry is a cache miss: the job rebuilds it.
        try:
            return json.loads(self.path(view).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def save(self, view, result):
        self.root.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=self.root, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as output:
                json.dump(result, output, allow_nan=False)
            os.replace(temporary, self.path(view))
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


class FieldJobs(SeriesJobs):
    def start(
        self,
        view,
        catalog,
        cache: Any,
        source,
        timeout,
        finish: Callable[[], Any],
        area_cache=None,
    ):
        # Reuse scheduling/lifecycle with a FieldCache rather than a Series store.
        return super().start(view, catalog, cache, source, timeout, finish, area_cache)

    async def _run(
        self, job, key, view, catalog, cache, source, timeout, finish, area_cache
    ):
        job["status"] = "running"
        try:
            async with asyncio.timeout(timeout):
                token = settings().get("EARTHDATA_TOKEN", "")
                if source is None and not token:
                    raise AcquisitionUnavailable("Server token unavailable")
                area = view.get("area")
                result = await acquire_series(
                    catalog.region(view["region_id"]) if area is None else None,
                    catalog.variable(view["variable_ids"][0]),
                    Period(**view["period"]),
                    token=token,
                    source=source,
                    aggregation=view["aggregation"],
                    time_step=view["time_step"],
                    field_map=True,
                    rectangles=area["rectangles"] if area else None,
                )
                cache.save(view, result)
                job.update(result=result, progress=100, status="succeeded")
        except asyncio.CancelledError:
            self._fail(job)
            raise
        except Exception:
            logger.exception("Field map acquisition failed")
            self._fail(job)
        finally:
            self.pending.pop(key, None)

    @staticmethod
    def _fail(job):
        job.update(
            status="failed",
            error={
                "code": "acquisition_failed",
                "message": "The Field map could not be obtained. Please try again.",
            },
        )
