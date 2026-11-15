"""Ticket #12: the seed set is computed offline from Series and written to disk.

Driven through `engine.compute_seed_set` and `engine.write_seed_set` over
synthetic series, with no network: the real acquisition is the data layer's job
and `scripts/build_seed_set.py` only wires the two together.
"""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from synthetic import driven_series, driver_signal, series_for

from engine import (
    JsonResultStore,
    Period,
    compute_seed_set,
    load_catalog,
    missing_evidence_labels,
    write_seed_set,
)
from engine.contracts import NOT_ENOUGH_EVIDENCE, STRONG_EVIDENCE


@pytest.fixture(scope="module")
def catalog(catalog_path):
    return load_catalog(catalog_path)


def excluded(series):
    return dataclasses.replace(
        series,
        values=tuple(None for _ in series.values),
        quality=dataclasses.replace(
            series.quality,
            included=False,
            missing_fraction=0.4,
            exclusions=("too_many_missing_months",),
        ),
    )


def opposite_pair():
    return [
        series_for("amazon-basin", "temperature", 2.0, seed=1),
        series_for("sahel", "temperature", -2.0, seed=2),
    ]


def test_opposite_trends_become_a_candidate_with_strong_evidence(catalog):
    seed = compute_seed_set(opposite_pair(), catalog)

    (discovery,) = seed.discoveries
    assert discovery.discovery_id == "amazon-basin--sahel"
    assert discovery.contrasts[0].kind == "opposite_sign"
    assert discovery.evidence_label == STRONG_EVIDENCE


def test_every_series_is_kept_for_the_results_service(catalog):
    series = opposite_pair()

    seed = compute_seed_set(series, catalog)

    assert list(seed.series) == series


def test_an_excluded_series_is_kept_but_takes_no_part_in_any_discovery(catalog):
    series = [
        *opposite_pair(),
        excluded(series_for("sahel", "precipitation", 3, seed=3)),
    ]

    seed = compute_seed_set(series, catalog)

    assert len(seed.series) == 3
    assert {
        ref
        for d in seed.discoveries
        for c in d.contrasts
        for t in c.trends
        for ref in [t.variable_id]
    } == {"temperature"}


def test_trends_are_rated_as_one_family_of_the_usable_series(catalog):
    series = [
        *opposite_pair(),
        series_for("central-india", "temperature", 0.1, seed=4),
        excluded(series_for("sahel", "precipitation", 3, seed=3)),
    ]

    seed = compute_seed_set(series, catalog)

    trends = [t for d in seed.discoveries for c in d.contrasts for t in c.trends]
    assert {t.multiple_comparisons.family_size for t in trends} == {3}


def test_a_mirror_between_the_pair_joins_its_candidate(catalog):
    driver = driver_signal(seed=7)
    series = [
        driven_series(
            "amazon-basin",
            "temperature",
            driver,
            weight=1.0,
            seed=1,
            slope_per_decade=2.0,
        ),
        driven_series(
            "sahel", "temperature", driver, weight=1.0, seed=2, slope_per_decade=-2.0
        ),
    ]

    (discovery,) = compute_seed_set(series, catalog).discoveries

    assert len(discovery.mirrors) == 1
    assert discovery.score_components.mirror > 0


def test_the_same_series_give_the_same_seed_set(catalog):
    first = compute_seed_set(opposite_pair(), catalog)
    second = compute_seed_set(opposite_pair(), catalog)

    assert first == second


def test_missing_evidence_labels_names_each_label_no_candidate_has(catalog):
    (discovery,) = compute_seed_set(opposite_pair(), catalog).discoveries
    weak = dataclasses.replace(discovery, evidence_label=NOT_ENOUGH_EVIDENCE)

    assert missing_evidence_labels([discovery, weak]) == ["Some evidence"]
    assert missing_evidence_labels([]) == [
        "Strong evidence",
        "Some evidence",
        "Not enough evidence yet",
    ]


