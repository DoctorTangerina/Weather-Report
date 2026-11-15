"""Finished Selected-area Series, kept apart from every Region store (#79).

A Selected area is never a Region, so its Series live in their own folder and
can never be listed as a stored Region Series or feed the Discovery engine.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from engine import ENGINE_VERSION
from engine.contracts import Period


class AreaSeriesCache:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def _path(self, rectangles: list, variable_id: str, period: Period) -> Path:
        identity = json.dumps(
            [rectangles, variable_id, period.start, period.end, ENGINE_VERSION]
        )
        return self._root / f"{hashlib.sha256(identity.encode()).hexdigest()}.json"

    def series(
        self, rectangles: list, variable_id: str, period: Period
    ) -> dict[str, Any] | None:
        try:
            return json.loads(
                self._path(rectangles, variable_id, period).read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            return None

    def save_series(self, payload: dict[str, Any]) -> None:
        """Publish a complete entry atomically, so a reader never sees half of it."""
        path = self._path(
            payload["area"]["rectangles"],
            payload["variable_id"],
            Period(**payload["period"]),
        )
        self._root.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", dir=self._root, suffix=".tmp", delete=False, encoding="utf-8"
            ) as handle:
                temporary = Path(handle.name)
                json.dump(payload, handle, allow_nan=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
