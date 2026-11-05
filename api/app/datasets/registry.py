"""Dataset catalog served by ``GET /api/datasets``.

Only MAIAC is implemented. The other entries describe planned adapters so the web
client and API contract are ready for them; their endpoints answer 501 NOT_IMPLEMENTED
until an adapter with tests and provenance exists. Metadata for planned datasets comes
from ``docs/DATA_CATALOG.md`` and must be re-verified against the Earth Engine catalog
when each adapter is implemented.
"""

from __future__ import annotations

from typing import Any

from . import maiac_spec as maiac

_PLANNED_NOTE = "From docs/DATA_CATALOG.md; re-verify against the Earth Engine catalog when implementing."

DATASETS: dict[str, dict[str, Any]] = {
    maiac.DATASET_KEY: {
        "key": maiac.DATASET_KEY,
        "status": "implemented",
        "title": maiac.DATASET_TITLE,
        "collection_id": maiac.COLLECTION_ID,
        "observation_type": "satellite_retrieval",
        "observation_type_label": "Satellite retrieval (observation-derived)",
        "variables": [
            {
                "band": maiac.AOD_BAND,
                "derived_band": maiac.DERIVED_BAND,
                "quantity": maiac.QUANTITY,
                "unit": maiac.UNIT,
                "scale_factor": maiac.SCALE_FACTOR,
            },
            {"band": maiac.QA_BAND, "quantity": "AOD quality assurance bit field", "unit": "bit field"},
        ],
        "native_grid": "MODIS sinusoidal grid, catalog pixel size 1000 m",
        "temporal_support": "Per-overpass granules (Terra and Aqua), daily cadence",
        "caveats": [maiac.CAVEAT],
        "not_a_measurement_of": list(maiac.NOT_A_MEASUREMENT_OF),
        "catalog_url": maiac.CATALOG_URL,
        "citation": maiac.CITATION,
        "metadata_note": "Checked against the Earth Engine catalog and MAIAC user guide on 2026-11-04. "
        f"Processing method {maiac.METHOD_VERSION} (primary variant {maiac.PRIMARY.id}).",
    },
    "era5_land_wind": {
        "key": "era5_land_wind",
        "status": "planned",
        "title": "ERA5-Land hourly — 10 m wind components",
        "collection_id": "ECMWF/ERA5_LAND/HOURLY",
        "observation_type": "reanalysis",
        "observation_type_label": "Reanalysis (model output constrained by observations)",
        "variables": [
            {"band": "u_component_of_wind_10m", "unit": "m/s"},
            {"band": "v_component_of_wind_10m", "unit": "m/s"},
        ],
        "native_grid": "~11,132 m",
        "temporal_support": "Hourly",
        "caveats": [
            "Reanalysis, not a site anemometer; ~11 km grid does not resolve mine-scale flow.",
            "Wind direction must state 'from' vs 'toward' convention explicitly.",
            "Pair with satellite overpass hour rather than daily or monthly means where feasible.",
        ],
        "not_a_measurement_of": ["site-scale wind", "plume transport"],
        "catalog_url": "https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_HOURLY",
        "metadata_note": _PLANNED_NOTE,
    },
    "sentinel2_sr": {
        "key": "sentinel2_sr",
        "status": "planned",
        "title": "Sentinel-2 L2A surface reflectance (harmonized)",
        "collection_id": "COPERNICUS/S2_SR_HARMONIZED",
        "observation_type": "surface_imagery",
        "observation_type_label": "Surface reflectance imagery (land surface context)",
        "variables": [{"band": "B2, B3, B4, B8 (10 m); B11, B12 (20 m)", "unit": "scaled reflectance"}],
        "native_grid": "10 / 20 / 60 m depending on band",
        "temporal_support": "Revisit of a few days, cloud-dependent",
        "caveats": [
            "Maps surface features (pits, stockpiles, haul roads); does not measure airborne dust.",
            "Cannot sharpen 1 km MAIAC AOD into a 10 m aerosol observation.",
        ],
        "not_a_measurement_of": ["airborne dust concentration", "AOD"],
        "catalog_url": "https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED",
        "metadata_note": _PLANNED_NOTE,
    },
    "s5p_aai": {
        "key": "s5p_aai",
        "status": "planned",
        "title": "Sentinel-5P TROPOMI absorbing aerosol index (OFFL L3)",
        "collection_id": "COPERNICUS/S5P/OFFL/L3_AER_AI",
        "observation_type": "satellite_retrieval",
        "observation_type_label": "Satellite retrieval (observation-derived)",
        "variables": [{"band": "absorbing_aerosol_index", "unit": "dimensionless"}],
        "native_grid": "1,113.2 m Earth Engine L3 grid (native retrieval footprint is coarser)",
        "temporal_support": "Daily overpass",
        "caveats": ["Regional dust/smoke episode indicator; not PM mass and not source-specific."],
        "not_a_measurement_of": ["PM10", "PM2.5", "mine-attributable dust"],
        "catalog_url": "https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_OFFL_L3_AER_AI",
        "metadata_note": _PLANNED_NOTE,
    },
    "merra2_dust": {
        "key": "merra2_dust",
        "status": "planned",
        "title": "MERRA-2 aerosol diagnostics (dust)",
        "collection_id": "NASA/GSFC/MERRA/aer/2",
        "observation_type": "reanalysis",
        "observation_type_label": "Aerosol reanalysis (model output)",
        "variables": [
            {"band": "DUSMASS", "unit": "kg/m³"},
            {"band": "DUSMASS25", "unit": "kg/m³"},
            {"band": "DUEXTTAU", "unit": "dimensionless"},
        ],
        "native_grid": "~69,375 × 55,000 m",
        "temporal_support": "Hourly",
        "caveats": ["Very coarse regional background; cannot resolve local mine-scale concentrations."],
        "not_a_measurement_of": ["local surface concentration", "mine-attributable dust"],
        "catalog_url": "https://developers.google.com/earth-engine/datasets/catalog/NASA_GSFC_MERRA_aer_2",
        "metadata_note": _PLANNED_NOTE,
    },
}

UNAVAILABLE_MODULES = [
    {
        "key": "dispersion_model",
        "title": "Dispersion model",
        "status": "not_available",
        "reason": "Requires independent emission estimates, a suitable transport model "
        "(e.g. AERMOD/HYSPLIT) and validation. Satellite overlays are not a transport model.",
    },
    {
        "key": "mine_contribution",
        "title": "Mine contribution / attribution",
        "status": "not_available",
        "reason": "Requires verified source geometry, matched upwind/control regions, regional "
        "dust-event screening and statistical testing with uncertainty.",
    },
    {
        "key": "pm_estimates",
        "title": "Surface PM10 / PM2.5 estimates",
        "status": "not_available",
        "reason": "Requires independent ground observations for training and held-out validation. "
        "AOD is never converted to PM with unvalidated constants.",
    },
]


def get_dataset(key: str) -> dict[str, Any] | None:
    return DATASETS.get(key)
