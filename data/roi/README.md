# Study-region boundary requirements

Provide vetted polygons (GeoJSON or GeoPackage) for mine footprint, stockpiles and haul-road corridors, if permitted. Document source organization, observation date, license, CRS, version and any manual digitization steps. A demonstration ROI drawn in the GEE Code Editor is **not** a verified mine footprint.

Recommended workflow: keep authoritative source and working AOI separate; preserve an immutable raw geometry version and a versioned derived analysis geometry. Do not publish restricted coordinates or mine operating information without permission.

## Server-side ROI registry (used by the API)

The backend lists every `*.geojson` file in `ROI_DIR` (default `data/roi/`) at `GET /api/rois`.
Each file must contain **one GeoJSON Feature** with a Polygon or MultiPolygon in WGS84 lon/lat:

```json
{
  "type": "Feature",
  "properties": {
    "id": "short-stable-id",
    "label": "Human-readable name",
    "verification_status": "verified | unverified",
    "source": "Issuing organisation, document or survey, date",
    "license": "Terms under which the geometry may be used",
    "observation_date": "YYYY-MM-DD",
    "notes": "Digitisation steps, CRS conversions, accuracy"
  },
  "geometry": { "type": "Polygon", "coordinates": ["… real coordinates from the authoritative source …"] }
}
```

- Only `verification_status: "verified"` is shown as verified. That value is a claim recorded by whoever placed the file; the server does not check it.
- Files that fail validation (outside the study box, too large, invalid geometry) are skipped and reported in `/api/rois` under `problems`.
- **Restricted geometry stays out of this public repository.** Put it in `data/roi/private/` (git-ignored) or anywhere outside the repo, and set `ROI_DIR` to that folder.
- No example mine polygon is shipped. The platform does not invent boundaries.
