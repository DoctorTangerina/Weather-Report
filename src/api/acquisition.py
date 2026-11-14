"""Integration boundary for #6; no client-provided credentials or file paths.

The preserved #6 branch only selects previously downloaded files. Until a real
live provider is re-landed and adapted to the monthly Series contract, the
default reports unavailability so the API can serve the shipped examples.
"""

from typing import Any

from engine.contracts import Period, Region, Variable


class AcquisitionUnavailable(Exception):
    """Expected upstream/authentication/quality failure, not a programming error."""


async def acquire_series(
    region: Region, variable: Variable, period: Period, *, token: str
) -> dict[str, Any]:
    """Return a computed monthly Series payload, or raise AcquisitionUnavailable.

    Implementations must be asynchronous, release resources on cancellation and
    enforce transport timeouts. The API enforces an overall request time limit.
    They receive the Earthdata token only from the server environment and must
    translate expected upstream and quality-gate failures to the typed exception.
    """
    raise AcquisitionUnavailable("Live acquisition from #6 is not integrated")
