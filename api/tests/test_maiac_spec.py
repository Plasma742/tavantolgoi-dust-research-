"""QA, range and variant logic checked exhaustively against an independent hand-written rule."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.datasets import maiac_spec as spec

ROOT = Path(__file__).resolve().parents[2]


def qa(
    cloud: int = 1, lwsi: int = 0, adjacency: int = 0, aodq: int = 0, glint: int = 0, model: int = 0, reserved: int = 0
) -> int:
    return cloud | (lwsi << 3) | (adjacency << 5) | (aodq << 8) | (glint << 12) | (model << 13) | (reserved << 15)


def independent_rule(raw: int | None, q: int | None, variant: str) -> bool:
    """Written directly from the MAIAC AOD_QA table and the review decisions, not from maiac_spec."""
    if raw is None or q is None:
        return False
    cloud, lwsi, adj = q & 7, (q >> 3) & 3, (q >> 5) & 7
    aodq, model, reserved = (q >> 8) & 15, (q >> 13) & 3, (q >> 15) & 1
    core = cloud == 1 and lwsi == 0 and aodq == 0
    guard = adj in (0, 1, 2, 3, 4, 5) and model in (0, 1, 2) and reserved == 0  # glint 0/1 always documented
    if variant == "product_range":
        return core and guard and -100 <= raw <= 8000
    if variant == "nonnegative_sensitivity":
        return core and guard and 0 <= raw <= 8000
    if variant == "adjacency_clear_sensitivity":
        return core and guard and adj == 0 and -100 <= raw <= 8000
    raise AssertionError(variant)


def test_method_json_is_coherent() -> None:
    assert spec.METHOD_VERSION == "maiac-aod550/0.2.0"
    assert [v.id for v in spec.VARIANTS] == ["product_range", "nonnegative_sensitivity", "adjacency_clear_sensitivity"]
    assert [v.role for v in spec.VARIANTS].count("primary") == 1 and spec.PRIMARY.id == "product_range"
    assert (spec.SCALE_FACTOR, spec.RAW_VALID_MIN, spec.RAW_VALID_MAX) == (0.001, -100, 8000)
    for v in spec.VARIANTS:
        assert spec.RAW_VALID_MIN <= v.raw_min <= v.raw_max <= spec.RAW_VALID_MAX
    bits = sorted(b for f in spec.QA_FIELDS.values() for b in range(f.start_bit, f.start_bit + f.n_bits))
    assert bits == list(range(16)), "QA fields must cover all 16 bits exactly once"


@pytest.mark.parametrize("variant", [v.id for v in spec.VARIANTS])
def test_exhaustive_truth_table(variant: str) -> None:
    v = spec.VARIANTS_BY_ID[variant]
    for raw in (None, -101, -100, -1, 0, 1, 7999, 8000, 8001):
        for q in range(1 << 16):
            assert spec.is_valid_retrieval(raw, q, v) is independent_rule(raw, q, variant), (raw, q)
        assert spec.is_valid_retrieval(raw, None, v) is False


def test_negative_aod_boundaries() -> None:
    p, nn = spec.PRIMARY, spec.VARIANTS_BY_ID["nonnegative_sensitivity"]
    assert spec.is_valid_retrieval(-100, qa(), p)  # AOD -0.100 kept in the primary series
    assert not spec.is_valid_retrieval(-101, qa(), p)  # below the product range
    assert spec.is_valid_retrieval(8000, qa(), p) and not spec.is_valid_retrieval(8001, qa(), p)
    assert not spec.is_valid_retrieval(-1, qa(), nn)  # excluded (not clamped) in the sensitivity variant
    assert spec.is_valid_retrieval(0, qa(), nn)
    assert spec.scale_raw_aod(-100) == pytest.approx(-0.1)  # no clamping anywhere
    assert spec.PRIMARY.aod_min == pytest.approx(-0.1) and nn.aod_min == 0.0


def test_adjacency_variants() -> None:
    p, adj = spec.PRIMARY, spec.VARIANTS_BY_ID["adjacency_clear_sensitivity"]
    for a in range(6):
        assert spec.is_valid_retrieval(100, qa(adjacency=a), p)
        assert spec.is_valid_retrieval(100, qa(adjacency=a), adj) is (a == 0)
    assert spec.decode_aod_qa(qa(adjacency=3))["adjacency"] == 3


@pytest.mark.parametrize("bad", [qa(adjacency=6), qa(adjacency=7), qa(model=3), qa(reserved=1)])
def test_undocumented_and_reserved_values_are_rejected_and_counted(bad: int) -> None:
    for v in spec.VARIANTS:
        assert not spec.is_valid_retrieval(100, bad, v)
    assert spec.is_guard_rejection(100, bad)
    assert not spec.is_guard_rejection(100, qa())
    assert not spec.is_guard_rejection(100, bad | 0b010)  # core already fails -> not a guard rejection
    assert not spec.is_guard_rejection(-101, bad)  # not present in the product range


def test_core_rejections() -> None:
    for bad in (
        qa(cloud=0),
        qa(cloud=2),
        qa(cloud=3),
        qa(cloud=4),
        qa(lwsi=1),
        qa(lwsi=2),
        qa(aodq=2),
        qa(aodq=3),
        qa(aodq=11),
        0,
    ):
        assert not spec.passes_core_qa(bad)
    assert spec.passes_core_qa(qa(glint=1, model=2))


def test_decode_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        spec.decode_aod_qa(70000)


def test_generated_artifacts_are_current() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "scripts.generate_method_artifacts", "--check"],
        cwd=ROOT / "api",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_protocol_and_parity_share_definitions() -> None:
    protocol = (ROOT / "docs" / "RESEARCH_PROTOCOL.md").read_text()
    for key, text in spec.STATISTIC_DEFINITIONS.items():
        assert f"`{key}`: {text}" in protocol, key
    js = (ROOT / "gee" / "maiac_parity_check.js").read_text()
    block = js.split("// BEGIN GENERATED METHOD - do not edit by hand\n")[1].split("// END GENERATED METHOD")[0]
    embedded = json.loads(block.strip().removeprefix("var METHOD = ").removesuffix(";"))
    assert embedded == spec.METHOD


def test_single_reduction_rule_in_source() -> None:
    py = (ROOT / "api" / "app" / "datasets" / "maiac_ee.py").read_text()
    js = (ROOT / "gee" / "maiac_parity_check.js").read_text()
    assert py.count(".reduceRegion(") == 1 and "reducer.unweighted()" in py
    assert js.count(".reduceRegion(") == 1 and "reducer.unweighted()" in js


def test_ee_module_has_no_hardcoded_constants() -> None:
    import re

    source = (ROOT / "api" / "app" / "datasets" / "maiac_ee.py").read_text()
    assert not re.search(r"0\.001|-100|8000|Optical_Depth_055|AOD_QA|MCD19A2", source)


def test_smoke_test_is_labelled_legacy() -> None:
    smoke = (ROOT / "gee" / "maiac_smoke_test.js").read_text()
    assert "LEGACY EXPLORATORY" in smoke and "not the acceptance parity" in smoke
