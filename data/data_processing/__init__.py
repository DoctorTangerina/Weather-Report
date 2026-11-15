"""Manual processing of acquired and derived series, independent of the engine."""

from .arithmetic import preview_expression, process_series
from .correlation_map import build_correlation_map
from .errors import ProcessingError

__all__ = [
    "ProcessingError",
    "build_correlation_map",
    "preview_expression",
    "process_series",
]
