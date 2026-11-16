"""BS-004: the engine finds contrasts between pairs of Regions by itself.

Driven through `engine.find_candidate_discoveries` over Trends estimated from
synthetic series, with no network.
"""

from __future__ import annotations

import dataclasses
import json

import pytest
from synthetic import rated_trends

from engine import Catalog, Period, find_candidate_discoveries, load_catalog
from engine.contracts import as_dict


@pytest.fixture(scope="module")
def catalog(catalog_path) -> Catalog:
    return load_catalog(catalog_path)


def test_two_significant_trends_of_opposite_sign_are_a_candidate(catalog):
    trends = rated_trends(
        {("amazon-basin", "temperature"): 0.6, ("sahel", "temperature"): -0.6}
    )
    # Given both Trends are significant after correction, one rising and one falling.
    assert [t.evidence_label for t in trends] == ["Strong evidence"] * 2
    assert {t.direction for t in trends} == {"rising", "falling"}

    candidates = find_candidate_discoveries(trends, catalog)

    (candidate,) = candidates
    assert candidate.region_ids == ("amazon-basin", "sahel")
    (contrast,) = candidate.contrasts
    assert contrast.variable_id == "temperature"
    assert contrast.kind == "opposite_sign"


def test_a_pair_that_contrasts_on_two_variables_is_one_candidate(catalog):
    trends = rated_trends(
        {
            ("amazon-basin", "temperature"): 0.3,
            ("sahel", "temperature"): 0.9,
            ("amazon-basin", "precipitation"): -0.6,
            ("sahel", "precipitation"): 0.6,
        }
    )
    # Given one Region has rising temperature and falling precipitation, the
    # other rising temperature and rising precipitation, all of them significant.
    by_key = {(t.region_id, t.variable_id): t for t in trends}
    assert by_key["amazon-basin", "temperature"].direction == "rising"
    assert by_key["sahel", "temperature"].direction == "rising"
    assert by_key["amazon-basin", "precipitation"].direction == "falling"
    assert by_key["sahel", "precipitation"].direction == "rising"

    (candidate,) = find_candidate_discoveries(trends, catalog)

    assert {c.variable_id for c in candidate.contrasts} == {
        "temperature",
        "precipitation",
    }
    assert {c.variable_id: c.kind for c in candidate.contrasts} == {
        "temperature": "magnitude_gap",
        "precipitation": "opposite_sign",
    }


def test_a_contrast_without_significant_trends_is_not_enough_evidence(catalog):
    trends = rated_trends(
        {("amazon-basin", "temperature"): 0.0, ("sahel", "temperature"): 0.0}
    )
    # Given the Trends differ in magnitude and neither is significant.
    low, high = sorted(abs(t.rate_per_decade) for t in trends)
    assert high > 2 * low
    assert {t.evidence_label for t in trends} == {"Not enough evidence yet"}

    (candidate,) = find_candidate_discoveries(trends, catalog)

    assert candidate.evidence_label == "Not enough evidence yet"
    assert not candidate.headline_eligible
    (contrast,) = candidate.contrasts
    assert contrast.kind == "magnitude_gap"


def by_pair(candidates):
    return {c.region_ids: c for c in candidates}


def only_candidate(catalog, slopes):
    (candidate,) = find_candidate_discoveries(rated_trends(slopes), catalog)
    return candidate


def test_candidates_rank_opposite_signs_then_multi_variable_then_magnitude_gap(
    catalog,
):
    opposite = only_candidate(
        catalog,
        {("amazon-basin", "temperature"): 0.6, ("sahel", "temperature"): -0.6},
    )
    multi_variable = only_candidate(
        catalog,
        {
            ("amazon-basin", "temperature"): 0.3,
            ("sahel", "temperature"): 0.9,
            ("amazon-basin", "precipitation"): 0.4,
            ("sahel", "precipitation"): 1.2,
        },
    )
    magnitude_gap = only_candidate(
        catalog,
        {("amazon-basin", "temperature"): 0.3, ("sahel", "temperature"): 0.9},
    )

    assert [c.evidence_label for c in (opposite, multi_variable, magnitude_gap)] == [
        "Strong evidence"
    ] * 3
    assert len(multi_variable.contrasts) == 2
    assert opposite.score > multi_variable.score > magnitude_gap.score > 0


