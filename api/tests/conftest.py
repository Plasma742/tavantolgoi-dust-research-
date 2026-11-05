"""Shared fixtures. The fake engine returns SYNTHETIC numbers only - never observations."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, load_settings
from app.datasets.maiac_reference import Granule, reference_period_stats
from app.main import create_app

# A small rectangle in the Gobi, used only as a test geometry. It is NOT a mine boundary.
TEST_RECT = {
    "type": "Polygon",
    "coordinates": [[[105.30, 43.50], [105.70, 43.50], [105.70, 43.80], [105.30, 43.80], [105.30, 43.50]]],
}


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    base = replace(load_settings(), ee_project_id=None, roi_dir=tmp_path / "roi", code_revision="test-rev")
    return replace(base, **overrides)


class FakeRuntime:
    """Pretends Earth Engine initialised. Only used with FakeEngine."""

    earthengine_api_version = "fake"

    def ensure_ready(self) -> None:
        return None

    def snapshot(self) -> dict[str, Any]:
        return {
            "status": "READY",
            "message": None,
            "project_configured": True,
            "auth_mode": "fake",
            "earthengine_api_version": "fake",
        }


class FakeFetcher:
    def __init__(self, name: str):
        self.name = name
        self.calls: list[tuple[int, int, int]] = []

    def fetch_tile(self, x: float, y: float, z: float) -> bytes:
        self.calls.append((int(z), int(x), int(y)))
        return b"\x89PNG-fixture-" + self.name.encode()


GOOD_QA = 0b001
ADJ1_QA = GOOD_QA | (1 << 5)
CLOUDY_QA = 0b011
ROI_PIXELS = {(0, 0), (1, 0), (2, 0), (3, 0)}


class FakeEngine:
    """Deterministic SYNTHETIC values produced by the reference model (never real data).

    * 2025-02 -> no granules
    * 2025-03 -> granules but every retrieval cloudy
    * otherwise -> 4-pixel synthetic grid with one negative AOD and one adjacency-flagged retrieval
    """

    def __init__(self) -> None:
        self.stats_calls: list[tuple[date, date]] = []
        self.fetchers: dict[str, FakeFetcher] = {}

    def native_grid(self) -> dict[str, Any]:
        return {"crs": "SR-ORG:6974", "nominal_scale_m": 926.6254330555, "crs_transform": None}

    def period_stats(self, geometry: dict[str, Any], start: date, end_exclusive: date) -> dict[str, Any]:
        self.stats_calls.append((start, end_exclusive))
        day = start.isoformat()
        if (start.year, start.month) == (2025, 2):
            return reference_period_stats([], ROI_PIXELS)
        if (start.year, start.month) == (2025, 3):
            return reference_period_stats([Granule(day, {px: (100, CLOUDY_QA) for px in ROI_PIXELS})], ROI_PIXELS)
        g1 = Granule(day, {(0, 0): (-50, GOOD_QA), (1, 0): (300, ADJ1_QA), (2, 0): (200, GOOD_QA)})
        g2 = Granule(start.replace(day=5).isoformat(), {(0, 0): (150, GOOD_QA), (1, 0): (500, GOOD_QA)})
        return reference_period_stats([g1, g2], ROI_PIXELS)

    def layer_fetchers(self, geometry: dict[str, Any], start: date, end_exclusive: date) -> dict[str, FakeFetcher]:
        self.fetchers = {k: FakeFetcher(k) for k in ("aod_mean", "valid_count", "no_valid_retrieval")}
        return self.fetchers  # type: ignore[return-value]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def unconfigured_client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


@pytest.fixture
def engine() -> FakeEngine:
    return FakeEngine()


@pytest.fixture
def fake_client(settings: Settings, engine: FakeEngine) -> TestClient:
    app = create_app(settings, runtime=FakeRuntime(), engine_factory=lambda: engine)  # type: ignore[arg-type]
    return TestClient(app)


def roi_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "geometry": TEST_RECT,
        "label": "Test rectangle (not a mine boundary)",
        "declared_status": "demonstration",
    }
    payload.update(overrides)
    return payload
