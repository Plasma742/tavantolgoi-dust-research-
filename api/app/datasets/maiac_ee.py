"""Earth Engine implementation of the MAIAC AOD 550 nm method (see maiac_method.json).

Every constant comes from ``maiac_spec``. ``gee/maiac_parity_check.js`` mirrors this module
function for function, and both are checked against ``maiac_reference`` / shared truth-table
fixtures by the test suite (with a scalar fake of the ``ee`` API, no network).

This module needs an initialised Earth Engine session for real use.
"""

from __future__ import annotations

import threading
from datetime import date
from typing import Any

import ee

from . import maiac_spec as spec

_P_DAY = "tt_utc_day"
GUARD_BAND = "guard_rejected"
PRESENT_BAND = "raw_present"


def _p_count(variant_id: str) -> str:
    return f"tt_n_{variant_id}"


def roi_geometry(geojson_geometry: dict[str, Any]) -> ee.Geometry:
    # Planar (non-geodesic) edges in EPSG:4326, as RFC 7946 GeoJSON and Code Editor geometries.
    return ee.Geometry(geojson_geometry, "EPSG:4326", False)


def _field(qa: ee.Image, name: str) -> ee.Image:
    f = spec.QA_FIELDS[name]
    return qa.rightShift(f.start_bit).bitwiseAnd(f.mask)


def _in_values(image: ee.Image, values: tuple[int, ...]) -> ee.Image:
    accepted = image.eq(values[0])
    for value in values[1:]:
        accepted = accepted.Or(image.eq(value))
    return accepted


def _in_range(image: ee.Image, low: int, high: int) -> ee.Image:
    return image.gte(low).And(image.lte(high))


def pixel_masks(image: ee.Image) -> dict[str, ee.Image]:
    """Per-granule images: one scaled, masked AOD image per variant, plus the guard and
    raw-present indicator masks. Range tests use the raw integers (no float boundary error)."""
    qa = image.select(spec.QA_BAND)
    raw = image.select(spec.AOD_BAND)
    core = ee.Image.constant(1)
    for name, accepted in spec.CORE_QA_ACCEPT.items():
        core = core.And(_in_values(_field(qa, name), accepted))
    guard = ee.Image.constant(1)
    for name in spec.GUARD_FIELDS:
        guard = guard.And(_in_values(_field(qa, name), spec.QA_FIELDS[name].documented_values))
    present = _in_range(raw, spec.RAW_VALID_MIN, spec.RAW_VALID_MAX)
    aod = raw.multiply(spec.SCALE_FACTOR).add(spec.OFFSET)

    out: dict[str, ee.Image] = {}
    for v in spec.VARIANTS:
        keep = core.And(guard).And(_in_range(raw, v.raw_min, v.raw_max))
        if v.adjacency_accept is not None:
            keep = keep.And(_in_values(_field(qa, "adjacency"), v.adjacency_accept))
        out[v.id] = aod.updateMask(keep)
    out[GUARD_BAND] = present.And(core).And(guard.Not()).selfMask()
    out[PRESENT_BAND] = present.selfMask()
    return out


def _granule_bands(image: ee.Image) -> ee.Image:
    masks = pixel_masks(image)
    bands = [masks[v.id].rename(v.id) for v in spec.VARIANTS]
    bands += [masks[GUARD_BAND].rename(GUARD_BAND), masks[PRESENT_BAND].rename(PRESENT_BAND)]
    return ee.Image(ee.Image.cat(bands).toFloat().copyProperties(image, ["system:time_start"]))


def _empty_granule() -> ee.Image:
    names = [v.id for v in spec.VARIANTS] + [GUARD_BAND, PRESENT_BAND]
    return ee.Image.cat([ee.Image.constant(0).toFloat().rename(n).selfMask() for n in names])


class _Reduction:
    """The single canonical spatial rule: native grid, ROI geometry, UNWEIGHTED reducers."""

    def __init__(self, roi: ee.Geometry, projection: ee.Projection, max_pixels: int):
        self.roi = roi
        self.projection = projection
        self.max_pixels = max_pixels

    def __call__(self, image: ee.Image, reducer: ee.Reducer) -> ee.Dictionary:
        return image.reduceRegion(
            reducer=reducer.unweighted(),
            geometry=self.roi,
            crs=self.projection,
            maxPixels=self.max_pixels,
            bestEffort=False,
        )


class _Composites:
    """Server-side images for one ROI and period (no network calls are made here)."""

    def __init__(self, geometry: dict[str, Any], start: date, end_exclusive: date):
        self.roi = roi_geometry(geometry)
        self.raw = (
            ee.ImageCollection(spec.COLLECTION_ID)
            .filterBounds(self.roi)
            .filterDate(start.isoformat(), end_exclusive.isoformat())
        )
        self.n_raw = self.raw.size()
        bands = self.raw.map(_granule_bands)
        # Guard: mean()/count() of an empty collection has no bands.
        self.bands = ee.ImageCollection(
            ee.Algorithms.If(self.n_raw.gt(0), bands, ee.ImageCollection([_empty_granule()]))
        )
        ids = [v.id for v in spec.VARIANTS]
        # Bands are (re)named by position so later selects never depend on reducer naming rules.
        self.count = self.bands.count().unmask(0).rename([*ids, GUARD_BAND, PRESENT_BAND])  # per-pixel counts
        self.mean = self.bands.select(ids).mean().rename(ids)  # masked where no valid retrieval
        self.sum = self.bands.select(ids).sum().unmask(0).rename(ids)


