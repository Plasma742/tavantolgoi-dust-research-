import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent, type RefObject } from "react";
import type { PeriodStatus } from "../../api/types";
import { fmtAod, fmtInt, fmtPct, monthLabel, niceRange } from "../../lib/format";

// Two small multiples sharing one x axis (never a dual-axis chart):
//   1. ROI mean AOD at 550 nm (line, 2px; 8px markers with a 2px surface ring). The y axis always
//      contains 0 and extends below it when a month has a negative mean (no clamping).
//   2. Valid days per month (columns <= 24px, 4px rounded data end, square at the baseline)
// Months without valid retrievals are shaded bands — a gap, never a zero.

export interface ChartPoint {
  month: string;
  status: PeriodStatus;
  mean: number | null;
  pooledMean: number | null;
  validDays: number;
  daysInPeriod: number;
  coverage: number | null;
  validRetrievals: number;
}

const M = { left: 48, right: 12, top: 10, bottom: 24 };
const H_AOD = 170;
const H_DAYS = 110;

interface Props {
  points: ChartPoint[];
  variantLabel: string;
  isSensitivity: boolean;
  selectedMonth: string | null;
  onSelect: (month: string) => void;
  initialWidth?: number;
}

function useWidth<T extends HTMLElement>(initial: number): [RefObject<T | null>, number] {
  const ref = useRef<T | null>(null);
  const [width, setWidth] = useState(initial);
  useEffect(() => {
    if (!ref.current || typeof ResizeObserver === "undefined") return;
    const obs = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w) setWidth(Math.max(320, Math.floor(w)));
    });
    obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);
  return [ref, width];
}

