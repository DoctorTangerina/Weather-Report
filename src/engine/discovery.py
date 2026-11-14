"""Finding, scoring and presenting Candidate Discoveries.

Rule-based throughout (ADR 0001): the numbers come from the statistics and the
text comes from templates over those numbers. An LLM may rephrase the result
(ticket #18) but may not add to it.
"""

from __future__ import annotations

import dataclasses
import math
import random
from decimal import ROUND_HALF_UP, Decimal
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations

from .contracts import (
    NOT_ENOUGH_EVIDENCE,
    SOME_EVIDENCE,
    STRONG_EVIDENCE,
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
    ScoreComponents,
    SeriesRef,
    Trend,
    Variable,
)
from .version import ENGINE_VERSION

# Two same-direction Trends contrast when the faster rate is at least this many
# times the slower. The spec left "a lot" open; a factor of two is the plainest
# reading that a student can see on a chart.
MAGNITUDE_GAP_RATIO = 2.0
# Two Regions are a surprising pair when their bbox centers are within this
# distance (ADR 0003). A placeholder: 13 of the 276 catalog pairs fall inside it.
SURPRISING_PAIR_KM = 2500.0
EARTH_RADIUS_KM = 6371.0
# Score weights. Only their order is specified: opposite signs, then a
# multi-Variable contrast, then the size of the magnitude gap. The gap component
# is capped below MULTI_VARIABLE_SCORE and that below OPPOSITE_SIGN_SCORE, so the
# order holds whatever the data.
OPPOSITE_SIGN_SCORE = 100.0
MULTI_VARIABLE_SCORE = 20.0
# The same tier as a multi-Variable contrast, as the spec ranks them together.
SURPRISING_PAIR_SCORE = 20.0
MAGNITUDE_GAP_CAP = 10.0
# Added once for each Mirror between the pair that is significant after
# correction (ADR 0003). The smallest tier: a Mirror adds to a Discovery that
# already has a Contrast and never makes one.
MIRROR_SCORE = 5.0

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
    """Tickets #7 and #8. Mirrors are optional because ticket #8 may be cut.

    Every pair of Regions is compared on every Variable both have a Trend for.
    A Variable contrasts when the two Trends run in opposite directions
    (`opposite_sign`) or in the same direction at rates `MAGNITUDE_GAP_RATIO`
    or more apart, with 95% intervals that do not overlap (`magnitude_gap`). When
    neither Trend is significant the ratio alone decides, and the contrast stays
    as a Candidate labeled "Not enough evidence yet". A pair with at least one
    contrast is one Candidate Discovery, however many Variables contrast. A pair
    of Regions close together is also a surprising pair, which raises its score.

    `mirrors` come from `find_mirrors`. A Mirror joins the Candidate for the two
    Regions it lies between and raises its score; it never makes a Candidate on
    its own, since a Discovery is built around a Contrast. A Mirror that is not
    significant after correction is left out.

    `trends` should come from `rate_evidence`, which settles the Evidence
    labels. A contrast with a Trend that has "Not enough evidence yet" is kept,
    and so labeled, only when the pair has no contrast that rests on evidence;
    otherwise it would pull the whole Candidate down.

    The result is ordered from highest score to lowest.
    """
    periods = {trend.period for trend in trends}
    if len(periods) > 1:
        raise ValueError("every Trend must cover the same period")

    by_region: dict[str, dict[str, Trend]] = defaultdict(dict)
    for trend in trends:
        by_region[trend.region_id][trend.variable_id] = trend

    mirrors_by_pair: dict[tuple[str, str], list[Mirror]] = defaultdict(list)
    for mirror in mirrors:
        if mirror.significant_after_correction:
            regions = sorted({ref.region_id for ref in mirror.series})
            mirrors_by_pair[tuple(regions)].append(mirror)

    candidates = []
    for first, second in combinations(sorted(by_region), 2):
        contrasts = _contrasts(by_region[first], by_region[second])
        supported = [c for c in contrasts if not _lacks_evidence(c)]
        contrasts = sorted(supported or contrasts, key=_contrast_score, reverse=True)
        if not contrasts:
            continue
        period = contrasts[0].trends[0].period
        label = _weakest_label(contrasts)
        pair_mirrors = mirrors_by_pair[first, second]
        components = _score_components(
            contrasts, _are_close(catalog, first, second), len(pair_mirrors)
        )
        candidates.append(
            Discovery(
                discovery_id=f"{first}--{second}",
                region_ids=(first, second),
                period=period,
                contrasts=tuple(contrasts),
                mirrors=tuple(pair_mirrors),
                score=sum(dataclasses.astuple(components)),
                score_components=components,
                evidence_label=label,
                headline_eligible=label != NOT_ENOUGH_EVIDENCE,
                narrative=build_narrative(contrasts, period, label, catalog),
                engine_version=ENGINE_VERSION,
            )
        )
    return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)


def _contrasts(left: dict[str, Trend], right: dict[str, Trend]) -> list[Contrast]:
    found = []
    for variable_id in sorted(left.keys() & right.keys()):
        pair = (left[variable_id], right[variable_id])
        if {pair[0].direction, pair[1].direction} == {"rising", "falling"}:
            found.append(Contrast(variable_id, "opposite_sign", pair))
        elif _is_magnitude_gap(pair):
            found.append(Contrast(variable_id, "magnitude_gap", pair))
    return found


