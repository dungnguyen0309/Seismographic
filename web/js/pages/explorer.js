// Indicator explorer (app_pages/explorer.py): any one of the index's indicators on the 3D globe, with its distribution and leaders.
import * as ui from "../lib/ui.js";
import { h, clear } from "../lib/dom.js";
import { distribution, mapColorscale, plot } from "../lib/charts.js";
import { countryTable } from "../lib/table.js";
import { fixed } from "../lib/format.js";
import * as g8 from "../charts/group8.js";

export const title = "Indicator explorer";
export const required = [];

const ALL = "All regions";
const link = (href, text) => h("a", { href, target: "_blank", rel: "noopener" }, text);

export async function render(main, ctx) {
  await ui.loadCss("/css/group8.css");
  const c = ctx.core.config, year = ctx.core.meta.year;
  const table = ctx.table(), hist = ctx.history(), scores = ctx.scores();
  const options = g8.indicatorOptions(c);
  const labels = Object.fromEntries(options.map((o) => [o.key, o.label]));
  const regions = g8.regionList(table);
  let key = g8.recall("exp-indicator", options[0].key);
  let region = g8.recall("exp-region", ALL);
  if (!labels[key]) key = options[0].key;
  if (region !== ALL && !regions.includes(region)) region = ALL;

  const body = h("div", { class: "sg-page g8-body" });
  let cleanups = [];
  const pickInd = ui.select({ label: "Indicator", options: options.map((o) => o.key), value: key, format: (k) => labels[k],
    onChange: (k) => { key = k; g8.remember("exp-indicator", k); draw(); } });
  const pickRegion = ui.select({ label: "Region", options: [ALL, ...regions], value: region,
    onChange: (r) => { region = r; g8.remember("exp-region", r); draw(); } });
  pickInd.classList.add("g8-wide-2");
  pickRegion.classList.add("g8-wide-1");
  main.append(...[ui.weightsNote(ctx), ui.hero(title), h("div", { class: "sg-inputs" }, h("div", { class: "sg-row" }, pickInd, pickRegion)), body].filter(Boolean));

  function draw() {
    cleanups.forEach((f) => f());
    cleanups = [];
    body.style.minHeight = `${body.offsetHeight}px`;
    clear(body);
    const ind = c.indicators.find((i) => i.key === key);
    const color = c.PILLAR_COLORS[ind.pillar];
    const { view, known } = g8.explorerFrame(table, ctx.core.values, scores, key, region, year);
    // one caption and no KPI row, so on a phone the first list starts on the first screen
    body.append(h("p", { class: "sg-caption g8-lead" }, `${ind.description}\n${ind.unit} · ${ind.higher_is_riskier ? "higher" : "lower"} = riskier · `
      + `${known.length} countries with data, median ${g8.medianText(known, ind)} · source: `, link(ind.source_url, ind.source), " · ", link(ind.url, "see the data ↗")));

    // --- Leaders, stacked: side by side, half-width tables hid the risk score behind a sideways scroll
    for (const list of g8.leaderLists(known, ind)) {
      const box = h("div", { class: "g8-leaders" });
      body.append(h("h2", null, list.title), box);
      const columns = [{ key: "name", label: "Country", type: "country" }, { key: "shown", label: ind.unit, align: "right" },
        { key: "risk", label: "Risk score", align: "right", fmt: (v) => fixed(v, 0) },
        { key: "year", label: "Year", align: "right", fmt: (v) => String(Math.trunc(v)) }];
      countryTable(box, list.rows, { columns, noFlag: c.NO_FLAG, extra: g8.progressCells(columns, { risk: color }) });
    }

    // --- Globe
    const globeBox = h("div");
    body.append(h("h2", null, "On the globe"), globeBox, ui.cite([ind.source_key, "natural_earth"]));
    const mine = cleanups;
    ui.globePanel(globeBox, ctx, { table, hist, flows: null, metric: ind.pillar, metricLabel: `${ind.short} risk`, key: "exp_globe",
      inView: view.map((r) => r.iso3), region: region === ALL ? null : region, custom: g8.explorerCustom(table, scores, key),
      colorscale: mapColorscale(ind.pillar), notes: g8.explorerNotes(known, ind), layers: { spin: true, flows: false, conflict: false } })
      .then((globe) => { if (globe) (mine === cleanups && globeBox.isConnected ? cleanups.push(() => globe.destroy()) : globe.destroy()); });

    // --- Distribution
    const distBox = h("div");
    body.append(h("h2", null, "Distribution"), distBox, ui.cite([ind.source_key]), ui.footer());
    cleanups.push(plot(distBox, distribution(known.map((r) => r.value), `${ind.short} (${ind.unit})`, color, ind.norm === "log")));
    requestAnimationFrame(() => { body.style.minHeight = ""; });
  }

  draw();
  return () => cleanups.forEach((f) => f());
}
