// Global overview (app_pages/overview.py): the headline numbers, the map with the news, then hotspots, changes, the
// ranking and the risk matrix in tabs. The map and filter choices live in this history entry (history.state), so a
// weights redraw or Back keeps them and a new visit starts with the defaults, as the app's widgets do.
import { h, clear } from "../lib/dom.js";
import * as ui from "../lib/ui.js";
import * as charts from "../lib/charts.js";
import { countryTable } from "../lib/table.js";
import { asMap, asRows, na } from "../lib/scoring.js";
import { fixed } from "../lib/format.js";
import * as ov from "../charts/overview.js";

export const title = "Global overview";
export const required = ["data/overview/wgi_changes.json", "data/overview/new_flags.json", "data/events.json", "data/flows.json"];

// Material Symbols (Rounded, as Streamlit draws them) missing from /vendor/icons
const PATHS = {
  warning: "M109 -120Q98 -120 89 -125.5Q80 -131 75 -140Q70 -149 69.5 -159.5Q69 -170 75 -180L445 -820Q451 -830 460.5 -835Q470 -840 480 -840Q490 -840 499.5 -835Q509 -830 515 -820L885 -180Q891 -170 890.5 -159.5Q890 -149 885 -140Q880 -131 871 -125.5Q862 -120 851 -120ZM178 -200H782L480 -720ZM480 -240Q497 -240 508.5 -251.5Q520 -263 520 -280Q520 -297 508.5 -308.5Q497 -320 480 -320Q463 -320 451.5 -308.5Q440 -297 440 -280Q440 -263 451.5 -251.5Q463 -240 480 -240ZM520 -400V-520Q520 -537 508.5 -548.5Q497 -560 480 -560Q463 -560 451.5 -548.5Q440 -537 440 -520V-400Q440 -383 451.5 -371.5Q463 -360 480 -360Q497 -360 508.5 -371.5Q520 -383 520 -400ZM480 -460Z",
  format_list_numbered: "M150 -80Q137 -80 128.5 -88.5Q120 -97 120 -110Q120 -123 128.5 -131.5Q137 -140 150 -140H220V-170H190Q177 -170 168.5 -178.5Q160 -187 160 -200Q160 -213 168.5 -221.5Q177 -230 190 -230H220V-260H150Q137 -260 128.5 -268.5Q120 -277 120 -290Q120 -303 128.5 -311.5Q137 -320 150 -320H240Q257 -320 268.5 -308.5Q280 -297 280 -280V-240Q280 -223 268.5 -211.5Q257 -200 240 -200Q257 -200 268.5 -188.5Q280 -177 280 -160V-120Q280 -103 268.5 -91.5Q257 -80 240 -80ZM150 -360Q137 -360 128.5 -368.5Q120 -377 120 -390V-470Q120 -487 131.5 -498.5Q143 -510 160 -510H220V-540H150Q137 -540 128.5 -548.5Q120 -557 120 -570Q120 -583 128.5 -591.5Q137 -600 150 -600H240Q257 -600 268.5 -588.5Q280 -577 280 -560V-490Q280 -473 268.5 -461.5Q257 -450 240 -450H180V-420H250Q263 -420 271.5 -411.5Q280 -403 280 -390Q280 -377 271.5 -368.5Q263 -360 250 -360ZM180 -670V-820H150Q137 -820 128.5 -828.5Q120 -837 120 -850Q120 -863 128.5 -871.5Q137 -880 150 -880H210Q223 -880 231.5 -871.5Q240 -863 240 -850V-670Q240 -657 231.5 -648.5Q223 -640 210 -640Q197 -640 188.5 -648.5Q180 -657 180 -670ZM400 -200Q383 -200 371.5 -211.5Q360 -223 360 -240Q360 -257 371.5 -268.5Q383 -280 400 -280H800Q817 -280 828.5 -268.5Q840 -257 840 -240Q840 -223 828.5 -211.5Q817 -200 800 -200ZM400 -440Q383 -440 371.5 -451.5Q360 -463 360 -480Q360 -497 371.5 -508.5Q383 -520 400 -520H800Q817 -520 828.5 -508.5Q840 -497 840 -480Q840 -463 828.5 -451.5Q817 -440 800 -440ZM400 -680Q383 -680 371.5 -691.5Q360 -703 360 -720Q360 -737 371.5 -748.5Q383 -760 400 -760H800Q817 -760 828.5 -748.5Q840 -737 840 -720Q840 -703 828.5 -691.5Q817 -680 800 -680Z",
  scatter_plot: "M680 -120Q614 -120 567 -167Q520 -214 520 -280Q520 -346 567 -393Q614 -440 680 -440Q746 -440 793 -393Q840 -346 840 -280Q840 -214 793 -167Q746 -120 680 -120ZM680 -200Q713 -200 736.5 -223.5Q760 -247 760 -280Q760 -313 736.5 -336.5Q713 -360 680 -360Q647 -360 623.5 -336.5Q600 -313 600 -280Q600 -247 623.5 -223.5Q647 -200 680 -200ZM280 -240Q214 -240 167 -287Q120 -334 120 -400Q120 -466 167 -513Q214 -560 280 -560Q346 -560 393 -513Q440 -466 440 -400Q440 -334 393 -287Q346 -240 280 -240ZM280 -320Q313 -320 336.5 -343.5Q360 -367 360 -400Q360 -433 336.5 -456.5Q313 -480 280 -480Q247 -480 223.5 -456.5Q200 -433 200 -400Q200 -367 223.5 -343.5Q247 -320 280 -320ZM440 -560Q374 -560 327 -607Q280 -654 280 -720Q280 -786 327 -833Q374 -880 440 -880Q506 -880 553 -833Q600 -786 600 -720Q600 -654 553 -607Q506 -560 440 -560ZM440 -640Q473 -640 496.5 -663.5Q520 -687 520 -720Q520 -753 496.5 -776.5Q473 -800 440 -800Q407 -800 383.5 -776.5Q360 -753 360 -720Q360 -687 383.5 -663.5Q407 -640 440 -640Z",
  filter_list: "M440 -240Q423 -240 411.5 -251.5Q400 -263 400 -280Q400 -297 411.5 -308.5Q423 -320 440 -320H520Q537 -320 548.5 -308.5Q560 -297 560 -280Q560 -263 548.5 -251.5Q537 -240 520 -240ZM280 -440Q263 -440 251.5 -451.5Q240 -463 240 -480Q240 -497 251.5 -508.5Q263 -520 280 -520H680Q697 -520 708.5 -508.5Q720 -497 720 -480Q720 -463 708.5 -451.5Q697 -440 680 -440ZM160 -640Q143 -640 131.5 -651.5Q120 -663 120 -680Q120 -697 131.5 -708.5Q143 -720 160 -720H800Q817 -720 828.5 -708.5Q840 -697 840 -680Q840 -663 828.5 -651.5Q817 -640 800 -640Z",
};
function icon(name) {
  if (!PATHS[name]) return ui.icon(name);
  const span = h("span", { class: "sg-glyph ov-icon", "aria-hidden": "true" });
  span.innerHTML = `<svg viewBox="0 -960 960 960" width="1em" height="1em" fill="currentColor"><path d="${PATHS[name]}"/></svg>`;
  return span;
}
const pageLink = (href, label, iconName, attrs = {}) => h("a", { class: "sg-page-link", href, ...attrs }, icon(iconName), h("span", null, label));

