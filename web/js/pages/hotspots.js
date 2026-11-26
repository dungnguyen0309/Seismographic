// Hotspots (app_pages/hotspots.py): where fighting is happening now (UCDP candidate events), where conflict news is
// rising (GDELT), and the calendar of dated events. The board follows the visitor's weights and today's date.
import * as ui from "../lib/ui.js";
import { h } from "../lib/dom.js";
import { clickedIso3, mapColorscale, plot } from "../lib/charts.js";
import { asRows, na } from "../lib/scoring.js";
import { countryTable, flagUrl } from "../lib/table.js";
import { fixed } from "../lib/format.js";
import * as g9 from "../charts/group9.js";

export const title = "Hotspots";
export const required = ["data/hotspots/meta.json", "data/hotspots/monthly.json", "data/hotspots/cells.json",
  "data/hotspots/signal.json", "data/events.json"];

const C = g9.HOTSPOTS;
const TABS = { board: "Board", map: "Map", calendar: "Calendar" };
const STATUS_TONE = { Escalating: "var(--sg-worse)", Easing: "var(--sg-better)" };  // Steady and Quiet stay muted ink
const EMPTY = { columns: [], rows: [] };

export async function render(main, ctx) {
  await ui.loadCss("/css/group9.css");
  const c = ctx.core.config;
  const { heading } = g9;
  const plots = new Map();  // box -> cleanup of the chart drawn in it
  const cleanups = [];
  let gone = false;
  const chart = (box, fig, onClick = null) => {
    plots.get(box)?.();
    const el = h("div", { class: "g9-chart" });
    box.replaceChildren(el);
    plots.set(box, plot(el, fig, onClick ? { onClick } : {}));
  };
  const toCountry = (p) => { const iso3 = clickedIso3(p); if (iso3) ctx.go("/country", { country: iso3 }); };
  const get = (name) => ctx.fetchJSON(`/data/hotspots/${name}.json`).catch(() => null);
  const [meta, monthly, cells, sig] = await Promise.all([get("meta"), get("monthly"), get("cells"), get("signal")]);
  const m = meta ?? {};
  const today = g9.todayIso();
  const stale = g9.newsStale(m, today);
  const signal = stale ? EMPTY : sig ?? EMPTY;
  const hasSignal = asRows(signal).length > 0;
  const inSignal = new Set(asRows(signal).map((s) => s.iso3));
  const newsNote = hasSignal ? "" : stale ? " The news data is out of date." : " The news data has not been collected yet.";
  const table = ctx.table();
  const brd = g9.board(table, monthly ?? EMPTY, cells ?? EMPTY, signal);
  const cellRows = asRows(cells ?? EMPTY);
  const through = m.ucdp_through;
  const hasUcdp = !!through && cellRows.length > 0;  // no files is no data, not "no fighting"
  let ucdpWindow = "";
  if (hasUcdp) {
    let start = g9.addDays(through, -(C.WINDOW_DAYS - 1));
    if (m.ucdp_from && m.ucdp_from > start) start = m.ucdp_from;  // the files may cover less than the window
    ucdpWindow = `${g9.day(start)} to ${g9.day(through)}`;
  }
  const asOf = [through ? `UCDP events through ${g9.day(through)}` : "", m.gdelt_through ? `conflict news through ${g9.day(m.gdelt_through)}` : ""];
  const sum = (k) => cellRows.reduce((s, r) => s + r[k], 0);

  main.append(...[ui.weightsNote(ctx), ui.hero(title, asOf.filter(Boolean).join(" · "))].filter(Boolean));
  main.append(ui.kpiRow([
    { label: "Hotspots tracked", value: brd.length, help: `Countries with at least ${C.MIN_EVENTS_90D} UCDP events or ${C.MIN_DEATHS_90D} `
      + `deaths in the last ${C.WINDOW_DAYS} days, an Escalating conflict-news signal, or a composite score of ${C.MIN_COMPOSITE} or more.` },
    { label: "Escalating now", value: hasSignal ? brd.filter((r) => r.status === "Escalating").length : "—",
      help: `Hotspots where the share of news about conflict in the last ${C.RECENT_DAYS} days is at least ${C.ESCALATING_RATIO} `
        + `times its usual level over the ${C.WINDOW_DAYS} days (GDELT).${newsNote}` },
    { label: `UCDP events, ${C.WINDOW_DAYS} days`, value: hasUcdp ? fixed(sum("events"), 0, { group: true }) : "—",
      help: `Organised violence with at least one death${hasUcdp ? `, ${ucdpWindow},` : ""} from UCDP's candidate events: preliminary `
        + `data, published about six weeks after the month ends and revised later.${hasUcdp ? "" : " The UCDP data is not available."}` },
    { label: `Deaths, ${C.WINDOW_DAYS} days`, value: hasUcdp ? fixed(sum("deaths"), 0, { group: true }) : "—",
      help: `UCDP's best estimate of the deaths in those events${hasUcdp ? `, ${ucdpWindow}.` : "."}` },
  ]));

  const tabs = h("div");
  main.append(tabs, ui.footer());
  ui.urlTabs(tabs, TABS, ctx).on("board", boardTab).on("map", mapTab).on("calendar", calendarTab);

  // --- Board: one card per hotspot ---------------------------------------------------------------------------------
  function card(r) {
    const flag = flagUrl(r.iso2, c.NO_FLAG);
    const score = na(r.composite) ? "" : `${fixed(r.composite, 0)} · `;
    let word = [h("span", { style: `color:${STATUS_TONE[r.status] ?? "var(--sg-muted)"};font-weight:600` }, r.status), " · "], news;
    if (!inSignal.has(r.iso3)) [word, news] = [null, "No conflict-news data yet"];  // a status word would read as a finding
    else if (r.status === "Quiet") news = "Too little coverage to read";
    else if (na(r.ratio)) news = "Conflict news up from none on most days";  // a usual level of zero: no ratio to show
    else news = [h("span", { "aria-hidden": "true" }, `×${fixed(r.ratio, 1)}`), ui.sr(`${fixed(r.ratio, 1)} times the`), " conflict news vs its 90-day level"];
    const b = (n) => h("b", null, fixed(n, 0, { group: true }));
    const fighting = !hasUcdp ? "No UCDP data" : r.events_90d
      ? [b(r.events_90d), " UCDP events · ", b(r.deaths_90d), " deaths in the last 90 days"] : "No UCDP events in the last 90 days";
    return h("div", { class: "g9-card" }, h("div", { class: "g9-hs" },
      h("div", { class: "g9-hs-id" }, flag ? h("img", { src: flag, alt: "" }) : null, h("span", { class: "g9-hs-name" }, r.name)),
      h("div", null, ui.tierBadge(r.tier, score)),
      h("div", null, word, news),
      h("div", null, fighting),
      r.last_event ? h("div", { class: "g9-hs-meta" }, `Last event ${g9.day(r.last_event)}`) : null,
      r.analyst_rating ? h("div", { class: "g9-hs-meta" }, "Analyst: ", ui.tierBadge(r.analyst_rating)) : null),
    ui.button(`Open ${r.name}`, { type: "tertiary", icon: "arrow_forward", href: `/country?country=${encodeURIComponent(r.iso3)}` }));
  }

  function boardTab(panel) {
    let region = "All regions", status = "All";
    const controls = h("div", { class: "g9-controls" }), grid = h("div", { class: "g9-board" });
    const select = ui.select({ label: "Region", options: ["All regions", ...g9.regions(brd)], value: region,
      onChange: (r) => { region = r; draw(); } });
    select.classList.add("g9-w290");
    panel.append(controls, grid, ui.cite(["ucdp_ged", "gdelt", "index", "flags"]));
    const draw = () => {
      const inRegion = region === "All regions" ? brd : brd.filter((r) => r.region === region);
      const counts = {};
      for (const r of inRegion) counts[r.status] = (counts[r.status] ?? 0) + 1;
      const seg = ui.segmented({ label: "Status", options: ["All", ...C.STATUS_ORDER], value: status,
        format: (s) => (hasSignal || s === "All" ? `${s} (${s === "All" ? inRegion.length : counts[s] ?? 0})` : s),
        help: `From the share of news about conflict: Escalating = at least ${C.ESCALATING_RATIO} times its usual level in the last `
          + `${C.RECENT_DAYS} days; Easing = ${C.EASING_RATIO} times or less; Quiet = fewer than ${C.MIN_ARTICLES_7D} articles in the `
          + `week, too few to read.${newsNote}`,
        onChange: (s) => { status = s; cards(inRegion); } });
      if (!hasSignal) seg.querySelectorAll(".sg-seg").forEach((btn) => { btn.disabled = true; });  // every count would be Quiet
      controls.replaceChildren(select, seg);
      cards(inRegion);
    };
    const cards = (inRegion) => {
      const shown = status === "All" ? inRegion : inRegion.filter((r) => r.status === status);
      grid.replaceChildren(shown.length ? h("div", { class: "g9-grid" }, shown.map(card)) : ui.emptyState("No hotspots with these filters."));
    };
    draw();
  }

  // --- Map: the UCDP event cells and the events by month ------------------------------------------------------------
  function mapTab(panel) {
    const regionOf = Object.fromEntries(asRows(table).map((r) => [r.iso3, r.region]));
    const names = Object.fromEntries(asRows(ctx.core.countries).map((r) => [r.iso3, r.name]));
    const body = h("div", { class: "sg-stack" }), mapBox = h("div"), barsBox = h("div");
    const select = ui.select({ label: "Region", options: ["All regions", ...g9.regions(g9.mapCells(cellRows, regionOf, "All regions"))],
      value: "All regions", onChange: (r) => draw(r) });
    select.classList.add("g9-w290");
    panel.append(select, body, ui.cite(["ucdp_ged", "natural_earth"]));
    const draw = (region) => {
      const where = region === "All regions" ? "" : `, ${c.regions.find((x) => x.name === region)?.short ?? region}`;
      const shown = g9.mapCells(cellRows, regionOf, region);
      plots.get(mapBox)?.(); plots.get(barsBox)?.();
      body.replaceChildren(heading(`Events in the last ${C.WINDOW_DAYS} days${where}`), mapBox);
      if (!shown.length) mapBox.replaceChildren(ui.emptyState(hasUcdp ? "No UCDP events in this window." : "No UCDP data."));
      else chart(mapBox, g9.hotspotMap(shown, names, C.VIOLENCE, region !== "All regions"), toCountry);
      const bars = g9.monthlyBars(monthly ?? EMPTY, regionOf, region);
      if (bars) { body.append(heading(`UCDP events by month${where}`), barsBox); chart(barsBox, bars); }
    };
    draw("All regions");
  }

  // --- Calendar: dated events (elections, deadlines) ------------------------------------------------------------------
  async function calendarTab(panel) {
    const events = await ctx.fetchJSON("/data/events.json").catch(() => null);
    const names = Object.fromEntries(asRows(table).map((r) => [r.iso3, r.name]));
    const cal = events ? g9.calendar(events, names, today) : null;
    if (!cal || (!cal.upcoming.length && !cal.past.length)) return panel.append(ui.emptyState("No events on the calendar yet."));
    const body = h("div", { class: "sg-stack" }), timeline = h("div");
    panel.append(ui.segmented({ label: "Show", options: Object.keys(cal.windows), value: "Next 12 months",
      format: (w) => `${w} (${cal.windows[w].length})`, onChange: (w) => draw(w) }), body);
    const draw = (w) => {
      const shown = cal.windows[w];
      plots.get(timeline)?.();
      if (!shown.length) return body.replaceChildren(ui.emptyState("No events in this window."));
      const box = h("div", { class: "g9-table" });
      body.replaceChildren(timeline, box, ui.cite(["ifes"]));
      chart(timeline, g9.eventsTimeline(shown, today));
      const columns = [
        { key: "country", label: "Country", fmt: g9.medium }, { key: "date", label: "Date", fmt: (d) => g9.dmy(d) },
        { key: "event", label: "Event", fmt: g9.large },
        ...(new Set(shown.map((e) => e.category)).size > 1 ? [{ key: "category", label: "Category" }] : []),  // one category says nothing
        { key: "significance", label: "Significance" }, { key: "notes", label: "Notes" },
        { key: "source_url", label: "Source", fmt: (u) => (String(u).startsWith("http") ? h("a", { href: u, target: "_blank", rel: "noopener" }, "Link") : "") },
      ];
      countryTable(box, shown, { columns, key: "iso3", height: g9.TEN_ROWS });
    };
    draw("Next 12 months");
    if (cal.upcoming.length) {
      const globe = h("div", { class: "g9-globe" });
      panel.append(heading("Upcoming events on the globe"), globe, ui.cite(["ifes", "natural_earth"]));
      ui.globePanel(globe, ctx, { table, hist: ctx.history(), flows: null, metric: "composite", metricLabel: "Next event", key: "evt_globe",
        custom: new Map(cal.next.map((e) => [e.iso3, e.days])), colorscale: g9.reversedScale(mapColorscale("social")),
        valueRange: [0, 365], valueFormat: "days", ticks: ["now", "in 6 months", "in a year"],
        notes: Object.fromEntries(cal.next.map((e) => [e.iso3, e.note])), emptyLabel: "no event in the next year",
        layers: { spin: true, extrude: false, flows: false, conflict: false }, height: 360 })
        .then((g) => { if (g) gone ? g.destroy() : cleanups.push(() => g.destroy()); });
    }
  }

  return () => { gone = true; cleanups.forEach((fn) => fn()); plots.forEach((fn) => fn()); };
}
