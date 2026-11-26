// Compare, Score changes, Regions, Indicator explorer: what the pages compute from a visitor's choices equals the Python
// pages (app_pages/*.py) for fixed choices, with the default weights and ?w=50,20,20,10. Fixtures: staticbuild/group8.py.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as charts from "../js/lib/charts.js";
import { asMap, asRows, setConfig } from "../js/lib/scoring.js";
import * as g8 from "../js/charts/group8.js";
import { data, fixture, same } from "./helpers.mjs";

const config = data("config");
setConfig(config);
charts.setConfig(config);
const values = data("values");
const year = data("meta").year;
const RUNS = {
  default: { scores: asMap(data("scores")), hist: data("history"), table: data("master") },
  w50_20_20_10: { scores: asMap(fixture("scores_w50_20_20_10")), hist: fixture("history_w50_20_20_10"), table: fixture("master_w50_20_20_10") },
};
const pick = (rows, cols) => rows.map((r) => Object.fromEntries(cols.map((c) => [c, r[c] ?? null])));
const seriesFile = (iso3) => JSON.parse(readFileSync(new URL(`../data/group8/series/${iso3}.json`, import.meta.url), "utf8"));
const options = asRows(data("countries")).map((r) => r.iso3);

test("compare: ?c= is read as the Python page reads it", () => {
  for (const { c, picked } of fixture("group8_compare").parse) assert.deepEqual(g8.parsePicks(c, options, config.MAX_COMPARE), picked, c);
});

test("compare: a shared link first, then the saved list, then the current country with KEN, ZAF, ETH", () => {
  const seed = (c, saved, current) => g8.seedPicks({ c, saved, current }, options, config.MAX_COMPARE);
  assert.deepEqual(seed("SYR,NOR", ["USA"], "VNM"), ["SYR", "NOR"]);
  assert.deepEqual(seed("XXX,YYY", ["USA", "usa", "XXX", "USA"], "VNM"), ["USA"]);
  assert.deepEqual(seed(null, [], "VNM"), ["VNM", "KEN", "ZAF"]);
  assert.deepEqual(seed("", null, "KEN"), ["KEN", "ZAF", "ETH"]);
  assert.deepEqual(seed(null, [], "XXX"), ["KEN", "ZAF", "ETH"]);
});

test("compare: similar countries, score cards, indicator table and every figure", () => {
  const names = Object.fromEntries(asRows(data("countries")).map((r) => [r.iso3, r.name]));
  for (const c of fixture("group8_compare").cases) {
    const { scores, hist, table } = RUNS[c.weights];
    const at = `${c.weights} ${c.picked}`;
    const rows = asMap(table);
    assert.deepEqual(g8.similarTo(scores, c.picked, config.MAX_COMPARE), c.similar, at);
    same(c.picked.map((i) => g8.scorecard(rows.get(i), year)), c.cards, `${at} cards`);
    same(g8.indicatorRows(values, rows, c.picked, names, config), c.indicators, `${at} indicators`);
    same(charts.radar(new Map(c.picked.map((i) => [i, rows.get(i)])), names), c.radar, `${at} radar`, 1e-6);
    const files = Object.fromEntries(c.picked.map((i) => [i, seriesFile(i)]));
    const series = { ...g8.seriesFrom(files), ...g8.compositeSeries(hist) };
    const lines = {
      composite: charts.compareLines(series, "composite", c.picked, names, "Composite risk score (0–100)"),
      wgi_pv: charts.compareLines(series, "wgi_pv", c.picked, names, "WGI score (0–100, higher = better)"),
      wgi_cc: charts.compareLines(series, "wgi_cc", c.picked, names, "WGI score (0–100, higher = better)"),
      gdp_growth: charts.compareLines(series, "gdp_growth", c.picked, names, "Real GDP growth (%)", year - 12, year + 5, year),
      gov_debt: charts.compareLines(series, "gov_debt", c.picked, names, "Public debt (% of GDP)", year - 12, year + 5, year),
    };
    for (const k of Object.keys(c.lines)) same(lines[k], c.lines[k], `${at} ${k}`, 1e-6);
  }
});

