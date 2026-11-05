import { describe, expect, it } from "vitest";
import { fmtAod, fmtPct, fmtSigned, niceAxis, niceRange } from "./format";
import { addDays, monthBounds, monthsBetween, toApiWindow } from "./period";
import { approxAreaKm2, bboxOf, parseRoiGeoJson, rectangleFromCorners, RoiParseError, vertexCount } from "./roi";

describe("period helpers", () => {
  it("converts months to end-exclusive windows", () => {
    expect(monthBounds("2025-04")).toEqual({ start: "2025-04-01", endExclusive: "2025-05-01" });
    expect(monthBounds("2025-12")).toEqual({ start: "2025-12-01", endExclusive: "2026-01-01" });
  });
  it("turns an inclusive UI end date into an exclusive API end", () => {
    expect(toApiWindow({ mode: "range", month: "2025-04", start: "2025-04-10", endInclusive: "2025-04-20" }))
      .toEqual({ start: "2025-04-10", endExclusive: "2025-04-21" });
    expect(addDays("2024-02-28", 1)).toBe("2024-02-29");
  });
  it("counts months inclusively", () => {
    expect(monthsBetween("2025-01", "2025-12")).toBe(12);
    expect(monthsBetween("2024-11", "2025-02")).toBe(4);
  });
});

describe("formatting", () => {
  it("never renders missing AOD as zero", () => {
    expect(fmtAod(null)).toBe("No valid data");
    expect(fmtAod(0)).toBe("0.000");
    expect(fmtAod(0.123456)).toBe("0.123");
  });
  it("formats fractions", () => {
    expect(fmtPct(0.9167)).toBe("91.7%");
    expect(fmtPct(null)).toBe("—");
  });
  it("keeps negative AOD on the axis and never clips data", () => {
    const r = niceRange(-0.04, 0.37, 0.2);
    expect(r.bottom).toBeLessThanOrEqual(-0.04);
    expect(r.top).toBeGreaterThanOrEqual(0.37);
    expect(r.ticks).toContain(0);
    expect(niceRange(0.05, 0.3, 0.2).bottom).toBe(0);
    expect(fmtAod(-0.05)).toBe("-0.050");
    expect(fmtSigned(0.0123)).toBe("+0.012");
    expect(fmtSigned(null)).toBe("—");
  });
  it("builds a 0-based nice axis", () => {
    const axis = niceAxis(0.37, 0.1);
    expect(axis.ticks[0]).toBe(0);
    expect(axis.top).toBeGreaterThanOrEqual(0.37);
  });
});

describe("ROI helpers", () => {
  const rect = rectangleFromCorners([105.7, 43.8], [105.3, 43.5]);
  it("normalises corners into a closed ring", () => {
    expect(rect.coordinates).toEqual([[[105.3, 43.5], [105.7, 43.5], [105.7, 43.8], [105.3, 43.8], [105.3, 43.5]]]);
    expect(vertexCount(rect)).toBe(4);
    expect(bboxOf(rect)).toEqual([105.3, 43.5, 105.7, 43.8]);
  });
  it("matches the backend's spherical area formula", () => {
    const rad = Math.PI / 180;
    const expected = 6371.0088 ** 2 * 0.4 * rad * (Math.sin(43.8 * rad) - Math.sin(43.5 * rad));
    expect(approxAreaKm2(rect)).toBeCloseTo(expected, 6);
  });
  it("parses Features and single-feature collections", () => {
    const feature = { type: "Feature", properties: { name: "Control" }, geometry: rect };
    expect(parseRoiGeoJson(JSON.stringify(feature)).name).toBe("Control");
    const fc = { type: "FeatureCollection", features: [feature] };
    expect(parseRoiGeoJson(JSON.stringify(fc)).geometry.type).toBe("Polygon");
  });
  it("rejects unsupported input", () => {
    expect(() => parseRoiGeoJson("{")).toThrow(RoiParseError);
    expect(() => parseRoiGeoJson(JSON.stringify({ type: "Point", coordinates: [1, 2] }))).toThrow(RoiParseError);
    const two = { type: "FeatureCollection", features: [{ type: "Feature", geometry: rect }, { type: "Feature", geometry: rect }] };
    expect(() => parseRoiGeoJson(JSON.stringify(two))).toThrow(/exactly one/);
    const z = { type: "Polygon", coordinates: [[[1, 2, 3], [2, 2, 3], [2, 3, 3], [1, 2, 3]]] };
    expect(() => parseRoiGeoJson(JSON.stringify(z))).toThrow(/2D only/);
  });
});
