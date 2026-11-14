"""DS-001 content: the real Region catalog and Variable catalog in `data/catalog.json`.

These tests go through the public loading interface (`load_catalog`, `applies_to`)
and the catalog JSON Schema. `data/stub/catalog.json` stays the four-Region stub
the skeleton runs on; this is the catalog the engine analyzes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine import ENGINE_VERSION, applies_to, load_catalog

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "catalog.json"

VARIABLE_IDS = {"temperature", "precipitation", "soil-moisture", "vegetation-index"}
OCEAN_REGION_IDS = {"equatorial-pacific", "north-atlantic"}
# Regions where a land mask and vegetation make no sense (ice and open water).
NO_LAND_VARIABLE_REGION_IDS = OCEAN_REGION_IDS | {"greenland-coast", "antarctic-peninsula"}
CONTRASTING_PAIRS = [
    ("amazon-basin", "sahara"),  # rain forest vs desert
    ("congo-basin", "arabian-peninsula"),  # rain forest vs desert
    ("western-europe", "australian-outback"),  # mild and wet vs hot and dry
]


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(CATALOG_PATH)


def words(text: str) -> int:
    return len(text.split())


def test_catalog_matches_the_catalog_schema(validator_for):
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    validator_for("catalog.schema.json").validate(payload)


def test_catalog_loads_through_the_contracts_at_the_engine_version(catalog):
    assert catalog.engine_version == ENGINE_VERSION
    assert catalog.method_citation


def test_catalog_has_about_two_dozen_regions(catalog):
    assert 22 <= len(catalog.regions) <= 26


def test_catalog_has_exactly_the_four_variables(catalog):
    assert {v.variable_id for v in catalog.variables} == VARIABLE_IDS


def test_identifiers_and_names_are_unique(catalog):
    region_ids = [r.region_id for r in catalog.regions]
    names = [r.name for r in catalog.regions]
    assert len(set(region_ids)) == len(region_ids)
    assert len(set(names)) == len(names)


def test_every_region_lists_only_known_variables(catalog):
    for region in catalog.regions:
        assert set(region.variable_ids) <= VARIABLE_IDS, region.region_id


def test_every_region_offers_temperature_and_precipitation(catalog):
    for region in catalog.regions:
        assert applies_to(catalog, region.region_id, "temperature"), region.region_id
        assert applies_to(catalog, region.region_id, "precipitation"), region.region_id


def test_land_only_variables_are_not_listed_for_ocean_regions(catalog):
    land_only = {v.variable_id for v in catalog.variables if v.land_only}
    assert land_only == {"soil-moisture", "vegetation-index"}
    for region_id in OCEAN_REGION_IDS:
        assert catalog.region(region_id) is not None, region_id
        for variable_id in land_only:
            assert not applies_to(catalog, region_id, variable_id), (region_id, variable_id)


def test_land_variables_are_listed_for_the_land_regions_that_can_use_them(catalog):
    for region in catalog.regions:
        expected = region.region_id not in NO_LAND_VARIABLE_REGION_IDS
        for variable_id in ("soil-moisture", "vegetation-index"):
            assert applies_to(catalog, region.region_id, variable_id) is expected, (
                region.region_id,
                variable_id,
            )


def test_every_variable_is_offered_for_several_regions(catalog):
    for variable in catalog.variables:
        offered = [r for r in catalog.regions if variable.variable_id in r.variable_ids]
        assert len(offered) >= 10, variable.variable_id


def test_bounding_boxes_are_ordered_and_do_not_cross_the_antimeridian(catalog):
    for region in catalog.regions:
        assert region.bbox.west < region.bbox.east, region.region_id
        assert region.bbox.south < region.bbox.north, region.region_id


def test_regions_are_spread_across_the_major_climate_zones(catalog):
    def band(region) -> str:
        latitude = abs((region.bbox.south + region.bbox.north) / 2)
        if latitude < 23.5:
            return "tropical"
        if latitude < 60:
            return "temperate"
        return "polar"

    counts = {"tropical": 0, "temperate": 0, "polar": 0}
    for region in catalog.regions:
        counts[band(region)] += 1
    assert counts["tropical"] >= 6
    assert counts["temperate"] >= 6
    assert counts["polar"] >= 2
    hemispheres = {region.bbox.north > 0 for region in catalog.regions}
    assert hemispheres == {True, False}, "both hemispheres need Regions"


@pytest.mark.parametrize(("first", "second"), CONTRASTING_PAIRS)
def test_catalog_contains_contrasting_region_pairs(catalog, first, second):
    assert catalog.region(first) is not None
    assert catalog.region(second) is not None


def test_regions_have_a_one_line_description_a_student_can_read(catalog):
    for region in catalog.regions:
        assert "\n" not in region.description, region.region_id
        assert 3 <= words(region.description) <= 25, region.region_id
        assert region.description.endswith("."), region.region_id


def test_variables_have_plain_language_definitions(catalog):
    for variable in catalog.variables:
        assert "\n" not in variable.definition, variable.variable_id
        assert 5 <= words(variable.definition) <= 35, variable.variable_id
        assert variable.units, variable.variable_id


def test_variable_sources_name_a_nasa_product_and_variable(catalog):
    for variable in catalog.variables:
        source = variable.source
        assert source.provider in {"GES DISC", "AppEEARS"}, variable.variable_id
        assert source.dataset and source.variable, variable.variable_id
        assert "unresolved" not in f"{source.dataset} {source.variable}".lower()
    assert catalog.variable("vegetation-index").source.provider == "AppEEARS"


def test_every_variable_has_several_distinct_possible_causes_labeled_as_context(catalog):
    for variable in catalog.variables:
        causes = variable.possible_causes
        assert len(causes) >= 3, variable.variable_id
        assert len({cause.text for cause in causes}) == len(causes), variable.variable_id
        assert all(cause.kind == "context" for cause in causes), variable.variable_id
        assert all(cause.text.endswith(".") for cause in causes), variable.variable_id


def test_possible_causes_do_not_claim_the_data_proved_anything(catalog):
    overclaiming = ("proves", "proved", "shows that", "our data", "we found", "caused by")
    for variable in catalog.variables:
        for cause in variable.possible_causes:
            lowered = cause.text.lower()
            assert not any(phrase in lowered for phrase in overclaiming), cause.text


def test_method_citation_names_the_method_paper(catalog):
    assert "SeaWiFS" in catalog.method_citation
    assert "chlorophyll" in catalog.method_citation.lower()
