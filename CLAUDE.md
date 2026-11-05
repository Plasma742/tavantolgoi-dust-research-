# Claude Development Instructions — Tavan Tolgoi Dust Research

Start by reading, in order:
1. `README.md`
2. `docs/RESEARCH_PROTOCOL.md`
3. `docs/DATA_CATALOG.md`
4. `docs/SYSTEM_ARCHITECTURE.md`
5. `docs/CLAUDE_BUILD_BRIEF.md`
6. `docs/IMPLEMENTATION_ROADMAP.md`

## Working agreement

- This is a scientific research project. Do not manufacture observations, live EE outputs, source geometries, or model validation.
- Clearly distinguish *observed AOD*, *meteorological model/reanalysis fields*, *statistical attribution*, and *dust dispersion simulation*.
- Implement the **first real-data milestone** (QA-filtered April 2025 MAIAC 550 nm AOD) before a visually elaborate site.
- No public deployment or automatic changes to `main` without human review. Work on a feature branch and send a pull request.
- Never commit passwords, Google Cloud keys, or Earth Engine credentials. Keep EE access on the backend.
- Declare `NOT_CONFIGURED` if cloud credentials or verified ROI are missing. Fake values must never masquerade as science.
- Prefer code, tests, clear provenance and reproducible methods over cosmetic UI claims.
- Follow dataset-native resolution and quality flags; do not derive PM10 directly from AOD.
- Each new analytic output must have a test case and a metadata/provenance record.
- Before proposing a PR, show lint/build/test results and manual Earth Engine parity-check instructions.

**First deliverable:** a working, authenticated, testable GEE-backed AOD layer and valid-observation-count layer for a user-approved ROI, plus a small React/TypeScript map and method panel. Do not imply that this is a validated mining-emissions map.
