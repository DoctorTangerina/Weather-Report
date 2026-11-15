"""Small explicit conversion registry; unknown units remain opaque labels."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Unit:
    dimension: str
    scale: float = 1.0
    offset: float = 0.0


_GROUPS = [
    (Unit("dimensionless"), ("1", "dimensionless", "unitless")),
    (Unit("length"), ("m", "metre", "metres", "meter", "meters")),
    (Unit("length", 0.01), ("cm", "centimetre", "centimetres")),
    (Unit("length", 0.001), ("mm", "millimetre", "millimetres")),
    (Unit("length", 1000), ("km", "kilometre", "kilometres")),
    (Unit("time"), ("s", "second", "seconds")),
    (Unit("time", 60), ("min", "minute", "minutes")),
    (Unit("time", 3600), ("h", "hour", "hours")),
    (Unit("time", 86400), ("d", "day", "days")),
    (Unit("temperature"), ("K", "kelvin")),
    (Unit("temperature", 1, 273.15), ("°C", "degC", "degrees Celsius", "Celsius")),
    (Unit("temperature", 5 / 9, 255.3722222222222), ("°F", "degF", "Fahrenheit")),
    (Unit("pressure"), ("Pa", "pascal", "pascals")),
    (Unit("pressure", 100), ("hPa", "mbar")),
    (Unit("pressure", 1000), ("kPa",)),
    (Unit("dimensionless"), ("fraction",)),
    (Unit("dimensionless", 0.01), ("%", "percent")),
]
UNITS = {name: definition for definition, names in _GROUPS for name in names}


def conversion(source: str, target: str) -> tuple[float, float] | None:
    """Return factor/offset for source → target, or None if unsupported."""
    if source == target:
        return 1.0, 0.0
    first, second = UNITS.get(source), UNITS.get(target)
    if first is None or second is None or first.dimension != second.dimension:
        return None
    return first.scale / second.scale, (first.offset - second.offset) / second.scale


def compound(left: str, right: str, *, divide: bool) -> str:
    """Preserve opaque units without pretending to simplify unknown dimensions."""
    if right == "1":
        return left
    if left == "1" and not divide:
        return right
    if divide and left == right:
        return "1"
    return f"({left}) {'/' if divide else '*'} ({right})"


_TIME_UNITS = {
    "s",
    "sec",
    "second",
    "seconds",
    "min",
    "minute",
    "minutes",
    "h",
    "hr",
    "hour",
    "hours",
    "d",
    "day",
    "days",
    "month",
    "months",
    "yr",
    "year",
    "years",
}


def is_rate(units: str) -> bool:
    """Whether units are per unit of time: "mm/day", "kg m-2 s-1", "mm per hour"."""
    text = units.strip()
    if "/" in text and text.rsplit("/", 1)[1].strip(" ()") in _TIME_UNITS:
        return True
    tokens = text.replace("^", "").split()
    return any(
        (token.endswith("-1") and token[:-2] in _TIME_UNITS)
        or (
            token == "per"
            and index + 1 < len(tokens)
            and tokens[index + 1] in _TIME_UNITS
        )
        for index, token in enumerate(tokens)
    )
