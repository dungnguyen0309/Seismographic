// The overview page's numbers (web/js/charts/overview.js) against app_pages/overview.py for fixed inputs: the region
// and income filter, the headline numbers, the hotspots, the ranking CSV and the filtered stability movers.
// Fixtures: staticbuild/overview.py fixtures(); tables: data/master.json + history.json (default weights) and the
// w50_20_20_10 fixtures (custom weights).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as ov from "../js/charts/overview.js";
import * as charts from "../js/lib/charts.js";
import { setConfig } from "../js/lib/scoring.js";
import { data, fixture, objects, same } from "./helpers.mjs";

const config = data("config");
setConfig(config);
charts.setConfig(config);
const year = data("meta").year;
const values = new Map(objects(data("values")).map((r) => [r.iso3, r]));
const TABLES = {
  default: { table: objects(data("master")), hist: objects(data("history")) },
  w50_20_20_10: { table: objects(fixture("master_w50_20_20_10")), hist: objects(fixture("history_w50_20_20_10")) },
};
const viewOf = (c) => ov.filterView(TABLES[c.weights ?? "default"].table, c.region, c.incomes);

test("the filter keeps the rows app_pages/overview.py keeps", () => {
  for (const c of fixture("overview_headline").cases) {
    assert.deepEqual(viewOf(c).map((r) => r.iso3), c.view, `${c.weights} ${c.region} ${c.incomes}`);
  }
});

test("headline numbers", () => {
  for (const c of fixture("overview_headline").cases) {
    const got = ov.headline(viewOf(c), TABLES[c.weights].hist, values, year);
    same(got, c.expected, `${c.weights} ${c.region} ${c.incomes}`);
  }
});

test("highest risk in a region: the 12 lowest ranks", () => {
  for (const c of fixture("overview_headline").cases) {
    assert.deepEqual(ov.topRisk(viewOf(c)).map((r) => r.iso3), c.top, `${c.weights} ${c.region}`);
  }
});

test("hotspots: reasons, order and the top six", () => {
  const { today, cases } = fixture("overview_hotspots");
  const opts = { newFlags: data("overview/new_flags"), events: objects(data("events")), today, year };
  for (const c of cases) same(ov.hotspotRows(viewOf(c), opts), c.expected, `${c.weights} ${c.region} ${c.incomes}`);
});

test("ranking order and CSV", () => {
  for (const c of fixture("overview_ranking_csv").cases) {
    const rows = ov.rankingRows(viewOf(c));
    assert.deepEqual(rows.map((r) => r.iso3), c.order);
    assert.equal(ov.rankingCsv(rows), c.expected, `${c.weights} ${c.region}`);
  }
});

test("political stability movers for the filtered view", () => {
  const changes = objects(data("overview/wgi_changes"));
  const table = TABLES.default.table;
  for (const c of fixture("overview_movers").cases) {
    const rows = ov.wgiMovers(changes, table, ov.filterView(table, c.region, c.incomes), ov.filtered(c.region, c.incomes));
    same(charts.movers(rows), c.figure, `${c.region} ${c.incomes}`, 1e-6);
  }
});

test("an unscored country gives no NaN and no hotspot", () => {
  const unscored = TABLES.default.table.filter((r) => r.composite === null).slice(0, 3);
  assert.ok(unscored.length);
  const got = ov.headline(unscored, TABLES.default.hist, values, year);
  assert.equal(got.scored, 0);
  assert.equal(got.median, "—");
  for (const [k, v] of Object.entries(got)) assert.ok(!Number.isNaN(v) && v !== undefined, `${k}: ${v}`);
  assert.deepEqual(ov.hotspotRows(unscored, { newFlags: {}, events: [], today: "2026-01-01", year }), []);
  assert.ok(!ov.rankingCsv(ov.rankingRows(unscored)).includes("NaN"));
});

test("pyFloat writes floats as pandas' to_csv does", () => {
  assert.equal(ov.pyFloat(97), "97.0");
  assert.equal(ov.pyFloat(0.3), "0.3");
  assert.equal(ov.pyFloat(-2), "-2.0");
  assert.equal(ov.pyFloat(3.2e-5), "3.2e-05");
  assert.equal(ov.pyFloat(null), "");
});

test("overview.css only styles elements inside the page's own .ov- elements", () => {
  // ui.loadCss keeps the sheet for the rest of the visit: a rule on a bare shell class would restyle every later page
  const css = readFileSync(new URL("../css/overview.css", import.meta.url), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
  const top = (s, stop) => { // split at stop characters outside parentheses
    const out = [""];
    let depth = 0;
    for (const ch of s) {
      depth += ch === "(" ? 1 : ch === ")" ? -1 : 0;
      if (!depth && stop.test(ch)) out.push(""); else out[out.length - 1] += ch;
    }
    return out.map((p) => p.trim()).filter(Boolean);
  };
  const selectors = [...css.matchAll(/([^{}]+)\{/g)].map((m) => m[1].trim()).filter((s) => !s.startsWith("@"))
    .flatMap((s) => top(s, /,/));
  assert.ok(selectors.length > 20);
  const unscoped = selectors.filter((s) => !top(s, /[\s>+~]/)[0].includes(".ov-"));
  assert.deepEqual(unscoped, []);
});
