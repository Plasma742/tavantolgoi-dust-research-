import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { DatasetsResponse, MethodsResponse } from "../api/types";

export function MethodsPage() {
  const [datasets, setDatasets] = useState<DatasetsResponse | null>(null);
  const [methods, setMethods] = useState<MethodsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.datasets(), api.methods()])
      .then(([d, m]) => {
        setDatasets(d);
        setMethods(m);
      })
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Could not load method documentation."));
  }, []);

  return (
    <div className="page">
      <h2>Data &amp; methods</h2>
      <p>
        This platform separates <strong>satellite observations</strong>, <strong>meteorological model / reanalysis fields</strong>,
        <strong> statistical attribution</strong> and <strong>dispersion simulation</strong>. Only the first is implemented:
        QA-filtered MAIAC aerosol optical depth at 550 nm. Nothing here measures PM10 or attributes dust to the mine.
      </p>
      {error && <div className="callout critical" role="alert"><span className="icon">✕</span>{error}</div>}

      {methods && (
        <>
          <h3>MAIAC AOD processing <span className="badge">{methods.method_version}</span></h3>
          <dl className="kv">
            <dt>Dataset</dt><dd><code>{methods.maiac.dataset_id}</code> · band <code>{methods.maiac.band}</code> · QA <code>{methods.maiac.qa_band}</code></dd>
            <dt>Scaling</dt><dd>× {methods.maiac.scale_factor} → {methods.maiac.unit} AOD</dd>
            <dt>Quality filter</dt><dd>{methods.maiac.quality_filter}</dd>
            <dt>Temporal aggregation</dt><dd>{methods.maiac.temporal_aggregation}</dd>
            <dt>Spatial reduction</dt><dd>{methods.maiac.spatial_reduction}</dd>
            <dt>Not a measurement of</dt><dd>{methods.maiac.not_a_measurement_of.join(" · ")}</dd>
            <dt>Caveat</dt><dd>{methods.maiac.caveat}</dd>
            <dt>Citation</dt><dd>{methods.maiac.citation}</dd>
            <dt>Code revision</dt><dd>{methods.code_revision ?? "unknown"}</dd>
          </dl>
          <h3>Processing variants</h3>
          <table className="data">
            <thead><tr><th>Variant</th><th>Role</th><th>Raw range</th><th>AOD range</th><th>Rule</th></tr></thead>
            <tbody>
              {methods.maiac.method.variants.map((v) => (
                <tr key={v.id}>
                  <td><code>{v.id}</code></td>
                  <td>{v.role === "primary" ? "Primary" : "Sensitivity — not the primary result"}</td>
                  <td>{v.raw_range[0]}..{v.raw_range[1]}</td>
                  <td>{v.aod_range[0].toFixed(3)}..{v.aod_range[1].toFixed(3)}</td>
                  <td style={{ textAlign: "left", whiteSpace: "normal" }}>{v.text}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <h3>AOD_QA decoding</h3>
          <p>{methods.maiac.method.core_qa}. {methods.maiac.method.documented_value_guard}</p>
          <ul>
            {methods.maiac.method.qa_fields.map((f) => (
              <li key={f.name}><code>{f.name}</code> bits {f.bits}: documented values {f.documented_values.join(", ")}</li>
            ))}
          </ul>
          <h3>Statistic definitions</h3>
          <dl className="kv">
            {Object.entries(methods.maiac.method.statistic_definitions).map(([k, v]) => (
              <div key={k} style={{ display: "contents" }}><dt><code>{k}</code></dt><dd>{v}</dd></div>
            ))}
          </dl>
          <h3>Parity scripts</h3>
          <ul>
            <li>Acceptance: {methods.maiac.parity_scripts.acceptance}</li>
            <li>Legacy: {methods.maiac.parity_scripts.legacy_exploratory}</li>
          </ul>
          <h3>Review notes</h3>
          <ul>{methods.maiac.review_notes.map((q) => <li key={q}>{q}</li>)}</ul>
          <h3>Compute quota</h3>
          <p>{methods.quota_note}</p>
        </>
      )}

      {datasets && (
        <>
          <h2>Dataset catalog</h2>
          <div className="cards">
            {datasets.datasets.map((d) => (
              <article className="card" key={d.key}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <h3>{d.title}</h3>
                  <span className="badge">{d.status === "implemented" ? "✓ Implemented" : "Planned"}</span>
                </div>
                <div className="small secondary">{d.observation_type_label}</div>
                <div className="small"><code>{d.collection_id}</code></div>
                <div className="small muted">Grid: {d.native_grid} · {d.temporal_support}</div>
                <div className="small muted">Variables: {d.variables.map((v) => `${v.band} (${v.unit})`).join("; ")}</div>
                <ul className="small">{d.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
                <div className="small muted">{d.metadata_note}</div>
                <a className="small" href={d.catalog_url} target="_blank" rel="noreferrer noopener">Earth Engine catalog</a>
              </article>
            ))}
          </div>

          <h2>Not yet available</h2>
          <div className="cards">
            {datasets.unavailable_modules.map((m) => (
              <article className="card" key={m.key}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <h3>{m.title}</h3>
                  <span className="badge">Not yet available</span>
                </div>
                <p className="small">{m.reason}</p>
              </article>
            ))}
          </div>
        </>
      )}

      <h2>Display context</h2>
      <p>
        The satellite basemap is display context only and is not used in any computation. Earth Engine tiles are proxied by
        the backend, so no Google credentials or Earth Engine URLs reach the browser.
      </p>
    </div>
  );
}
