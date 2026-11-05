# Tavan Tolgoi Dust Research Platform

**Status:** research prototype on branch `feature/maiac-mvp`. It is **not publicly deployed** and has not yet been run against live Earth Engine in this environment. No measured mining-dust concentration and no validated mine attribution are claimed.

**Монгол нэр:** Тавантолгойн уурхайн тоосжилтын орон зай, цаг хугацааны тархалтын судалгаа

**English working title:** *Spatiotemporal Assessment of Dust Dispersion from the Tavan Tolgoi Coal Mining Complex, Mongolia, Using Multi-Source Satellite Observations and Meteorological Data*

## Project purpose

Develop a reproducible web-based research platform to (1) explore aerosol observations, (2) analyse wind and land-surface context, (3) test mine-vs-natural-dust attribution, and (4) eventually incorporate independently validated dust-transport modelling. **Observations**, **model outputs** and **statistical attribution** are kept distinct in both the UI and published results.

## Scientific principles

- **AOD is column-integrated aerosol optical depth**, not surface PM10 or mine-generated PM10.
- Sentinel-2 10 m land imagery cannot make 1 km MAIAC AOD a genuine 10 m aerosol observation.
- Sentinel-5P AAI is useful for regional dust episodes, not for source-specific PM concentration.
- ERA5-Land (~11 km) winds and MERRA-2 (~50–70 km) diagnostics do not resolve mine-scale plumes.
- Missing and invalid pixels stay visible. There is no silent interpolation, unsupported precision or arbitrary attribution.
- Every map and export reports the dataset ID, bands, native pixel size, temporal support, quality filter, sample count, units, processing version and provenance.

## What this branch implements

| Area | Implemented | Not implemented (labelled "planned" / "not yet available") |
| --- | --- | --- |
| Data | MODIS MAIAC `MODIS/061/MCD19A2_GRANULES`, `Optical_Depth_055` × 0.001, strict `AOD_QA` mask (clear + land + best quality), physical screen 0–8 | ERA5-Land, Sentinel-2, Sentinel-5P, MERRA-2 (catalogued; endpoints return 501) |
| Map | Period-mean AOD layer, valid-observation count layer, grey "no valid retrieval" layer, ROI outline, legends from the API, nearest-neighbour pixels | Pixel inspector, wind overlay |
| Statistics | Per-period ROI mean AOD, coverage, valid days, valid retrievals, QA retention, granule counts, internal consistency check | Uncertainty intervals, trends, upwind/downwind tests |
| Time series | Monthly series (≤36 months) chart, table and CSV with a provenance header | Seasonal comparisons |
| ROI | Server registry (`ROI_DIR`), GeoJSON upload, hand-drawn **demonstration** rectangle, each labelled by its declared status | Any built-in mine boundary (deliberately none) |
| Safety | Credentials only on the backend, Earth Engine tiles proxied (no EE URLs in the browser), bounded ROI/period/series, caching, typed errors, `NOT_CONFIGURED` state | App-level user auth (use Cloud Run IAM/IAP when deploying privately) |
| Science modules | — | Dispersion model, mine contribution, PM estimates: shown as "Not yet available" |

## Repository layout

```text
tavantolgoi-dust-research/
├── README.md · CLAUDE.md · .env.example · .gitignore
├── .github/workflows/ci.yml      # lint, tests, build, secret guard — no deploy job
├── api/                          # FastAPI + Earth Engine backend (Python ≥3.11)
│   ├── app/
│   │   ├── main.py               # routes: health, datasets, methods, rois, layers, stats, tiles
│   │   ├── datasets/maiac_spec.py    # single source of truth: scale, QA bits, palettes, method text
│   │   ├── datasets/maiac_ee.py      # Earth Engine implementation (mirrored by gee/maiac_parity_check.js)
│   │   ├── datasets/maiac_service.py # validation → cache → engine → summary + provenance
│   │   ├── datasets/registry.py      # dataset catalog (MAIAC implemented, others planned)
│   │   ├── roi.py · periods.py · tiles.py · provenance.py · csv_export.py · ee_runtime.py
│   ├── scripts/parity_report.py  # CLI: backend numbers for one ROI + month
│   ├── tests/                    # spec, ROI/period, API (fake engine), opt-in live EE test
│   └── Dockerfile                # prepared for private Cloud Run; NOT deployed
├── web/                          # React + TypeScript + Vite + MapLibre GL dashboard
├── gee/
│   ├── maiac_smoke_test.js       # original Code Editor baseline (unchanged)
│   └── maiac_parity_check.js     # exact mirror of the backend for cross-checks
├── docs/                         # protocol, catalog, architecture, roadmap, ADDING_A_DATASET.md
├── data/                         # metadata only; ROI registry format in data/roi/README.md
└── tests/test_repository_contract.py   # starter static contract tests
```

## Setup

### 1. Earth Engine project (one time)

1. Create or choose a Google Cloud project. Register it for **noncommercial** Earth Engine use and pick a quota tier (Community = 150 EECU-hours per month). Enable the **Earth Engine API**.
2. Install the Google Cloud CLI, then authenticate **on the machine that runs the backend**. Do either of the following:
   ```bash
   earthengine authenticate                                 # EE_AUTH_MODE=persistent (default)
   # or
   gcloud auth application-default login \
     --scopes=https://www.googleapis.com/auth/earthengine,https://www.googleapis.com/auth/cloud-platform
   # then set EE_AUTH_MODE=adc
   ```
   Never download service-account JSON keys into this repository. For a future Cloud Run deployment, use the service identity (`EE_AUTH_MODE=adc`) with least-privilege IAM.

