// The country page's own steps (web/js/charts/country.js) against what Python gives for the same inputs
// (web/tests/fixtures/country_cases.json, written by staticbuild/country.py fixtures()).
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { asMap, asRows, redFlags, setConfig } from "../js/lib/scoring.js";
import {
  applyPreset, flowLists, headerMeta, indicatorsCsv, markdown, peerGroups, peerRanking, regionalMedian,
  sensitivityRows, similarRows, videosAbout, whatifResult, WHATIF_PRESETS,
} from "../js/charts/country.js";
import { data, fixture, same } from "./helpers.mjs";

const config = data("config");
setConfig(config);
const cases = fixture("country_cases");
const values = data("values");
const countries = asRows(data("countries"));
const names = new Map(countries.map((c) => [c.iso3, c.name]));
const profile = (iso3) => JSON.parse(readFileSync(new URL(`../data/country/${iso3}.json`, import.meta.url), "utf8"));
const WEIGHTS = {
  default: { weights: { stability: 35, governance: 25, economic: 25, social: 15 }, scores: data("scores"), master: data("master") },
  w50_20_20_10: { weights: { stability: 50, governance: 20, economic: 20, social: 10 }, scores: fixture("scores_w50_20_20_10"),
    master: fixture("master_w50_20_20_10") },
};
const ISOS = Object.keys(cases.countries);

test("the fixture covers an unscored country and both weightings", () => {
  assert.ok(ISOS.includes("ASM") && ISOS.length >= 5);
  assert.deepEqual(Object.keys(cases.weights).sort(), Object.keys(WEIGHTS).sort());
  assert.deepEqual(Object.keys(WHATIF_PRESETS), Object.keys(cases.countries.NGA.presets));
});

for (const iso3 of ISOS) {
  const c = cases.countries[iso3];
  const master = asMap(data("master")), scores = asMap(data("scores")), v = asMap(values).get(iso3);

  test(`headerMeta ${iso3}`, () => {
    assert.equal(headerMeta(master.get(iso3), v, scores.get(iso3), config), c.meta);
  });

  test(`indicatorsCsv ${iso3}`, () => {
    assert.equal(indicatorsCsv(v, scores.get(iso3), names.get(iso3), iso3, config), c.csv);
  });

  test(`flowLists ${iso3}`, () => {
    const got = flowLists(data("flows"), names, iso3);
    for (const side of ["origin", "host"]) {
      assert.deepEqual(got[side].rows.map((r) => [r.iso3, r.value]), c.flows[side].rows, side);
      assert.equal(got[side].total, c.flows[side].total, side);
    }
  });

  test(`applyPreset ${iso3}`, () => {
    const { controls } = profile(iso3).whatif;
    for (const preset of Object.keys(WHATIF_PRESETS)) same(applyPreset(preset, controls), c.presets[preset], preset);
  });

  for (const [label, w] of Object.entries(WEIGHTS)) {
    const expected = cases.weights[label][iso3];
    const sc = asMap(w.scores), table = asRows(w.master);
    const row = table.find((r) => r.iso3 === iso3);

    test(`sensitivityRows ${iso3} ${label}`, () => {
      same(sensitivityRows(values, iso3, w.weights, config), expected.sensitivity);
    });

    test(`regionalMedian ${iso3} ${label}`, () => {
      same(regionalMedian(table, row.region, config), expected.regional_median);
    });

    test(`peerRanking ${iso3} ${label}`, () => {
      const groups = peerGroups(table, row);
      assert.deepEqual(Object.keys(groups), Object.keys(expected.peers));
      for (const [group, rows] of Object.entries(groups)) {
        const got = peerRanking(rows, iso3, names.get(iso3), sc.get(iso3).composite);
        const want = expected.peers[group];
        assert.equal(got.place, want.place, group);
        assert.equal(got.sr, want.sr, group);
        assert.equal(got.caption, want.caption, group);
        assert.deepEqual(got.rows.map((r) => [r.iso3, r.group_rank]), want.rows, group);
        assert.ok(got.rows.every((r) => (r.iso3 === iso3) === r.name.startsWith("▶ ")), group);
      }
    });

    test(`similarRows ${iso3} ${label}`, () => {
      same(similarRows(sc, iso3, config).map((r) => [r.iso3, r.closeness]), expected.similar);
    });

    test(`whatifResult ${iso3} ${label}`, () => {
      const { controls } = profile(iso3).whatif;
      for (const [preset, want] of Object.entries(expected.whatif)) {
        const setTo = preset === "none" ? {} : applyPreset(preset, controls);
        const got = whatifResult(values, sc.get(iso3), w.weights, iso3, names.get(iso3), controls, setTo,
          preset === "none" ? null : preset, config);
        for (const key of Object.keys(want)) same(got[key], want[key], `${preset}.${key}`);
      }
    });
  }
}

test("the header's top flag is the most severe one (red flags, then the stability flag)", () => {
  const nga = redFlags(asMap(values).get("NGA"), config);
  assert.equal(nga[0].short, "War");
});

test("videosAbout matches the videos the app matches", () => {
  for (const [iso3, c] of Object.entries(cases.videos.about)) {
    const got = videosAbout(cases.videos.videos, iso3, names, c.news_name, c.official, c.aliases).map((v) => v.video_id);
    assert.deepEqual(got, c.ids, iso3);
  }
});

test("markdown: blocks, inline marks, links, and escaped text", () => {
  const html = markdown("## Bottom line\nOne *two* **three** `four` <b>x</b>  \nnext\n\n1. first\n2. second\n\n"
    + "- a [link](https://example.org/a_b) and https://example.org/c_d.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n---");
  assert.equal(html, "<h2>Bottom line</h2><p>One <em>two</em> <strong>three</strong> <code>four</code> &lt;b&gt;x&lt;/b&gt;<br>next</p>"
    + "<ol><li>first</li><li>second</li></ol>"
    + '<ul><li>a <a href="https://example.org/a_b" target="_blank" rel="noopener">link</a> and '
    + '<a href="https://example.org/c_d" target="_blank" rel="noopener">https://example.org/c_d</a>.</li></ul>'
    + '<div class="sg-cp-md-table"><table><thead><tr><th>A</th><th>B</th></tr></thead><tbody><tr><td>1</td><td>2</td></tr></tbody></table></div><hr>');
  assert.equal(markdown("3. third\n4. fourth"), '<ol start="3"><li>third</li><li>fourth</li></ol>');
  assert.equal(markdown('<script>alert("x")</script>'), "<p>&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;</p>");
});

test("assessment tables keep whole words: no overflow-wrap: anywhere on the Markdown body", () => {
  // anywhere shrinks min-content, so a table's auto layout squeezes its columns and splits words letter by letter
  const css = readFileSync(new URL("../css/country.css", import.meta.url), "utf8");
  const rules = css.match(/[^{}]*\.sg-cp-md[^{}]*\{[^}]*\}/g) ?? [];
  assert.ok(rules.length > 0);
  for (const rule of rules) assert.doesNotMatch(rule, /overflow-wrap:\s*anywhere/, rule.trim());
});

test("every country file has the controls and figures the page reads", () => {
  for (const iso3 of ISOS) {
    const p = profile(iso3);
    assert.ok(Array.isArray(p.whatif.controls) && Array.isArray(p.whatif.missing), iso3);
    assert.ok(p.figures.wgi.data && p.figures.macro.data, iso3);
    assert.ok(Array.isArray(p.elsewhere) && p.news_name, iso3);
  }
});
