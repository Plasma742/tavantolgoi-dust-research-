"""Request and response models (also published as OpenAPI at /api/openapi.json).

Statistic descriptions come verbatim from ``maiac_method.json`` so the API schema, CSV
header, UI and research protocol all use one definition.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .datasets.maiac_spec import STATISTIC_DEFINITIONS as D

DeclaredStatus = Literal["demonstration", "unverified_upload", "user_declared_verified", "registry"]
PeriodStatus = Literal["OK", "NO_GRANULES", "NO_VALID_OBSERVATIONS"]


class RoiInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geometry: dict[str, Any] | None = Field(
        None, description="GeoJSON Polygon or MultiPolygon in WGS84 lon/lat. Omit when registry_id is set."
    )
    registry_id: str | None = Field(None, max_length=120, description="ID of a server-registered ROI.")
    label: str = Field(..., min_length=1, max_length=120)
    declared_status: DeclaredStatus
    source_note: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def _check(self) -> RoiInput:
        if self.declared_status == "registry":
            if not self.registry_id:
                raise ValueError("registry_id is required when declared_status is 'registry'.")
        elif self.geometry is None:
            raise ValueError("geometry is required unless a registry ROI is used.")
        if self.declared_status == "user_declared_verified" and not (self.source_note or "").strip():
            raise ValueError("A source_note is required to declare an uploaded ROI as verified.")
        return self


class MaiacLayerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roi: RoiInput
    start: date = Field(..., description="Inclusive UTC start date.")
    end_exclusive: date = Field(..., description="Exclusive UTC end date (Earth Engine filterDate semantics).")


class MonthlySeriesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roi: RoiInput
    start_month: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    end_month: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="Inclusive.")


class VariantStats(BaseModel):
    variant: str
    role: Literal["primary", "sensitivity"]
    label: str
    definition: str
    status: PeriodStatus
    status_message: str
    roi_mean_aod: float | None = Field(description=D["roi_mean_aod"])
    roi_pooled_retrieval_mean_aod: float | None = Field(description=D["roi_pooled_retrieval_mean_aod"])
    valid_retrievals: int = Field(description=D["valid_retrievals"])
    valid_retrievals_granule_sum: int = Field(description=D["valid_retrievals_granule_sum"])
    pixels_with_valid: int = Field(description=D["pixels_with_valid"])
    coverage_fraction: float | None = Field(description=D["coverage_fraction"])
    granules_with_valid: int = Field(description=D["granules_with_valid"])
    valid_day_count: int = Field(description=D["valid_day_count"])
    consistency_check_passed: bool = Field(description="valid_retrievals == valid_retrievals_granule_sum")


class VariantDifference(BaseModel):
    """Sensitivity variant minus primary. null where either value is null."""

    valid_retrievals: int
    valid_day_count: int
    pixels_with_valid: int
    coverage_fraction: float | None
    roi_mean_aod: float | None
    roi_pooled_retrieval_mean_aod: float | None


class SensitivityResult(VariantStats):
    difference_vs_primary: VariantDifference


class PeriodSummary(BaseModel):
    method_version: str
    primary_variant: str
    status: PeriodStatus
    status_message: str
    time_start_utc: str
    time_end_exclusive_utc: str
    days_in_period: int
    roi_mean_aod: float | None = Field(description=D["roi_mean_aod"])
    roi_pooled_retrieval_mean_aod: float | None = Field(description=D["roi_pooled_retrieval_mean_aod"])
    pixels_total: int = Field(description=D["pixels_total"])
    pixels_with_valid: int = Field(description=D["pixels_with_valid"])
    coverage_fraction: float | None = Field(description=D["coverage_fraction"])
    valid_retrievals: int = Field(description=D["valid_retrievals"])
    valid_retrievals_granule_sum: int = Field(description=D["valid_retrievals_granule_sum"])
    retrievals_before_qa: int = Field(description=D["retrievals_before_qa"])
    qa_retention_fraction: float | None = Field(description=D["qa_retention_fraction"])
    qa_guard_rejections: int = Field(description=D["qa_guard_rejections"])
    granules_intersecting: int = Field(description=D["granules_intersecting"])
    granules_with_valid: int = Field(description=D["granules_with_valid"])
    valid_day_count: int = Field(description=D["valid_day_count"])
    consistency_check_passed: bool = Field(description="valid_retrievals == valid_retrievals_granule_sum (primary)")
    sensitivity: list[SensitivityResult] = Field(
        description="Sensitivity variants computed in the same pass. Never a replacement for the primary result."
    )


class MonthlyRow(PeriodSummary):
    month: str


class LegendStop(BaseModel):
    value: float
    label: str


class LayerLegend(BaseModel):
    kind: Literal["continuous", "categorical"]
    title: str
    unit: str
    palette: list[str]
    min: float | None = None
    max: float | None = None
    ticks: list[LegendStop] = []
    note: str


class MapLayer(BaseModel):
    id: str
    title: str
    observation_type: str
    variant: str
    tile_url_template: str
    max_native_zoom: int
    default_visible: bool
    default_opacity: float
    legend: LayerLegend


class LayerResponse(BaseModel):
    status: PeriodStatus
    dataset_key: str
    layers: list[MapLayer]
    summary: PeriodSummary
    provenance: dict[str, Any]
    tiles_note: str


class MonthlySeriesResponse(BaseModel):
    dataset_key: str
    rows: list[MonthlyRow]
    provenance: dict[str, Any]
