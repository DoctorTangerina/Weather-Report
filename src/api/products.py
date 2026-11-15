"""NASA products for each Variable that can be fetched on demand (ADR 0004).

Each entry is (monthly product, native sub-monthly product, version, field,
unit conversion). Vegetation index has none yet (#41).
"""

# Explicit product versions prevent selecting GLDAS 2.0 (ends in 2014).
PRODUCTS = {
    "temperature": ("M2TMNXSLV", "M2T1NXSLV", "5.12.4", "T2M", "kelvin_to_celsius"),
    "precipitation": (
        "M2TMNXFLX",
        "M2T1NXFLX",
        "5.12.4",
        "PRECTOTCORR",
        "rate_per_second_to_per_month",
    ),
    "soil-moisture": (
        "GLDAS_NOAH025_M",
        "GLDAS_NOAH025_3H",
        "2.1",
        "SoilMoi0_10cm_inst",
        "identity",
    ),
}
