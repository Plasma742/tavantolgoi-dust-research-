// Period helpers. The UI shows an INCLUSIVE end date; the API takes an EXCLUSIVE end
// (Earth Engine filterDate semantics). All dates are UTC calendar dates (YYYY-MM-DD).

export interface PeriodSelection {
  mode: "month" | "range";
  month: string; // YYYY-MM
  start: string; // YYYY-MM-DD
  endInclusive: string; // YYYY-MM-DD
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

export function addDays(isoDate: string, days: number): string {
  const [y, m, d] = isoDate.split("-").map(Number) as [number, number, number];
  const t = new Date(Date.UTC(y, m - 1, d + days));
  return `${t.getUTCFullYear()}-${pad(t.getUTCMonth() + 1)}-${pad(t.getUTCDate())}`;
}

export function monthBounds(month: string): { start: string; endExclusive: string } {
  const [y, m] = month.split("-").map(Number) as [number, number];
  const next = m === 12 ? `${y + 1}-01` : `${y}-${pad(m + 1)}`;
  return { start: `${month}-01`, endExclusive: `${next}-01` };
}

export function toApiWindow(sel: PeriodSelection): { start: string; endExclusive: string } {
  return sel.mode === "month" ? monthBounds(sel.month) : { start: sel.start, endExclusive: addDays(sel.endInclusive, 1) };
}

export function daysBetween(start: string, endExclusive: string): number {
  const a = Date.parse(`${start}T00:00:00Z`);
  const b = Date.parse(`${endExclusive}T00:00:00Z`);
  return Math.round((b - a) / 86_400_000);
}

export function describeWindow(start: string, endExclusive: string): string {
  return `${start} to ${addDays(endExclusive, -1)} (UTC, inclusive) · ${daysBetween(start, endExclusive)} days`;
}

export function monthsBetween(startMonth: string, endMonth: string): number {
  const [y1, m1] = startMonth.split("-").map(Number) as [number, number];
  const [y2, m2] = endMonth.split("-").map(Number) as [number, number];
  return (y2 - y1) * 12 + (m2 - m1) + 1;
}
