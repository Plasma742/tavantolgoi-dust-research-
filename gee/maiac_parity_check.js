/**
 * MAIAC MCD19A2.061 AOD 550 nm - ACCEPTANCE PARITY CHECK for the FastAPI backend.
 *
 * Mirrors api/app/datasets/maiac_ee.py function for function. All method constants live in
 * the GENERATED METHOD block below, written from api/app/datasets/maiac_method.json by
 *   cd api && python -m scripts.generate_method_artifacts
 * (tests fail if this block drifts from the canonical JSON).
 *
 * How to use (Earth Engine Code Editor, https://code.earthengine.google.com/):
 *   1. Paste the SAME GeoJSON geometry the backend received as `roiGeoJson`
 *      (dashboard: Study area -> Download ROI GeoJSON; use its "geometry").
 *   2. Set `start` / `endExclusive` (acceptance month: 2025-04-01 .. 2025-05-01).
 *   3. Run. Copy the single line printed after "PARITY JSON" into a file and pass it to
 *      api/tests/test_ee_acceptance.py (see README > Acceptance).
 *
 * gee/maiac_smoke_test.js is a LEGACY EXPLORATORY script (different grid, weighting and
 * range); it is not an acceptance check. This script attributes nothing to mining.
 */

// ---- inputs ------------------------------------------------------------------------
var roiGeoJson = {
  // Replace with your ROI (WGS84 lon/lat). This placeholder ring is NOT a mine boundary.
  type: 'Polygon',
  coordinates: [[[105.30, 43.50], [105.70, 43.50], [105.70, 43.80], [105.30, 43.80], [105.30, 43.50]]]
};
var start = '2025-04-01';
var endExclusive = '2025-05-01';

