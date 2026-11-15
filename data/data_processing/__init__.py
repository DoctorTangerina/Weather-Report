"""Manual processing of acquired and derived series, independent of the engine."""

from .arithmetic import preview_expression, process_series
from .errors import ProcessingError

__all__ = ["ProcessingError", "preview_expression", "process_series"]
