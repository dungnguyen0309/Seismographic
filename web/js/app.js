// The shell: loads the core data, draws the sidebar, the bottom dock with Find, the weights panel, and the page for
// the address (js/pages/<route>.js) inside an error boundary. Navigation uses pushState; links stay real <a href>.
import { h } from "./lib/dom.js";
import { ROUTES, route, makeCtx, weightsShares } from "./lib/ctx.js";
import * as ui from "./lib/ui.js";
import * as follow from "./lib/follow.js";
import { asRows, defaultWeights, na } from "./lib/scoring.js";
import { fixed, pyRound, signed, trendLabel } from "./lib/format.js";
import { flagUrl } from "./lib/table.js";
import { setConfig as setChartsConfig } from "./lib/charts.js"; // config only: plotly loads when a page plots

const APP = "Seismographic";
const CORE = { meta: "meta", config: "config", countries: "countries", values: "values", scores: "scores", history: "history",
  master: "master", wgiTrend: "wgi_trend" };
const DOCK_TABS = [["/", "Home", "public"], ["/compare", "Compare", "compare_arrows"], ["/video", "Live", "live_tv"], ["/guide", "Guide", "lightbulb"]];
const WIDE = "(min-width: 768px)"; // the sidebar sits beside the page from here up and over it below
const LAST = "sg-country"; // sessionStorage: the country opened last in this visit (the dock follows it)

const main = document.getElementById("main");
const side = document.getElementById("sidebar");
const top = document.getElementById("topbar");
const dock = document.getElementById("dock");
let ctx = null;

// ---- boot -------------------------------------------------------------------------------------------------------
async function loadCore() {
  const get = (file) => fetch(`/data/${file}.json`).then((r) => {
    if (!r.ok) throw new Error(`${r.status} /data/${file}.json`);
    return r.json();
  });
  const all = async () => Object.fromEntries(await Promise.all(Object.entries(CORE).map(async ([k, f]) => [k, await get(f)])));
  try {
    return await all();
  } catch {
    await new Promise((r) => setTimeout(r, 1000));
    return all(); // one retry
  }
}

async function boot() {
  drawSidebar(null);
  drawTopbar();
  let core;
  try {
    core = await loadCore();
  } catch (err) {
    console.warn("core data failed", err);
    document.title = APP;
    main.replaceChildren(h("div", { class: "sg-page" },
      ui.callout("error", "The data couldn't be loaded. Check your connection and try again."),
      h("div", null, ui.button("Try again", { icon: "refresh", onClick: () => location.reload() })),
      ui.expander("Technical details", {}, h("pre", { class: "sg-code" }, `${err.name}: ${String(err.message).slice(0, 500)}`))));
    drawDock(null);
    return;
  }
  ctx = makeCtx(core, { render, onParam });
  setChartsConfig(core.config); // charts.js and globe.js read it
  ctx.fail = (err) => pageError(main.firstElementChild, err); // pages reach it through ctx.forPage (render below)
  drawSidebar(core.config);
  document.addEventListener("click", onLinkClick);
  addEventListener("popstate", () => {
    ctx.syncAddress(); // the entry's ?w= may be from other weights: the address follows the weights in use
    render({ focusTitle: true }); // Back and Forward land on the page title, as a link does
  });
  addEventListener(follow.CHANGED, () => drawDock(ctx.route));
  render({ first: true });
}

// ---- router -----------------------------------------------------------------------------------------------------
let seq = 0;
let cleanup = null;

