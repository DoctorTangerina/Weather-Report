"""Regenerate the committed stub set under `data/stub/`.

    python scripts/generate_stub_data.py

The stub set is synthetic, not NASA data, and exists so the engine, the API and
the frontend can run against the contracts before the real pipeline lands. The
series are generated from an explicit slope, so every Trend here reports the
slope it was built from: no statistics are computed. Ticket #12 replaces this
with the seed set computed from real data.

Because the fixtures are built through `engine.contracts`, the committed JSON
cannot drift from the Python contract objects.
"""

from __future__ import annotations

import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from engine.contracts import (  # noqa: E402
    Autocorrelation,
    Bbox,
    Catalog,
    CheckStep,
    Contrast,
    Discovery,
    EvidenceSource,
    Fit,
    HowDoWeKnow,
    Investigation,
    LeastSquaresFit,
    MannKendallTest,
    Mirror,
    MultipleComparisons,
    Narrative,
    OutlierCheck,
    Period,
    PossibleCause,
    PredictOption,
    PredictStep,
    ReasonStep,
    Region,
    ScoreComponents,
    Series,
    SeriesQuality,
    SeriesRef,
    Source,
    TheilSenFit,
    Trend,
    TrendMethods,
    Variable,
    as_dict,
    direction_of,
)
from engine.version import ENGINE_VERSION  # noqa: E402

PERIOD = Period(start="2000-01", end="2024-12")
MONTHS = 300
FALSE_DISCOVERY_RATE = 0.1
FAMILY_SIZE = 96

METHOD_CITATION = (
    "Time-series analysis of remotely sensed SeaWiFS chlorophyll in "
    "river-influenced coastal regions (see docs/challenge-brief.md)."
)

UNRESOLVED_SOURCE = Source(
    provider="GES DISC",
    dataset="unresolved, see ticket #3",
    variable="unresolved, see ticket #3",
    url=None,
)

STUB_SOURCE = Source(
    provider="Synthetic (stub)",
    dataset="STUB",
    variable="synthetic",
    url=None,
)

REGIONS = (
    Region(
        region_id="amazon-basin",
        name="Amazon Basin",
        description="The rain forest basin of northern South America.",
        bbox=Bbox(west=-70.0, east=-50.0, south=-10.0, north=2.0),
        variable_ids=("temperature", "precipitation"),
    ),
    Region(
        region_id="sahel",
        name="Sahel",
        description="The dry belt between the Sahara and the African savannah.",
        bbox=Bbox(west=-15.0, east=25.0, south=12.0, north=18.0),
        variable_ids=("temperature", "precipitation"),
    ),
    Region(
        region_id="central-india",
        name="Central India",
        description="The monsoon-fed plateau of central India.",
        bbox=Bbox(west=74.0, east=84.0, south=18.0, north=26.0),
        variable_ids=("temperature", "precipitation"),
    ),
    Region(
        region_id="greenland-coast",
        name="Greenland Coast",
        description="The ice-free coastal strip of southwest Greenland.",
        bbox=Bbox(west=-53.0, east=-45.0, south=60.0, north=67.0),
        variable_ids=("temperature", "precipitation"),
    ),
)

VARIABLES = (
    Variable(
        variable_id="temperature",
        name="Air temperature",
        units="K",
        definition="How warm the air near the ground is, averaged over a month.",
        source=UNRESOLVED_SOURCE,
        land_only=False,
        possible_causes=(
            PossibleCause(text="More greenhouse gases in the atmosphere hold in heat."),
            PossibleCause(text="Less vegetation means less cooling from evaporation."),
            PossibleCause(
                text="Changes in cloud cover alter how much sunlight reaches the ground."
            ),
        ),
    ),
    Variable(
        variable_id="precipitation",
        name="Precipitation",
        units="mm/month",
        definition="How much rain and snow falls, added up over a month.",
        source=UNRESOLVED_SOURCE,
        land_only=False,
        possible_causes=(
            PossibleCause(
                text="Shifting wind belts move storm tracks away from a region."
            ),
            PossibleCause(text="A warmer atmosphere can carry more water vapour."),
            PossibleCause(text="Changes in ocean temperature alter where rain forms."),
        ),
    ),
)


