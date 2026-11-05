"""Write every artifact derived from api/app/datasets/maiac_method.json.

    python -m scripts.generate_method_artifacts          # rewrite artifacts
    python -m scripts.generate_method_artifacts --check  # exit 1 if any artifact is stale (CI/tests)

Artifacts:
  * gee/maiac_parity_check.js      - GENERATED METHOD block (the Code Editor cannot read files)
  * gee/tests/qa_truth_cases.json  - shared per-pixel truth table computed by maiac_spec
  * docs/RESEARCH_PROTOCOL.md      - "Implemented MAIAC method" section
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from app.datasets import maiac_spec as spec  # noqa: E402

PARITY_JS = ROOT / "gee" / "maiac_parity_check.js"
TRUTH_CASES = ROOT / "gee" / "tests" / "qa_truth_cases.json"
PROTOCOL = ROOT / "docs" / "RESEARCH_PROTOCOL.md"

JS_BEGIN = "// BEGIN GENERATED METHOD - do not edit by hand\n"
JS_END = "// END GENERATED METHOD\n"
MD_BEGIN = "<!-- BEGIN GENERATED: maiac-method (python -m scripts.generate_method_artifacts) -->\n"
MD_END = "<!-- END GENERATED: maiac-method -->\n"

RAW_CASES = [None, -101, -100, -1, 0, 1, 7999, 8000, 8001]


def qa_cases() -> list[int | None]:
    """Every value of every field with the others at a passing base, plus seeded random values."""
    base = 0b001  # cloud clear; everything else 0
    values: list[int | None] = [None, base]
    for f in spec.QA_FIELDS.values():
        for v in range(1 << f.n_bits):
            values.append((base & ~(f.mask << f.start_bit)) | (v << f.start_bit))
    rng = random.Random(20261104)  # noqa: S311 - deterministic test-case sampling, not security
    values += [rng.randrange(0, 1 << 16) for _ in range(150)]
    seen: set[int | None] = set()
    unique = []
    for v in values:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique


def truth_cases() -> dict[str, object]:
    columns = [v.id for v in spec.VARIANTS] + ["guard_rejected", "raw_present"]
    cases = []
    for qa in qa_cases():
        for raw in RAW_CASES:
            expected = [int(spec.is_valid_retrieval(raw, qa, v)) for v in spec.VARIANTS]
            expected += [int(spec.is_guard_rejection(raw, qa)), int(spec.raw_present(raw))]
            cases.append([raw, qa, expected])
    return {
        "method_version": spec.METHOD_VERSION,
        "generated_by": "api/scripts/generate_method_artifacts.py from api/app/datasets/maiac_method.json",
        "columns": columns,
        "cases": cases,
    }


def js_block() -> str:
    return f"{JS_BEGIN}var METHOD = {json.dumps(spec.METHOD, indent=2)};\n{JS_END}"


def protocol_block() -> str:
    m = spec.METHOD
    lines = [
        MD_BEGIN,
        f"#### Implemented MAIAC method `{spec.METHOD_VERSION}`\n",
        "\n",
        "This section is generated from `api/app/datasets/maiac_method.json`, the single source used by the "
        "backend, the parity script, the API schema, the CSV header and the UI.\n",
        "\n",
        f"- Scaling: `{spec.AOD_BAND}` raw integer x {spec.SCALE_FACTOR:g} (offset {spec.OFFSET:g}); "
        "range tests are applied to the raw integers; **no clamping**.\n",
        f"- Core QA (`core_qa`): {spec.CORE_QA_TEXT}.\n",
        f"- Documented-value guard: {spec.GUARD_TEXT}\n",
        "- Variants (computed in the same pass; sensitivity variants never replace the primary result):\n",
    ]
    for v in spec.VARIANTS:
        lines.append(f"  - `{v.id}` ({v.role}): {v.text}\n")
    lines += [
        f"- Spatial rule: {m['spatial_rule']['text']}\n",
        f"- Temporal rule: {m['temporal_rule']['text']}\n",
        "- Statistic definitions:\n",
    ]
    for key, text in spec.STATISTIC_DEFINITIONS.items():
        lines.append(f"  - `{key}`: {text}\n")
    acc = m["acceptance"]
    lines += [
        f"- Acceptance parity (opt-in, live Earth Engine): month {acc['test_month']}; integer fields exact; "
        f"means within an absolute tolerance of {acc['mean_abs_tolerance']:g}. {acc['note']}\n",
        MD_END,
    ]
    return "".join(lines)


def replace_block(text: str, begin: str, end: str, block: str, path: Path) -> str:
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(text):
        raise SystemExit(f"Markers not found in {path}")
    return pattern.sub(lambda _: block, text, count=1)


def build() -> dict[Path, str]:
    js = replace_block(PARITY_JS.read_text(encoding="utf-8"), JS_BEGIN, JS_END, js_block(), PARITY_JS)
    proto = replace_block(PROTOCOL.read_text(encoding="utf-8"), MD_BEGIN, MD_END, protocol_block(), PROTOCOL)
    cases = json.dumps(truth_cases(), separators=(",", ":")) + "\n"
    return {PARITY_JS: js, PROTOCOL: proto, TRUTH_CASES: cases}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if artifacts are stale")
    args = parser.parse_args()
    stale = []
    for path, content in build().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != content:
            stale.append(path)
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
    if args.check and stale:
        print("Stale generated artifacts:", *[str(p.relative_to(ROOT)) for p in stale], sep="\n  ")
        raise SystemExit(1)
    print("up to date" if not stale else "regenerated: " + ", ".join(str(p.relative_to(ROOT)) for p in stale))


if __name__ == "__main__":
    main()
