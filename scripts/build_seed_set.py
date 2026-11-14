"""Regenerate the committed seed set under `data/seed/` from real data.

    python scripts/build_seed_set.py

One command, offline once the NASA files are acquired (see
`data/data_gathering/README.md`): it builds the monthly Series for every catalog
Region and Variable the data can provide, runs the engine over them (Trends,
Mirrors, Candidate Discoveries) and writes the result where the results service
reads it. Commit `data/seed/` afterwards so the demo works with no network.

    --series-dir DIR   reuse Series files already built instead of reading the
                       acquired NASA files
    --output DIR       where to write the seed set (default `data/seed`)

A Series the data cannot provide is reported and skipped. The command refuses to
overwrite the seed set when no Candidate carries one of the three Evidence
labels, so a demo cannot lose its strong or weak case unnoticed; pass
`--allow-missing-labels` to write it anyway.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from engine import (
    Period,
    Series,
    compute_seed_set,
    load_catalog,
    missing_evidence_labels,
    write_seed_set,
)

DEFAULT_CATALOG = ROOT / "data" / "catalog.json"
DEFAULT_OUTPUT = ROOT / "data" / "seed"
DEFAULT_SERIES_DIR = ROOT / "data" / "data_gathering" / "downloads" / "series"


def build_series_from_acquired_data(
    catalog_path: Path, series_dir: Path, period: Period
) -> None:
    """Write one Series file per Region and Variable the acquired data can give."""
    from data.data_gathering.build_series import build_series_files
    from data.data_gathering.models import Period as GatheringPeriod

    catalog = load_catalog(catalog_path)
    variable_ids = [variable.variable_id for variable in catalog.variables]
    report = build_series_files(
        [region.region_id for region in catalog.regions],
        variable_ids,
        GatheringPeriod(period.start, period.end),
        series_dir,
        catalog_path=catalog_path,
    )
    for row in report:
        if row["status"] != "included":
            print(f"  {row['region_id']} {row['variable_id']}: {row['status']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--series-dir", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--start", default="2000-01", help="YYYY-MM")
    parser.add_argument("--end", default="2024-12", help="YYYY-MM")
    parser.add_argument("--allow-missing-labels", action="store_true")
    args = parser.parse_args(argv)

    series_dir = args.series_dir
    if series_dir is None:
        series_dir = DEFAULT_SERIES_DIR
        print("Building Series from the acquired NASA files...")
        build_series_from_acquired_data(
            args.catalog, series_dir, Period(args.start, args.end)
        )
    paths = sorted(series_dir.glob("*.json"))
    if not paths:
        print(f"No Series files in {series_dir}: nothing to compute.", file=sys.stderr)
        return 1
    series = [Series.from_dict(json.loads(p.read_text("utf-8"))) for p in paths]

    seed = compute_seed_set(series, load_catalog(args.catalog))
    missing = missing_evidence_labels(seed.discoveries)
    excluded = sum(1 for one in seed.series if not one.quality.included)
    print(
        f"{len(seed.series)} Series ({excluded} excluded by the Quality gate), "
        f"{len(seed.discoveries)} Candidate Discoveries."
    )
    if missing and not args.allow_missing_labels:
        print(
            "Not written: no Candidate carries " + ", ".join(missing) + ". "
            "Pass --allow-missing-labels to write it anyway.",
            file=sys.stderr,
        )
        return 1
    write_seed_set(seed, args.output)
    print(f"Wrote the seed set to {args.output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
