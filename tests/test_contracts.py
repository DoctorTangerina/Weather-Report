"""The contract test: the committed stub set validates against the schemas.

The stub set is built through `engine.contracts`, so passing here also shows
the Python contract objects and the JSON Schemas agree.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from engine import ENGINE_VERSION, JsonResultStore, Period, applies_to, load_catalog
from engine.contracts import Discovery, Series, as_dict


def series_paths(stub_dir: Path) -> list[Path]:
    return sorted(stub_dir.glob("series/*.json"))


def discovery_paths(stub_dir: Path) -> list[Path]:
    return sorted(stub_dir.glob("discoveries/*.json"))


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_schema_is_itself_valid(schema_paths):
    assert schema_paths, "no schemas found"
    for path in schema_paths:
        Draft202012Validator.check_schema(load(path))


def test_catalog_matches_the_catalog_schema(catalog_path, validator_for):
    validator_for("catalog.schema.json").validate(load(catalog_path))


def test_stub_series_match_the_series_schema(stub_dir, validator_for):
    paths = series_paths(stub_dir)
    assert paths, "no stub series found"
    validator = validator_for("series.schema.json")
    for path in paths:
        validator.validate(load(path))


def test_stub_discoveries_match_the_discovery_schema(stub_dir, validator_for):
    paths = discovery_paths(stub_dir)
    assert paths, "no stub discoveries found"
    validator = validator_for("discovery.schema.json")
    for path in paths:
        validator.validate(load(path))


def test_stub_set_covers_every_evidence_label(stub_dir):
    labels = {load(path)["evidence_label"] for path in discovery_paths(stub_dir)}
    assert labels == {"Strong evidence", "Some evidence", "Not enough evidence yet"}


def test_series_values_are_aligned_with_the_period(stub_dir):
    for path in series_paths(stub_dir):
        series = Series.from_dict(load(path))
        start_year, start_month = (int(part) for part in series.period.start.split("-"))
        end_year, end_month = (int(part) for part in series.period.end.split("-"))
        expected = (end_year - start_year) * 12 + (end_month - start_month) + 1
        assert len(series.values) == expected, path.name


def test_missing_fraction_counts_the_null_months(stub_dir):
    for path in series_paths(stub_dir):
        series = Series.from_dict(load(path))
        missing = sum(1 for value in series.values if value is None)
        assert series.quality.missing_fraction == pytest.approx(
            missing / len(series.values), abs=1e-4
        ), path.name


def test_trends_are_ordered_to_match_the_discovery_regions(stub_dir):
    for path in discovery_paths(stub_dir):
        discovery = load(path)
        for contrast in discovery["contrasts"]:
            ordered = [trend["region_id"] for trend in contrast["trends"]]
            assert ordered == discovery["region_ids"], path.name


def test_discovery_trends_agree_with_the_declared_contrast_kind(stub_dir):
    for path in discovery_paths(stub_dir):
        discovery = load(path)
        for contrast in discovery["contrasts"]:
            rates = [trend["rate_per_decade"] for trend in contrast["trends"]]
            same_sign = rates[0] * rates[1] > 0
            if contrast["kind"] == "opposite_sign":
                assert not same_sign, path.name
            else:
                assert same_sign, path.name


def test_catalog_offers_only_variables_that_apply_to_the_region(catalog_path):
    catalog = load_catalog(catalog_path)
    known = {variable.variable_id for variable in catalog.variables}
    for region in catalog.regions:
        assert set(region.variable_ids) <= known
        for variable_id in region.variable_ids:
            assert applies_to(catalog, region.region_id, variable_id)
    assert not applies_to(catalog, "not-a-region", "temperature")


def test_store_serves_the_stub_set_keyed_by_region_variable_and_period(stub_dir):
    store = JsonResultStore(stub_dir, ENGINE_VERSION)
    period = Period(start="2000-01", end="2024-12")

    assert store.series("amazon-basin", "temperature", period) is not None
    assert (
        store.series("amazon-basin", "temperature", Period("2010-01", "2024-12"))
        is None
    )
    assert store.series("not-a-region", "temperature", period) is None
    assert [d["discovery_id"] for d in store.discoveries()][0] == "amazon-basin--sahel"
    assert store.discovery("amazon-basin--sahel") is not None
    assert store.discovery("nope") is None


def mutated(stub_dir: Path, name: str, change) -> dict:
    payload = load(stub_dir / "discoveries" / name)
    change(payload)
    return payload


def test_schema_rejects_an_unknown_property(stub_dir, validator_for):
    payload = load(stub_dir / "series" / "sahel__temperature.json")
    payload["rate_per_decade"] = 0.42
    with pytest.raises(ValidationError):
        validator_for("series.schema.json").validate(payload)


def test_schema_rejects_an_excluded_series_marked_as_included(stub_dir, validator_for):
    payload = load(stub_dir / "series" / "sahel__temperature.json")
    payload["quality"]["exclusions"] = ["too_many_missing_months"]
    with pytest.raises(ValidationError):
        validator_for("series.schema.json").validate(payload)


def test_schema_rejects_a_weak_discovery_offered_as_a_headline(stub_dir, validator_for):
    payload = mutated(
        stub_dir,
        "greenland-coast--amazon-basin.json",
        lambda d: d.update(headline_eligible=True),
    )
    with pytest.raises(ValidationError):
        validator_for("discovery.schema.json").validate(payload)


def test_schema_rejects_investigation_steps_out_of_order(stub_dir, validator_for):
    def swap(discovery: dict) -> None:
        steps = discovery["narrative"]["investigation"]["steps"]
        steps[0], steps[1] = steps[1], steps[0]

    payload = mutated(stub_dir, "amazon-basin--sahel.json", swap)
    with pytest.raises(ValidationError):
        validator_for("discovery.schema.json").validate(payload)


def test_schema_rejects_a_possible_cause_not_labeled_as_context(
    stub_dir, validator_for
):
    def relabel(discovery: dict) -> None:
        reason = discovery["narrative"]["investigation"]["steps"][2]
        reason["possible_causes"][0]["kind"] = "result"

    payload = mutated(stub_dir, "amazon-basin--sahel.json", relabel)
    with pytest.raises(ValidationError):
        validator_for("discovery.schema.json").validate(payload)


def test_schema_rejects_an_invalid_evidence_label(stub_dir, validator_for):
    payload = mutated(
        stub_dir,
        "amazon-basin--sahel.json",
        lambda d: d.update(evidence_label="p < 0.05"),
    )
    with pytest.raises(ValidationError):
        validator_for("discovery.schema.json").validate(payload)


def test_stub_discoveries_only_reference_catalog_entries(stub_dir, catalog_path):
    catalog = load_catalog(catalog_path)
    for path in discovery_paths(stub_dir):
        discovery = load(path)
        refs = [
            (trend["region_id"], trend["variable_id"])
            for contrast in discovery["contrasts"]
            for trend in contrast["trends"]
        ]
        refs += [
            (ref["region_id"], ref["variable_id"])
            for mirror in discovery["mirrors"]
            for ref in mirror["series"]
        ]
        refs += [
            (ref["region_id"], ref["variable_id"])
            for ref in discovery["narrative"]["investigation"]["steps"][1]["series"]
        ]
        for region_id, variable_id in refs:
            assert applies_to(catalog, region_id, variable_id), (
                f"{path.name}: {region_id}/{variable_id}"
            )


def test_every_series_a_stub_discovery_charts_is_in_the_store(stub_dir):
    store = JsonResultStore(stub_dir, ENGINE_VERSION)
    for path in discovery_paths(stub_dir):
        discovery = load(path)
        period = Period(**discovery["period"])
        check = discovery["narrative"]["investigation"]["steps"][1]
        for ref in check["series"]:
            assert (
                store.series(ref["region_id"], ref["variable_id"], period) is not None
            )


def test_stub_trends_use_the_engines_false_discovery_rate(stub_dir):
    import engine

    for path in discovery_paths(stub_dir):
        for contrast in load(path)["contrasts"]:
            for trend in contrast["trends"]:
                assert trend["multiple_comparisons"]["q"] == engine.FALSE_DISCOVERY_RATE


def test_a_stored_discovery_round_trips_through_the_contract_objects(stub_dir):
    """from_dict and as_dict must be exact inverses over JSON, or the API would
    quietly reshape a payload on its way back out."""
    for path in discovery_paths(stub_dir):
        payload = load(path)
        rebuilt = json.loads(json.dumps(as_dict(Discovery.from_dict(payload))))
        assert rebuilt == payload, path.name
