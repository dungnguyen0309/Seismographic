// Case studies, stress test, builder, data downloads: every number and text these pages compute in the browser equals
// Python's for fixed inputs. Fixtures: staticbuild/group10.py fixtures(ctx).
import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import * as S from "../js/lib/scoring.js";
import * as stress from "../js/group10/stress.js";
import * as cases from "../js/group10/cases.js";
import * as content from "../js/group10/content.js";
import * as ex from "../js/group10/export.js";
import { data, fixture, objects, same, sameTable } from "./helpers.mjs";

const config = data("config");
S.setConfig(config);
const values = data("values");
const custom = { stability: 50, governance: 20, economic: 20, social: 10 };
const sha1 = (s) => createHash("sha1").update(s, "utf8").digest("hex");

// ---- carried from Task 3: normaliseAgainst against Python ----------------------------------------------------------
test("normaliseAgainst equals scoring.normalise_against", () => {
  const { cases: list } = fixture("group10_normalise_against");
  assert.ok(list.length >= 8);
  list.forEach((c, i) => same(S.normaliseAgainst(c.values, c.reference, c.higher_is_riskier, c.method, config), c.out,
    `case ${i} (${c.name})`));
});

// ---- stress test ---------------------------------------------------------------------------------------------------
const st = data("group10/stress");
const fx = fixture("group10_stress");

test("stress decode: ?shock= read exactly as stress.decode (garbage gives nothing)", () => {
  for (const c of fx.decode) {
    const got = stress.decode(c.in, st.shocks);
    assert.deepEqual(Object.keys(got), Object.keys(c.out), `keys of ${JSON.stringify(c.in)}`);
    same(got, c.out, `decode(${JSON.stringify(c.in)})`);
  }
});

test("stress encode", () => {
  for (const c of fx.encode) assert.equal(stress.encode(c.in, st.shocks), c.out, JSON.stringify(c.in));
});

test("stress run, summary and the results CSV equal Python's", () => {
  const master = data("master");
  for (const [i, c] of fx.runs.entries()) {
    const weights = Object.fromEntries(c.weights);
    const rows = stress.run(values, weights, c.shocks, c.scope, st.shocks, config);
    const exp = objects(c.rows);
    assert.equal(rows.length, exp.length);
    rows.forEach((r, j) => {
      for (const col of c.rows.columns) same(r[col] ?? null, exp[j][col], `run ${i} ${exp[j].iso3}.${col}`);
    });
    same(stress.summary(rows, config), c.summary, `summary ${i}`, 1e-9);
    assert.equal(stress.resultsCsv(rows, master), c.csv, `csv ${i}`);
  }
});

test("stress run reuses precomputed scores for today", () => {
  const c = fx.runs[0];
  const before = S.asMap(data("scores"));
  const a = stress.run(values, Object.fromEntries(c.weights), c.shocks, c.scope, st.shocks, config);
  const b = stress.run(values, Object.fromEntries(c.weights), c.shocks, c.scope, st.shocks, config, { before });
  same(b, a);
});

// ---- case studies ----------------------------------------------------------------------------------------------------
test("case readings equal cases.reading, default and custom weights", () => {
  const file = data("group10/cases");
  const want = fixture("group10_cases");
  for (const [name, hist] of [["default", data("history")], ["w50_20_20_10", fixture("history_w50_20_20_10")]]) {
    for (const c of file.cases) same(cases.reading(c, hist, config), want[name][c.key], `${name} ${c.key}`);
  }
});

test("a case without a score the year before has no verdict", () => {
  const c = { ...data("group10/cases").cases[0], iso3: "ASM" };
  assert.deepEqual(cases.reading(c, data("history"), config), { before: 2019, verdict: null });
});

// ---- builder ---------------------------------------------------------------------------------------------------------
const bf = fixture("group10_builder");

test("build_assessment_markdown", () => {
  for (const [i, c] of bf.markdown.entries()) assert.equal(content.buildAssessmentMarkdown(c.in), c.out, `case ${i}`);
});

test("csv_row", () => {
  for (const c of bf.csv_row) assert.equal(content.csvRow(c.in), c.out, JSON.stringify(c.in));
});

test("parse_front_matter", () => {
  for (const c of bf.front_matter) assert.deepEqual(content.parseFrontMatter(c.in), [c.meta, c.body], JSON.stringify(c.in));
});

test("estimative_term", () => {
  for (const c of bf.estimative) assert.equal(content.estimativeTerm(c.p, config), c.term, String(c.p));
});

