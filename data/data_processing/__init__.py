"""Manual processing of acquired and derived series, independent of the engine."""

from .arithmetic import ProcessingError, preview_expression, process_series

__all__ = ["ProcessingError", "preview_expression", "process_series"]
