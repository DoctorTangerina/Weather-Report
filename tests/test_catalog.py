"""Invariants of the Region and Variable catalog in `data/catalog.json`.

The first group holds for any catalog. The second records what #23 established
about this one: the NASA products confirmed against CMR and the AppEEARS product
API, the climate zones it covers and the contrasts it is built to show. Changing
any of those should be a deliberate edit to this file, not a side effect.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from engine import ENGINE_VERSION, applies_to, load_catalog

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "catalog.json"

# Regions that are open water, where land-only Variables must not be listed.
OCEAN_REGION_IDS = {"equatorial-pacific", "north-atlantic"}

# Regions where the ground is mostly ice. Land models such as GLDAS do not
# simulate ice sheets, so land-only Variables are not offered there either.
ICE_REGION_IDS = {"greenland-coast", "antarctic-peninsula"}

# Confirmed on 2026-11-14 against NASA's CMR collection and variable records,
# and the vegetation index against the AppEEARS product API it is requested
# from. See docs/catalog-sources.md for the units and conversions.
VERIFIED_SOURCES = {
    "temperature": ("GES DISC", "M2TMNXSLV", "T2M", "10.5067/AP1B0BA5PD2K"),
    "precipitation": ("GES DISC", "M2TMNXFLX", "PRECTOTCORR", "10.5067/0JRLVL8YV2Y4"),
    "soil-moisture": (
        "GES DISC",
        "GLDAS_NOAH025_M",
        "SoilMoi0_10cm_inst",
        "10.5067/SXAVCZFAQLNO",
    ),
    "vegetation-index": (
        "AppEEARS",
        "MOD13A3",
        "_1_km_monthly_NDVI",
        "10.5067/MODIS/MOD13A3.061",
    ),
}

# Pairs the catalog is built to contrast, each across a clear divide.
CONTRASTING_PAIRS = [
    ("amazon-basin", "sahara"),  # rain forest and desert
    ("congo-basin", "arabian-peninsula"),  # rain forest and desert
    ("siberian-arctic", "siberia"),  # tundra and the taiga just south of it
    ("equatorial-pacific", "north-atlantic"),  # warm and cool open ocean
    ("california", "great-plains"),  # winter rain and summer rain
]


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


def test_variable_schema_rejects_a_variable_without_a_definition(
    payload, validator_for
):
    variable = {k: v for k, v in payload["variables"][0].items() if k != "definition"}
    with pytest.raises(ValidationError):
        validator_for("variable.schema.json").validate(variable)


def test_variable_schema_rejects_a_cause_not_labeled_as_context(payload, validator_for):
    variable = json.loads(json.dumps(payload["variables"][0]))
    variable["possible_causes"][0]["kind"] = "result"
    with pytest.raises(ValidationError):
        validator_for("variable.schema.json").validate(variable)


def test_catalog_schema_rejects_a_variable_the_variable_schema_rejects(
    payload, validator_for
):
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
            assert not applies_to(catalog, region_id, variable_id), (
                region_id,
                variable_id,
            )


def test_bounding_boxes_are_ordered_and_do_not_cross_the_antimeridian(catalog):
    for region in catalog.regions:
        assert region.bbox.west < region.bbox.east, region.region_id
        assert region.bbox.south < region.bbox.north, region.region_id


def test_every_variable_has_distinct_possible_causes_labeled_as_context(catalog):
    for variable in catalog.variables:
        causes = variable.possible_causes
        assert causes, variable.variable_id
        assert len({cause.text for cause in causes}) == len(causes), (
            variable.variable_id
        )
        assert all(cause.kind == "context" for cause in causes), variable.variable_id


def test_land_only_variables_are_not_listed_for_ice_regions(catalog):
    land_only = {v.variable_id for v in catalog.variables if v.land_only}
    for region_id in ICE_REGION_IDS:
        assert catalog.region(region_id) is not None, region_id
        for variable_id in land_only:
            assert not applies_to(catalog, region_id, variable_id), (
                region_id,
                variable_id,
            )


def test_every_variable_names_its_confirmed_nasa_source(catalog):
    assert {v.variable_id for v in catalog.variables} == set(VERIFIED_SOURCES)
    for variable in catalog.variables:
        provider, product, field, doi = VERIFIED_SOURCES[variable.variable_id]
        source = variable.source
        assert source.provider == provider, variable.variable_id
        assert product in source.dataset, variable.variable_id
        assert source.variable == field, variable.variable_id
        assert source.url == f"https://doi.org/{doi}", variable.variable_id


def test_no_source_is_a_placeholder(catalog):
    for variable in catalog.variables:
        text = " ".join(
            filter(
                None,
                (
                    variable.source.dataset,
                    variable.source.variable,
                    variable.source.url,
                ),
            )
        ).lower()
        for marker in ("unresolved", "todo", "tbd", "placeholder", "stub"):
            assert marker not in text, (variable.variable_id, marker)


def zone(region) -> str:
    centre = (region.bbox.south + region.bbox.north) / 2
    if abs(centre) < 23.44:
        return "tropical"
    if abs(centre) >= 66.56:
        return "polar"
    return "temperate"


def test_regions_cover_every_climate_zone_in_both_hemispheres(catalog):
    covered = set()
    for region in catalog.regions:
        centre = (region.bbox.south + region.bbox.north) / 2
        if centre != 0:
            covered.add((zone(region), "north" if centre > 0 else "south"))
    for wanted in ("tropical", "temperate", "polar"):
        for hemisphere in ("north", "south"):
            assert (wanted, hemisphere) in covered, (wanted, hemisphere)


def test_the_catalog_holds_its_contrasting_pairs(catalog):
    for first, second in CONTRASTING_PAIRS:
        assert catalog.region(first) is not None, first
        assert catalog.region(second) is not None, second


def test_temperature_is_shown_in_degrees_celsius(catalog):
    """Students read Celsius; MERRA-2 stores kelvin, so the fetch layer converts."""
    assert catalog.variable("temperature").units == "°C"


def test_method_citation_names_its_authors_year_and_venue(catalog):
    citation = catalog.method_citation
    for part in ("Acker", "2009", "SeaWiFS", "EARSeL eProceedings"):
        assert part in citation, part
