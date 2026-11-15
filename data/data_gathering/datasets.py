"""Public NASA CMR discovery for the app's themes and selected bounding boxes.

Search returns candidate collections, not a claim that every observation or grid cell
passes the app's quality gate. Acquisition must inspect the selected granules.
"""

from __future__ import annotations

import argparse
import calendar
import json
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from itertools import islice
from pathlib import Path
from urllib.parse import unquote, urlencode, urlsplit
from urllib.request import Request, urlopen

if __package__:
    from .config import ROOT, configured_bbox, configured_path, load_config
else:
    from config import ROOT, configured_bbox, configured_path, load_config

CMR_URL = "https://cmr.earthdata.nasa.gov/search"


def load_themes(path: Path | None = None) -> dict:
    path = path or configured_path("THEMES_FILE", Path(__file__).parent / "themes.json")
    themes = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(themes, dict) or any(
        not isinstance(value, dict) for value in themes.values()
    ):
        raise ValueError("Themes file must map names to NASA search-parameter objects.")
    return themes


def default_area() -> SearchArea:
    return SearchArea("box", configured_bbox())


@dataclass(frozen=True)
class SearchArea:
    name: str
    bbox: tuple[float, float, float, float]

    def __post_init__(self):
        west, south, east, north = self.bbox
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError(
                "Bounding box must be west,south,east,north within Earth coordinates."
            )


def region_area(name: str, catalog_path: Path) -> SearchArea:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    for region in catalog["regions"]:
        if region["region_id"] == name:
            bbox = region["bbox"]
            return SearchArea(
                name, tuple(bbox[key] for key in ("west", "south", "east", "north"))
            )
    raise ValueError(
        f"Unknown Region: {name}; use a catalog Region id, BBOX in config.json, or --bbox."
    )


def temporal_range(start: str, end: str) -> str:
    first = datetime.strptime(start, "%Y-%m-%d" if len(start) == 10 else "%Y-%m")
    last = datetime.strptime(end, "%Y-%m-%d" if len(end) == 10 else "%Y-%m")
    if first > last:
        raise ValueError("Start month must not be later than end month.")
    day = last.day if len(end) == 10 else calendar.monthrange(last.year, last.month)[1]
    return f"{first:%Y-%m-%d}T00:00:00Z,{last:%Y-%m}-{day:02d}T23:59:59Z"


def cmr_page(resource: str, parameters: dict) -> tuple[list[dict], int]:
    query = urlencode(parameters, doseq=True)
    request = Request(
        f"{CMR_URL}/{resource}.json?{query}", headers={"Accept": "application/json"}
    )
    with urlopen(request, timeout=60) as response:
        entries = json.load(response)["feed"].get("entry", [])
        hits = int(response.headers.get("CMR-Hits", len(entries)))
    return entries, hits


def cmr_entries(resource: str, parameters: dict):
    """Page through CMR results without sending the user's Earthdata token."""
    page = 1
    while True:
        entries, _ = cmr_page(
            resource, {**parameters, "page_size": 100, "page_num": page}
        )
        yield from entries
        if len(entries) < 100:
            return
        page += 1


def cadence(title: str) -> str:
    """Report native frequency when explicitly present in the collection title."""
    match = re.search(
        r"\b(?:\d+[- ]?(?:minute|hour|day|month|year)(?:ly)?|hourly|daily|monthly|annual|yearly|16-day|8-day)\b",
        title,
        flags=re.IGNORECASE,
    )
    return match.group(0) if match else "not specified in title"


def search(
    theme: str,
    areas: list[SearchArea],
    start: str,
    end: str,
    limit: int = 20,
    *,
    keyword: str | None = None,
    selected: list[str] | None = None,
    themes: dict | None = None,
) -> list[dict]:
    """Find candidate collections at any frequency overlapping every selected Region."""
    if not areas or limit < 1:
        raise ValueError("Select at least one Region and a positive result limit.")
    temporal = temporal_range(start, end)
    themes = load_themes() if themes is None and keyword is None else (themes or {})
    if keyword is None and theme not in themes:
        raise ValueError(f"Unknown theme {theme!r}. Edit themes.json or use --keyword.")
    parameters = {"keyword": keyword} if keyword is not None else themes[theme]
    providers = load_config().get("CMR_PROVIDERS", [])
    if not isinstance(providers, list) or any(
        not isinstance(provider, str) for provider in providers
    ):
        raise ValueError(
            "CMR_PROVIDERS in config.json must be a list of provider names."
        )
    matches: dict[str, dict] | None = None
    for area in areas:
        if matches == {}:
            break
        entries = {
            entry["id"]: entry
            for entry in islice(
                cmr_entries(
                    "collections",
                    {
                        **parameters,
                        **(
                            {"concept_id[]": list(matches)}
                            if matches is not None
                            else ({"concept_id[]": selected} if selected else {})
                        ),
                        **({"provider[]": providers} if providers else {}),
                        "bounding_box": ",".join(map(str, area.bbox)),
                        "temporal": temporal,
                        "has_granules": "true",
                    },
                ),
                limit,
            )
            if matches is None or entry["id"] in matches
        }
        matches = (
            entries
            if matches is None
            else {key: entry for key, entry in matches.items() if key in entries}
        )
    return sorted(
        (
            {
                "collection_id": entry["id"],
                "short_name": entry["short_name"],
                "version": entry.get("version_id"),
                "title": entry["title"],
                "cadence": cadence(entry["title"]),
                "start": entry.get("time_start"),
                "end": entry.get("time_end"),
                "metadata_url": f"{CMR_URL}/concepts/{entry['id']}.html",
            }
            for entry in (matches or {}).values()
        ),
        key=lambda entry: (entry["short_name"], entry["version"] or ""),
    )


