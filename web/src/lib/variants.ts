import type { PeriodStatus, PeriodSummary, VariantDifference, VariantRole } from "../api/types";

/** One variant's statistics for a period, primary or sensitivity, in a uniform shape. */
export interface VariantView {
  id: string;
  role: VariantRole;
  label: string;
  status: PeriodStatus;
  roi_mean_aod: number | null;
  roi_pooled_retrieval_mean_aod: number | null;
  valid_retrievals: number;
  valid_day_count: number;
  coverage_fraction: number | null;
  pixels_with_valid: number;
  granules_with_valid: number;
  consistency_check_passed: boolean;
  difference: VariantDifference | null;
}

export function primaryLabel(summary: PeriodSummary): string {
  return `Primary (${summary.primary_variant})`;
}

export function variantView(summary: PeriodSummary, variantId: string): VariantView {
  if (variantId === summary.primary_variant) {
    return {
      id: summary.primary_variant,
      role: "primary",
      label: primaryLabel(summary),
      status: summary.status,
      roi_mean_aod: summary.roi_mean_aod,
      roi_pooled_retrieval_mean_aod: summary.roi_pooled_retrieval_mean_aod,
      valid_retrievals: summary.valid_retrievals,
      valid_day_count: summary.valid_day_count,
      coverage_fraction: summary.coverage_fraction,
      pixels_with_valid: summary.pixels_with_valid,
      granules_with_valid: summary.granules_with_valid,
      consistency_check_passed: summary.consistency_check_passed,
      difference: null,
    };
  }
  const s = summary.sensitivity.find((v) => v.variant === variantId);
  if (!s) throw new Error(`Unknown variant ${variantId}`);
  return {
    id: s.variant,
    role: s.role,
    label: s.label,
    status: s.status,
    roi_mean_aod: s.roi_mean_aod,
    roi_pooled_retrieval_mean_aod: s.roi_pooled_retrieval_mean_aod,
    valid_retrievals: s.valid_retrievals,
    valid_day_count: s.valid_day_count,
    coverage_fraction: s.coverage_fraction,
    pixels_with_valid: s.pixels_with_valid,
    granules_with_valid: s.granules_with_valid,
    consistency_check_passed: s.consistency_check_passed,
    difference: s.difference_vs_primary,
  };
}

export function variantOptions(summary: PeriodSummary): { id: string; role: VariantRole; label: string }[] {
  return [
    { id: summary.primary_variant, role: "primary", label: primaryLabel(summary) },
    ...summary.sensitivity.map((s) => ({ id: s.variant, role: s.role, label: s.label })),
  ];
}