const STYLES = ["3D globe", "Flat map"];
const EXPLORED = "sg-explored"; // sessionStorage: the visitor has opened the Introduction (prm/ui.py page_setup)
const HELP = {
  metric: "Composite: the weighted average of the four pillar scores. Each pillar scores one area of risk (stability, "
    + "governance, economy, social) from 0 to 100. Higher is riskier.",
  style: "3D globe: drag to rotate, Ctrl/⌘ + scroll or +/− to zoom, click a country. On a touch screen, tap the globe first.",
  conflict: "Countries with at least 25 battle-related deaths in the latest UCDP year.",
  assessed: "Countries with a written assessment in the assessments/ folder.",
  hotspots: "A different list: countries with recent fighting (UCDP) or rising conflict news (GDELT).",
};

const localToday = () => {
  const d = new Date(), p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};
const builtAt = (iso) => (iso ? `${String(iso).slice(0, 16).replace("T", " ")} UTC` : null);
const storage = (fn) => { try { return fn(); } catch { return null; } }; // blocked storage: carry on without it

// st.column_config.ProgressColumn: a bar from 0 to 100 and the whole number
const bar = (color) => (v) => h("span", { class: "ov-bar" },
  h("span", { class: "ov-bar-track", "aria-hidden": "true" }, h("span", { style: `width:${Math.max(0, Math.min(100, v))}%;background:${color}` })),
  h("span", { class: "ov-bar-num" }, fixed(v, 0)));