@dataclass(frozen=True)
class Profile:
    """How strongly the data support a Trend, as a set of fixture test results."""

    evidence_label: str
    p_value: float
    r_squared: float
    adjusted_p_value: float
    significant: bool
    outlier_survives: bool
    robust_agrees: bool


STRONG = Profile(
    evidence_label="Strong evidence",
    p_value=0.0003,
    r_squared=0.52,
    adjusted_p_value=0.004,
    significant=True,
    outlier_survives=True,
    robust_agrees=True,
)

SOME = Profile(
    evidence_label="Some evidence",
    p_value=0.011,
    r_squared=0.18,
    adjusted_p_value=0.14,
    significant=False,
    outlier_survives=True,
    robust_agrees=True,
)

NONE = Profile(
    evidence_label="Not enough evidence yet",
    p_value=0.41,
    r_squared=0.01,
    adjusted_p_value=0.88,
    significant=False,
    outlier_survives=False,
    robust_agrees=False,
)


@dataclass(frozen=True)
class SeriesSpec:
    region_id: str
    variable_id: str
    units: str
    baseline: float
    seasonal_amplitude: float
    rate_per_decade: float
    noise: float
    seed: int
    profile: Profile
    missing_indices: tuple[int, ...] = ()


SPECS = (
    SeriesSpec("amazon-basin", "temperature", "K", 299.1, 1.4, 0.28, 0.35, 11, STRONG),
    SeriesSpec("sahel", "temperature", "K", 301.4, 5.8, 0.42, 0.52, 12, STRONG),
    SeriesSpec("central-india", "temperature", "K", 298.2, 6.1, 0.19, 0.61, 13, SOME),
    SeriesSpec("greenland-coast", "temperature", "K", 272.6, 9.3, 0.05, 1.21, 14, NONE),
    SeriesSpec(
        "amazon-basin",
        "precipitation",
        "mm/month",
        212.0,
        68.0,
        -2.10,
        21.0,
        21,
        STRONG,
    ),
    SeriesSpec(
        "sahel", "precipitation", "mm/month", 54.0, 49.0, 3.40, 12.0, 22, STRONG
    ),
    SeriesSpec(
        "central-india",
        "precipitation",
        "mm/month",
        96.0,
        88.0,
        0.60,
        18.0,
        23,
        SOME,
        missing_indices=(37, 38, 39, 150, 151, 266),
    ),
    SeriesSpec(
        "greenland-coast", "precipitation", "mm/month", 71.0, 14.0, 0.20, 9.0, 24, NONE
    ),
)


def build_series(spec: SeriesSpec) -> Series:
    rng = random.Random(spec.seed)
    values: list[float | None] = []
    for index in range(MONTHS):
        if index in spec.missing_indices:
            values.append(None)
            continue
        seasonal = spec.seasonal_amplitude * math.sin(2 * math.pi * (index % 12) / 12)
        drift = spec.rate_per_decade * index / 120
        values.append(
            round(spec.baseline + seasonal + drift + rng.gauss(0, spec.noise), 3)
        )

    missing = sum(1 for value in values if value is None)
    return Series(
        region_id=spec.region_id,
        variable_id=spec.variable_id,
        period=PERIOD,
        units=spec.units,
        values=tuple(values),
        quality=SeriesQuality(
            included=True,
            missing_fraction=round(missing / MONTHS, 4),
            valid_land_fraction=None,
            exclusions=(),
        ),
        source=STUB_SOURCE,
        engine_version=ENGINE_VERSION,
    )


