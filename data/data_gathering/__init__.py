"""Access to acquired scientific files; no downloading during API selection."""

from .selection import SeriesSelectionError
from .series import get_time_series, list_available_series

__all__ = ["SeriesSelectionError", "get_time_series", "list_available_series"]
