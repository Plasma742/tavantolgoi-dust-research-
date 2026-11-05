// TypeScript mirror of api/app/schemas.py. Keep in sync with the OpenAPI schema at /api/openapi.json.

export type DeclaredStatus = "demonstration" | "unverified_upload" | "user_declared_verified" | "registry";
export type PeriodStatus = "OK" | "NO_GRANULES" | "NO_VALID_OBSERVATIONS";
export type EEStatus = "NOT_CONFIGURED" | "NOT_INITIALIZED" | "READY" | "AUTH_ERROR";

export interface PolygonGeometry {
  type: "Polygon" | "MultiPolygon";
  coordinates: number[][][] | number[][][][];
}

export interface RoiInput {
  geometry?: PolygonGeometry;
  registry_id?: string;
  label: string;
  declared_status: DeclaredStatus;
  source_note?: string | null;
}

export interface Health {
  status: "ok";
  version: string;
  code_revision: string | null;
  earth_engine: {
    status: EEStatus;
    message: string | null;
    project_configured: boolean;
    auth_mode: string;
    earthengine_api_version: string | null;
  };
  limits: {
    max_roi_area_km2: number;
    max_roi_vertices: number;
    allowed_bbox: [number, number, number, number];
    max_layer_days: number;
    max_series_months: number;
  };
  deployment: string;
}

export type VariantRole = "primary" | "sensitivity";

export interface VariantStats {
  variant: string;
  role: VariantRole;
  label: string;
  definition: string;
  status: PeriodStatus;
  status_message: string;
  roi_mean_aod: number | null;
  roi_pooled_retrieval_mean_aod: number | null;
  valid_retrievals: number;
  valid_retrievals_granule_sum: number;
  pixels_with_valid: number;
  coverage_fraction: number | null;
  granules_with_valid: number;
  valid_day_count: number;
  consistency_check_passed: boolean;
}

export interface VariantDifference {
  valid_retrievals: number;
  valid_day_count: number;
  pixels_with_valid: number;
  coverage_fraction: number | null;
  roi_mean_aod: number | null;
  roi_pooled_retrieval_mean_aod: number | null;
}

export interface SensitivityResult extends VariantStats {
  difference_vs_primary: VariantDifference;
}

export interface PeriodSummary {
  method_version: string;
  primary_variant: string;
  status: PeriodStatus;
  status_message: string;
  time_start_utc: string;
  time_end_exclusive_utc: string;
  days_in_period: number;
  roi_mean_aod: number | null;
  roi_pooled_retrieval_mean_aod: number | null;
  pixels_total: number;
  pixels_with_valid: number;
  coverage_fraction: number | null;
  valid_retrievals: number;
  valid_retrievals_granule_sum: number;
  retrievals_before_qa: number;
  qa_retention_fraction: number | null;
  qa_guard_rejections: number;
  granules_intersecting: number;
  granules_with_valid: number;
  valid_day_count: number;
  consistency_check_passed: boolean;
  sensitivity: SensitivityResult[];
}

export interface MonthlyRow extends PeriodSummary {
  month: string;
}

export interface LegendStop {
  value: number;
  label: string;
}

export interface LayerLegend {
  kind: "continuous" | "categorical";
  title: string;
  unit: string;
  palette: string[];
  min: number | null;
  max: number | null;
  ticks: LegendStop[];
  note: string;
}

export interface MapLayer {
  id: string;
  title: string;
  observation_type: string;
  variant: string;
  tile_url_template: string;
  max_native_zoom: number;
  default_visible: boolean;
  default_opacity: number;
  legend: LayerLegend;
}

export type Provenance = Record<string, unknown> & {
  dataset_id: string;
  unit: string;
  scale_factor: number;
  quality_filter: { text: string };
  roi: Record<string, unknown> & { label: string; declared_status: DeclaredStatus; sha256: string };
  not_a_measurement_of: string[];
  caveat: string;
  citation: string;
  source_url: string;
  processing: Record<string, unknown> & { method_version: string; computed_at_utc: string; served_from_cache: boolean };
};

export interface LayerResponse {
  status: PeriodStatus;
  dataset_key: string;
  layers: MapLayer[];
  summary: PeriodSummary;
  provenance: Provenance;
  tiles_note: string;
}

export interface MonthlySeriesResponse {
  dataset_key: string;
  rows: MonthlyRow[];
  provenance: Provenance;
}

export interface DatasetEntry {
  key: string;
  status: "implemented" | "planned";
  title: string;
  collection_id: string;
  observation_type: string;
  observation_type_label: string;
  variables: { band: string; unit: string; quantity?: string }[];
  native_grid: string;
  temporal_support: string;
  caveats: string[];
  not_a_measurement_of: string[];
  catalog_url: string;
  citation?: string;
  metadata_note: string;
}

export interface DatasetsResponse {
  datasets: DatasetEntry[];
  unavailable_modules: { key: string; title: string; status: "not_available"; reason: string }[];
}

export interface MethodVariant {
  id: string;
  role: VariantRole;
  label: string;
  raw_range: [number, number];
  aod_range: [number, number];
  adjacency_policy: string;
  quality_filter: string;
  text: string;
}

export interface MethodDescription {
  method_version: string;
  qa_fields: { name: string; bits: string; documented_values: number[] }[];
  core_qa: string;
  documented_value_guard: string;
  adjacency_policies: Record<string, string>;
  variants: MethodVariant[];
  spatial_rule: { text: string };
  temporal_rule: string;
  statistic_definitions: Record<string, string>;
  acceptance: { test_month: string; mean_abs_tolerance: number; note: string };
}

export interface MethodsResponse {
  method_version: string;
  code_revision: string | null;
  maiac: {
    dataset_id: string;
    band: string;
    qa_band: string;
    scale_factor: number;
    unit: string;
    quality_filter: string;
    physical_range: [number, number];
    temporal_aggregation: string;
    spatial_reduction: string;
    not_a_measurement_of: string[];
    caveat: string;
    citation: string;
    catalog_url: string;
    method: MethodDescription;
    parity_scripts: { acceptance: string; legacy_exploratory: string };
    review_notes: string[];
  };
  quota_note: string;
}

export interface RegistryRoi {
  id: string;
  label: string;
  verified: boolean;
  source: string | null;
  license: string | null;
  observation_date: string | null;
  notes: string | null;
  geometry: PolygonGeometry;
}

export interface RoisResponse {
  rois: RegistryRoi[];
  problems: { file: string; problem: string }[];
  note: string;
}
