"""Compare backend engine output with the Code Editor parity script output (acceptance rule
from maiac_method.json: integer fields exact, means within an absolute tolerance).

Passing this comparison is PARITY EVIDENCE for one ROI and period. It is not scientific
validation of the AOD product, of the QA choices, or of any attribution.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..roi import canonical_hash
from . import maiac_spec as spec

ACCEPT = spec.METHOD["acceptance"]
VARIANT_INT_FIELDS = (
    "valid_retrievals",
    "valid_retrievals_granule_sum",
    "pixels_with_valid",
    "granules_with_valid",
    "valid_day_count",
)
TOP_INT_FIELDS = ("granules_intersecting", "pixels_total", "retrievals_before_qa", "qa_guard_rejections")


def _pooled(v: dict[str, Any]) -> float | None:
    return (v["aod_sum"] / v["valid_retrievals"]) if v["valid_retrievals"] else None


def compare_engine_outputs(
    backend: dict[str, Any], code_editor: dict[str, Any], tolerance: float = ACCEPT["mean_abs_tolerance"]
) -> list[str]:
    """Return human-readable mismatches (empty list = parity)."""
    problems: list[str] = []
    for key in TOP_INT_FIELDS:
        if int(backend[key]) != int(code_editor[key]):
            problems.append(f"{key}: backend {backend[key]} != code editor {code_editor[key]}")
    for v in spec.VARIANTS:
        b, c = backend["variants"].get(v.id), code_editor["variants"].get(v.id)
        if b is None or c is None:
            problems.append(f"variant {v.id} missing")
            continue
        for key in VARIANT_INT_FIELDS:
            if int(b[key]) != int(c[key]):
                problems.append(f"{v.id}.{key}: backend {b[key]} != code editor {c[key]}")
        for key, bv, cv in (
            ("roi_mean_aod", b["roi_mean_aod"], c["roi_mean_aod"]),
            ("roi_pooled_retrieval_mean_aod", _pooled(b), _pooled(c)),
        ):
            if (bv is None) != (cv is None):
                problems.append(f"{v.id}.{key}: backend {bv} vs code editor {cv} (null mismatch)")
            elif bv is not None and abs(float(bv) - float(cv)) > tolerance:
                problems.append(f"{v.id}.{key}: |{bv} - {cv}| > {tolerance:g}")
        if int(b["valid_retrievals"]) != int(b["valid_retrievals_granule_sum"]):
            problems.append(f"{v.id}: backend pixel-sum and granule-sum counts disagree")
    return problems


def check_code_editor_record(
    record: dict[str, Any], geometry: dict[str, Any], start: str, end_exclusive: str
) -> list[str]:
    problems = []
    if record.get("method_version") != spec.METHOD_VERSION:
        problems.append(f"method_version {record.get('method_version')} != {spec.METHOD_VERSION}")
    if canonical_hash(record.get("roi_geojson") or {}) != canonical_hash(geometry):
        problems.append("Code Editor ROI geometry differs from the acceptance ROI")
    if (record.get("start"), record.get("end_exclusive")) != (start, end_exclusive):
        problems.append(f"period {record.get('start')}..{record.get('end_exclusive')} != {start}..{end_exclusive}")
    return problems


def write_evidence(directory: Path, payload: dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"maiac_parity_{payload.get('roi_sha256', 'roi')[:12]}_{stamp}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