class MaiacEarthEngine:
    """Real engine. Methods block on Earth Engine and may raise ``ee.EEException``."""

    def __init__(self, max_pixels: int = 10_000_000):
        self._max_pixels = max_pixels
        self._grid_lock = threading.Lock()
        self._grid: dict[str, Any] | None = None

    def _projection(self) -> ee.Projection:
        return ee.ImageCollection(spec.COLLECTION_ID).first().select(spec.AOD_BAND).projection()

    def native_grid(self) -> dict[str, Any]:
        with self._grid_lock:
            if self._grid is None:
                proj = self._projection()
                info = ee.Dictionary({"projection": proj, "nominal_scale_m": proj.nominalScale()}).getInfo()
                self._grid = {
                    "crs": info["projection"].get("crs"),
                    "crs_transform": info["projection"].get("transform"),
                    "nominal_scale_m": info["nominal_scale_m"],
                }
            return self._grid

    def period_stats(self, geometry: dict[str, Any], start: date, end_exclusive: date) -> dict[str, Any]:
        c = _Composites(geometry, start, end_exclusive)
        reduce = _Reduction(c.roi, self._projection(), self._max_pixels)
        ids = [v.id for v in spec.VARIANTS]

        has_valid = c.count.select(ids).gt(0).rename([f"has_{i}" for i in ids])
        roi_px = ee.Image.constant(1).rename("roi_px")
        pixel_sums = reduce(
            ee.Image.cat(
                [
                    c.count.rename([f"n_{b}" for b in [*ids, GUARD_BAND, PRESENT_BAND]]),
                    has_valid,
                    c.sum.rename([f"sum_{i}" for i in ids]),
                    roi_px,
                ]
            ),
            ee.Reducer.sum(),
        )
        means = reduce(c.mean.rename([f"mean_{i}" for i in ids]), ee.Reducer.mean())

        def per_granule(img: ee.Image) -> ee.Image:
            counts = reduce(_granule_bands(img).select(ids), ee.Reducer.count())
            props = {_p_count(i): counts.get(i) for i in ids}
            props[_P_DAY] = ee.Date(img.get("system:time_start")).format("YYYY-MM-dd")
            return img.set(props)

        granules = c.raw.map(per_granule)
        per_variant = {}
        for i in ids:
            with_valid = granules.filter(ee.Filter.gt(_p_count(i), 0))
            per_variant[i] = ee.Dictionary(
                {
                    "granule_sum": granules.aggregate_sum(_p_count(i)),
                    "granules_with_valid": with_valid.size(),
                    "valid_day_count": with_valid.aggregate_array(_P_DAY).distinct().size(),
                }
            )

        out = ee.Dictionary(
            {
                "granules_intersecting": c.n_raw,
                "pixel_sums": pixel_sums,
                "means": means,
                "per_variant": ee.Dictionary(per_variant),
            }
        ).getInfo()
        return engine_output_from_ee(out, ids)

    def layer_fetchers(self, geometry: dict[str, Any], start: date, end_exclusive: date) -> dict[str, Any]:
        """Map layers for the PRIMARY variant only."""
        c = _Composites(geometry, start, end_exclusive)
        pid = spec.PRIMARY.id
        aod = c.mean.select(pid).clip(c.roi)
        count = c.count.select(pid)
        count_vis = count.updateMask(count.gt(0)).clip(c.roi)
        none_valid = count.eq(0).selfMask().clip(c.roi)
        layers = {
            "aod_mean": aod.getMapId({**spec.AOD_VIS, "format": "png"}),
            "valid_count": count_vis.getMapId({**spec.COUNT_VIS, "format": "png"}),
            "no_valid_retrieval": none_valid.getMapId({"min": 0, "max": 1, **spec.NO_VALID_VIS, "format": "png"}),
        }
        return {key: value["tile_fetcher"] for key, value in layers.items()}


def _int(value: Any) -> int:
    return round(float(value or 0))


def engine_output_from_ee(out: dict[str, Any], ids: list[str]) -> dict[str, Any]:
    """Convert the getInfo() dictionary into the engine-output shape used by maiac_reference."""
    sums = out.get("pixel_sums") or {}
    means = out.get("means") or {}
    variants = {}
    for i in ids:
        pv = out["per_variant"][i]
        variants[i] = {
            "valid_retrievals": _int(sums.get(f"n_{i}")),
            "valid_retrievals_granule_sum": _int(pv.get("granule_sum")),
            "pixels_with_valid": _int(sums.get(f"has_{i}")),
            "roi_mean_aod": means.get(f"mean_{i}"),
            "aod_sum": float(sums.get(f"sum_{i}") or 0.0),
            "granules_with_valid": _int(pv.get("granules_with_valid")),
            "valid_day_count": _int(pv.get("valid_day_count")),
        }
    return {
        "granules_intersecting": _int(out.get("granules_intersecting")),
        "pixels_total": _int(sums.get("roi_px")),
        "retrievals_before_qa": _int(sums.get(f"n_{PRESENT_BAND}")),
        "qa_guard_rejections": _int(sums.get(f"n_{GUARD_BAND}")),
        "variants": variants,
    }
