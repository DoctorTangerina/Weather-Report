"""Resolve cached catalog Series by Variable/Region name, without NASA downloads.

Custom-area and on-demand sources plug into the same callable loader boundary;
this fallback never silently reads a machine-specific raw NetCDF collection.
"""

import json
from collections.abc import Mapping
from pathlib import Path

from ..data_gathering.models import Period
from ..data_gathering.quality_gate import months_in
from ..time_steps import normalize_time_step
from .errors import ProcessingError

_DATA = Path(__file__).resolve().parents[1]


class SeedSeriesLoader:
    """Load precomputed monthly catalog data using names or stable catalog IDs."""

    def __init__(
        self,
        *,
        catalog_path: Path = _DATA / "catalog.json",
        series_dir: Path = _DATA / "seed/series",
    ):
        self.catalog_path = Path(catalog_path)
        self.series_dir = Path(series_dir)

    def __call__(self, selection: dict, period: dict) -> dict:
        try:
            catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            region = self._find(catalog["regions"], "region_id", selection["area"])
            variable = self._find(
                catalog["variables"], "variable_id", selection["variable"]
            )
        except (OSError, ValueError, KeyError, TypeError):
            raise ProcessingError(
                "catalog_unavailable", "The Variable and Region catalog is unavailable."
            ) from None
        if region is None:
            raise ProcessingError(
                "area_unavailable",
                "Data for this area is unavailable. Choose another area, period or Variable.",
            )
        if variable is None:
            raise ProcessingError(
                "variable_unavailable",
                "This Variable is unavailable. Choose another Variable.",
            )
        requested_step = selection.get("source_time_step", "monthly")
        try:
            if normalize_time_step(requested_step) != "month":
                raise ValueError
        except ValueError:
            raise ProcessingError(
                "source_unavailable",
                "The requested Time step is not available in the cached data.",
            ) from None
        if selection.get("aggregation", "mean") not in ("mean", "average", "avg"):
            raise ProcessingError(
                "aggregation_unavailable",
                "The requested Aggregation is not available in the cached data.",
            )
        # Only trusted catalog IDs enter filenames, never an arbitrary user path.
        path = (
            self.series_dir / f"{region['region_id']}__{variable['variable_id']}.json"
        )
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(result, dict):
                raise TypeError
            result["timestamps"] = [
                month + "-01" for month in months_in(Period(**result["period"]))
            ]
        except (OSError, ValueError, KeyError, TypeError):
            raise ProcessingError(
                "source_unavailable",
                "No cached data is available for this Variable and area.",
            ) from None
        dataset_id = selection.get("dataset_id")
        if dataset_id is not None and dataset_id not in (
            result.get("dataset_id"),
            result.get("source", {}).get("dataset"),
        ):
            raise ProcessingError(
                "dataset_unavailable",
                "The selected dataset is not available in the cached data.",
            )
        result.setdefault("time_step", "monthly")
        result.setdefault("aggregation", "mean")
        result.setdefault("calendar", "standard")
        result["variable_name"] = variable.get("name", selection["variable"])
        result["area_name"] = region.get("name", selection["area"])
        return result

    @staticmethod
    def _find(entries, key, requested):
        if not isinstance(requested, str):
            return None
        query = requested.strip().casefold()
        return next(
            (
                entry
                for entry in entries
                if isinstance(entry, Mapping)
                and query
                in (
                    str(entry.get(key, "")).casefold(),
                    str(entry.get("name", "")).casefold(),
                )
            ),
            None,
        )
