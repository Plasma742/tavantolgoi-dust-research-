import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api/client";
import type { Health, LayerResponse, MonthlySeriesResponse, RoiInput, RoisResponse } from "./api/types";
import { LayerPanel } from "./components/LayerPanel";
import { MapView, type LayerUiState } from "./components/MapView";
import { MethodsPage } from "./components/MethodsPage";
import { PeriodPanel } from "./components/PeriodPanel";
import { ProvenanceDrawer } from "./components/ProvenanceDrawer";
import { RoiPanel, type RoiState } from "./components/RoiPanel";
import { SummaryPanel } from "./components/SummaryPanel";
import { TimeSeriesPanel } from "./components/TimeSeriesPanel";
import type { PolygonGeometry } from "./api/types";
import { toApiWindow, type PeriodSelection } from "./lib/period";

type Tab = "explorer" | "methods";

function roiInput(roi: RoiState): RoiInput {
  return roi.declaredStatus === "registry" && roi.registryId
    ? { registry_id: roi.registryId, label: roi.label, declared_status: "registry" }
    : { geometry: roi.geometry, label: roi.label, declared_status: roi.declaredStatus, source_note: roi.sourceNote };
}

function errorText(err: unknown): string {
  if (err instanceof ApiError) {
    const details = Array.isArray(err.details)
      ? (err.details as { msg?: string }[]).map((d) => d.msg).filter(Boolean).join("; ")
      : "";
    return `${err.code}: ${err.message}${details ? ` (${details})` : ""}`;
  }
  return "Unexpected error.";
}

function EEPill({ health, error }: { health: Health | null; error: string | null }) {
  if (error) return <span className="pill critical" role="status"><span className="dot" />Backend unreachable</span>;
  if (!health) return <span className="pill neutral" role="status"><span className="dot" />Checking backend…</span>;
  const s = health.earth_engine.status;
  const map = {
    READY: ["good", "Earth Engine: ready"],
    NOT_CONFIGURED: ["warning", "Earth Engine: NOT_CONFIGURED"],
    NOT_INITIALIZED: ["neutral", "Earth Engine: not initialised"],
    AUTH_ERROR: ["critical", "Earth Engine: authentication error"],
  } as const;
  const [tone, label] = map[s];
  return <span className={`pill ${tone}`} role="status" title={health.earth_engine.message ?? undefined}><span className="dot" />{label}</span>;
}

