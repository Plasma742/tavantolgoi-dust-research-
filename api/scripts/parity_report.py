"""Print the backend's MAIAC engine output for one ROI and month, in the same JSON shape as the
"PARITY JSON" line printed by gee/maiac_parity_check.js (for side-by-side comparison).

Usage (from api/, Earth Engine authenticated, EE_PROJECT_ID set):

    python -m scripts.parity_report --roi ../data/roi/private/my_roi.geojson --month 2025-04

Then run gee/maiac_parity_check.js in the Code Editor with the same geometry and month. The
acceptance rule (maiac_method.json) is: integer fields exact, means within the stated absolute
tolerance. tests/test_ee_acceptance.py automates the comparison. Report mismatches; never tune.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import load_settings
from app.datasets import maiac_spec as spec
from app.datasets.maiac_ee import MaiacEarthEngine
from app.datasets.maiac_service import summarize
from app.ee_runtime import EERuntime
from app.periods import month_period
from app.roi import validate_roi


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--roi", required=True, type=Path, help="GeoJSON Polygon/MultiPolygon or Feature")
    parser.add_argument("--month", required=True, help="YYYY-MM")
    args = parser.parse_args()

    settings = load_settings()
    data = json.loads(args.roi.read_text(encoding="utf-8"))
    geometry = data["geometry"] if data.get("type") == "Feature" else data
    valid = validate_roi(
        geometry,
        max_area_km2=settings.max_roi_area_km2,
        max_vertices=settings.max_roi_vertices,
        allowed_bbox=settings.allowed_bbox,
    )
    EERuntime(settings).ensure_ready()
    engine = MaiacEarthEngine(max_pixels=settings.ee_max_pixels)
    period = month_period(args.month)
    raw = engine.period_stats(valid.geometry, period.start, period.end_exclusive)
    print(
        json.dumps(
            {
                "method_version": spec.METHOD_VERSION,
                "roi_geojson": valid.geometry,
                "roi_sha256": valid.sha256,
                "start": period.start.isoformat(),
                "end_exclusive": period.end_exclusive.isoformat(),
                "native_grid": engine.native_grid(),
                "engine_output": raw,
                "summary": summarize(raw, period),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
