// Country profile (app_pages/country.py): score, red flags, automatic brief, peers, What-if simulator, indicators,
// governance and the economy, news and the analyst's assessment. ?country= picks the country; tabs are ?tab=, the
// Peers and Data views ?view=.
import * as ui from "../lib/ui.js";
import * as charts from "../lib/charts.js";
import * as follow from "../lib/follow.js";
import * as cc from "../charts/country.js";
import { h } from "../lib/dom.js";
import { asMap, asRows, countryBrief, na, redFlags } from "../lib/scoring.js";
import { AUDIENCES, countryReading, readingMarkdown } from "../lib/interpret.js";
import { fixed, signed } from "../lib/format.js";
import { countryTable, flagUrl } from "../lib/table.js";

export const title = "Country profile";
export const required = ["data/country/NGA.json", "data/events.json", "data/flows.json", "files/briefs/NGA.pdf"];

const LAST = "sg-country"; // sessionStorage (app.js): the country opened last in this visit
const COMPARE = "sg-compare"; // sessionStorage: the countries added with "Add to compare" (ui.COMPARE_LIST)
const TABS = { summary: "Summary", assessment: "Assessment", peers: "Peers", whatif: "What-if", data: "Data", news: "News" };
const PEERS_VIEWS = { ranking: "Ranking", map: "Map & refugees" };
const DATA_VIEWS = { indicators: "Indicators", governance: "Governance", economy: "Economy" };
// links made before the tabs were merged: ?tab=map opens Peers on its map, ?tab=real the Summary's real-life reading
const OLD_TABS = { map: "peers", indicators: "data", governance: "data", economy: "data" };
const whatifState = new Map(); // per country, for this visit (the app keeps the sliders in its session)

// st.header: the app hides header help (prm/ui.py GLOBAL_CSS hides stHeaderActionElements), so none is drawn
const h2 = (text) => h("h2", null, text);
const h4 = (text) => h("h4", null, text);
const md = (text) => { const el = h("div", { class: "sg-cp-md" }); el.innerHTML = cc.markdown(text); return el; }; // escaped by cc.markdown
// st.page_link with an icon the vendored set lacks (drawn from country.css)
const link = (href, label, icon) => h("a", { class: "sg-page-link", href }, h("span", { class: `sg-icon sg-cp-i-${icon}`, "aria-hidden": "true" }), h("span", null, label));
const join = (items, sep = " · ") => items.flatMap((x, i) => (i ? [sep, x] : [x]));
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };

function read(key, fallback) {
  try { return JSON.parse(sessionStorage.getItem(key) ?? "null") ?? fallback; } catch { return fallback; }
}
function write(key, value) {
  try { sessionStorage.setItem(key, JSON.stringify(value)); } catch { /* storage blocked */ }
}

// ui.current_country: ?country=, else the country opened last in this visit, else the first followed (chosen: the
// visitor picked it); otherwise Nigeria is shown but not tracked, and the address is left alone
function pick(ctx, names) {
  let last = null;
  try { last = sessionStorage.getItem(LAST); } catch { /* storage blocked */ }
  for (const c of [ctx.params.get("country"), last, follow.following()[0]]) {
    const code = c ? String(c).toUpperCase() : null;
    if (code && names.has(code)) return { iso3: code, chosen: true };
  }
  return { iso3: names.has("NGA") ? "NGA" : names.keys().next().value, chosen: false };
}

// st.toast
function toast(text) {
  const el = h("div", { class: "sg-cp-toast", role: "status" }, h("span", null, text));
  document.body.append(el);
  setTimeout(() => el.remove(), 4000);
}

export async function render(main, ctx) {
  await ui.loadCss("/css/country.css");
  main.classList.add("sg-cp");
  const countries = asRows(ctx.core.countries);
  const names = new Map(countries.map((c) => [c.iso3, c.name]));
  const options = [...names.keys()].sort((a, b) => (names.get(a) < names.get(b) ? -1 : names.get(a) > names.get(b) ? 1 : 0));
  const { iso3, chosen } = pick(ctx, names);
  if (chosen && ctx.params.get("country") !== iso3) ctx.setParam("country", iso3);
  const cleanups = [];
  const drop = () => cleanups.splice(0).forEach((fn) => { try { fn(); } catch (err) { console.warn("country cleanup", err); } });
  const body = h("div", { class: "sg-stack" });
  const draw = (code) => {
    drop();
    const box = h("div", { class: "sg-stack" });
    body.replaceChildren(box);
    return profile(box, ctx, code, names, countries, cleanups);
  };
  const picker = ui.select({ label: "Country", options, value: iso3, format: (i) => names.get(i) ?? i,
    onChange: (code) => { ctx.setParam("country", code); draw(code); } });
  picker.classList.add("sg-country-pick");
  main.append(...[ui.weightsNote(ctx), picker, body].filter(Boolean));
  await draw(iso3);
  return drop;
}

