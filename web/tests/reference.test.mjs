// The reference pages' calculations against Python (fixtures from staticbuild/reference.py).
import test from "node:test";
import assert from "node:assert/strict";
import { data, fixture, same } from "./helpers.mjs";
import { historyFor, setConfig, weightShares } from "../js/lib/scoring.js";
import * as charts from "../js/lib/charts.js";
import { flagRows, glossarySearch, highlight, onsetPanel, tierRows, trackRecord, videosAbout } from "../js/charts/reference.js";

const config = data("config");
setConfig(config);
charts.setConfig(config);
const custom = weightShares({ stability: 50, governance: 20, economic: 20, social: 10 }, config);

test("track record: onset panel and summary as validation.summary, and its chart", () => {
  const { conflict, cases } = fixture("reference_track");
  assert.equal(cases.length, 4);
  for (const c of cases) {
    const hist = c.weights === "default" ? data("history") : historyFor(data("history"), custom, config);
    const got = trackRecord(onsetPanel(hist, conflict, c.score));
    same(got, c.summary, `${c.weights} ${c.score}`);
    same(charts.onsetFifths(got.by_fifth, got.base_rate, config.PILLAR_COLORS.stability), c.figure, `${c.weights} ${c.score} figure`, 1e-6);
  }
});

test("track record: no conflict data gives nothing to show", () => {
  assert.equal(trackRecord(onsetPanel(data("history"), null, "stability")), null);
  assert.equal(trackRecord([]), null);
});

test("videos about a country as ui.videos_about", () => {
  const { videos, aliases, news_names: newsNames, cases } = fixture("reference_videos");
  const countries = data("countries");
  const col = (name) => countries.rows.map((r) => r[countries.columns.indexOf(name)]);
  const iso3 = col("iso3");
  const names = Object.fromEntries(iso3.map((i, k) => [i, col("name")[k]]));
  const official = Object.fromEntries(iso3.map((i, k) => [i, col("official_name")[k]]));
  for (const c of cases) {
    const got = videosAbout(videos, c.iso3, names, official[c.iso3], { newsNames, aliases });
    assert.deepEqual(got.map((v) => videos.indexOf(v)), c.hits, c.iso3);
  }
});

test("glossary search and highlight as the page", () => {
  const { categories } = data("reference/glossary");
  const { cases, marks } = fixture("reference_glossary");
  for (const c of cases) {
    const got = glossarySearch(categories, c.query);
    assert.equal(got.caption, c.caption, c.query);
    assert.deepEqual(got.hits.map((g) => ({ name: g.name, terms: g.terms.map((t) => t.term) })), c.categories, c.query);
  }
  for (const m of marks) assert.deepEqual(highlight(m.text, m.query), m.parts, `${m.text} / ${m.query}`);
});

test("guide tables: tiers for the weights in use, red flags crossed", () => {
  const f = fixture("reference_guide");
  same(tierRows(data("master"), config), f.tiers.default, "default");
  same(tierRows(fixture("master_w50_20_20_10"), config), f.tiers.w50_20_20_10, "w50_20_20_10");
  same(flagRows(data("values"), config), f.flags, "flags");
});
