# Tavan Tolgoi Dust Research Platform

**Status:** research prototype on branch `feature/maiac-mvp`, processing method **`maiac-aod550/0.2.0`**. It is **not publicly deployed** and has **not yet been run against live Earth Engine**. No parity pass, no measured mining-dust concentration and no validated mine attribution are claimed.

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
| Data | MODIS MAIAC `MODIS/061/MCD19A2_GRANULES`, `Optical_Depth_055` × 0.001 (no clamping). Primary variant `product_range`: core `AOD_QA` (clear + land + best quality), documented-value guard, product valid range −0.1..8.0. Sensitivity variants `nonnegative_sensitivity` (0..8.0) and `adjacency_clear_sensitivity` (adjacency bits 5–7 = 0), computed in the same pass | ERA5-Land, Sentinel-2, Sentinel-5P, MERRA-2 (catalogued; endpoints return 501) |
| Map | Primary-variant period-mean AOD layer (colour range −0.10..1.00, negatives shown), valid-observation count layer, grey "no valid retrieval" layer, ROI outline, legends from the API, nearest-neighbour pixels | Sensitivity-variant map layers, pixel inspector, wind overlay |
| Statistics | Per variant: mean of per-pixel period means (`roi_mean_aod`), pooled retrieval mean (separate statistic), coverage, valid days, valid retrievals, granule counts, pixel-sum vs granule-sum consistency check; QA retention and `qa_guard_rejections`; sensitivity differences vs primary | Uncertainty intervals, trends, upwind/downwind tests |
| Time series | Monthly series (≤36 months): chart with a variant selector that labels sensitivity views, table, long-format CSV (one row per month × variant) with definitions in the header | Seasonal comparisons |
| ROI | Server registry (`ROI_DIR`), GeoJSON upload, hand-drawn **demonstration** rectangle, each labelled by its declared status | Any built-in mine boundary (deliberately none) |
| Safety | Credentials only on the backend; EE tiles proxied (no EE URLs in the browser); bounded ROI/period/series; caching; typed errors; `NOT_CONFIGURED` state. Public-mode hooks behind `APP_MODE=public`: IAP JWT authentication, principal allowlist, per-principal rate limits, compute concurrency/queue limit, streamed body-size limit, principal-bound tile tokens, minimal health disclosure | A reviewed public deployment (see `docs/DEPLOYMENT_CHECKLIST.md`) |
| Science modules | — | Dispersion model, mine contribution, PM estimates: shown as "Not yet available" |

## Repository layout

```text
tavantolgoi-dust-research/
├── README.md · CLAUDE.md · .env.example · .gitignore
├── .github/workflows/ci.yml      # lint, tests, build, secret guard — no deploy job
├── api/                          # FastAPI + Earth Engine backend (Python ≥3.11)
│   ├── app/
│   │   ├── main.py               # routes: health, datasets, methods, rois, layers, stats, tiles
│   │   ├── datasets/maiac_method.json  # CANONICAL method v0.2.0: QA fields, variants, rules, definitions
│   │   ├── datasets/maiac_spec.py      # loads the JSON; pure-Python reference rules
│   │   ├── datasets/maiac_reference.py # executable reference of every period statistic (offline)
│   │   ├── datasets/maiac_ee.py        # Earth Engine implementation (mirrored by gee/maiac_parity_check.js)
│   │   ├── datasets/maiac_service.py   # validation → cache → engine → summary + sensitivity + provenance
│   │   ├── datasets/maiac_acceptance.py# parity comparison rule (exact counts, mean tolerance)
│   │   ├── datasets/registry.py        # dataset catalog (MAIAC implemented, others planned)
│   │   ├── security.py                 # public-mode auth, rate/concurrency limits, body limit
│   │   ├── roi.py · periods.py · tiles.py · provenance.py · csv_export.py · ee_runtime.py
│   ├── scripts/generate_method_artifacts.py  # writes parity-script METHOD block, truth table, protocol section
│   ├── scripts/parity_report.py    # CLI: backend engine output for one ROI + month
│   ├── tests/                      # truth tables, fake-EE parity, reference stats, API, security, acceptance
│   └── Dockerfile                # prepared for private Cloud Run; NOT deployed
├── web/                          # React + TypeScript + Vite + MapLibre GL dashboard
├── gee/
│   ├── maiac_smoke_test.js       # LEGACY exploratory script (different grid/weighting/range) — not acceptance
│   ├── maiac_parity_check.js     # ACCEPTANCE parity script; mirrors the backend; generated METHOD block
│   └── tests/                    # Node test of the parity script vs the shared truth table
├── docs/                         # protocol (generated method section), catalog, architecture, roadmap,
│                                 # ADDING_A_DATASET.md, DEPLOYMENT_CHECKLIST.md
├── data/                         # metadata only; ROI registry format in data/roi/README.md
└── tests/test_repository_contract.py   # starter static contract tests
```

## Setup

### Option A — private GitHub Codespace (runs the whole site in GitHub's cloud)

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/Plasma742/tavantolgoi-dust-research-/tree/feature/maiac-mvp)

1. Open the link (sign in to GitHub) and click **Create codespace**. Dependencies install automatically.
2. In the Codespace terminal, run `bash .devcontainer/start.sh`. Enter your Earth Engine project ID, follow the sign-in link, and paste the code back.
3. The dashboard opens through Codespaces' **private** port forwarding, which only your GitHub account can open. Never set the port to Public; that would be a public URL before review. Details: `.devcontainer/CODESPACE.md`.

