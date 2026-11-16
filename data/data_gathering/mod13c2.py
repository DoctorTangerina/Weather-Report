"""MODIS/Terra MOD13C2 granules (HDF4) as CF NetCDF-4 files the reader can open.

The series reader only opens NetCDF/CF files, and the netCDF4 library here is
built without HDF4 support. So each granule is converted once, when it is
acquired, into a NetCDF-4 file holding its NDVI layer with CF time, latitude and
longitude coordinates.

MODIS HDF4 files *divide* by their `scale_factor` (NDVI = stored / 10000), the
opposite of CF, which multiplies. The converted file keeps the stored integers
and states the CF form (`scale_factor` 0.0001), so any CF reader gets NDVI.
"""

from __future__ import annotations

import os
import re
import tempfile
from datetime import date
from pathlib import Path

import numpy as np
from netCDF4 import Dataset

NDVI = "CMG 0.05 Deg Monthly NDVI"
QUALITY = "CMG 0.05 Deg Monthly VI Quality"
TIME_UNITS = "days since 2000-01-01"
LAND = 1  # Land/Water flag 001, "Land (Nothing else but land)"
# Relative to the acquisition folder; config.json's VARIABLE_RULES points here.
LAND_MASK = Path("masks/MOD13C2_landmask_005d.nc")


def is_granule(path: Path) -> bool:
    """A MOD13C2 HDF4 granule, by NASA's file naming (MOD13C2.AYYYYDDD...hdf).

    Decided by the file, not the dataset label, because callers label datasets
    differently: the API passes the catalog's "MODIS/Terra MOD13C2 v061".
    """
    path = Path(path)
    return path.name.startswith("MOD13C2.") and path.suffix == ".hdf"


def readable_copy(hdf_path: Path) -> Path:
    """The granule's NetCDF-4 copy beside it, converting it the first time."""
    nc_path = Path(hdf_path).with_suffix(".nc")
    return nc_path if nc_path.exists() else convert(hdf_path, nc_path)


def convert(hdf_path: Path, nc_path: Path) -> Path:
    """Write the granule's NDVI as a CF NetCDF-4 file; returns `nc_path`.

    The file is written beside `nc_path` and moved into place only when
    complete, so an existing `nc_path` is always a whole conversion.
    """
    metadata, attributes, stored = _read(hdf_path, NDVI)
    latitudes, longitudes = _grid(metadata["StructMetadata.0"], stored.shape)
    first_day = _first_day(metadata["CoreMetadata.0"])
    scale, offset = float(attributes["scale_factor"]), float(attributes["add_offset"])
    if scale <= 0 or offset != 0:
        raise ValueError(
            f"{Path(hdf_path).name}: expected a positive scale_factor and no "
            f"add_offset, found {scale} and {offset}."
        )

    def write(out):
        out.title = "MOD13C2 v061 NDVI converted from HDF4 for the series reader"
        out.source = Path(hdf_path).name
        out.createDimension("time", 1)
        time = out.createVariable("time", "f8", ("time",))
        time.standard_name = "time"
        time.units = TIME_UNITS
        time.calendar = "standard"
        time[:] = [(first_day - date(2000, 1, 1)).days]
        _write_axes(out, latitudes, longitudes)
        ndvi = out.createVariable(
            NDVI,
            "i2",
            ("time", "lat", "lon"),
            zlib=True,
            complevel=4,
            fill_value=np.int16(attributes["_FillValue"]),
        )
        ndvi.set_auto_maskandscale(False)
        ndvi.long_name = NDVI
        ndvi.units = attributes.get("units", "NDVI")
        ndvi.scale_factor = 1.0 / scale
        ndvi.add_offset = 0.0
        ndvi.valid_range = np.asarray(attributes["valid_range"], dtype=np.int16)
        ndvi[0] = stored

    return _write_atomically(Path(nc_path), write)


