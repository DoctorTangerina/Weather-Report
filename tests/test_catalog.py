"""Catalog invariants that must hold for any Region and Variable catalog.

They run against the stub catalog in `data/stub/catalog.json`. The real catalog
content is a separate ticket; when it lands, point `CATALOG_PATH` at it and these
tests keep guarding the same rules.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from engine import ENGINE_VERSION, applies_to, load_catalog

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "stub" / "catalog.json"

# Stub Regions that are open water, where land-only Variables must not be listed.
OCEAN_REGION_IDS = {"equatorial-pacific", "north-atlantic"}


@pytest.fixture(scope="module")
def payload() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(CATALOG_PATH)


def test_catalog_matches_the_catalog_schema(payload, validator_for):
    validator_for("catalog.schema.json").validate(payload)


def test_catalog_loads_through_the_contracts_at_the_engine_version(catalog):
    assert catalog.engine_version == ENGINE_VERSION
    assert catalog.method_citation


def test_every_variable_matches_the_variable_schema(payload, validator_for):
    validator = validator_for("variable.schema.json")
    assert payload["variables"]
    for variable in payload["variables"]:
        validator.validate(variable)


def test_variable_schema_rejects_a_variable_without_a_definition(payload, validator_for):
    variable = {k: v for k, v in payload["variables"][0].items() if k != "definition"}
    with pytest.raises(ValidationError):
        validator_for("variable.schema.json").validate(variable)


def test_variable_schema_rejects_a_cause_not_labeled_as_context(payload, validator_for):
    variable = json.loads(json.dumps(payload["variables"][0]))
    variable["possible_causes"][0]["kind"] = "result"
    with pytest.raises(ValidationError):
        validator_for("variable.schema.json").validate(variable)


def test_catalog_schema_rejects_a_variable_the_variable_schema_rejects(payload, validator_for):
    broken = json.loads(json.dumps(payload))
    del broken["variables"][0]["definition"]
    with pytest.raises(ValidationError):
        validator_for("catalog.schema.json").validate(broken)


def test_identifiers_and_names_are_unique(catalog):
    for items in (catalog.regions, catalog.variables):
        ids = [getattr(item, "region_id", None) or item.variable_id for item in items]
        names = [item.name for item in items]
        assert len(set(ids)) == len(ids)
        assert len(set(names)) == len(names)


def test_every_region_lists_only_known_variables(catalog):
    known = {variable.variable_id for variable in catalog.variables}
    for region in catalog.regions:
        assert set(region.variable_ids) <= known, region.region_id


def test_every_region_offers_temperature_and_precipitation(catalog):
    for region in catalog.regions:
        assert applies_to(catalog, region.region_id, "temperature"), region.region_id
        assert applies_to(catalog, region.region_id, "precipitation"), region.region_id


def test_land_only_variables_are_not_listed_for_ocean_regions(catalog):
    land_only = {v.variable_id for v in catalog.variables if v.land_only}
    assert land_only, "the catalog needs a land-only Variable to exercise this rule"
    for region_id in OCEAN_REGION_IDS:
        assert catalog.region(region_id) is not None, region_id
        for variable_id in land_only:
            assert not applies_to(catalog, region_id, variable_id), (region_id, variable_id)


def test_bounding_boxes_are_ordered_and_do_not_cross_the_antimeridian(catalog):
    for region in catalog.regions:
        assert region.bbox.west < region.bbox.east, region.region_id
        assert region.bbox.south < region.bbox.north, region.region_id


def test_every_variable_has_distinct_possible_causes_labeled_as_context(catalog):
    for variable in catalog.variables:
        causes = variable.possible_causes
        assert causes, variable.variable_id
        assert len({cause.text for cause in causes}) == len(causes), variable.variable_id
        assert all(cause.kind == "context" for cause in causes), variable.variable_id