// BEGIN GENERATED METHOD - do not edit by hand
var METHOD = {
  "method_version": "maiac-aod550/0.2.0",
  "dataset": {
    "key": "maiac_aod550",
    "collection_id": "MODIS/061/MCD19A2_GRANULES",
    "title": "MCD19A2.061 Terra & Aqua MAIAC Land Aerosol Optical Depth Daily 1 km",
    "aod_band": "Optical_Depth_055",
    "qa_band": "AOD_QA",
    "derived_band": "AOD_550",
    "scale_factor": 0.001,
    "offset": 0.0,
    "unit": "dimensionless",
    "quantity": "Aerosol optical depth at 550 nm (column-integrated, atmosphere total)",
    "product_valid_raw_range": [
      -100,
      8000
    ],
    "catalog_pixel_size_m": 1000,
    "start_date": "2000-02-24",
    "catalog_url": "https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD19A2_GRANULES",
    "citation": "MODIS/Terra+Aqua Land Aerosol Optical Depth Daily L2G Global 1km SIN Grid V061 (MCD19A2.061). NASA EOSDIS Land Processes DAAC. https://doi.org/10.5067/MODIS/MCD19A2.061 - see the LP DAAC 'Citing Our Data' page for the full citation format."
  },
  "qa": {
    "fields": [
      {
        "name": "cloud_mask",
        "start_bit": 0,
        "n_bits": 3,
        "documented_values": [
          0,
          1,
          2,
          3,
          5,
          6,
          7
        ]
      },
      {
        "name": "land_water_snow_ice",
        "start_bit": 3,
        "n_bits": 2,
        "documented_values": [
          0,
          1,
          2,
          3
        ]
      },
      {
        "name": "adjacency",
        "start_bit": 5,
        "n_bits": 3,
        "documented_values": [
          0,
          1,
          2,
          3,
          4,
          5
        ]
      },
      {
        "name": "aod_quality",
        "start_bit": 8,
        "n_bits": 4,
        "documented_values": [
          0,
          1,
          3,
          4,
          5,
          6,
          7,
          8,
          9,
          10,
          11
        ]
      },
      {
        "name": "glint",
        "start_bit": 12,
        "n_bits": 1,
        "documented_values": [
          0,
          1
        ]
      },
      {
        "name": "aerosol_model",
        "start_bit": 13,
        "n_bits": 2,
        "documented_values": [
          0,
          1,
          2
        ]
      },
      {
        "name": "reserved",
        "start_bit": 15,
        "n_bits": 1,
        "documented_values": [
          0
        ]
      }
    ],
    "core_qa": {
      "name": "core_qa",
      "accept": {
        "cloud_mask": [
          1
        ],
        "land_water_snow_ice": [
          0
        ],
        "aod_quality": [
          0
        ]
      },
      "text": "AOD_QA bits 0-2 == 1 (clear) AND bits 3-4 == 0 (land) AND bits 8-11 == 0 (best quality)"
    },
    "documented_value_guard": {
      "name": "documented_value_guard",
      "fields": [
        "adjacency",
        "glint",
        "aerosol_model",
        "reserved"
      ],
      "text": "Every non-core AOD_QA field must hold a documented value: adjacency bits 5-7 in {0..5}, glint bit 12 in {0,1}, aerosol model bits 13-14 in {0,1,2}, reserved bit 15 == 0. Retrievals failing only this guard are rejected and counted as qa_guard_rejections, never silently accepted."
    },
    "adjacency_policies": {
      "any_documented": {
        "accept": null,
        "text": "Adjacency bits 5-7 are decoded but not used to filter (any documented value accepted)."
      },
      "clear_only": {
        "accept": [
          0
        ],
        "text": "Adjacency bits 5-7 == 0 (normal condition / clear) only."
      }
    }
  },
  "variants": [
    {
      "id": "product_range",
      "role": "primary",
      "label": "Primary - core QA, product valid range",
      "raw_range": [
        -100,
        8000
      ],
      "adjacency_policy": "any_documented",
      "text": "Core QA + documented-value guard; raw Optical_Depth_055 in [-100, 8000] (AOD -0.100..8.000); adjacency not filtered. No clamping: small negative AOD is kept."
    },
    {
      "id": "nonnegative_sensitivity",
      "role": "sensitivity",
      "label": "Sensitivity - non-negative AOD only",
      "raw_range": [
        0,
        8000
      ],
      "adjacency_policy": "any_documented",
      "text": "As primary, but raw Optical_Depth_055 in [0, 8000] (AOD 0.000..8.000). Negative retrievals are excluded, not set to zero."
    },
    {
      "id": "adjacency_clear_sensitivity",
      "role": "sensitivity",
      "label": "Sensitivity - cloud-adjacency clear only",
      "raw_range": [
        -100,
        8000
      ],
      "adjacency_policy": "clear_only",
      "text": "As primary, plus AOD_QA adjacency bits 5-7 == 0."
    }
  ],
  "spatial_rule": {
    "grid": "MAIAC native sinusoidal projection (taken from the collection's own Optical_Depth_055 band; no scale override)",
    "pixel_inclusion": "pixel centre inside the ROI",
    "reducers": "unweighted for every statistic (pixel sums, per-granule counts and means)",
    "roi_edges": "planar (non-geodesic) edges in EPSG:4326",
    "text": "All ROI statistics use the MAIAC native sinusoidal grid and Earth Engine unweighted reducers: a pixel is included when its centre lies inside the ROI. Pixel-level sums and per-granule counts use the identical rule."
  },
  "temporal_rule": {
    "text": "Per-pixel statistics use all QA-passing granule retrievals with system:time_start in [start, end_exclusive) (UTC). Granules are independent overpass retrievals; a valid day is a UTC calendar day with >= 1 valid retrieval anywhere in the ROI."
  },
  "statistic_definitions": {
    "pixels_total": "Number of MAIAC native-grid pixels whose centre lies inside the ROI.",
    "pixels_with_valid": "Number of ROI pixels with at least one valid retrieval in the period.",
    "coverage_fraction": "pixels_with_valid / pixels_total; null when pixels_total is 0.",
    "valid_retrievals": "Sum over ROI pixels of the per-pixel count of valid granule retrievals (pixel-level sum).",
    "valid_retrievals_granule_sum": "Sum over granules of each granule's count of valid ROI pixels (per-granule sum); must equal valid_retrievals.",
    "retrievals_before_qa": "Sum over ROI pixels of granule retrievals whose raw Optical_Depth_055 is present and inside the product valid range [-100, 8000], before any QA test.",
    "qa_retention_fraction": "valid_retrievals / retrievals_before_qa; null when retrievals_before_qa is 0.",
    "qa_guard_rejections": "Retrievals inside the product valid range that pass core QA but fail the documented-value guard (undocumented or reserved AOD_QA values).",
    "granules_intersecting": "Number of granules whose footprint intersects the ROI in the period.",
    "granules_with_valid": "Number of granules with at least one valid ROI pixel.",
    "valid_day_count": "Number of distinct UTC days with at least one valid retrieval anywhere in the ROI.",
    "roi_mean_aod": "Unweighted mean, over ROI pixels with >= 1 valid retrieval, of each pixel's period-mean AOD (mean of per-pixel period means). null when no valid retrieval.",
    "roi_pooled_retrieval_mean_aod": "Mean of all valid pixel-level retrievals pooled together (sum of AOD over every valid pixel retrieval / valid_retrievals). A different statistic from roi_mean_aod; null when no valid retrieval."
  },
  "acceptance": {
    "test_month": "2025-04",
    "integer_fields_exact": [
      "granules_intersecting",
      "pixels_total",
      "retrievals_before_qa",
      "qa_guard_rejections",
      "valid_retrievals",
      "valid_retrievals_granule_sum",
      "pixels_with_valid",
      "granules_with_valid",
      "valid_day_count"
    ],
    "mean_fields": [
      "roi_mean_aod",
      "roi_pooled_retrieval_mean_aod"
    ],
    "mean_abs_tolerance": 1e-09,
    "note": "Parity evidence shows the backend reproduces the Code Editor computation for one ROI and month. It is not scientific validation of the AOD product or of any attribution."
  }
};
// END GENERATED METHOD

