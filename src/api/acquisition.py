"""Cancellable bridge to #6's download and monthly Series pipeline."""

import asyncio
import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

from engine.contracts import Period, Region, Variable

from .grid_source import GridAcquisitionSource

# netCDF4 preparation in injected sources must not run concurrently in this process.
_PREPARE_LOCK = threading.Lock()


def _prepare(source: GridAcquisitionSource, request: dict) -> Path:
    with _PREPARE_LOCK:
        return source.prepare(request)


class AcquisitionUnavailable(Exception):
    """Expected upstream/authentication/quality failure, not a programming error."""


async def acquire_series(
    region: Region | None,
    variable: Variable,
    period: Period,
    *,
    token: str,
    source: GridAcquisitionSource | None = None,
    aggregation: str = "mean",
    keep_values: bool = False,
    rectangles: list[list[float]] | None = None,
    time_step: str = "monthly",
    field_map: bool = False,
) -> dict[str, Any]:
    """A catalog Region's Series, or with `region` None a Selected area's.

    keep_values keeps an excluded Series' values. `time_step` asks the source
    for native sub-monthly grids and reduces them to that Time step.
    """
    root = Path(__file__).resolve().parents[2]
    env = {
        **os.environ,
        "EARTHDATA_TOKEN": token,
        "PYTHONPATH": os.pathsep.join((str(root), str(root / "src"))),
    }
    with tempfile.TemporaryDirectory(prefix="weather-acquisition-") as workspace:
        geometry = (
            {"rectangles": rectangles, "bbox": rectangles[0]}
            if region is None
            else {
                "region_id": region.region_id,
                "bbox": [
                    region.bbox.west,
                    region.bbox.south,
                    region.bbox.east,
                    region.bbox.north,
                ],
            }
        )
        request = {
            **geometry,
            "variable_id": variable.variable_id,
            "period": {"start": period.start, "end": period.end},
            "dataset": variable.source.dataset,
            "time_step": time_step,
            "aggregation": aggregation,
            "keep_values": keep_values,
            "field_map": field_map,
            "workspace": workspace,
        }
        if source is not None:
            preparation = asyncio.create_task(
                asyncio.to_thread(_prepare, source, request)
            )
            try:
                config = await asyncio.shield(preparation)
            except asyncio.CancelledError:
                # Let preparation release its files before cleaning the workspace.
                await asyncio.gather(preparation, return_exceptions=True)
                raise
            request["config_path"] = str(config)
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "api.acquisition_worker",
            cwd=root,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            output, _ = await process.communicate(json.dumps(request).encode())
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
        if process.returncode == 2:
            raise AcquisitionUnavailable("Acquisition or source data unavailable")
        if process.returncode != 0:
            raise RuntimeError("Acquisition worker failed unexpectedly")
        return json.loads(output)
