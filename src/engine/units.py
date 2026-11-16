"""Turning NASA's native units into the units students see.

The fetch layer (#6) calls these after reading a product and before building a
Series, so every series already carries the units listed in `data/catalog.json`.
`docs/catalog-sources.md` lists the native units of each product.
"""

from __future__ import annotations

import calendar
import math
import re
from collections.abc import Sequence

SECONDS_PER_DAY = 86_400

# MERRA-2 stores a missing value as this number, held as a 32-bit float. When it
# is read back as a 64-bit float it becomes 999999986991104.0, so it is matched
# with a relative tolerance rather than exactly.
MERRA2_FILL_VALUE = 9.99999987e14

PRECIPITATION_RATE_UNITS = "kg m-2 s-1"
MONTHLY_PRECIPITATION_UNITS = "mm/month"

# The wettest calendar month ever recorded at a single place is about 9,300 mm
# (Cherrapunji, India, July 1861). A Region's average cannot exceed that, so a
# larger total means the input was not a rate in kg m-2 s-1: for example
# millimetres per day labelled as a rate, which would come out about 2.6 million
# times too large.
MONTHLY_PRECIPITATION_CEILING = 10_000.0

_MONTH = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def seconds_in_month(year: int, month: int) -> int:
    """Seconds in one calendar month, counting leap Februaries."""
    return calendar.monthrange(year, month)[1] * SECONDS_PER_DAY


def precipitation_rate_to_monthly_total(
    rates: Sequence[float | None],
    start: str,
    units: str,
    fill_value: float = MERRA2_FILL_VALUE,
) -> list[float | None]:
    """Monthly precipitation totals in mm, from MERRA-2's monthly mean rates.

    `PRECTOTCORR` in a MERRA-2 monthly file is the average precipitation rate
    over that month, in kg m-2 s-1. One kilogram of water spread over a square
    metre is one millimetre deep, so the month's total in millimetres is the rate
    times the seconds in that month.

    `rates[i]` is the month `i` months after `start` ("YYYY-MM"), matching the
    Series contract, so every value is multiplied by its own month's length: 28
    to 31 days, with leap Februaries.

    A missing month stays missing. None, NaN, infinities and the fill value all
    come back as None, never as a converted number. Anything that cannot be a
    precipitation rate raises ValueError instead of being converted:

    - units other than kg m-2 s-1, so a series cannot be converted twice;
    - a negative rate;
    - a total above `MONTHLY_PRECIPITATION_CEILING`.

    Values are not rounded here; rounding is for display only.
    """
    if " ".join(units.split()) != PRECIPITATION_RATE_UNITS:
        raise ValueError(
            f"expected precipitation in {PRECIPITATION_RATE_UNITS!r}, got {units!r}"
        )
    match = _MONTH.match(start)
    if match is None:
        raise ValueError(f"start must be a month as YYYY-MM, got {start!r}")
    year, month = int(match.group(1)), int(match.group(2))

    totals: list[float | None] = []
    for index, rate in enumerate(rates):
        month_index = month - 1 + index
        when_year, when_month = year + month_index // 12, month_index % 12 + 1
        if _is_missing(rate, fill_value):
            totals.append(None)
            continue
        if rate < 0:
            raise ValueError(
                f"negative precipitation rate {rate} in {when_year}-{when_month:02d}"
            )
        total = rate * seconds_in_month(when_year, when_month)
        if total > MONTHLY_PRECIPITATION_CEILING:
            raise ValueError(
                f"{total:.0f} mm in {when_year}-{when_month:02d} is wetter than any "
                f"month ever recorded; the input is probably not in "
                f"{PRECIPITATION_RATE_UNITS}"
            )
        totals.append(total)
    return totals


def _is_missing(value: float | None, fill_value: float) -> bool:
    if value is None or not math.isfinite(value):
        return True
    return math.isclose(value, fill_value, rel_tol=1e-6)
