import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, LngLatBoundsLike, Map as MlMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { useEffect, useRef, useState } from "react";
import { tileUrl } from "../api/client";
import type { DeclaredStatus, MapLayer, PolygonGeometry } from "../api/types";
import { bboxOf, rectangleFromCorners, type LonLat } from "../lib/roi";

export interface LayerUiState {
  visible: boolean;
  opacity: number;
}

interface Props {
  roi: PolygonGeometry | null;
  roiStatus: DeclaredStatus | null;
  roiVerified: boolean;
  layers: MapLayer[];
  layerState: Record<string, LayerUiState>;
  dimBasemap: boolean;
  drawing: boolean;
  onDrawComplete: (geometry: PolygonGeometry) => void;
  onDrawCancel: () => void;
  onTileProblem: (kind: "data" | "basemap", message: string) => void;
}

// Initial view only: Wikipedia's point coordinate for the Tavan Tolgoi deposit
// (43.625 N, 105.474 E). It is NOT drawn and is NOT a mine boundary.
const INITIAL_CENTER: [number, number] = [105.474, 43.625];
const BASEMAP_URL =
  import.meta.env.VITE_BASEMAP_URL ??
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const BASEMAP_ATTRIBUTION =
  import.meta.env.VITE_BASEMAP_ATTRIBUTION ?? "Basemap: Esri World Imagery (© Esri and its data providers)";
const EE_ATTRIBUTION = "MAIAC MCD19A2.061: NASA LP DAAC, processed in Google Earth Engine";
// MapLibre derives its worker URL from import.meta.url, which breaks after bundling; point it
// at the worker that Vite bundles for us.
maplibregl.setWorkerUrl(workerUrl);

const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

function asFeature(geometry: PolygonGeometry): GeoJSON.FeatureCollection {
  return { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry: geometry as GeoJSON.Geometry }] };
}