### Option B — your own computer


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
node --test "gee/tests/*.test.mjs"                               # parity script vs shared truth table
cd api && python -m scripts.generate_method_artifacts --check    # generated artifacts in sync
ruff check . && ruff format --check . && python -m pytest
cd ../web && npm run lint && npm run typecheck && npm test && npm run build
```

These are software checks. They do **not** validate the AOD product scientifically and are **not** Earth Engine parity evidence; that requires the live acceptance workflow below.

### Changing the method

Edit `api/app/datasets/maiac_method.json`, bump `method_version`, then run `python -m scripts.generate_method_artifacts` from `api/`. It rewrites the parity script's METHOD block, the shared truth table and the protocol section; the tests fail if any of them is stale.

## Acceptance: live Earth Engine parity (required before review; not done yet)

Parity evidence shows that the backend reproduces the Code Editor computation for one ROI and month. It is **not** scientific validation of the AOD product, the QA choices or any attribution.

1. Use a **verified** ROI in registry format (`data/roi/README.md`, `verification_status: "verified"`). Without one, a demonstration ROI can be used with `ACCEPTANCE_ALLOW_UNVERIFIED_ROI=1`, and the evidence then says "demonstration ROI".
2. In the [Code Editor](https://code.earthengine.google.com/), paste `gee/maiac_parity_check.js`. Set `roiGeoJson` to the ROI's `geometry`, and the period to `2025-04-01` .. `2025-05-01`. Run it, then save the single line printed after **PARITY JSON** to a file, for example `code_editor_2025-04.json`.
3. From `api/` (Earth Engine authenticated):
   ```bash
   RUN_EE_ACCEPTANCE=1 EE_PROJECT_ID=<project> \
   ACCEPTANCE_ROI_GEOJSON=<roi.geojson> ACCEPTANCE_CODE_EDITOR_JSON=code_editor_2025-04.json \
   python -m pytest tests/test_ee_acceptance.py -s
   ```
   On Windows PowerShell, set each variable with `$env:NAME="value"` first.
4. Rule (from `maiac_method.json`): every integer field matches **exactly** for every variant, and both means agree within an absolute tolerance of 1e-9. The test writes an evidence record (PASS/FAIL, both outputs, ROI sha256, method version) to `api/.acceptance_evidence/`. That folder is git-ignored because it contains the geometry; attach the record to the PR deliberately.
5. Optional: `python -m scripts.parity_report --roi <roi.geojson> --month 2025-04` prints the backend output in the same JSON shape.

`gee/maiac_smoke_test.js` is a **legacy exploratory** script with a different grid, weighting and range. Its numbers are expected to differ, and it is not an acceptance check.

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
| `401 UNAUTHENTICATED` / `403 FORBIDDEN` | Public mode only: missing/invalid IAP assertion, or the account is not in `AUTHORIZED_PRINCIPALS`. |
| `429 RATE_LIMITED` / `503 SERVER_BUSY` | Per-principal request rate or compute concurrency limit reached. Retry shortly. |
| `413 PAYLOAD_TOO_LARGE` | Request body over `MAX_REQUEST_BYTES` (ROI too detailed). |
| QA guard rejections > 0 | Retrievals passed core QA but carried undocumented or reserved AOD_QA values; they were excluded. Report them to the methodology review. |
| Internal check FAILED | Pixel-sum and per-granule counts disagree. Do not use the numbers; report it. |

## Method decisions in `maiac-aod550/0.2.0` (from the methodology review)

1. Small negative AOD is **kept** in the primary series (product valid range raw −100..8000 → AOD −0.1..8.0). It is never clamped to 0. The non-negative screen is the separate sensitivity variant `nonnegative_sensitivity`.
2. The adjacency mask (bits 5–7) is decoded. Filtering on adjacency = 0 is the sensitivity variant `adjacency_clear_sensitivity`, not the primary.
3. Undocumented or reserved AOD_QA values (adjacency 6–7, aerosol model 3, reserved bit 15 = 1) are rejected and counted as `qa_guard_rejections`, never silently accepted.
4. There is one canonical spatial rule: native sinusoidal grid, pixel centre in ROI, unweighted reducers for pixel sums and per-granule counts alike.
5. `roi_mean_aod` is the unweighted mean of per-pixel period means. `roi_pooled_retrieval_mean_aod` is a separately named pooled statistic.

## Reference documentation

- MAIAC MCD19A2.061: https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD19A2_GRANULES (DOI 10.5067/MODIS/MCD19A2.061)
- Sentinel-2 L2A: https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED
- Sentinel-5P Aerosol Index: https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_OFFL_L3_AER_AI
- ERA5-Land hourly: https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_HOURLY
- MERRA-2 aerosol: https://developers.google.com/earth-engine/datasets/catalog/NASA_GSFC_MERRA_aer_2
- Earth Engine noncommercial tiers: https://developers.google.com/earth-engine/guides/noncommercial_tiers
- Earth Engine service account auth: https://developers.google.com/earth-engine/guides/service_account

**Deployment:** none. Do not deploy publicly before review. Work through `docs/DEPLOYMENT_CHECKLIST.md` first. A private GitHub repository alone does not make a hosted site private.
