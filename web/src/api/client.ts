import type {
  DatasetsResponse,
  Health,
  LayerResponse,
  MethodsResponse,
  MonthlySeriesResponse,
  RoiInput,
  RoisResponse,
} from "./types";

// Empty base = same origin (Vite dev proxy). Only a public URL may ever go here.
export const API_BASE: string = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError(0, "BACKEND_UNREACHABLE", "The backend API could not be reached. Is it running on port 8000?");
  }
  if (!res.ok) {
    let code = `HTTP_${res.status}`;
    let message = res.statusText || "Request failed";
    let details: unknown;
    try {
      const body = (await res.json()) as { error?: { code?: string; message?: string; details?: unknown } };
      if (body.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
        details = body.error.details;
      }
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, code, message, details);
  }
  return (await res.json()) as T;
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

export const api = {
  health: (checkEarthEngine = false) => request<Health>(`/api/health${checkEarthEngine ? "?check_earth_engine=true" : ""}`),
  datasets: () => request<DatasetsResponse>("/api/datasets"),
  methods: () => request<MethodsResponse>("/api/methods"),
  rois: () => request<RoisResponse>("/api/rois"),
  maiacLayer: (roi: RoiInput, start: string, endExclusive: string) =>
    post<LayerResponse>("/api/layers/maiac_aod550", { roi, start, end_exclusive: endExclusive }),
  maiacMonthly: (roi: RoiInput, startMonth: string, endMonth: string) =>
    post<MonthlySeriesResponse>("/api/stats/maiac_aod550/monthly", { roi, start_month: startMonth, end_month: endMonth }),
  async maiacMonthlyCsv(roi: RoiInput, startMonth: string, endMonth: string): Promise<Blob> {
    let res: Response;
    try {
      res = await fetch(`${API_BASE}/api/stats/maiac_aod550/monthly.csv`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ roi, start_month: startMonth, end_month: endMonth }),
      });
    } catch {
      throw new ApiError(0, "BACKEND_UNREACHABLE", "The backend API could not be reached.");
    }
    if (!res.ok) {
      const body = (await res.json().catch(() => ({}))) as { error?: { code?: string; message?: string } };
      throw new ApiError(res.status, body.error?.code ?? `HTTP_${res.status}`, body.error?.message ?? "CSV export failed");
    }
    return res.blob();
  },
};

/** Absolute tile URL. MapLibre fetches tiles from a worker, so relative URLs would not resolve. */
export function tileUrl(template: string): string {
  const base = API_BASE || window.location.origin;
  return `${base}${template}`;
}