def granule_query(
    collection_id: str, areas: list[SearchArea], start: str, end: str
) -> dict:
    return {
        "collection_concept_id": collection_id,
        "bounding_box[]": [",".join(map(str, area.bbox)) for area in areas],
        "options[bounding_box][or]": "true",
        "temporal": temporal_range(start, end),
        "sort_key[]": "start_date",
    }


def file_url(granule: dict) -> str:
    """Select a direct science-data link, excluding inherited collection links."""
    urls = []
    for link in granule.get("links", []):
        url = link.get("href", "")
        parsed = urlsplit(url)
        if (
            not link.get("inherited")
            and link.get("rel", "").endswith("/data#")
            and parsed.scheme == "https"
            and (parsed.hostname or "").endswith(".nasa.gov")
            and Path(parsed.path).name not in {"s3credentials", "s3-credentials"}
            and not parsed.path.endswith("/")
            and link.get("type") != "text/html"
        ):
            urls.append(url)
    if not urls:
        raise ValueError(
            f"No supported direct file URL for {granule.get('title', granule.get('id'))}"
        )
    return min(urls, key=lambda url: ("earthdata.nasa.gov" not in url, url))


def acquire(
    results: list[dict],
    areas: list[SearchArea],
    start: str,
    end: str,
    destination: Path,
) -> Path:
    """Download explicitly selected collections, reusing complete existing files."""
    if __package__:
        from .download import download, load_token
    else:
        from download import download, load_token

    token = load_token()
    records = []
    for dataset in results:
        granules = cmr_entries(
            "granules", granule_query(dataset["collection_id"], areas, start, end)
        )
        count = 0
        for granule in granules:
            count += 1
            url = file_url(granule)
            filename = Path(unquote(urlsplit(url).path)).name
            path = destination / filename
            try:
                expected = round(float(granule["granule_size"]) * 1024**2)
            except (KeyError, TypeError, ValueError, OverflowError):
                expected = None
            if path.exists():
                if expected is None or path.stat().st_size != expected:
                    raise ValueError(
                        f"Cannot verify existing file: {path}; choose another output directory."
                    )
                print(f"Reusing {path}", flush=True)
            else:
                print(f"Downloading {filename}", flush=True)
                download(url, path, token)
                if expected is not None and path.stat().st_size != expected:
                    raise ValueError(
                        f"Downloaded size differs from NASA metadata: {path}"
                    )
            records.append(
                {
                    "collection_id": dataset["collection_id"],
                    "dataset": dataset["short_name"],
                    "granule_id": granule["id"],
                    "url": url,
                    "file": Path(
                        os.path.relpath(path.resolve(), destination.resolve())
                    ).as_posix(),
                    "bytes": path.stat().st_size,
                    "start": granule.get("time_start"),
                    "end": granule.get("time_end"),
                }
            )
        if count == 0:
            raise ValueError(
                f"No source files match the selected dates/box for {dataset['short_name']}."
            )
    return write_manifest(destination, start, end, areas, records)


