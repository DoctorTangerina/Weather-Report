"""Autonomous Discovery Engine.

This module is seam 1 of the testing plan: the public interface the API, the
seed-set script and the tests build against. The package has no web
dependency, so the statistics can be run and tested without the API.

Contract objects live in `engine.contracts`.
"""

from .catalog import applies_to, catalog_from_dict, load_catalog
from .contracts import Catalog, Discovery, Period, Series, Trend
from .discovery import (
    SessionHistory,
    build_narrative,
    find_candidate_discoveries,
    select_surprise,
)
from .mirror import find_mirrors
from .quality import usable_series
from .seed import SeedSet, compute_seed_set, missing_evidence_labels, write_seed_set
from .store import JsonResultStore, ResultStore
from .trend import FALSE_DISCOVERY_RATE, estimate_trend, rate_evidence
from .units import precipitation_rate_to_monthly_total
from .version import ENGINE_VERSION

__all__ = [
    "ENGINE_VERSION",
    "FALSE_DISCOVERY_RATE",
    "Catalog",
    "Discovery",
    "JsonResultStore",
    "Period",
    "ResultStore",
    "SeedSet",
    "Series",
    "SessionHistory",
    "Trend",
    "applies_to",
    "build_narrative",
    "catalog_from_dict",
    "compute_seed_set",
    "estimate_trend",
    "find_candidate_discoveries",
    "find_mirrors",
    "load_catalog",
    "missing_evidence_labels",
    "precipitation_rate_to_monthly_total",
    "rate_evidence",
    "select_surprise",
    "usable_series",
    "write_seed_set",
]