const whole = (v) => fixed(v, 0);

// A column's help, as st.column_config draws it: a tooltip while the header is hovered or its sort button focused
let tips = 0;
function headerHelp(th, text) {
  const id = `ov-tip-${++tips}`;
  const wrap = h("span", { class: "sg-help-wrap ov-th-help" }, h("span", { class: "sg-tip", role: "tooltip", id }, text));
  const sort = th.querySelector(".sg-sort");
  sort.setAttribute("aria-describedby", id);
  const show = () => { wrap.classList.add("open"); ui.keepInView(wrap.firstChild); };
  const hide = () => wrap.classList.remove("open");
  th.addEventListener("mouseenter", show);
  th.addEventListener("mouseleave", () => { if (document.activeElement !== sort) hide(); });
  sort.addEventListener("focus", show);
  sort.addEventListener("blur", hide);
  sort.addEventListener("keydown", (e) => { if (e.key === "Escape") hide(); });
  th.append(wrap);
}

// A countryTable with the app's dataframe extras: column help, tier fills from Elevated up (Severe bold)
function frame(el, rows, columns, config, opts = {}) {
  const tiers = config.tiers.slice(config.tiers.findIndex((t) => t.label === "Elevated"));
  const top = config.tiers.at(-1).label;
  countryTable(el, rows, { columns, tiers, noFlag: config.NO_FLAG, ...opts,
    extra: (tr, row) => { if (row.tier === top) tr.querySelector(".sg-cell-tier")?.classList.add("ov-tier-top"); } });
  const ths = el.querySelectorAll("thead th");
  columns.forEach((c, i) => { if (c.help) headerHelp(ths[i], c.help); });
  return el;
}

