import type { LayerLegend, LegendStop, MapLayer } from "../api/types";
import type { LayerUiState } from "./MapView";

const MIN_LABEL_GAP = 16; // percent of ramp width

/**
 * Every tick gets a mark on the ramp; a label is skipped when it would collide with a neighbour
 * (first and last labels are always shown). A skipped value stays readable via the mark's title.
 */
export function layoutTicks(ticks: LegendStop[], min: number, max: number) {
  const pos = (v: number) => ((v - min) / (max - min)) * 100;
  const lastPos = ticks.length ? pos(ticks[ticks.length - 1]!.value) : 100;
  const out: (LegendStop & { left: number; show: boolean })[] = [];
  let lastShown = -Infinity;
  ticks.forEach((t, i) => {
    const left = pos(t.value);
    const isEdge = i === 0 || i === ticks.length - 1;
    const show = isEdge || (left - lastShown >= MIN_LABEL_GAP && lastPos - left >= MIN_LABEL_GAP);
    if (show) lastShown = left;
    out.push({ ...t, left, show });
  });
  return out;
}

function Legend({ legend }: { legend: LayerLegend }) {
  if (legend.kind === "categorical") {
    return (
      <div className="small secondary" style={{ marginTop: 4 }}>
        <span className="swatch" style={{ background: `#${legend.palette[0]}` }} aria-hidden="true" />
        <span className="muted">{legend.note}</span>
      </div>
    );
  }
  const min = legend.min ?? 0;
  const max = legend.max ?? 1;
  const gradient = `linear-gradient(to right, ${legend.palette.map((c) => `#${c}`).join(", ")})`;
  const ticks = layoutTicks(legend.ticks, min, max);
  return (
    <div style={{ marginTop: 4 }}>
      <div className="legend-ramp" style={{ background: gradient, position: "relative" }} role="img"
        aria-label={`${legend.title}: colour ramp from ${legend.ticks[0]?.label ?? min} to ${legend.ticks[legend.ticks.length - 1]?.label ?? max} ${legend.unit}`}>
        {ticks.map((t) => (
          <span key={`m-${t.label}`} className="legend-mark" data-testid="legend-mark" data-value={t.value}
            title={t.label} style={{ left: `${t.left}%` }} />
        ))}
      </div>
      <div className="legend-ticks tabular" aria-hidden="true">
        {ticks.filter((t) => t.show).map((t) => (
          <span key={t.label} style={{ left: `${t.left}%` }}>{t.label}</span>
        ))}
      </div>
      <div className="small muted">Unit: {legend.unit}</div>
      <div className="small muted">{legend.note}</div>
    </div>
  );
}

interface Props {
  layers: MapLayer[];
  state: Record<string, LayerUiState>;
  dimBasemap: boolean;
  onState: (id: string, next: LayerUiState) => void;
  onDimBasemap: (value: boolean) => void;
  nativeScaleM: number | null;
}

export function LayerPanel({ layers, state, dimBasemap, onState, onDimBasemap, nativeScaleM }: Props) {
  return (
    <section className="section" aria-labelledby="layers-h">
      <h2 id="layers-h">3 · Layers &amp; legend</h2>
      {layers.length === 0 ? (
        <p className="small muted">No data layers loaded. Nothing is drawn until Earth Engine returns real observations.</p>
      ) : (
        layers.map((layer) => {
          const s = state[layer.id] ?? { visible: layer.default_visible, opacity: layer.default_opacity };
          return (
            <div className="layer" key={layer.id}>
              <div className="layer-head">
                <input
                  id={`vis-${layer.id}`}
                  type="checkbox"
                  checked={s.visible}
                  onChange={(e) => onState(layer.id, { ...s, visible: e.target.checked })}
                />
                <label htmlFor={`vis-${layer.id}`}>{layer.title}</label>
                <input
                  type="range" min={0} max={1} step={0.05} value={s.opacity}
                  aria-label={`${layer.title} opacity`}
                  onChange={(e) => onState(layer.id, { ...s, opacity: Number(e.target.value) })}
                />
              </div>
              <Legend legend={layer.legend} />
            </div>
          );
        })
      )}
      <label className="row small" style={{ marginTop: 8 }}>
        <input type="checkbox" checked={dimBasemap} onChange={(e) => onDimBasemap(e.target.checked)} />
        Dim basemap (display context only)
      </label>
      <p className="small muted" style={{ marginBottom: 0 }}>
        Native grid: MODIS sinusoidal, catalog pixel 1 km
        {nativeScaleM !== null && <> (Earth Engine reports {nativeScaleM.toFixed(1)} m)</>}. Zooming in does not add
        resolution; pixels are drawn with nearest-neighbour sampling.
      </p>
    </section>
  );
}
