"""The contract objects the three groups build against.

Every class here mirrors one definition in `schemas/`. `tests/test_contracts.py`
validates the serialized form against those schemas, so the two cannot drift.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Literal

EvidenceLabel = Literal["Strong evidence", "Some evidence", "Not enough evidence yet"]
Direction = Literal["rising", "falling", "flat"]
ExclusionReason = Literal["too_many_missing_months", "insufficient_land_fraction"]
ContrastKind = Literal["opposite_sign", "magnitude_gap"]
NoticeCode = Literal["live_data_unavailable"]

STRONG_EVIDENCE: EvidenceLabel = "Strong evidence"
SOME_EVIDENCE: EvidenceLabel = "Some evidence"
NOT_ENOUGH_EVIDENCE: EvidenceLabel = "Not enough evidence yet"


def as_dict(contract: Any) -> dict[str, Any]:
    """Serialize a contract object to its JSON form."""
    return dataclasses.asdict(contract)


def direction_of(rate: float) -> Direction:
    if rate > 0:
        return "rising"
    if rate < 0:
        return "falling"
    return "flat"


@dataclass(frozen=True)
class Period:
    start: str
    end: str


@dataclass(frozen=True)
class Source:
    provider: str
    dataset: str
    variable: str
    url: str | None = None


@dataclass(frozen=True)
class Notice:
    code: NoticeCode
    message: str


@dataclass(frozen=True)
class SeriesRef:
    region_id: str
    variable_id: str


@dataclass(frozen=True)
class SeriesQuality:
    included: bool
    missing_fraction: float
    valid_land_fraction: float | None
    exclusions: tuple[ExclusionReason, ...] = ()


@dataclass(frozen=True)
class Series:
    region_id: str
    variable_id: str
    period: Period
    units: str
    values: tuple[float | None, ...]
    quality: SeriesQuality
    source: Source
    engine_version: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Series:
        quality = payload["quality"]
        return cls(
            region_id=payload["region_id"],
            variable_id=payload["variable_id"],
            period=Period(**payload["period"]),
            units=payload["units"],
            values=tuple(payload["values"]),
            quality=SeriesQuality(
                included=quality["included"],
                missing_fraction=quality["missing_fraction"],
                valid_land_fraction=quality["valid_land_fraction"],
                exclusions=tuple(quality["exclusions"]),
            ),
            source=Source(**payload["source"]),
            engine_version=payload["engine_version"],
        )


@dataclass(frozen=True)
class Fit:
    slope_per_decade: float
    p_value: float


@dataclass(frozen=True)
class LeastSquaresFit:
    slope_per_decade: float
    p_value: float
    r_squared: float


@dataclass(frozen=True)
class TheilSenFit:
    slope_per_decade: float


@dataclass(frozen=True)
class MannKendallTest:
    tau: float
    p_value: float


@dataclass(frozen=True)
class OutlierCheck:
    survives: bool
    removed_month: str
    slope_per_decade: float
    p_value: float


@dataclass(frozen=True)
class TrendMethods:
    least_squares: LeastSquaresFit
    annual_anomaly: Fit
    robust: Fit
    theil_sen: TheilSenFit
    mann_kendall: MannKendallTest
    outlier_check: OutlierCheck


@dataclass(frozen=True)
class MultipleComparisons:
    q: float
    family_size: int
    adjusted_p_value: float
    significant: bool
    method: str = "benjamini-hochberg"


@dataclass(frozen=True)
class Autocorrelation:
    lag1: float
    effective_sample_size: float


@dataclass(frozen=True)
class Trend:
    region_id: str
    variable_id: str
    period: Period
    rate_per_decade: float
    units_per_decade: str
    confidence_interval_95: tuple[float, float]
    direction: Direction
    evidence_label: EvidenceLabel
    methods: TrendMethods
    multiple_comparisons: MultipleComparisons
    autocorrelation: Autocorrelation
    source: Source
    method_citation: str
    engine_version: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Trend:
        methods = payload["methods"]
        return cls(
            region_id=payload["region_id"],
            variable_id=payload["variable_id"],
            period=Period(**payload["period"]),
            rate_per_decade=payload["rate_per_decade"],
            units_per_decade=payload["units_per_decade"],
            confidence_interval_95=tuple(payload["confidence_interval_95"]),
            direction=payload["direction"],
            evidence_label=payload["evidence_label"],
            methods=TrendMethods(
                least_squares=LeastSquaresFit(**methods["least_squares"]),
                annual_anomaly=Fit(**methods["annual_anomaly"]),
                robust=Fit(**methods["robust"]),
                theil_sen=TheilSenFit(**methods["theil_sen"]),
                mann_kendall=MannKendallTest(**methods["mann_kendall"]),
                outlier_check=OutlierCheck(**methods["outlier_check"]),
            ),
            multiple_comparisons=MultipleComparisons(**payload["multiple_comparisons"]),
            autocorrelation=Autocorrelation(**payload["autocorrelation"]),
            source=Source(**payload["source"]),
            method_citation=payload["method_citation"],
            engine_version=payload["engine_version"],
        )


@dataclass(frozen=True)
class Contrast:
    variable_id: str
    kind: ContrastKind
    trends: tuple[Trend, Trend]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Contrast:
        first, second = payload["trends"]
        return cls(
            variable_id=payload["variable_id"],
            kind=payload["kind"],
            trends=(Trend.from_dict(first), Trend.from_dict(second)),
        )


@dataclass(frozen=True)
class Mirror:
    series: tuple[SeriesRef, SeriesRef]
    correlation: float
    p_value: float
    adjusted_p_value: float
    significant_after_correction: bool

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Mirror:
        first, second = payload["series"]
        return cls(
            series=(SeriesRef(**first), SeriesRef(**second)),
            correlation=payload["correlation"],
            p_value=payload["p_value"],
            adjusted_p_value=payload["adjusted_p_value"],
            significant_after_correction=payload["significant_after_correction"],
        )


@dataclass(frozen=True)
class ScoreComponents:
    opposite_sign: float
    multi_variable: float
    surprising_pair: float
    magnitude_gap: float
    mirror: float


@dataclass(frozen=True)
class PredictOption:
    option_id: str
    label: str


@dataclass(frozen=True)
class PredictStep:
    question: str
    options: tuple[PredictOption, ...]
    answer_option_id: str
    kind: str = "predict"


@dataclass(frozen=True)
class CheckStep:
    series: tuple[SeriesRef, SeriesRef]
    comparison: str
    kind: str = "check"


@dataclass(frozen=True)
class PossibleCause:
    text: str
    kind: str = "context"


@dataclass(frozen=True)
class ReasonStep:
    prompt: str
    possible_causes: tuple[PossibleCause, ...]
    kind: str = "reason"


@dataclass(frozen=True)
class Investigation:
    steps: tuple[PredictStep, CheckStep, ReasonStep]


@dataclass(frozen=True)
class EvidenceSource:
    region_id: str
    variable_id: str
    source: Source


@dataclass(frozen=True)
class HowDoWeKnow:
    period: Period
    sources: tuple[EvidenceSource, ...]
    statistics_summary: str
    method_citation: str


@dataclass(frozen=True)
class Narrative:
    question: str
    investigation: Investigation
    how_do_we_know: HowDoWeKnow

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Narrative:
        predict, check, reason = payload["investigation"]["steps"]
        evidence = payload["how_do_we_know"]
        return cls(
            question=payload["question"],
            investigation=Investigation(
                steps=(
                    PredictStep(
                        question=predict["question"],
                        options=tuple(
                            PredictOption(**option) for option in predict["options"]
                        ),
                        answer_option_id=predict["answer_option_id"],
                    ),
                    CheckStep(
                        series=tuple(SeriesRef(**ref) for ref in check["series"]),
                        comparison=check["comparison"],
                    ),
                    ReasonStep(
                        prompt=reason["prompt"],
                        possible_causes=tuple(
                            PossibleCause(text=cause["text"])
                            for cause in reason["possible_causes"]
                        ),
                    ),
                )
            ),
            how_do_we_know=HowDoWeKnow(
                period=Period(**evidence["period"]),
                sources=tuple(
                    EvidenceSource(
                        region_id=entry["region_id"],
                        variable_id=entry["variable_id"],
                        source=Source(**entry["source"]),
                    )
                    for entry in evidence["sources"]
                ),
                statistics_summary=evidence["statistics_summary"],
                method_citation=evidence["method_citation"],
            ),
        )


@dataclass(frozen=True)
class Discovery:
    discovery_id: str
    region_ids: tuple[str, str]
    period: Period
    contrasts: tuple[Contrast, ...]
    mirrors: tuple[Mirror, ...]
    score: float
    score_components: ScoreComponents
    evidence_label: EvidenceLabel
    headline_eligible: bool
    narrative: Narrative
    engine_version: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Discovery:
        first, second = payload["region_ids"]
        return cls(
            discovery_id=payload["discovery_id"],
            region_ids=(first, second),
            period=Period(**payload["period"]),
            contrasts=tuple(
                Contrast.from_dict(contrast) for contrast in payload["contrasts"]
            ),
            mirrors=tuple(Mirror.from_dict(mirror) for mirror in payload["mirrors"]),
            score=payload["score"],
            score_components=ScoreComponents(**payload["score_components"]),
            evidence_label=payload["evidence_label"],
            headline_eligible=payload["headline_eligible"],
            narrative=Narrative.from_dict(payload["narrative"]),
            engine_version=payload["engine_version"],
        )


@dataclass(frozen=True)
class Bbox:
    west: float
    east: float
    south: float
    north: float


@dataclass(frozen=True)
class Region:
    region_id: str
    name: str
    description: str
    bbox: Bbox
    variable_ids: tuple[str, ...]


@dataclass(frozen=True)
class Variable:
    variable_id: str
    name: str
    units: str
    definition: str
    source: Source
    land_only: bool
    possible_causes: tuple[PossibleCause, ...]


@dataclass(frozen=True)
class Catalog:
    regions: tuple[Region, ...]
    variables: tuple[Variable, ...]
    method_citation: str
    engine_version: str

    def region(self, region_id: str) -> Region | None:
        return next((r for r in self.regions if r.region_id == region_id), None)

    def variable(self, variable_id: str) -> Variable | None:
        return next((v for v in self.variables if v.variable_id == variable_id), None)