export async function render(main, ctx) {
  await ui.loadCss("/css/overview.css");
  const c = ctx.core.config, meta = ctx.core.meta, year = meta.year;
  const table = asRows(ctx.table()), hist = asRows(ctx.history()), values = asMap(ctx.core.values);
  const names = new Map(table.map((r) => [r.iso3, r]));
  const regions = [...new Set(table.map((r) => r.region).filter(Boolean))].sort();
  const incomes = ov.INCOMES.filter((i) => table.some((r) => r.income === i));
  const short = (region) => c.regions.find((x) => x.name === region)?.short ?? region;
  const pillarBy = new Map(c.pillars.map((p) => [p.key, p]));
  const metrics = { composite: "Composite risk index", ...Object.fromEntries(c.pillars.map((p) => [p.key, p.label])) };

  // the visitor's choices, restored from this history entry (unknown values fall back to the defaults)
  const kept = history.state?.overview ?? {};
  const state = {
    metric: Object.hasOwn(metrics, kept.metric ?? "") ? kept.metric : "composite",
    style: STYLES.includes(kept.style) ? kept.style : STYLES[0],
    region: regions.includes(kept.region) ? kept.region : ov.ALL,
    incomes: incomes.filter((i) => (kept.incomes ?? []).includes(i)),
    selected: names.has(kept.selected) ? kept.selected : null,
  };
  const save = () => history.replaceState({ ...history.state, overview: { ...state } }, "", location.href);
  const view = () => ov.filterView(table, state.region, state.incomes);
  const active = () => [...(state.region !== ov.ALL ? [short(state.region)] : []),
    ...(state.incomes.length ? [`${state.incomes.length} income group${state.incomes.length > 1 ? "s" : ""}`] : [])];
  const mapTitle = () => (state.metric === "composite" ? "Composite" : pillarBy.get(state.metric).short);

  let gone = false, globe = null, globeLib = null, flows = null, newsSeq = 0, tabs = null;
  const plots = new Map(); // chart element -> cleanup
  const draw = (el, fig, onClick) => { plots.set(el, charts.plot(el, fig, { onClick })); return el; };
  const sweep = () => { for (const [el, done] of plots) if (!el.isConnected) { done(); plots.delete(el); } };
  const openCountry = (point) => { const iso3 = charts.clickedIso3(point); if (iso3) ctx.go("/country", { country: iso3 }); };

  // ---- title and headline numbers (they count the filtered view) -------------------------------------------------
  const head = h("div", { class: "ov-head" });
  function drawHead() {
    const n = ov.headline(view(), hist, values, year);
    const vs = `vs ${year - 1}`;
    const explored = storage(() => sessionStorage.getItem(EXPLORED));
    const k5 = n.assessed ? { label: "Assessments", value: String(n.assessed), help: HELP.assessed }
      : { label: "Critical red flag", value: String(n.critical),
        help: `War-level violence (1,000+ battle deaths in a year) or inflation of 50% or more. ${n.flagged} of ${n.scored} have at least one red flag.` };
    clear(head).append(...[
      ui.hero(title, [String(year), ...active()].join(" · ")),
      explored ? null : h("p", { class: "ov-intro" }, pageLink("/introduction", "Introduction: how the index works", "info",
        { onclick: () => storage(() => sessionStorage.setItem(EXPLORED, "1")) })),
      ui.kpiRow([
        { label: "Countries scored", value: String(n.scored) },
        { label: "High or Severe risk", value: String(n.high), delta: n.high_delta, deltaColor: "inverse", note: n.high_delta === null ? null : vs },
        { label: "Median score", value: n.median, delta: n.median_delta === null ? null : ov.pyFloat(n.median_delta),
          deltaColor: n.median_color, note: n.median_delta === null ? null : vs },
        { label: "In armed conflict", value: String(n.conflict), delta: n.conflict_delta, deltaColor: "inverse",
          note: n.conflict_delta === null ? null : vs, help: HELP.conflict },
        k5,
      ]),
    ].filter(Boolean));
  }

  // ---- map controls: what the map shows, and one filter for the whole page ---------------------------------------
  const metricPick = ui.select({ label: "Map shows", options: Object.keys(metrics), value: state.metric, format: (k) => metrics[k],
    help: HELP.metric, onChange: (k) => { state.metric = k; save(); drawMap(); drawLegend(); } });
  metricPick.classList.add("ov-metric");
  const stylePick = ui.segmented({ label: "Map style", options: STYLES, value: state.style, help: HELP.style,
    onChange: (s) => { state.style = s; save(); drawMap(); drawCite(); drawFilterLabel(); } });
  const filter = ui.popover("Filter");
  filter.button.prepend(icon("filter_list"));
  const regionPick = ui.select({ label: "Region", options: [ov.ALL, ...regions], value: state.region,
    onChange: (r) => { state.region = r; filtersChanged(); } });
  const incomePick = ui.multiselect({ label: "Income group", options: incomes, value: state.incomes, placeholder: "All income groups",
    onChange: (list) => { state.incomes = list; filtersChanged(); } });
  filter.body.append(regionPick, incomePick);
  function drawFilterLabel() {
    const label = active().length ? `Filter: ${active().join(" · ")}` : "Filter";
    filter.button.querySelector(":scope > span:not([aria-hidden])").textContent = label;
    filter.body.setAttribute("aria-label", label);
    filter.button.title = "Limit the whole page to a region or income group"
      + (active().length && state.style === STYLES[0] ? ". The globe dims the countries outside it." : "");
  }
  const controls = h("div", { class: "ov-controls" }, metricPick, stylePick, filter);

  // ---- the map: the 3D globe with the news beside it, or the flat map ---------------------------------------------
  const mapBox = h("div", { class: "ov-map" });
  const newsBox = h("div", { class: "ov-news", role: "region", "aria-label": "News" });
  function globeOptions() {
    return { inView: view().map((r) => r.iso3), region: state.region === ov.ALL ? null : state.region, selected: state.selected };
  }
  // a map that fails says so in its place; the rest of the page carries on
  const drawMap = () => mapNow().catch((err) => {
    console.warn("section failed: the map", err);
    if (!gone) clear(mapBox).append(ui.caption("The map can't be shown right now. The rest of the page is unaffected."));
  });
  async function mapNow() {
    if (state.style === STYLES[0]) {
      if (globe && globeLib) {
        globe.update(globeLib.buildGlobeData(table, hist, flows, state.metric, mapTitle(), { ...globeOptions(), onFlat: true }));
        return;
      }
      for (const [el, done] of plots) if (mapBox.contains(el)) { done(); plots.delete(el); }
      const globeEl = h("div", { class: "ov-globe" });
      clear(mapBox).append(h("div", { class: "ov-split" }, h("div", { class: "ov-split-row" }, globeEl, newsBox)));
      drawNews();
      [flows, globeLib] = await Promise.all([ctx.fetchJSON("/data/flows.json").catch(() => null), import("../lib/globe.js")]);
      if (gone || state.style !== STYLES[0] || !globeEl.isConnected) return;
      const handle = await ui.globePanel(globeEl, ctx, { table, hist, flows, metric: state.metric, metricLabel: mapTitle(), ...globeOptions(),
        onSelect: (iso3) => { state.selected = iso3 && names.has(iso3) ? iso3 : null; save(); drawNews(); },
        onFlat: () => { stylePick.value = state.style = STYLES[1]; save(); drawMap(); drawCite(); drawFilterLabel();
          stylePick.querySelector('[aria-checked="true"]')?.focus(); } });
      if (gone || !globeEl.isConnected) handle?.destroy();
      else globe = handle;
    } else {
      globe?.destroy();
      globe = null;
      const fig = charts.choropleth(view(), state.metric, mapTitle(), state.region !== ov.ALL);
      if (state.metric === "composite") fig.data.forEach((t) => { t.showscale = false; }); // the tier legend below is the one legend
      const el = h("div", { class: "ov-flat" });
      clear(mapBox).append(el);
      sweep();
      draw(el, fig, openCountry);
    }
  }

  // the news column follows the country picked on the globe (headlines are fetched when the site is built)
  function drawNews() {
    const n = ++newsSeq;
    const r = names.get(state.selected);
    const list = h("div", null, ui.caption("Loading headlines…"));
    clear(newsBox).append(
      r ? ui.countryHeading(r.name, r.iso2, 2, "sg-panel-title") : h("h2", { class: "sg-panel-title" }, "Global risk news"),
      list, pageLink("/video", "Watch live TV news", "live_tv"));
    ctx.fetchJSON(`/data/news/${r ? r.iso3 : "global"}.json`)
      .then((news) => ({ articles: news.items ?? [], source: news.source, fetched: builtAt(news.fetched) }), () => null)
      .then((news) => { if (n === newsSeq && !gone) clear(list).append(ui.newsList(news, { limit: 12 })); });
  }

  // ---- legend, sources, followed countries --------------------------------------------------------------------------
  const legend = h("div", { class: "ov-legend" });
  const drawLegend = () => clear(legend).append(state.metric === "composite" ? ui.tierLegend()
    : ui.pillarChip(state.metric, `${pillarBy.get(state.metric).label}: brighter = riskier, grey = no data`));
  const citeBox = h("div");
  // the page's one Sources line: the tabs' event calendar, country facts and flags are named here too
  const drawCite = () => clear(citeBox).append(ui.cite(["index", "natural_earth", ...(state.style === STYLES[0] ? ["news", "gdelt"] : []),
    "ifes", "wb_countries", "flags"]));

  // ---- the rest, one tab at a time ------------------------------------------------------------------------------------
  const tabsBox = h("div");
  const label = (name, text) => { const f = document.createDocumentFragment(); f.append(icon(name), text); return f; };
  function drawTabs() {
    clear(tabsBox);
    sweep();
    tabs = ui.urlTabs(tabsBox, { hotspots: label("warning", "Hotspots"), changes: label("trending_up", "Changes"),
      ranking: label("format_list_numbered", "Ranking"), matrix: label("scatter_plot", "Risk matrix") }, ctx);
    tabs.on("hotspots", hotspotsTab).on("changes", changesTab).on("ranking", rankingTab).on("matrix", matrixTab);
  }

  function hotspotsTab(panel) {
    const v = view();
    panel.append(ui.guard("The hotspots", async (box) => {
      const [newFlags, events] = await Promise.all([ctx.fetchJSON("/data/overview/new_flags.json"),
        ctx.fetchJSON("/data/events.json").then(asRows, () => [])]); // no calendar: no event reasons, as in the app
      const rows = ov.hotspotRows(v, { newFlags, events, today: localToday(), year });
      if (!rows.length) box.append(ui.emptyState("No hotspots with the current filters."));
      else {
        box.append(frame(h("div", { class: "ov-hot" }), rows, [ // no flag here, as in the app
          { key: "name", label: "Country", type: "country" },
          { key: "composite", label: "Score", fmt: bar("var(--sg-soft)") },
          { key: "why", label: "Why listed", help: `Scores 50 or more and, since ${year - 1}, got at least 2 points riskier (▲), crossed a `
            + `new red-flag threshold (⚑, not crossed in ${year - 1}), or faces a high-significance event in the next 120 days.` },
          { key: "tier", label: "Tier", type: "tier" },
        ], c));
        box.append(h("p", { class: "ov-here" }, pageLink("/?tab=ranking", "Full ranking", "format_list_numbered", { "aria-current": "page",
          onclick: (e) => { e.preventDefault(); tabs.select("ranking"); } })));
      }
    }), h("p", null, pageLink("/hotspots?tab=board", "Conflict hotspots", "radar", { title: HELP.hotspots })));
  }

  function changesTab(panel) {
    const v = view();
    panel.append(h("h2", null, `Biggest moves since ${year - 1}`), ui.moversLists(v, { n: 5 }),
      h("p", null, pageLink("/changes", "All score changes this year", "trending_up")),
      h("h2", null, "Biggest movers in political stability"),
      ui.guard("The political stability movers", async (box) => {
        const changes = await ctx.fetchJSON("/data/overview/wgi_changes.json");
        if (!box.isConnected) return; // the visitor moved on while it loaded
        const rows = ov.wgiMovers(asRows(changes), table, v, ov.filtered(state.region, state.incomes));
        if (!rows.length) { box.append(ui.emptyState("Not enough governance data to show changes.")); return; }
        box.append(h("p", { class: "sg-caption" }, h("em", null, "Political Stability & Absence of Violence"),
          `, ${rows[0].start_year} → ${rows[0].end_year}. Red = worse, blue = better. Small changes may be within the margin of error shown on each country profile.`),
        draw(h("div"), charts.movers(rows), openCountry));
      }));
  }

  function rankingTab(panel) {
    const rows = ov.rankingRows(view());
    const w = ctx.weights();
    const share = (p) => `${p.short} ${fixed((w[p.key] / 100) * 100, 0)}%`;
    panel.append(frame(h("div", { class: "ov-rank" }), rows, [
      { key: "name", label: "Country", type: "country" },
      { key: "composite", label: "Composite", fmt: bar("var(--sg-soft)"),
        help: `Weighted average of the pillar scores (${c.pillars.map(share).join(", ")}), from 0 to 100. Higher is riskier.` },
      { key: "trend", label: "1-yr change", align: "right", help: `Composite score vs ${year - 1}. ▲ = riskier, ▼ = safer, ■ = under 1 point` },
      { key: "tier", label: "Tier", type: "tier" },
      { key: "rank", label: "Rank", fmt: whole, help: "1 = highest risk" },
      ...c.pillars.map((p) => ({ key: p.key, label: p.short, fmt: bar(c.PILLAR_COLORS[p.key]), help: p.label })),
      { key: "flags", label: "Red flags", fmt: whole, help: "Warning thresholds crossed, plus a falling political stability trend" },
      { key: "region", label: "Region", fmt: short },
      { key: "coverage", label: "Data coverage", fmt: (x) => `${fixed(x, 0)}%` },
      { key: "assessment", label: "Assessment", help: "A written analyst assessment exists" },
      { key: "analyst_rating", label: "Analyst rating" },
    ], c, { height: "460px" }),
    h("div", null, ui.download("Download ranking (CSV)", { data: () => ov.rankingCsv(rows), filename: `seismographic_risk_index_${year}.csv`,
      mime: "text/csv", icon: null })));
  }

  function matrixTab(panel) {
    const v = view(), scored = v.filter((r) => !na(r.composite));
    const axes = Object.fromEntries(c.pillars.map((p) => [p.key, p.label]));
    let x = c.pillars[0].key, y = c.pillars[2].key;
    const chart = h("div");
    const redraw = () => { plots.get(chart)?.(); draw(chart, charts.riskMatrix(scored, x, y), openCountry); };
    const pick = (lab, value, set) => ui.select({ label: lab, options: Object.keys(axes), value, format: (k) => axes[k], onChange: (k) => { set(k); redraw(); } });
    const left = h("div", { class: "sg-stack" }, h("h2", null, "Risk matrix"),
      h("div", { class: "sg-inputs" }, h("div", { class: "sg-row" }, pick("Horizontal axis", x, (k) => { x = k; }),
        pick("Vertical axis", y, (k) => { y = k; }))),
      chart, ui.caption("Bubble size = population."));
    const right = h("div", { class: "sg-stack" });
    if (state.region === ov.ALL) {
      right.append(h("h2", null, "Risk tiers by region"), draw(h("div"), charts.tierDistribution(scored), (point) => {
        const region = regions.find((r) => short(r) === point?.y);
        if (region) { regionPick.value = state.region = region; filtersChanged(); } // a region's bar filters the page to it
      }));
    } else {
      right.append(h("h2", null, `Highest risk in ${state.region}`), frame(h("div"), ov.topRisk(v), [
        { key: "name", label: "Country", type: "country" },
        { key: "composite", label: "Score", fmt: bar("var(--sg-soft)") },
        { key: "tier", label: "Tier", type: "tier" },
        { key: "flags", label: "Red flags", fmt: whole },
      ], c));
    }
    panel.append(h("div", { class: "sg-pair" }, h("div", { class: "sg-row" }, left, right)));
    redraw();
  }

  function filtersChanged() {
    save();
    drawHead();
    drawFilterLabel();
    drawMap();
    drawTabs();
  }

  main.append(...[ui.weightsNote(ctx), head, controls, mapBox, legend, citeBox, ui.followingStrip(table), tabsBox,
    ui.dataStatus(meta), ui.footer()].filter(Boolean));
  drawHead();
  drawFilterLabel();
  drawLegend();
  drawCite();
  drawMap();
  drawTabs();
  return () => {
    gone = true;
    globe?.destroy();
    for (const done of plots.values()) done();
  };
}
