"""Acceptance parity workflow.

Offline tests check the comparison rule itself. The two live tests are OPT-IN and skipped
unless explicitly enabled; CI never enables them and never claims scientific validation.

Live acceptance (from api/, Earth Engine authenticated):

    RUN_EE_ACCEPTANCE=1 EE_PROJECT_ID=<project> \\
    ACCEPTANCE_ROI_GEOJSON=<verified ROI Feature (registry format)> \\
    ACCEPTANCE_CODE_EDITOR_JSON=<file holding the "PARITY JSON" line from gee/maiac_parity_check.js> \\
    python -m pytest tests/test_ee_acceptance.py -s

Set ACCEPTANCE_ALLOW_UNVERIFIED_ROI=1 to run with a demonstration ROI; the evidence record
then says so. Evidence is written to ACCEPTANCE_EVIDENCE_DIR (default api/.acceptance_evidence,
git-ignored because it contains the ROI geometry).
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

from app.datasets import maiac_spec as spec
from app.datasets.maiac_acceptance import check_code_editor_record, compare_engine_outputs, write_evidence
from app.datasets.maiac_reference import Granule, reference_period_stats

from .conftest import GOOD_QA, ROI_PIXELS

ACCEPT = spec.METHOD["acceptance"]
API_DIR = Path(__file__).resolve().parents[1]


def synthetic_output() -> dict:
    return reference_period_stats([Granule("2025-04-01", {(0, 0): (-50, GOOD_QA), (1, 0): (300, GOOD_QA)})], ROI_PIXELS)


# -- offline: the comparison rule -----------------------------------------------------


def test_identical_outputs_pass() -> None:
    out = synthetic_output()
    assert compare_engine_outputs(out, copy.deepcopy(out)) == []


def test_integer_difference_fails_exactly() -> None:
    a, b = synthetic_output(), synthetic_output()
    b["variants"]["product_range"]["valid_day_count"] += 1
    b["pixels_total"] += 1
    problems = compare_engine_outputs(a, b)
    assert any("valid_day_count" in p for p in problems) and any("pixels_total" in p for p in problems)


def test_mean_tolerance_and_null_mismatch() -> None:
    a, b = synthetic_output(), synthetic_output()
    b["variants"]["product_range"]["roi_mean_aod"] += ACCEPT["mean_abs_tolerance"] / 2
    assert compare_engine_outputs(a, b) == []
    b["variants"]["product_range"]["roi_mean_aod"] += ACCEPT["mean_abs_tolerance"] * 10
    assert any("roi_mean_aod" in p for p in compare_engine_outputs(a, b))
    c = synthetic_output()
    c["variants"]["nonnegative_sensitivity"]["roi_mean_aod"] = None
    assert any("null mismatch" in p for p in compare_engine_outputs(a, c))


def test_record_must_match_method_roi_and_period() -> None:
    geom = {"type": "Polygon", "coordinates": [[[105.3, 43.5], [105.7, 43.5], [105.7, 43.8], [105.3, 43.5]]]}
    record = {
        "method_version": spec.METHOD_VERSION,
        "roi_geojson": geom,
        "start": "2025-04-01",
        "end_exclusive": "2025-05-01",
    }
    assert check_code_editor_record(record, geom, "2025-04-01", "2025-05-01") == []
    other = {**record, "method_version": "maiac-aod550-strict-qa/0.1.0", "start": "2025-03-01"}
    assert len(check_code_editor_record(other, {**geom, "coordinates": [[[0, 0]]]}, "2025-04-01", "2025-05-01")) == 3


# -- live, opt-in ---------------------------------------------------------------------

LIVE = os.environ.get("RUN_EE_ACCEPTANCE") == "1" and os.environ.get("EE_PROJECT_ID")


def _load_roi() -> tuple[dict, bool]:
    feature = json.loads(Path(os.environ["ACCEPTANCE_ROI_GEOJSON"]).read_text(encoding="utf-8"))
    verified = (feature.get("properties") or {}).get("verification_status") == "verified"
    return (feature["geometry"] if feature.get("type") == "Feature" else feature), verified


@pytest.mark.skipif(
    not LIVE or not os.environ.get("ACCEPTANCE_ROI_GEOJSON") or not os.environ.get("ACCEPTANCE_CODE_EDITOR_JSON"),
    reason="live acceptance disabled (see module docstring)",
)
def test_live_acceptance_parity_april_2025() -> None:
    from app.config import load_settings
    from app.datasets.maiac_ee import MaiacEarthEngine
    from app.ee_runtime import EERuntime
    from app.periods import month_period
    from app.roi import validate_roi

    settings = load_settings()
    geometry, verified = _load_roi()
    if not verified and os.environ.get("ACCEPTANCE_ALLOW_UNVERIFIED_ROI") != "1":
        pytest.fail(
            "Acceptance ROI is not marked verification_status=verified "
            "(set ACCEPTANCE_ALLOW_UNVERIFIED_ROI=1 to record a demonstration-ROI run)."
        )
    valid = validate_roi(
        geometry,
        max_area_km2=settings.max_roi_area_km2,
        max_vertices=settings.max_roi_vertices,
        allowed_bbox=settings.allowed_bbox,
    )
    period = month_period(ACCEPT["test_month"])
    start, end = period.start.isoformat(), period.end_exclusive.isoformat()
    record = json.loads(Path(os.environ["ACCEPTANCE_CODE_EDITOR_JSON"]).read_text(encoding="utf-8").strip())

    EERuntime(settings).ensure_ready()
    engine = MaiacEarthEngine(max_pixels=settings.ee_max_pixels)
    backend = engine.period_stats(valid.geometry, period.start, period.end_exclusive)
    problems = check_code_editor_record(record, valid.geometry, start, end)
    problems += compare_engine_outputs(backend, record["engine_output"])
    evidence = write_evidence(
        Path(os.environ.get("ACCEPTANCE_EVIDENCE_DIR", API_DIR / ".acceptance_evidence")),
        {
            "kind": "maiac_parity_evidence",
            "note": ACCEPT["note"],
            "result": "PASS" if not problems else "FAIL",
            "problems": problems,
            "method_version": spec.METHOD_VERSION,
            "roi_sha256": valid.sha256,
            "roi_verification": "verified" if verified else "demonstration ROI (not verified)",
            "period": {"start": start, "end_exclusive": end},
            "tolerance": {"integers": "exact", "means_abs": ACCEPT["mean_abs_tolerance"]},
            "backend_engine_output": backend,
            "code_editor_record": record,
            "native_grid": engine.native_grid(),
            "code_revision": settings.code_revision,
        },
    )
    print(f"evidence written to {evidence}")
    assert not problems, "\n".join(problems)


@pytest.mark.skipif(
    os.environ.get("RUN_EE_INTEGRATION") != "1"
    or not os.environ.get("EE_PROJECT_ID")
    or not os.environ.get("TEST_ROI_GEOJSON"),
    reason="live integration test disabled",
)
def test_live_internal_invariants() -> None:
    from app.config import load_settings
    from app.datasets.maiac_ee import MaiacEarthEngine
    from app.ee_runtime import EERuntime
    from app.periods import month_period

    EERuntime(load_settings()).ensure_ready()
    data = json.loads(Path(os.environ["TEST_ROI_GEOJSON"]).read_text())
    geometry = data["geometry"] if data.get("type") == "Feature" else data
    period = month_period(ACCEPT["test_month"])
    raw = MaiacEarthEngine().period_stats(geometry, period.start, period.end_exclusive)
    print(json.dumps(raw, indent=2))
    p = raw["variants"][spec.PRIMARY.id]
    for v in spec.SENSITIVITY_VARIANTS:  # every sensitivity variant is a subset of the primary
        assert raw["variants"][v.id]["valid_retrievals"] <= p["valid_retrievals"]
    for v in raw["variants"].values():
        assert v["valid_retrievals"] == v["valid_retrievals_granule_sum"]
        assert 0 <= v["pixels_with_valid"] <= raw["pixels_total"]
        assert v["valid_day_count"] <= period.days
        if v["roi_mean_aod"] is not None:
            assert -0.1 - 1e-9 <= v["roi_mean_aod"] <= 8.0 + 1e-9