### 2. Backend

```bash
cd api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example .env          # then set EE_PROJECT_ID=<your-project-id>
uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file .env
# check:  curl "http://127.0.0.1:8000/api/health?check_earth_engine=true"
# docs:   http://127.0.0.1:8000/api/docs
```

Without `EE_PROJECT_ID` the API runs in **NOT_CONFIGURED** mode. Health, catalog and method endpoints work; data endpoints return `503 NOT_CONFIGURED`. No placeholder values are produced.

### 3. Frontend

```bash
cd web
npm ci
npm run dev                      # http://127.0.0.1:5173 (proxies /api → 127.0.0.1:8000)
```

`web/.env.example` lists the only frontend settings: the API base and the basemap URL. All are public, build-time values. The default basemap is Esri World Imagery; check its terms before any deployment.

### 4. Checks (all must pass before a PR)

```bash
python3 -m unittest discover -s tests -p "test_*.py"             # starter contract (repo root)
node --check gee/maiac_smoke_test.js && node --check gee/maiac_parity_check.js
cd api && ruff check . && ruff format --check . && python -m pytest
cd ../web && npm run lint && npm run typecheck && npm test && npm run build
```

These checks do **not** validate Earth Engine output scientifically. That is what the parity check is for.

## Acceptance: Earth Engine parity check (manual, required before review)

1. Choose the ROI. Ideally it is a verified polygon in `ROI_DIR`; otherwise draw a demonstration rectangle. Use **Download ROI GeoJSON** in the Study area panel to save the exact geometry the backend received.
2. In the dashboard, load **April 2025**. Note the period summary and the ROI `sha256` in the provenance drawer.
3. Run `python -m scripts.parity_report --roi <file> --month 2025-04` from `api/`. It prints the same numbers from the CLI.
4. Paste the same GeoJSON into `gee/maiac_parity_check.js` in the [Code Editor](https://code.earthengine.google.com/) and run it.
5. **Integer counts** (granules, valid days, pixels, retrievals) must match exactly. **`roi_mean_aod`** must match to floating-point precision. `consistency_check_passed` must be `true`.
6. Compare the map visually with the Code Editor layers (same palettes). Attach screenshots and both printed outputs to the PR.
7. Optional: `gee/maiac_smoke_test.js` uses a weighted mean at `scale: 1000` in EPSG:4326, so small differences from the backend mean are expected. Record them; do not tune to match.

Opt-in live test: `RUN_EE_INTEGRATION=1 EE_PROJECT_ID=… TEST_ROI_GEOJSON=… python -m pytest tests/test_ee_integration.py -s` (from `api/`).

## Failure modes

| Symptom | Meaning / action |
| --- | --- |
| Pill shows `NOT_CONFIGURED` | `EE_PROJECT_ID` is empty. Set it in `api/.env` and restart. |
| `AUTH_ERROR` / `EE_UNAVAILABLE` | Credentials missing or project not registered for Earth Engine. Re-run authentication; check the project's EE registration. The backend retries after 60 s. |
| `400 INVALID_ROI` | Geometry is invalid, outside `ALLOWED_BBOX`, larger than `MAX_ROI_AREA_KM2`, or has too many vertices. |
| `400 INVALID_PERIOD` | The period is reversed, longer than the limit, before 2000-02-24, or not yet ended (partial periods are refused). |
| `NO_GRANULES` | No granule intersects the ROI and period. This is missing data, not zero aerosol. |
| `NO_VALID_OBSERVATIONS` | Granules exist but nothing passed QA (cloud, snow, low quality). Grey pixels show where. |
| `429 EE_QUOTA` / `504 EE_TIMEOUT` | Earth Engine quota/concurrency or time limit. Shrink the ROI or range, or wait. Quota resets monthly. |
| Map notice "tiles expired" (`410 TILE_EXPIRED`) | Layer older than ~60 min. Load it again. |
| Internal check FAILED | Pixel-sum and per-granule counts disagree. Do not use the numbers; report it. |

## Open methodology questions (flagged for scientific review, not changed)

1. The physical screen `0 ≤ AOD ≤ 8` (from the smoke test) drops valid small negative retrievals (the product range starts at −0.1). This can bias clean-air means upward.
2. The strict QA rule does not use the adjacency mask (bits 5–7).
3. The smoke test's ROI mean uses a different grid and weighting from the backend (see the acceptance check above).

## Reference documentation

- MAIAC MCD19A2.061: https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD19A2_GRANULES (DOI 10.5067/MODIS/MCD19A2.061)
- Sentinel-2 L2A: https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED
- Sentinel-5P Aerosol Index: https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_OFFL_L3_AER_AI
- ERA5-Land hourly: https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_HOURLY
- MERRA-2 aerosol: https://developers.google.com/earth-engine/datasets/catalog/NASA_GSFC_MERRA_aer_2
- Earth Engine noncommercial tiers: https://developers.google.com/earth-engine/guides/noncommercial_tiers
- Earth Engine service account auth: https://developers.google.com/earth-engine/guides/service_account

**Deployment:** none. Do not deploy publicly before review. A private deployment needs authenticated access (for example Cloud Run with IAM or IAP); a private GitHub repository alone does not make a hosted site private.
