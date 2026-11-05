from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

import pytest

from app.errors import InvalidPeriod, InvalidRoi
from app.periods import month_period, validate_month_range, validate_window
from app.roi import EARTH_RADIUS_KM, canonical_hash, load_registry, validate_roi

from .conftest import TEST_RECT

LIMITS = {"max_area_km2": 10_000.0, "max_vertices": 2_000, "allowed_bbox": (87.0, 41.0, 120.0, 52.5)}
EARLIEST = date(2000, 2, 24)


def rect(w: float, s: float, e: float, n: float) -> dict:
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


def test_valid_rectangle_area_matches_spherical_formula() -> None:
    valid = validate_roi(TEST_RECT, **LIMITS)
    expected = EARTH_RADIUS_KM**2 * math.radians(0.4) * (math.sin(math.radians(43.8)) - math.sin(math.radians(43.5)))
    assert valid.approx_area_km2 == pytest.approx(expected, rel=1e-9)
    assert valid.vertex_count == 4
    assert valid.bbox == (105.3, 43.5, 105.7, 43.8)


def test_hash_ignores_key_order() -> None:
    reordered = {"coordinates": TEST_RECT["coordinates"], "type": "Polygon"}
    assert canonical_hash(reordered) == canonical_hash(TEST_RECT)


def test_hole_reduces_area() -> None:
    outer = rect(105.0, 43.0, 106.0, 44.0)["coordinates"][0]
    hole = [[105.4, 43.4], [105.4, 43.6], [105.6, 43.6], [105.6, 43.4], [105.4, 43.4]]
    with_hole = validate_roi({"type": "Polygon", "coordinates": [outer, hole]}, **LIMITS)
    without = validate_roi(rect(105.0, 43.0, 106.0, 44.0), **LIMITS)
    assert with_hole.approx_area_km2 < without.approx_area_km2


def test_multipolygon_accepted() -> None:
    geom = {
        "type": "MultiPolygon",
        "coordinates": [rect(105.0, 43.0, 105.2, 43.2)["coordinates"], rect(105.5, 43.5, 105.7, 43.7)["coordinates"]],
    }
    assert validate_roi(geom, **LIMITS).vertex_count == 8


@pytest.mark.parametrize(
    ("geometry", "fragment"),
    [
        ({"type": "Point", "coordinates": [105, 43]}, "Polygon or MultiPolygon"),
        ({"type": "Polygon", "coordinates": [[[105, 43], [106, 43], [106, 44], [105, 44]]]}, "closed"),
        (
            {"type": "Polygon", "coordinates": [[[105, 43, 10], [106, 43, 10], [106, 44, 10], [105, 43, 10]]]},
            "longitude, latitude",
        ),
        ({"type": "Polygon", "coordinates": [[[105, 43], [True, 43], [106, 44], [105, 43]]]}, "longitude, latitude"),
        ({"type": "Polygon", "coordinates": [[[105, 43], [106, 44], [106, 43], [105, 44], [105, 43]]]}, "invalid"),
        (rect(10.0, 43.0, 10.5, 43.5), "outside the configured study bounding box"),
        (rect(100.0, 42.0, 110.0, 46.0), "limit is"),
        ({"type": "Polygon", "coordinates": [[[105, 43], [105, 43], [105, 43], [105, 43]]]}, "invalid"),
        ({"type": "Polygon", "coordinates": "nope"}, "must be an array"),
        ({"type": "Polygon", "coordinates": [], "crs": "x"}, "only contain"),
        ("not a dict", "geometry object"),
    ],
)
def test_invalid_rois(geometry: object, fragment: str) -> None:
    with pytest.raises(InvalidRoi) as info:
        validate_roi(geometry, **LIMITS)
    assert fragment in info.value.message


def test_non_finite_coordinates_rejected() -> None:
    geom = {"type": "Polygon", "coordinates": [[[105, 43], [float("nan"), 43], [106, 44], [105, 43]]]}
    with pytest.raises(InvalidRoi):
        validate_roi(geom, **LIMITS)


def test_vertex_limit() -> None:
    n = 50
    ring = [[105 + 0.2 * math.cos(2 * math.pi * i / n), 43.6 + 0.2 * math.sin(2 * math.pi * i / n)] for i in range(n)]
    ring.append(ring[0])
    with pytest.raises(InvalidRoi, match="vertices"):
        validate_roi({"type": "Polygon", "coordinates": [ring]}, **{**LIMITS, "max_vertices": 10})


def test_registry_loads_valid_and_reports_invalid(tmp_path: Path) -> None:
    (tmp_path / "good.geojson").write_text(
        json.dumps(
            {
                "type": "Feature",
                "geometry": TEST_RECT,
                "properties": {
                    "id": "control-a",
                    "label": "Control A",
                    "verification_status": "verified",
                    "source": "test fixture",
                    "license": "n/a",
                },
            }
        )
    )
    (tmp_path / "bad.geojson").write_text(json.dumps({"type": "Feature", "geometry": rect(0, 0, 1, 1)}))
    (tmp_path / "broken.geojson").write_text("{not json")
    entries, problems = load_registry(tmp_path, **LIMITS)
    assert list(entries) == ["control-a"] and entries["control-a"].verified
    assert {p["file"] for p in problems} == {"bad.geojson", "broken.geojson"}


# -- periods -------------------------------------------------------------------------


def test_month_periods() -> None:
    assert month_period("2025-04").days == 30
    assert month_period("2024-02").days == 29
    dec = month_period("2025-12")
    assert (dec.start, dec.end_exclusive) == (date(2025, 12, 1), date(2026, 1, 1))
    with pytest.raises(InvalidPeriod):
        month_period("2025-13")


def test_window_rules() -> None:
    today = date(2026, 11, 4)
    p = validate_window(date(2025, 4, 1), date(2025, 5, 1), max_days=31, earliest=EARLIEST, today=today)
    assert p.days == 30
    with pytest.raises(InvalidPeriod, match="after start"):
        validate_window(date(2025, 4, 2), date(2025, 4, 1), max_days=31, earliest=EARLIEST, today=today)
    with pytest.raises(InvalidPeriod, match="limit is 31"):
        validate_window(date(2025, 1, 1), date(2025, 3, 1), max_days=31, earliest=EARLIEST, today=today)
    with pytest.raises(InvalidPeriod, match="first available"):
        validate_window(date(1999, 1, 1), date(1999, 1, 20), max_days=31, earliest=EARLIEST, today=today)
    with pytest.raises(InvalidPeriod, match="not ended"):
        validate_window(date(2026, 11, 1), date(2026, 11, 10), max_days=31, earliest=EARLIEST, today=today)


def test_month_range() -> None:
    today = date(2026, 11, 4)
    months = validate_month_range("2024-11", "2025-04", max_months=36, earliest=EARLIEST, today=today)
    assert [m for m, _ in months] == ["2024-11", "2024-12", "2025-01", "2025-02", "2025-03", "2025-04"]
    with pytest.raises(InvalidPeriod, match="has not ended"):
        validate_month_range("2026-01", "2026-11", max_months=36, earliest=EARLIEST, today=today)
    with pytest.raises(InvalidPeriod, match=r"more than|limit is"):
        validate_month_range("2018-01", "2025-12", max_months=36, earliest=EARLIEST, today=today)
    with pytest.raises(InvalidPeriod, match="before start_month"):
        validate_month_range("2025-05", "2025-04", max_months=36, earliest=EARLIEST, today=today)