def test_a_written_seed_set_is_served_by_the_result_store(catalog, tmp_path):
    seed = compute_seed_set(opposite_pair(), catalog)

    write_seed_set(seed, tmp_path)

    store = JsonResultStore(tmp_path, catalog.engine_version)
    stored = store.series("amazon-basin", "temperature", Period("2000-01", "2024-12"))
    assert stored["values"] == list(seed.series[0].values)
    assert [d["discovery_id"] for d in store.discoveries()] == ["amazon-basin--sahel"]


def test_a_written_seed_set_matches_the_schemas(catalog, tmp_path, validator_for):
    write_seed_set(compute_seed_set(opposite_pair(), catalog), tmp_path)

    for path in (tmp_path / "series").glob("*.json"):
        validator_for("series.schema.json").validate(json.loads(path.read_text()))
    for path in (tmp_path / "discoveries").glob("*.json"):
        validator_for("discovery.schema.json").validate(json.loads(path.read_text()))


def test_regenerating_replaces_the_previous_seed_set(catalog, tmp_path: Path):
    write_seed_set(compute_seed_set(opposite_pair(), catalog), tmp_path)
    stale = tmp_path / "discoveries" / "old--gone.json"
    stale.write_text("{}")

    write_seed_set(compute_seed_set(opposite_pair(), catalog), tmp_path)

    assert not stale.exists()
    assert (tmp_path / "discoveries" / "amazon-basin--sahel.json").exists()


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_seed_set.py"


def run_script(series_dir: Path, output: Path, *flags: str):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--series-dir",
            str(series_dir),
            "--output",
            str(output),
            *flags,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_the_command_refuses_a_seed_set_missing_an_evidence_label(tmp_path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    for one in opposite_pair():
        (series_dir / f"{one.region_id}__{one.variable_id}.json").write_text(
            json.dumps(dataclasses.asdict(one))
        )
    output = tmp_path / "seed"

    refused = run_script(series_dir, output)

    assert refused.returncode == 1
    assert "Some evidence" in refused.stderr
    assert not output.exists()

    allowed = run_script(series_dir, output, "--allow-missing-labels")

    assert allowed.returncode == 0, allowed.stderr
    assert (output / "discoveries" / "amazon-basin--sahel.json").exists()


SEED_DIR = Path(__file__).resolve().parents[1] / "data" / "seed"


def seed_files(kind: str) -> list[Path]:
    return sorted((SEED_DIR / kind).glob("*.json"))


def test_the_committed_seed_set_matches_the_schemas(validator_for):
    assert seed_files("series") and seed_files("discoveries")
    for path in seed_files("series"):
        validator_for("series.schema.json").validate(json.loads(path.read_text()))
    for path in seed_files("discoveries"):
        validator_for("discovery.schema.json").validate(json.loads(path.read_text()))


def test_the_committed_seed_set_shows_strong_and_weak_cases():
    labels = {
        json.loads(path.read_text())["evidence_label"]
        for path in seed_files("discoveries")
    }

    assert labels == {STRONG_EVIDENCE, "Some evidence", NOT_ENOUGH_EVIDENCE}


def test_the_committed_seed_set_has_a_series_for_each_offered_pair(catalog):
    stored = {path.stem for path in seed_files("series")}
    offered = {
        f"{region.region_id}__{variable.variable_id}"
        for region in catalog.regions
        for variable in catalog.variables
        if variable.variable_id in region.variable_ids
        and variable.variable_id != "vegetation-index"  # not acquired yet (#41)
    }

    assert stored == offered


def test_the_results_service_serves_the_seed_set_by_default():
    root = Path(__file__).resolve().parents[1]
    env = {k: v for k, v in os.environ.items() if k != "WEATHER_REPORT_DATA_DIR"}
    probe = (
        "from fastapi.testclient import TestClient; from api.main import app;"
        "r = TestClient(app).get('/api/series', params="
        "{'region_id': 'sahara', 'variable_id': 'temperature'});"
        "print(r.status_code, len(TestClient(app).get('/api/discoveries').json()['data']))"
    )

    run = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=root,
        env={**env, "PYTHONPATH": str(root / "src")},
        capture_output=True,
        text=True,
        check=False,
    )

    expected = len(seed_files("discoveries"))
    assert run.stdout.split() == ["200", str(expected)], run.stderr
