// Score changes: this year's index against last year's (app_pages/changes.py) — risers, fallers, tier moves, new red flags.
import * as ui from "../lib/ui.js";
import { h, clear } from "../lib/dom.js";
import { changeBars, clickedIso3, plot } from "../lib/charts.js";
import { countryTable } from "../lib/table.js";
import { signed } from "../lib/format.js";
import * as g8 from "../charts/group8.js";

export const title = "Score changes";
export const required = ["data/group8/flag_changes.json"];

const ALL = "All regions";
const TABS = { moves: "Moves", map: "Map", tiers: "Tiers", drivers: "Drivers", flags: "Red flags" };
const noFlag = (rows) => rows.map((r) => ({ ...r, iso2: null })); // no flag in these tables: on a phone it pushed the change off screen
const country = { key: "name", label: "Country", type: "country" };

export async function render(main, ctx) {
  await ui.loadCss("/css/group8.css");
  const c = ctx.core.config, year = ctx.core.meta.year, prev = year - 1;
  const revised = ` ${year} uses IMF estimates for the current year, so economic moves can still be revised.`;
  const table = ctx.table(), hist = ctx.history();
  const regions = g8.regionList(table);
  let region = g8.recall("chg-region", ALL);
  if (region !== ALL && !regions.includes(region)) region = ALL;
  let flagTable = null;
  try {
    flagTable = await ctx.fetchJSON("/data/group8/flag_changes.json");
  } catch (err) {
    console.warn("section failed: the red flags", err);
  }

  const body = h("div", { class: "sg-page g8-body" });
  let cleanups = [];
  const picker = ui.select({ label: "Region", options: [ALL, ...regions], value: region,
    onChange: (r) => { region = r; g8.remember("chg-region", r); draw(); } });
  picker.classList.add("g8-narrow");
  main.append(...[ui.weightsNote(ctx), ui.hero(title, `${year} vs ${prev}`), picker, body].filter(Boolean));

  function draw() {
    cleanups.forEach((f) => f());
    cleanups = [];
    body.style.minHeight = `${body.offsetHeight}px`;
    clear(body);
    const { view, moved } = g8.changesView(table, hist, region, year, c);
    const flags = flagTable ? g8.changesFlags(flagTable, view, c) : [];
    const [riskier, safer, up, down, newFlags] = g8.changesKpis(moved, flags);
    body.append(ui.kpiRow([
      { label: "Riskier", value: riskier, help: "Composite up by a point or more." + revised },
      { label: "Safer", value: safer, help: "Composite down by a point or more." + revised },
      { label: "To a riskier tier", value: up },
      { label: "To a safer tier", value: down },
      { label: "New red flags", value: flagTable ? newFlags : "—", help: "Absolute warning thresholds crossed this year that were not crossed last year" },
    ]));

    const tabs = ui.urlTabs(body, TABS, ctx);
    tabs.on("moves", (panel) => {
      if (!moved.length) return panel.append(ui.emptyState("No year-on-year comparison is available for this selection."));
      const box = h("div");
      panel.append(box);
      cleanups.push(plot(box, changeBars(moved.map((r) => ({ ...r, thin: g8.thin(r, c) }))),
        { onClick: (p) => { const iso3 = clickedIso3(p); if (iso3) ctx.go("/country", { country: iso3 }); } }));
      panel.append(ui.caption("Scores are relative, so a country can move because others changed."
        + (g8.thinNote(moved, c) ? " Hatched bars rest on limited data." : "")));
    });
    tabs.on("map", (panel) => {
      const box = h("div");
      panel.append(box, ui.caption("Taller = bigger move. Moves beyond ±10 points share the end colour."));
      const mine = cleanups;
      ui.globePanel(box, ctx, { table, hist, flows: null, metric: "composite", metricLabel: `Change vs ${prev}`, key: "chg_globe",
        inView: view.map((r) => r.iso3), region: region === ALL ? null : region,
        custom: Object.fromEntries(moved.map((r) => [r.iso3, r.delta_1y])), colorscale: c.CHANGE_COLORSCALE, valueRange: [-10, 10],
        valueFormat: "signed", ticks: ["−10 · safer", "0", "riskier · +10"], notes: g8.changeNotes(moved),
        emptyLabel: "no comparison", extrudeAbs: true, layers: { spin: true, flows: false, conflict: false } })
        .then((globe) => { if (globe) (mine === cleanups && box.isConnected ? cleanups.push(() => globe.destroy()) : globe.destroy()); });
    });
    tabs.on("tiers", (panel) => {
      const rows = g8.tierRows(moved);
      if (!rows.length) return panel.append(ui.caption("No country changed tier."));
      const box = h("div");
      panel.append(box);
      countryTable(box, noFlag(rows), { columns: [country, { key: "trend", label: "Change", align: "right" },
        { key: "move", label: "Tier" }, { key: "driver", label: "Main driver" }] });
    });
    tabs.on("drivers", (panel) => {
      const box = h("div");
      panel.append(ui.caption(`Pillar changes since ${prev}, for countries whose composite moved a point or more.`), box);
      countryTable(box, noFlag(g8.driverRows(moved, c)), { height: "420px", columns: [country,
        { key: "trend", label: "Composite", align: "right" },
        ...c.pillars.map((p) => ({ key: `d_${p.key}`, label: p.short, align: "right", fmt: (v) => signed(v, 0) }))] });
    });
    tabs.on("flags", (panel) => {
      if (!flagTable) return panel.append(ui.emptyState("The red flags can't be shown right now. The rest of the page is unaffected."));
      if (!flags.length) return panel.append(ui.caption("No red flags changed."));
      const box = h("div");
      panel.append(box);
      countryTable(box, flags, { height: "380px", columns: [country, { key: "change", label: "Change" },
        { key: "severity", label: "Severity" }, { key: "flag_label", label: "Red flag" }] });
    });
    body.append(ui.cite(["index", "ucdp_def", "imf_ara"]), ui.footer());
    requestAnimationFrame(() => { body.style.minHeight = ""; });
  }

  draw();
  return () => cleanups.forEach((f) => f());
}