def _is_magnitude_gap(pair: tuple[Trend, Trend]) -> bool:
    if _magnitude_ratio(pair) < MAGNITUDE_GAP_RATIO:
        return False
    if all(trend.evidence_label == NOT_ENOUGH_EVIDENCE for trend in pair):
        return True  # no Trend to separate with an interval; kept as a lead
    (low_a, high_a), (low_b, high_b) = (t.confidence_interval_95 for t in pair)
    return high_a < low_b or high_b < low_a


def _magnitude_ratio(pair: tuple[Trend, Trend]) -> float:
    """How many times larger the faster rate is; infinite against a rate of zero."""
    low, high = sorted(abs(trend.rate_per_decade) for trend in pair)
    if high == 0:
        return 1.0
    return math.inf if low == 0 else high / low


def _lacks_evidence(contrast: Contrast) -> bool:
    return any(t.evidence_label == NOT_ENOUGH_EVIDENCE for t in contrast.trends)


def _weakest_label(contrasts: Sequence[Contrast]) -> EvidenceLabel:
    labels = {trend.evidence_label for c in contrasts for trend in c.trends}
    for label in (NOT_ENOUGH_EVIDENCE, SOME_EVIDENCE):
        if label in labels:
            return label
    return STRONG_EVIDENCE


def _are_close(catalog: Catalog, first: str, second: str) -> bool:
    """Whether two Regions' bbox centers lie within `SURPRISING_PAIR_KM`."""
    centers = []
    for region_id in (first, second):
        region = catalog.region(region_id)
        if region is None:
            raise ValueError(f"Region {region_id!r} is not in the catalog")
        bbox = region.bbox
        # A box that crosses the antimeridian has west > east.
        east = bbox.east + 360 if bbox.west > bbox.east else bbox.east
        centers.append(((bbox.south + bbox.north) / 2, (bbox.west + east) / 2))
    (lat1, lon1), (lat2, lon2) = (
        (math.radians(lat), math.radians(lon)) for lat, lon in centers
    )
    haversine = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    distance = 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(haversine))
    return distance <= SURPRISING_PAIR_KM


def _contrast_score(contrast: Contrast) -> float:
    if contrast.kind == "opposite_sign":
        return OPPOSITE_SIGN_SCORE
    return _gap_score(contrast)


def _gap_score(contrast: Contrast) -> float:
    return min(math.log2(_magnitude_ratio(contrast.trends)), MAGNITUDE_GAP_CAP)


def _score_components(
    contrasts: Sequence[Contrast], close_together: bool, mirror_count: int
) -> ScoreComponents:
    """What a Candidate scores, in the order the spec fixes and no more.

    Opposite signs outrank everything (`OPPOSITE_SIGN_SCORE` is above the sum of
    every other component can reach), then a contrast on several Variables, then
    how far apart the rates are. A surprising pair earns the multi-Variable tier.
    Each Mirror adds `MIRROR_SCORE` on top.
    """
    opposite = any(c.kind == "opposite_sign" for c in contrasts)
    gaps = [_gap_score(c) for c in contrasts if c.kind == "magnitude_gap"]
    return ScoreComponents(
        opposite_sign=OPPOSITE_SIGN_SCORE if opposite else 0.0,
        multi_variable=MULTI_VARIABLE_SCORE if len(contrasts) > 1 else 0.0,
        surprising_pair=SURPRISING_PAIR_SCORE if close_together else 0.0,
        magnitude_gap=max(gaps, default=0.0),
        mirror=MIRROR_SCORE * mirror_count,
    )


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

def build_narrative(
    contrasts: Sequence[Contrast],
    period: Period,
    evidence_label: EvidenceLabel,
    catalog: Catalog,
) -> Narrative:
    """The question, the Become a Detective steps and "How do we know?".

    The first Contrast is the lead: it drives the question and the three steps,
    so callers order `contrasts` from most to least notable by score.

    Ticket #10 owns the wording and its tests. This is the least that gives a
    Candidate Discovery the narrative its contract requires: templates with no
    numbers in them, so nothing here can be a number the engine did not compute.
    """
    lead = contrasts[0]
    variable = catalog.variable(lead.variable_id)
    if variable is None:
        raise ValueError(f"Variable {lead.variable_id!r} is not in the catalog")
    first, second = lead.trends
    names = []
    for trend in lead.trends:
        region = catalog.region(trend.region_id)
        if region is None:
            raise ValueError(f"Region {trend.region_id!r} is not in the catalog")
        names.append(region.name)
    subject = variable.name.lower()
    faster = (
        first if abs(first.rate_per_decade) >= abs(second.rate_per_decade) else second
    )
    return Narrative(
        question=f"Why does {subject} change so differently in these two places?",
        investigation=Investigation(
            steps=(
                PredictStep(
                    question=f"Where do you think {subject} is changing faster?",
                    options=tuple(
                        PredictOption(trend.region_id, name)
                        for trend, name in zip(lead.trends, names, strict=True)
                    ),
                    answer_option_id=faster.region_id,
                ),
                CheckStep(
                    series=(
                        SeriesRef(first.region_id, first.variable_id),
                        SeriesRef(second.region_id, second.variable_id),
                    ),
                    comparison=f"Compare {subject} in {names[0]} and {names[1]}.",
                ),
                ReasonStep(
                    prompt=f"What could make {subject} change this way?",
                    possible_causes=tuple(
                        PossibleCause(cause.text) for cause in variable.possible_causes
                    ),
                ),
            )
        ),
        how_do_we_know=HowDoWeKnow(
            period=period,
            sources=tuple(
                EvidenceSource(t.region_id, t.variable_id, t.source)
                for contrast in contrasts
                for t in contrast.trends
            ),
            statistics_summary=f"Each Trend was rated: {evidence_label}.",
            method_citation=first.method_citation,
        ),
    )
      
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