test("changes: headline numbers, bars, globe values and notes, tier, driver and red-flag tables", () => {
  const flagTable = JSON.parse(readFileSync(new URL("../data/group8/flag_changes.json", import.meta.url), "utf8"));
  for (const c of fixture("group8_changes").cases) {
    const { hist, table } = RUNS[c.weights];
    const at = `${c.weights} ${c.region}`;
    const { view, moved } = g8.changesView(table, hist, c.region, year, config);
    const flags = g8.changesFlags(flagTable, view, config);
    assert.deepEqual(g8.changesKpis(moved, flags), c.kpis, at);
    if (c.bars) same(charts.changeBars(moved.map((r) => ({ ...r, thin: g8.thin(r, config) }))), c.bars, `${at} bars`, 1e-6);
    else assert.equal(moved.length, 0, at);
    assert.equal(g8.thinNote(moved, config), c.thin, `${at} thin`);
    same(g8.changeNotes(moved), c.notes, `${at} notes`);
    same(Object.fromEntries(moved.map((r) => [r.iso3, r.delta_1y])), c.custom, `${at} custom`);
    same(pick(g8.tierRows(moved), ["iso3", "name", "trend", "move", "driver"]), c.tiers, `${at} tiers`);
    same(pick(g8.driverRows(moved, config), ["iso3", "name", "trend", ...config.pillars.map((p) => `d_${p.key}`)]), c.drivers, `${at} drivers`);
    same(pick(flags, ["iso3", "name", "change", "severity", "flag_label"]), c.flags, `${at} flags`);
  }
});

test("regions: the region from ?region=, headline numbers, tier mix, ranking order and events", () => {
  const events = asRows(data("events"));
  for (const c of fixture("group8_regions").cases) {
    const { hist, table } = RUNS[c.weights];
    const at = `${c.weights} ${c.asked}`;
    const region = g8.pickRegion(c.asked, g8.regionList(table));
    assert.equal(region, c.region, at);
    const s = g8.regionSummary(table, hist, values, region, year);
    assert.equal(s.subtitle, c.subtitle, at);
    assert.equal(s.kpis.length, c.kpis.length, at);
    c.kpis.forEach((k, i) => same(Object.fromEntries(Object.keys(k).map((f) => [f, s.kpis[i][f] ?? null])), k, `${at} kpi ${i}`));
    same(charts.tierMix(s.rh), c.tier_mix, `${at} tier mix`, 1e-6);
    assert.deepEqual(g8.byRank(s.rv).map((r) => r.iso3), c.ranking, `${at} ranking`);
    assert.equal(s.height, c.height, at);
    same(pick(g8.regionEvents(events, s.rv), ["date", "iso3", "country", "event", "significance", "source_url"]), c.events, `${at} events`);
  }
});

test("explorer: counts, median, leader lists, globe values and notes, distribution", () => {
  const { scores, table } = RUNS.default;
  for (const c of fixture("group8_explorer").cases) {
    const at = `${c.key} ${c.region}`;
    const ind = config.indicators.find((i) => i.key === c.key);
    const { view, known } = g8.explorerFrame(table, values, scores, c.key, c.region, year);
    assert.equal(known.length, c.count, at);
    assert.equal(g8.medianText(known, ind), c.median, at);
    same(g8.leaderLists(known, ind).map((l) => ({ part: l.part, title: l.title, rows: pick(l.rows, ["iso3", "name", "shown", "risk", "year"]) })), c.lists, `${at} lists`);
    same(g8.explorerNotes(known, ind), c.notes, `${at} notes`);
    same(g8.explorerCustom(table, scores, c.key), c.custom, `${at} custom`);
    assert.deepEqual(view.map((r) => r.iso3), c.inView, at);
    same(charts.distribution(known.map((r) => r.value), `${ind.short} (${ind.unit})`, config.PILLAR_COLORS[ind.pillar], ind.norm === "log"),
      c.distribution, `${at} distribution`, 1e-6);
  }
});

test("indicator labels and values are formatted as the Python Indicator", () => {
  assert.deepEqual(g8.indicatorOptions(config)[0], { key: "wgi_pv", label: "Stability · Political stability & absence of violence" });
  const ind = { decimals: 2 };
  assert.equal(g8.fmtInd(ind, 1234.5678), "1,234.57");
  assert.equal(g8.fmtInd(ind, null), "—");
  assert.equal(g8.fmtInd(ind, NaN), "—");
  assert.equal(g8.floatText(0.7), "0.7");
  assert.equal(g8.floatText(2), "2.0");
  assert.equal(g8.floatText(0), "0.0");
  assert.equal(g8.floatText(-1.6), "-1.6");
});
