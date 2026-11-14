"""Finding, scoring and presenting Candidate Discoveries.

Rule-based throughout (ADR 0001): the numbers come from the statistics and the
text comes from templates over those numbers. An LLM may rephrase the result
(ticket #18) but may not add to it.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from .contracts import (
    NOT_ENOUGH_EVIDENCE,
    Catalog,
    CheckStep,
    Contrast,
    Discovery,
    EvidenceLabel,
    EvidenceSource,
    HowDoWeKnow,
    Investigation,
    Mirror,
    Narrative,
    Period,
    PossibleCause,
    PredictOption,
    PredictStep,
    ReasonStep,
    Region,
    Series,
    SeriesRef,
    Trend,
    Variable,
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


def build_narrative(
    contrasts: Sequence[Contrast],
    period: Period,
    evidence_label: EvidenceLabel,
    catalog: Catalog,
) -> Narrative:
    """The question, the Become a Detective steps and "How do we know?".

    Takes the parts of a Discovery the text is built from, so a Discovery can
    be assembled with its narrative in one step (ticket #7 calls this).

    Templates over those computed values, with no LLM (ADR 0001): every number
    in the text is a value carried by a Trend or the period, rounded by
    `_number`.

    The first Contrast is the lead Contrast: it drives the question and the
    three steps, so the caller orders `contrasts` from most to least notable.
    "How do we know?" names the source of every Trend, since the evidence view
    reads their rates from `contrasts`.
    """
    if not contrasts:
        raise ValueError("a Discovery needs at least one Contrast")
    headline = contrasts[0]
    variable = _catalog_variable(catalog, headline.variable_id)
    first, second = headline.trends
    regions = {
        trend.region_id: _catalog_region(catalog, trend.region_id)
        for trend in headline.trends
    }
    faster = (
        first if abs(first.rate_per_decade) >= abs(second.rate_per_decade) else second
    )
    subject = variable.name.lower()

    predict = PredictStep(
        question=f"Where do you think {subject} is changing faster?",
        options=tuple(
            PredictOption(
                option_id=trend.region_id, label=regions[trend.region_id].name
            )
            for trend in headline.trends
        ),
        answer_option_id=faster.region_id,
    )
    check = CheckStep(
        series=(
            SeriesRef(first.region_id, first.variable_id),
            SeriesRef(second.region_id, second.variable_id),
        ),
        comparison=(
            f"{regions[first.region_id].name}: {_rate_text(first)}. "
            f"{regions[second.region_id].name}: {_rate_text(second)}. "
            f"{regions[faster.region_id].name} is changing faster. "
            f"{_evidence_text(first, regions)} {_evidence_text(second, regions)}"
        ),
    )
    reason = ReasonStep(
        prompt=f"What could make {subject} change this way?",
        # Rebuilt so each cause is always labeled context, never a data result.
        possible_causes=tuple(
            PossibleCause(text=cause.text) for cause in variable.possible_causes
        ),
    )
    return Narrative(
        question=_question(headline, variable),
        investigation=Investigation(steps=(predict, check, reason)),
        how_do_we_know=HowDoWeKnow(
            period=period,
            sources=_evidence_sources(contrasts),
            statistics_summary=_statistics_summary(period, evidence_label, headline),
            method_citation=first.method_citation,
        ),
    )


def _catalog_variable(catalog: Catalog, variable_id: str) -> Variable:
    variable = catalog.variable(variable_id)
    if variable is None:
        raise ValueError(f"Variable {variable_id!r} is not in the catalog")
    return variable


def _catalog_region(catalog: Catalog, region_id: str) -> Region:
    region = catalog.region(region_id)
    if region is None:
        raise ValueError(f"Region {region_id!r} is not in the catalog")
    return region


def _number(value: float) -> str:
    """A computed value as shown to a student.

    Rounded half up to at most three decimals, in decimal arithmetic rather
    than binary floating point, with no trailing zeros: 7.0625 is 7.063 and
    5.500 is 5.5. A value that rounds to zero is 0, never -0. The frontend
    applies the same rule to the rates it lists (see the Discovery schema).
    """
    rounded = Decimal(repr(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    text = format(rounded, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def _evidence_text(trend: Trend, regions: dict[str, Region]) -> str:
    """Names a Trend's Evidence label and says nothing more about it."""
    return (
        f"Evidence label for {regions[trend.region_id].name}: {trend.evidence_label}."
    )


def _rate_text(trend: Trend) -> str:
    low, high = trend.confidence_interval_95
    return (
        f"{_number(trend.rate_per_decade)} {trend.units_per_decade} "
        f"(95% interval {_number(low)} to {_number(high)})"
    )


def _question(headline: Contrast, variable: Variable) -> str:
    first, second = headline.trends
    if NOT_ENOUGH_EVIDENCE in (first.evidence_label, second.evidence_label):
        # A Trend without enough evidence has no established direction, so the
        # question may not state one (ADR 0001).
        return (
            f"{variable.name} seems to be changing faster in one of these "
            "places than in the other. Is the difference real?"
        )
    if headline.kind == "opposite_sign":
        return (
            f"{variable.name} is rising in one of these places and falling in "
            "the other. Which is which?"
        )
    if first.direction == second.direction and first.direction != "flat":
        return (
            f"{variable.name} is {first.direction} in both of these places. Why "
            "would it change so much faster in one of them?"
        )
    return (
        f"{variable.name} is changing at very different rates in these two "
        "places. Why would one change so much faster?"
    )


def _evidence_sources(contrasts: Sequence[Contrast]) -> tuple[EvidenceSource, ...]:
    sources: dict[tuple[str, str], EvidenceSource] = {}
    for contrast in contrasts:
        for trend in contrast.trends:
            key = (trend.region_id, trend.variable_id)
            sources.setdefault(
                key,
                EvidenceSource(
                    region_id=trend.region_id,
                    variable_id=trend.variable_id,
                    source=trend.source,
                ),
            )
    return tuple(sources.values())


def _statistics_summary(
    period: Period, evidence_label: EvidenceLabel, headline: Contrast
) -> str:
    comparisons = headline.trends[0].multiple_comparisons
    return (
        f"Each series covers {period.start} to {period.end}. The seasonal cycle "
        "was removed, then a least-squares fit gave each rate per decade and its "
        "95% interval. Fits on annual anomalies, a robust fit, a rerun without the "
        "most extreme month and a Theil-Sen fit with a Mann-Kendall test checked "
        "that result. The fits were corrected for month-to-month autocorrelation "
        f"and, because {_number(comparisons.family_size)} series were tested, for "
        f"false discoveries at a rate of {_number(comparisons.q)}. Together these "
        f"give the Evidence label: {evidence_label}."
    )