// Everything under the picker, for one country
async function profile(el, ctx, iso3, names, countries, cleanups) {
  const config = ctx.core.config, year = ctx.core.meta.year;
  const table = asRows(ctx.table()), scores = ctx.scores(), values = ctx.core.values;
  const row = table.find((r) => r.iso3 === iso3), s = scores.get(iso3), v = asMap(values).get(iso3) ?? {};
  const name = names.get(iso3);
  document.title = `${name} · ${config.APP_TITLE}`;
  let prof = null;
  try {
    prof = await ctx.fetchJSON(`/data/country/${iso3}.json`);
  } catch (err) {
    console.warn("section failed: the country file", err); // its sections show their empty state
  }
  if (!el.isConnected) return;
  const plotInto = (box, fig, opts) => { const div = h("div", { class: "sg-cp-chart" }); box.append(div); cleanups.push(charts.plot(div, fig, opts)); return div; };
  const flags = [...redFlags(v, config), ...(prof?.stability_flags ?? [])]; // most severe first
  const hasAssessment = row.assessment === "✓";

  // --- header and actions ---------------------------------------------------------------------------------
  let tabs = null;
  el.append(ui.countryHeader(name, row, row.delta_1y, year,
    h("span", null, flags.length ? [ui.sevMark(flags[0].severity), `${flags[0].short ?? flags[0].label} · `] : null, cc.headerMeta(row, v, s, config)),
    { analystRating: hasAssessment ? row.analyst_rating || null : null,
      onAnalyst: () => { tabs?.select("assessment"); el.querySelector(".sg-tablist")?.scrollIntoView({ block: "nearest" }); } }));

  const actions = h("div", { class: "sg-country-actions" });
  const compareList = () => [...new Set(read(COMPARE, []).filter((i) => names.has(i)))];
  const openCompare = () => ctx.go("/compare", { c: compareList().join(",") });
  const drawActions = () => {
    const list = compareList();
    let compare;
    if (list.includes(iso3)) {
      compare = ui.button(`Open comparison (${list.length})`, { icon: "compare_arrows", help: `${name} is in your comparison`, onClick: openCompare });
    } else if (list.length >= config.MAX_COMPARE) {
      compare = ui.button("Comparison is full", { disabled: true,
        help: `You can compare up to ${config.MAX_COMPARE} countries. Remove one on the Compare page.` });
    } else {
      compare = ui.button("Add to compare", { onClick: () => {
        write(COMPARE, [...list, iso3]);
        toast(`${name} added to your comparison`);
        drawActions();
        actions.firstElementChild?.focus(); // the button is redrawn as "Open comparison": keep the keyboard on it
      } });
    }
    const pdf = ui.download("Download PDF brief", { href: `/files/briefs/${iso3}.pdf?v=${encodeURIComponent(ctx.core.meta.version ?? "")}`, filename: `${iso3}_risk_brief_${year}.pdf`,
      mime: "application/pdf", icon: null });
    pdf.title = "A one-page brief: score, pillars, trend, red flags and what it means in real life.";
    const others = list.length && !list.includes(iso3)
      ? ui.pageLink(`/compare?c=${list.join(",")}`, `Open comparison (${list.length})`, "compare_arrows") : null;
    actions.replaceChildren(...[compare, pdf, follow.followButton(iso3, name), others].filter(Boolean));
  };
  drawActions();
  el.append(actions);
  if (ctx.customLabel()) el.append(ui.caption("The PDF brief uses the default weights."));

  // --- tabs ------------------------------------------------------------------------------------------------
  const asked = ctx.params.get("tab");
  let realLife = false;
  if (asked === "real") { ctx.setParam("tab", "summary"); realLife = true; }
  else if (OLD_TABS[asked]) { ctx.setParam("tab", OLD_TABS[asked]); ctx.setParam("view", asked); }
  const order = hasAssessment ? TABS : (({ assessment, ...rest }) => ({ ...rest, assessment }))(TABS); // no assessment: its empty state goes last
  tabs = ui.urlTabs(el, order, ctx);
  if (!["peers", "data"].includes(tabs.open)) ctx.setParam("view", null); // ?view belongs to those two tabs

  // a view's content is redrawn when the view changes: what it drew is released first
  const views = (panel, label, list, draw) => {
    const view = ui.urlView(panel, label, list, ctx);
    const box = h("div", { class: "sg-stack" });
    panel.append(box);
    let mine = [];
    cleanups.push(() => mine.splice(0).forEach((fn) => fn()));
    view.on((slug) => {
      mine.splice(0).forEach((fn) => fn());
      box.replaceChildren(ui.guard(list[slug], (inner) => { inner.classList.add("sg-stack"); return draw(slug, inner, mine); }));
    });
  };

  // --- Summary -------------------------------------------------------------------------------------------------
  tabs.on("summary", (p) => {
    p.append(h2("Risk over time"));
    const countryHist = asRows(ctx.history()).filter((r) => r.iso3 === iso3).sort((a, b) => a.year - b.year);
    if (countryHist.filter((r) => !na(r.composite)).length >= 2) {
      plotInto(p, charts.riskHistory(countryHist, true));
      p.append(ui.caption(`${year} uses IMF estimates.`, ui.sr(` ${charts.historySummary(countryHist)}`)));
    } else p.append(ui.emptyState("Not enough history to draw a trend for this country."));

    const left = h("div", { class: "sg-stack" }, h2("What the data says"),
      h("ul", { class: "sg-cp-brief" }, countryBrief(iso3, name, values, scores, ctx.core.countries, year,
        { wgiTrend: ctx.core.wgiTrend?.[iso3] ?? null, nextGrowth: prof?.next_growth ?? null, config }).map((line) => h("li", null, line))));
    const right = h("div", { class: "sg-stack" });
    if (prof?.outlook) {
      right.append(h2("Conflict outlook"), h("p", null, prof.outlook.level ? ui.sevMark(prof.outlook.level, false) : null, prof.outlook.text),
        link("/conflict?tab=outlook", "How this is estimated", "insights"));
    }
    right.append(h2("Red flags"));
    if (flags.length) {
      const sorted = flags.map((f, i) => [f, i]).sort((a, b) => config.SEVERITY_ORDER[a[0].severity] - config.SEVERITY_ORDER[b[0].severity] || a[1] - b[1]);
      right.append(...sorted.map(([f]) => h("p", null, ui.sevMark(f.severity, false), `${config.SEVERITY_LABEL[f.severity]}: ${f.label}`)));
    } else right.append(h("p", null, "No absolute warning thresholds crossed."));
    right.append(h2("Upcoming events"), ui.guard("Upcoming events", async (box) => {
      const events = await ctx.fetchJSON("/data/events.json");
      box.append(ui.upcomingEvents(asRows(events).filter((e) => e.iso3 === iso3).map((e) => ({ ...e, country: name })), { limit: 5 }));
    }), link("/hotspots?tab=calendar", "Event calendar", "event"));
    p.append(h("div", { class: "sg-row sg-country-cols" }, left, right));

    const real = ui.expander("What it means in real life", { expanded: realLife });
    let readingDrawn = false;
    const buildReading = () => {
      if (readingDrawn) return;
      readingDrawn = true;
      real.body.append(ui.guard("The real-life reading", async (box) => {
        box.classList.add("sg-stack");
        const [events, flows] = await Promise.all([ctx.fetchJSON("/data/events.json"), ctx.fetchJSON("/data/flows.json")]);
        const reading = countryReading(iso3, ctx.table(), values, ctx.scores(), ctx.history(), {
          events: asRows(events).filter((e) => e.iso3 === iso3), flows: asRows(flows).filter((f) => f.origin === iso3),
          year, today: today(), wgiTrend: ctx.core.wgiTrend?.[iso3] ?? null, config });
        renderReading(box, reading);
        box.append(ui.pageLink("/guide", "Guide: reading the numbers", "explore"));
      }));
    };
    real.addEventListener("toggle", () => { if (real.open) buildReading(); });
    if (realLife) buildReading();
    p.append(real);

    p.append(h2("Pillar scores"));
    plotInto(p, charts.pillarBars(s, cc.regionalMedian(table, row.region, config)));
    const sens = ui.expander("Sensitivity to the weights");
    sens.addEventListener("toggle", () => {
      if (!sens.open || sens.dataset.built) return;
      sens.dataset.built = "1";
      const box = h("div", { class: "sg-cp-sens" });
      countryTable(box, cc.sensitivityRows(values, iso3, ctx.weights(), config), { key: "Scenario", columns: [
        { key: "Scenario", label: "Scenario" },
        { key: "Score", label: "Score", fmt: (x) => fixed(x, 1) },
        { key: "Rank", label: "Rank", fmt: (x) => String(Math.trunc(x)) }] });
      sens.body.append(box, ui.caption("If the rank barely moves when a pillar is dropped, the result does not hinge on that choice. Large swings show which pillar drives the score."));
    });
    p.append(sens, ui.cite(["index", "ucdp_def", "imf_ara", "ifes"]));
  });

  // --- Peers -----------------------------------------------------------------------------------------------------
  tabs.on("peers", (p) => views(p, "Peers view", PEERS_VIEWS, (slug, box, mine) => (slug === "map" ? peerMap(box, mine) : peerRanking(box))));

  function peerRanking(box) {
    const groups = cc.peerGroups(table, row);
    const labels = Object.keys(groups);
    const out = h("div", { class: "sg-stack" });
    const shown = [];
    const draw = (label) => {
      shown.splice(0).forEach((fn) => fn());
      out.replaceChildren();
      const r = cc.peerRanking(groups[label], iso3, name, s.composite);
      if (r.place) out.append(h("p", null, r.place, ui.sr(r.sr)));
      const div = h("div", { class: "sg-cp-chart" });
      out.append(div);
      shown.push(charts.plot(div, charts.peerStrip(s, groups[label].filter((x) => x.iso3 !== iso3), name)));
      out.append(ui.cite(["index", "wb_countries"]), h2("Peer ranking"));
      out.append(rankTable(r.rows, config, { extra: [{ key: "group_rank", label: "Group rank", fmt: (x) => String(x), align: "right" }] }));
      out.append(ui.caption(r.caption));
      out.append(h2("Most similar risk profiles"));
      const like = cc.similarRows(scores, iso3, config);
      if (!like.length) out.append(ui.caption("Not enough data to compare profiles."));
      else {
        const byIso = new Map(table.map((t) => [t.iso3, t]));
        out.append(rankTable(like.map((l) => ({ ...byIso.get(l.iso3), closeness: l.closeness })), config, {
          extra: [{ key: "closeness", label: "Similarity", fmt: (x) => bar(x, config.INK.accent) }] })); // closest first; the theme colour, as an uncoloured st ProgressColumn
      }
    };
    cleanups.push(() => shown.splice(0).forEach((fn) => fn()));
    box.append(ui.segmented({ label: "Compare with", options: labels, value: labels[0], onChange: draw }), out);
    draw(labels[0]);
  }

  async function peerMap(box, mine) {
    const flows = await ctx.fetchJSON("/data/flows.json").catch((err) => { console.warn("section failed: refugee flows", err); return null; });
    if (!box.isConnected) return;
    const globe = h("div");
    box.append(globe);
    const handle = await ui.globePanel(globe, ctx, { table: ctx.table(), hist: ctx.history(), flows, metric: "composite",
      metricLabel: "Composite", key: `profile_globe_${iso3}`, focus: iso3, height: 520, layers: { spin: false, flows: true, conflict: true },
      hint: `Arcs = refugees from or hosted by ${name} · ▶ replays since ${config.HISTORY_START}`,
      fallback: flows?.rows?.length ? null : "Everything else on the page still works." });
    if (handle) {
      if (!box.isConnected) { handle.destroy(); return; }
      mine.push(() => handle.destroy());
    }
    box.append(ui.cite(["unhcr", "ucdp", "natural_earth"]));
    if (!flows?.rows?.length) return;
    const lists = cc.flowLists(flows, names, iso3);
    const cols = [["origin", `Where refugees from ${name} are`, config.INK.worse, `people from ${name}`],
      ["host", `Who ${name} hosts`, config.INK.better, "people hosted"]].map(([side, heading, colour, hover]) => {
      const col = h("div", { class: "sg-stack" }, h2(heading));
      const list = lists[side];
      if (!list.rows.length) col.append(ui.caption(`No recorded flows (${lists.year}).`));
      else {
        const div = h("div", { class: "sg-cp-chart" });
        col.append(div, ui.caption(list.total));
        mine.push(charts.plot(div, charts.rankedBars(list.rows, "value", "name", colour, hover), {
          onClick: (point) => { const code = charts.clickedIso3(point); if (code) ctx.go("/country", { country: code }); } }));
      }
      return col;
    });
    box.append(h("div", { class: "sg-pair" }, h("div", { class: "sg-row" }, cols)));
  }

  // --- What-if ---------------------------------------------------------------------------------------------------
  tabs.on("whatif", (p) => {
    p.append(h2("What-if simulator"));
    if (!prof) { p.append(ui.emptyState("The What-if simulator can't be shown right now. The rest of the page is unaffected.")); return; }
    whatif(p, prof.whatif);
  });

  function whatif(p, { controls, missing }) {
    if (!whatifState.has(iso3)) whatifState.set(iso3, { values: {}, picked: null, opened: new Set() });
    const st = whatifState.get(iso3);
    const valueOf = (c) => st.values[c.key] ?? c.current;
    const presets = Object.keys(cc.WHATIF_PRESETS).map((preset) => ui.button(preset, {
      type: st.picked === preset ? "primary" : "secondary",
      onClick: () => { st.values = cc.applyPreset(preset, controls); st.picked = preset; st.opened = new Set(); sync(); } }));
    const reset = ui.button("Reset indicators", { onClick: () => { st.values = {}; st.picked = null; st.opened = new Set(); sync(); } });
    reset.prepend(h("span", { class: "sg-icon sg-cp-i-restart", "aria-hidden": "true" }));
    p.append(h("div", { class: "sg-row sg-row-tight sg-whatif-presets" }, presets, reset));

    const live = h("div", { class: "sg-whatif-live", "aria-hidden": "true" });
    const left = h("div", { class: "sg-stack sg-whatif-controls" }, live);
    const right = h("div", { class: "sg-stack sg-whatif-results" });
    p.append(h("div", { class: "sg-whatif-split" }, h("div", { class: "sg-whatif-cols" }, left, right)));
    const widgets = new Map(), panels = new Map();
    const set = (c, value) => {
      st.values[c.key] = value;
      if (value !== c.current && !st.opened.has(c.pillar)) { st.opened.add(c.pillar); panels.get(c.pillar).open = true; }
      results();
    };
    config.pillars.forEach((pillar, i) => {
      const mine = controls.filter((c) => c.pillar === pillar.key);
      if (!mine.length) return;
      if (mine.some((c) => valueOf(c) !== c.current)) st.opened.add(pillar.key);
      const panel = ui.expander(pillar.label, { expanded: i === 0 || st.opened.has(pillar.key) });
      panel.dataset.first = i === 0 ? "1" : "";
      for (const c of mine) {
        const w = c.kind === "select"
          ? ui.slider({ label: c.label, min: 0, max: c.options.length - 1, step: 1, value: Math.max(0, c.options.indexOf(valueOf(c))),
            format: (k) => fixed(c.options[k], 0, { group: true }), onChange: (k) => set(c, c.options[k]) })
          : ui.slider({ label: c.label, min: c.min, max: c.max, step: 0.1, value: valueOf(c), format: (x) => fixed(x, 1), help: c.help,
            onChange: (x) => set(c, Math.round(x * 10) / 10) });
        widgets.set(c.key, w);
        panel.body.append(w);
      }
      panels.set(pillar.key, panel);
      left.append(panel);
    });
    if (missing.length) left.append(ui.caption(`No data to simulate: ${missing.join(", ")}`));

    function sync() { // after a preset or a reset: sliders, open pillars and the picked button follow the state
      for (const c of controls) {
        const w = widgets.get(c.key);
        w.value = c.kind === "select" ? c.options.indexOf(valueOf(c)) : valueOf(c);
        if (valueOf(c) !== c.current) st.opened.add(c.pillar);
      }
      for (const [key, panel] of panels) panel.open = panel.dataset.first === "1" || st.opened.has(key);
      presets.forEach((b) => {
        const on = b.textContent === st.picked;
        b.classList.toggle("sg-btn-primary", on);
        b.classList.toggle("sg-btn-secondary", !on);
      });
      results();
    }

    let unplot = null;
    function results() {
      unplot?.();
      unplot = null;
      right.replaceChildren();
      if (na(s.composite)) {
        live.hidden = true;
        right.append(ui.emptyState(`${name} has too little data for a composite score, so there is nothing to simulate.`));
        return;
      }
      const r = cc.whatifResult(values, s, ctx.weights(), iso3, name, controls, st.values, st.picked, config);
      live.replaceChildren(h("span", null, `Score ${r.score_value}${r.score_change ? ` (${r.score_change})` : ""} · Rank ${r.rank}`), ui.tierBadge(r.tier));
      const rank = ui.metric({ label: `Global rank (of ${r.n_ranked})`, value: String(r.rank), help: "1 = highest risk, so a smaller number means riskier." });
      if (r.places) { // red and up when riskier, green and down when safer (the rank number itself falls)
        rank.append(h("div", { class: "sg-metric-delta" }, h("span", { class: `sg-delta sg-delta-${r.riskier ? "worse" : "better"}` },
          h("span", { "aria-hidden": "true" }, r.riskier ? "↑ " : "↓ "), r.places)));
      }
      right.append(h("div", { class: "sg-kpis" },
        ui.metric({ label: "Composite score (of 100)", value: r.score_value, delta: r.score_change, deltaColor: "inverse" }), rank));
      right.append(h("p", { class: "sg-whatif-tier" }, "Risk tier  ", ui.tierBadge(r.tier), r.was ? h("span", { class: "sg-cp-was" }, ` was ${r.was}`) : null));
      const div = h("div", { class: "sg-cp-chart" });
      right.append(div);
      unplot = charts.plot(div, charts.whatifPillars(s, r.scenario));
      right.append(ui.cite("index"));
      if (r.flags.length || r.cleared.length) {
        right.append(h("p", { class: "sg-strong" }, "Red flags in this scenario"),
          ...r.flags.map((f) => h("p", null, ui.sevMark(f.severity), `New: ${f.label}`)),
          ...r.cleared.map((label) => h("p", null, `Cleared: ${label}`)));
      }
      if (r.caption) right.append(ui.caption(r.caption));
    }
    cleanups.push(() => unplot?.());
    results();
  }

  // --- Data ------------------------------------------------------------------------------------------------------
  tabs.on("data", (p) => views(p, "Data view", DATA_VIEWS, (slug, box, mine) => {
    if (slug === "governance") governance(box, mine);
    else if (slug === "economy") economy(box, mine);
    else indicators(box);
  }));

  function indicators(box) {
    box.append(h2("Every indicator behind the score"));
    const rows = cc.indicatorRows(v, s, config);
    const wrap = h("div", { class: "sg-cp-indicators" });
    countryTable(wrap, rows, { key: "Indicator", height: "640px", columns: [
      { key: "Indicator", label: "Indicator" },
      { key: "Value", label: "Value", align: "right" },
      { key: "Risk score", label: "Risk score", fmt: (x) => bar(x, config.INK.accent) },
      { key: "Year", label: "Year" },
      { key: "Pillar", label: "Pillar" },
      { key: "Unit", label: "Unit" },
      { key: "Source", label: "Source" },
      { key: "Data", label: "Data", fmt: (url) => h("a", { href: url, target: "_blank", rel: "noopener" }, "Open ↗") },
    ] });
    wrap.querySelector("th:nth-child(3)")?.setAttribute("title", "Position relative to all other countries (0–100). Battle deaths and displacement use a log scale so that countries without conflict score 0.");
    box.append(wrap, ui.cite("index"));
    const cross = ui.expander(`Cross-check ${name} with independent sources`, {},
      ui.caption("Indices that measure similar things but are not used in the score."));
    for (const [pillar, keys] of Object.entries(config.CROSS_CHECKS)) {
      cross.body.append(h("p", null, pillar === "composite" ? h("strong", null, "Overall fragility") : ui.pillarChip(pillar), "  ",
        join(keys.map((k) => ui.sourceLink(k, config.SOURCES[k].name)))));
    }
    cross.body.append(ui.pageLink("/sources", "All sources and cross-checks", "verified"));
    box.append(cross, h("div", null, ui.download("Download indicators (CSV)", { icon: null, mime: "text/csv", filename: `${iso3}_indicators_${year}.csv`,
      data: () => String.fromCharCode(0xfeff) + cc.indicatorsCsv(v, s, name, iso3, config) }))); // with the byte-order mark, as utf-8-sig
  }

  function governance(box, mine) {
    box.append(h2("Governance over time"));
    if (!prof) { box.append(ui.emptyState("The governance charts can't be shown right now. The rest of the page is unaffected.")); return; }
    const div = h("div", { class: "sg-cp-chart" });
    box.append(div, ui.cite("wgi"));
    mine.push(charts.plot(div, prof.figures.wgi));
    const t = prof.governance;
    if (!t) return;
    const wrap = h("div", { class: "sg-cp-gov" });
    countryTable(wrap, asRows(t), { key: "Dimension", columns: t.columns.map((c) => ({ key: c, label: c,
      ...(c.startsWith("Score ") ? { fmt: (x) => fixed(x, 1) } : c === "Change" ? { fmt: (x) => signed(x) } : {}) })) });
    box.append(wrap);
  }

  function economy(box, mine) {
    const edition = ctx.core.meta.series?.gdp_growth?.edition || "IMF World Economic Outlook";
    box.append(h2("Macroeconomic picture"), ui.caption(`Dashed lines are IMF projections (${edition}).`));
    if (prof) {
      const div = h("div", { class: "sg-cp-chart" });
      box.append(div);
      mine.push(charts.plot(div, prof.figures.macro));
    } else box.append(ui.emptyState("The IMF charts can't be shown right now. The rest of the page is unaffected."));
    box.append(ui.cite(["imf", "wdi", "unhcr"]));
    const ind = new Map(config.indicators.map((i) => [i.key, i]));
    box.append(h("div", { class: "sg-kpis" }, [
      ["reserves_months", "FX reserves (months of imports)", "World Bank WDI. Below 3 months is a common warning line."],
      ["youth_unemployment", "Youth unemployment (%)", null],
      ["displaced_share", "Displaced (% of population)", "Refugees, asylum seekers, others in need of protection and IDPs from this country (UNHCR)."],
    ].map(([key, label, help]) => {
      const raw = v[key];
      const m = ui.metric({ label, value: na(raw) ? "No data" : fixed(raw, ind.get(key).decimals, { group: true }), help });
      if (na(raw)) m.classList.add("sg-cp-nodata"); // a missing figure reads "No data" in small grey, not a big dash
      return m;
    })));
  }

  // --- News --------------------------------------------------------------------------------------------------------
  tabs.on("news", (p) => {
    const newsName = prof?.news_name ?? name;
    p.append(h2("Risk-related news, last 7 days"));
    const news = h("div");
    p.append(news);
    ctx.fetchJSON(`/data/news/${iso3}.json`)
      .then((n) => news.append(ui.newsList({ articles: n.items, source: n.source, fetched: built(n.fetched) }, { limit: 20 })))
      .catch(() => news.append(ui.newsList(null)));
    p.append(ui.guard("Video reports", async (box) => {
      box.classList.add("sg-stack");
      box.append(h2(`Video reports on ${name}`));
      const all = await ctx.fetchJSON("/data/videos.json").catch(() => null); // no file: the same line as no match
      const official = countries.find((c) => c.iso3 === iso3)?.official_name ?? null;
      const about = all ? cc.videosAbout(all.items, iso3, names, newsName, official, all.aliases?.[iso3] ?? []) : [];
      box.append(about.length ? ui.videoGallery(about, { limit: 6 }) : ui.caption(`None of the latest videos mention ${name}.`),
        ui.pageLink("/video", "Live TV and all video reports", "live_tv"));
    }));
    p.append(gdelt("tone", "Media tone, last 3 months (GDELT)",
      "GDELT average tone of English-language coverage. A sustained fall often precedes or accompanies crises.",
      "GDELT's tone data isn't available right now. It is refreshed every week.", "No tone data returned."));
    p.append(gdelt("protests", "Protest coverage, last 3 months (GDELT)",
      `Share of all English-language news GDELT monitors that mentions ${name} together with protests, riots, strikes or unrest, smoothed over a week.`,
      "GDELT's protest data isn't available right now. It is refreshed every week.", "No protest coverage found."));
    p.append(ui.cite(["news", "gdelt", "youtube"]));
  });

  // A GDELT chart behind a toggle (built every week: data/gdelt/<ISO3>.json)
  function gdelt(key, label, help, missingText, emptyText) {
    const out = h("div", { class: "sg-stack" });
    let unplot = null;
    const show = async (on) => {
      unplot?.();
      unplot = null;
      out.replaceChildren();
      if (!on) return;
      let file = null;
      try { file = await ctx.fetchJSON(`/data/gdelt/${iso3}.json`); } catch (err) { console.warn(`section failed: GDELT ${key}`, err); }
      if (!out.isConnected || !toggle.value) return;
      if (!file) out.append(ui.emptyState(missingText));
      else if (!file[key]) out.append(ui.emptyState(emptyText));
      else { const div = h("div", { class: "sg-cp-chart" }); out.append(div); unplot = charts.plot(div, file[key]); }
    };
    const toggle = ui.toggle({ label, help, onChange: show });
    cleanups.push(() => unplot?.());
    return h("div", { class: "sg-stack" }, toggle, out);
  }

  // --- Assessment ----------------------------------------------------------------------------------------------------
  tabs.on("assessment", async (p) => {
    if (!hasAssessment) {
      p.append(ui.emptyState(`No analyst assessment for ${name} yet.`),
        h("p", null, "Write one in the Assessment builder and add the file to the project's ", h("code", { class: "sg-cp-code" }, "assessments/"), " folder."),
        ui.pageLink("/builder", "Open the assessment builder", "edit_note"));
      return;
    }
    let a;
    try { a = await ctx.fetchJSON(`/data/assessments/${iso3}.json`); } catch (err) {
      console.warn("section failed: the assessment", err);
      p.append(ui.emptyState("The analyst assessment can't be shown right now. The rest of the page is unaffected."));
      return;
    }
    const m = a.meta ?? {};
    p.append(h("div", { class: "sg-row sg-cp-assess" },
      h("div", { class: "sg-stack sg-cp-rating" }, h("strong", null, "Analyst rating"), h("div", null, ui.tierBadge(m.analyst_rating))),
      ui.metric({ label: "Outlook", value: m.outlook || "—" }), ui.metric({ label: "Confidence", value: m.confidence || "—" }),
      ui.metric({ label: "Written", value: m.date || "—" })));
    const order = config.tiers.map((t) => t.label);
    const model = s.tier, analyst = m.analyst_rating;
    if (order.includes(model) && order.includes(analyst) && model !== analyst) {
      const gap = order.indexOf(analyst) - order.indexOf(model);
      p.append(ui.callout("info", h("span", null, `The analyst rates ${name} ${Math.abs(gap)} tier${Math.abs(gap) > 1 ? "s" : ""} ${gap > 0 ? "higher" : "lower"} than the model (${model}). The reasoning is under `,
        h("em", null, "Why my rating differs from the model"), ".")));
    }
    p.append(ui.caption(`By ${m.author || "the analyst"} · horizon ${m.horizon || "—"}`), h("hr"), md(a.body));
  });

  // --- under the tabs --------------------------------------------------------------------------------------------------
  const source = (k) => h("a", { href: config.SOURCES[k].url, target: "_blank", rel: "noopener" }, config.CITE_LABELS[k] ?? config.SOURCES[k].name);
  el.append(h("p", { class: "sg-caption" }, "Region, income, population and GDP: ", join(["wb_countries", "wdi", "imf"].map(source)),
    prof ? [h("br"), "Elsewhere: ", join(prof.elsewhere.map(([label, url]) => h("a", { href: url, target: "_blank", rel: "noopener" }, `${label} ↗`)))] : null));
  el.append(ui.footer());
}