export default function App() {
  const [tab, setTab] = useState<Tab>("explorer");
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [registry, setRegistry] = useState<RoisResponse | null>(null);

  const [roi, setRoiState] = useState<RoiState | null>(null);
  const [drawing, setDrawing] = useState(false);
  const [period, setPeriod] = useState<PeriodSelection>({
    mode: "month", month: "2025-04", start: "2025-04-01", endInclusive: "2025-04-30",
  });

  const [layerResp, setLayerResp] = useState<LayerResponse | null>(null);
  const [layerLoading, setLayerLoading] = useState(false);
  const [layerError, setLayerError] = useState<string | null>(null);
  const [layerState, setLayerState] = useState<Record<string, LayerUiState>>({});
  const [dimBasemap, setDimBasemap] = useState(true);
  const [tileProblem, setTileProblem] = useState<string | null>(null);
  const [basemapProblem, setBasemapProblem] = useState<string | null>(null);

  const [series, setSeries] = useState<MonthlySeriesResponse | null>(null);
  const [seriesRange, setSeriesRange] = useState({ start: "2025-01", end: "2025-12" });
  const [seriesLoading, setSeriesLoading] = useState(false);
  const [seriesError, setSeriesError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const refreshHealth = useCallback(() => {
    api
      .health(true)
      .then((h) => {
        setHealth(h);
        setHealthError(null);
      })
      .catch((err: unknown) => setHealthError(errorText(err)));
    api.rois().then(setRegistry).catch(() => setRegistry(null));
  }, []);

  useEffect(() => {
    refreshHealth();
  }, [refreshHealth]);

  const eeStatus = health?.earth_engine.status;
  const ready = eeStatus === "READY";
  const disabledReason = healthError
    ? "Backend API unreachable. Start it (see README) and press Retry."
    : eeStatus === "NOT_CONFIGURED"
      ? "Earth Engine is NOT_CONFIGURED on the backend, so no observations can be loaded. See README → Earth Engine setup."
      : eeStatus === "AUTH_ERROR"
        ? `Earth Engine initialisation failed: ${health?.earth_engine.message ?? "unknown error"}`
        : !roi
          ? "Select, upload or draw an ROI first."
          : null;

  const setRoi = (next: RoiState | null) => {
    setRoiState(next);
    setLayerResp(null);
    setLayerState({});
    setSeries(null);
    setLayerError(null);
    setSeriesError(null);
    setTileProblem(null);
  };

  const onDrawComplete = useCallback((geometry: PolygonGeometry) => {
    setDrawing(false);
    const stamp = new Date().toISOString().slice(0, 16).replace("T", " ");
    setRoi({
      geometry, label: `Demonstration rectangle (${stamp} UTC)`, declaredStatus: "demonstration",
      sourceNote: null, registryId: null, registryVerified: false,
    });
  }, []);
  const onDrawCancel = useCallback(() => setDrawing(false), []);
  const onTileProblem = useCallback((kind: "data" | "basemap", message: string) => {
    if (kind === "basemap") setBasemapProblem(message);
    else setTileProblem(message);
  }, []);

  const loadLayer = async (selection: PeriodSelection = period) => {
    if (!roi) return;
    const { start, endExclusive } = toApiWindow(selection);
    setLayerLoading(true);
    setLayerError(null);
    setTileProblem(null);
    try {
      const resp = await api.maiacLayer(roiInput(roi), start, endExclusive);
      setLayerResp(resp);
      setLayerState(Object.fromEntries(resp.layers.map((l) => [l.id, { visible: l.default_visible, opacity: l.default_opacity }])));
    } catch (err) {
      setLayerResp(null);
      setLayerError(errorText(err));
    } finally {
      setLayerLoading(false);
    }
  };

  const computeSeries = async () => {
    if (!roi) return;
    setSeriesLoading(true);
    setSeriesError(null);
    try {
      setSeries(await api.maiacMonthly(roiInput(roi), seriesRange.start, seriesRange.end));
    } catch (err) {
      setSeriesError(errorText(err));
    } finally {
      setSeriesLoading(false);
    }
  };

  const exportCsv = async () => {
    if (!roi) return;
    try {
      const blob = await api.maiacMonthlyCsv(roiInput(roi), seriesRange.start, seriesRange.end);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `maiac_aod550_monthly_${seriesRange.start}_${seriesRange.end}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setSeriesError(errorText(err));
    }
  };

  const selectMonth = (month: string) => {
    const next: PeriodSelection = { ...period, mode: "month", month };
    setPeriod(next);
    if (ready && roi) void loadLayer(next);
  };

  const nativeScale = (() => {
    const spatial = layerResp?.provenance.spatial as { native_grid_reported_by_earth_engine?: { nominal_scale_m?: number } } | undefined;
    return spatial?.native_grid_reported_by_earth_engine?.nominal_scale_m ?? null;
  })();

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <h1>Tavan Tolgoi Dust Research Platform</h1>
          <span>Research prototype · v{health?.version ?? "?"} · {health?.code_revision ?? "revision unknown"} · not publicly deployed</span>
        </div>
        <nav className="tabs" role="tablist" aria-label="Pages">
          <button role="tab" aria-selected={tab === "explorer"} onClick={() => setTab("explorer")}>Map explorer</button>
          <button role="tab" aria-selected={tab === "methods"} onClick={() => setTab("methods")}>Data &amp; methods</button>
        </nav>
        <EEPill health={health} error={healthError} />
        <button className="btn small" type="button" onClick={refreshHealth}>Retry</button>
      </header>
      <div className="integrity">
        <strong>Scientific scope:</strong> MAIAC AOD is column-integrated aerosol optical depth at 550 nm — not PM10, not a
        surface dust concentration, and not evidence of mine-generated dust on its own. Missing pixels are shown as missing.
      </div>

      {tab === "methods" ? (
        <MethodsPage />
      ) : (
        <div className="explorer">
          <aside className="sidebar" aria-label="Controls">
            <RoiPanel
              roi={roi}
              registry={registry}
              drawing={drawing}
              maxAreaKm2={health?.limits.max_roi_area_km2 ?? null}
              onStartDrawing={() => setDrawing(true)}
              onCancelDrawing={() => setDrawing(false)}
              onChange={setRoi}
            />
            <PeriodPanel
              value={period}
              maxDays={health?.limits.max_layer_days ?? 31}
              canLoad={ready && roi !== null}
              loading={layerLoading}
              disabledReason={disabledReason}
              onChange={setPeriod}
              onLoad={() => void loadLayer()}
            />
            {layerError && (
              <div className="section"><div className="callout critical" role="alert"><span className="icon">✕</span>{layerError}</div></div>
            )}
            <LayerPanel
              layers={layerResp?.layers ?? []}
              state={layerState}
              dimBasemap={dimBasemap}
              onState={(id, next) => setLayerState((s) => ({ ...s, [id]: next }))}
              onDimBasemap={setDimBasemap}
              nativeScaleM={nativeScale}
            />
            <SummaryPanel summary={layerResp?.summary ?? null} onOpenProvenance={() => setDrawerOpen(true)} />
          </aside>
          <main className="main">
            <div style={{ position: "relative", flex: 1, display: "flex", flexDirection: "column" }}>
              <MapView
                roi={roi?.geometry ?? null}
                roiStatus={roi?.declaredStatus ?? null}
                roiVerified={roi?.registryVerified ?? false}
                layers={layerResp?.layers ?? []}
                layerState={layerState}
                dimBasemap={dimBasemap}
                drawing={drawing}
                onDrawComplete={onDrawComplete}
                onDrawCancel={onDrawCancel}
                onTileProblem={onTileProblem}
              />
              <div className="map-notice" role="status">
                {eeStatus === "NOT_CONFIGURED" || healthError
                  ? "No aerosol data is displayed: the backend's Earth Engine connection is not configured. The map shows the basemap and your ROI only."
                  : layerResp
                    ? `${layerResp.provenance.dataset_id} · ${layerResp.summary.time_start_utc.slice(0, 10)} → ${layerResp.summary.time_end_exclusive_utc.slice(0, 10)} (exclusive) · ${layerResp.tiles_note}`
                    : "No data layer loaded."}
                {tileProblem && <div style={{ marginTop: 4, color: "var(--text-primary)" }}><strong>!</strong> {tileProblem}</div>}
                {basemapProblem && <div style={{ marginTop: 4 }}><strong>!</strong> {basemapProblem}</div>}
              </div>
            </div>
            <TimeSeriesPanel
              series={series}
              loading={seriesLoading}
              error={seriesError}
              startMonth={seriesRange.start}
              endMonth={seriesRange.end}
              maxMonths={health?.limits.max_series_months ?? 36}
              canCompute={ready && roi !== null}
              disabledReason={disabledReason}
              selectedMonth={layerResp && period.mode === "month" ? period.month : null}
              onRange={(start, end) => setSeriesRange({ start, end })}
              onCompute={() => void computeSeries()}
              onCsv={() => void exportCsv()}
              onSelectMonth={selectMonth}
            />
          </main>
        </div>
      )}
      {drawerOpen && (
        <ProvenanceDrawer layer={layerResp?.provenance ?? null} series={series?.provenance ?? null} onClose={() => setDrawerOpen(false)} />
      )}
    </div>
  );
}
