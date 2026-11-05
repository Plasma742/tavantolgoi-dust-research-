// @vitest-environment jsdom
// Component tests. All numbers below are synthetic test fixtures, not observations.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { LayerLegend, MonthlyRow, MonthlySeriesResponse, PeriodSummary, SensitivityResult } from "../api/types";
import { SeriesCharts, type ChartPoint } from "./charts/SeriesCharts";
import { LayerPanel } from "./LayerPanel";
import { SensitivityTable, SummaryPanel } from "./SummaryPanel";
import { TimeSeriesPanel } from "./TimeSeriesPanel";

afterEach(cleanup);

function sensitivity(variant: string, label: string, mean: number | null, dMean: number | null): SensitivityResult {
  return {
    variant, role: "sensitivity", label, definition: `${variant} rule`, status: mean === null ? "NO_VALID_OBSERVATIONS" : "OK",
    status_message: "", roi_mean_aod: mean, roi_pooled_retrieval_mean_aod: mean, valid_retrievals: 8,
    valid_retrievals_granule_sum: 8, pixels_with_valid: 3, coverage_fraction: 0.75, granules_with_valid: 2,
    valid_day_count: 2, consistency_check_passed: true,
    difference_vs_primary: { valid_retrievals: -2, valid_day_count: 0, pixels_with_valid: 0, coverage_fraction: 0,
      roi_mean_aod: dMean, roi_pooled_retrieval_mean_aod: dMean },
  };
}

function summary(overrides: Partial<PeriodSummary> = {}): PeriodSummary {
  return {
    method_version: "maiac-aod550/0.2.0", primary_variant: "product_range", status: "OK", status_message: "",
    time_start_utc: "2025-04-01T00:00:00Z", time_end_exclusive_utc: "2025-05-01T00:00:00Z", days_in_period: 30,
    roi_mean_aod: -0.012, roi_pooled_retrieval_mean_aod: -0.01, pixels_total: 4, pixels_with_valid: 3,
    coverage_fraction: 0.75, valid_retrievals: 10, valid_retrievals_granule_sum: 10, retrievals_before_qa: 12,
    qa_retention_fraction: 10 / 12, qa_guard_rejections: 0, granules_intersecting: 3, granules_with_valid: 2,
    valid_day_count: 2, consistency_check_passed: true,
    sensitivity: [
      sensitivity("nonnegative_sensitivity", "Sensitivity - non-negative AOD only", 0.02, 0.032),
      sensitivity("adjacency_clear_sensitivity", "Sensitivity - cloud-adjacency clear only", -0.015, -0.003),
    ],
    ...overrides,
  };
}

const POINTS: ChartPoint[] = [
  { month: "2025-01", status: "OK", mean: -0.04, pooledMean: -0.04, validDays: 5, daysInPeriod: 31, coverage: 0.5, validRetrievals: 9 },
  { month: "2025-02", status: "NO_VALID_OBSERVATIONS", mean: null, pooledMean: null, validDays: 0, daysInPeriod: 28, coverage: 0, validRetrievals: 0 },
  { month: "2025-03", status: "OK", mean: 0.3, pooledMean: 0.31, validDays: 12, daysInPeriod: 31, coverage: 0.9, validRetrievals: 40 },
];

describe("SeriesCharts", () => {
  it("extends the axis below zero for negative AOD and never draws missing months as zero", () => {
    const { container } = render(
      <SeriesCharts points={POINTS} variantLabel="Primary (product_range)" isSensitivity={false} selectedMonth={null} onSelect={() => {}} />,
    );
    const markers = screen.getAllByTestId("aod-marker");
    expect(markers.map((m) => m.getAttribute("data-month"))).toEqual(["2025-01", "2025-03"]);
    const gaps = screen.getAllByTestId("gap-band-aod");
    expect(gaps.map((g) => g.getAttribute("data-month"))).toEqual(["2025-02"]);
    const ticks = screen.getAllByTestId("aod-tick").map((t) => Number(t.getAttribute("data-value")));
    expect(Math.min(...ticks)).toBeLessThan(-0.04 + 1e-9);
    const zeroLine = screen.getAllByTestId("aod-tick").find((t) => Number(t.getAttribute("data-value")) === 0)!.querySelector("line")!;
    const janMarker = markers[0]!;
    expect(Number(janMarker.getAttribute("cy"))).toBeGreaterThan(Number(zeroLine.getAttribute("y1")));
    expect(container.textContent).toContain("-0.040");
    expect(container.textContent).not.toContain("Sensitivity — not the primary result");
  });

  it("labels sensitivity variants", () => {
    render(<SeriesCharts points={POINTS} variantLabel="Sensitivity - non-negative AOD only" isSensitivity selectedMonth={null} onSelect={() => {}} />);
    expect(screen.getByText("Sensitivity — not the primary result")).toBeTruthy();
  });
});