async function render(opts = {}) {
  const n = ++seq;
  try { cleanup?.(); } catch (err) { console.warn("page cleanup failed", err); }
  cleanup = null;
  ui.closeFloats();
  const r = route(location.pathname);
  ctx.route = r;
  followCountry(r);
  markNav(r);
  syncWeights();
  drawDock(r);
  const page = h("div", { class: "sg-page" });
  main.style.minHeight = opts.weights ? `${main.offsetHeight}px` : ""; // a redraw keeps the scroll position
  main.replaceChildren(page);
  if (opts.navigated) scrollTo(0, 0);
  if (!r) {
    document.title = `Page not found · ${APP}`;
    page.append(ui.hero("Page not found"), h("p", null, ui.pageLink("/", "Global overview", "public")));
  } else {
    document.title = `${r.title} · ${APP}`;
    try {
      const mod = await import(`./pages/${r.module}.js`);
      if (n !== seq) return;
      const done = await mod.render(page, ctx.forPage(() => n === seq));
      if (typeof done === "function") n === seq ? (cleanup = done) : done();
    } catch (err) {
      if (n === seq) pageError(page, err);
    }
  }
  if (n !== seq) return;
  main.style.minHeight = "";
  if (opts.navigated || opts.focusTitle) focusTitle();
}

// ui.page_error_boundary: a short message with a way out; the sidebar and the dock keep working
function pageError(page, err) {
  if (!page) return;
  console.warn("page failed", err); // a warning: the error is handled, the visitor sees the message
  const retry = () => {
    ctx.setParam("tab", null);
    ctx.setParam("view", null);
    render({});
  };
  page.replaceChildren(
    ui.callout("error", ui.icon("error"), "This page couldn't be drawn. Try again, or open another page: the rest of the app still works."),
    h("div", { class: "sg-row sg-row-tight" }, ui.button("Try again", { icon: "refresh", onClick: retry }), ui.pageLink("/", "Global overview", "public")),
    ui.expander("Technical details", {}, h("pre", { class: "sg-code" }, `${err?.name ?? "Error"}: ${String(err?.message ?? err).slice(0, 500)}`)));
}

function focusTitle() {
  const h1 = main.querySelector("h1");
  if (!h1) return;
  h1.tabIndex = -1;
  h1.focus({ preventScroll: true });
}

function onLinkClick(e) {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  const a = e.target.closest?.("a[href]");
  if (!a || (a.target && a.target !== "_self") || a.hasAttribute("download")) return;
  const url = new URL(a.href, location.href);
  if (url.origin !== location.origin || !route(url.pathname)) return;
  if (url.hash && url.pathname === location.pathname && url.search === location.search) return; // an anchor on this page
  e.preventDefault();
  if (!matchMedia(WIDE).matches) setSidebar(false); // on phones the sidebar covers the page: put it away
  ctx.go(url.pathname, url.searchParams);
}

// ---- sidebar ----------------------------------------------------------------------------------------------------
let sliders = [];
let shares = null;

function setSidebar(open) {
  document.body.dataset.sidebar = open ? "open" : "closed";
  top.querySelector(".sg-side-open")?.setAttribute("aria-expanded", String(open));
  side.inert = !open;
}

function drawTopbar() {
  top.replaceChildren(
    h("img", { class: "sg-top-logo", src: "/assets/icon.svg", alt: "", width: 32, height: 32 }),
    h("button", { type: "button", class: "sg-side-open", "aria-label": "Open sidebar", "aria-controls": "sidebar",
      onclick: () => { setSidebar(true); side.querySelector(".sg-side-close")?.focus(); } }, ui.glyph("expand")));
  setSidebar(matchMedia(WIDE).matches); // like Streamlit's "auto": open on wide screens, folded away on phones
  addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !matchMedia(WIDE).matches && document.body.dataset.sidebar === "open") setSidebar(false);
  });
  document.addEventListener("pointerdown", (e) => { // phones: a tap beside the open sidebar closes it
    if (!matchMedia(WIDE).matches && document.body.dataset.sidebar === "open" && !side.contains(e.target) && !top.contains(e.target)) setSidebar(false);
  });
}