export function MapView(props: Props) {
  const { roi, roiStatus, roiVerified, layers, layerState, dimBasemap, drawing, onDrawComplete, onDrawCancel, onTileProblem } =
    props;
  const container = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MlMap | null>(null);
  const [ready, setReady] = useState(false);
  const eeLayerIds = useRef<string[]>([]);
  const problemRef = useRef(onTileProblem);

  useEffect(() => {
    problemRef.current = onTileProblem;
  }, [onTileProblem]);

  // -- init -------------------------------------------------------------------------
  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      center: INITIAL_CENTER,
      zoom: 8,
      maxZoom: 15,
      attributionControl: false,
      style: {
        version: 8,
        sources: {
          basemap: { type: "raster", tiles: [BASEMAP_URL], tileSize: 256, maxzoom: 18, attribution: BASEMAP_ATTRIBUTION },
          roi: { type: "geojson", data: EMPTY },
          draft: { type: "geojson", data: EMPTY },
        },
        layers: [
          { id: "background", type: "background", paint: { "background-color": "#1a1a19" } },
          { id: "basemap", type: "raster", source: "basemap", paint: { "raster-saturation": -0.5, "raster-brightness-max": 0.75 } },
          { id: "roi-outline", type: "line", source: "roi", paint: { "line-color": "#f0efec", "line-width": 2 } },
          {
            id: "draft-fill", type: "fill", source: "draft",
            paint: { "fill-color": "#f0efec", "fill-opacity": 0.08 },
          },
          { id: "draft-line", type: "line", source: "draft", paint: { "line-color": "#fab219", "line-width": 2 } },
        ],
      },
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: false, showCompass: false }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
    map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: EE_ATTRIBUTION }), "bottom-right");
    let basemapWarned = false;
    map.on("error", (event) => {
      const e = event as unknown as { sourceId?: string; error?: { status?: number; message?: string } };
      if (e.sourceId?.startsWith("ee-")) {
        // The backend answers 410 Gone for expired layers (MapLibre ignores 404 tiles silently).
        problemRef.current(
          "data",
          e.error?.status === 410
            ? "Map layer tiles expired. Press 'Load MAIAC AOD layer' again."
            : `A data tile failed to load (${e.error?.message ?? "unknown error"}).`,
        );
      } else if (e.sourceId === "basemap" && !basemapWarned) {
        basemapWarned = true;
        problemRef.current("basemap", "Basemap tiles could not be loaded (network or provider). Data layers are unaffected.");
      }
    });
    map.on("load", () => setReady(true));
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // -- basemap dimming ----------------------------------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    map.setPaintProperty("basemap", "raster-brightness-max", dimBasemap ? 0.55 : 1);
    map.setPaintProperty("basemap", "raster-saturation", dimBasemap ? -0.6 : 0);
  }, [dimBasemap, ready]);

  // -- ROI ----------------------------------------------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    (map.getSource("roi") as GeoJSONSource).setData(roi ? asFeature(roi) : EMPTY);
    // Demonstration / unverified outlines are dashed; registry-verified ROIs are solid.
    map.setPaintProperty("roi-outline", "line-dasharray", roiStatus === "registry" && roiVerified ? [1, 0] : [3, 2]);
    if (roi) {
      const [w, s, e, n] = bboxOf(roi);
      map.fitBounds([[w, s], [e, n]] as LngLatBoundsLike, { padding: 60, maxZoom: 11, duration: 600 });
    }
  }, [roi, roiStatus, roiVerified, ready]);

  // -- Earth Engine layers --------------------------------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    for (const id of eeLayerIds.current) {
      if (map.getLayer(id)) map.removeLayer(id);
      if (map.getSource(id)) map.removeSource(id);
    }
    eeLayerIds.current = [];
    // Draw order bottom->top: no-valid mask, count, AOD mean — ROI outline stays on top.
    const order = ["no_valid_retrieval", "valid_count", "aod_mean"];
    const sorted = [...layers].sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
    for (const layer of sorted) {
      const id = `ee-${layer.id}`;
      map.addSource(id, {
        type: "raster",
        tiles: [tileUrl(layer.tile_url_template)],
        tileSize: 256,
        maxzoom: layer.max_native_zoom,
      });
      map.addLayer(
        { id, type: "raster", source: id, paint: { "raster-resampling": "nearest", "raster-fade-duration": 0 } },
        "roi-outline",
      );
      eeLayerIds.current.push(id);
    }
  }, [layers, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    for (const layer of layers) {
      const id = `ee-${layer.id}`;
      const state = layerState[layer.id];
      if (!map.getLayer(id) || !state) continue;
      map.setLayoutProperty(id, "visibility", state.visible ? "visible" : "none");
      map.setPaintProperty(id, "raster-opacity", state.opacity);
    }
  }, [layers, layerState, ready]);

  // -- rectangle drawing ----------------------------------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !drawing) return;
    let first: LonLat | null = null;
    const draft = map.getSource("draft") as GeoJSONSource;
    map.getCanvas().style.cursor = "crosshair";
    map.doubleClickZoom.disable();

    const onClick = (e: maplibregl.MapMouseEvent) => {
      const point: LonLat = [e.lngLat.lng, e.lngLat.lat];
      if (!first) {
        first = point;
        return;
      }
      const geometry = rectangleFromCorners(first, point);
      draft.setData(EMPTY);
      onDrawComplete(geometry);
    };
    const onMove = (e: maplibregl.MapMouseEvent) => {
      if (first) draft.setData(asFeature(rectangleFromCorners(first, [e.lngLat.lng, e.lngLat.lat])));
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        draft.setData(EMPTY);
        onDrawCancel();
      }
    };
    map.on("click", onClick);
    map.on("mousemove", onMove);
    window.addEventListener("keydown", onKey);
    return () => {
      map.off("click", onClick);
      map.off("mousemove", onMove);
      window.removeEventListener("keydown", onKey);
      map.getCanvas().style.cursor = "";
      map.doubleClickZoom.enable();
      draft.setData(EMPTY);
    };
  }, [drawing, ready, onDrawComplete, onDrawCancel]);

  return (
    <div className="map-wrap">
      <div ref={container} className="map" role="region" aria-label="Satellite map" />
      {drawing && (
        <div className="map-hint" role="status">
          Click two opposite corners to draw a <strong>demonstration</strong> rectangle · Esc to cancel
        </div>
      )}
    </div>
  );
}
