# Research Protocol / Судалгааны арга зүйн эхний хувилбар

**Version:** 0.2 — concept and preregistration draft, not a validated research result. MAIAC processing: method `maiac-aod550/0.2.0` (see the generated section in §3).

## 1. Study design

**Target:** Tavan Tolgoi coal-mining complex, Ömnögovi, Mongolia. Delimit exactly which pits, stockpiles, facilities, and haul-road corridors are included (e.g., Ukhaa Khudag and Tsankhi operations) based on approved source polygons. Do not label one centroid as the mine boundary.

**Proposed periods:** Start with a proof of concept for April 2025; then expand to monthly/seasonal and dust-event analyses in **2018–2025**, depending on source coverage and QA completeness. Do not present partial 2026 as a full-year comparison.

**Comparison regions:** Upwind sectors and matched background/control regions selected for comparable elevation, substrate, land cover, and weather; dynamically rotate upwind/downwind by day/hour when possible. Candidate buffer rings 0–10, 10–30, 30–50 km are exploratory rather than physical plume limits; vary these in sensitivity analysis.

## 2. Research questions and testable hypotheses

- RQ1: Are QA-controlled aerosol measures systematically elevated downwind of mine/haul-road zones relative to meteorologically comparable upwind/control regions?
- RQ2: How do wind vectors, wind speed, surface moisture, precipitation, season, and land cover modify the observed spatial pattern?
- RQ3: What part of the apparent signal is consistent with regional dust outbreaks (e.g., high regional background aerosol signal and MERRA-2 dust diagnostics)?
- RQ4: Where independent PM10 / PM2.5 ground observations exist, how well do statistical estimates transfer to held-out time periods and sites?

Pre-register primary comparisons and report null findings; treat any causal attribution as an inference requiring control comparisons and alternative explanations.

## 3. Data processing

### MAIAC AOD (primary aerosol observable)

- Collection: `MODIS/061/MCD19A2_GRANULES`
- Band: `Optical_Depth_055`; scale factor **0.001** to produce dimensionless AOD at 0.55 μm.
- Apply documented `AOD_QA` bit fields: cloud mask bits 0–2, land/snow bits 3–4, AOD quality bits 8–11. Core QA mask: clear (1), land (0), best QA (0). Adjacency bits 5–7 are decoded; filtering on adjacency == 0 is a sensitivity variant. Undocumented or reserved QA values are rejected and counted, never silently accepted.
- Keep the product valid range (raw −100..8000, AOD −0.1..8.0) in the primary series; never clamp AOD to 0. A non-negative (0..8.0) series is a separate sensitivity variant. Handle granule overlaps consistently. Count valid retrievals and report coverage for every time window.

<!-- BEGIN GENERATED: maiac-method (python -m scripts.generate_method_artifacts) -->
#### Implemented MAIAC method `maiac-aod550/0.2.0`

This section is generated from `api/app/datasets/maiac_method.json`, the single source used by the backend, the parity script, the API schema, the CSV header and the UI.

- Scaling: `Optical_Depth_055` raw integer x 0.001 (offset 0); range tests are applied to the raw integers; **no clamping**.
- Core QA (`core_qa`): AOD_QA bits 0-2 == 1 (clear) AND bits 3-4 == 0 (land) AND bits 8-11 == 0 (best quality).
- Documented-value guard: Every non-core AOD_QA field must hold a documented value: adjacency bits 5-7 in {0..5}, glint bit 12 in {0,1}, aerosol model bits 13-14 in {0,1,2}, reserved bit 15 == 0. Retrievals failing only this guard are rejected and counted as qa_guard_rejections, never silently accepted.
- Variants (computed in the same pass; sensitivity variants never replace the primary result):
  - `product_range` (primary): Core QA + documented-value guard; raw Optical_Depth_055 in [-100, 8000] (AOD -0.100..8.000); adjacency not filtered. No clamping: small negative AOD is kept.
  - `nonnegative_sensitivity` (sensitivity): As primary, but raw Optical_Depth_055 in [0, 8000] (AOD 0.000..8.000). Negative retrievals are excluded, not set to zero.
  - `adjacency_clear_sensitivity` (sensitivity): As primary, plus AOD_QA adjacency bits 5-7 == 0.
- Spatial rule: All ROI statistics use the MAIAC native sinusoidal grid and Earth Engine unweighted reducers: a pixel is included when its centre lies inside the ROI. Pixel-level sums and per-granule counts use the identical rule.
- Temporal rule: Per-pixel statistics use all QA-passing granule retrievals with system:time_start in [start, end_exclusive) (UTC). Granules are independent overpass retrievals; a valid day is a UTC calendar day with >= 1 valid retrieval anywhere in the ROI.
- Statistic definitions:
  - `pixels_total`: Number of MAIAC native-grid pixels whose centre lies inside the ROI.
  - `pixels_with_valid`: Number of ROI pixels with at least one valid retrieval in the period.
  - `coverage_fraction`: pixels_with_valid / pixels_total; null when pixels_total is 0.
  - `valid_retrievals`: Sum over ROI pixels of the per-pixel count of valid granule retrievals (pixel-level sum).
  - `valid_retrievals_granule_sum`: Sum over granules of each granule's count of valid ROI pixels (per-granule sum); must equal valid_retrievals.
  - `retrievals_before_qa`: Sum over ROI pixels of granule retrievals whose raw Optical_Depth_055 is present and inside the product valid range [-100, 8000], before any QA test.
  - `qa_retention_fraction`: valid_retrievals / retrievals_before_qa; null when retrievals_before_qa is 0.
  - `qa_guard_rejections`: Retrievals inside the product valid range that pass core QA but fail the documented-value guard (undocumented or reserved AOD_QA values).
  - `granules_intersecting`: Number of granules whose footprint intersects the ROI in the period.
  - `granules_with_valid`: Number of granules with at least one valid ROI pixel.
  - `valid_day_count`: Number of distinct UTC days with at least one valid retrieval anywhere in the ROI.
  - `roi_mean_aod`: Unweighted mean, over ROI pixels with >= 1 valid retrieval, of each pixel's period-mean AOD (mean of per-pixel period means). null when no valid retrieval.
  - `roi_pooled_retrieval_mean_aod`: Mean of all valid pixel-level retrievals pooled together (sum of AOD over every valid pixel retrieval / valid_retrievals). A different statistic from roi_mean_aod; null when no valid retrieval.
