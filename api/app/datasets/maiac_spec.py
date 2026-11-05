"""MAIAC MCD19A2.061 processing specification - pure Python, no Earth Engine import.

The canonical, machine-readable method is ``maiac_method.json`` (same folder). This module
loads it and is the single Python entry point for:

* the Earth Engine implementation (``maiac_ee.py``),
* the API method documentation (``GET /api/methods``) and provenance records,
* the generated parity script (``gee/maiac_parity_check.js``) and protocol section,
* unit tests that check QA/range logic without Earth Engine access.

Sources (checked 2026-11-04): GEE catalog for MODIS/061/MCD19A2_GRANULES (Optical_Depth_055
raw range -100..8000, scale 0.001) and the MAIAC user guide / LAADS file spec AOD_QA table
(bits 0-2 cloud mask, 3-4 land/water/snow/ice, 5-7 adjacency, 8-11 QA for AOD, 12 glint,
13-14 aerosol model, 15 reserved).

Any change to maiac_method.json is a methodology change: bump ``method_version``, then run
``python -m scripts.generate_method_artifacts`` to refresh the parity script and protocol.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

METHOD_PATH = Path(__file__).with_name("maiac_method.json")
METHOD: dict[str, Any] = json.loads(METHOD_PATH.read_text(encoding="utf-8"))

METHOD_VERSION: str = METHOD["method_version"]
_DS = METHOD["dataset"]
DATASET_KEY: str = _DS["key"]
COLLECTION_ID: str = _DS["collection_id"]
DATASET_TITLE: str = _DS["title"]
CATALOG_URL: str = _DS["catalog_url"]
CITATION: str = _DS["citation"]
DATASET_START_DATE: str = _DS["start_date"]
AOD_BAND: str = _DS["aod_band"]
QA_BAND: str = _DS["qa_band"]
DERIVED_BAND: str = _DS["derived_band"]
SCALE_FACTOR: float = _DS["scale_factor"]
OFFSET: float = _DS["offset"]
UNIT: str = _DS["unit"]
QUANTITY: str = _DS["quantity"]
RAW_VALID_MIN, RAW_VALID_MAX = (int(v) for v in _DS["product_valid_raw_range"])
CATALOG_PIXEL_SIZE_M: int = _DS["catalog_pixel_size_m"]

STATISTIC_DEFINITIONS: dict[str, str] = METHOD["statistic_definitions"]
SPATIAL_REDUCTION_TEXT: str = METHOD["spatial_rule"]["text"]
TEMPORAL_AGGREGATION_TEXT: str = METHOD["temporal_rule"]["text"]


@dataclass(frozen=True)
class QaField:
    name: str
    start_bit: int
    n_bits: int
    documented_values: tuple[int, ...]

    @property
    def mask(self) -> int:
        return (1 << self.n_bits) - 1

    @property
    def bits(self) -> str:
        return f"{self.start_bit}-{self.start_bit + self.n_bits - 1}" if self.n_bits > 1 else str(self.start_bit)

    def value(self, qa: int) -> int:
        return (qa >> self.start_bit) & self.mask


@dataclass(frozen=True)
class Variant:
    id: str
    role: str  # "primary" | "sensitivity"
    label: str
    raw_min: int
    raw_max: int
    adjacency_policy: str
    adjacency_accept: tuple[int, ...] | None
    text: str

    @property
    def aod_min(self) -> float:
        return self.raw_min * SCALE_FACTOR + OFFSET

    @property
    def aod_max(self) -> float:
        return self.raw_max * SCALE_FACTOR + OFFSET


QA_FIELDS: dict[str, QaField] = {
    f["name"]: QaField(f["name"], f["start_bit"], f["n_bits"], tuple(f["documented_values"]))
    for f in METHOD["qa"]["fields"]
}
CORE_QA_ACCEPT: dict[str, tuple[int, ...]] = {k: tuple(v) for k, v in METHOD["qa"]["core_qa"]["accept"].items()}
CORE_QA_TEXT: str = METHOD["qa"]["core_qa"]["text"]
GUARD_FIELDS: tuple[str, ...] = tuple(METHOD["qa"]["documented_value_guard"]["fields"])
GUARD_TEXT: str = METHOD["qa"]["documented_value_guard"]["text"]
ADJACENCY_POLICIES: dict[str, dict[str, Any]] = METHOD["qa"]["adjacency_policies"]

VARIANTS: tuple[Variant, ...] = tuple(
    Variant(
        id=v["id"],
        role=v["role"],
        label=v["label"],
        raw_min=int(v["raw_range"][0]),
        raw_max=int(v["raw_range"][1]),
        adjacency_policy=v["adjacency_policy"],
        adjacency_accept=(
            tuple(ADJACENCY_POLICIES[v["adjacency_policy"]]["accept"])
            if ADJACENCY_POLICIES[v["adjacency_policy"]]["accept"] is not None
            else None
        ),
        text=v["text"],
    )
    for v in METHOD["variants"]
)
VARIANTS_BY_ID: dict[str, Variant] = {v.id: v for v in VARIANTS}
PRIMARY: Variant = next(v for v in VARIANTS if v.role == "primary")
SENSITIVITY_VARIANTS: tuple[Variant, ...] = tuple(v for v in VARIANTS if v.role == "sensitivity")

# Backwards-compatible names for the primary variant.
PHYSICAL_MIN = PRIMARY.aod_min
PHYSICAL_MAX = PRIMARY.aod_max

ADJACENCY_VALUES = {
    0: "normal condition / clear",
    1: "adjacent to clouds",
    2: "surrounded by more than 8 cloudy pixels",
    3: "adjacent to a single cloudy pixel",
    4: "adjacent to snow",
    5: "snow was previously detected in this pixel",
}


# -- pure-Python reference logic (mirrored by maiac_ee.py and the parity script) -------


def decode_aod_qa(qa: int) -> dict[str, int]:
    """Decode a 16-bit AOD_QA value into every documented field."""
    if not 0 <= qa <= 0xFFFF:
        raise ValueError("AOD_QA must be a 16-bit unsigned integer")
    return {name: f.value(qa) for name, f in QA_FIELDS.items()}


def passes_core_qa(qa: int) -> bool:
    return all(QA_FIELDS[name].value(qa) in accepted for name, accepted in CORE_QA_ACCEPT.items())


def passes_documented_value_guard(qa: int) -> bool:
    return all(QA_FIELDS[name].value(qa) in QA_FIELDS[name].documented_values for name in GUARD_FIELDS)


def passes_adjacency(qa: int, variant: Variant) -> bool:
    return variant.adjacency_accept is None or QA_FIELDS["adjacency"].value(qa) in variant.adjacency_accept


def raw_present(raw_aod: int | None) -> bool:
    """Raw AOD present before QA: unmasked and inside the product valid range."""
    return raw_aod is not None and RAW_VALID_MIN <= raw_aod <= RAW_VALID_MAX


def scale_raw_aod(raw: int) -> float:
    return raw * SCALE_FACTOR + OFFSET


def is_valid_retrieval(raw_aod: int | None, qa: int | None, variant: Variant = PRIMARY) -> bool:
    """A pixel retrieval counts for ``variant`` only if every rule passes. Range tests use raw integers."""
    if raw_aod is None or qa is None:
        return False
    return (
        variant.raw_min <= raw_aod <= variant.raw_max
        and passes_core_qa(qa)
        and passes_documented_value_guard(qa)
        and passes_adjacency(qa, variant)
    )


def is_guard_rejection(raw_aod: int | None, qa: int | None) -> bool:
    """Present, core-QA-passing retrieval rejected only by the documented-value guard."""
    if not raw_present(raw_aod) or qa is None:
        return False
    return passes_core_qa(qa) and not passes_documented_value_guard(qa)


def qa_rule_text(variant: Variant = PRIMARY) -> str:
    return (
        f"{CORE_QA_TEXT}; documented-value guard on adjacency, glint, aerosol-model and reserved fields; "
        f"{ADJACENCY_POLICIES[variant.adjacency_policy]['text']} "
        f"Raw Optical_Depth_055 in [{variant.raw_min}, {variant.raw_max}] "
        f"(AOD {variant.aod_min:.3f}..{variant.aod_max:.3f}) after which AOD = raw x {SCALE_FACTOR:g}; no clamping."
    )


QA_RULE_TEXT = qa_rule_text(PRIMARY)

NOT_A_MEASUREMENT_OF = (
    "PM10",
    "PM2.5",
    "surface (ground-level) dust concentration",
    "dust emission rate",
    "dust attributable to the Tavan Tolgoi mine",
)

CAVEAT = (
    "Column AOD at 550 nm is an optical property of the whole atmospheric column. It is not "
    "ground-level PM10/PM2.5 and an AOD pattern is not, by itself, evidence of mine-generated "
    "dust. Small negative AOD retrievals are kept in the primary series. Cloud, snow and QA "
    "gaps are missing data, never zero."
)

# Visualisation (single source for EE tiles and the web legend).
# AOD: single-hue blue sequential ramp spanning the negative product range: values -0.1..1.0.
AOD_VIS = {
    "min": -0.1,
    "max": 1.0,
    "palette": [
        "cde2fb",
        "b7d3f6",
        "9ec5f4",
        "86b6ef",
        "6da7ec",
        "5598e7",
        "3987e5",
        "2a78d6",
        "256abf",
        "1c5cab",
        "184f95",
        "104281",
        "0d366b",
    ],
}
COUNT_VIS = {
    "min": 1,
    "max": 25,
    "palette": ["f3bca8", "ed997a", "e4744a", "d64c00", "b13e02", "8d2f00", "6f2401"],
}
NO_VALID_VIS = {"palette": ["8a8a86"]}


def method_summary() -> dict[str, Any]:
    """Method description for /api/methods and provenance."""
    return {
        "method_version": METHOD_VERSION,
        "qa_fields": [
            {"name": f.name, "bits": f.bits, "documented_values": list(f.documented_values)} for f in QA_FIELDS.values()
        ],
        "core_qa": CORE_QA_TEXT,
        "documented_value_guard": GUARD_TEXT,
        "adjacency_policies": {k: v["text"] for k, v in ADJACENCY_POLICIES.items()},
        "variants": [
            {
                "id": v.id,
                "role": v.role,
                "label": v.label,
                "raw_range": [v.raw_min, v.raw_max],
                "aod_range": [round(v.aod_min, 3), round(v.aod_max, 3)],
                "adjacency_policy": v.adjacency_policy,
                "quality_filter": qa_rule_text(v),
                "text": v.text,
            }
            for v in VARIANTS
        ],
        "spatial_rule": METHOD["spatial_rule"],
        "temporal_rule": TEMPORAL_AGGREGATION_TEXT,
        "statistic_definitions": STATISTIC_DEFINITIONS,
        "acceptance": METHOD["acceptance"],
    }
