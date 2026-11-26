// Conflict, economy and hotspots: every figure and number those pages compute in the browser equals Python's for the
// same inputs (fixtures: staticbuild/group9.py fixtures(); inputs: web/data, built from the same snapshot).
import { test } from "node:test";
import assert from "node:assert/strict";
import * as charts from "../js/lib/charts.js";
import { asRows, setConfig } from "../js/lib/scoring.js";
import * as g9 from "../js/charts/group9.js";
import { data, fixture, same } from "./helpers.mjs";

const config = data("config");
charts.setConfig(config);
setConfig(config);
const master = data("master");
const year = data("meta").year;
const names = Object.fromEntries(asRows(data("countries")).map((r) => [r.iso3, r.name]));
const regionOf = Object.fromEntries(asRows(master).map((r) => [r.iso3, r.region]));
const pick = (rows, keys) => rows.map((r) => Object.fromEntries(keys.map((k) => [k, r[k] ?? null])));

test("economy: headline counts, warning notes, warnings table and the three charts for a region", () => {
  const economy = data("group9/economy");
  for (const c of fixture("group9_economy").cases) {
    const view = g9.econView(master, data("values"), c.region);
    assert.deepEqual(g9.econKpis(view), c.kpis, `${c.region} kpis`);
    const flags = g9.econFlags(view, data("values"), config);
    same(g9.econNotes(flags), c.notes, `${c.region} notes`);
    same(pick(g9.warningRows(view, flags, config), ["iso3", "name", "count", "economic", "warnings"]), c.warnings, `${c.region} warnings`);
    same(g9.econHeatmap(g9.heatRows(view, c.n)), c.heatmap, `${c.region} heatmap`, 1e-6);
    same(g9.stagflationScatter(view), c.scatter, `${c.region} scatter`, 1e-6);
    const series = g9.inView(economy.series[c.key], view);
    same(g9.imfOutlook(series, year, c.label, year - 12, year + 5), c.outlook, `${c.region} outlook`, 1e-6);
    assert.equal(g9.outlookLast(series, year), c.last);
  }
});

test("economy: an unscored country never reaches the heatmap and has no count or NaN anywhere", () => {
  const view = g9.econView(master, data("values"), "All regions");
  const unscored = view.find((r) => r.economic === null);
  assert.ok(unscored, "the data has a country without an economy score");
  assert.ok(!g9.heatRows(view, 250).some((r) => r.iso3 === unscored.iso3));
  const counts = g9.econKpis([{ iso3: "X", inflation: null, gdp_growth: null, gov_debt: null, fiscal_balance: null, reserves_months: null }]);
  assert.deepEqual(counts, [0, 0, 0, 0, 0]);
  assert.ok(!JSON.stringify(g9.stagflationScatter(view)).includes("NaN"));
});

test("hotspots: the constants match prm/hotspots.py", () => {
  same(g9.HOTSPOTS, fixture("group9_hotspots").constants);
});

test("hotspots: the board for the default and custom weights, and with stale news (no signal)", () => {
  const { boards } = fixture("group9_hotspots");
  const [monthly, cells, signal] = ["monthly", "cells", "signal"].map((n) => data(`hotspots/${n}`));
  for (const b of boards) {
    const table = b.weights === "default" ? master : fixture(`master_${b.weights}`);
    same(g9.board(table, monthly, cells, b.stale ? null : signal), b.board, `${b.weights} stale=${b.stale}`);
  }
});

test("hotspots: the news is stale three days after the GDELT file ends", () => {
  assert.equal(g9.newsStale({ gdelt_through: "2026-11-21" }, "2026-11-24"), false);
  assert.equal(g9.newsStale({ gdelt_through: "2026-11-20" }, "2026-11-24"), true);
  assert.equal(g9.newsStale({}, "2026-11-24"), false);
});

test("hotspots: the event map and the monthly bars, for all regions and one region", () => {
  const { maps, bars } = fixture("group9_hotspots");
  const [monthly, cells] = ["monthly", "cells"].map((n) => data(`hotspots/${n}`));
  for (const m of maps) {
    const shown = g9.mapCells(cells, regionOf, m.region);
    same(g9.hotspotMap(shown, names, g9.HOTSPOTS.VIOLENCE, m.region !== "All regions"), m.figure, m.region, 1e-6);
  }
  for (const b of bars) same(g9.monthlyBars(monthly, regionOf, b.region), b.figure, b.region, 1e-6);
  assert.equal(g9.monthlyBars([], regionOf, "All regions"), null);
});

test("hotspots calendar: windows, the timeline and the next event per country for a given day", () => {
  const c = fixture("group9_calendar");
  const cal = g9.calendar(data("events"), names, c.today);
  assert.deepEqual(Object.keys(cal.windows), Object.keys(c.windows));
  for (const [label, rows] of Object.entries(c.windows)) {
    same(cal.windows[label].map((r) => ({ ...r, date: g9.dmy(r.date) })), rows, label);
    if (rows.length) same(g9.eventsTimeline(cal.windows[label], c.today), c.timeline[label], `${label} timeline`, 1e-6);
  }
  same(Object.fromEntries(cal.next.map((e) => [e.iso3, e.days])), c.custom, "days");
  same(Object.fromEntries(cal.next.map((e) => [e.iso3, e.note])), c.notes, "notes");
  same(g9.reversedScale(charts.mapColorscale("social")), c.colorscale, "globe colours");
});

test("conflict outlook: the top 20 table and the numbers under it", () => {
  const c = fixture("group9_outlook");
  const { rows, chanceMax } = g9.outlookRows(data("outlook"), master);
  same(pick(rows, ["iso3", "name", "chance", "relative", "recent", "tier"]), c.rows);
  same(chanceMax, c.chance_max);
  assert.deepEqual(g9.outlookTexts(data("outlook")), c.texts);
});

test("dates as the app writes them", () => {
  assert.equal(g9.day("2026-10-04"), "4 Oct 2026");
  assert.equal(g9.dmy("2026-10-04"), "04 Oct 2026");
  assert.equal(g9.addDays("2026-12-30", 3), "2027-01-02");
});
