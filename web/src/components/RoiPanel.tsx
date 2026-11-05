import { useRef, useState } from "react";
import type { DeclaredStatus, PolygonGeometry, RegistryRoi, RoisResponse } from "../api/types";
import { fmtArea } from "../lib/format";
import { approxAreaKm2, parseRoiGeoJson, RoiParseError, vertexCount } from "../lib/roi";

export interface RoiState {
  geometry: PolygonGeometry;
  label: string;
  declaredStatus: DeclaredStatus;
  sourceNote: string | null;
  registryId: string | null;
  registryVerified: boolean;
}

interface Props {
  roi: RoiState | null;
  registry: RoisResponse | null;
  drawing: boolean;
  maxAreaKm2: number | null;
  onStartDrawing: () => void;
  onCancelDrawing: () => void;
  onChange: (roi: RoiState | null) => void;
}

const STATUS_TEXT: Record<DeclaredStatus, string> = {
  demonstration: "Manual demonstration ROI — not a verified mine boundary",
  unverified_upload: "Uploaded GeoJSON — provenance unverified",
  user_declared_verified: "Uploaded GeoJSON — declared verified by you (not checked by the server)",
  registry: "Server-registered ROI",
};

/** Exact geometry sent to the backend — use it for the Code Editor parity check. */
function downloadRoi(roi: RoiState) {
  const feature = {
    type: "Feature",
    properties: { label: roi.label, declared_status: roi.declaredStatus, source_note: roi.sourceNote },
    geometry: roi.geometry,
  };
  const url = URL.createObjectURL(new Blob([JSON.stringify(feature, null, 2)], { type: "application/geo+json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "roi.geojson";
  a.click();
  URL.revokeObjectURL(url);
}

export function RoiPanel({ roi, registry, drawing, maxAreaKm2, onStartDrawing, onCancelDrawing, onChange }: Props) {
  const fileInput = useRef<HTMLInputElement | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [pending, setPending] = useState<{ geometry: PolygonGeometry; name: string } | null>(null);
  const [declareVerified, setDeclareVerified] = useState(false);
  const [sourceNote, setSourceNote] = useState("");

  const onFile = async (file: File) => {
    setUploadError(null);
    try {
      const parsed = parseRoiGeoJson(await file.text());
      setPending({ geometry: parsed.geometry, name: parsed.name ?? file.name.replace(/\.(geo)?json$/i, "") });
      setDeclareVerified(false);
      setSourceNote("");
    } catch (err) {
      setUploadError(err instanceof RoiParseError ? err.message : "Could not read the file.");
    } finally {
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const acceptUpload = () => {
    if (!pending) return;
    const verified = declareVerified && sourceNote.trim().length > 0;
    onChange({
      geometry: pending.geometry,
      label: pending.name.slice(0, 120) || "Uploaded ROI",
      declaredStatus: verified ? "user_declared_verified" : "unverified_upload",
      sourceNote: verified ? sourceNote.trim().slice(0, 500) : null,
      registryId: null,
      registryVerified: false,
    });
    setPending(null);
  };

  const selectRegistry = (entry: RegistryRoi) =>
    onChange({
      geometry: entry.geometry,
      label: entry.label,
      declaredStatus: "registry",
      sourceNote: entry.source,
      registryId: entry.id,
      registryVerified: entry.verified,
    });

  const area = roi ? approxAreaKm2(roi.geometry) : null;

  return (
    <section className="section" aria-labelledby="roi-h">
      <h2 id="roi-h">1 · Study area (ROI)</h2>

      <label className="field">
        Server-registered ROIs
        <select
          value={roi?.registryId ?? ""}
          onChange={(e) => {
            const entry = registry?.rois.find((r) => r.id === e.target.value);
            if (entry) selectRegistry(entry);
          }}
          disabled={!registry || registry.rois.length === 0}
        >
          <option value="">{registry && registry.rois.length > 0 ? "Select…" : "None registered on the server"}</option>
          {registry?.rois.map((r) => (
            <option key={r.id} value={r.id}>
              {r.label} {r.verified ? "(verified)" : "(unverified)"}
            </option>
          ))}
        </select>
      </label>
      {registry && registry.problems.length > 0 && (
        <p className="small muted">{registry.problems.length} ROI file(s) on the server were rejected; see API /api/rois.</p>
      )}

      <div className="row" style={{ marginTop: 10 }}>
        {drawing ? (
          <button className="btn" type="button" onClick={onCancelDrawing}>Cancel drawing</button>
        ) : (
          <button className="btn" type="button" onClick={onStartDrawing}>Draw demonstration rectangle</button>
        )}
        <button className="btn" type="button" onClick={() => fileInput.current?.click()}>Upload GeoJSON…</button>
        <input
          ref={fileInput}
          type="file"
          accept=".geojson,.json,application/geo+json,application/json"
          className="visually-hidden"
          aria-label="Upload ROI GeoJSON"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void onFile(file);
          }}
        />
      </div>
      {uploadError && <div className="callout critical" role="alert" style={{ marginTop: 8 }}><span className="icon">✕</span>{uploadError}</div>}

      {pending && (
        <div className="callout neutral stack" style={{ marginTop: 8 }}>
          <div><strong>{pending.name}</strong> · {fmtArea(approxAreaKm2(pending.geometry))} · {vertexCount(pending.geometry)} vertices</div>
          <label className="row small">
            <input type="checkbox" checked={declareVerified} onChange={(e) => setDeclareVerified(e.target.checked)} />
            This polygon comes from an authoritative, approved source
          </label>
          {declareVerified && (
            <label className="field">
              Source (organisation, date, licence) — required
              <textarea value={sourceNote} onChange={(e) => setSourceNote(e.target.value)} maxLength={500} />
            </label>
          )}
          <div className="row">
            <button className="btn primary small" type="button" onClick={acceptUpload} disabled={declareVerified && !sourceNote.trim()}>
              Use this ROI
            </button>
            <button className="btn small" type="button" onClick={() => setPending(null)}>Discard</button>
          </div>
        </div>
      )}

      {roi ? (
        <div className={`callout ${roi.declaredStatus === "registry" && roi.registryVerified ? "good" : "warning"}`} style={{ marginTop: 10 }}>
          <div><strong>{roi.label}</strong></div>
          <div>
            <span className="icon">{roi.declaredStatus === "registry" && roi.registryVerified ? "✓" : "!"}</span>
            {STATUS_TEXT[roi.declaredStatus]}
            {roi.declaredStatus === "registry" && (roi.registryVerified ? " (verified per metadata)" : " (unverified per metadata)")}
          </div>
          {area !== null && (
            <div className="muted">
              ≈ {fmtArea(area)} · {vertexCount(roi.geometry)} vertices
              {maxAreaKm2 !== null && area > maxAreaKm2 && <strong> — exceeds the {fmtArea(maxAreaKm2)} limit</strong>}
            </div>
          )}
          <div className="row" style={{ marginTop: 6 }}>
            <button className="btn small" type="button" onClick={() => downloadRoi(roi)}>Download ROI GeoJSON</button>
            <button className="btn small" type="button" onClick={() => onChange(null)}>Clear ROI</button>
          </div>
        </div>
      ) : (
        <p className="small muted" style={{ marginTop: 10 }}>
          No ROI selected. The platform never invents mine boundaries: register an authoritative polygon on the server,
          upload one, or draw a clearly labelled demonstration rectangle.
        </p>
      )}
    </section>
  );
}
