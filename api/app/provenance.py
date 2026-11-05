"""Provenance records attached to every MAIAC response (schema follows docs/PROVENANCE_EXAMPLE.json)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .datasets import maiac_spec as spec
from .roi import ValidRoi

SCHEMA_VERSION = "1.0"


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def roi_record(
    valid: ValidRoi, *, label: str, declared_status: str, source_note: str | None, registry_verified: bool | None = None
) -> dict[str, Any]:
    status_text = {
        "demonstration": "Manual demonstration ROI drawn in the browser — NOT a verified mine boundary.",
        "unverified_upload": "Uploaded GeoJSON with unverified provenance.",
        "user_declared_verified": "Uploaded GeoJSON declared verified by the user (claim not checked by the server).",
        "registry": "Server-registered ROI; verification status from its metadata file.",
    }[declared_status]
    record: dict[str, Any] = {
        "label": label,
        "declared_status": declared_status,
        "status_description": status_text,
        "source_note": source_note,
        "sha256": valid.sha256,
        "approx_area_km2": round(valid.approx_area_km2, 1),
        "approx_area_method": "spherical approximation used only to bound request size",
        "bbox_wgs84": [round(v, 6) for v in valid.bbox],
        "vertex_count": valid.vertex_count,
        "edge_interpretation": "planar (non-geodesic) edges in EPSG:4326",
    }
    if registry_verified is not None:
        record["registry_verified"] = registry_verified
    return record


def maiac_provenance(
    *,
    roi: dict[str, Any],
    periods: list[dict[str, Any]],
    native_grid: dict[str, Any] | None,
    code_revision: str | None,
    ee_version: str | None,
    cache_hit: bool,
    computed_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "computed_from_earth_engine",
        "observation_type": "satellite_retrieval",
        "dataset_id": spec.COLLECTION_ID,
        "dataset_title": spec.DATASET_TITLE,
        "band": spec.AOD_BAND,
        "qa_band": spec.QA_BAND,
        "derived_band": spec.DERIVED_BAND,
        "quantity": spec.QUANTITY,
        "unit": spec.UNIT,
        "scale_factor": spec.SCALE_FACTOR,
        "offset": spec.OFFSET,
        "method_version": spec.METHOD_VERSION,
        "primary_variant": spec.PRIMARY.id,
        "quality_filter": {
            "text": spec.QA_RULE_TEXT,
            "core_qa": spec.CORE_QA_TEXT,
            "documented_value_guard": spec.GUARD_TEXT,
            "rules": [
                {"field": name, "bits": spec.QA_FIELDS[name].bits, "accepted_values": list(values)}
                for name, values in spec.CORE_QA_ACCEPT.items()
            ],
            "primary_raw_range": [spec.PRIMARY.raw_min, spec.PRIMARY.raw_max],
            "physical_range": [spec.PRIMARY.aod_min, spec.PRIMARY.aod_max],
            "clamping": "none",
        },
        "variants": spec.method_summary()["variants"],
        "statistic_definitions": spec.STATISTIC_DEFINITIONS,
        "temporal_aggregation": spec.TEMPORAL_AGGREGATION_TEXT,
        "spatial_reduction": spec.SPATIAL_REDUCTION_TEXT,
        "periods": periods,
        "spatial": {
            "catalog_pixel_size_m": spec.CATALOG_PIXEL_SIZE_M,
            "native_grid_reported_by_earth_engine": native_grid,
            "display_note": "Map tiles are rendered by Earth Engine for display (Web Mercator). Zooming in "
            "does not add resolution; statistics use the native grid.",
            "resampling": "none for statistics (native grid); nearest-neighbour for display tiles",
            "interpolation": "none; missing pixels stay missing",
            "spatial_rule": spec.METHOD["spatial_rule"],
        },
        "roi": roi,
        "not_a_measurement_of": list(spec.NOT_A_MEASUREMENT_OF),
        "caveat": spec.CAVEAT,
        "source_url": spec.CATALOG_URL,
        "citation": spec.CITATION,
        "processing": {
            "method_version": spec.METHOD_VERSION,
            "code_revision": code_revision,
            "earthengine_api_version": ee_version,
            "computed_at_utc": computed_at,
            "served_from_cache": cache_hit,
            "parity_script": "gee/maiac_parity_check.js",
        },
    }