describe("SummaryPanel", () => {
  it("shows missing data as missing, never as zero", () => {
    const s = summary({ status: "NO_VALID_OBSERVATIONS", status_message: "Granules exist but none passed QA.", roi_mean_aod: null,
      roi_pooled_retrieval_mean_aod: null, valid_retrievals: 0, valid_retrievals_granule_sum: 0, pixels_with_valid: 0, coverage_fraction: 0 });
    const { container } = render(<SummaryPanel summary={s} onOpenProvenance={() => {}} />);
    expect(screen.getByTestId("roi-mean").textContent).toBe("No valid data");
    expect(screen.getByText("No valid observations")).toBeTruthy();
    expect(container.textContent).not.toContain("0.000");
  });

  it("shows negative primary means and the method version", () => {
    render(<SummaryPanel summary={summary()} onOpenProvenance={() => {}} />);
    expect(screen.getByTestId("roi-mean").textContent).toBe("-0.012");
    expect(screen.getByText("Method maiac-aod550/0.2.0")).toBeTruthy();
  });

  it("surfaces QA guard rejections", () => {
    render(<SummaryPanel summary={summary({ qa_guard_rejections: 3 })} onOpenProvenance={() => {}} />);
    expect(screen.getByText(/undocumented or reserved AOD_QA values/)).toBeTruthy();
  });
});

describe("SensitivityTable", () => {
  it("labels every sensitivity row and reports signed differences", () => {
    render(<SensitivityTable summary={summary()} />);
    expect(screen.getByText("not the primary result")).toBeTruthy();
    const table = screen.getByRole("table", { name: /Sensitivity variants/ });
    expect(within(table).getByText("non-negative AOD only")).toBeTruthy();
    expect(within(table).getByText("+0.032")).toBeTruthy();
    expect(within(table).getByText("-0.003")).toBeTruthy();
  });
});

describe("LayerPanel legend", () => {
  it("places negative AOD on the colour ramp", () => {
    const legend: LayerLegend = {
      kind: "continuous", title: "Mean AOD", unit: "dimensionless", palette: ["cde2fb", "0d366b"], min: -0.1, max: 1.0,
      ticks: [{ value: -0.1, label: "-0.10" }, { value: 0, label: "0.00" }, { value: 1, label: "≥1.00" }], note: "",
    };
    const layer = { id: "aod_mean", title: "AOD", observation_type: "satellite_retrieval", variant: "product_range",
      tile_url_template: "/api/tiles/x/{z}/{x}/{y}.png", max_native_zoom: 13, default_visible: true, default_opacity: 0.8, legend };
    render(<LayerPanel layers={[layer]} state={{}} dimBasemap onState={() => {}} onDimBasemap={() => {}} nativeScaleM={null} />);
    const neg = screen.getByText("-0.10");
    expect(neg.style.left).toBe("0%");
    const zero = screen.getAllByTestId("legend-mark").find((m) => Number(m.getAttribute("data-value")) === 0)!;
    expect(Number.parseFloat(zero.style.left)).toBeCloseTo((0.1 / 1.1) * 100, 5); // zero marked on the ramp
    expect(screen.queryByText("0.00")).toBeNull(); // label skipped: it would collide with "-0.10"
    expect(screen.getByText("≥1.00")).toBeTruthy();
  });
});

describe("TimeSeriesPanel", () => {
  it("switches to a sensitivity variant with an explicit label", () => {
    const row = (month: string): MonthlyRow => ({ ...summary(), month });
    const series: MonthlySeriesResponse = { dataset_key: "maiac_aod550", rows: [row("2025-03"), row("2025-04")], provenance: {} as never };
    render(
      <TimeSeriesPanel series={series} loading={false} error={null} startMonth="2025-03" endMonth="2025-04" maxMonths={36}
        canCompute disabledReason={null} selectedMonth={null} onRange={() => {}} onCompute={() => {}} onCsv={() => {}} onSelectMonth={() => {}} />,
    );
    expect(screen.queryByText(/Sensitivity variant — not the primary result/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Sensitivity: non-negative AOD only" }));
    expect(screen.getByText(/Sensitivity variant — not the primary result/)).toBeTruthy();
  });
});
