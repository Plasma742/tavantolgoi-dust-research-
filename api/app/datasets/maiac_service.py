"""MAIAC request handling: validation -> cache -> Earth Engine engine -> response + provenance.

The engine is injected so the API layer can be tested without Earth Engine. Tests use
engines whose numbers are synthetic fixtures; they are never wired into the running app.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any, Protocol

from cachetools import TTLCache

from ..config import Settings
from ..ee_runtime import EERuntime
from ..errors import ApiError, InvalidRoi, classify_ee_error
from ..periods import Period, validate_month_range, validate_window
from ..provenance import maiac_provenance, roi_record, utc_now_iso
from ..roi import RegistryEntry, ValidRoi, validate_roi
from ..schemas import LayerResponse, MaiacLayerRequest, MonthlySeriesRequest, MonthlySeriesResponse, RoiInput
from ..security import LOCAL_PRINCIPAL, Principal
from ..tiles import TileFetcherLike, TileRegistry
from . import maiac_spec as spec

DATASET_START = date.fromisoformat(spec.DATASET_START_DATE)


class MaiacEngine(Protocol):
    def native_grid(self) -> dict[str, Any]: ...
    def period_stats(self, geometry: dict[str, Any], start: date, end_exclusive: date) -> dict[str, Any]: ...
    def layer_fetchers(
        self, geometry: dict[str, Any], start: date, end_exclusive: date
    ) -> dict[str, TileFetcherLike]: ...


def _variant_stats(raw: dict[str, Any], variant: spec.Variant) -> dict[str, Any]:
    v = raw["variants"][variant.id]
    granules = int(raw["granules_intersecting"])
    px_total = int(raw["pixels_total"])
    valid = int(v["valid_retrievals"])
    mean = v.get("roi_mean_aod")
    if granules == 0:
        status = "NO_GRANULES"
        message = (
            "No MAIAC granules intersect the ROI in this period (the period may be outside the "
            "collection's processed range). This is missing data, not zero aerosol."
        )
    elif px_total == 0:
        status = "NO_VALID_OBSERVATIONS"
        message = "The ROI contains no native-grid (~1 km) pixel centre. Enlarge the ROI."
    elif valid == 0 or mean is None:
        status = "NO_VALID_OBSERVATIONS"
        message = (
            "Granules exist but no retrieval in the ROI passed this variant's rules (cloud, land, AOD "
            "quality, documented-value guard, range or adjacency). This is missing data, not zero AOD."
        )
    else:
        status = "OK"
        message = "QA-filtered retrievals available."
    ok = status == "OK"
    return {
        "variant": variant.id,
        "role": variant.role,
        "label": variant.label,
        "definition": spec.qa_rule_text(variant),
        "status": status,
        "status_message": message,
        "roi_mean_aod": float(mean) if ok else None,
        "roi_pooled_retrieval_mean_aod": (float(v["aod_sum"]) / valid) if ok else None,
        "valid_retrievals": valid,
        "valid_retrievals_granule_sum": int(v["valid_retrievals_granule_sum"]),
        "pixels_with_valid": int(v["pixels_with_valid"]),
        "coverage_fraction": (int(v["pixels_with_valid"]) / px_total) if px_total else None,
        "granules_with_valid": int(v["granules_with_valid"]),
        "valid_day_count": int(v["valid_day_count"]),
        "consistency_check_passed": valid == int(v["valid_retrievals_granule_sum"]),
    }


def _diff(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else a - b


def summarize(raw: dict[str, Any], period: Period) -> dict[str, Any]:
    """Engine output (same shape as maiac_reference) -> primary summary + sensitivity variants."""
    primary = _variant_stats(raw, spec.PRIMARY)
    sensitivity = []
    for variant in spec.SENSITIVITY_VARIANTS:
        s = _variant_stats(raw, variant)
        s["difference_vs_primary"] = {
            "valid_retrievals": s["valid_retrievals"] - primary["valid_retrievals"],
            "valid_day_count": s["valid_day_count"] - primary["valid_day_count"],
            "pixels_with_valid": s["pixels_with_valid"] - primary["pixels_with_valid"],
            "coverage_fraction": _diff(s["coverage_fraction"], primary["coverage_fraction"]),
            "roi_mean_aod": _diff(s["roi_mean_aod"], primary["roi_mean_aod"]),
            "roi_pooled_retrieval_mean_aod": _diff(
                s["roi_pooled_retrieval_mean_aod"], primary["roi_pooled_retrieval_mean_aod"]
            ),
        }
        sensitivity.append(s)
    before = int(raw["retrievals_before_qa"])
    return {
        "method_version": spec.METHOD_VERSION,
        "primary_variant": spec.PRIMARY.id,
        "status": primary["status"],
        "status_message": primary["status_message"],
        "time_start_utc": f"{period.start.isoformat()}T00:00:00Z",
        "time_end_exclusive_utc": f"{period.end_exclusive.isoformat()}T00:00:00Z",
        "days_in_period": period.days,
        "roi_mean_aod": primary["roi_mean_aod"],
        "roi_pooled_retrieval_mean_aod": primary["roi_pooled_retrieval_mean_aod"],
        "pixels_total": int(raw["pixels_total"]),
        "pixels_with_valid": primary["pixels_with_valid"],
        "coverage_fraction": primary["coverage_fraction"],
        "valid_retrievals": primary["valid_retrievals"],
        "valid_retrievals_granule_sum": primary["valid_retrievals_granule_sum"],
        "retrievals_before_qa": before,
        "qa_retention_fraction": (primary["valid_retrievals"] / before) if before else None,
        "qa_guard_rejections": int(raw["qa_guard_rejections"]),
        "granules_intersecting": int(raw["granules_intersecting"]),
        "granules_with_valid": primary["granules_with_valid"],
        "valid_day_count": primary["valid_day_count"],
        "consistency_check_passed": primary["consistency_check_passed"],
        "sensitivity": sensitivity,
    }


def _legend_aod() -> dict[str, Any]:
    vis = spec.AOD_VIS
    return {
        "kind": "continuous",
        "title": f"Mean AOD at 550 nm - primary variant ({spec.PRIMARY.id})",
        "unit": spec.UNIT,
        "palette": vis["palette"],
        "min": vis["min"],
        "max": vis["max"],
        "ticks": [{"value": v, "label": f"{v:.2f}"} for v in (-0.1, 0.0, 0.25, 0.5, 0.75)]
        + [{"value": 1.0, "label": "≥1.00"}],
        "note": "Colour range -0.10 to 1.00: small negative AOD (product range starts at -0.100) is shown, "
        "not clamped. Values ≥1.0 use the darkest colour. Grey = ROI pixel with no valid retrieval. "
        "Column AOD, not PM10 and not mine-attributed dust.",
    }


def _legend_count() -> dict[str, Any]:
    vis = spec.COUNT_VIS
    return {
        "kind": "continuous",
        "title": f"Valid retrievals per pixel - primary variant ({spec.PRIMARY.id})",
        "unit": "count of QA-passing granule retrievals",
        "palette": vis["palette"],
        "min": vis["min"],
        "max": vis["max"],
        "ticks": [{"value": v, "label": str(v)} for v in (1, 5, 10, 15, 20)] + [{"value": 25, "label": "≥25"}],
        "note": "Granule-level count: Terra and Aqua overpasses are counted separately, so more than one "
        "per day is possible. Pixels with zero are shown by the 'No valid retrieval' layer.",
    }


def _legend_none() -> dict[str, Any]:
    return {
        "kind": "categorical",
        "title": "No valid retrieval in period",
        "unit": "mask",
        "palette": spec.NO_VALID_VIS["palette"],
        "note": "ROI pixels with zero valid retrievals in the primary variant (cloud, snow/ice, low QA, "
        "guard, or no overpass). Missing data - not zero AOD.",
    }


class MaiacService:
    def __init__(
        self,
        settings: Settings,
        runtime: EERuntime,
        engine_factory: Callable[[], MaiacEngine],
        tiles: TileRegistry,
        registry: dict[str, RegistryEntry],
    ):
        self._settings = settings
        self._runtime = runtime
        self._engine_factory = engine_factory
        self._engine: MaiacEngine | None = None
        self._engine_lock = threading.Lock()
        self._tiles = tiles
        self._registry = registry
        # Stats are keyed by geometry hash + period only: identical inputs give identical numbers,
        # so sharing them across principals reveals nothing the requester did not submit.
        self._stats_cache: TTLCache[tuple[str, ...], tuple[dict[str, Any], str]] = TTLCache(
            maxsize=4096, ttl=settings.stats_cache_ttl_s
        )
        # Layer responses carry tile ids bound to a principal, so they are cached per principal.
        self._layer_cache: TTLCache[tuple[str, ...], dict[str, Any]] = TTLCache(
            maxsize=256, ttl=settings.layer_cache_ttl_s
        )
        self._cache_lock = threading.Lock()

    # -- helpers -------------------------------------------------------------------
    def _engine_ready(self) -> MaiacEngine:
        self._runtime.ensure_ready()
        with self._engine_lock:
            if self._engine is None:
                self._engine = self._engine_factory()
            return self._engine

    def resolve_roi(self, roi: RoiInput) -> tuple[ValidRoi, dict[str, Any]]:
        limits = {
            "max_area_km2": self._settings.max_roi_area_km2,
            "max_vertices": self._settings.max_roi_vertices,
            "allowed_bbox": self._settings.allowed_bbox,
        }
        if roi.declared_status == "registry":
            entry = self._registry.get(roi.registry_id or "")
            if entry is None:
                raise InvalidRoi(f"Unknown registry ROI '{roi.registry_id}'.")
            valid = validate_roi(entry.geometry, **limits)
            record = roi_record(
                valid,
                label=entry.label,
                declared_status="registry",
                source_note=entry.source,
                registry_verified=entry.verified,
            )
            record["registry_id"] = entry.id
            record["license"] = entry.license
            return valid, record
        valid = validate_roi(roi.geometry, **limits)
        return valid, roi_record(
            valid, label=roi.label, declared_status=roi.declared_status, source_note=roi.source_note
        )

    def _native_grid(self, engine: MaiacEngine) -> dict[str, Any] | None:
        try:
            return engine.native_grid()
        except Exception as exc:  # report, never guess
            return {"error": f"native grid lookup failed: {str(exc)[:200]}"}

    def _stats(self, engine: MaiacEngine, valid: ValidRoi, period: Period) -> tuple[dict[str, Any], str, bool]:
        key = (spec.METHOD_VERSION, valid.sha256, period.start.isoformat(), period.end_exclusive.isoformat())
        with self._cache_lock:
            hit = self._stats_cache.get(key)
        if hit is not None:
            return hit[0], hit[1], True
        try:
            raw = engine.period_stats(valid.geometry, period.start, period.end_exclusive)
        except ApiError:
            raise
        except Exception as exc:
            raise classify_ee_error(exc) from exc
        computed_at = utc_now_iso()
        with self._cache_lock:
            self._stats_cache[key] = (raw, computed_at)
        return raw, computed_at, False

    def _owner(self, principal: Principal) -> str | None:
        return principal.id if self._settings.public else None

    # -- endpoints -----------------------------------------------------------------
    def layer(self, req: MaiacLayerRequest, principal: Principal = LOCAL_PRINCIPAL) -> dict[str, Any]:
        valid, roi_rec = self.resolve_roi(req.roi)
        period = validate_window(
            req.start, req.end_exclusive, max_days=self._settings.max_layer_days, earliest=DATASET_START
        )
        engine = self._engine_ready()
        owner = self._owner(principal)
        key = (
            spec.METHOD_VERSION,
            owner or "",
            valid.sha256,
            period.start.isoformat(),
            period.end_exclusive.isoformat(),
        )
        with self._cache_lock:
            cached = self._layer_cache.get(key)
        if cached is not None:
            response = dict(cached)
            response["provenance"] = {
                **cached["provenance"],
                "roi": roi_rec,
                "processing": {**cached["provenance"]["processing"], "served_from_cache": True},
            }
            return LayerResponse.model_validate(response).model_dump()

        raw, computed_at, stats_hit = self._stats(engine, valid, period)
        summary = summarize(raw, period)
        layers: list[dict[str, Any]] = []
        if summary["status"] != "NO_GRANULES":
            try:
                fetchers = engine.layer_fetchers(valid.geometry, period.start, period.end_exclusive)
            except ApiError:
                raise
            except Exception as exc:
                raise classify_ee_error(exc) from exc
            specs = [
                ("aod_mean", "MAIAC AOD 550 nm - period mean (primary variant)", _legend_aod(), True, 0.85),
                ("valid_count", "Valid-observation count (granule level, primary)", _legend_count(), False, 0.85),
                ("no_valid_retrieval", "No valid retrieval in period (primary)", _legend_none(), True, 0.55),
            ]
            for layer_id, title, legend, visible, opacity in specs:
                tile_id = self._tiles.register(fetchers[layer_id], valid.bbox, owner=owner)
                layers.append(
                    {
                        "id": layer_id,
                        "title": title,
                        "observation_type": "satellite_retrieval",
                        "variant": spec.PRIMARY.id,
                        "tile_url_template": f"/api/tiles/{tile_id}/{{z}}/{{x}}/{{y}}.png",
                        "max_native_zoom": self._tiles.max_zoom,
                        "default_visible": visible,
                        "default_opacity": opacity,
                        "legend": legend,
                    }
                )
        provenance = maiac_provenance(
            roi=roi_rec,
            periods=[
                {
                    "label": "map period",
                    **period.as_dict(),
                    "computed_at_utc": computed_at,
                    "summary_from_cache": stats_hit,
                }
            ],
            native_grid=self._native_grid(engine),
            code_revision=self._settings.code_revision,
            ee_version=self._runtime.earthengine_api_version,
            cache_hit=False,
            computed_at=utc_now_iso(),
        )
        response = {
            "status": summary["status"],
            "dataset_key": spec.DATASET_KEY,
            "layers": layers,
            "summary": summary,
            "provenance": provenance,
            "tiles_note": "Tiles are proxied by the backend and expire after about "
            f"{self._settings.layer_cache_ttl_s // 60} minutes; reload the layer if they stop loading.",
        }
        validated = LayerResponse.model_validate(response).model_dump()
        if layers:
            with self._cache_lock:
                self._layer_cache[key] = validated
        return validated

    def monthly(self, req: MonthlySeriesRequest) -> dict[str, Any]:
        valid, roi_rec = self.resolve_roi(req.roi)
        months = validate_month_range(
            req.start_month, req.end_month, max_months=self._settings.max_series_months, earliest=DATASET_START
        )
        engine = self._engine_ready()

        def one(item: tuple[str, Period]) -> tuple[str, Period, dict[str, Any], str, bool]:
            label, period = item
            raw, computed_at, hit = self._stats(engine, valid, period)
            return label, period, raw, computed_at, hit

        with ThreadPoolExecutor(max_workers=self._settings.ee_max_parallel) as pool:
            results = list(pool.map(one, months))

        rows = [{"month": label, **summarize(raw, period)} for label, period, raw, _, _ in results]
        periods = [
            {"label": label, **period.as_dict(), "computed_at_utc": computed_at, "summary_from_cache": hit}
            for label, period, _, computed_at, hit in results
        ]
        provenance = maiac_provenance(
            roi=roi_rec,
            periods=periods,
            native_grid=self._native_grid(engine),
            code_revision=self._settings.code_revision,
            ee_version=self._runtime.earthengine_api_version,
            cache_hit=all(p["summary_from_cache"] for p in periods),
            computed_at=utc_now_iso(),
        )
        return MonthlySeriesResponse.model_validate(
            {"dataset_key": spec.DATASET_KEY, "rows": rows, "provenance": provenance}
        ).model_dump()
