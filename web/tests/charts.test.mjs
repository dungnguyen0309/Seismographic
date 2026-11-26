// charts.js: each ported figure equals the Python figure (plotly.io.to_json minus the template) for the fixture inputs,
// trace by trace and key by key, numbers to 1e-6. Fixtures: staticbuild/charts.py.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as charts from "../js/lib/charts.js";
import { data, fixture, same } from "./helpers.mjs";

charts.setConfig(data("config"));

const PORTED = {
  choropleth: "choropleth", risk_matrix: "riskMatrix", tier_distribution: "tierDistribution", movers: "movers",
  risk_history: "riskHistory", pillar_bars: "pillarBars", whatif_pillars: "whatifPillars", radar: "radar",
  compare_lines: "compareLines", change_bars: "changeBars", tier_mix: "tierMix", tier_shift: "tierShift",
  ranked_bars: "rankedBars", yearly_bars: "yearlyBars", distribution: "distribution", peer_strip: "peerStrip",
  onset_fifths: "onsetFifths", case_history: "caseHistory",
};

for (const [py, js] of Object.entries(PORTED)) {
  test(js, () => {
    const { cases } = fixture(`charts_${py}`);
    assert.ok(cases.length);
    cases.forEach((c, i) => same(charts[js](...c.args), c.figure, `${py}[${i}]`, 1e-6));
  });
}

test("historySummary", () => {
  for (const c of fixture("charts_history_summary").cases) assert.equal(charts.historySummary(...c.args), c.text);
});

test("base adds the shared layout", () => {
  const fig = charts.base({ data: [], layout: {} }, 300, true);
  assert.equal(fig.layout.height, 300);
  assert.equal(fig.layout.showlegend, true);
  same(fig.layout.margin, { l: 8, r: 8, t: 36, b: 8 });
});

test("themed: the Streamlit template, the container width and the click modes", () => {
  const fig = { data: [{ type: "bar", x: [1], y: [2] }], layout: { height: 300, title: { text: "T" } } };
  const plain = charts.themed(fig, 640);
  assert.equal(plain.layout.width, 640);
  assert.equal(plain.layout.height, 300);
  assert.equal(plain.layout.title.text, "<b>T</b>");
  assert.equal(plain.layout.template.layout.paper_bgcolor, "#000000");
  assert.equal(plain.layout.clickmode, undefined);
  assert.equal(plain.config.displayModeBar, false);
  assert.equal(plain.config.topojsonURL, "/vendor/plotly/topojson/", "geo base maps come from /vendor, not cdn.plot.ly");
  assert.equal(fig.layout.title.text, "T", "the input figure is not changed");
  const clickable = charts.themed({ data: [], layout: { hovermode: "x unified" } }, 100, { clickable: true });
  assert.equal(clickable.layout.width, 150, "never narrower than 150 px");
  assert.equal(clickable.layout.height, 450, "450 px without a figure height");
  assert.deepEqual([clickable.layout.clickmode, clickable.layout.hovermode, clickable.layout.dragmode],
    ["event+select", "x unified", "pan"]);
  // pre-built figure JSON may still carry the template with Streamlit's placeholder colours
  const prebuilt = charts.themed({ data: [], layout: { template: { layout: { colorway: ["#000001"] } } } }, 500);
  assert.equal(prebuilt.layout.template.layout.colorway[0], "#83c9ff");
});

test("rankedBars leaves out rows without a value (an unscored country) instead of failing", () => {
  const [rows, ...rest] = fixture("charts_ranked_bars").cases[0].args;
  const expected = fixture("charts_ranked_bars").cases[0].figure;
  const unscored = [{ iso3: "ASM", name: "American Samoa", value: null }, { iso3: "XKX", name: "Kosovo", value: NaN }];
  same(charts.rankedBars([unscored[0], ...rows, unscored[1]], ...rest), expected, "with nulls", 1e-6);
});

test("the vendored geo base map is the one plotly.js asks for (world, 110m: no chart sets scope or resolution)", () => {
  const geo = charts.choropleth([{ iso3: "NGA", name: "Nigeria", tier: "High", rank_label: "1", composite: 60 }], "composite", "C").layout.geo;
  assert.equal(geo.scope, undefined);
  assert.equal(geo.resolution, undefined);
  const topo = JSON.parse(readFileSync(new URL("../vendor/plotly/topojson/world_110m.json", import.meta.url), "utf8"));
  assert.equal(topo.type, "Topology");
  assert.ok(topo.objects.countries && topo.objects.land && topo.objects.ocean && topo.objects.lakes);
});

test("clickedIso3 reads the last customdata value", () => {
  assert.equal(charts.clickedIso3({ customdata: ["Nigeria", 58, "NGA"] }), "NGA");
  assert.equal(charts.clickedIso3({ customdata: [] }), null);
  assert.equal(charts.clickedIso3({ y: "x" }), null);
});
