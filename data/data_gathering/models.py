"""Plain data records used by the gathering method, with no engine dependency."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Bbox:
    west: float
    east: float
    south: float
    north: float


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
class SeriesQuality:
    included: bool
    missing_fraction: float
    valid_land_fraction: float | None
    exclusions: tuple[str, ...] = ()
