# Adding a dataset adapter (ERA5-Land, Sentinel-2, Sentinel-5P, MERRA-2)

The API and web client are already shaped for more datasets. Today only
`maiac_aod550` is implemented; the others are listed by `GET /api/datasets` with
`status: "planned"`, and their endpoints answer **501 NOT_IMPLEMENTED**. Nothing is drawn
for them in the UI.

## Extension points

| Piece | File | What to add |
| --- | --- | --- |
| Catalog entry | `api/app/datasets/registry.py` | Re-verify bands, units, grid and cadence against the Earth Engine catalog; set `status: "implemented"` only when the adapter, tests and provenance exist. |
| Pure spec | `api/app/datasets/<name>_spec.py` | Constants, QA/cloud rules, units, method text and visualisation, with no `ee` import, so tests can check them offline. |
| Earth Engine engine | `api/app/datasets/<name>_ee.py` | Server-side images and reductions that take every constant from the spec module. |
| Service | `api/app/datasets/<name>_service.py` | Validation, caching, explicit empty states and provenance. Follow `maiac_service.py`. |
| Routes | `api/app/main.py` | Dispatch `POST /api/layers/{key}` and `/api/stats/{key}/...` to the new service. |
| Parity script | `gee/<name>_parity_check.js` | A Code Editor mirror of the backend computation. |
| Tests | `api/tests/` | Spec tests (offline), API tests with a fake engine, and an opt-in live test. |
| UI | `web/src/` | Legend and provenance come from the API; label the observation type (observation, reanalysis or model). |

## Dataset-specific requirements (from the research protocol)

**ERA5-Land (`ECMWF/ERA5_LAND/HOURLY`)** is a reanalysis, not an observation.
- Speed = sqrt(u² + v²) in m/s.
- Direction must state its convention. Meteorological "from" direction = atan2(−u, −v) in degrees, mod 360. "Toward" direction = atan2(u, v) in degrees, mod 360. Show both labels explicitly.
- Pair winds with the MAIAC overpass hour rather than daily or monthly means where feasible. Warn that the ~11 km grid does not resolve mine-scale flow.

**Sentinel-2 SR (`COPERNICUS/S2_SR_HARMONIZED`)** provides surface context only (pits, stockpiles, haul roads).
- Document the cloud-mask choice; Cloud Score+ is one option that needs review.
- Never present Sentinel-2 as an aerosol or dust-concentration product, and never use it to "sharpen" 1 km AOD.

**Sentinel-5P AAI (`COPERNICUS/S5P/OFFL/L3_AER_AI`)** is a regional dust/smoke indicator. It is dimensionless and is not PM. The 1,113.2 m Earth Engine L3 grid is finer than the native footprint; say so.

**MERRA-2 (`NASA/GSFC/MERRA/aer/2`)** is a coarse aerosol reanalysis (~50–70 km), used for the regional background and dust-event screening (protocol RQ3). It does not provide local concentrations.

## Not datasets: modules that stay "Not yet available"

These require independent modelling and validation first:
- Dispersion model
- Mine contribution / attribution
- PM10/PM2.5 estimates

Do not add plume animations, interpolated surfaces or AOD→PM conversions as placeholders.
