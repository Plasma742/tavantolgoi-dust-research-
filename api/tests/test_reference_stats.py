"""Definitions of the period statistics on a synthetic native grid (no Earth Engine).

The grid, ROI and granules are synthetic test data, not observations.
"""

from __future__ import annotations

from datetime import date

import pytest
from shapely.geometry import Point, Polygon

from app.datasets import maiac_spec as spec
from app.datasets.maiac_reference import Granule, reference_period_stats
from app.datasets.maiac_service import summarize
from app.periods import Period

GOOD = 0b001  # clear, land, best quality, adjacency 0
ADJ1 = GOOD | (1 << 5)  # adjacent to clouds
BAD_GUARD = GOOD | (6 << 5)  # undocumented adjacency value
CLOUDY = 0b011
APRIL = Period(date(2025, 4, 1), date(2025, 5, 1))


def centre_pixels(polygon: Polygon, nx: int, ny: int) -> set[tuple[int, int]]:
    """Unit grid; pixel (i, j) has centre (i + 0.5, j + 0.5). Pixel-centre-in-ROI rule."""
    return {(i, j) for i in range(nx) for j in range(ny) if polygon.contains(Point(i + 0.5, j + 0.5))}


def test_edge_pixels_follow_centre_rule_in_pixel_and_granule_sums() -> None:
    # ROI covers x in [0.6, 2.4]: pixel 0 (centre 0.5) and pixel 2 (centre 2.5) overlap the ROI
    # partially but their centres are outside -> excluded from BOTH sums.
    roi = Polygon([(0.6, 0.0), (2.4, 0.0), (2.4, 1.0), (0.6, 1.0)])
    inside = centre_pixels(roi, 3, 1)
    assert inside == {(1, 0)}
    everywhere = {(i, 0): (200, GOOD) for i in range(3)}
    out = reference_period_stats([Granule("2025-04-01", everywhere), Granule("2025-04-02", everywhere)], inside)
    v = out["variants"]["product_range"]
    assert out["pixels_total"] == 1
    assert v["valid_retrievals"] == v["valid_retrievals_granule_sum"] == 2
    assert v["pixels_with_valid"] == 1 and v["valid_day_count"] == 2


def build_synthetic() -> dict:
    roi = {(0, 0), (1, 0), (2, 0), (3, 0)}
    g1 = Granule(
        "2025-04-03", {(0, 0): (-50, GOOD), (1, 0): (300, ADJ1), (2, 0): (100, BAD_GUARD), (3, 0): (400, CLOUDY)}
    )
    g2 = Granule("2025-04-03", {(0, 0): (150, GOOD), (1, 0): (None, GOOD), (2, 0): (200, GOOD)})  # same UTC day
    g3 = Granule("2025-04-10", {(0, 0): (-101, GOOD), (1, 0): (500, GOOD)})  # -101 out of range
    return reference_period_stats([g1, g2, g3], roi)


def test_variants_negative_values_and_guard() -> None:
    out = build_synthetic()
    p = out["variants"]["product_range"]
    nn = out["variants"]["nonnegative_sensitivity"]
    adj = out["variants"]["adjacency_clear_sensitivity"]
    # primary: (0,0): -0.05, 0.15 ; (1,0): 0.30, 0.50 ; (2,0): 0.20
    assert p["valid_retrievals"] == 5 and p["pixels_with_valid"] == 3 and p["valid_day_count"] == 2
    assert p["roi_mean_aod"] == pytest.approx(((-0.05 + 0.15) / 2 + (0.30 + 0.50) / 2 + 0.20) / 3)
    assert p["aod_sum"] == pytest.approx(-0.05 + 0.15 + 0.30 + 0.50 + 0.20)
    # non-negative drops -0.05 (excluded, not zeroed)
    assert nn["valid_retrievals"] == 4 and nn["roi_mean_aod"] == pytest.approx((0.15 + (0.30 + 0.50) / 2 + 0.20) / 3)
    # adjacency-clear drops the adjacency=1 retrieval
    assert adj["valid_retrievals"] == 4
    assert out["qa_guard_rejections"] == 1
    assert out["retrievals_before_qa"] == 7  # -101 and the masked raw are not present
    for v in (p, nn, adj):
        assert v["valid_retrievals"] == v["valid_retrievals_granule_sum"]


def test_summarize_reports_primary_pooled_and_sensitivity_differences() -> None:
    s = summarize(build_synthetic(), APRIL)
    assert s["method_version"] == spec.METHOD_VERSION and s["primary_variant"] == "product_range"
    assert s["status"] == "OK"
    assert s["roi_pooled_retrieval_mean_aod"] == pytest.approx((-0.05 + 0.15 + 0.30 + 0.50 + 0.20) / 5)
    assert s["roi_pooled_retrieval_mean_aod"] != pytest.approx(s["roi_mean_aod"])  # distinct statistics
    assert s["qa_guard_rejections"] == 1 and s["coverage_fraction"] == 0.75
    sens = {x["variant"]: x for x in s["sensitivity"]}
    assert set(sens) == {"nonnegative_sensitivity", "adjacency_clear_sensitivity"}
    d = sens["nonnegative_sensitivity"]["difference_vs_primary"]
    assert d["valid_retrievals"] == -1 and d["valid_day_count"] == 0
    assert d["roi_mean_aod"] == pytest.approx(sens["nonnegative_sensitivity"]["roi_mean_aod"] - s["roi_mean_aod"])
    assert all(x["role"] == "sensitivity" for x in s["sensitivity"])


def test_empty_period_and_tiny_roi() -> None:
    empty = summarize(reference_period_stats([], {(0, 0)}), APRIL)
    assert empty["status"] == "NO_GRANULES" and empty["roi_mean_aod"] is None
    assert all(x["status"] == "NO_GRANULES" for x in empty["sensitivity"])
    tiny = summarize(reference_period_stats([Granule("2025-04-01", {(0, 0): (100, GOOD)})], set()), APRIL)
    assert tiny["status"] == "NO_VALID_OBSERVATIONS" and tiny["coverage_fraction"] is None
    assert "pixel centre" in tiny["status_message"]


def test_all_cloudy_is_missing_not_zero() -> None:
    out = reference_period_stats([Granule("2025-04-01", {(0, 0): (100, CLOUDY)})], {(0, 0)})
    s = summarize(out, APRIL)
    assert s["status"] == "NO_VALID_OBSERVATIONS"
    assert s["roi_mean_aod"] is None and s["roi_pooled_retrieval_mean_aod"] is None
    assert s["valid_retrievals"] == 0 and s["coverage_fraction"] == 0.0
