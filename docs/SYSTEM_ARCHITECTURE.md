# Proposed web / API architecture

```text
Browser (React + TypeScript + MapLibre, charts)
    | HTTPS JSON / imagery tile requests
    v
Backend (Python FastAPI on Cloud Run)
    | user inputs, validation, caching, rate limits
    | service identity / Google application default credentials
    v
Google Earth Engine Python API + Cloud project
    |-- MODIS MAIAC AOD
    |-- Sentinel-2 SR
    |-- ERA5-Land hourly
    |-- Sentinel-5P AAI
    |-- MERRA-2 aerosol
    +--> derived tiles, trend summaries, QA/coverage metadata

Optional precomputed cache: Cloud Storage / COG / GeoJSON
Research reproducibility: GitHub source code + metadata and exported tables
```

## Secrets and deployment

- The website frontend **must not hold service account JSON keys**, tokens or admin credentials. No credentials committed to GitHub.
- For Cloud Run, prefer application default credentials / workload identity. Configure least-privilege IAM permissions and verify Earth Engine Cloud Project registration.
- A truly private project must have authenticated access restrictions; a GitHub private repo alone does not make a separately hosted site private.
- Use `.env.example` with placeholders only; use managed cloud secrets and per-environment configuration.
- Quota-aware caching and request throttling: as of Apr 2026, Earth Engine noncommercial usage has monthly EECU-hour tiers; avoid recomputing global/annual rasters on every pan.
- For publication-ready maps, precompute reproducible aggregates; do not rely exclusively on transient live tile URLs.

## Minimum web pages

1. **Research Map** — verified AOI, base satellite image, QA-filtered MAIAC layer, valid observations layer, legends, uncertainty/metadata panel.
2. **Time Series** — choose ROI and months, plot mean/median AOD and valid-day counts; export CSV with provenance.
3. **Meteorology** — 10 m wind vector/seasonal rose (ERA5-Land), wind-aligned regions, caveat for ~11 km winds.
4. **Data & Methods** — complete source catalog, scaling, QA, references, and clear observed-vs-modeled labels.
5. **Future research modules (not MVP)** — source attribution, PM ground validation, dispersion model, publication dashboard.

## Proposed API contract (adapt only after scientific tests)

- `GET /api/health`: backend service status
- `GET /api/datasets`: names, units, native resolution, updates, limits
- `POST /api/layers/maiac`: bounded ROI + date window -> safe short-lived tile metadata + provenance
- `POST /api/stats/maiac/monthly`: bounded ROI + date window -> monthly AOD and valid sample counts
- `POST /api/met/wind`: bounded ROI + selected timestamp -> wind vectors + provenance
- `GET /api/methods`: public documentation or version info

Every request should validate ROI size, date limits, allowed collections, user authorization (if private), expected results, compute quota and error handling. Return meaningful 'no observations' rather than fabricating an image.

## Example metadata payload

```json
{
  "dataset_id": "MODIS/061/MCD19A2_GRANULES",
  "band": "Optical_Depth_055",
  "display_name": "AOD at 550 nm",
  "units": "dimensionless",
  "scale_factor": 0.001,
  "native_pixel_size_m": 1000,
  "qa_rule": "clear + land + best AOD QA",
  "period_start": "2025-04-01",
  "period_end_exclusive": "2025-05-01",
  "type": "satellite_observation",
  "not_a_measurement_of": ["PM10", "mine-only dust"],
  "status": "example_schema_not_observed_data"
}
```

## Technical release criteria

- Deployment runs with valid backend identity and Earth Engine permissions (not a static mock).
- One real AOD layer renders and is compared pixel-wise/summarized against Earth Engine Code Editor baseline.
- Map date selection affects both rendered tiles and statistics.
- Cloud/QA masking is documented and observation-count metadata is displayed.
- A no-data query returns an informative empty state.
- Credentials absent from frontend bundles, logs and repository.
- README has repeatable local run and production deployment steps.
