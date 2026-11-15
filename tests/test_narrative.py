"""Seam 1: explanations and investigation content through the engine's interface.

Covers BS-006 (Become a Detective: Predict, Check, Reason), BS-007 (explain only
what was computed, with no LLM) and BS-008 (the "How do we know?" payload).

Discoveries come from the committed stub set, and from a synthetic Discovery
whose numbers (period, rates, intervals, family size, q) deliberately differ
from the stub's, so a number hard-coded in a template cannot pass by luck.
The last test runs the whole path: Candidate Discoveries from ticket #7 carry
the narrative this module specifies.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest
from synthetic import rated_trends

from engine import build_narrative, find_candidate_discoveries, load_catalog
from engine.contracts import (
    Catalog,
    Contrast,
    Discovery,
    MultipleComparisons,
    Narrative,
    Period,
    Source,
    Trend,
    as_dict,
)


def narrate(discovery: Discovery, catalog: Catalog) -> Narrative:
    """Build the narrative from the parts it reads, as ticket #7 will call it."""
    return build_narrative(
        discovery.contrasts, discovery.period, discovery.evidence_label, catalog
    )


def load_discovery(stub_dir: Path, name: str) -> Discovery:
    payload = json.loads(
        (stub_dir / "discoveries" / f"{name}.json").read_text(encoding="utf-8")
    )
    return Discovery.from_dict(payload)


@pytest.fixture(scope="module")
def catalog(stub_dir: Path) -> Catalog:
    return load_catalog(stub_dir / "catalog.json")


@pytest.fixture(scope="module")
def stub_discoveries(stub_dir: Path) -> list[Discovery]:
    return [
        load_discovery(stub_dir, path.stem)
        for path in sorted((stub_dir / "discoveries").glob("*.json"))
    ]


SYNTHETIC_PERIOD = Period(start="2003-01", end="2021-12")


def synthetic_trend(
    template: Trend,
    region_id: str,
    variable_id: str,
    rate: float,
    interval: tuple[float, float],
) -> Trend:
    return replace(
        template,
        region_id=region_id,
        variable_id=variable_id,
        period=SYNTHETIC_PERIOD,
        rate_per_decade=rate,
        confidence_interval_95=interval,
        direction="rising" if rate > 0 else "falling",
        multiple_comparisons=MultipleComparisons(
            q=0.05,
            family_size=37,
            adjusted_p_value=0.0123,
            significant=True,
        ),
        source=Source(
            provider="NASA GES DISC",
            dataset=f"SYNTH_{variable_id.upper()}",
            variable=f"{variable_id}_var",
            url=f"https://disc.gsfc.nasa.gov/{variable_id}",
        ),
        method_citation="Synthetic method citation for the test.",
    )


@pytest.fixture(scope="module")
def synthetic(stub_discoveries: list[Discovery]) -> Discovery:
    """Sahel falls slowly, Central India rises fast: Central India is faster."""
    template = stub_discoveries[0].contrasts[0].trends[0]
    contrast = Contrast(
        variable_id="precipitation",
        kind="opposite_sign",
        trends=(
            synthetic_trend(
                template, "sahel", "precipitation", -1.234567, (-2.71828, 0.3141)
            ),
            synthetic_trend(
                template, "central-india", "precipitation", 7.0625, (5.5, 8.625)
            ),
        ),
    )
    return replace(
        stub_discoveries[0],
        discovery_id="sahel--central-india",
        region_ids=("sahel", "central-india"),
        period=SYNTHETIC_PERIOD,
        contrasts=(contrast,),
        mirrors=(),
        evidence_label="Some evidence",
    )


# BS-006: Ask for a prediction before showing the charts.
def test_bs006_the_investigation_opens_by_asking_which_region_changes_faster(
    synthetic, catalog
):
    predict = narrate(synthetic, catalog).investigation.steps[0]

    assert predict.kind == "predict"
    assert "changing faster" in predict.question
    assert [(o.option_id, o.label) for o in predict.options] == [
        ("sahel", "Sahel"),
        ("central-india", "Central India"),
    ]
    assert predict.answer_option_id == "central-india"


