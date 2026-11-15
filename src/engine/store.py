"""Where computed results are kept between runs.

The store holds JSON payloads rather than contract objects: it is a cache of
results to serve, keyed by Region, Variable, period and engine version. Code
that needs to compute on a series converts with `Series.from_dict`.

`JsonResultStore` reads the committed stub set today and the seed set once
ticket #12 lands. A cache miss returns None; deciding what to do about it
belongs to the caller (ticket #13).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from .contracts import Period

SeriesKey = tuple[str, str, str, str, str]


class ResultStore(Protocol):
    def series(
        self, region_id: str, variable_id: str, period: Period
    ) -> dict[str, Any] | None: ...

    def available_series(self) -> list[dict[str, Any]]: ...

    def discoveries(self) -> list[dict[str, Any]]: ...

    def discovery(self, discovery_id: str) -> dict[str, Any] | None: ...


class JsonResultStore:
    def __init__(self, root: str | Path, engine_version: str) -> None:
        self._root = Path(root)
        self._engine_version = engine_version
        self._series: dict[SeriesKey, dict[str, Any]] = {}
        self._discoveries: list[dict[str, Any]] = []
        self._load()

    def series(
        self, region_id: str, variable_id: str, period: Period
    ) -> dict[str, Any] | None:
        key = (region_id, variable_id, period.start, period.end, self._engine_version)
        return self._series.get(key)

    def available_series(self) -> list[dict[str, Any]]:
        """Which Region-Variable series this store holds, without their values."""
        return [
            {
                "region_id": region_id,
                "variable_id": variable_id,
                "period": {"start": start, "end": end},
            }
            for region_id, variable_id, start, end, version in sorted(self._series)
            if version == self._engine_version
        ]

    def discoveries(self) -> list[dict[str, Any]]:
        return list(self._discoveries)

    def discovery(self, discovery_id: str) -> dict[str, Any] | None:
        return next(
            (d for d in self._discoveries if d["discovery_id"] == discovery_id), None
        )

    def _load(self) -> None:
        for path in sorted(self._root.glob("series/*.json")):
            payload = _read(path)
            self._series[_series_key(payload)] = payload
        for path in sorted(self._root.glob("discoveries/*.json")):
            self._discoveries.append(_read(path))
        self._discoveries.sort(key=lambda d: d["score"], reverse=True)


def _series_key(payload: dict[str, Any]) -> SeriesKey:
    return (
        payload["region_id"],
        payload["variable_id"],
        payload["period"]["start"],
        payload["period"]["end"],
        payload["engine_version"],
    )


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
