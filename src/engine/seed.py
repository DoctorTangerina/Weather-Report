"""The seed set: results computed offline so the demo works with no network (#12).

`compute_seed_set` runs the whole engine over the Series it is given: it rates
every Trend as one family (ADR 0002), finds the Mirrors, and lists the Candidate
Discoveries. `write_seed_set` lays the result out the way `JsonResultStore`
reads it. Acquiring the real Series is the data layer's job (#6), so this module
takes Series and never touches the network.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .contracts import (
    NOT_ENOUGH_EVIDENCE,
    SOME_EVIDENCE,
    STRONG_EVIDENCE,
    Catalog,
    Discovery,
    Series,
    as_dict,
)
from .discovery import find_candidate_discoveries
from .mirror import find_mirrors
from .quality import usable_series
from .trend import estimate_trend, rate_evidence

EVIDENCE_LABELS = (STRONG_EVIDENCE, SOME_EVIDENCE, NOT_ENOUGH_EVIDENCE)


@dataclass(frozen=True)
class SeedSet:
    """Every Series, kept for the results service, and the Candidates found."""

    series: tuple[Series, ...]
    discoveries: tuple[Discovery, ...]


def compute_seed_set(series: Sequence[Series], catalog: Catalog) -> SeedSet:
    """Candidate Discoveries and Mirrors over the usable Series.

    A Series the Quality gate excluded is kept in the result, with its reasons,
    but takes no part in any Trend, Mirror or Candidate (BS-003).
    """
    usable = usable_series(series)
    trends = rate_evidence([estimate_trend(one) for one in usable])
    discoveries = find_candidate_discoveries(trends, catalog, find_mirrors(usable))
    return SeedSet(series=tuple(series), discoveries=tuple(discoveries))


def missing_evidence_labels(discoveries: Iterable[Discovery]) -> list[str]:
    """The Evidence labels no Candidate carries, so a demo lacking a case is seen."""
    present = {discovery.evidence_label for discovery in discoveries}
    return [label for label in EVIDENCE_LABELS if label not in present]


def write_seed_set(seed: SeedSet, directory: str | Path) -> None:
    """Replace `series/` and `discoveries/` under `directory` with this seed set.

    The old files are removed first so a rerun cannot leave a Candidate that the
    new data no longer supports.
    """
    root = Path(directory)
    for name in ("series", "discoveries"):
        shutil.rmtree(root / name, ignore_errors=True)
        (root / name).mkdir(parents=True)
    for one in seed.series:
        _write(root / "series" / f"{one.region_id}__{one.variable_id}.json", one)
    for discovery in seed.discoveries:
        _write(root / "discoveries" / f"{discovery.discovery_id}.json", discovery)


def _write(path: Path, contract: Series | Discovery) -> None:
    path.write_text(
        json.dumps(as_dict(contract), indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
