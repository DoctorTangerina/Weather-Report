"""Finding, scoring and presenting Candidate Discoveries.

Rule-based throughout (ADR 0001): the numbers come from the statistics and the
text comes from templates over those numbers. An LLM may rephrase the result
(ticket #18) but may not add to it.
"""

from __future__ import annotations

import dataclasses
import math
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
) -> Discovery | None:
    """Ticket #9. None once the session has no unseen Discovery left to offer."""
    raise NotImplementedError("surprise me selection: ticket #9")


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
