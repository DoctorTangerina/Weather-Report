#!/usr/bin/env python3
"""Extract numeric native-frequency series from acquired NetCDF/CF files."""

import argparse
import json
from pathlib import Path

if __package__:
    from .config import configured_bbox
    from .datasets import SearchArea
    from .netcdf import extract, load_manifest
else:
    from config import configured_bbox
    from datasets import SearchArea
    from netcdf import extract, load_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", type=Path)
    source.add_argument("--files", nargs="+", type=Path)
    parser.add_argument("--dataset-name", default="data", help="Grouping label when --files is used")
    parser.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    parser.add_argument("--variables", nargs="+", help="Omit to discover all numeric time-varying fields")
    parser.add_argument("--aggregation", choices=("area-mean", "mean", "none"), default="area-mean")
    parser.add_argument("--time-coordinate")
    parser.add_argument("--latitude-coordinate")
    parser.add_argument("--longitude-coordinate")
    parser.add_argument("--area-variable")
    parser.add_argument("--max-series", type=int, default=10000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        records = (load_manifest(args.manifest)["files"] if args.manifest else
                   [{"file": str(path), "dataset": args.dataset_name} for path in args.files])
        area = SearchArea("box", tuple(args.bbox) if args.bbox else configured_bbox())
        result = extract(records, area, aggregation=args.aggregation, variables=args.variables,
                         time_coordinate=args.time_coordinate, latitude=args.latitude_coordinate,
                         longitude=args.longitude_coordinate, area_variable=args.area_variable,
                         max_series=args.max_series)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError) as error:
        parser.exit(1, f"Extraction failed: {error}\n")
    count = sum(len(fields) for fields in result["datasets"].values())
    print(f"Saved {count} native-frequency time series to {args.output}; {len(result['skipped'])} unsupported fields/groups reported.")


if __name__ == "__main__":
    main()