# BS-006: Ask for a prediction before showing the charts; acceptance criterion:
# steps come in the order Predict, Check, Reason.
def test_bs006_steps_come_in_the_order_predict_check_reason(
    stub_discoveries, synthetic, catalog
):
    for discovery in [*stub_discoveries, synthetic]:
        steps = narrate(discovery, catalog).investigation.steps
        assert [step.kind for step in steps] == ["predict", "check", "reason"]


# BS-006: Compare the guess with the data.
def test_bs006_the_check_charts_both_regions_against_the_computed_trends(
    synthetic, catalog
):
    check = narrate(synthetic, catalog).investigation.steps[1]

    assert check.kind == "check"
    assert [(ref.region_id, ref.variable_id) for ref in check.series] == [
        ("sahel", "precipitation"),
        ("central-india", "precipitation"),
    ]
    assert "Sahel: -1.235 mm/month per decade" in check.comparison
    assert "(95% interval -2.718 to 0.314)" in check.comparison
    assert "Central India: 7.063 mm/month per decade" in check.comparison
    assert "(95% interval 5.5 to 8.625)" in check.comparison
    assert "Central India is changing faster" in check.comparison


# BS-006: Present possible causes as context.
def test_bs006_every_possible_cause_is_labeled_context_from_the_catalog(
    synthetic, catalog
):
    reason = narrate(synthetic, catalog).investigation.steps[2]

    assert reason.kind == "reason"
    assert reason.prompt
    expected = [c.text for c in catalog.variable("precipitation").possible_causes]
    assert [cause.text for cause in reason.possible_causes] == expected
    assert {cause.kind for cause in reason.possible_causes} == {"context"}


# --- BS-007: Explain only what was computed -------------------------------------

