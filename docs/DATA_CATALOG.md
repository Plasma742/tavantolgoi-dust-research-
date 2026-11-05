# Verified Earth Engine Data Catalog

All values below are native/source dataset characteristics, **not** claimed output resolution after resampling. Always verify up-to-date collection status and scene coverage before analysis.

| Dataset | GEE collection ID | Primary fields | Reported grid size | Scientific caveat |
| --- | --- | --- | --- | --- |
| MODIS MAIAC MCD19A2 v6.1 | `MODIS/061/MCD19A2_GRANULES` | `Optical_Depth_055`, `AOD_QA`, `AOD_Uncertainty` | 1,000 m | Column AOD, not surface PM; scale AOD by 0.001 and mask QA |
| Sentinel-2 SR Harmonized | `COPERNICUS/S2_SR_HARMONIZED` | B2/B3/B4/B8 (10m), B11/B12 (20m), cloud masks | 10/20/60 m | Surface features, not airborne dust concentration |
| Sentinel-5P AER AI | `COPERNICUS/S5P/OFFL/L3_AER_AI` | `absorbing_aerosol_index` | 1,113.2 m GEE L3 grid | Native TROPOMI retrieval footprint is coarser; AAI not PM mass |
| ERA5-Land hourly | `ECMWF/ERA5_LAND/HOURLY` | `u_component_of_wind_10m`, `v_component_of_wind_10m`, soil moisture | ~11,132 m | Reanalysis not site-scale anemometer |
| MERRA-2 aerosol hourly | `NASA/GSFC/MERRA/aer/2` | `DUSMASS`, `DUSMASS25`, `DUEXTTAU` | ~69,375 × 55,000 m | Very coarse regional aerosol reanalysis; DUSMASS kg/m³ |

### Data quality contract for every map layer

- Dataset/collection ID and version
- Requested date range and actual observation window
- Variable/band and physical units
- Scale/offset applied; QA masks and resampling/interpolation choices
- Native resolution vs exported/display resolution
- Number of contributing images and valid pixels / coverage percentage
- Source citation, date accessed, processing code commit
- Explicit 'No data' for masked/missing observations

### Sources

- https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD19A2_GRANULES
- https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED
- https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_OFFL_L3_AER_AI
- https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_HOURLY
- https://developers.google.com/earth-engine/datasets/catalog/NASA_GSFC_MERRA_aer_2
