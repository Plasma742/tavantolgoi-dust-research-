import type { PeriodSelection } from "../lib/period";
import { daysBetween, describeWindow, toApiWindow } from "../lib/period";

interface Props {
  value: PeriodSelection;
  maxDays: number;
  canLoad: boolean;
  loading: boolean;
  disabledReason: string | null;
  onChange: (value: PeriodSelection) => void;
  onLoad: () => void;
}

export function PeriodPanel({ value, maxDays, canLoad, loading, disabledReason, onChange, onLoad }: Props) {
  const win = toApiWindow(value);
  const days = daysBetween(win.start, win.endExclusive);
  const invalid = days <= 0 ? "End date must be on or after the start date." : days > maxDays ? `Limit is ${maxDays} days.` : null;

  return (
    <section className="section" aria-labelledby="period-h">
      <h2 id="period-h">2 · Map period</h2>
      <div className="segmented" role="group" aria-label="Period type">
        <button type="button" aria-pressed={value.mode === "month"} onClick={() => onChange({ ...value, mode: "month" })}>
          Month
        </button>
        <button type="button" aria-pressed={value.mode === "range"} onClick={() => onChange({ ...value, mode: "range" })}>
          Custom range
        </button>
      </div>
      <div className="row" style={{ marginTop: 8 }}>
        {value.mode === "month" ? (
          <label className="field">
            Month (UTC)
            <input type="month" value={value.month} min="2000-03" onChange={(e) => e.target.value && onChange({ ...value, month: e.target.value })} />
          </label>
        ) : (
          <>
            <label className="field">
              Start (UTC)
              <input type="date" value={value.start} min="2000-02-24" onChange={(e) => e.target.value && onChange({ ...value, start: e.target.value })} />
            </label>
            <label className="field">
              End, inclusive (UTC)
              <input type="date" value={value.endInclusive} min={value.start} onChange={(e) => e.target.value && onChange({ ...value, endInclusive: e.target.value })} />
            </label>
          </>
        )}
      </div>
      <p className="small muted" style={{ margin: "6px 0" }}>
        {invalid ?? describeWindow(win.start, win.endExclusive)}
      </p>
      <button className="btn primary" type="button" onClick={onLoad} disabled={!canLoad || loading || invalid !== null}>
        {loading ? "Computing in Earth Engine…" : "Load MAIAC AOD layer"}
      </button>
      {disabledReason && <p className="small muted" style={{ marginBottom: 0 }}>{disabledReason}</p>}
    </section>
  );
}