var GUARD_BAND = 'guard_rejected';
var PRESENT_BAND = 'raw_present';

// ---- per-pixel rules (mirror of maiac_ee.pixel_masks) -------------------------------
function qaField(name) {
  for (var i = 0; i < METHOD.qa.fields.length; i++) {
    if (METHOD.qa.fields[i].name === name) { return METHOD.qa.fields[i]; }
  }
  throw new Error('Unknown QA field ' + name);
}

function fieldValue(qa, name) {
  var f = qaField(name);
  return qa.rightShift(f.start_bit).bitwiseAnd(Math.pow(2, f.n_bits) - 1);
}

function inValues(image, values) {
  var accepted = image.eq(values[0]);
  for (var i = 1; i < values.length; i++) { accepted = accepted.or(image.eq(values[i])); }
  return accepted;
}

function inRange(image, low, high) {
  return image.gte(low).and(image.lte(high));
}

function pixelMasks(image) {
  var ds = METHOD.dataset;
  var qa = image.select(ds.qa_band);
  var raw = image.select(ds.aod_band);
  var core = ee.Image.constant(1);
  Object.keys(METHOD.qa.core_qa.accept).forEach(function (name) {
    core = core.and(inValues(fieldValue(qa, name), METHOD.qa.core_qa.accept[name]));
  });
  var guard = ee.Image.constant(1);
  METHOD.qa.documented_value_guard.fields.forEach(function (name) {
    guard = guard.and(inValues(fieldValue(qa, name), qaField(name).documented_values));
  });
  var present = inRange(raw, ds.product_valid_raw_range[0], ds.product_valid_raw_range[1]);
  var aod = raw.multiply(ds.scale_factor).add(ds.offset);
  var out = {};
  METHOD.variants.forEach(function (v) {
    var keep = core.and(guard).and(inRange(raw, v.raw_range[0], v.raw_range[1]));
    var adjacency = METHOD.qa.adjacency_policies[v.adjacency_policy].accept;
    if (adjacency !== null) { keep = keep.and(inValues(fieldValue(qa, 'adjacency'), adjacency)); }
    out[v.id] = aod.updateMask(keep);
  });
  out[GUARD_BAND] = present.and(core).and(guard.not()).selfMask();
  out[PRESENT_BAND] = present.selfMask();
  return out;
}

function variantIds() {
  return METHOD.variants.map(function (v) { return v.id; });
}

function primaryId() {
  return METHOD.variants.filter(function (v) { return v.role === 'primary'; })[0].id;
}

function granuleBands(image) {
  var masks = pixelMasks(image);
  var bands = variantIds().map(function (id) { return masks[id].rename(id); });
  bands.push(masks[GUARD_BAND].rename(GUARD_BAND), masks[PRESENT_BAND].rename(PRESENT_BAND));
  return ee.Image(ee.Image.cat(bands).toFloat().copyProperties(image, ['system:time_start']));
}

function emptyGranule() {
  var names = variantIds().concat([GUARD_BAND, PRESENT_BAND]);
  return ee.Image.cat(names.map(function (n) { return ee.Image.constant(0).toFloat().rename(n).selfMask(); }));
}

// ---- result conversion and status (mirror of engine_output_from_ee / summarize) ---------
function toInt(v) { return Math.round(Number(v || 0)); }

function toEngineOutput(o, ids) {
  var sums = o.pixel_sums || {};
  var means = o.means || {};
  var variants = {};
  ids.forEach(function (i) {
    var pv = o.per_variant[i];
    variants[i] = {
      valid_retrievals: toInt(sums['n_' + i]),
      valid_retrievals_granule_sum: toInt(pv.granule_sum),
      pixels_with_valid: toInt(sums['has_' + i]),
      roi_mean_aod: (means['mean_' + i] === undefined) ? null : means['mean_' + i],
      aod_sum: Number(sums['sum_' + i] || 0),
      granules_with_valid: toInt(pv.granules_with_valid),
      valid_day_count: toInt(pv.valid_day_count)
    };
  });
  return {
    granules_intersecting: toInt(o.granules_intersecting),
    pixels_total: toInt(sums.roi_px),
    retrievals_before_qa: toInt(sums['n_' + PRESENT_BAND]),
    qa_guard_rejections: toInt(sums['n_' + GUARD_BAND]),
    variants: variants
  };
}

