// Stress test: one economic shock applied to many countries at once (app_pages/stress.py). The test runs here
// (group10/stress.js, a port of prm/stress.py) with the visitor's weights; ?shock=, ?regions= and ?incomes= hold it.
import * as ui from "../lib/ui.js";
import * as charts from "../lib/charts.js";
import { h, clear } from "../lib/dom.js";
import { asRows, na } from "../lib/scoring.js";
import { fixed, signed } from "../lib/format.js";
import { countryTable } from "../lib/table.js";
import { decode, encode, fmtG, resultsCsv, run, summary } from "../group10/stress.js";
import { BOM, npRound } from "../group10/export.js";
import { icon, withIcon } from "../group10/icons.js";

export const title = "Stress test";
export const required = ["data/group10/stress.json"];

const CUSTOM = "Custom";
const INCOMES = ["Low income", "Lower middle income", "Upper middle income", "High income"];
const SHOW = ["Crossing a line", "All countries hit"];
// Streamlit keeps a page's widgets while the visitor stays (a weights change redraws the page) and drops them when they
// leave; a draw while this page is still on screen is such a redraw
let here = false;
let last = null; // the shocks used last in this visit: a new visit without a link opens on them
let kept = null; // {scenario, show, open}: the picks on screen when the page was last drawn over

const sameShocks = (a, b) => Object.keys(a).length === Object.keys(b).length && Object.entries(a).every(([k, v]) => b[k] === v);

