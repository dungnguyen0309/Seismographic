// Regions: one region at a time (app_pages/regions.py) — scores, trend, risers and fallers, ranking, events and news.
import * as ui from "../lib/ui.js";
import { h, clear } from "../lib/dom.js";
import { plot, tierMix } from "../lib/charts.js";
import { countryTable } from "../lib/table.js";
import { fixed } from "../lib/format.js";
import * as g8 from "../charts/group8.js";

export const title = "Regions";
export const required = ["data/events.json", "data/flows.json"];

const slug = (text) => String(text).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, ""); // staticbuild/core.py slug

export async function render(main, ctx) {
  await ui.loadCss("/css/group8.css");
  const c = ctx.core.config, year = ctx.core.meta.year;
  const table = ctx.table(), hist = ctx.history();
  const regions = g8.regionList(table);
  let region = g8.pickRegion(ctx.params.get("region"), regions);

  const head = h("div"), body = h("div", { class: "sg-page g8-body" });
  let cleanups = [];
  const picker = ui.select({ label: "Region", options: regions, value: region, onChange: (r) => { region = r; draw(); } });
  picker.classList.add("g8-narrow");
  main.append(...[ui.weightsNote(ctx), head, picker, body].filter(Boolean));

  function draw() {
    cleanups.forEach((f) => f());
    cleanups = [];
    ctx.setParam("region", region);
    const s = g8.regionSummary(table, hist, ctx.core.values, region, year);
    clear(head).append(ui.hero(region, s.subtitle)); // the title names the picked region, above the picker
    body.style.minHeight = `${body.offsetHeight}px`;
    clear(body);
    body.append(ui.kpiRow(s.kpis.map((k) => ({ label: k.label, value: k.value, delta: k.delta ?? null,
      deltaColor: k.color ?? "normal", note: k.delta === null || k.delta === undefined ? null : k.note, help: k.help ?? null }))));

    // --- Map and tier mix
    const globeBox = h("div"), mixBox = h("div");
    body.append(h("div", { class: "sg-pair" }, h("div", { class: "sg-row" },
      h("div", { class: "g8-wide-13" }, h("h2", null, "Risk globe"), globeBox),
      h("div", { class: "g8-wide-1" }, h("h2", null, `Tier mix since ${c.HISTORY_START}`), mixBox))));
    const mine = cleanups;
    ctx.fetchJSON("/data/flows.json").catch(() => null) // no flows: the globe still draws, without arcs
      .then((flows) => (mine === cleanups && globeBox.isConnected ? ui.globePanel(globeBox, ctx, { table, hist, flows,
        metric: "composite", metricLabel: "Composite", inView: s.rv.map((r) => r.iso3), region, key: "reg_globe", height: 520,
        layers: { spin: false, flows: false } }) : null))
      .then((globe) => { if (globe) (mine === cleanups && globeBox.isConnected ? cleanups.push(() => globe.destroy()) : globe.destroy()); });
    cleanups.push(plot(mixBox, tierMix(s.rh)));

    // --- Risers and fallers, ranking
    body.append(h("h2", null, `Biggest moves since ${year - 1}`), ui.moversLists(s.rv, { n: 5 }));
    const rankBox = h("div");
    body.append(h("h2", null, "Ranking"), rankBox);
    const columns = [
      { key: "name", label: "Country", type: "country" },
      { key: "composite", label: "Composite", align: "right", fmt: (v) => fixed(v, 0) },
      { key: "trend", label: "1-yr change", align: "right" },
      { key: "tier", label: "Tier", type: "tier" },
      { key: "rank", label: "Global rank", align: "right", fmt: (v) => String(Math.trunc(v)) },
      ...c.pillars.map((p) => ({ key: p.key, label: p.short, align: "right", fmt: (v) => fixed(v, 0) })),
    ];
    const bars = g8.progressCells(columns, { composite: c.INK.soft, ...c.PILLAR_COLORS });
    countryTable(rankBox, g8.byRank(s.rv), { columns, height: `${s.height}px`, noFlag: c.NO_FLAG,
      tiers: c.tiers.slice(c.tiers.findIndex((t) => t.label === "Elevated")), // as the tier badges: Elevated and up filled
      extra: (tr, row) => { bars(tr, row); if (row.tier === c.tiers.at(-1).label) tr.children[3].style.fontWeight = "700"; } });

    // --- Events and news
    const eventsBox = h("div"), newsBox = h("div", { class: "g8-news" });
    body.append(h("div", { class: "sg-pair" }, h("div", { class: "sg-row" },
      h("div", { class: "sg-stack" }, h("h2", null, "Upcoming events"), eventsBox,
        h("a", { class: "sg-page-link", href: "/hotspots?tab=calendar" }, h("span", { class: "sg-icon g8-icon-event", "aria-hidden": "true" }),
          h("span", null, "Full event calendar"))),
      h("div", null, h("h2", null, "Regional news"), newsBox))));
    ctx.fetchJSON("/data/events.json")
      .then((events) => eventsBox.append(ui.upcomingEvents(g8.regionEvents(events, s.rv), { limit: 10 })))
      .catch((err) => { console.warn("section failed: the events", err); eventsBox.append(ui.emptyState("The event calendar can't be shown right now.")); });
    ctx.fetchJSON(`/data/news/region-${slug(region)}.json`).catch(() => null)
      .then((news) => newsBox.append(ui.newsList(g8.newsFrom(news), { limit: 12 })));
    body.append(ui.cite(["index", "unhcr", "natural_earth", "wb_countries", "flags", "ifes", "news", "gdelt"]), ui.footer());
    requestAnimationFrame(() => { body.style.minHeight = ""; });
  }

  draw();
  return () => cleanups.forEach((f) => f());
}
