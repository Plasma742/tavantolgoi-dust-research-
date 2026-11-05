// Runs gee/maiac_parity_check.js (the Code Editor acceptance script) in Node with a scalar fake
// of the Earth Engine API and checks it against the shared truth table generated from the
// Python method spec. Behavioural test, not a string-token check.  Run: node --test gee/tests
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(here, "..", "maiac_parity_check.js"), "utf8");
const truth = JSON.parse(readFileSync(join(here, "qa_truth_cases.json"), "utf8"));

class Pix {
  constructor(value, masked = false) { this.value = value; this.masked = masked || value === null; }
  bin(o, fn) {
    const other = o instanceof Pix ? o : new Pix(o);
    return this.masked || other.masked ? new Pix(0, true) : new Pix(fn(this.value, other.value));
  }
  rightShift(n) { return this.bin(n, (a, b) => a >> b); }
  bitwiseAnd(m) { return this.bin(m, (a, b) => a & b); }
  eq(v) { return this.bin(v, (a, b) => Number(a === b)); }
  gte(v) { return this.bin(v, (a, b) => Number(a >= b)); }
  lte(v) { return this.bin(v, (a, b) => Number(a <= b)); }
  and(o) { return this.bin(o, (a, b) => Number(Boolean(a) && Boolean(b))); }
  or(o) { return this.bin(o, (a, b) => Number(Boolean(a) || Boolean(b))); }
  not() { return this.masked ? new Pix(0, true) : new Pix(Number(!this.value)); }
  multiply(v) { return this.bin(v, (a, b) => a * b); }
  add(v) { return this.bin(v, (a, b) => a + b); }
  updateMask(m) { return new Pix(this.value, !(!this.masked && !m.masked && Boolean(m.value))); }
  selfMask() { return new Pix(this.value, this.masked || !this.value); }
  rename() { return this; }
}

function loadScript() {
  const Image = (x) => x;
  Image.constant = (v) => new Pix(v);
  const context = { PARITY_TEST_HARNESS: true, ee: { Image }, print: () => {}, Map: {} };
  vm.createContext(context);
  vm.runInContext(`${source}\nthis.api = { pixelMasks, toEngineOutput, variantStatus, METHOD, primaryId };`, context);
  return context.api;
}

test("generated METHOD block matches the truth-table method version", () => {
  const api = loadScript();
  assert.equal(api.METHOD.method_version, truth.method_version);
  assert.equal(api.primaryId(), "product_range");
});

test("pixelMasks reproduces the shared truth table for every case", () => {
  const api = loadScript();
  for (const [raw, qa, expected] of truth.cases) {
    const masks = api.pixelMasks({ select: (b) => new Pix(b === "AOD_QA" ? qa : raw) });
    const got = truth.columns.map((c) => Number(!masks[c].masked));
    assert.deepEqual(got, expected, `raw=${raw} qa=${qa}`);
  }
});

test("negative AOD is scaled, not clamped", () => {
  const api = loadScript();
  const masks = api.pixelMasks({ select: (b) => new Pix(b === "AOD_QA" ? 1 : -100) });
  assert.equal(masks.product_range.masked, false);
  assert.ok(Math.abs(masks.product_range.value - -0.1) < 1e-12);
  assert.equal(masks.nonnegative_sensitivity.masked, true);
});

test("empty collection yields NO_GRANULES and null means", () => {
  const api = loadScript();
  const ids = api.METHOD.variants.map((v) => v.id);
  const perVariant = Object.fromEntries(ids.map((i) => [i, { granule_sum: 0, granules_with_valid: 0, valid_day_count: 0 }]));
  const engine = api.toEngineOutput({ granules_intersecting: 0, pixel_sums: { roi_px: 9 }, means: {}, per_variant: perVariant }, ids);
  assert.equal(api.variantStatus(engine, "product_range"), "NO_GRANULES");
  assert.equal(engine.variants.product_range.roi_mean_aod, null);
  assert.equal(engine.pixels_total, 9);
});

test("ROI without a pixel centre yields NO_VALID_OBSERVATIONS", () => {
  const api = loadScript();
  const ids = api.METHOD.variants.map((v) => v.id);
  const perVariant = Object.fromEntries(ids.map((i) => [i, { granule_sum: 0, granules_with_valid: 0, valid_day_count: 0 }]));
  const engine = api.toEngineOutput({ granules_intersecting: 5, pixel_sums: { roi_px: 0 }, means: {}, per_variant: perVariant }, ids);
  assert.equal(api.variantStatus(engine, "product_range"), "NO_VALID_OBSERVATIONS");
});
