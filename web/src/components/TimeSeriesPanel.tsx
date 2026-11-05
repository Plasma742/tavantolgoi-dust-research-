import { useState } from "react";
import type { MonthlySeriesResponse } from "../api/types";
import { fmtAod, fmtInt, fmtPct, fmtSigned, fmtSignedInt, monthLabel } from "../lib/format";
import { monthsBetween } from "../lib/period";
import { variantOptions, variantView } from "../lib/variants";
import { SeriesCharts, type ChartPoint } from "./charts/SeriesCharts";

interface Props {
  series: MonthlySeriesResponse | null;
  loading: boolean;
  error: string | null;
  startMonth: string;
  endMonth: string;
  maxMonths: number;
  canCompute: boolean;
  disabledReason: string | null;
  selectedMonth: string | null;
  onRange: (start: string, end: string) => void;
  onCompute: () => void;
  onCsv: () => void;
  onSelectMonth: (month: string) => void;
}

export function TimeSeriesPanel(props: Props) {
  const { series, loading, error, startMonth, endMonth, maxMonths, canCompute, disabledReason, selectedMonth } = props;
  const [showTable, setShowTable] = useState(false);
  const [variantId, setVariantId] = useState<string | null>(null);
  const count = monthsBetween(startMonth, endMonth);
  const rangeProblem = count < 1 ? "End month is before start month." : count > maxMonths ? `Limit is ${maxMonths} months.` : null;

  const first = series?.rows[0];
  const options = first ? variantOptions(first) : [];
  const selected = options.find((o) => o.id === variantId) ?? options[0];
  const views = series && selected ? series.rows.map((r) => ({ row: r, v: variantView(r, selected.id) })) : [];
  const failedChecks = views.filter(({ v }) => !v.consistency_check_passed).length;
  const guardRows = series?.rows.filter((r) => r.qa_guard_rejections > 0).length ?? 0;
  const points: ChartPoint[] = views.map(({ row, v }) => ({
    month: row.month, status: v.status, mean: v.roi_mean_aod, pooledMean: v.roi_pooled_retrieval_mean_aod,
    validDays: v.valid_day_count, daysInPeriod: row.days_in_period, coverage: v.coverage_fraction,
    validRetrievals: v.valid_retrievals,
  }));
  const isSensitivity = selected?.role === "sensitivity";

  return (
    <section className="series" aria-labelledby="series-h">
      <div className="series-head">
        <h2 id="series-h">Monthly ROI time series · MAIAC AOD 550 nm</h2>
        <label className="field">
          From
          <input type="month" value={startMonth} min="2000-03" onChange={(e) => e.target.value && props.onRange(e.target.value, endMonth)} />
        </label>
        <label className="field">
          To (inclusive)
          <input type="month" value={endMonth} min={startMonth} onChange={(e) => e.target.value && props.onRange(startMonth, e.target.value)} />
        </label>
        <button className="btn primary" type="button" onClick={props.onCompute} disabled={!canCompute || loading || rangeProblem !== null}>
          {loading ? "Computing…" : `Compute ${count > 0 ? count : ""} months`}
        </button>
        <button className="btn" type="button" onClick={props.onCsv} disabled={!series || loading}>Export CSV</button>
        <button className="btn" type="button" aria-pressed={showTable} onClick={() => setShowTable((v) => !v)} disabled={!series}>
          {showTable ? "Show chart" : "Show table"}
        </button>
      </div>
      {rangeProblem && <p className="small muted">{rangeProblem}</p>}
      {disabledReason && !series && <p className="small muted">{disabledReason}</p>}
      {error && <div className="callout critical" role="alert"><span className="icon">✕</span>{error}</div>}
      {!series && !error && (
        <p className="small muted">
          No series computed. Each month is an Earth Engine computation counted against the project's monthly EECU quota,
          so the series is computed only when you ask for it.
        </p>
      )}
      {series && selected && (
        <div className={loading ? "refetching" : undefined}>
          <div className="row" style={{ marginBottom: 6 }}>
            <span className="small secondary">Variant:</span>
            <div className="segmented" role="group" aria-label="Processing variant">
              {options.map((o) => (
                <button key={o.id} type="button" aria-pressed={o.id === selected.id} onClick={() => setVariantId(o.id)}>
                  {o.role === "primary" ? "Primary" : o.label.replace(/^Sensitivity - /, "Sensitivity: ")}
                </button>
              ))}
            </div>
          </div>
          {isSensitivity && (
            <div className="callout warning" role="note" style={{ marginBottom: 6 }}>
              <span className="icon">!</span><strong>Sensitivity variant — not the primary result.</strong> {selected.label}. Use it
              only to judge how much the conclusions depend on this processing choice.
            </div>
          )}
          {failedChecks > 0 && (
            <div className="callout critical" role="alert">
              <span className="icon">✕</span>{failedChecks} month(s) failed the internal count-consistency check. Treat them as unreliable.
            </div>
          )}
          {guardRows > 0 && (
            <div className="callout warning" role="note">
              <span className="icon">!</span>{guardRows} month(s) contain retrievals rejected for undocumented or reserved AOD_QA values (see table).
            </div>
          )}
          {showTable ? (
            <div className="table-scroll">
              <table className="data tabular">
                <thead>
                  <tr>
                    <th>Month</th><th>Status</th><th>Mean of pixel means</th><th>Pooled mean</th><th>Valid days</th>
                    <th>Coverage</th><th>Valid retrievals</th>
                    {isSensitivity && <><th>Δ mean vs primary</th><th>Δ retrievals</th><th>Δ valid days</th><th>Δ coverage</th></>}
                    <th>QA guard rejections</th><th>Check</th>
                  </tr>
                </thead>
                <tbody>
                  {views.map(({ row, v }) => (
                    <tr key={row.month}>
                      <td>{monthLabel(row.month)}</td>
                      <td>{v.status}</td>
                      <td>{v.status === "OK" ? fmtAod(v.roi_mean_aod) : "—"}</td>
                      <td>{v.status === "OK" ? fmtAod(v.roi_pooled_retrieval_mean_aod) : "—"}</td>
                      <td>{v.valid_day_count} / {row.days_in_period}</td>
                      <td>{fmtPct(v.coverage_fraction)}</td>
                      <td>{fmtInt(v.valid_retrievals)}</td>
                      {isSensitivity && v.difference && (
                        <>
                          <td>{fmtSigned(v.difference.roi_mean_aod)}</td>
                          <td>{fmtSignedInt(v.difference.valid_retrievals)}</td>
                          <td>{fmtSignedInt(v.difference.valid_day_count)}</td>
                          <td>{v.difference.coverage_fraction === null ? "—" : `${fmtSigned(v.difference.coverage_fraction * 100, 1)} pp`}</td>
                        </>
                      )}
                      <td>{fmtInt(row.qa_guard_rejections)}</td>
                      <td>{v.consistency_check_passed ? "✓ pass" : "✕ fail"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <SeriesCharts points={points} variantLabel={selected.label} isSensitivity={isSensitivity}
              selectedMonth={selectedMonth} onSelect={props.onSelectMonth} />
          )}
          <p className="small muted" style={{ marginBottom: 0 }}>
            Monthly ROI means summarise whatever retrievals survived QA; months with low coverage or few valid days are less
            representative. No trend, uncertainty interval or attribution is implied. The map always shows the primary variant.
          </p>
        </div>
      )}
    </section>
  );
}
