"""MOD13C2 granules (HDF4) become CF NetCDF-4 files the series reader opens (#41).

Granules here are tiny synthetic HDF4 files laid out like the real ones: the
same layer names, attributes and HDF-EOS grid metadata, on a coarse global grid
instead of 3600 x 7200 cells. Nothing is downloaded.
"""

import json
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from netCDF4 import Dataset
from pyhdf.SD import SD, SDC

from data.data_gathering import datasets, get_catalog_series, mod13c2
from data.data_gathering import download as download_module
from data.data_gathering.series import DEFAULT_CONFIG

FILL = -3000
LAND, COAST, DEEP_OCEAN = 1, 2, 7
COLLECTION = "C2565788914-LPCLOUD"


def quality(land_water: np.ndarray) -> np.ndarray:
    """VI Quality words whose Land/Water flag (bits 11-13) is `land_water`."""
    return (np.asarray(land_water, dtype=np.uint16) << 11).astype(np.uint16)


def write_granule(path, ndvi, land_water=None, *, date="2020-06-01"):
    """A MOD13C2-like granule on a global grid of ndvi's shape, north row first."""
    ndvi = np.asarray(ndvi, dtype=np.int16)
    rows, cols = ndvi.shape
    if land_water is None:
        land_water = np.full(ndvi.shape, LAND)
    granule = SD(str(path), SDC.WRITE | SDC.CREATE | SDC.TRUNC)
    setattr(
        granule,
        "StructMetadata.0",
        "GROUP=GridStructure\n\tGROUP=GRID_1\n"
        '\t\tGridName="MOD_Grid_monthly_CMG_VI"\n'
        f"\t\tXDim={cols}\n\t\tYDim={rows}\n"
        "\t\tUpperLeftPointMtrs=(-180000000.000000,90000000.000000)\n"
        "\t\tLowerRightMtrs=(180000000.000000,-90000000.000000)\n"
        "\t\tProjection=GCTP_GEO\n\tEND_GROUP=GRID_1\nEND_GROUP=GridStructure\n",
    )
    setattr(
        granule,
        "CoreMetadata.0",
        "GROUP = RANGEDATETIME\n  OBJECT = RANGEBEGINNINGDATE\n    NUM_VAL = 1\n"
        f'    VALUE = "{date}"\n  END_OBJECT = RANGEBEGINNINGDATE\n'
        "END_GROUP = RANGEDATETIME\n",
    )
    layer = granule.create(mod13c2.NDVI, SDC.INT16, ndvi.shape)
    layer.long_name = mod13c2.NDVI
    layer.units = "NDVI"
    layer.valid_range = [-2000, 10000]
    layer.setfillvalue(FILL)
    layer.scale_factor = 10000.0
    layer.add_offset = 0.0
    layer[:] = ndvi
    layer.endaccess()
    flags = granule.create(mod13c2.QUALITY, SDC.UINT16, ndvi.shape)
    flags[:] = quality(land_water)
    flags.endaccess()
    granule.end()
    return path


def read_ndvi(path) -> np.ma.MaskedArray:
    with Dataset(path) as data:
        return data.variables[mod13c2.NDVI][:]


def test_ndvi_is_the_stored_integer_divided_by_10000(tmp_path):
    stored = np.array([[5000, 1234, 9999, -1500], [0, 10000, -2000, 7]])
    hdf = write_granule(tmp_path / "MOD13C2.A2020153.061.hdf", stored)

    converted = mod13c2.convert(hdf, tmp_path / "out.nc")

    values = read_ndvi(converted)
    assert values.shape == (1, 2, 4)
    assert values[0].filled(np.nan) == pytest.approx(stored / 10000)


def test_fill_and_out_of_range_cells_are_missing(tmp_path):
    stored = np.array([[FILL, -2001, 10001, 4000]])
    hdf = write_granule(tmp_path / "granule.hdf", stored)

    values = read_ndvi(mod13c2.convert(hdf, tmp_path / "out.nc"))[0, 0]

    assert values.mask.tolist() == [True, True, True, False]
    assert values[3] == pytest.approx(0.4)