function drawSidebar(config) {
  const nav = h("nav", { class: "sg-nav", "aria-label": "Pages" },
    [...new Set(ROUTES.map((r) => r.section))].map((section) => [section, ROUTES.filter((r) => r.section === section)]).map(([section, pages]) => h("div", { class: "sg-nav-section" },
      h("div", { class: "sg-nav-head" }, section),
      h("ul", null, pages.map((r) => h("li", null, h("a", { class: "sg-nav-link", href: r.path }, ui.icon(r.icon), h("span", null, r.title))))))));
  const parts = [
    h("div", { class: "sg-side-head" },
      h("img", { class: "sg-logo", src: "/assets/logo.svg", alt: APP, width: 161, height: 32 }),
      h("button", { type: "button", class: "sg-side-close", "aria-label": "Close sidebar",
        onclick: () => { setSidebar(false); top.querySelector(".sg-side-open")?.focus(); } }, ui.glyph("collapse"))),
    nav,
  ];
  if (config) parts.push(h("div", { class: "sg-side-user" }, weightsPanel(config),
    h("p", { class: "sg-caption" }, h("b", null, config.APP_TITLE), ` · built by ${config.AUTHOR}`, h("br"),
      "Educational project. Not investment or security advice.")));
  side.replaceChildren(...parts);
  markNav(ctx?.route ?? route(location.pathname));
}

// "Index weights": four sliders (step 5), the shares they give, and Reset
function weightsPanel(config) {
  shares = ui.caption("");
  sliders = config.pillars.map((p) => ui.slider({ label: p.label, help: p.question, min: 0, max: 100, step: 5,
    value: ctx.rawWeights()[p.key], onChange: (v) => ctx.setWeights({ ...ctx.rawWeights(), [p.key]: v }) }));
  const panel = ui.expander("Index weights", {},
    ui.caption("How much each pillar counts in the composite score. Weights are rescaled to 100%, so only the proportions count."),
    ...sliders, shares, ui.button("Reset weights", { onClick: () => ctx.setWeights(defaultWeights(config)) }));
  syncWeights();
  return panel;
}

function syncWeights() {
  if (!ctx || !shares) return;
  const raw = ctx.rawWeights(), w = weightsShares(raw); // what the scores use: all sliders at 0 means the defaults
  ctx.core.config.pillars.forEach((p, i) => { if (sliders[i].value !== raw[p.key]) sliders[i].value = raw[p.key]; });
  shares.textContent = ctx.core.config.pillars.map((p) => `${p.short} ${fixed((w[p.key] / 100) * 100, 0)}%`).join(" · ");
}

function markNav(r) {
  for (const a of side.querySelectorAll(".sg-nav-link")) {
    if (r && a.getAttribute("href") === r.path) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  }
}

// ---- dock -------------------------------------------------------------------------------------------------------
let namesCache = null;
const names = () => (namesCache ??= new Map(asRows(ctx.core.countries).map((c) => [c.iso3, c.name])));

// On the profile, ?country= is the country the visitor is looking at: the dock follows it
function followCountry(r) {
  const asked = ctx.params.get("country")?.toUpperCase();
  if (r?.path !== "/country" || !asked || !names().has(asked)) return false;
  try { sessionStorage.setItem(LAST, asked); } catch { /* storage blocked */ }
  return true;
}

// A page changed a query value without a redraw (the profile's country picker uses ctx.setParam("country", …))
function onParam(name) {
  if (name === "country" && followCountry(ctx.route)) drawDock(ctx.route);
}

// The country opened last in this visit, else the address's ?country=, else the first followed; null until one exists
function tracked() {
  let last = null;
  try { last = sessionStorage.getItem(LAST); } catch { /* storage blocked */ }
  return [last, ctx.params.get("country"), follow.following()[0]]
    .map((c) => (c ? String(c).toUpperCase() : null)).find((c) => c && names().has(c)) ?? null;
}

const MEANING = { "▲": "riskier than last year", "▼": "safer than last year", "■": "steady, under 1 point from last year" };

