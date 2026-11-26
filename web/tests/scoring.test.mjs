import test from "node:test";
import assert from "node:assert/strict";
import * as S from "../js/lib/scoring.js";
import { data, fixture, same, sameTable } from "./helpers.mjs";

const config = data("config");
const values = data("values");
const defaults = Object.fromEntries(config.pillars.map((p) => [p.key, p.default_weight]));
const custom = { stability: 50, governance: 20, economic: 20, social: 10 };
const extras = fixture("model_extras");
const vmap = S.asMap(values);

test("default weights reproduce scores_default", () => {
  sameTable(S.computeScores(values, defaults, { config }), fixture("scores_default"));
});
test("w=50,20,20,10 reproduces scores and history", () => {
  sameTable(S.computeScores(values, custom, { config }), fixture("scores_w50_20_20_10"));
  const h = S.historyFor(data("history"), custom, config);
  const exp = fixture("history_w50_20_20_10");
  assert.deepEqual(h.columns, exp.columns);
  assert.equal(h.rows.length, exp.rows.length);
  h.rows.forEach((r, i) => same(r, exp.rows[i], `history[${i}]`));
});
test("historyFor with default weights is the stored history", () => {
  const stored = data("history");
  const h = S.historyFor(stored, defaults, config);
  h.rows.forEach((r, i) => same(r, stored.rows[i], `history[${i}]`));
});
test("unscored country has null composite, rank and tier", () => {
  const s = S.computeScores(values, defaults, { config });
  const asm = s.get("ASM");
  assert.equal(asm.composite, null);
  assert.equal(asm.rank, null);
  assert.equal(asm.tier, null);
  assert.ok(s.get("NGA").composite > 0);
});
test("flag counts equal Python's", () => {
  assert.deepEqual(S.flagCounts(values, data("wgi_trend"), config), fixture("flag_counts"));
});
test("normaliseAgainst(values, values) is normalise", () => {
  const xs = [3, 1, 4, 1, 5, null, 9, 2, 6];
  for (const [hi, m] of [[true, "percentile"], [false, "percentile"], [true, "log"], [false, "log"]]) {
    same(S.normaliseAgainst(xs, xs, hi, m, config), S.normalise(xs, hi, m, config), `${hi}${m}`);
  }
});
test("normalise: ties rank min, missing stays missing", () => {
  assert.deepEqual(S.normalise([1, 1, 3, null], true, "percentile", config), [0, 0, 100, null]);
  assert.deepEqual(S.normalise([5], true, "percentile", config), [null]);
});
test("tierFor", () => {
  assert.equal(S.tierFor(null, config), null);
  assert.equal(S.tierFor(NaN, config), null);
  assert.equal([0, 19.99, 20, 59.99, 60, 80, 100].map((x) => S.tierFor(x, config)).join(), "Low,Low,Moderate,Elevated,High,Severe,Severe");
});
test("redFlags and flagChanges", () => {
  for (const [iso, exp] of Object.entries(extras.flags)) same(S.redFlags(vmap.get(iso), config), exp, iso);
  const before = vmap.get("NGA");
  const after = { ...before, ...extras.flag_changes.after };
  const [worse, eased] = S.flagChanges(before, after, config);
  same(worse, extras.flag_changes.worse);
  same(eased, extras.flag_changes.eased);
});
test("sensitivity, similar and simulate match Python", () => {
  const scores = S.computeScores(values, custom, { config });
  for (const [iso, exp] of Object.entries(extras.sensitivity)) same(S.sensitivity(values, iso, custom, config), exp, iso);
  for (const [iso, exp] of Object.entries(extras.similar)) same(S.similar(scores, iso, 6, config), exp, iso);
  for (const [iso, e] of Object.entries(extras.simulate)) {
    const { scores: s2 } = S.simulate(values, iso, e.changes, custom, config);
    const r = s2.get(iso);
    same({ composite: r.composite, rank: r.rank, tier: r.tier, stability: r.stability },
      { composite: e.composite, rank: e.rank, tier: e.tier, stability: e.stability }, iso);
  }
});
test("countryBrief matches Python", () => {
  const scores = S.computeScores(values, defaults, { config });
  const countries = data("countries");
  for (const [iso, e] of Object.entries(extras.brief)) {
    const lines = S.countryBrief(iso, e.name, values, scores, countries, data("meta").year,
      { wgiTrend: data("wgi_trend")[iso], nextGrowth: e.nextGrowth, config });
    assert.deepEqual(lines, e.lines, iso);
  }
});
test("decodeWeights", () => {
  assert.deepEqual(S.decodeWeights("50,20,20,10", config), custom);
  for (const bad of ["1,2,3", "50,20,20,11", "0,0,0,0", "x", "105,0,0,0", null]) assert.equal(S.decodeWeights(bad, config), null, String(bad));
});
