import type { PeriodSummary } from "../api/types";
import { fmtAod, fmtInt, fmtPct, fmtSigned, fmtSignedInt } from "../lib/format";
import { describeWindow } from "../lib/period";

export function StatusCallout({ summary }: { summary: PeriodSummary }) {
  if (summary.status === "OK") return null;
  return (
    <div className="callout warning" role="status">
      <span className="icon">!</span>
      <strong>{summary.status === "NO_GRANULES" ? "No granules" : "No valid observations"}</strong> — {summary.status_message}
    </div>
  );
}

/** Sensitivity variants next to the primary result, with differences (variant minus primary). */
export function SensitivityTable({ summary }: { summary: PeriodSummary }) {
  if (summary.sensitivity.length === 0) return null;
  return (
    <div>
      <h3 style={{ margin: "4px 0" }}>Sensitivity analysis <span className="badge sensitivity">not the primary result</span></h3>
      <div className="table-scroll">
        <table className="data tabular" aria-label="Sensitivity variants compared with the primary result">
          <thead>
            <tr><th>Variant</th><th>Mean</th><th>Δ mean</th><th>Valid ret.</th><th>Δ</th><th>Valid days</th><th>Δ</th><th>Coverage</th></tr>
          </thead>
          <tbody>
            <tr>
              <td>Primary ({summary.primary_variant})</td>
              <td>{summary.status === "OK" ? fmtAod(summary.roi_mean_aod) : "—"}</td><td />
              <td>{fmtInt(summary.valid_retrievals)}</td><td />
              <td>{summary.valid_day_count}</td><td />
              <td>{fmtPct(summary.coverage_fraction)}</td>
            </tr>
            {summary.sensitivity.map((s) => (
              <tr key={s.variant}>
                <td title={s.definition}>{s.label.replace(/^Sensitivity - /, "")}</td>
                <td>{s.status === "OK" ? fmtAod(s.roi_mean_aod) : "No valid data"}</td>
                <td>{fmtSigned(s.difference_vs_primary.roi_mean_aod)}</td>
                <td>{fmtInt(s.valid_retrievals)}</td>
                <td>{fmtSignedInt(s.difference_vs_primary.valid_retrievals)}</td>
                <td>{s.valid_day_count}</td>
                <td>{fmtSignedInt(s.difference_vs_primary.valid_day_count)}</td>
                <td>{fmtPct(s.coverage_fraction)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function SummaryPanel({ summary, onOpenProvenance }: { summary: PeriodSummary | null; onOpenProvenance: () => void }) {
  return (
    <section className="section" aria-labelledby="summary-h">
      <h2 id="summary-h">4 · Period summary</h2>
      {!summary ? (
        <p className="small muted">Load a layer to see ROI statistics. No values are shown before Earth Engine returns them.</p>
      ) : (
        <div className="stack">
          <p className="small muted" style={{ margin: 0 }}>
            {describeWindow(summary.time_start_utc.slice(0, 10), summary.time_end_exclusive_utc.slice(0, 10))}
          </p>
          <div className="row small">
            <span className="badge">Method {summary.method_version}</span>
            <span className="badge">Primary: {summary.primary_variant}</span>
          </div>
          <StatusCallout summary={summary} />
          <div className="tiles">
            <div className="tile wide">
              <div className="label">ROI mean AOD at 550 nm (mean of per-pixel period means)</div>
              <div className="value" data-testid="roi-mean">{fmtAod(summary.roi_mean_aod)}</div>
              <div className="sub">
                Pooled retrieval mean (a different statistic): {fmtAod(summary.roi_pooled_retrieval_mean_aod)} ·
                dimensionless · shown to 0.001 (product quantisation, not uncertainty)
              </div>
            </div>
            <div className="tile">
              <div className="label">Spatial coverage</div>
              <div className="value">{fmtPct(summary.coverage_fraction)}</div>
              <div className="sub">{fmtInt(summary.pixels_with_valid)} of {fmtInt(summary.pixels_total)} ROI pixels (centre in ROI) with ≥1 valid retrieval</div>
            </div>
            <div className="tile">
              <div className="label">Valid days</div>
              <div className="value">{summary.valid_day_count} / {summary.days_in_period}</div>
              <div className="sub">UTC days with ≥1 valid retrieval in ROI</div>
            </div>
            <div className="tile">
              <div className="label">Valid retrievals</div>
              <div className="value">{fmtInt(summary.valid_retrievals)}</div>
              <div className="sub">QA retention {fmtPct(summary.qa_retention_fraction)} of {fmtInt(summary.retrievals_before_qa)} AOD values</div>
            </div>
            <div className="tile">
              <div className="label">Granules</div>
              <div className="value">{summary.granules_with_valid} / {summary.granules_intersecting}</div>
              <div className="sub">with valid retrievals / intersecting ROI</div>
            </div>
          </div>
          {summary.qa_guard_rejections > 0 && (
            <div className="callout warning" role="note">
              <span className="icon">!</span>{fmtInt(summary.qa_guard_rejections)} retrieval(s) passed core QA but were rejected for
              undocumented or reserved AOD_QA values.
            </div>
          )}
          <div className={`callout ${summary.consistency_check_passed ? "good" : "critical"}`}>
            <span className="icon">{summary.consistency_check_passed ? "✓" : "✕"}</span>
            {summary.consistency_check_passed
              ? "Internal check passed: pixel-level and per-granule valid counts agree."
              : "Internal check FAILED: pixel-level and per-granule valid counts disagree. Do not use these numbers."}
          </div>
          <SensitivityTable summary={summary} />
          <button className="btn small" type="button" onClick={onOpenProvenance}>Provenance &amp; method…</button>
        </div>
      )}
    </section>
  );
}
