/**
 * LEGACY EXPLORATORY SCRIPT - this is not the acceptance parity check.
 * It predates method maiac-aod550/0.2.0 and differs from the backend: it reduces at
 * scale 1000 in the composite's default projection (EPSG:4326) with fractional-pixel
 * weighting, and drops negative AOD (0..8 screen). Use gee/maiac_parity_check.js for
 * acceptance. Kept unchanged below for the historical record.
 *
 * MAIAC MCD19A2.061 AOD (550 nm), strict QA-smoke test for April 2025.
 * Before running, draw a polygon/rectangle in GEE Code Editor's map UI
 * and keep its default imported variable name `geometry`.
 * This script does NOT attribute any aerosol signal to mining.
 * https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD19A2_GRANULES
 */

var aoi = geometry; // Draw your VERIFIED area of interest in the GEE Code Editor.
var start = '2025-04-01';
var end = '2025-05-01'; // Earth Engine filterDate end is exclusive.

var raw = ee.ImageCollection('MODIS/061/MCD19A2_GRANULES')
  .filterBounds(aoi)
  .filterDate(start, end);

function qaFilterAod(image) {
  var qa = image.select('AOD_QA');
  // AOD_QA bits 0-2: cloud flag 1 = clear.
  var clear = qa.bitwiseAnd(7).eq(1);
  // Bits 3-4: land/water/snow flag 0 = land.
  var land = qa.rightShift(3).bitwiseAnd(3).eq(0);
  // Bits 8-11: AOD quality 0 = best quality.
  var bestAodQa = qa.rightShift(8).bitwiseAnd(15).eq(0);
  var aod = image.select('Optical_Depth_055').multiply(0.001);
  var physical = aod.gte(0).and(aod.lte(8));
  return aod.updateMask(clear.and(land).and(bestAodQa).and(physical))
    .rename('AOD_550')
    .copyProperties(image, ['system:time_start']);
}

var filtered = raw.map(qaFilterAod);
var meanAod = filtered.mean().clip(aoi);
var validObservationCount = filtered.count().clip(aoi);

Map.centerObject(aoi, 9);
Map.addLayer(aoi, {color: 'white'}, 'Research ROI');
Map.addLayer(meanAod,
  {min: 0, max: 1, palette: ['152238', '277da1', '90be6d', 'f9c74f', 'f94144']},
  'MAIAC AOD 550 nm | April 2025 | QA-filtered');
Map.addLayer(validObservationCount,
  {min: 0, max: 25, palette: ['1f1f1f', '4169e1', 'c0ff00']},
  'Valid-observation count (granules)', false);

print('Granules intersecting ROI and period:', raw.size());
print('QA-filtered collection:', filtered);
print('ROI mean AOD (0.55 um; dimensionless):',
  meanAod.reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: aoi,
    scale: 1000,
    maxPixels: 10000000,
    bestEffort: false
  }).get('AOD_550'));
print('This is atmospheric column AOD, not PM10 or mine-specific emission.');