// The build time of a scheduled file, where the app showed the time it fetched ("2026-11-25 06:00 UTC")
const built = (iso) => (iso ? `${String(iso).slice(0, 16).replace("T", " ")} UTC` : "recently");

// A score as Streamlit's progress column draws it: a bar and the whole number
function bar(x, colour) {
  return h("span", { class: "sg-cp-progress" }, h("span", { class: "sg-cp-bar", style: `--p:${Math.max(0, Math.min(100, x))}%;--c:${colour}` }),
    h("span", { class: "sg-cp-num" }, fixed(x, 0)));
}

// ui.country_table: name, extra columns, composite, change, flag, tier, global rank and the pillars (scores as bars).
// rows come in the order to show (sorting is the visitor's, by the column heads)
function rankTable(rows, config, { extra = [] } = {}) {
  const box = h("div", { class: "sg-cp-ranks" });
  const top = config.tiers[config.tiers.length - 1].label;
  countryTable(box, rows, { tiers: config.tiers.slice(config.tiers.findIndex((t) => t.label === "Elevated")),
    noFlag: config.NO_FLAG,
    extra: (tr, r) => { if (r.tier === top) tr.querySelector(".sg-cell-tier")?.classList.add("sg-cp-tier-top"); },
    columns: [
      { key: "name", label: "Country", fmt: (n, r) => h("a", { class: "sg-row-link", href: `/country?country=${encodeURIComponent(r.iso3)}` }, n) },
      ...extra,
      { key: "composite", label: "Composite", fmt: (x) => bar(x, config.INK.soft) },
      { key: "trend", label: "1-yr change", align: "right" },
      { key: "iso2", label: " ", fmt: (code) => { const url = flagUrl(code, config.NO_FLAG); return url ? h("img", { class: "sg-flag", src: url, alt: "" }) : ""; } },
      { key: "tier", label: "Tier", type: "tier" },
      { key: "rank", label: "Global rank", fmt: (x) => String(Math.trunc(x)), align: "right" },
      ...config.pillars.map((p) => ({ key: p.key, label: p.short, fmt: (x) => bar(x, config.PILLAR_COLORS[p.key]) })),
    ] });
  return box;
}

