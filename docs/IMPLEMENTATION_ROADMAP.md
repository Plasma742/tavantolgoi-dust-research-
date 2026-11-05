# Implementation roadmap and acceptance gates

## Gate 0 — Research foundation (this starter)

- [x] Draft protocol, first dataset catalog, scientific limitations and architecture present.
- [x] GEE Code Editor smoke-test script drafted for user-drawn ROI.
- [ ] Scientific team approves scope, processing windows, comparison-area strategy and authoritative geometry.
- [ ] Earth Engine project registered and API enabled.

## Gate 1 — Live MAIAC research map (first engineering priority)

> Status 2026-11-04: code for every Gate 1 item exists on `feature/maiac-mvp` (method `maiac-aod550/0.2.0`) and passes offline tests, but **no item is checked** — none has been run against live Earth Engine yet. Check items only with the parity evidence described in README › Acceptance.

- [ ] Run `gee/maiac_smoke_test.js` in Code Editor with explicit, verified ROI and save processing log.
- [ ] Implement backend startup/health response, safe Google Earth Engine authentication and bounded AOI/date validation.
- [ ] Serve April 2025 QA-filtered AOD 550 nm map tiles and *granule-level* valid observation counts.
- [ ] Display provenance, sample count, QA rule, units, missing-data areas and correct native spatial resolution.
- [ ] Frontend map, date range selector, real error/no-data states and no exposed credentials.
- [ ] Cross-check at least one map, area mean and count against GEE Code Editor result.

## Gate 2 — Time-series and meteorological context

- [ ] Monthly and seasonal AOD series 2018–2025 with quality and data-coverage reporting.
- [ ] ERA5-Land u/v wind with explicit temporal pairing and *from* vs *towards* wind direction.
- [ ] Selectable zones and CSV/GeoJSON export with source metadata, code version and date range.
- [ ] Add tests for masked pixels, zero observation cases and different temporal coverage.

## Gate 3 — Scientific inference (not a first-MVP claim)

- [ ] Verify mines, stockpiles, haul roads and matched upwind/control polygons.
- [ ] Treat regional dust storms and natural sources as confounders; sensitivity analyses.
- [ ] Statistical upwind/downwind comparisons with uncertainty intervals.
- [ ] External PM observations/operations logs/dispersion model if verifiably available.
- [ ] Independent validation and peer-review-ready reproduction package.

## Gate 4 — Publication-quality delivery

- [ ] Re-run reproducible figures and statistical tables from pinned scripts and dataset versions.
- [ ] Include independent validation or carefully limited claims when unavailable.
- [ ] Confirm data rights, citations, ethics, licensing and security; avoid publication before review.

## Acceptance rules

No checkmark without actual logs, screenshots, output metadata or reviewed test evidence. A polished screenshot is not evidence of scientifically correct data. AOD is not ground-level PM10 and an AOD anomaly is not automatically mine-origin dust.
