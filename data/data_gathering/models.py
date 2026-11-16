"""Plain data records used by the gathering method, with no engine dependency."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Bbox:
    west: float
    east: float
    south: float
    north: float


@dataclass(frozen=True)
class SelectedArea:
    """Rectangles (west, south, east, north) a user drew; never a Region.

    A grid cell belongs to the area when its centre lies in any rectangle, so a
    cell shared by two rectangles counts once. A rectangle whose west edge lies
    east of its east edge crosses the antimeridian.
    """

    rectangles: tuple[tuple[float, float, float, float], ...]


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
