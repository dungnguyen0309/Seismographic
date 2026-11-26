// Conflict & displacement (app_pages/conflict.py): battle deaths (UCDP via the World Bank) and forced displacement
// (UNHCR). Figures with no visitor choice come pre-built in data/group9/conflict.json; tiers follow the weights.
import * as ui from "../lib/ui.js";
import { h } from "../lib/dom.js";
import { clickedIso3, plot } from "../lib/charts.js";
import { asRows } from "../lib/scoring.js";
import { countryTable } from "../lib/table.js";
import { fixed } from "../lib/format.js";
import * as g9 from "../charts/group9.js";

export const title = "Conflict & displacement";
export const required = ["data/group9/conflict.json", "data/flows.json", "data/outlook.json"];

const MISSING = "Conflict data is not available right now.";
const TABS = { conflict: "Armed conflict", displacement: "Displacement & refugees", outlook: "Outlook" };
const { heading, progress } = g9;
const grouped = (v) => fixed(v, 0, { group: true });

export async function render(main, ctx) {
  await ui.loadCss("/css/group9.css");
  const c = ctx.core.config;
  const cleanups = [];
  let gone = false;
  const chart = (fig, clickable = false) => {
    const el = h("div", { class: "g9-chart" });
    cleanups.push(plot(el, fig, clickable ? { onClick: (p) => { const iso3 = clickedIso3(p); if (iso3) ctx.go("/country", { country: iso3 }); } } : {}));
    return el;
  };
  const [cf, flows] = await Promise.all([ctx.fetchJSON("/data/group9/conflict.json").catch(() => null),
    ctx.fetchJSON("/data/flows.json").catch(() => null)]);
  const table = ctx.table();
  const bd = cf?.bd_year;

  main.append(...[ui.weightsNote(ctx), ui.hero(title)].filter(Boolean));
  main.append(cf ? ui.kpiRow(cf.kpis) : ui.emptyState(MISSING));

  // --- The globe: stability risk, conflict rings, refugee arcs; the deadliest conflicts beside it -----------------
  main.append(heading("On the globe"));
  const globe = h("div", { class: "g9-globe" });
  const side = h("div", { class: "g9-side g9-table" });
  main.append(h("div", { class: "sg-row g9-globe-row" }, globe, side));
  ui.globePanel(globe, ctx, { table, hist: ctx.history(), flows, metric: "stability", metricLabel: "Stability", key: "cf_globe",
    notes: cf?.notes ?? null, layers: { spin: true, flows: true, conflict: true },
    hint: `Rings = armed conflict · arcs = refugee flows · ▶ replays since ${c.HISTORY_START}` })
    .then((g) => { if (g) gone ? g.destroy() : cleanups.push(() => g.destroy()); });
  if (cf) {
    countryTable(side, cf.deadliest, { columns: [{ key: "name", label: "Country" },
      { key: "deaths", label: `Battle deaths, ${bd}`, fmt: grouped }] });
  } else side.append(ui.emptyState(MISSING));
  main.append(ui.cite(["index", "ucdp", "ucdp_def", "unhcr", "natural_earth"]));

  const tabs = h("div");
  main.append(tabs, ui.footer());
  ui.urlTabs(tabs, TABS, ctx)
    .on("conflict", (panel) => armedConflict(panel))
    .on("displacement", (panel) => displacement(panel))
    .on("outlook", (panel) => outlookTab(panel));

  // --- Armed conflict -------------------------------------------------------------------------------------------
  function armedConflict(panel) {
    if (!cf) return panel.append(ui.emptyState(MISSING));
    const f = cf.figures;
    panel.append(h("div", { class: "sg-row" },
      h("div", { class: "sg-stack" }, heading("Battle deaths worldwide"), chart(f.deaths)),
      h("div", { class: "sg-stack" }, heading("Deadliest conflicts over time"), chart(f.deadliest))));
    panel.append(heading(`Countries in armed conflict (${bd})`));
    const box = h("div", { class: "g9-table" });
    panel.append(box);
    const columns = [
      { key: "name", label: "Country", type: "country" },
      { key: "deaths", label: `Deaths ${bd}`, fmt: grouped },
      { key: "change_text", label: `vs ${bd - 1}`, align: "right" },
      { key: "battle_deaths_100k", label: "Per 100k", fmt: (v) => fixed(v, 2) },
      { key: "displaced_share", label: "Displaced", fmt: (v) => `${fixed(v, 1)}%`, help: "Share of the population" },
      { key: "stability", label: "Stability risk", fmt: (v) => progress(v, 100, c.PILLAR_COLORS.stability, fixed(v, 0)) },
      { key: "level", label: "Level", help: "War = 1,000 or more battle deaths in the year (UCDP)" },
      { key: "tier", label: "Tier" },
    ];
    countryTable(box, g9.withTier(asRows(cf.rows), table), { height: "460px", noFlag: c.NO_FLAG, extra: g9.nameTitle, columns });
    box.querySelectorAll("thead th").forEach((th, i) => { if (columns[i].help) th.append(ui.helpMark(columns[i].help)); });
    panel.append(ui.cite(["ucdp", "ucdp_def", "unhcr", "wgi"]));
  }

  // --- Displacement ---------------------------------------------------------------------------------------------
  function displacement(panel) {
    if (!cf) return panel.append(ui.emptyState(MISSING));
    const f = cf.figures;
    panel.append(heading("Forcibly displaced people"), chart(f.displaced));
    panel.append(h("div", { class: "sg-row" },  // origins beside hosts, so both columns end level
      h("div", { class: "sg-stack" }, heading(`Largest displaced populations (${cf.dp_year}, millions)`), chart(f.origins, true)),
      h("div", { class: "sg-stack" }, ...(f.hosts ? [heading(`Largest host countries (${cf.flows_year}, millions)`), chart(f.hosts, true)]
        : [ui.emptyState("Refugee flow data is not available right now.")]))));
    if (f.sankey) {
      panel.append(heading("The 25 largest refugee corridors"), chart(f.sankey),
        ui.caption("Internally displaced people are not included, as they never cross a border."));
    }
    panel.append(ui.cite(["unhcr"]));
  }

  // --- Outlook: chance of new armed conflict next year ------------------------------------------------------------
  async function outlookTab(panel) {
    const outlook = await ctx.fetchJSON("/data/outlook.json").catch(() => null);
    if (!panel.isConnected) return; // the visitor moved on while it loaded
    if (!outlook) return panel.append(ui.emptyState("Not enough conflict history to run the outlook model right now."));
    const nxt = outlook.index_year + 1;
    const [average, auc, tested] = g9.outlookTexts(outlook);
    panel.append(h("p", null, `The chance that armed conflict (25+ battle deaths) breaks out in ${nxt} in each country at peace in `
      + `${outlook.data_year}, the latest conflict data. The model learned from every year since ${c.HISTORY_START}.`));
    panel.append(ui.kpiRow([
      { label: "Average chance", value: average, help: "How often armed conflict broke out the next year in a country at peace, "
        + `since ${c.HISTORY_START}.` },
      { label: "AUC on unseen years", value: auc, help: "On years the model had not seen: the chance a country where conflict "
        + "broke out had a higher prediction than one where it did not (the AUC). 0.5 = a coin flip, 1 = perfect." },
      { label: "Already in conflict", value: cf ? cf.in_conflict : "—", help: `25+ battle deaths in ${bd}: not given a chance of a new outbreak.` },
    ]));
    panel.append(heading(`Highest chance of new conflict in ${nxt}`));
    const { rows, chanceMax } = g9.outlookRows(outlook, table);
    const box = h("div", { class: "g9-table" });
    panel.append(box);
    countryTable(box, rows, { height: g9.TEN_ROWS, noFlag: c.NO_FLAG, extra: g9.nameTitle, columns: [
      { key: "name", label: "Country", type: "country" },
      { key: "chance", label: "Chance", fmt: (v) => progress(v, chanceMax, "#fd8078", `${fixed(v, 1)}%`) },
      { key: "relative", label: "× average", fmt: (v) => `${fixed(v, 1)}×` },
      { key: "recent", label: "Conflict in past 5 yrs" },
      { key: "tier", label: "Index tier" },
    ] });
    const f = cf?.figures ?? {};
    panel.append(h("div", { class: "sg-row" },
      h("div", { class: "sg-stack" }, heading("What raises the chance"), f.drivers ? chart(f.drivers) : ui.emptyState(MISSING)),
      h("div", { class: "sg-stack" }, heading("Tested on unseen years"), f.calibration ? chart(f.calibration) : ui.emptyState(MISSING),
        tested ? ui.caption(tested) : null)));
    panel.append(ui.caption("A statistical estimate across countries; it cannot foresee any one event. Few conflicts break out each "
      + "year, and coups or invasions can come without warning in this data. Use it to decide where to look closer."));
    panel.append(ui.cite(["ucdp", "ucdp_def", "index"]));
  }

  return () => { gone = true; cleanups.forEach((fn) => fn()); };
}