test("the driver boxes' figures equal the builder's _facts", () => {
  assert.deepEqual(content.DRIVER_FACTS, bf.driver_facts);
  const scores = S.asMap(data("scores"));
  for (const [iso3, boxes] of Object.entries(bf.facts)) {
    for (const [box, text] of Object.entries(boxes)) {
      assert.equal(content.facts(iso3, content.DRIVER_FACTS[box], values, scores, config), text, `${iso3} ${box}`);
    }
  }
});

test("Latest data lines with the exported next-year growth equal country_brief", () => {
  const nextGrowth = data("group10/builder").next_growth;
  const scores = S.asMap(data("scores"));
  const trend = data("wgi_trend");
  for (const [iso3, lines] of Object.entries(bf.brief)) {
    const name = S.asMap(data("countries")).get(iso3).name;
    assert.deepEqual(S.countryBrief(iso3, name, values, scores, data("countries"), data("meta").year,
      { wgiTrend: trend[iso3] ?? null, nextGrowth: nextGrowth[iso3] ?? null, config }), lines, iso3);
  }
});

test("builder constants come from prm.content", () => {
  assert.deepEqual(content.OUTLOOKS, bf.outlooks);
  assert.deepEqual(content.CONFIDENCE, bf.confidence);
});

// ---- data downloads --------------------------------------------------------------------------------------------------
const ef = fixture("group10_export");
const tables = data("group10/tables");

test("floats are written as Python's repr", () => {
  for (const c of ef.repr) assert.equal(ex.pyRepr(c.in), c.out, String(c.in));
});

test("floats in the JSON are rounded as pandas' to_json(double_precision=4)", () => {
  for (const c of ef.ujson) assert.equal(ex.ujson(c.in), c.out, String(c.in));
});

const defaultTables = () => ({
  index: ex.indexTable(data("master"), tables.dtypes.index),
  indicators: tables.indicators,
  red_flags: tables.red_flags,
  history: ex.historyTable(data("history"), data("countries"), tables.bd_last_year, tables.dtypes.history),
  conflict_outlook: tables.conflict_outlook,
  dictionary: tables.dictionary,
});

test("each CSV equals pandas' to_csv with the default weights", () => {
  const all = defaultTables();
  for (const [name, hash] of Object.entries(ef.csv_sha1)) {
    const t = { ...all[name], dtypes: tables.dtypes[name] };
    assert.equal(sha1(ex.toCsv(t)), hash, name);
  }
});

test("the JSON download equals export.to_json with the default weights", () => {
  const all = Object.fromEntries(Object.entries(defaultTables()).map(([k, t]) => [k, { ...t, dtypes: tables.dtypes[k] }]));
  const meta = data("meta");
  const shares = Object.fromEntries(config.pillars.map((p) => [p.key, p.default_weight]));
  const text = ex.toJson(all, ex.exportMeta(tables.meta, shares, ef.json.generated));
  assert.equal(text.length, ef.json.length);
  assert.equal(sha1(text), ef.json.sha1);
  assert.equal(tables.meta.index_year, meta.year);
});

test("custom weights: the index and history tables follow them", () => {
  const index = ex.indexTable(fixture("master_w50_20_20_10"), tables.dtypes.index);
  sameTable(index, ef.custom.index);
  assert.deepEqual(index.rows.map((r) => r[0]), ef.custom.index.rows.map((r) => r[0]), "row order (by rank)");
  const hist = ex.historyTable(fixture("history_w50_20_20_10"), data("countries"), tables.bd_last_year, tables.dtypes.history);
  assert.equal(hist.rows.length, ef.custom.history_rows);
  const want = objects(ef.custom.history_sample);
  const got = objects(hist).filter((r) => ef.custom.history_iso3.includes(r.iso3));
  same(got, want, "history sample");
  const meta = ex.exportMeta(tables.meta, S.weightShares(custom, config), "2026-01-01T00:00:00+00:00");
  assert.equal(ex.toJson({}, meta), ef.custom.meta_json);
});

test("an unscored economy is written with empty cells, never NaN", () => {
  const t = ex.indexTable(data("master"), tables.dtypes.index);
  const line = ex.toCsv(t).split("\n").find((l) => l.startsWith("ASM,"));
  assert.ok(line && !/nan|undefined|null/i.test(line), line);
  assert.match(line, /^ASM,American Samoa,East Asia & Pacific,High income,,/);
});