// ui.render_reading: a country's numbers in real life (on the ground, warning signs, direction, what to do)
function renderReading(box, r) {
  box.append(h("p", null, ui.tierBadge(r.tier), "  ", r.headline));
  if (r.tier === null) { box.append(ui.emptyState(r.ground)); return; }
  const left = h("div", { class: "sg-stack" }, h4("What it looks like on the ground"), md(r.ground),
    r.drivers.map((d) => h("div", { class: "sg-card" }, h("div", null, ui.pillarChip(d.pillar, `${d.label} · ${fixed(d.score, 0)}/100`)), md(d.ground),
      d.evidence.length ? ui.caption(`Driven by ${d.evidence.join("; ")}.`) : null, ui.caption(`Felt first by: ${d.felt_by}`))));
  const right = h("div", { class: "sg-stack" }, h4("Warning signs right now"));
  if (r.warnings.length) {
    for (const w of r.warnings) right.append(h("p", null, ui.sevMark(w.severity), h("strong", null, w.label), h("br"), w.meaning), ui.caption(`Typical response: ${w.response}`));
  } else right.append(h("p", null, "No absolute warning thresholds crossed."));
  const list = (items) => md(items.map((x) => `- ${x}`).join("\n"));
  if (r.near.length) right.append(h4("Close to a red line"), list(r.near));
  if (r.direction.length) right.append(h4("Direction"), list(r.direction));
  right.append(h4("Coming up"), r.events.length ? list(r.events) : ui.caption("No events on the calendar for the next 12 months."));
  box.append(h("div", { class: "sg-row sg-cp-reading" }, left, right));

  // What to do with it: plain tabs (not kept in the address)
  box.append(h4("What to do with it"));
  const keys = Object.keys(AUDIENCES);
  const list2 = h("div", { class: "sg-tablist", role: "tablist" });
  const panels = keys.map((k) => h("div", { class: "sg-tabpanel", role: "tabpanel", tabindex: "0", hidden: true }, list((r.actions[k] ?? []))));
  const buttons = keys.map((k, i) => h("button", { type: "button", role: "tab", class: "sg-tab", onclick: () => select(i) }, AUDIENCES[k]));
  const select = (i, focus = false) => {
    buttons.forEach((b, j) => { b.setAttribute("aria-selected", String(i === j)); b.tabIndex = i === j ? 0 : -1; panels[j].hidden = i !== j; });
    if (focus) buttons[i].focus();
  };
  list2.addEventListener("keydown", (e) => {
    const i = buttons.indexOf(document.activeElement);
    const step = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
    if (i < 0 || !step) return;
    e.preventDefault();
    select((i + step + keys.length) % keys.length, true);
  });
  list2.append(...buttons);
  select(0);
  box.append(h("div", { class: "sg-tabs" }, list2, ...panels));
  box.append(h("div", null, ui.download("Download reading (Markdown)", { icon: null, mime: "text/markdown", filename: `${r.iso3}_real_life_reading.md`,
    data: () => readingMarkdown(r) })), ui.caption(r.caveats.join(" ")));
}
