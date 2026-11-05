import { useEffect, useRef } from "react";
import type { Provenance } from "../api/types";

function download(name: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function Block({ title, provenance, file }: { title: string; provenance: Provenance; file: string }) {
  const p = provenance as Provenance & {
    spatial?: { native_grid_reported_by_earth_engine?: { crs?: string; nominal_scale_m?: number } | null };
    periods?: { label: string; start_utc: string; end_exclusive_utc: string }[];
    temporal_aggregation?: string;
    spatial_reduction?: string;
  };
  const grid = p.spatial?.native_grid_reported_by_earth_engine;
  const rows: [string, string][] = [
    ["Method version", String(p.method_version ?? "")],
    ["Primary variant", String(p.primary_variant ?? "")],
    ["Observation type", String(p.observation_type ?? "")],
    ["Dataset", p.dataset_id],
    ["Band", `${String(p.band)} → ${String(p.derived_band)} (×${p.scale_factor})`],
    ["Unit", p.unit],
    ["Quality filter", p.quality_filter.text],
    ["Temporal aggregation", p.temporal_aggregation ?? ""],
    ["Spatial reduction", p.spatial_reduction ?? ""],
    ["Native grid (EE)", grid?.crs ? `${grid.crs}, ${grid.nominal_scale_m?.toFixed(3)} m` : "not reported"],
    ["Periods", (p.periods ?? []).map((x) => `${x.label}: ${x.start_utc} → ${x.end_exclusive_utc} (exclusive)`).join("; ")],
    ["ROI", `${p.roi.label} · ${String(p.roi.status_description ?? p.roi.declared_status)}`],
    ["ROI sha256", p.roi.sha256],
    ["Code revision", String(p.processing.code_revision ?? "unknown")],
    ["Computed (UTC)", p.processing.computed_at_utc],
    ["Served from cache", p.processing.served_from_cache ? "yes" : "no"],
    ["Not a measurement of", p.not_a_measurement_of.join(", ")],
    ["Caveat", p.caveat],
    ["Citation", p.citation],
  ];
  return (
    <section className="section">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>{title}</h2>
        <button className="btn small" type="button" onClick={() => download(file, provenance)}>Download JSON</button>
      </div>
      <dl className="kv" style={{ marginTop: 10 }}>
        {rows.map(([k, v]) => (
          <div key={k} style={{ display: "contents" }}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      <p className="small" style={{ marginBottom: 4 }}>
        Source: <a href={p.source_url} target="_blank" rel="noreferrer noopener">{p.source_url}</a>
      </p>
      <details>
        <summary className="small secondary">Full provenance record</summary>
        <pre className="json">{JSON.stringify(provenance, null, 2)}</pre>
      </details>
    </section>
  );
}

interface Props {
  layer: Provenance | null;
  series: Provenance | null;
  onClose: () => void;
}

export function ProvenanceDrawer({ layer, series, onClose }: Props) {
  const closeRef = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <aside className="drawer" role="dialog" aria-modal="true" aria-label="Provenance and method">
      <header>
        <h2>Provenance &amp; method</h2>
        <button ref={closeRef} className="btn small" type="button" onClick={onClose}>Close</button>
      </header>
      {!layer && !series && <p className="section small muted">Nothing computed yet.</p>}
      {layer && <Block title="Map layer" provenance={layer} file="maiac_layer_provenance.json" />}
      {series && <Block title="Monthly series" provenance={series} file="maiac_monthly_provenance.json" />}
      <p className="section small muted">
        Parity check: run <code>gee/maiac_parity_check.js</code> in the Earth Engine Code Editor with the same ROI GeoJSON and
        period, and compare its printed dictionary with these numbers.
      </p>
    </aside>
  );
}