- Acceptance parity (opt-in, live Earth Engine): month 2025-04; integer fields exact; means within an absolute tolerance of 1e-09. Parity evidence shows the backend reproduces the Code Editor computation for one ROI and month. It is not scientific validation of the AOD product or of any attribution.
<!-- END GENERATED: maiac-method -->

- Compare per-pixel mean/median and episode-specific scenes; do not interpret cloud-induced gaps as zero AOD.
- Reprojection / resampling cannot create new independent information.

### ERA5-Land climate covariates

- Collection `ECMWF/ERA5_LAND/HOURLY` with `u_component_of_wind_10m` and `v_component_of_wind_10m` (m/s), and soil moisture / precipitation as appropriate.
- Wind speed = sqrt(u² + v²); wind direction must clearly distinguish **towards** vs **from** conventions.
- Align temporal measurements to actual satellite overpass windows rather than daily/montly averages where feasible. Beware local-scale winds not represented in ~11 km model grids.

### Sentinel-2 source mapping

- Collection `COPERNICUS/S2_SR_HARMONIZED` with appropriately selected S2 cloud-quality layers.
- Map expansion of pits, disturbance, stockpiles, active haul roads, vegetation/bare ground. These layers **do not directly measure airborne dust**.

### Additional supporting observations

- `COPERNICUS/S5P/OFFL/L3_AER_AI`: absorbing aerosol index; useful as regional dust-event indicator, not as direct PM10 or mine attribution.
- `NASA/GSFC/MERRA/aer/2`: use `DUSMASS`, `DUSMASS25`, `DUEXTTAU` as **coarse model fields** for regional aerosol background, not local mine-scale concentrations.
- Ground PM10, PM2.5, wind, humidity and ideally AERONET/AOD references if verifiably available. Document calibration and uncertainties.

## 4. Attribution framework

1. Identify credible source geometry (pits, haul roads, loading areas, stockpiles) and operations data if obtainable.
2. Pair satellite observations with near-overpass meteorology, plus seasonal controls.
3. Measure directional upwind/downwind contrasts at matched distances; estimate effect size, confidence intervals and bootstrap or suitable spatial/temporal error treatment.
4. Flag and/or separately analyze regional dust-storm days using external observations, synoptic winds and aerosol reanalysis.
5. Cross-check with activity logs, road traffic intensity, ground PM measurements where possible.
6. Conduct sensitivity analysis for ROI, QA criteria, sector angular widths, buffer rings, time windows, weather covariates, and alternative control areas.
7. If emission estimates and meteorological forcing support it, compare an independent dispersion model (e.g., AERMOD for suitable near-field scenarios / HYSPLIT for transport) with observations. Satellite overlay alone is not a transport model.

## 5. Validation / reporting

- Present sensor QA retention fraction, valid-day counts, and uncertainty per time unit.
- For PM predictions, train/validate on independent ground observations; use spatial and temporal holdouts, and compare against simple baselines. Report MAE, RMSE, R², bias and coverage with appropriate units; never convert AOD to PM using unvalidated constants.
- For plume patterns, test reproducibility under independent imagery/time windows and wind direction. Acknowledge the coarse native resolution of regional products.
- Track missing data, versioned processing scripts, dates accessed, chosen thresholds, and provenance. All figure captions must name observation type.

## 6. Minimum deliverables

- Verified ROI/zone and control geometry.
- At least one QA-filtered MAIAC AOD map with observation-count / QA coverage companion layer.
- Monthly trend and seasonal comparison with statistical uncertainty.
- Wind-aligned upwind/downwind analysis.
- Methodology, limitations and reproducible notebooks/scripts.
- Public claims only after independent validation and peer/research review.

## 7. Relevant scholarly context

- Stirnberg et al. (2020), *Mapping and Understanding Patterns of Air Quality Using Satellite Data and Machine Learning*, JGR Atmospheres: https://doi.org/10.1029/2019JD031380
- *Vertical Aerosol Structure Matters: Improving the AOD–PM2.5 Link for Air Quality and Exposure*, Environmental Science & Technology (2026): https://doi.org/10.1021/acs.est.6c00095
- *Monitoring Aeolian Erosion from Surface Coal Mines in the Mongolian Gobi Using InSAR Time Series Analysis*, Remote Sensing 16(21), 4111 (2024): https://www.mdpi.com/2072-4292/16/21/4111