def update_land_mask(mask_path: Path, hdf_paths: list[Path]) -> Path:
    """Add the granules' land cells to the static land mask at `mask_path`.

    A cell is land (1) when any granule, including those already in the mask,
    flags it "Land" in VI Quality bits 11-13. Coastlines, shorelines and inland
    water are not land. Taking every granule matters: a land cell with no data,
    as in polar night, is fill and its flag then reads as deep ocean, so one
    month alone would drop it, and the reader refuses a mask that changes.
    """
    mask_path = Path(mask_path)
    land, grid = None, None
    for hdf_path in hdf_paths:
        metadata, _, flags = _read(hdf_path, QUALITY)
        cells = ((flags >> 11) & 0b111) == LAND  # fill (65535) reads as 7, not land
        if land is None:
            land = cells
            grid = _grid(metadata["StructMetadata.0"], flags.shape)
        elif cells.shape != land.shape:
            raise ValueError(f"{Path(hdf_path).name} is on a different grid.")
        else:
            land |= cells
    if land is None:
        raise ValueError("Give at least one granule to build the land mask from.")
    if mask_path.exists():
        with Dataset(mask_path) as existing:
            earlier = np.asarray(existing.variables["land_mask"][:]) == 1
        if earlier.shape != land.shape:
            raise ValueError(f"{mask_path} is on a different grid.")
        land |= earlier

    def write(out):
        out.title = "MOD13C2 static land mask from the VI Quality Land/Water flag"
        _write_axes(out, *grid)
        variable = out.createVariable(
            "land_mask", "i1", ("lat", "lon"), zlib=True, complevel=4
        )
        variable.long_name = "land (1) in any acquired MOD13C2 granule, else 0"
        variable[:] = land.astype(np.int8)

    return _write_atomically(mask_path, write)


def _read(hdf_path: Path, layer_name: str):
    """The granule's global attributes, and one layer's attributes and values."""
    from pyhdf.SD import SD, SDC

    granule = SD(str(hdf_path), SDC.READ)
    try:
        layer = granule.select(layer_name)
        try:
            return granule.attributes(), layer.attributes(), layer[:]
        finally:
            layer.endaccess()
    finally:
        granule.end()


def _write_axes(out, latitudes, longitudes) -> None:
    out.Conventions = "CF-1.8"
    for name, values, units, standard in (
        ("lat", latitudes, "degrees_north", "latitude"),
        ("lon", longitudes, "degrees_east", "longitude"),
    ):
        out.createDimension(name, len(values))
        axis = out.createVariable(name, "f8", (name,))
        axis.standard_name = standard
        axis.units = units
        axis[:] = values


def _write_atomically(path: Path, write) -> Path:
    """Run `write` on a new NetCDF-4 file, then move it to `path` in one step."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        dir=path.parent, prefix=".write-", suffix=".nc"
    )
    os.close(handle)
    try:
        with Dataset(temporary, "w", format="NETCDF4") as out:
            write(out)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return path


def _grid(struct_metadata: str, shape: tuple[int, int]):
    """Cell-centre latitudes (north first) and longitudes of a GCTP_GEO grid."""

    def value(key: str) -> str:
        match = re.search(rf"\b{key}=([^\n]+)", struct_metadata)
        if match is None:
            raise ValueError(f"Grid metadata has no {key}.")
        return match.group(1).strip()

    if value("Projection") != "GCTP_GEO":
        raise ValueError("Only geographic (GCTP_GEO) MOD13C2 grids are supported.")
    rows, cols = int(value("YDim")), int(value("XDim"))
    if (rows, cols) != tuple(shape):
        raise ValueError(f"Grid metadata says {rows}x{cols}, the layer is {shape}.")
    west, north = (
        _degrees(part) for part in value("UpperLeftPointMtrs").strip("()").split(",")
    )
    east, south = (
        _degrees(part) for part in value("LowerRightMtrs").strip("()").split(",")
    )
    latitudes = north - (np.arange(rows) + 0.5) * (north - south) / rows
    longitudes = west + (np.arange(cols) + 0.5) * (east - west) / cols
    return latitudes, longitudes


def _degrees(packed: str) -> float:
    """GCTP packed degrees-minutes-seconds (DDDMMMSSS.SS) as decimal degrees."""
    number = float(packed)
    magnitude = abs(number)
    degrees, rest = divmod(magnitude, 1_000_000)
    minutes, seconds = divmod(rest, 1_000)
    return float(np.copysign(degrees + minutes / 60 + seconds / 3600, number))


def _first_day(core_metadata: str) -> date:
    match = re.search(
        r"OBJECT\s*=\s*RANGEBEGINNINGDATE\b.*?VALUE\s*=\s*\"(\d{4}-\d{2}-\d{2})\"",
        core_metadata,
        re.DOTALL,
    )
    if match is None:
        raise ValueError("Granule metadata has no RANGEBEGINNINGDATE.")
    return date.fromisoformat(match.group(1))
