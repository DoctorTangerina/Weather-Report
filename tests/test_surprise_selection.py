"""Seam 1: Surprise Me! selection through the engine's public interface.

Covers BS-005 (no repeated Discovery, no repeated Region) and the BS-004
scenario that a Candidate without enough evidence is never the headline.

Candidates are built by varying a real committed Discovery, so the fixtures
carry a full, schema-valid narrative rather than a hand-made stand-in.
"""

from __future__ import annotations

import json
import random
from dataclasses import replace
from pathlib import Path

import pytest

from engine import SessionHistory, select_surprise
from engine.contracts import Discovery

SEED = 20241114

# A rule the selector must never break is checked across many draws, not one seed:
# with a single seed a weighted draw can satisfy the assertion by luck.
DRAWS = 300


@pytest.fixture(scope="module")
def template(stub_dir: Path) -> Discovery:
    payload = json.loads(
        (stub_dir / "discoveries" / "amazon-basin--sahel.json").read_text(
            encoding="utf-8"
        )
    )
    return Discovery.from_dict(payload)


def candidate(
    template: Discovery,
    discovery_id: str,
    regions: tuple[str, str],
    score: float,
    evidence_label: str = "Strong evidence",
) -> Discovery:
    return replace(
        template,
        discovery_id=discovery_id,
        region_ids=regions,
        score=score,
        evidence_label=evidence_label,
        headline_eligible=evidence_label != "Not enough evidence yet",
    )


@pytest.fixture
def rng() -> random.Random:
    return random.Random(SEED)


def test_a_discovery_is_selected_when_the_session_is_empty(template, rng):
    candidates = [candidate(template, "a--b", ("a", "b"), 9.0)]
    chosen = select_surprise(candidates, SessionHistory(), rng=rng)
    assert chosen is not None
    assert chosen.discovery_id == "a--b"


def test_a_discovery_already_shown_is_not_shown_again(template, rng):
    candidates = [
        candidate(template, "a--b", ("a", "b"), 9.0),
        candidate(template, "c--d", ("c", "d"), 8.0),
    ]
    history = SessionHistory(shown_discovery_ids=("a--b",), shown_region_ids=("a", "b"))

    chosen = select_surprise(candidates, history, rng=rng)
    assert chosen is not None
    assert chosen.discovery_id == "c--d"


def test_a_region_already_shown_is_avoided(template):
    """Across many draws, never once: the reusing Candidate outscores the other 10:1."""
    candidates = [
        candidate(template, "a--c", ("a", "c"), 9.9),
        candidate(template, "d--e", ("d", "e"), 1.0),
    ]
    history = SessionHistory(shown_discovery_ids=("a--b",), shown_region_ids=("a", "b"))

    drawn = {
        select_surprise(candidates, history, rng=random.Random(seed)).discovery_id
        for seed in range(DRAWS)
    }
    assert drawn == {"d--e"}


def test_a_candidate_without_enough_evidence_is_never_the_headline(template):
    candidates = [
        candidate(template, "a--b", ("a", "b"), 9.9, "Not enough evidence yet"),
        candidate(template, "c--d", ("c", "d"), 0.1),
    ]
    drawn = {
        select_surprise(
            candidates, SessionHistory(), rng=random.Random(seed)
        ).discovery_id
        for seed in range(DRAWS)
    }
    assert drawn == {"c--d"}


def test_a_weak_candidate_is_skipped_even_if_it_claims_to_be_eligible(template):
    """A Candidate built in memory has passed no schema, so the label is checked."""
    mislabeled = replace(
        candidate(template, "a--b", ("a", "b"), 9.9, "Not enough evidence yet"),
        headline_eligible=True,
    )
    candidates = [mislabeled, candidate(template, "c--d", ("c", "d"), 0.1)]

    drawn = {
        select_surprise(
            candidates, SessionHistory(), rng=random.Random(seed)
        ).discovery_id
        for seed in range(DRAWS)
    }
    assert drawn == {"c--d"}


def test_nothing_is_returned_once_every_eligible_discovery_has_been_shown(
    template, rng
):
    candidates = [
        candidate(template, "a--b", ("a", "b"), 9.0),
        candidate(template, "c--d", ("c", "d"), 8.0, "Not enough evidence yet"),
    ]
    history = SessionHistory(shown_discovery_ids=("a--b",), shown_region_ids=("a", "b"))

    assert select_surprise(candidates, history, rng=rng) is None


def test_the_region_rule_gives_way_before_the_session_dead_ends(template, rng):
    """BS-005 avoids a repeated Region; it never repeats a Discovery."""
    candidates = [
        candidate(template, "a--b", ("a", "b"), 9.0),
        candidate(template, "b--c", ("b", "c"), 8.0),
    ]
    history = SessionHistory(shown_discovery_ids=("a--b",), shown_region_ids=("a", "b"))

    chosen = select_surprise(candidates, history, rng=rng)
    assert chosen is not None
    assert chosen.discovery_id == "b--c", "a reused Region beats showing nothing"


def test_the_draw_only_considers_the_top_n_by_score(template, rng):
    candidates = [
        candidate(template, f"r{index}--s{index}", (f"r{index}", f"s{index}"), score)
        for index, score in enumerate([9.0, 8.0, 7.0, 0.5, 0.4, 0.3])
    ]
    drawn = {
        select_surprise(
            candidates, SessionHistory(), top_n=3, rng=random.Random(seed)
        ).discovery_id
        for seed in range(200)
    }
    assert drawn == {"r0--s0", "r1--s1", "r2--s2"}


def test_the_draw_is_weighted_so_a_better_candidate_headlines_more_often(template):
    candidates = [
        candidate(template, "strong", ("a", "b"), 9.0),
        candidate(template, "weak", ("c", "d"), 1.0),
    ]
    draws = [
        select_surprise(
            candidates, SessionHistory(), rng=random.Random(seed)
        ).discovery_id
        for seed in range(1000)
    ]
    strong = draws.count("strong")

    assert strong > draws.count("weak")
    assert 0.80 < strong / len(draws) < 0.99, f"expected roughly 9:1, got {strong}/1000"


def test_the_draw_still_returns_something_when_no_score_is_positive(template):
    candidates = [
        candidate(template, "a--b", ("a", "b"), 0.0),
        candidate(template, "c--d", ("c", "d"), 0.0),
    ]
    drawn = {
        select_surprise(
            candidates, SessionHistory(), rng=random.Random(seed)
        ).discovery_id
        for seed in range(50)
    }
    assert drawn == {"a--b", "c--d"}


def test_no_candidates_at_all_returns_nothing(rng):
    assert select_surprise([], SessionHistory(), rng=rng) is None


def test_selection_does_not_mutate_the_candidates_it_was_given(template, rng):
    candidates = [
        candidate(template, "a--b", ("a", "b"), 9.0),
        candidate(template, "c--d", ("c", "d"), 8.0),
    ]
    before = list(candidates)

    select_surprise(candidates, SessionHistory(), rng=rng)

    assert candidates == before