def test_time_is_the_granules_first_day_and_cells_are_located_by_their_centres(
    tmp_path,
):
    hdf = write_granule(tmp_path / "g.hdf", np.zeros((4, 8)), date="2024-06-01")

    with Dataset(mod13c2.convert(hdf, tmp_path / "out.nc")) as data:
        time = data.variables["time"]
        assert (time.units, time.calendar) == ("days since 2000-01-01", "standard")
        assert time[:].tolist() == [(date(2024, 6, 1) - date(2000, 1, 1)).days]
        assert data.variables["lat"].units == "degrees_north"
        assert data.variables["lat"][:].tolist() == [67.5, 22.5, -22.5, -67.5]
        assert data.variables["lon"].units == "degrees_east"
        assert data.variables["lon"][:].tolist() == [
            -157.5,
            -112.5,
            -67.5,
            -22.5,
            22.5,
            67.5,
            112.5,
            157.5,
        ]


def read_mask(path):
    with Dataset(path) as data:
        return (
            data.variables["land_mask"][:].tolist(),
            data.variables["lat"][:].tolist(),
            data.variables["lon"][:].tolist(),
        )


def test_a_cell_is_land_if_any_granule_flags_it_land_and_never_if_coast_or_water(
    tmp_path,
):
    # In June the southern row is in polar night: fill, whose flag reads as ocean.
    june = write_granule(
        tmp_path / "june.hdf",
        [[5000, 5000, FILL, FILL], [FILL, FILL, FILL, FILL]],
        [[LAND, COAST, DEEP_OCEAN, LAND], [DEEP_OCEAN] * 4],
    )
    december = write_granule(
        tmp_path / "december.hdf",
        [[5000, 5000, FILL, FILL], [3000, 3000, FILL, FILL]],
        [[LAND, COAST, DEEP_OCEAN, DEEP_OCEAN], [LAND, LAND, DEEP_OCEAN, COAST]],
    )

    mask = mod13c2.update_land_mask(tmp_path / "masks" / "mask.nc", [june, december])

    land, latitudes, longitudes = read_mask(mask)
    assert land == [[1, 0, 0, 1], [1, 1, 0, 0]]
    assert latitudes == [45.0, -45.0]
    assert longitudes == [-135.0, -45.0, 45.0, 135.0]


def test_the_land_mask_aligns_with_the_converted_granules(tmp_path):
    hdf = write_granule(tmp_path / "g.hdf", np.zeros((4, 8)))
    mask = mod13c2.update_land_mask(tmp_path / "mask.nc", [hdf])
    with Dataset(mod13c2.convert(hdf, tmp_path / "out.nc")) as data:
        _, latitudes, longitudes = read_mask(mask)
        assert latitudes == data.variables["lat"][:].tolist()
        assert longitudes == data.variables["lon"][:].tolist()


def test_a_later_acquisition_adds_land_to_the_existing_mask(tmp_path):
    first = write_granule(tmp_path / "a.hdf", np.zeros((1, 2)), [[LAND, DEEP_OCEAN]])
    later = write_granule(tmp_path / "b.hdf", np.zeros((1, 2)), [[DEEP_OCEAN, LAND]])
    mask = tmp_path / "mask.nc"

    mod13c2.update_land_mask(mask, [first])
    mod13c2.update_land_mask(mask, [later])

    assert read_mask(mask)[0] == [[1, 1]]


def test_a_granule_with_an_offset_is_refused_rather_than_guessed(tmp_path):
    hdf = write_granule(tmp_path / "g.hdf", np.zeros((2, 4)))
    granule = SD(str(hdf), SDC.WRITE)
    layer = granule.select(mod13c2.NDVI)
    layer.add_offset = 5.0
    layer.endaccess()
    granule.end()

    with pytest.raises(ValueError, match="add_offset"):
        mod13c2.convert(hdf, tmp_path / "out.nc")
    assert not (tmp_path / "out.nc").exists()


# Acquisition through to the catalog series. Amazon basin (-70..-50 E, -10..2 N)
# holds 2 x 4 centres of a 5-degree grid: rows -2.5 and -7.5, columns -67.5 to
# -52.5. Six are land; the two at -52.5 E are coast, given an NDVI that would
# shift the mean if water were not masked out.
GRID = (36, 72)
AMAZON = (slice(18, 20), slice(22, 26))


