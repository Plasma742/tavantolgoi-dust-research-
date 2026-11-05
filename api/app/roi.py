"""Region-of-interest validation, hashing and the server-side ROI registry.

The platform never invents mine boundaries. An ROI is one of:

* ``demonstration``           — drawn by hand in the browser; explicitly NOT a mine boundary.
* ``unverified_upload``       — GeoJSON uploaded by the user, provenance unknown.
* ``user_declared_verified``  — uploaded with a source note; verification is the user's claim.
* ``registry``                — loaded from ``ROI_DIR`` on the server; its own metadata says
                                whether it is verified.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shapely.geometry import shape
from shapely.validation import explain_validity

from .errors import InvalidRoi

log = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0088  # IUGG mean radius; used only for the request-size bound
DECLARED_STATUSES = ("demonstration", "unverified_upload", "user_declared_verified", "registry")


@dataclass(frozen=True)
class ValidRoi:
    geometry: dict[str, Any]
    sha256: str
    approx_area_km2: float
    bbox: tuple[float, float, float, float]
    vertex_count: int


def _ring_area_km2(ring: list[list[float]]) -> float:
    """Spherical polygon ring area (Chamberlain & Duquette 2007). Bounding check only."""
    total = 0.0
    for (lon1, lat1), (lon2, lat2) in itertools.pairwise(ring):
        total += math.radians(lon2 - lon1) * (2 + math.sin(math.radians(lat1)) + math.sin(math.radians(lat2)))
    return abs(total) * EARTH_RADIUS_KM**2 / 2.0


def _polygons(geometry: dict[str, Any]) -> list[list[list[list[float]]]]:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype == "Polygon":
        return [coords]  # type: ignore[list-item]
    if gtype == "MultiPolygon":
        return list(coords)  # type: ignore[arg-type]
    raise InvalidRoi("ROI geometry must be a GeoJSON Polygon or MultiPolygon.")


def canonical_hash(geometry: dict[str, Any]) -> str:
    payload = json.dumps(geometry, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_roi(
    geometry: Any,
    *,
    max_area_km2: float,
    max_vertices: int,
    allowed_bbox: tuple[float, float, float, float],
) -> ValidRoi:
    if not isinstance(geometry, dict):
        raise InvalidRoi("ROI geometry must be a GeoJSON geometry object.")
    if set(geometry) - {"type", "coordinates"}:
        raise InvalidRoi("ROI geometry may only contain 'type' and 'coordinates'.")
    if not isinstance(geometry.get("coordinates"), list):
        raise InvalidRoi("ROI geometry 'coordinates' must be an array.")
    polygons = _polygons(geometry)
    if not polygons:
        raise InvalidRoi("ROI contains no polygons.")

    vertices = 0
    lons: list[float] = []
    lats: list[float] = []
    area = 0.0
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            raise InvalidRoi("Each polygon needs at least an exterior ring.")
        for ring_index, ring in enumerate(polygon):
            if not isinstance(ring, list) or len(ring) < 4:
                raise InvalidRoi("Each ring needs at least 4 positions (closed).")
            for pos in ring:
                if (
                    not isinstance(pos, list)
                    or len(pos) != 2
                    or not all(isinstance(v, int | float) and not isinstance(v, bool) for v in pos)
                ):
                    raise InvalidRoi("Positions must be [longitude, latitude] number pairs (no altitude).")
                lon, lat = float(pos[0]), float(pos[1])
                if not (math.isfinite(lon) and math.isfinite(lat)):
                    raise InvalidRoi("Coordinates must be finite numbers.")
                if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                    raise InvalidRoi("Coordinates must be WGS84 longitude/latitude in degrees.")
                lons.append(lon)
                lats.append(lat)
            if ring[0] != ring[-1]:
                raise InvalidRoi("Polygon rings must be closed (first position == last position).")
            vertices += len(ring) - 1
            ring_area = _ring_area_km2(ring)
            area += ring_area if ring_index == 0 else -ring_area

    if vertices > max_vertices:
        raise InvalidRoi(f"ROI has {vertices} vertices; the limit is {max_vertices}. Simplify it first.")

    try:
        geom = shape(geometry)
    except Exception as exc:  # shapely raises several types for malformed input
        raise InvalidRoi(f"ROI geometry could not be parsed: {exc}") from exc
    if not geom.is_valid:
        raise InvalidRoi(f"ROI geometry is invalid: {explain_validity(geom)}")
    if geom.is_empty or area <= 0:
        raise InvalidRoi("ROI has zero area.")

    west, south, east, north = min(lons), min(lats), max(lons), max(lats)
    aw, as_, ae, an = allowed_bbox
    if west < aw or east > ae or south < as_ or north > an:
        raise InvalidRoi(
            "ROI lies outside the configured study bounding box "
            f"({aw}, {as_}, {ae}, {an}); requests outside it are refused to protect compute quota.",
            details={"allowed_bbox": list(allowed_bbox)},
        )
    if area > max_area_km2:
        raise InvalidRoi(
            f"ROI area is about {area:,.0f} km²; the limit is {max_area_km2:,.0f} km².",
            details={"approx_area_km2": area, "max_area_km2": max_area_km2},
        )
    return ValidRoi(
        geometry={"type": geometry["type"], "coordinates": geometry["coordinates"]},
        sha256=canonical_hash(geometry),
        approx_area_km2=area,
        bbox=(west, south, east, north),
        vertex_count=vertices,
    )


# -- server-side registry ------------------------------------------------------------


@dataclass(frozen=True)
class RegistryEntry:
    id: str
    label: str
    verified: bool
    source: str | None
    license: str | None
    observation_date: str | None
    notes: str | None
    geometry: dict[str, Any]

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "verified": self.verified,
            "source": self.source,
            "license": self.license,
            "observation_date": self.observation_date,
            "notes": self.notes,
            "geometry": self.geometry,
        }


def load_registry(roi_dir: Path, **limits: Any) -> tuple[dict[str, RegistryEntry], list[dict[str, str]]]:
    """Load ``*.geojson`` Features from ``roi_dir``. Invalid files are reported, not used."""
    entries: dict[str, RegistryEntry] = {}
    problems: list[dict[str, str]] = []
    if not roi_dir.is_dir():
        return entries, problems
    for path in sorted(roi_dir.glob("*.geojson")):
        try:
            feature = json.loads(path.read_text(encoding="utf-8"))
            if feature.get("type") != "Feature":
                raise InvalidRoi("file must contain a single GeoJSON Feature")
            props = feature.get("properties") or {}
            roi_id = str(props.get("id") or path.stem)
            valid = validate_roi(feature.get("geometry"), **limits)
            entries[roi_id] = RegistryEntry(
                id=roi_id,
                label=str(props.get("label") or roi_id),
                verified=props.get("verification_status") == "verified",
                source=props.get("source"),
                license=props.get("license"),
                observation_date=props.get("observation_date"),
                notes=props.get("notes"),
                geometry=valid.geometry,
            )
        except (OSError, ValueError, InvalidRoi) as exc:
            message = exc.message if isinstance(exc, InvalidRoi) else str(exc)
            log.warning("Skipping ROI file %s: %s", path.name, message)
            problems.append({"file": path.name, "problem": message})
    return entries, problems