DATE = re.compile(r"\b\d{4}-\d{2}\b")
NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def as_written(value: float) -> str:
    """How the engine writes a computed value: rounded half up to at most three
    decimals, with no trailing zeros (the rule in the Discovery schema)."""
    rounded = Decimal(repr(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    text = format(rounded, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def computed_values(discovery: Discovery) -> set[str]:
    """Every number the Discovery's Trends and Mirrors carry, as the engine
    writes it."""
    found: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, bool):
            return
        if isinstance(node, int | float):
            found.add(as_written(node))
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list | tuple):
            for value in node:
                walk(value)

    walk([as_dict(contrast) for contrast in discovery.contrasts])
    walk([as_dict(mirror) for mirror in discovery.mirrors])
    return found


def explanation_texts(narrative: Narrative) -> list[str]:
    """The text the engine writes itself, as opposed to catalog or source text."""
    predict, check, reason = narrative.investigation.steps
    return [
        narrative.question,
        predict.question,
        check.comparison,
        reason.prompt,
        narrative.how_do_we_know.statistics_summary,
    ]


def ungrounded_numbers(text: str, discovery: Discovery) -> list[str]:
    """Numbers in `text` that are not computed values, under the engine's own
    formatting: values rounded by the schema's rule, months as YYYY-MM.

    "95%" names the interval the BS-008 evidence view asks for ("its 95%
    interval"); it is the interval's level, not a computed value.
    """
    periods = {discovery.period.start, discovery.period.end}
    for contrast in discovery.contrasts:
        for trend in contrast.trends:
            periods |= {trend.period.start, trend.period.end}
    stray = [month for month in DATE.findall(text) if month not in periods]
    text = DATE.sub(" ", text).replace("95% interval", " ")
    values = computed_values(discovery)
    return stray + [n for n in NUMBER.findall(text) if n not in values]


# BS-007: Build an explanation from the computed numbers.
def test_bs007_every_number_in_the_explanation_is_a_computed_value(
    stub_discoveries, synthetic, catalog
):
    for discovery in [*stub_discoveries, synthetic]:
        narrative = narrate(discovery, catalog)
        for text in explanation_texts(narrative):
            assert ungrounded_numbers(text, discovery) == [], (
                discovery.discovery_id,
                text,
            )


# BS-007: the synthetic Discovery's own numbers reach the text, so the check
# above cannot pass on an explanation that states no numbers at all.
def test_bs007_the_explanation_states_the_discoverys_own_numbers(synthetic, catalog):
    summary = narrate(synthetic, catalog).how_do_we_know.statistics_summary

    assert "2003-01 to 2021-12" in summary
    assert "37 series" in summary
    assert "rate of 0.05" in summary
    assert "Some evidence" in summary


# BS-007: Build the explanation without an LLM.
def test_bs007_the_explanation_is_complete_with_no_llm_configured(
    monkeypatch, stub_discoveries, synthetic, catalog, validator_for
):
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LLM_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
    validator = validator_for("discovery.schema.json", "#/$defs/narrative")

    for discovery in [*stub_discoveries, synthetic]:
        narrative = narrate(discovery, catalog)
        validator.validate(json.loads(json.dumps(as_dict(narrative))))
        assert all(text.strip() for text in explanation_texts(narrative))


# --- BS-008: Show how we know ---------------------------------------------------


# BS-008: Show the evidence behind a Discovery. The payload is checked whole, as
# the API serves it: the evidence view reads the rate, its 95% interval and the
# Evidence label from contrasts[].trends (schema $defs/howDoWeKnow).
def test_bs008_the_discovery_payload_carries_how_do_we_know(
    synthetic, catalog, validator_for
):
    discovery = replace(synthetic, narrative=narrate(synthetic, catalog))
    payload = json.loads(json.dumps(as_dict(discovery)))
    validator_for("discovery.schema.json").validate(payload)

    evidence = payload["narrative"]["how_do_we_know"]
    assert evidence["period"] == {"start": "2003-01", "end": "2021-12"}
    assert evidence["method_citation"] == "Synthetic method citation for the test."
    trends = {
        (trend["region_id"], trend["variable_id"]): trend
        for contrast in payload["contrasts"]
        for trend in contrast["trends"]
    }
    shown = [(s["region_id"], s["variable_id"]) for s in evidence["sources"]]
    assert shown == [("sahel", "precipitation"), ("central-india", "precipitation")]
    for entry in evidence["sources"]:
        trend = trends[(entry["region_id"], entry["variable_id"])]
        assert entry["source"] == trend["source"]
        assert entry["source"]["provider"] == "NASA GES DISC"
        assert isinstance(trend["rate_per_decade"], float)
        assert len(trend["confidence_interval_95"]) == 2
        assert trend["evidence_label"] == "Strong evidence"


# BS-008: a multi-Variable Discovery shows the source of every Trend it carries.
def test_bs008_how_do_we_know_names_a_source_for_every_trend_shown(
    stub_discoveries, catalog
):
    for discovery in stub_discoveries:
        evidence = narrate(discovery, catalog).how_do_we_know
        shown = {(s.region_id, s.variable_id) for s in evidence.sources}
        carried = {
            (trend.region_id, trend.variable_id)
            for contrast in discovery.contrasts
            for trend in contrast.trends
        }
        assert shown == carried
        assert evidence.period == discovery.period


# --- The thought-provoking question and the summary stay within the evidence ----


def discovery_named(discoveries: list[Discovery], discovery_id: str) -> Discovery:
    return next(d for d in discoveries if d.discovery_id == discovery_id)


# BS-007 (ADR 0001: no claim beyond the computed results). The question may
# state a direction only when the Trends support one.
def test_bs007_the_question_states_directions_the_trends_support(
    stub_discoveries, catalog
):
    opposite = discovery_named(stub_discoveries, "amazon-basin--sahel")

    question = narrate(opposite, catalog).question

    assert question.startswith("Precipitation")
    assert "rising" in question
    assert "falling" in question
    assert question.endswith("?")


# BS-007 (ADR 0001). A Trend labeled "Not enough evidence yet" has no
# established direction, so the question asks whether the difference is real
# instead of stating that the Variable is rising or falling.
def test_bs007_the_question_claims_no_direction_without_enough_evidence(
    stub_discoveries, catalog
):
    weak = discovery_named(stub_discoveries, "greenland-coast--amazon-basin")
    labels = {trend.evidence_label for trend in weak.contrasts[0].trends}
    assert "Not enough evidence yet" in labels

    question = narrate(weak, catalog).question

    assert question.startswith("Air temperature")
    assert "rising" not in question
    assert "falling" not in question
    assert question.endswith("?")


# BS-008. A multi-Variable Discovery carries more than two series, so the
# summary must not describe them as a pair.
def test_bs008_the_summary_does_not_call_many_series_both(stub_discoveries, catalog):
    multi = discovery_named(stub_discoveries, "amazon-basin--sahel")
    evidence = narrate(multi, catalog).how_do_we_know
    assert len(evidence.sources) > 2

    assert "Both series" not in evidence.statistics_summary
    assert "2000-01 to 2024-12" in evidence.statistics_summary


# --- Numbers follow the rounding rule -------------------------------------------


# BS-007 (ticket #10 decision): values are rounded half up to at most three
# decimals, in decimal arithmetic, with no trailing zeros.
def test_bs007_numbers_are_rounded_half_up_to_three_decimals(synthetic, catalog):
    check = narrate(synthetic, catalog).investigation.steps[1].comparison

    # 7.0625 is exact in binary, so half-even rounding would give 7.062.
    assert "7.063" in check
    assert "7.0625" not in check
    # Trailing zeros are dropped: 5.5, not 5.500.
    assert "(95% interval 5.5 to 8.625)" in check
    assert "5.500" not in check


# BS-007: a value that rounds to zero is written as 0, never as -0.
def test_bs007_a_value_that_rounds_to_zero_has_no_sign(synthetic, catalog):
    sahel, india = synthetic.contrasts[0].trends
    tiny = replace(sahel, rate_per_decade=-0.0004, confidence_interval_95=(-0.5, 0.5))
    contrast = replace(synthetic.contrasts[0], trends=(tiny, india))

    check = (
        build_narrative(
            (contrast,), synthetic.period, synthetic.evidence_label, catalog
        )
        .investigation.steps[1]
        .comparison
    )

    assert "Sahel: 0 mm/month per decade" in check
    assert "-0" not in check.replace("-0.5", "")


# --- Evidence labels in the Check step ------------------------------------------


# BS-006: Compare the guess with the data. Ticket #10 decision: the Check
# names each Region's Evidence label and says nothing more about it, so a
# Trend without evidence is never presented as an established difference.
def test_bs006_the_check_names_each_regions_evidence_label(synthetic, catalog):
    sahel, india = synthetic.contrasts[0].trends
    weak = replace(sahel, evidence_label="Not enough evidence yet")
    contrast = replace(synthetic.contrasts[0], trends=(weak, india))

    check = build_narrative(
        (contrast,), synthetic.period, "Some evidence", catalog
    ).investigation.steps[1]

    assert "Evidence label for Sahel: Not enough evidence yet." in check.comparison
    assert "Evidence label for Central India: Strong evidence." in check.comparison


# BS-006: the answer still follows the computed rates (larger absolute rate),
# even when that Region's Trend lacks evidence; only the Check qualifies it.
def test_bs006_the_answer_follows_the_rates_even_without_evidence(synthetic, catalog):
    sahel, india = synthetic.contrasts[0].trends
    weak = replace(india, evidence_label="Not enough evidence yet")
    contrast = replace(synthetic.contrasts[0], trends=(sahel, weak))

    predict = build_narrative(
        (contrast,), synthetic.period, "Some evidence", catalog
    ).investigation.steps[0]

    assert predict.answer_option_id == "central-india"


# Integration of #7 and #10: a Candidate Discovery's narrative is the one this
# module specifies, built from its own Contrasts, period and Evidence label, so
# #7 cannot assemble a Discovery with a different narrative than the one #10 owns.
def test_candidate_discoveries_carry_the_narrative_built_from_their_own_parts(catalog):
    trends = rated_trends(
        {("amazon-basin", "temperature"): 0.6, ("sahel", "temperature"): -0.6}
    )

    (candidate,) = find_candidate_discoveries(trends, catalog)

    assert candidate.narrative == build_narrative(
        candidate.contrasts, candidate.period, candidate.evidence_label, catalog
    )
    check = candidate.narrative.investigation.steps[1]
    assert "Evidence label for Amazon Basin: Strong evidence." in check.comparison