def amazon_granule(month: int, *, empty=False):
    ndvi = np.full(GRID, FILL)
    land_water = np.full(GRID, DEEP_OCEAN)
    land_water[AMAZON] = LAND
    land_water[18:20, 25] = COAST
    if not empty:
        ndvi[AMAZON] = 5000 + 100 * month  # 0.51 in January ... 0.62 in December
        ndvi[18:20, 25] = 9500
    return ndvi, land_water


def fake_acquisition(monkeypatch, months, *, empty=()):
    """CMR lists one granule per month; downloading writes it as a MOD13C2 file."""
    granules = {
        f"MOD13C2.A2020{month:03d}.061.2020999999999.hdf": month for month in months
    }

    def entries(resource, parameters):
        assert parameters["collection_concept_id"] == COLLECTION
        for name, month in granules.items():
            yield {
                "id": f"G{month}-LPCLOUD",
                "time_start": f"2020-{month:02d}-01T00:00:00.000Z",
                "links": [
                    {
                        "rel": "http://esipfed.org/ns/fedsearch/1.1/data#",
                        "href": "https://data.lpdaac.earthdatacloud.nasa.gov/"
                        f"lp-prod-protected/MOD13C2.061/{name[:-4]}/{name}",
                    }
                ],
            }

    def download(url, destination, token):
        month = granules[Path(url).name]
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_granule(
            destination,
            *amazon_granule(month, empty=month in empty),
            date=f"2020-{month:02d}-01",
        )
        return destination

    monkeypatch.setattr(datasets, "cmr_entries", entries)
    monkeypatch.setattr(download_module, "download", download)
    monkeypatch.setattr(download_module, "load_token", lambda: "token")


def acquire(tmp_path, short_name="MOD13C2"):
    area = datasets.SearchArea("box", (-180.0, -90.0, 180.0, 90.0))
    return datasets.acquire(
        [{"collection_id": COLLECTION, "short_name": short_name}],
        [area],
        "2020-01",
        "2020-12",
        tmp_path / "downloads",
    )


def test_acquiring_mod13c2_records_converted_files_and_writes_the_land_mask(
    tmp_path, monkeypatch
):
    fake_acquisition(monkeypatch, [1, 2])

    # The API's live acquisition names the dataset by the catalog's label.
    manifest = json.loads(acquire(tmp_path, "MODIS/Terra MOD13C2 v061").read_text())

    downloads = tmp_path / "downloads"
    assert [record["file"] for record in manifest["files"]] == [
        "MOD13C2.A2020001.061.2020999999999.nc",
        "MOD13C2.A2020002.061.2020999999999.nc",
    ]
    assert [record["source_file"] for record in manifest["files"]] == [
        "MOD13C2.A2020001.061.2020999999999.hdf",
        "MOD13C2.A2020002.061.2020999999999.hdf",
    ]
    for record in manifest["files"]:
        assert record["bytes"] == (downloads / record["file"]).stat().st_size
        assert read_ndvi(downloads / record["file"]).count() == 8
    assert np.sum(read_mask(downloads / mod13c2.LAND_MASK)[0]) == 6


def test_the_vegetation_index_series_loads_from_acquired_mod13c2_granules(
    tmp_path, monkeypatch
):
    fake_acquisition(monkeypatch, range(1, 13), empty={4})
    manifest = acquire(tmp_path)
    # The shipped config, with its paths moved into this test's folder.
    config = json.loads(DEFAULT_CONFIG.read_text())
    config["SERIES_MANIFEST"] = str(manifest)
    rule = config["VARIABLE_RULES"][COLLECTION][mod13c2.NDVI]
    rule["land_mask"]["file"] = str(tmp_path / "downloads" / mod13c2.LAND_MASK)
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))

    result = get_catalog_series(
        "amazon-basin",
        "vegetation-index",
        {"start": "2020-01", "end": "2020-12"},
        config_path=config_path,
    )

    assert result["units"] == "NDVI"
    assert result["source"]["dataset"] == "MODIS/Terra MOD13C2 v061"
    expected = [None if month == 4 else 0.5 + month / 100 for month in range(1, 13)]
    assert result["values"] == pytest.approx(expected)
    assert result["quality"] == {
        "included": True,
        "missing_fraction": pytest.approx(1 / 12),
        "valid_land_fraction": 0.75,
        "exclusions": [],
    }
