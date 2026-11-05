// Display formatting. AOD is shown to 0.001 — the product's quantisation step — which is a
// display precision, not an uncertainty estimate.

export const AOD_DECIMALS = 3;

export function fmtAod(value: number | null | undefined): string {
  return value === null || value === undefined ? "No valid data" : value.toFixed(AOD_DECIMALS);
}

export function fmtInt(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : Math.round(value).toLocaleString("en-US");
}

export function fmtPct(fraction: number | null | undefined, digits = 1): string {
  return fraction === null || fraction === undefined ? "—" : `${(fraction * 100).toFixed(digits)}%`;
}

export function fmtArea(km2: number): string {
  return `${Math.round(km2).toLocaleString("en-US")} km²`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function monthLabel(month: string, withYear = true): string {
  const [y, m] = month.split("-");
  const name = MONTHS[Number(m) - 1] ?? month;
  return withYear ? `${name} ${y}` : name;
}

/** Signed difference, e.g. "+0.012" / "-0.004"; "—" when either side is missing. */
export function fmtSigned(value: number | null | undefined, digits = AOD_DECIMALS): string {
  if (value === null || value === undefined) return "—";
  const text = value.toFixed(digits);
  return value > 0 ? `+${text}` : text;
}

export function fmtSignedInt(value: number): string {
  return value > 0 ? `+${value.toLocaleString("en-US")}` : value.toLocaleString("en-US");
}

/**
 * Nice linear range that always contains 0 and every value (AOD can be slightly negative).
 * Never clips data: bottom <= min(0, minValue) and top >= max(maxValue, minTop).
 */
export function niceRange(minValue: number, maxValue: number, minTop: number): { bottom: number; top: number; ticks: number[] } {
  const low = Math.min(0, minValue);
  const high = Math.max(maxValue, minTop);
  const rawStep = (high - low) / 4;
  const mag = 10 ** Math.floor(Math.log10(rawStep));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= rawStep) ?? 10 * mag;
  const bottom = Math.floor(low / step + 1e-9) * step;
  const top = Math.ceil(high / step - 1e-9) * step;
  const ticks: number[] = [];
  for (let v = bottom; v <= top + step / 2; v += step) ticks.push(Number(v.toFixed(10)));
  return { bottom, top, ticks };
}

/** "Nice" upper bound for a 0-based linear axis, with ~4 ticks. */
export function niceAxis(maxValue: number, minTop: number): { top: number; ticks: number[] } {
  const target = Math.max(maxValue, minTop);
  const rawStep = target / 4;
  const mag = 10 ** Math.floor(Math.log10(rawStep));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= rawStep) ?? 10 * mag;
  const top = Math.ceil(target / step - 1e-9) * step;
  const ticks: number[] = [];
  for (let v = 0; v <= top + step / 2; v += step) ticks.push(Number(v.toFixed(10)));
  return { top, ticks };
}
