# Build Brief for Claude — Tavan Tolgoi Research Platform

You are the lead software engineer for a scientific geospatial web application. Read `README.md`, `docs/RESEARCH_PROTOCOL.md`, `docs/DATA_CATALOG.md`, and `docs/SYSTEM_ARCHITECTURE.md` before implementing. Scientific fidelity and reproducibility outrank visual polish.

## Goal

Implement the **smallest genuinely functional MVP** for the Tavan Tolgoi Coal Mining Dust Research Platform. It must use **real Google Earth Engine data** through a secured backend, not synthetic/random mock values presented as observations.

## Technical stack

- Frontend: React + TypeScript + Vite; MapLibre GL JS (or Leaflet if robust EE XYZ tiles are simpler), responsive clean dark map UI; accessible legends and date controls; concise charts.
- Backend: Python FastAPI; `earthengine-api`; Google Cloud project ID from environment; ADC-based Cloud Run identity for production; local `ee.Authenticate()` for authenticated development.
- Earth Engine first data product: `MODIS/061/MCD19A2_GRANULES`, `Optical_Depth_055`, `AOD_QA`; second: `ECMWF/ERA5_LAND/HOURLY` for 10 m wind u/v.
- Repo: separate `web/` and `api/`, typed API responses, CI checks, `.env.example` not secrets, documentation.

## Critical scientific constraints

1. Apply MAIAC AOD scale **0.001**, and implement documented `AOD_QA` bits (initial strict mask clear=1, land=0, best AOD quality=0). Include valid-pixel observation counts and missing/invalid detection.
2. Identify AOD in graphics as **dimensionless aerosol optical depth at 550 nm**. Never call AOD PM10, real-time dust emission, or dust attributable exclusively to the mine.
3. Preserve source native pixel size; display zoom is not sensor resolution. Warn that site-scale winds are unresolved by ERA5-Land grid.
4. Accept verified ROI polygon input or an explicitly labeled manual-drawn demonstration polygon, not invented mine boundaries. Make it easy to replace with authoritative GeoJSON later.
5. Use exact source collection IDs and full documented provenance; include source citation and access/update time.
6. Only show **Dispersion Model** or **Mine Contribution** after real independent modeling and validation exist; otherwise label as 'Not yet available'. No invented plume animations or interpolated values.
7. Note 2026 noncommercial Earth Engine compute quota, and implement basic caching, bounded AOIs, date/window limits, and informative errors.
8. Keep Google service account credentials server-side only; prefer Cloud Run ADC / identity; never commit JSON keys.

## MVP pages and behavior

- Map Explorer: verified ROI boundary selector, satellite basemap, show/hide QA-filtered MAIAC AOD mean layer, valid-count layer, legend, selected date/month, and provenance/quality drawer.
- Charts: monthly AOD summary with valid retrieval counts; CSV export with dataset ID, units, date interval, masks, sample counts; explicit 'no data' handling.
- Meteorology: for selected hour/day show wind speed and 'from'/'toward' distinction from ERA5-Land u/v, with units and native grid warnings.
- Methodology & limitations: static documentation generated from `docs/` and scientific limitations.

## Implementation workflow

Phase A: inspect and document actual API/data response; make Earth Engine connectivity/QA unit tests pass and produce one **verified** April 2025 layer; avoid spending effort on elaborate UI until this works.

Phase B: implement FastAPI endpoint(s) and responsive web map + one time series; show errors, provenance and valid pixel counts, not placeholders.

Phase C: add wind overlay and exports; validation, test, readme and deployment configuration.

## Definition of done

- No placeholder values are rendered as scientific measurements.
- README gives reproducible setup with an Earth Engine Cloud project, backend ADC, frontend dev instructions, run scripts, env example, and failure modes.
- Live layer and stats for one test ROI are cross-checked against the GEE Code Editor script `gee/maiac_smoke_test.js`; include precise acceptance instructions and screenshots in PR description.
- Lint/test/build pass; malformed/out-of-bounds requests fail safely.
- No credentials or private keys in repository or browser code.
- Clearly explain which scientific features are not implemented and avoid overstating accuracy or attribution.

**Delivery requirement:** Make code changes on a feature branch and propose a pull request. Do not deploy a public site or modify `main` before review. At each phase, provide concise summary and exact reproducible test commands. If Earth Engine credentials are unavailable, implement the integration with explicit `NOT_CONFIGURED` status and keep any demo states visually labeled, not passed off as live observations.
