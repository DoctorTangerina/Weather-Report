"""Acquiring one product after another keeps every product in the manifest."""

import json

from data.data_gathering.datasets import SearchArea, write_manifest

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