def test_candidates_are_listed_from_highest_score_to_lowest(catalog):
    trends = rated_trends(
        {
            ("amazon-basin", "temperature"): 0.3,
            ("sahel", "temperature"): 0.9,
            ("congo-basin", "temperature"): 0.35,
            ("sahara", "temperature"): -0.6,
        }
    )

    candidates = find_candidate_discoveries(trends, catalog)

    assert len(candidates) >= 3
    scores = [c.score for c in candidates]
    assert scores == sorted(scores, reverse=True)
    assert candidates[0].score_components.opposite_sign > 0


def test_a_larger_magnitude_gap_scores_higher(catalog):
    trends = rated_trends(
        {
            ("amazon-basin", "temperature"): 0.4,
            ("sahel", "temperature"): 0.9,
            ("congo-basin", "temperature"): 0.3,
            ("sahara", "temperature"): 1.5,
        }
    )
    pairs = by_pair(find_candidate_discoveries(trends, catalog))

    assert (
        pairs["congo-basin", "sahara"].score > pairs["amazon-basin", "sahel"].score > 0
    )


def test_a_candidate_carries_both_trends_the_period_the_variables_and_a_score(
    catalog,
):
    trends = rated_trends(
        {("sahel", "temperature"): -0.6, ("amazon-basin", "temperature"): 0.6}
    )

    (candidate,) = find_candidate_discoveries(trends, catalog)

    # Trends are ordered to match region_ids whatever order they arrive in.
    (contrast,) = candidate.contrasts
    assert [t.region_id for t in contrast.trends] == list(candidate.region_ids)
    assert set(contrast.trends) == set(trends)
    assert candidate.period == trends[0].period
    assert candidate.score > 0
    assert candidate.evidence_label == "Strong evidence"
    assert candidate.headline_eligible


def test_the_lead_contrast_is_the_one_with_the_highest_score(catalog):
    trends = rated_trends(
        {
            ("amazon-basin", "temperature"): 0.3,
            ("sahel", "temperature"): 0.9,
            ("amazon-basin", "precipitation"): -0.6,
            ("sahel", "precipitation"): 0.6,
        }
    )

    (candidate,) = find_candidate_discoveries(trends, catalog)

    assert [c.variable_id for c in candidate.contrasts] == [
        "precipitation",
        "temperature",
    ]
    # ...and the narrative is built about that lead.
    (predict, *_) = candidate.narrative.investigation.steps
    assert "precipitation" in predict.question


def test_trends_that_are_alike_are_not_a_contrast(catalog):
    trends = rated_trends(
        {("amazon-basin", "temperature"): 0.5, ("sahel", "temperature"): 0.6}
    )

    assert find_candidate_discoveries(trends, catalog) == []


def test_regions_without_a_common_variable_are_not_compared(catalog):
    trends = rated_trends(
        {("amazon-basin", "temperature"): 0.6, ("sahel", "precipitation"): -0.6}
    )

    assert find_candidate_discoveries(trends, catalog) == []


def test_a_contrast_that_lacks_evidence_does_not_weaken_one_that_has_it(catalog):
    trends = rated_trends(
        {
            ("amazon-basin", "temperature"): 0.0,
            ("sahel", "temperature"): 0.0,
            ("amazon-basin", "precipitation"): -0.6,
            ("sahel", "precipitation"): 0.6,
        }
    )
    assert {t.evidence_label for t in trends if t.variable_id == "temperature"} == {
        "Not enough evidence yet"
    }

    (candidate,) = find_candidate_discoveries(trends, catalog)

    assert [c.variable_id for c in candidate.contrasts] == ["precipitation"]
    assert candidate.evidence_label == "Strong evidence"


