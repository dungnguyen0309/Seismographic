// Economic stress (app_pages/economy.py): inflation, growth, debt, deficits, external balance and reserves for every
// country. Every chart here depends on the region picked, so web/js/charts/group9.js draws them.
import * as ui from "../lib/ui.js";
import { h } from "../lib/dom.js";
import { clickedIso3, plot } from "../lib/charts.js";
import { countryTable } from "../lib/table.js";
import { fixed } from "../lib/format.js";
import * as g9 from "../charts/group9.js";

export const title = "Economic stress";
export const required = ["data/group9/economy.json"];

const SIZES = [20, 40, 60, 100, 250];
const OUTLOOK = { Inflation: ["inflation", "Inflation (%)"], Growth: ["gdp_growth", "Real GDP growth (%)"],
  "Public debt": ["gov_debt", "Public debt (% of GDP)"] };

export async function render(main, ctx) {
  await ui.loadCss("/css/group9.css");
  const c = ctx.core.config, year = ctx.core.meta.year;
  const { heading, progress } = g9;
  const cleanups = [];
  let gone = false;
  const economy = await ctx.fetchJSON("/data/group9/economy.json").catch(() => null);
  const table = ctx.table(), values = ctx.core.values;
  const all = g9.econView(table, values, "All regions");
  let region = "All regions", size = 40, show = "Inflation", view = all, globe = null;

  const edition = ctx.core.meta.series?.gdp_growth?.edition || "IMF World Economic Outlook";
  main.append(...[ui.weightsNote(ctx), ui.hero(title, `${year} estimates from the ${edition}, plus World Bank reserves data.`)].filter(Boolean));

  const regionSelect = ui.select({ label: "Region", options: ["All regions", ...g9.regions(all)], value: region,
    onChange: (r) => { region = r; view = g9.econView(table, values, r); drawRegion(); } });
  const sizeSlider = ui.slider({ label: "Countries in the heatmap", min: 0, max: SIZES.length - 1, step: 1, value: SIZES.indexOf(size),
    format: (i) => String(SIZES[i]), help: "The most economically stressed first (highest Economy pillar score)",
    onChange: (i) => { size = SIZES[i]; drawHeat(); } });
  sizeSlider.classList.add("g9-select-slider");
  const kpis = h("div"), globeBox = h("div", { class: "g9-globe" }), heat = h("div"), scatter = h("div"), outlook = h("div"),
    caption = h("div"), warnings = h("div", { class: "g9-table" });
  const plots = new Map();  // box -> cleanup of the chart drawn in it
  const chart = (box, fig, onClick = null) => {
    plots.get(box)?.();
    const el = h("div", { class: "g9-chart" });
    box.replaceChildren(el);
    plots.set(box, plot(el, fig, onClick ? { onClick } : {}));
  };
  const toCountry = (iso3) => { if (iso3) ctx.go("/country", { country: iso3 }); };

  main.append(
    h("div", { class: "sg-row" }, regionSelect, sizeSlider),
    kpis,
    ui.pageLink("/stress", "Stress test", "bolt"),
    heading("On the globe"),
    globeBox,
    heading("Stress heatmap"),
    heat,
    h("div", { class: "sg-row g9-split-115" },
      h("div", { class: "sg-stack" }, heading("Growth vs inflation"), scatter),
      h("div", { class: "sg-stack" }, heading("IMF outlook"), ui.segmented({ label: "Show", options: Object.keys(OUTLOOK), value: show,
        onChange: (s) => { show = s; drawOutlook(); } }), outlook, caption)),
    heading("Several warning thresholds crossed"),
    warnings,
    ui.cite(["imf", "wdi", "imf_ara"]),
    ui.footer(),
  );

  let flags, globeOpts;
  function drawHeat() {
    const rows = g9.heatRows(view, size);
    chart(heat, g9.econHeatmap(rows), (p) => toCountry(rows.find((r) => r.name === p.y)?.iso3));
  }
  function drawOutlook() {
    if (!economy) {
      plots.get(outlook)?.();
      outlook.replaceChildren(ui.emptyState("The IMF outlook is not available right now."));
      return caption.replaceChildren();
    }
    const [key, label] = OUTLOOK[show];
    const series = g9.inView(economy.series[key], view);
    chart(outlook, g9.imfOutlook(series, year, label, year - 12, year + 5));
    caption.replaceChildren(ui.caption(`Median, with the middle half shaded. Dashed = IMF projections to ${g9.outlookLast(series, year)}.`));
  }
  function drawRegion() {
    const counts = g9.econKpis(view);
    kpis.replaceChildren(ui.kpiRow([
      { label: "High inflation (≥ 20%)", value: counts[0] },
      { label: "Economy shrinking", value: counts[1], help: "Negative real GDP growth" },
      { label: "Public debt ≥ 90% of GDP", value: counts[2] },
      { label: "Deficit ≥ 5% of GDP", value: counts[3] },
      { label: "Reserves < 3 months of imports", value: counts[4] },
    ]));
    flags = g9.econFlags(view, values, c);
    globeOpts = { inView: view.map((r) => r.iso3), region: region === "All regions" ? null : region, key: "eco_globe",
      notes: g9.econNotes(flags), layers: { spin: true, flows: false, conflict: false } };
    if (globe) drawGlobe();
    drawHeat();
    chart(scatter, g9.stagflationScatter(view), (p) => toCountry(clickedIso3(p)));
    drawOutlook();
    const rows = g9.warningRows(view, flags, c);
    if (!rows.length) warnings.replaceChildren(ui.caption("No country crosses two or more economic warning thresholds."));
    else {
      countryTable(warnings, rows, { height: `${Math.min(460, 35 * (rows.length + 1) + 3)}px`, noFlag: c.NO_FLAG, extra: g9.nameTitle, columns: [
        { key: "name", label: "Country", type: "country" },
        { key: "count", label: "Warnings" },
        { key: "economic", label: "Economy risk", fmt: (v) => progress(v, 100, c.PILLAR_COLORS.economic, fixed(v, 0)) },
        { key: "warnings", label: "Thresholds crossed", fmt: g9.large },
      ] });
    }
  }
  const drawGlobe = () => import("../lib/globe.js")
    .then((m) => globe?.update(m.buildGlobeData(table, ctx.history(), null, "economic", "Economy", globeOpts)));
  drawRegion();
  const first = globeOpts;
  ui.globePanel(globeBox, ctx, { table, hist: ctx.history(), flows: null, metric: "economic", metricLabel: "Economy", ...first })
    .then((g) => {
      if (!g) return;
      if (gone) return g.destroy();
      globe = g;
      cleanups.push(() => g.destroy());
      if (globeOpts !== first) drawGlobe();  // the region changed while the globe was loading
    });

  return () => { gone = true; globe = null; cleanups.forEach((fn) => fn()); plots.forEach((fn) => fn()); };
}
