// globe.js: buildGlobeData reproduces the data dict prm/globe.py::risk_globe hands its component (staticbuild/charts.py).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { setConfig } from "../js/lib/charts.js";
import { buildGlobeData } from "../js/lib/globe.js";
import { data, fixture, same } from "./helpers.mjs";

setConfig(data("config"));
const table = data("master");
const hist = data("history");
const flows = fixture("globe_flows");

const read = (p) => readFileSync(new URL(p, import.meta.url), "utf8");

test("the outlines keep only what globe.js reads, coordinates at 4 dp (scripts/trim_geojson.py)", () => {
  for (const file of ["ne_110m", "ne_50m"]) {
    const { features } = JSON.parse(read(`../vendor/geo/${file}.geojson`));
    assert.ok(features.length > 170, file);
    for (const f of features) {
      assert.deepEqual(Object.keys(f.properties).sort(), ["ADM0_A3", "ADMIN", "ISO_A3"], `${file} ${f.properties.ADMIN}`);
      assert.match(f.properties.ADM0_A3, /^[A-Z0-9]{3}$/, `${file} ${f.properties.ADMIN}`);
    }
    const coords = JSON.stringify(features.map((f) => f.geometry.coordinates)).match(/-?\d+\.\d+/g);
    assert.ok(coords.every((c) => c.split(".")[1].length <= 4), `${file}: more than 4 decimals`);
  }
});

test("globe buttons are 44 px on touch screens", () => {
  const css = read("../css/globe.css");
  const coarse = css.slice(css.indexOf("@media (pointer: coarse) {"));
  assert.ok(coarse.length > 0 && coarse.indexOf("}") > 0, "a (pointer: coarse) block");
  const block = coarse.slice(0, coarse.indexOf("\n}"));
  assert.match(block, /\.rg-group button, \.rg-play \{ min-width: 44px; height: 44px; \}/);
  assert.match(block, /\.rg-close \{ min-width: 44px; min-height: 44px;/);
});

for (const name of ["overview", "changes", "focus"]) {
  test(`buildGlobeData: ${name}`, () => {
    const { inputs, data: expected } = fixture(`globe_${name}`);
    const got = buildGlobeData(table, hist, inputs.flows ? flows : null, inputs.metric, inputs.metricLabel, inputs.options);
    same(got, expected, name);
  });
}