def test_trends_over_different_periods_are_refused(catalog):
    trends = rated_trends(
        {("amazon-basin", "temperature"): 0.6, ("sahel", "temperature"): -0.6}
    )
    shifted = dataclasses.replace(trends[1], period=Period("2001-01", "2025-12"))

    with pytest.raises(ValueError, match="period"):
        find_candidate_discoveries([trends[0], shifted], catalog)


def test_candidates_follow_the_discovery_schema(catalog, validator_for):
    trends = rated_trends(
        {
            ("amazon-basin", "temperature"): 0.3,
            ("sahel", "temperature"): 0.9,
            ("amazon-basin", "precipitation"): -0.6,
            ("sahel", "precipitation"): 0.6,
            ("congo-basin", "temperature"): 0.0,
            ("sahara", "temperature"): 0.0,
        }
    )

    candidates = find_candidate_discoveries(trends, catalog)

    assert {c.evidence_label for c in candidates} == {
        "Strong evidence",
        "Not enough evidence yet",
    }
    for candidate in candidates:
        payload = json.loads(json.dumps(as_dict(candidate)))
        validator_for("discovery.schema.json").validate(payload)


def test_rates_that_differ_but_whose_intervals_overlap_are_not_a_contrast(catalog):
    trends = rated_trends(
        {("amazon-basin", "temperature"): 0.3, ("sahel", "temperature"): 0.65},
        noise=2.0,
    )
    slow, fast = sorted(trends, key=lambda t: t.rate_per_decade)
    # Given the same direction, the faster rate more than twice the slower, the
    # slower Trend significant, and yet the 95% intervals overlap.
    assert slow.direction == fast.direction == "rising"
    assert fast.rate_per_decade > 2 * slow.rate_per_decade
    assert slow.evidence_label != "Not enough evidence yet"
    assert slow.confidence_interval_95[1] > fast.confidence_interval_95[0]

    assert find_candidate_discoveries(trends, catalog) == []


def test_a_nearby_pair_with_a_contrast_is_a_surprising_pair(catalog):
    slopes = {"temperature": (0.6, -0.6)}

    def candidate(first: str, second: str):
        return only_candidate(
            catalog,
            {
                (first, "temperature"): slopes["temperature"][0],
                (second, "temperature"): slopes["temperature"][1],
            },
        )

    nearby = candidate("sahara", "sahel")  # about 1,200 km apart
    far = candidate("amazon-basin", "sahel")
    just_outside = candidate("congo-basin", "sahara")  # about 3,000 km apart

    assert nearby.score_components.surprising_pair > 0
    assert far.score_components.surprising_pair == 0
    assert just_outside.score_components.surprising_pair == 0
    assert nearby.score > far.score


def test_a_surprising_pair_ranks_with_multi_variable_below_opposite_signs(catalog):
    surprising = only_candidate(
        catalog,
        {("sahara", "temperature"): 0.3, ("sahel", "temperature"): 0.9},
    )
    far_opposite = only_candidate(
        catalog,
        {("amazon-basin", "temperature"): 0.6, ("sahel", "temperature"): -0.6},
    )
    far_gap = only_candidate(
        catalog,
        {("amazon-basin", "temperature"): 0.3, ("sahel", "temperature"): 0.9},
    )

    assert far_opposite.score > surprising.score > far_gap.score
    # ...and it earns the same as a multi-Variable contrast.
    assert (
        surprising.score_components.surprising_pair
        == far_gap_multi(catalog).score_components.multi_variable
    )


def far_gap_multi(catalog):
    return only_candidate(
        catalog,
        {
            ("amazon-basin", "temperature"): 0.3,
            ("sahel", "temperature"): 0.9,
            ("amazon-basin", "precipitation"): 0.4,
            ("sahel", "precipitation"): 1.2,
        },
    )
