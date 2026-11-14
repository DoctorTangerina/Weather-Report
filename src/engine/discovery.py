"""Finding, scoring and presenting Candidate Discoveries.

Rule-based throughout (ADR 0001): the numbers come from the statistics and the
text comes from templates over those numbers. An LLM may rephrase the result
(ticket #18) but may not add to it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .contracts import Catalog, Discovery, Mirror, Narrative, Series, Trend


@dataclass(frozen=True)
class SessionHistory:
    """What a student has already been shown, so Surprise Me! does not repeat."""

    shown_discovery_ids: tuple[str, ...] = ()
    shown_region_ids: tuple[str, ...] = ()


def find_candidate_discoveries(
    trends: Sequence[Trend],
    catalog: Catalog,
    mirrors: Sequence[Mirror] = (),
) -> list[Discovery]:
    """Ticket #7. Mirrors are optional because ticket #8 may be cut."""
    raise NotImplementedError("candidate discoveries: ticket #7")


def find_mirrors(series: Sequence[Series], q: float) -> list[Mirror]:
    """Ticket #8."""
    raise NotImplementedError("mirrors: ticket #8")


def select_surprise(
    candidates: Sequence[Discovery],
    history: SessionHistory,
) -> Discovery | None:
    """Ticket #9. None once the session has no unseen Discovery left to offer."""
    raise NotImplementedError("surprise me selection: ticket #9")


def build_narrative(discovery: Discovery, catalog: Catalog) -> Narrative:
    """Ticket #10."""
    raise NotImplementedError("explanations and investigation content: ticket #10")