def build_trend(spec: SeriesSpec) -> Trend:
    """A Trend reporting the slope its series was generated from."""
    rate = spec.rate_per_decade
    profile = spec.profile
    half_width = abs(rate) * 0.45 + 0.02
    robust_rate = rate * (0.9 if profile.robust_agrees else -0.3)
    return Trend(
        region_id=spec.region_id,
        variable_id=spec.variable_id,
        period=PERIOD,
        rate_per_decade=rate,
        units_per_decade=f"{spec.units} per decade",
        confidence_interval_95=(
            round(rate - half_width, 4),
            round(rate + half_width, 4),
        ),
        direction=direction_of(rate),
        evidence_label=profile.evidence_label,
        methods=TrendMethods(
            least_squares=LeastSquaresFit(
                slope_per_decade=rate,
                p_value=profile.p_value,
                r_squared=profile.r_squared,
            ),
            annual_anomaly=Fit(
                slope_per_decade=round(rate * 1.04, 4),
                p_value=round(profile.p_value * 1.6, 4),
            ),
            robust=Fit(
                slope_per_decade=round(robust_rate, 4),
                p_value=round(profile.p_value * 2.1, 4),
            ),
            theil_sen=TheilSenFit(slope_per_decade=round(rate * 0.96, 4)),
            mann_kendall=MannKendallTest(
                tau=round(0.3 if profile.significant else 0.04, 4),
                p_value=round(profile.p_value * 1.3, 4),
            ),
            outlier_check=OutlierCheck(
                survives=profile.outlier_survives,
                removed_month="2015-08",
                slope_per_decade=round(rate * 0.93, 4),
                p_value=round(profile.p_value * 1.8, 4),
            ),
        ),
        multiple_comparisons=MultipleComparisons(
            q=FALSE_DISCOVERY_RATE,
            family_size=FAMILY_SIZE,
            adjusted_p_value=profile.adjusted_p_value,
            significant=profile.significant,
        ),
        autocorrelation=Autocorrelation(lag1=0.31, effective_sample_size=158.4),
        source=STUB_SOURCE,
        method_citation=METHOD_CITATION,
        engine_version=ENGINE_VERSION,
    )


def rate_text(trend: Trend) -> str:
    low, high = trend.confidence_interval_95
    return f"{trend.rate_per_decade} {trend.units_per_decade} (95% interval {low} to {high})"


def build_narrative(
    question: str,
    headline: Contrast,
    regions: dict[str, Region],
    variables: dict[str, Variable],
) -> Narrative:
    first, second = headline.trends
    variable = variables[headline.variable_id]
    faster = (
        first if abs(first.rate_per_decade) >= abs(second.rate_per_decade) else second
    )
    options = tuple(
        PredictOption(option_id=trend.region_id, label=regions[trend.region_id].name)
        for trend in headline.trends
    )
    comparison = (
        f"{regions[first.region_id].name}: {rate_text(first)}. "
        f"{regions[second.region_id].name}: {rate_text(second)}."
    )
    summary = (
        f"Both series cover {PERIOD.start} to {PERIOD.end}. The seasonal cycle was removed, "
        f"then a least-squares fit gave the rate and its 95% interval. The fit was corrected "
        f"for serial correlation and for testing {FAMILY_SIZE} series at a false-discovery "
        f"rate of {FALSE_DISCOVERY_RATE}."
    )
    return Narrative(
        question=question,
        investigation=Investigation(
            steps=(
                PredictStep(
                    question=(
                        f"Where do you think {variable.name.lower()} is changing faster?"
                    ),
                    options=options,
                    answer_option_id=faster.region_id,
                ),
                CheckStep(
                    series=(
                        SeriesRef(first.region_id, first.variable_id),
                        SeriesRef(second.region_id, second.variable_id),
                    ),
                    comparison=comparison,
                ),
                ReasonStep(
                    prompt=f"What could make {variable.name.lower()} change this way?",
                    possible_causes=variable.possible_causes,
                ),
            )
        ),
        how_do_we_know=HowDoWeKnow(
            period=PERIOD,
            sources=tuple(
                EvidenceSource(
                    region_id=trend.region_id,
                    variable_id=trend.variable_id,
                    source=trend.source,
                )
                for trend in headline.trends
            ),
            statistics_summary=summary,
            method_citation=METHOD_CITATION,
        ),
    )