// The tracked country: flag, score, tier and change since last year; a link to its profile
function readout() {
  const iso3 = tracked();
  if (!iso3) return null;
  const c = ctx.core.config;
  const row = asRows(ctx.table()).find((r) => r.iso3 === iso3);
  if (!row) return null;
  const years = asRows(ctx.history()).filter((r) => r.iso3 === iso3 && !na(r.composite)).sort((a, b) => a.year - b.year);
  const delta = years.length >= 2 ? pyRound(years.at(-1).composite - years.at(-2).composite, 1) : null;
  let tip = "Open the country profile";
  let meta;
  if (na(row.composite)) meta = ["not enough data to score"];
  else {
    meta = [h("b", null, fixed(row.composite, 0)), ` · ${row.tier}`];
    if (delta !== null) {
      const label = trendLabel(delta);
      tip += `. ${label[0]} ${MEANING[label[0]]}`;
      meta.push(" · ", h("span", { "aria-hidden": "true", title: `${label[0]} ${MEANING[label[0]]}` }, label),
        ui.sr(`${signed(delta)}, ${MEANING[label[0]]}`));
    }
  }
  const color = c.tiers.find((t) => t.label === row.tier)?.color ?? c.INK.faint;
  const flag = flagUrl(row.iso2, c.NO_FLAG);
  return h("a", { class: "sg-read", href: `/country?country=${iso3}`, title: tip, style: `--sg-c:${color}` },
    h("span", { class: "sg-tier" }), flag ? h("img", { src: flag, alt: "" }) : null,
    h("span", { class: "sg-read-text" }, h("span", { class: "sg-read-name" }, row.name), h("span", { class: "sg-read-meta" }, meta)));
}

let find = null;

function drawDock(r) {
  const tabs = h("div", { class: "sg-dtabs" }, DOCK_TABS.map(([path, label, iconName]) =>
    h("a", { class: "sg-dtab", href: path, "aria-current": r?.path === path ? "page" : null }, ui.icon(iconName), h("span", null, label))));
  if (ctx) {
    find ??= findPopover();
    find.close(); // moving it would hide an open panel without close(), leaving its state and listeners behind
    tabs.append(find);
  }
  dock.replaceChildren(tabs);
  if (ctx && r?.path !== "/country") { // the profile's own header already shows the country
    try {
      const read = readout();
      if (read) dock.append(read);
    } catch (err) {
      console.warn("dock readout failed", err); // the dock is a convenience: never let it break a page
    }
  }
}

// Find: one search for every page and every country; opened with no text it lists the pages first
function findPopover() {
  const pop = ui.popover("Find", { icon: "search", type: "tertiary", placement: "up", className: "sg-find",
    help: "Search countries and pages (press / or Ctrl+K)" });
  const pages = new Map(ROUTES.map((r) => [`page:${r.path}`, r]));
  const jump = (key) => {
    pop.close();
    if (pages.has(key)) ctx.go(pages.get(key).path);
    else ctx.go("/country", { country: key });
  };
  pop.addEventListener("sg:open", () => {
    const isos = [...names().keys()].sort((a, b) => names().get(a).localeCompare(names().get(b)));
    const box = ui.select({ label: "Find a country or page", options: [...pages.keys(), ...isos], value: null,
      placeholder: "Type a country or page…", onChange: jump,
      format: (k) => (pages.has(k) ? `${pages.get(k).title} · page` : names().get(k)) });
    const followed = follow.following().filter((i) => names().has(i))
      .map((i) => ui.button(`★ ${names().get(i)}`, { type: "tertiary", onClick: () => jump(i) }));
    pop.body.replaceChildren(box, ...followed);
    box.input.focus();
  });
  return pop;
}

// "/" (when not typing) or Ctrl/Cmd+K opens Find with the cursor in its box
addEventListener("keydown", (e) => {
  const el = document.activeElement;
  const typing = el && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable);
  if (!((e.key === "k" && (e.ctrlKey || e.metaKey)) || (e.key === "/" && !typing && !e.ctrlKey && !e.metaKey && !e.altKey))) return;
  if (!find) return;
  e.preventDefault();
  if (!find.isOpen()) find.open();
  else find.body.querySelector("input")?.focus();
});

// Skip link: to the top of the page content, so the next Tab reaches the page's first control
document.querySelector(".sg-skip")?.addEventListener("click", (e) => {
  e.preventDefault();
  main.focus();
});

boot();