function variantStatus(engine, id) {
  var v = engine.variants[id];
  if (engine.granules_intersecting === 0) { return 'NO_GRANULES'; }
  if (engine.pixels_total === 0) { return 'NO_VALID_OBSERVATIONS'; }
  if (v.valid_retrievals === 0 || v.roi_mean_aod === null) { return 'NO_VALID_OBSERVATIONS'; }
  return 'OK';
}

// ---- Earth Engine computation ------------------------------------------------------
function main() {
  var ds = METHOD.dataset;
  var ids = variantIds();
  var roi = ee.Geometry(roiGeoJson, 'EPSG:4326', false);  // planar edges, as the backend
  var raw = ee.ImageCollection(ds.collection_id).filterBounds(roi).filterDate(start, endExclusive);
  var nRaw = raw.size();
  var bands = ee.ImageCollection(ee.Algorithms.If(nRaw.gt(0), raw.map(granuleBands),
                                                  ee.ImageCollection([emptyGranule()])));
  // Bands are (re)named by position so later selects never depend on reducer naming rules.
  var count = bands.count().unmask(0).rename(ids.concat([GUARD_BAND, PRESENT_BAND]));
  var mean = bands.select(ids).mean().rename(ids);
  var sum = bands.select(ids).sum().unmask(0).rename(ids);
  var proj = ee.ImageCollection(ds.collection_id).first().select(ds.aod_band).projection();

  // The single canonical spatial rule: native grid, ROI geometry, UNWEIGHTED reducers.
  function reduce(image, reducer) {
    return image.reduceRegion({reducer: reducer.unweighted(), geometry: roi, crs: proj,
                               maxPixels: 10000000, bestEffort: false});
  }
  function prefixed(prefix, names) { return names.map(function (n) { return prefix + n; }); }

  var allBands = ids.concat([GUARD_BAND, PRESENT_BAND]);
  var hasValid = count.select(ids).gt(0).rename(prefixed('has_', ids));
  var pixelSums = reduce(ee.Image.cat([count.rename(prefixed('n_', allBands)), hasValid,
                                       sum.rename(prefixed('sum_', ids)), ee.Image.constant(1).rename('roi_px')]),
                         ee.Reducer.sum());
  var means = reduce(mean.rename(prefixed('mean_', ids)), ee.Reducer.mean());

  var granules = raw.map(function (img) {
    var counts = reduce(granuleBands(img).select(ids), ee.Reducer.count());
    var props = {tt_utc_day: ee.Date(img.get('system:time_start')).format('YYYY-MM-dd')};
    ids.forEach(function (i) { props['tt_n_' + i] = counts.get(i); });
    return img.set(props);
  });
  var perVariant = {};
  ids.forEach(function (i) {
    var withValid = granules.filter(ee.Filter.gt('tt_n_' + i, 0));
    perVariant[i] = ee.Dictionary({
      granule_sum: granules.aggregate_sum('tt_n_' + i),
      granules_with_valid: withValid.size(),
      valid_day_count: withValid.aggregate_array('tt_utc_day').distinct().size()
    });
  });

  ee.Dictionary({granules_intersecting: nRaw, pixel_sums: pixelSums, means: means,
                 per_variant: ee.Dictionary(perVariant)})
    .evaluate(function (o, err) {
      if (err) { print('Earth Engine error:', err); return; }
      var engine = toEngineOutput(o, ids);
      var statuses = {};
      ids.forEach(function (i) { statuses[i] = variantStatus(engine, i); });
      print('Primary status:', statuses[primaryId()],
            '(NO_GRANULES / NO_VALID_OBSERVATIONS mean missing data, not zero AOD)');
      print('PARITY JSON (copy this single line into the acceptance file):');
      print(JSON.stringify({method_version: METHOD.method_version, roi_geojson: roiGeoJson,
                            start: start, end_exclusive: endExclusive, statuses: statuses,
                            engine_output: engine}));
    });

  var primary = primaryId();
  Map.centerObject(roi, 9);
  Map.addLayer(roi, {color: 'white'}, 'ROI (as sent to backend)');
  Map.addLayer(mean.select(primary).clip(roi),
    {min: -0.1, max: 1, palette: ['cde2fb', '6da7ec', '2a78d6', '184f95', '0d366b']},
    'MAIAC AOD 550 nm mean | primary (' + primary + ')');
  Map.addLayer(count.select(primary).updateMask(count.select(primary).gt(0)).clip(roi),
    {min: 1, max: 25, palette: ['f3bca8', 'e4744a', 'b13e02', '6f2401']}, 'Valid retrievals per pixel', false);
  Map.addLayer(count.select(primary).eq(0).selfMask().clip(roi), {palette: ['8a8a86']}, 'No valid retrieval');
  print('Column AOD at 550 nm - not PM10, not mine-attributed dust.');
}

if (typeof PARITY_TEST_HARNESS === 'undefined') {
  main();
}
