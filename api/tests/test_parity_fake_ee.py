"""Run the REAL Earth Engine mask-building code (Python and the Code Editor parity script) on a
scalar fake of the EE API and compare both with the shared truth table generated from
maiac_spec. This checks behaviour, not string tokens. It does not replace the live
acceptance test (tests/test_ee_acceptance.py)."""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from . import fake_ee

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "gee" / "tests" / "qa_truth_cases.json").read_text())


@pytest.fixture(scope="module")
def maiac_ee_with_fake():
    real = sys.modules.get("ee")
    fake_ee.install()
    sys.modules.pop("app.datasets.maiac_ee", None)
    module = importlib.import_module("app.datasets.maiac_ee")
    yield module
    sys.modules.pop("app.datasets.maiac_ee", None)
    if real is not None:
        sys.modules["ee"] = real
    else:
        sys.modules.pop("ee", None)


def test_truth_cases_match_method_version() -> None:
    from app.datasets import maiac_spec as spec

    assert CASES["method_version"] == spec.METHOD_VERSION
    assert len(CASES["cases"]) > 1000


def test_python_pixel_masks_match_truth_table(maiac_ee_with_fake) -> None:
    columns = CASES["columns"]
    for raw, qa, expected in CASES["cases"]:
        image = fake_ee.Source(Optical_Depth_055=fake_ee.Pix(raw), AOD_QA=fake_ee.Pix(qa))
        masks = maiac_ee_with_fake.pixel_masks(image)
        got = [int(not masks[c].masked) for c in columns]
        assert got == expected, (raw, qa, dict(zip(columns, got, strict=True)))
        for vid in columns[:3]:
            if not masks[vid].masked:
                assert masks[vid].value == pytest.approx(raw * 0.001)  # scaled, never clamped


def test_python_reduction_is_unweighted_native_grid(maiac_ee_with_fake) -> None:
    roi, proj = object(), object()
    reduce = maiac_ee_with_fake._Reduction(roi, proj, 123)
    for factory in (fake_ee._Reducer.count, fake_ee._Reducer.sum, fake_ee._Reducer.mean):
        image = fake_ee.RecordingImage()
        reduce(image, factory())
        (call,) = image.calls
        assert call["reducer"].is_unweighted
        assert call["geometry"] is roi and call["crs"] is proj
        assert call["bestEffort"] is False and "scale" not in call


def test_engine_output_conversion_handles_empty_and_null() -> None:
    from app.datasets.maiac_ee import engine_output_from_ee

    out = {
        "granules_intersecting": 0,
        "pixel_sums": {"roi_px": 12.0},
        "means": {"mean_product_range": None},
        "per_variant": {
            i: {"granule_sum": 0, "granules_with_valid": 0, "valid_day_count": 0}
            for i in ("product_range", "nonnegative_sensitivity", "adjacency_clear_sensitivity")
        },
    }
    result = engine_output_from_ee(out, list(out["per_variant"]))
    assert result["pixels_total"] == 12 and result["granules_intersecting"] == 0
    assert result["variants"]["product_range"]["roi_mean_aod"] is None
    assert result["variants"]["nonnegative_sensitivity"]["valid_retrievals"] == 0


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_code_editor_parity_script_matches_truth_table() -> None:
    result = subprocess.run(
        ["node", "--test", "gee/tests/*.test.mjs"], cwd=ROOT, capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
