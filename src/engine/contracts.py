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


@dataclass(frozen=True)
class Contrast:
    variable_id: str
    kind: ContrastKind
    trends: tuple[Trend, Trend]


@dataclass(frozen=True)
class Mirror:
    series: tuple[SeriesRef, SeriesRef]
    correlation: float
    p_value: float
    adjusted_p_value: float
    significant_after_correction: bool


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