function topRoundedBar(x: number, y: number, w: number, h: number, r: number): string {
  const rr = Math.min(r, w / 2, h);
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`;
}

export function SeriesCharts({ points, variantLabel, isSensitivity, selectedMonth, onSelect, initialWidth = 640 }: Props) {
  const [boxRef, width] = useWidth<HTMLDivElement>(initialWidth);
  const [active, setActive] = useState<number | null>(null);
  const [pointer, setPointer] = useState<{ x: number; y: number } | null>(null);

  const n = points.length;
  const plotW = width - M.left - M.right;
  const bw = plotW / Math.max(n, 1);
  const cx = (i: number) => M.left + (i + 0.5) * bw;
  const labelEvery = n <= 12 ? 1 : n <= 24 ? 2 : 3;

  const valid = points.map((p) => (p.status === "OK" && p.mean !== null ? p.mean : null));
  const present = valid.filter((v): v is number => v !== null);
  const axis = niceRange(present.length ? Math.min(...present) : 0, present.length ? Math.max(...present) : 0, 0.2);
  const aodInnerH = H_AOD - M.top - M.bottom;
  const yAod = (v: number) => M.top + aodInnerH * (1 - (v - axis.bottom) / (axis.top - axis.bottom));

  const daysTop = 31;
  const daysTicks = [0, 10, 20, 30];
  const daysInnerH = H_DAYS - M.top - M.bottom;
  const yDays = (v: number) => M.top + daysInnerH * (1 - v / daysTop);

  let path = "";
  valid.forEach((v, i) => {
    if (v === null) return;
    const prevValid = i > 0 && valid[i - 1] !== null;
    path += `${prevValid ? "L" : "M"}${cx(i).toFixed(1)},${yAod(v).toFixed(1)}`;
  });
  const maxValue = present.length ? Math.max(...present) : null;
  const maxIndex = maxValue === null ? -1 : valid.findIndex((v) => v === maxValue);
  const minValue = present.length ? Math.min(...present) : null;
  const minIndex = minValue !== null && minValue < 0 ? valid.findIndex((v) => v === minValue) : -1;

  const indexFromX = (clientX: number): number | null => {
    const rect = boxRef.current?.getBoundingClientRect();
    if (!rect || n === 0) return null;
    const i = Math.floor((clientX - rect.left - M.left) / bw);
    return i >= 0 && i < n ? i : null;
  };

  const onMove = (e: PointerEvent<HTMLDivElement>) => {
    const rect = boxRef.current?.getBoundingClientRect();
    setActive(indexFromX(e.clientX));
    if (rect) setPointer({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (n === 0) return;
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const next = active === null ? 0 : Math.min(n - 1, Math.max(0, active + (e.key === "ArrowRight" ? 1 : -1)));
      setActive(next);
      setPointer({ x: cx(next), y: 40 });
    } else if (e.key === "Enter" && active !== null) {
      onSelect(points[active]!.month);
    } else if (e.key === "Escape") {
      setActive(null);
    }
  };

  const xLabels = (h: number) =>
    points.map((p, i) =>
      i % labelEvery === 0 ? (
        <text key={p.month} x={cx(i)} y={h - 6} textAnchor="middle" fontSize={11}
          fill={p.month === selectedMonth ? "var(--text-primary)" : "var(--text-muted)"}
          fontWeight={p.month === selectedMonth ? 600 : 400}>
          {monthLabel(p.month, false)}{p.month.endsWith("-01") || i === 0 ? ` ${p.month.slice(2, 4)}` : ""}
        </text>
      ) : null,
    );

  const gapBands = (h: number, chart: string) =>
    points.map((p, i) =>
      p.status !== "OK" ? (
        <rect key={`gap-${p.month}`} data-testid={`gap-band-${chart}`} data-month={p.month}
          x={M.left + i * bw + 1} y={M.top} width={Math.max(bw - 2, 1)} height={h - M.top - M.bottom}
          fill="var(--surface-3)" opacity={0.7} />
      ) : null,
    );

  const markers = (h: number) => {
    const out = [];
    if (active !== null) {
      out.push(<line key="cross" x1={cx(active)} x2={cx(active)} y1={M.top} y2={h - M.bottom} stroke="var(--text-muted)" strokeWidth={1} />);
    }
    const sel = points.findIndex((p) => p.month === selectedMonth);
    if (sel >= 0) {
      out.push(<line key="sel" x1={cx(sel)} x2={cx(sel)} y1={M.top} y2={h - M.bottom} stroke="var(--text-secondary)" strokeWidth={1} opacity={0.6} />);
    }
    return out;
  };

  const activePoint = active !== null ? points[active] : undefined;
  const barW = Math.min(24, bw * 0.6);

  return (
    <div
      ref={boxRef}
      className="chart-box"
      tabIndex={0}
      role="group"
      aria-label={`Monthly charts for ${variantLabel}. Use left and right arrow keys to inspect months, Enter to show a month on the map.`}
      onPointerMove={onMove}
      onPointerLeave={() => { setActive(null); setPointer(null); }}
      onClick={(e) => { const i = indexFromX(e.clientX); if (i !== null) onSelect(points[i]!.month); }}
      onKeyDown={onKey}
      style={{ cursor: "pointer" }}
    >
      <p className="chart-title">
        ROI mean AOD at 550 nm · {variantLabel}
        {isSensitivity && <span className="badge sensitivity" style={{ marginLeft: 8 }}>Sensitivity — not the primary result</span>}
      </p>
      <p className="chart-sub">Dimensionless · mean of per-pixel period means · shaded months = no valid retrieval (missing, not zero) · negative values are shown, not clamped</p>
      <svg width={width} height={H_AOD} aria-hidden="true">
        {axis.ticks.map((t) => (
          <g key={t} data-testid="aod-tick" data-value={t}>
            <line x1={M.left} x2={width - M.right} y1={yAod(t)} y2={yAod(t)} stroke={t === 0 ? "var(--baseline)" : "var(--grid)"} strokeWidth={1} />
            <text x={M.left - 6} y={yAod(t) + 4} textAnchor="end" fontSize={11} fill="var(--text-muted)" className="tabular">{t.toFixed(2)}</text>
          </g>
        ))}
        {gapBands(H_AOD, "aod")}
        {markers(H_AOD)}
        <path d={path} fill="none" stroke="var(--series-1)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {valid.map((v, i) => (v === null ? null : (
          <circle key={points[i]!.month} data-testid="aod-marker" data-month={points[i]!.month} data-value={v}
            cx={cx(i)} cy={yAod(v)} r={active === i ? 5 : 4} fill="var(--series-1)" stroke="var(--surface-1)" strokeWidth={2} />
        )))}
        {maxIndex >= 0 && maxValue !== null && (
          <text x={cx(maxIndex)} y={yAod(maxValue) - 10} textAnchor="middle" fontSize={11} fill="var(--text-secondary)" className="tabular">
            {fmtAod(maxValue)}
          </text>
        )}
        {minIndex >= 0 && minValue !== null && (
          <text x={cx(minIndex)} y={yAod(minValue) + 18} textAnchor="middle" fontSize={11} fill="var(--text-secondary)" className="tabular">
            {fmtAod(minValue)}
          </text>
        )}
        {xLabels(H_AOD)}
      </svg>

      <p className="chart-title">Valid days per month · {variantLabel}</p>
      <p className="chart-sub">UTC days with ≥1 valid retrieval anywhere in the ROI</p>
      <svg width={width} height={H_DAYS} aria-hidden="true">
        {daysTicks.map((t) => (
          <g key={t}>
            <line x1={M.left} x2={width - M.right} y1={yDays(t)} y2={yDays(t)} stroke={t === 0 ? "var(--baseline)" : "var(--grid)"} strokeWidth={1} />
            <text x={M.left - 6} y={yDays(t) + 4} textAnchor="end" fontSize={11} fill="var(--text-muted)" className="tabular">{t}</text>
          </g>
        ))}
        {gapBands(H_DAYS, "days")}
        {markers(H_DAYS)}
        {points.map((p, i) => {
          if (p.validDays <= 0) return null;
          const y = yDays(p.validDays);
          const h = yDays(0) - y;
          return (
            <path key={p.month} d={topRoundedBar(cx(i) - barW / 2, y, barW, h, 4)} fill="var(--series-3)"
              opacity={active === null || active === i ? 1 : 0.75} />
          );
        })}
        {xLabels(H_DAYS)}
      </svg>

      {activePoint && pointer && (
        <div className="tooltip" style={{ left: Math.min(pointer.x + 14, width - 210), top: Math.max(0, pointer.y - 20) }}>
          <div className="t-head">{monthLabel(activePoint.month)} · {variantLabel}</div>
          {activePoint.status === "OK" ? (
            <>
              <div className="t-row"><span className="key" style={{ background: "var(--series-1)" }} /><strong>{fmtAod(activePoint.mean)}</strong><span className="muted">mean of per-pixel means</span></div>
              <div className="t-row"><strong>{fmtAod(activePoint.pooledMean)}</strong><span className="muted">pooled retrieval mean</span></div>
            </>
          ) : (
            <div className="t-row"><strong>{activePoint.status === "NO_GRANULES" ? "No granules" : "No valid retrieval"}</strong></div>
          )}
          <div className="t-row"><span className="key" style={{ background: "var(--series-3)" }} /><strong>{activePoint.validDays} / {activePoint.daysInPeriod}</strong><span className="muted">valid days</span></div>
          <div className="t-row"><strong>{fmtPct(activePoint.coverage)}</strong><span className="muted">ROI pixel coverage</span></div>
          <div className="t-row"><strong>{fmtInt(activePoint.validRetrievals)}</strong><span className="muted">valid retrievals</span></div>
          <div className="t-row muted small">Click to show this month on the map (primary variant)</div>
        </div>
      )}
    </div>
  );
}
