"""Command line: build monthly series files for catalog Regions and Variables.

    python -m data.data_gathering.build_series --regions sahel --variables temperature
"""

import argparse
from pathlib import Path

from .catalog_series import DEFAULT_CATALOG, DEFAULT_PERIOD, ROOT, build_series_files
from .models import Period
from .series import DEFAULT_CONFIG


def main() -> int:
    parser = argparse.ArgumentParser(description="Build monthly series files for catalog Regions and Variables from acquired data.")
    parser.add_argument("--regions", nargs="+", required=True, help="Region ids from the catalog")
    parser.add_argument("--variables", nargs="+", required=True, help="Variable ids from the catalog")
    parser.add_argument("--start", default=DEFAULT_PERIOD.start, help="YYYY-MM")
    parser.add_argument("--end", default=DEFAULT_PERIOD.end, help="YYYY-MM")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/data_gathering/downloads/series")
    args = parser.parse_args()
    report = build_series_files(args.regions, args.variables, Period(args.start, args.end),
                                args.output_dir, catalog_path=args.catalog, config_path=args.config)
    for row in report:
        print(f"{row['region_id']:<16} {row['variable_id']:<18} {row['status']}")
    return 0 if all(row["status"] == "included" for row in report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
