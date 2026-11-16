"""Acquiring one product after another keeps every product in the manifest."""

import json

from data.data_gathering.datasets import SearchArea, size_matches, write_manifest

AREA = SearchArea("box", (-1.0, -1.0, 1.0, 1.0))


def record(collection, filename):
    return {"collection_id": collection, "dataset": collection, "file": filename}


def listed(destination):
    manifest = json.loads((destination / "acquisition-manifest.json").read_text())
    return sorted((item["collection_id"], item["file"]) for item in manifest["files"])


def test_a_second_acquisition_adds_to_the_first_instead_of_replacing_it(tmp_path):
    write_manifest(
        tmp_path,
        "2023-01",
        "2023-02",
        [AREA],
        [record("T", "t1.nc4"), record("T", "t2.nc4")],
    )
    write_manifest(tmp_path, "2023-01", "2023-02", [AREA], [record("P", "p1.nc4")])
    assert listed(tmp_path) == [("P", "p1.nc4"), ("T", "t1.nc4"), ("T", "t2.nc4")]


def test_repeating_an_acquisition_does_not_duplicate_its_files(tmp_path):
    write_manifest(tmp_path, "2023-01", "2023-02", [AREA], [record("T", "t1.nc4")])
    write_manifest(tmp_path, "2023-01", "2023-02", [AREA], [record("T", "t1.nc4")])
    assert listed(tmp_path) == [("T", "t1.nc4")]


# CMR reports granule_size in MiB, to whatever precision the provider gives.
LP_DAAC_BYTES = 94565572  # MOD13C2.A2023001.061.2023034191717.hdf, downloaded


def test_a_size_rounded_to_four_decimals_by_cmr_still_matches_the_file():
    assert size_matches(LP_DAAC_BYTES, "90.1848") is True


def test_a_size_that_differs_beyond_the_reported_precision_does_not_match():
    assert size_matches(LP_DAAC_BYTES, "90.1847") is False
    assert size_matches(LP_DAAC_BYTES + 200, "90.1848") is False


def test_a_full_precision_size_must_match_to_the_byte():
    assert size_matches(54360134, "51.84186363220215") is True  # GES DISC MERRA-2
    assert size_matches(54360135, "51.84186363220215") is False


def test_an_unreported_size_cannot_be_verified():
    assert size_matches(LP_DAAC_BYTES, None) is None
    assert size_matches(LP_DAAC_BYTES, "unknown") is None