def write_manifest(
    destination: Path,
    start: str,
    end: str,
    areas: list[SearchArea],
    records: list[dict],
) -> Path:
    """Record acquired files, keeping those of products acquired earlier.

    A file is identified by its collection and path, so repeating an acquisition
    refreshes its records instead of duplicating them.
    """
    destination.mkdir(parents=True, exist_ok=True)
    manifest = destination / "acquisition-manifest.json"
    earlier = []
    if manifest.exists():
        earlier = json.loads(manifest.read_text(encoding="utf-8")).get("files", [])
    identity = lambda item: (item.get("collection_id"), item["file"])
    replaced = {identity(item) for item in records}
    manifest.write_text(
        json.dumps(
            {
                "search_period": {"start": start, "end": end},
                "regions": [{"name": area.name, "bbox": area.bbox} for area in areas],
                "files": [item for item in earlier if identity(item) not in replaced]
                + records,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def estimate_size(
    collection_id: str,
    areas: list[SearchArea],
    start: str,
    end: str,
    sample_size: int = 20,
) -> dict:
    """Estimate full-file transfer size, using a small sample of granule metadata.

    OR-ing boxes lets CMR count each granule once even when Regions overlap.
    A sample avoids enumerating millions of high-frequency files just to browse.
    """
    entries, count = cmr_page(
        "granules",
        {
            **granule_query(collection_id, areas, start, end),
            "page_size": sample_size,
            "page_num": 1,
        },
    )
    sizes = []
    for entry in entries:
        try:
            size = float(entry["granule_size"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(size) and size >= 0:
            sizes.append(size * 1024**2)
    exact = count == len(entries) == len(sizes)
    estimated_bytes = (
        0 if count == 0 else (sum(sizes) / len(sizes) * count if sizes else None)
    )
    return {
        "files": count,
        "bytes": estimated_bytes,
        "exact": exact,
        "sampled_files": len(entries),
        "known_sizes": len(sizes),
    }


def size_label(size: dict) -> str:
    value = size["bytes"]
    if value is None:
        return f"unknown ({size['files']:,} files; NASA did not supply file sizes)"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if value < 1024 or unit == "PiB":
            break
        value /= 1024
    suffix = (
        "metadata total"
        if size["exact"]
        else f"estimate from {size['known_sizes']} file sizes"
    )
    return f"{value:,.2f} {unit} ({size['files']:,} files; {suffix})"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    query = parser.add_mutually_exclusive_group()
    query.add_argument(
        "--keyword",
        help="Any NASA catalog search text, e.g. 'air temperature' or 'drought'",
    )
    query.add_argument(
        "--theme",
        help="Convenience science-keyword theme; use --keyword for unrestricted search text",
    )
    parser.add_argument(
        "--themes-file", type=Path, help="JSON file containing editable named searches"
    )
    parser.add_argument("--list-themes", action="store_true")
    location = parser.add_mutually_exclusive_group()
    location.add_argument(
        "--region",
        nargs="+",
        help="Region ids from the catalog; otherwise use BBOX from config.json",
    )
    location.add_argument(
        "--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH")
    )
    parser.add_argument("--catalog", type=Path, default=ROOT / "data/catalog.json")
    parser.add_argument(
        "--start",
        default=load_config().get("DATA_START"),
        help="YYYY-MM or YYYY-MM-DD; defaults to DATA_START in config.json",
    )
    parser.add_argument(
        "--end",
        default=load_config().get("DATA_END"),
        help="YYYY-MM or YYYY-MM-DD; defaults to DATA_END in config.json",
    )
    parser.add_argument(
        "--limit", type=int, default=20, help="Maximum candidate results (default: 20)"
    )
    parser.add_argument(
        "--select",
        nargs="+",
        metavar="COLLECTION_ID",
        help="Only these NASA collection IDs",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download files for explicitly selected collections",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path(__file__).parent / "downloads"
    )
    args = parser.parse_args()
    try:
        themes = load_themes(args.themes_file) if args.theme or args.list_themes else {}
    except (OSError, ValueError) as error:
        parser.exit(1, f"Theme configuration failed: {error}\n")
    if args.list_themes:
        print(json.dumps(themes, indent=2))
        return
    if not (args.keyword or args.theme) or not (args.start and args.end):
        parser.error(
            "Supply --keyword or --theme, plus --start/--end or DATA_START/DATA_END in config.json."
        )
    if args.download and not args.select:
        parser.error(
            "--download requires --select so search results are not downloaded automatically."
        )
    try:
        areas = (
            [SearchArea("custom", tuple(args.bbox))]
            if args.bbox
            else (
                [region_area(name, args.catalog) for name in args.region]
                if args.region
                else [default_area()]
            )
        )
        results = search(
            args.theme or "",
            areas,
            args.start,
            args.end,
            max(args.limit, len(args.select or [])),
            keyword=args.keyword,
            selected=args.select,
            themes=themes,
        )
        if args.select:
            missing = set(args.select) - {item["collection_id"] for item in results}
            if missing:
                raise ValueError(
                    f"Selected collections do not match the search: {', '.join(sorted(missing))}"
                )
    except (ValueError, OSError) as error:
        parser.exit(1, f"Search failed: {error}\n")

    def with_size(dataset):
        try:
            return size_label(
                estimate_size(dataset["collection_id"], areas, args.start, args.end)
            )
        except (OSError, ValueError, KeyError):
            return "unknown (NASA size lookup failed)"

    with ThreadPoolExecutor(max_workers=4) as pool:
        sizes = list(pool.map(with_size, results))
    for index, (dataset, size) in enumerate(zip(results, sizes), start=1):
        print(
            f"{index}. {dataset['short_name']} v{dataset['version']} [{dataset['collection_id']}]"
        )
        print(f"   {dataset['title']}")
        print(f"   Coverage: {dataset['start']} — {dataset['end'] or 'ongoing'}")
        print(f"   Native interval: {dataset['cadence']}")
        print(f"   Full-file download size for selected dates/Regions: {size}")
    if not results:
        print("No matching candidate datasets.")
    else:
        print(
            "Candidates overlap the requested area and dates; granule coverage and data quality still need checking."
        )
        print(
            f"Showing up to {args.limit} candidates. Size estimates concern source files, before regional/variable subsetting."
        )
    if args.download:
        try:
            manifest = acquire(results, areas, args.start, args.end, args.output_dir)
        except (OSError, ValueError) as error:
            parser.exit(1, f"Acquisition failed: {error}\n")
        print(f"Acquisition complete. Manifest: {manifest}")


if __name__ == "__main__":
    main()
