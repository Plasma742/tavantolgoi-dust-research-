import type { PolygonGeometry } from "../api/types";

export type LonLat = [number, number];
export type BBox = [number, number, number, number];

const EARTH_RADIUS_KM = 6371.0088;

/** Closed rectangle polygon from two corner clicks (planar lon/lat edges). */
export function rectangleFromCorners(a: LonLat, b: LonLat): PolygonGeometry {
  const round = (v: number) => Math.round(v * 1e6) / 1e6; // ~0.1 m; avoids float noise in the ROI hash
  const west = round(Math.min(a[0], b[0]));
  const east = round(Math.max(a[0], b[0]));
  const south = round(Math.min(a[1], b[1]));
  const north = round(Math.max(a[1], b[1]));
  return {
    type: "Polygon",
    coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
  };
}

function rings(geometry: PolygonGeometry): number[][][][] {
  return geometry.type === "Polygon"
    ? [geometry.coordinates as number[][][]]
    : (geometry.coordinates as number[][][][]);
}

export function bboxOf(geometry: PolygonGeometry): BBox {
  let w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
  for (const polygon of rings(geometry)) {
    for (const ring of polygon) {
      for (const [lon, lat] of ring as [number, number][]) {
        w = Math.min(w, lon); e = Math.max(e, lon); s = Math.min(s, lat); n = Math.max(n, lat);
      }
    }
  }
  return [w, s, e, n];
}

/** Spherical area approximation — same formula as the backend's request-size bound. */
export function approxAreaKm2(geometry: PolygonGeometry): number {
  let total = 0;
  for (const polygon of rings(geometry)) {
    polygon.forEach((ring, index) => {
      let sum = 0;
      for (let i = 0; i < ring.length - 1; i += 1) {
        const [lon1, lat1] = ring[i] as [number, number];
        const [lon2, lat2] = ring[i + 1] as [number, number];
        const rad = Math.PI / 180;
        sum += (lon2 - lon1) * rad * (2 + Math.sin(lat1 * rad) + Math.sin(lat2 * rad));
      }
      const area = (Math.abs(sum) * EARTH_RADIUS_KM ** 2) / 2;
      total += index === 0 ? area : -area;
    });
  }
  return total;
}

export function vertexCount(geometry: PolygonGeometry): number {
  return rings(geometry).reduce((acc, polygon) => acc + polygon.reduce((a, ring) => a + ring.length - 1, 0), 0);
}

export class RoiParseError extends Error {}

function isPosition(value: unknown): value is [number, number] {
  return Array.isArray(value) && value.length === 2 && value.every((v) => typeof v === "number" && Number.isFinite(v));
}

function checkPolygonCoords(coords: unknown): void {
  if (!Array.isArray(coords) || coords.length === 0) throw new RoiParseError("Polygon has no rings.");
  for (const ring of coords) {
    if (!Array.isArray(ring) || ring.length < 4) throw new RoiParseError("Each ring needs at least 4 positions.");
    for (const pos of ring) {
      if (!isPosition(pos)) {
        throw new RoiParseError("Positions must be [longitude, latitude] pairs in WGS84 degrees (2D only).");
      }
    }
  }
}

/**
 * Accept a GeoJSON Polygon/MultiPolygon geometry, a Feature, or a FeatureCollection with exactly
 * one polygonal feature. Returns only the geometry; the backend re-validates everything.
 */
export function parseRoiGeoJson(text: string): { geometry: PolygonGeometry; name: string | null } {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new RoiParseError("File is not valid JSON.");
  }
  let name: string | null = null;
  const obj = data as { type?: string; features?: unknown[]; geometry?: unknown; properties?: Record<string, unknown> };
  let geometry: unknown = data;
  if (obj?.type === "FeatureCollection") {
    const features = Array.isArray(obj.features) ? obj.features : [];
    if (features.length !== 1) {
      throw new RoiParseError(`FeatureCollection must contain exactly one feature (found ${features.length}).`);
    }
    const feature = features[0] as { geometry?: unknown; properties?: Record<string, unknown> };
    geometry = feature.geometry;
    name = typeof feature.properties?.name === "string" ? feature.properties.name : null;
  } else if (obj?.type === "Feature") {
    geometry = obj.geometry;
    name = typeof obj.properties?.name === "string" ? obj.properties.name : null;
  }
  const g = geometry as { type?: string; coordinates?: unknown; crs?: unknown };
  if (!g || (g.type !== "Polygon" && g.type !== "MultiPolygon")) {
    throw new RoiParseError("Geometry must be a Polygon or MultiPolygon.");
  }
  if (g.type === "Polygon") checkPolygonCoords(g.coordinates);
  else {
    if (!Array.isArray(g.coordinates) || g.coordinates.length === 0) throw new RoiParseError("MultiPolygon is empty.");
    g.coordinates.forEach(checkPolygonCoords);
  }
  return { geometry: { type: g.type, coordinates: g.coordinates } as PolygonGeometry, name };
}
