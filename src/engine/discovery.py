"""Finding, scoring and presenting Candidate Discoveries.

Rule-based throughout (ADR 0001): the numbers come from the statistics and the
text comes from templates over those numbers. An LLM may rephrase the result
(ticket #18) but may not add to it.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from .contracts import (
    NOT_ENOUGH_EVIDENCE,
    Catalog,
    Discovery,
    Mirror,
    Narrative,
    Series,
    Trend,
)

# How many of the highest-scoring eligible Candidates the Surprise Me! draw
# considers. The spec left the number open. Five keeps the headline genuinely
# top-ranked while still varying between sessions, and because the draw is
# weighted by score, raising it costs little quality.
TOP_N = 5


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
    *,
    top_n: int = TOP_N,
    rng: random.Random | None = None,
) -> Discovery | None:
    """Pick the Discovery to headline next, or None once the session is spent.

    Candidates are filtered for eligibility first and ranked afterwards, so a
    long session works its way down the list instead of running dry the moment
    it has seen a fixed top N.

    BS-005 states its two session rules with different force: a Discovery is
    *never* repeated, while a Region is *avoided*. So when every remaining
    Candidate would reuse a Region, the Region rule gives way rather than the
    student getting nothing back. Only a session that has seen every eligible
    Discovery returns None.
    """
    unseen = [
        candidate
        for candidate in candidates
        if can_headline(candidate)
        and candidate.discovery_id not in history.shown_discovery_ids
    ]
    with_fresh_regions = [
        candidate for candidate in unseen if not _reuses_a_region(candidate, history)
    ]

    ranked = sorted(
        with_fresh_regions or unseen,
        key=lambda candidate: candidate.score,
        reverse=True,
    )[:top_n]
    if not ranked:
        return None
    return _weighted_draw(ranked, rng if rng is not None else random.Random())


def can_headline(candidate: Discovery) -> bool:
    """BS-004: a Candidate without enough evidence is never the headline.

    `headline_eligible` is the field the contract carries, and the schema already
    ties it to the Evidence label. The label is checked too so that a Candidate
    built in memory, which no schema has validated, cannot slip through.
    """
    return (
        candidate.headline_eligible and candidate.evidence_label != NOT_ENOUGH_EVIDENCE
    )


def _reuses_a_region(candidate: Discovery, history: SessionHistory) -> bool:
    return any(
        region_id in history.shown_region_ids for region_id in candidate.region_ids
    )


def _weighted_draw(ranked: Sequence[Discovery], rng: random.Random) -> Discovery:
    """Draw weighted by score, so a better Candidate headlines more often.

    Scores are weights, so a negative one would be meaningless; those are floored
    at zero. If that leaves nothing to weigh by, the draw is uniform.
    """
    population = list(ranked)
    weights = [max(candidate.score, 0.0) for candidate in population]
    if sum(weights) == 0:
        return rng.choice(population)
    return rng.choices(population, weights=weights, k=1)[0]


def build_narrative(discovery: Discovery, catalog: Catalog) -> Narrative:
    """Ticket #10."""
    raise NotImplementedError("explanations and investigation content: ticket #10")