export async function render(main, ctx) {
  const keep = here ? kept : null;
  const redraw = keep !== null && last !== null;
  here = true;
  kept = null;
  const leave = () => { here = location.pathname === "/stress"; };
  await ui.loadCss("/css/group10.css");
  main.append(...[ui.weightsNote(ctx), ui.hero(title)].filter(Boolean));
  let file;
  try {
    file = await ctx.fetchJSON("/data/group10/stress.json");
  } catch (err) {
    console.warn("section failed: stress test", err);
    main.append(ui.emptyState("The stress test can't be shown right now. The rest of the app still works."));
    return leave;
  }
  const { shocks: defs, scenarios } = file;
  const names = Object.keys(scenarios);
  const config = ctx.core.config;
  const table = ctx.table(), hist = ctx.history(), scores = ctx.scores();
  const rows = asRows(table);
  const regionList = [...new Set(rows.map((r) => r.region).filter(Boolean))].sort();
  const incomeList = INCOMES.filter((i) => rows.some((r) => r.income === i));

  // A redraw keeps the shocks on screen; a new visit takes a shared link first, then the shocks used last, then the first
  // scenario
  const linked = decode(ctx.params.get("shock"), defs);
  const seed = redraw ? last : Object.keys(linked).length ? linked : last && Object.keys(last).length ? last : scenarios[names[0]];
  let show = redraw ? keep.show : SHOW[0];
  const shocks = Object.fromEntries(defs.map((d) => [d.key, Number(seed[d.key] ?? 0)]));
  const fromLink = (param, options) => [...new Set((ctx.params.get(param) ?? "").split("|").filter((x) => options.includes(x)))];
  let regions = fromLink("regions", regionList), incomes = fromLink("incomes", incomeList);

  // ---- controls ----
  const scenario = ui.select({ label: "Scenario", options: [...names, CUSTOM],
    value: redraw ? keep.scenario : names.find((n) => sameShocks(scenarios[n], seed)) ?? CUSTOM,
    help: "Round-number versions of past world-wide shocks, to start from. Countries hit are scored against today's values, so the yardstick stays fixed.",
    onChange: (name) => {
      if (!(name in scenarios)) return;
      for (const d of defs) shocks[d.key] = scenarios[name][d.key] ?? 0;
      sliders.forEach((s, i) => { s.value = shocks[defs[i].key]; });
      update();
    } });
  const regionPick = ui.multiselect({ label: "Regions hit", options: regionList, value: regions, placeholder: "All regions",
    onChange: (v) => { regions = v; update(); } });
  const incomePick = ui.multiselect({ label: "Income groups hit", options: incomeList, value: incomes, placeholder: "All income groups",
    onChange: (v) => { incomes = v; update(); } });
  const custom = () => { scenario.value = CUSTOM; };
  const sliders = defs.map((d) => ui.slider({ label: `${d.label}, ${d.unit}`, min: d.low, max: d.high, step: d.step, value: shocks[d.key],
    format: (v) => fixed(v, d.step < 1 ? 1 : 0, { sign: true }),
    onChange: (v) => { shocks[d.key] = v; custom(); update(); } }));
  const shockRows = [];
  for (let i = 0; i < sliders.length; i += 4) shockRows.push(h("div", { class: "sg-row g10-shock-row" }, sliders.slice(i, i + 4)));
  const expander = ui.expander("Shocks: none", { expanded: redraw && keep.open }, ...shockRows,
    withIcon(ui.button("Clear shocks", { type: "tertiary", onClick: () => {
      for (const d of defs) shocks[d.key] = 0;
      sliders.forEach((s) => { s.value = 0; });
      custom();
      update();
    } }), "restart_alt"));
  expander.classList.add("g10-shocks");
  const summaryLabel = expander.querySelector("summary > span:last-child");
  summaryLabel.before(icon("tune"));
  main.append(h("div", { class: "sg-card" }, h("div", { class: "sg-inputs g10-stress-inputs" }, h("div", { class: "sg-row" }, scenario, regionPick, incomePick)), expander));

  // ---- results ----
  const info = ui.callout("info", "Pick a scenario or move a slider.");
  const kpis = h("div");
  const globeBox = h("div", { class: "g10-globe" });
  const segBox = h("div");
  const tableBox = h("div", { class: "g10-nowrap" });
  const tiersBox = h("div"), flagsBox = h("div");
  let csv = "";
  const results = h("div", { class: "sg-stack" }, kpis, globeBox, h("h2", null, "Who crosses a line"), segBox, tableBox,
    h("div", { class: "sg-pair" }, h("div", { class: "sg-row" },
      h("div", { class: "sg-stack g10-tight" }, h("p", { class: "sg-strong" }, "Tiers today and under stress"), tiersBox),
      h("div", { class: "sg-stack g10-tight" }, h("p", { class: "sg-strong" }, "Red-flag lines crossed"), flagsBox))),
    ui.download("Download results (CSV)", { data: () => `${BOM}${csv}`, filename: "seismographic-stress-test.csv", mime: "text/csv", type: "tertiary", icon: null }),
    ui.cite(["imf", "wdi", "index"]));
  main.append(info, results);

  let globe = null, hit = [];
  const cleanups = [];
  const drawTable = () => {
    const list = show === SHOW[1] ? hit : hit.filter((r) => r.tier_move > 0 || r.new_flag_count > 0);
    const desc = (k) => (a, b) => (na(a[k]) ? (na(b[k]) ? 0 : 1) : na(b[k]) ? -1 : b[k] - a[k]);
    const shown = [...list].sort((a, b) => desc("tier_move")(a, b) || desc("new_flag_count")(a, b) || desc("delta")(a, b))
      .map((r) => ({ ...r, tier_change: r.tier_move ? `${r.tier_before} → ${r.tier_after}` : String(r.tier_after), flags_text: r.new_flags.join(" · ") }));
    if (!shown.length) {
      clear(tableBox).append(ui.caption("No country crosses a tier or a red-flag line under these shocks."));
      return;
    }
    const bar = config.tiers.find((t) => t.label === "Elevated").color;
    countryTable(clear(tableBox), shown, { height: `${Math.min(520, 35 * (shown.length + 1) + 3)}px`, noFlag: config.NO_FLAG, columns: [
      { key: "name", label: "Country", type: "country" },
      { key: "delta", label: "Change", align: "right", fmt: (v) => signed(npRound(v, 1)) },
      { key: "composite_before", label: "Today", fmt: (v) => fixed(npRound(v, 0), 0) },
      { key: "composite_after", label: "Under stress", fmt: (v) => h("span", { class: "g10-bar" },
        h("span", { class: "g10-bar-track" }, h("span", { style: `width:${Math.min(Math.max(v, 0), 100)}%;background:${bar}` })),
        h("span", null, fixed(npRound(v, 0), 0))) },
      { key: "tier_change", label: "Tier" },
      { key: "flags_text", label: "New or worse red flags" },
    ] });
  };
  segBox.append(ui.segmented({ label: "Show", labelHidden: true, options: SHOW, value: show, onChange: (v) => { show = v; drawTable(); } }));

  function update() {
    const active = Object.fromEntries(defs.filter((d) => shocks[d.key]).map((d) => [d.key, shocks[d.key]]));
    const set = defs.filter((d) => shocks[d.key]).map((d) => `${d.label} ${shocks[d.key] > 0 ? "+" : ""}${fmtG(shocks[d.key])} ${d.unit}`);
    summaryLabel.textContent = `Shocks: ${set.length ? set.join(" · ") : "none"}`;
    last = active;
    ctx.setParam("regions", regions.length ? regions.join("|") : null);
    ctx.setParam("incomes", incomes.length ? incomes.join("|") : null);
    const any = Object.keys(active).length > 0;
    info.hidden = any;
    results.hidden = !any;
    ctx.setParam("shock", any ? encode(active, defs) : null);
    if (!any) return;

    const scope = regions.length || incomes.length
      ? rows.filter((r) => (!regions.length || regions.includes(r.region)) && (!incomes.length || incomes.includes(r.income))).map((r) => r.iso3) : null;
    const result = run(ctx.core.values, ctx.weights(), active, scope, defs, config, { before: scores });
    const s = summary(result, config);
    clear(kpis).append(ui.kpiRow([
      { label: "Countries hit", value: String(s.countries) },
      { label: "Move up a tier", value: String(s.tier_up), help: `Severe tier: ${s.severe_before} today → ${s.severe_after} under stress` },
      { label: "New red flags", value: String(s.new_flags), help: `New or more severe, in ${s.with_new_flags} countries` },
      { label: "Average change", value: s.mean_delta === null ? "—" : signed(s.mean_delta), help: "Composite score points, countries hit" },
    ]));

    const byIso = new Map(result.map((r) => [r.iso3, r]));
    hit = rows.map((t) => ({ ...t, ...byIso.get(t.iso3) })).filter((r) => r.hit && !na(r.composite_before));
    const notes = {};
    for (const r of hit) {
      const note = [...(r.tier_move > 0 ? [`${r.tier_before} → ${r.tier_after}`] : []), ...r.new_flags].join(" · ");
      if (note) notes[r.iso3] = note;
    }
    const opts = { key: "stress_globe", inView: hit.map((r) => r.iso3), custom: Object.fromEntries(hit.map((r) => [r.iso3, r.delta])),
      colorscale: config.CHANGE_COLORSCALE, valueRange: [-10, 10], valueFormat: "signed", ticks: ["▼ −10 safer", "no change", "riskier +10 ▲"],
      notes, emptyLabel: "not hit", extrudeAbs: true, layers: { spin: true, flows: false, conflict: false } };
    if (!globe) globe = ui.globePanel(globeBox, ctx, { table, hist, flows: null, metric: "composite", metricLabel: "Change under stress", ...opts });
    else {
      globe.then(async (g) => {
        if (!g) return;
        const { buildGlobeData } = await import("../lib/globe.js");
        g.update(buildGlobeData(table, hist, null, "composite", "Change under stress", opts));
      }).catch((err) => console.warn("section failed: the 3D globe", err));
    }

    drawTable();
    cleanups.splice(0).forEach((fn) => fn());
    const tiersChart = h("div");
    clear(tiersBox).append(tiersChart);
    cleanups.push(charts.plot(tiersChart, charts.tierShift(hit.map((r) => r.tier_before).filter(Boolean), hit.map((r) => r.tier_after).filter(Boolean))));
    const counts = new Map();
    for (const r of hit) for (const f of r.new_flags) counts.set(f, (counts.get(f) ?? 0) + 1);
    clear(flagsBox);
    if (!counts.size) flagsBox.append(ui.caption("None."));
    else {
      const flagsChart = h("div");
      flagsBox.append(flagsChart);
      const list = [...counts].map(([flag, count]) => ({ flag, count })).sort((a, b) => b.count - a.count);
      cleanups.push(charts.plot(flagsChart, charts.rankedBars(list, "count", "flag", config.INK.worse, "countries")));
    }
    csv = resultsCsv(result, table);
  }
  update();
  return () => {
    leave();
    kept = { scenario: scenario.value, show, open: expander.open };
    cleanups.splice(0).forEach((fn) => fn());
    globe?.then((g) => g?.destroy());
  };
}
