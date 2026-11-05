"""API behaviour with Earth Engine NOT_CONFIGURED and with a fake engine (fixture values only)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.datasets import maiac_spec as spec
from app.main import create_app
from app.tiles import TRANSPARENT_PNG

from .conftest import TEST_RECT, FakeEngine, FakeRuntime, make_settings, roi_payload

APRIL = {"start": "2025-04-01", "end_exclusive": "2025-05-01"}


# -- NOT_CONFIGURED ------------------------------------------------------------------


def test_health_reports_not_configured(unconfigured_client: TestClient) -> None:
    body = unconfigured_client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["earth_engine"]["status"] == "NOT_CONFIGURED"
    assert body["earth_engine"]["project_configured"] is False


def test_layer_refuses_without_configuration(unconfigured_client: TestClient) -> None:
    res = unconfigured_client.post("/api/layers/maiac_aod550", json={"roi": roi_payload(), **APRIL})
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "NOT_CONFIGURED"


def test_series_refuses_without_configuration(unconfigured_client: TestClient) -> None:
    res = unconfigured_client.post(
        "/api/stats/maiac_aod550/monthly", json={"roi": roi_payload(), "start_month": "2025-01", "end_month": "2025-12"}
    )
    assert res.status_code == 503 and res.json()["error"]["code"] == "NOT_CONFIGURED"


def test_input_validated_before_configuration_check(unconfigured_client: TestClient) -> None:
    bad = {"type": "Polygon", "coordinates": [[[10, 43], [10.5, 43], [10.5, 43.5], [10, 43]]]}
    res = unconfigured_client.post("/api/layers/maiac_aod550", json={"roi": roi_payload(geometry=bad), **APRIL})
    assert res.status_code == 400 and res.json()["error"]["code"] == "INVALID_ROI"


def test_dataset_catalog(unconfigured_client: TestClient) -> None:
    body = unconfigured_client.get("/api/datasets").json()
    status = {d["key"]: d["status"] for d in body["datasets"]}
    assert status == {
        "maiac_aod550": "implemented",
        "era5_land_wind": "planned",
        "sentinel2_sr": "planned",
        "s5p_aai": "planned",
        "merra2_dust": "planned",
    }
    assert {m["key"] for m in body["unavailable_modules"]} >= {"dispersion_model", "mine_contribution"}
    maiac = next(d for d in body["datasets"] if d["key"] == "maiac_aod550")
    assert "PM10" in maiac["not_a_measurement_of"]


def test_planned_and_unknown_datasets(unconfigured_client: TestClient) -> None:
    res = unconfigured_client.post("/api/layers/era5_land_wind", json={"roi": roi_payload(), **APRIL})
    assert res.status_code == 501 and res.json()["error"]["code"] == "NOT_IMPLEMENTED"
    res = unconfigured_client.post("/api/layers/nope", json={"roi": roi_payload(), **APRIL})
    assert res.status_code == 404 and res.json()["error"]["code"] == "UNKNOWN_DATASET"


def test_methods_publish_canonical_method(unconfigured_client: TestClient) -> None:
    body = unconfigured_client.get("/api/methods").json()
    assert body["method_version"] == spec.METHOD_VERSION
    assert body["maiac"]["scale_factor"] == 0.001
    assert body["maiac"]["method"]["statistic_definitions"] == spec.STATISTIC_DEFINITIONS
    assert "legacy" in body["maiac"]["parity_scripts"]["legacy_exploratory"]


def test_request_validation(unconfigured_client: TestClient) -> None:
    res = unconfigured_client.post(
        "/api/layers/maiac_aod550", json={"roi": roi_payload(declared_status="user_declared_verified"), **APRIL}
    )
    assert res.status_code == 422 and res.json()["error"]["code"] == "VALIDATION_ERROR"
    res = unconfigured_client.post("/api/layers/maiac_aod550", json={"roi": roi_payload(), "start": "2025-04-01"})
    assert res.status_code == 422
    res = unconfigured_client.post("/api/layers/maiac_aod550", json={"roi": roi_payload(), **APRIL, "extra": 1})
    assert res.status_code == 422


def test_body_size_limit(tmp_path: Path) -> None:
    client = TestClient(create_app(make_settings(tmp_path, max_request_bytes=200)))
    res = client.post("/api/layers/maiac_aod550", json={"roi": roi_payload(), **APRIL})
    assert res.status_code == 413 and res.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_body_size_limit_without_content_length(tmp_path: Path) -> None:
    """Chunked uploads carry no Content-Length; the streamed bytes must still be bounded."""
    client = TestClient(create_app(make_settings(tmp_path, max_request_bytes=200)))

    def chunks():
        yield b'{"roi": {"label": "x", "declared_status": "demonstration", "geometry": '
        yield b'{"type": "Polygon", "coordinates": [[' + b"[105.0, 43.0], " * 40 + b"[105.0, 43.0]]]}}}"

    res = client.post("/api/layers/maiac_aod550", content=chunks(), headers={"content-type": "application/json"})
    assert res.status_code == 413


# -- fake engine (fixture values) ----------------------------------------------------


def test_layer_ok(fake_client: TestClient, engine: FakeEngine) -> None:
    res = fake_client.post("/api/layers/maiac_aod550", json={"roi": roi_payload(), **APRIL})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "OK"
    assert [layer["id"] for layer in body["layers"]] == ["aod_mean", "valid_count", "no_valid_retrieval"]
    for layer in body["layers"]:
        assert layer["tile_url_template"].startswith("/api/tiles/")
        assert "googleapis" not in layer["tile_url_template"]
        assert layer["variant"] == "product_range"
    legend = body["layers"][0]["legend"]
    assert legend["palette"] == spec.AOD_VIS["palette"] and legend["min"] == -0.1  # negatives shown, not clamped
    assert legend["ticks"][0] == {"value": -0.1, "label": "-0.10"}
    s = body["summary"]
    assert s["method_version"] == "maiac-aod550/0.2.0" and s["primary_variant"] == "product_range"
    assert s["roi_mean_aod"] == pytest.approx((0.05 + 0.40 + 0.20) / 3)
    assert s["roi_pooled_retrieval_mean_aod"] == pytest.approx(1.10 / 5)
    assert s["coverage_fraction"] == 0.75 and s["valid_retrievals"] == s["valid_retrievals_granule_sum"] == 5
    assert s["qa_retention_fraction"] == 1.0 and s["qa_guard_rejections"] == 0
    assert s["consistency_check_passed"] is True
    sens = {x["variant"]: x for x in s["sensitivity"]}
    assert sens["nonnegative_sensitivity"]["difference_vs_primary"]["valid_retrievals"] == -1
    assert sens["adjacency_clear_sensitivity"]["difference_vs_primary"]["valid_retrievals"] == -1
    prov = body["provenance"]
    assert prov["dataset_id"] == spec.COLLECTION_ID and prov["method_version"] == spec.METHOD_VERSION
    assert prov["scale_factor"] == 0.001 and prov["unit"] == "dimensionless"
    assert prov["quality_filter"]["physical_range"] == [pytest.approx(-0.1), pytest.approx(8.0)]
    assert prov["quality_filter"]["clamping"] == "none"
    assert [v["id"] for v in prov["variants"]] == [v.id for v in spec.VARIANTS]
    assert prov["statistic_definitions"] == spec.STATISTIC_DEFINITIONS
    assert prov["roi"]["declared_status"] == "demonstration"
    assert "NOT a verified mine boundary" in prov["roi"]["status_description"]
    assert prov["processing"]["code_revision"] == "test-rev"
    assert "PM10" in prov["not_a_measurement_of"]
    assert prov["spatial"]["native_grid_reported_by_earth_engine"]["crs"] == "SR-ORG:6974"


def test_layer_cached(fake_client: TestClient, engine: FakeEngine) -> None:
    first = fake_client.post("/api/layers/maiac_aod550", json={"roi": roi_payload(), **APRIL}).json()
    second = fake_client.post("/api/layers/maiac_aod550", json={"roi": roi_payload(label="renamed"), **APRIL}).json()
    assert len(engine.stats_calls) == 1
    assert second["provenance"]["processing"]["served_from_cache"] is True
    assert second["provenance"]["roi"]["label"] == "renamed"
    assert first["layers"][0]["tile_url_template"] == second["layers"][0]["tile_url_template"]


def test_layer_no_granules(fake_client: TestClient) -> None:
    body = fake_client.post(
        "/api/layers/maiac_aod550", json={"roi": roi_payload(), "start": "2025-02-01", "end_exclusive": "2025-03-01"}
    ).json()
    assert body["status"] == "NO_GRANULES" and body["layers"] == []
    assert body["summary"]["roi_mean_aod"] is None
    assert "not zero" in body["summary"]["status_message"]


def test_layer_no_valid_observations(fake_client: TestClient) -> None:
    body = fake_client.post(
        "/api/layers/maiac_aod550", json={"roi": roi_payload(), "start": "2025-03-01", "end_exclusive": "2025-04-01"}
    ).json()
    assert body["status"] == "NO_VALID_OBSERVATIONS"
    assert body["summary"]["roi_mean_aod"] is None and body["summary"]["coverage_fraction"] == 0
    assert all(x["roi_mean_aod"] is None for x in body["summary"]["sensitivity"])
    assert len(body["layers"]) == 3  # the grey 'no valid retrieval' layer makes the gap visible


def test_tile_proxy(fake_client: TestClient, engine: FakeEngine) -> None:
    body = fake_client.post("/api/layers/maiac_aod550", json={"roi": roi_payload(), **APRIL}).json()
    template = body["layers"][0]["tile_url_template"]
    # z=8 tile containing (105.5E, 43.65N)
    inside = template.format(z=8, x=203, y=93)
    res = fake_client.get(inside)
    assert res.status_code == 200 and res.content.endswith(b"aod_mean")
    assert engine.fetchers["aod_mean"].calls == [(8, 203, 93)]
    outside = template.format(z=8, x=10, y=10)
    res = fake_client.get(outside)
    assert res.content == TRANSPARENT_PNG and len(engine.fetchers["aod_mean"].calls) == 1
    assert fake_client.get(template.format(z=20, x=0, y=0)).status_code == 400
    expired = fake_client.get("/api/tiles/unknown-id/8/203/93.png")
    assert expired.status_code == 410 and expired.json()["error"]["code"] == "TILE_EXPIRED"


def test_monthly_series_and_csv(fake_client: TestClient, engine: FakeEngine) -> None:
    req = {"roi": roi_payload(), "start_month": "2025-01", "end_month": "2025-06"}
    body = fake_client.post("/api/stats/maiac_aod550/monthly", json=req).json()
    rows = {r["month"]: r for r in body["rows"]}
    assert list(rows) == ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06"]
    assert rows["2025-02"]["status"] == "NO_GRANULES"
    assert rows["2025-03"]["status"] == "NO_VALID_OBSERVATIONS" and rows["2025-03"]["roi_mean_aod"] is None
    assert rows["2025-04"]["days_in_period"] == 30
    assert len(body["provenance"]["periods"]) == 6
    calls = len(engine.stats_calls)

    res = fake_client.post("/api/stats/maiac_aod550/monthly.csv", json=req)
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/csv")
    assert len(engine.stats_calls) == calls  # served from cache
    lines = res.text.splitlines()
    assert "# dataset_id: MODIS/061/MCD19A2_GRANULES" in lines
    assert "# method_version: maiac-aod550/0.2.0" in lines
    assert any(line.startswith("# not_a_measurement_of: PM10") for line in lines)
    for key, text in spec.STATISTIC_DEFINITIONS.items():
        assert f"# definition.{key}: {text}" in lines
    rows = list(csv.DictReader(line for line in lines if not line.startswith("#")))
    assert len(rows) == 6 * 3  # one row per month and variant (long format)
    feb = [r for r in rows if r["month"] == "2025-02"]
    assert {r["status"] for r in feb} == {"NO_GRANULES"} and {r["roi_mean_aod"] for r in feb} == {""}
    apr = {r["variant"]: r for r in rows if r["month"] == "2025-04"}
    assert apr["product_range"]["variant_role"] == "primary"
    assert apr["product_range"]["roi_mean_aod"] == f"{(0.05 + 0.40 + 0.20) / 3:.3f}"
    assert apr["product_range"]["roi_pooled_retrieval_mean_aod"] == "0.220"
    assert apr["nonnegative_sensitivity"]["variant_role"] == "sensitivity"
    assert apr["nonnegative_sensitivity"]["diff_vs_primary_valid_retrievals"] == "-1"


def test_csv_neutralises_formula_injection(fake_client: TestClient) -> None:
    req = {"roi": roi_payload(label="=HYPERLINK(1)"), "start_month": "2025-04", "end_month": "2025-04"}
    text = fake_client.post("/api/stats/maiac_aod550/monthly.csv", json=req).text
    assert "# roi_label: '=HYPERLINK(1)" in text


def test_registry_roi(tmp_path: Path) -> None:
    roi_dir = tmp_path / "roi"
    roi_dir.mkdir()
    (roi_dir / "control.geojson").write_text(
        json.dumps(
            {
                "type": "Feature",
                "geometry": TEST_RECT,
                "properties": {
                    "id": "control-a",
                    "label": "Control A",
                    "verification_status": "unverified",
                    "source": "test fixture",
                },
            }
        )
    )
    engine = FakeEngine()
    client = TestClient(
        create_app(
            make_settings(tmp_path, roi_dir=roi_dir),
            runtime=FakeRuntime(),  # type: ignore[arg-type]
            engine_factory=lambda: engine,
        )
    )
    listed = client.get("/api/rois").json()
    assert [r["id"] for r in listed["rois"]] == ["control-a"] and listed["rois"][0]["verified"] is False
    body = client.post(
        "/api/layers/maiac_aod550",
        json={"roi": {"registry_id": "control-a", "label": "ignored", "declared_status": "registry"}, **APRIL},
    ).json()
    assert body["provenance"]["roi"]["registry_id"] == "control-a"
    assert body["provenance"]["roi"]["registry_verified"] is False
    missing = client.post(
        "/api/layers/maiac_aod550",
        json={"roi": {"registry_id": "nope", "label": "x", "declared_status": "registry"}, **APRIL},
    )
    assert missing.status_code == 400
