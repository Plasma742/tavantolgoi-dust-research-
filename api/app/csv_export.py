"""CSV export of a monthly MAIAC series with a provenance header.

Long format: one row per month and variant. ``variant_role`` is ``primary`` for the main
result; ``sensitivity`` rows must never replace it. Statistic definitions in the header are
the same strings as the API schema, protocol and UI (from maiac_method.json).

Rounding: AOD means are written to 0.001, the product's quantisation step; differences to
0.001; fractions to 0.0001. These are export precisions, not uncertainty estimates.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from .datasets import maiac_spec as spec

COLUMNS = (
    "month",
    "variant",
    "variant_role",
    "status",
    "time_start_utc",
    "time_end_exclusive_utc",
    "days_in_period",
    "roi_mean_aod",
    "roi_pooled_retrieval_mean_aod",
    "pixels_total",
    "pixels_with_valid",
    "coverage_fraction",
    "valid_retrievals",
    "valid_retrievals_granule_sum",
    "retrievals_before_qa",
    "qa_retention_fraction",
    "qa_guard_rejections",
    "granules_intersecting",
    "granules_with_valid",
    "valid_day_count",
    "consistency_check_passed",
    "diff_vs_primary_roi_mean_aod",
    "diff_vs_primary_valid_retrievals",
    "diff_vs_primary_valid_day_count",
    "diff_vs_primary_coverage_fraction",
)


def _safe(text: Any) -> str:
    """Neutralise spreadsheet formula injection in free-text fields."""
    value = "" if text is None else str(text).replace("\n", " ").replace("\r", " ")
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t") else value


def _fmt(value: float | None, digits: int) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def _row(month: dict[str, Any], v: dict[str, Any], diff: dict[str, Any] | None) -> list[Any]:
    role = v["role"]
    return [
        month["month"],
        v["variant"],
        role,
        v["status"],
        month["time_start_utc"],
        month["time_end_exclusive_utc"],
        month["days_in_period"],
        _fmt(v["roi_mean_aod"], 3),
        _fmt(v["roi_pooled_retrieval_mean_aod"], 3),
        month["pixels_total"],
        v["pixels_with_valid"],
        _fmt(v["coverage_fraction"], 4),
        v["valid_retrievals"],
        v["valid_retrievals_granule_sum"],
        month["retrievals_before_qa"],
        _fmt(month["qa_retention_fraction"], 4) if role == "primary" else "",
        month["qa_guard_rejections"],
        month["granules_intersecting"],
        v["granules_with_valid"],
        v["valid_day_count"],
        str(v["consistency_check_passed"]).lower(),
        _fmt(diff["roi_mean_aod"], 3) if diff else "",
        diff["valid_retrievals"] if diff else "",
        diff["valid_day_count"] if diff else "",
        _fmt(diff["coverage_fraction"], 4) if diff else "",
    ]


def monthly_csv(series: dict[str, Any]) -> str:
    prov = series["provenance"]
    roi = prov["roi"]
    proc = prov["processing"]
    header: list[tuple[str, Any]] = [
        ("title", "MAIAC AOD 550 nm monthly ROI summary"),
        ("method_version", prov["method_version"]),
        ("primary_variant", prov["primary_variant"]),
        ("observation_type", prov["observation_type"]),
        ("dataset_id", prov["dataset_id"]),
        ("band", f"{prov['band']} -> {prov['derived_band']}"),
        ("unit", prov["unit"]),
        ("scale_factor", prov["scale_factor"]),
        ("clamping", "none (negative AOD kept in the primary variant)"),
    ]
    header += [(f"variant.{v['id']}", f"[{v['role']}] {v['quality_filter']}") for v in prov["variants"]]
    header += [
        ("spatial_rule", spec.SPATIAL_REDUCTION_TEXT),
        ("temporal_rule", spec.TEMPORAL_AGGREGATION_TEXT),
    ]
    header += [(f"definition.{k}", text) for k, text in spec.STATISTIC_DEFINITIONS.items()]
    header += [
        ("roi_label", _safe(roi.get("label"))),
        ("roi_declared_status", roi.get("declared_status")),
        ("roi_status_description", roi.get("status_description")),
        ("roi_source_note", _safe(roi.get("source_note"))),
        ("roi_sha256", roi.get("sha256")),
        ("code_revision", proc.get("code_revision")),
        ("earthengine_api_version", proc.get("earthengine_api_version")),
        ("computed_at_utc", proc["computed_at_utc"]),
        ("source_url", prov["source_url"]),
        ("citation", prov["citation"]),
        (
            "rounding",
            "AOD means and differences to 0.001 (product quantisation), fractions to 0.0001; not uncertainty estimates",
        ),
        ("missing_values", "empty AOD fields = no valid retrieval (see status); never zero"),
        ("sensitivity_rows", "variant_role=sensitivity rows are sensitivity analyses, never the primary result"),
        ("not_a_measurement_of", "; ".join(prov["not_a_measurement_of"])),
        ("caveat", prov["caveat"]),
    ]
    buf = io.StringIO()
    for key, value in header:
        buf.write(f"# {key}: {'' if value is None else value}\n")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(COLUMNS)
    for month in series["rows"]:
        primary = {
            k: month[k]
            for k in (
                "roi_mean_aod",
                "roi_pooled_retrieval_mean_aod",
                "pixels_with_valid",
                "coverage_fraction",
                "valid_retrievals",
                "valid_retrievals_granule_sum",
                "granules_with_valid",
                "valid_day_count",
                "consistency_check_passed",
                "status",
            )
        }
        primary.update({"variant": month["primary_variant"], "role": "primary"})
        writer.writerow(_row(month, primary, None))
        for s in month["sensitivity"]:
            writer.writerow(_row(month, s, s["difference_vs_primary"]))
    return buf.getvalue()