def build_discoveries(
    trends: dict[tuple[str, str], Trend],
    regions: dict[str, Region],
    variables: dict[str, Variable],
) -> list[Discovery]:
    temperature_gap = Contrast(
        variable_id="temperature",
        kind="magnitude_gap",
        trends=(
            trends[("amazon-basin", "temperature")],
            trends[("sahel", "temperature")],
        ),
    )
    precipitation_flip = Contrast(
        variable_id="precipitation",
        kind="opposite_sign",
        trends=(
            trends[("amazon-basin", "precipitation")],
            trends[("sahel", "precipitation")],
        ),
    )
    rainfall_gap = Contrast(
        variable_id="precipitation",
        kind="magnitude_gap",
        trends=(
            trends[("central-india", "precipitation")],
            trends[("sahel", "precipitation")],
        ),
    )
    weak_gap = Contrast(
        variable_id="temperature",
        kind="magnitude_gap",
        trends=(
            trends[("greenland-coast", "temperature")],
            trends[("amazon-basin", "temperature")],
        ),
    )

    return [
        Discovery(
            discovery_id="amazon-basin--sahel",
            region_ids=("amazon-basin", "sahel"),
            period=PERIOD,
            contrasts=(precipitation_flip, temperature_gap),
            mirrors=(
                Mirror(
                    series=(
                        SeriesRef("amazon-basin", "precipitation"),
                        SeriesRef("sahel", "temperature"),
                    ),
                    correlation=-0.46,
                    p_value=0.0009,
                    adjusted_p_value=0.012,
                    significant_after_correction=True,
                ),
            ),
            score=9.2,
            score_components=ScoreComponents(
                opposite_sign=5.0,
                multi_variable=2.0,
                surprising_pair=1.0,
                magnitude_gap=0.7,
                mirror=0.5,
            ),
            evidence_label="Strong evidence",
            headline_eligible=True,
            narrative=build_narrative(
                "Rainfall is falling in one of these places and rising in the other. Which is which?",
                precipitation_flip,
                regions,
                variables,
            ),
            engine_version=ENGINE_VERSION,
        ),
        Discovery(
            discovery_id="central-india--sahel",
            region_ids=("central-india", "sahel"),
            period=PERIOD,
            contrasts=(rainfall_gap,),
            mirrors=(),
            score=4.6,
            score_components=ScoreComponents(
                opposite_sign=0.0,
                multi_variable=0.0,
                surprising_pair=1.0,
                magnitude_gap=3.6,
                mirror=0.0,
            ),
            evidence_label="Some evidence",
            headline_eligible=True,
            narrative=build_narrative(
                "Both of these places are getting more rain. Why would one gain so much more than the other?",
                rainfall_gap,
                regions,
                variables,
            ),
            engine_version=ENGINE_VERSION,
        ),
        Discovery(
            discovery_id="greenland-coast--amazon-basin",
            region_ids=("greenland-coast", "amazon-basin"),
            period=PERIOD,
            contrasts=(weak_gap,),
            mirrors=(),
            score=1.3,
            score_components=ScoreComponents(
                opposite_sign=0.0,
                multi_variable=0.0,
                surprising_pair=1.0,
                magnitude_gap=0.3,
                mirror=0.0,
            ),
            evidence_label="Not enough evidence yet",
            headline_eligible=False,
            narrative=build_narrative(
                "One of these places is warming and the other barely moves. Is the difference real?",
                weak_gap,
                regions,
                variables,
            ),
            engine_version=ENGINE_VERSION,
        ),
    ]


def write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


def main() -> None:
    out = ROOT / "data" / "stub"
    regions = {region.region_id: region for region in REGIONS}
    variables = {variable.variable_id: variable for variable in VARIABLES}

    catalog = Catalog(
        regions=REGIONS,
        variables=VARIABLES,
        method_citation=METHOD_CITATION,
        engine_version=ENGINE_VERSION,
    )
    write(out / "catalog.json", as_dict(catalog))

    trends: dict[tuple[str, str], Trend] = {}
    for spec in SPECS:
        series = build_series(spec)
        write(
            out / "series" / f"{spec.region_id}__{spec.variable_id}.json",
            as_dict(series),
        )
        trends[(spec.region_id, spec.variable_id)] = build_trend(spec)

    for discovery in build_discoveries(trends, regions, variables):
        write(
            out / "discoveries" / f"{discovery.discovery_id}.json", as_dict(discovery)
        )


if __name__ == "__main__":
    main()
