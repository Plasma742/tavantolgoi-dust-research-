"""Executable reference definition of the MAIAC period statistics (pure Python, no Earth Engine).

It computes exactly what ``maiac_ee.MaiacEarthEngine.period_stats`` computes, on a small
synthetic pixel grid, so the definitions in ``maiac_method.json`` can be tested offline
(including edge pixels, empty periods and every variant). Its output has the same shape as
the Earth Engine engine output and feeds ``maiac_service.summarize``.

Test data built with this module is synthetic and must never be presented as observations.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from . import maiac_spec as spec

Pixel = tuple[int, int]


@dataclass(frozen=True)
class Granule:
    utc_day: str  # YYYY-MM-DD of system:time_start
    pixels: Mapping[Pixel, tuple[int | None, int | None]] = field(default_factory=dict)
    # pixel -> (raw Optical_Depth_055 or None if masked, AOD_QA or None if masked); absent = no data


def reference_period_stats(granules: Iterable[Granule], roi_pixels: set[Pixel]) -> dict[str, Any]:
    """``roi_pixels`` are the native-grid pixels whose centre lies inside the ROI."""
    granules = list(granules)
    retrievals_before_qa = 0
    guard_rejections = 0
    per_variant: dict[str, dict[str, Any]] = {}
    for variant in spec.VARIANTS:
        per_pixel: dict[Pixel, list[float]] = {}
        granule_counts: list[int] = []
        valid_days: set[str] = set()
        for g in granules:
            n = 0
            for px in roi_pixels:
                raw, qa = g.pixels.get(px, (None, None))
                if spec.is_valid_retrieval(raw, qa, variant):
                    per_pixel.setdefault(px, []).append(spec.scale_raw_aod(raw))  # type: ignore[arg-type]
                    n += 1
            granule_counts.append(n)
            if n > 0:
                valid_days.add(g.utc_day)
        pixel_means = [sum(v) / len(v) for v in per_pixel.values()]
        per_variant[variant.id] = {
            "valid_retrievals": sum(len(v) for v in per_pixel.values()),
            "valid_retrievals_granule_sum": sum(granule_counts),
            "pixels_with_valid": len(per_pixel),
            "roi_mean_aod": (sum(pixel_means) / len(pixel_means)) if pixel_means else None,
            "aod_sum": sum(sum(v) for v in per_pixel.values()),
            "granules_with_valid": sum(1 for n in granule_counts if n > 0),
            "valid_day_count": len(valid_days),
        }
    for g in granules:
        for px in roi_pixels:
            raw, qa = g.pixels.get(px, (None, None))
            if spec.raw_present(raw):
                retrievals_before_qa += 1
            if spec.is_guard_rejection(raw, qa):
                guard_rejections += 1
    return {
        "granules_intersecting": len(granules),
        "pixels_total": len(roi_pixels),
        "retrievals_before_qa": retrievals_before_qa,
        "qa_guard_rejections": guard_rejections,
        "variants": per_variant,
    }
