// Routes, weights and the ctx object every page gets (docs/static-site.md, "Page module contract").
import { asMap, computeScores, decodeWeights as decode, defaultWeights, historyFor, setConfig as setScoringConfig, weightShares } from "./scoring.js";
import { masterTable } from "./table.js";
import { fixed } from "./format.js";

// streamlit_app.py: four sections, in the same order, with the same titles and Material icons
const PAGES = {
  Monitor: [
    ["/", "overview", "Global overview", "public"],
    ["/country", "country", "Country profile", "flag"],
    ["/compare", "compare", "Compare countries", "compare_arrows"],
    ["/changes", "changes", "Score changes", "trending_up"],
    ["/video", "video", "Live video", "live_tv"],
  ],
  Briefings: [
    ["/regions", "regions", "Regions", "travel_explore"],
    ["/conflict", "conflict", "Conflict & displacement", "crisis_alert"],
    ["/economy", "economy", "Economic stress", "monitoring"],
    ["/hotspots", "hotspots", "Hotspots", "radar"],
    ["/cases", "cases", "Case studies", "history"],
  ],
  Tools: [
    ["/explorer", "explorer", "Indicator explorer", "explore"],
    ["/stress", "stress", "Stress test", "bolt"],
    ["/builder", "builder", "Assessment builder", "edit_note"],
    ["/data", "data", "Data downloads", "download"],
  ],
  Reference: [
    ["/introduction", "introduction", "Introduction", "info"],
    ["/guide", "guide", "Guide", "lightbulb"],
    ["/methodology", "methodology", "Methodology", "functions"],
    ["/glossary", "glossary", "Glossary & legend", "help"],
    ["/sources", "sources", "Sources", "verified"],
  ],
};
export const ROUTES = Object.entries(PAGES).flatMap(([section, pages]) =>
  pages.map(([path, module, title, icon]) => ({ path, module, title, section, icon })));
const BY_PATH = new Map(ROUTES.map((r) => [r.path, r]));

// The page for a pathname ("/country" or "/country/"), or null for anything else
export function route(pathname) {
  const path = String(pathname ?? "");
  return BY_PATH.get(path.length > 1 ? path.replace(/\/$/, "") : path) ?? null;
}

// ui.decode_weights: four ints, 0..100, multiples of 5, sum above 0; else null
export const decodeWeights = (text, config = null) => (text === null || text === undefined ? null : decode(text, config));
// ui.weights_tuple: the weights as shares of 100 (all zero means the defaults)
export const weightsShares = (w, config = null) => weightShares(w, config);

// ui.custom_weights_label: "Stability 50% · Governance 20% · …" when the shares differ from the defaults, else ""
export function customWeightsLabel(w, config = null) {
  const shares = weightShares(w, config);
  const pillars = (config ?? cfg).pillars;
  if (pillars.every((p) => shares[p.key] === Number(p.default_weight))) return "";
  return pillars.map((p) => `${p.short} ${fixed((shares[p.key] / 100) * 100, 0)}%`).join(" · ");
}
let cfg = null;
// data/config.json for every helper here, in ui.js and in scoring.js (makeCtx calls it)
export function setConfig(config) {
  cfg = config;
  setScoringConfig(config);
}
export const conf = () => cfg;

// A query string with readable commas (?w=50,20,20,10, ?c=NGA,KEN)
export function queryString(params) {
  const parts = [...params].map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v).replace(/%2C/gi, ",")}`);
  return parts.length ? `?${parts.join("&")}` : "";
}

// ctx for the pages. core: the parsed core files {config, meta, countries, values, scores, history, master, wgiTrend}.
// render(opts): called by go() ({navigated: true}) and by setWeights() ({weights: true}) to draw the page again.
// onParam(name, value): told after every setParam (the shell follows ?country= on the profile).
export function makeCtx(core, { render = () => {}, onParam = () => {} } = {}) {
  const config = core.config;
  setConfig(config);
  let raw = decodeWeights(new URLSearchParams(location.search).get("w"), config) ?? defaultWeights(config);
  const cache = new Map();
  const custom = () => customWeightsLabel(raw, config) !== "";
  const shares = () => weightShares(raw, config);
  const memo = (name, fn) => {
    const weights = custom() ? Object.values(shares()).join(",") : "default";
    const key = `${name}:${weights}`;
    if (!cache.has(key)) {
      // keep the default weights' tables and the current weights' only: dragging a slider makes a new set each step
      for (const k of cache.keys()) if (!k.endsWith(":default") && !k.endsWith(`:${weights}`)) cache.delete(k);
      cache.set(key, fn());
    }
    return cache.get(key);
  };
  const replace = (params) => history.replaceState(history.state, "", location.pathname + queryString(params) + location.hash);
  // ?w= follows the weights: the slider values while they differ from the defaults, absent otherwise
  const withWeights = (params) => {
    if (custom()) params.set("w", config.pillars.map((p) => raw[p.key]).join(","));
    else params.delete("w");
    return params;
  };
  // the precomputed assessments column, so a recomputed table keeps the analysts' ratings
  const assessments = () => {
    const rows = core.master.rows, cols = core.master.columns;
    const [i, a, r] = ["iso3", "assessment", "analyst_rating"].map((c) => cols.indexOf(c));
    return new Map(rows.filter((row) => row[a]).map((row) => [row[i], row[r]]));
  };

  const ctx = {
    core,
    route: null, // the current route object, set by app.js before each render
    get params() { return new URLSearchParams(location.search); },
    weights: shares,
    rawWeights: () => ({ ...raw }),
    customLabel: () => customWeightsLabel(raw, config),
    // w: slider values by pillar key; opts.focusTitle puts the keyboard on the page title after the redraw
    setWeights(w, opts = {}) {
      raw = { ...defaultWeights(config), ...w };
      replace(withWeights(ctx.params));
      render({ weights: true, ...opts });
    },
    scores: () => memo("scores", () => (custom() ? computeScores(core.values, shares(), { config }) : asMap(core.scores))),
    history: () => memo("history", () => (custom() ? historyFor(core.history, shares(), config) : core.history)),
    table: () => memo("table", () => (custom()
      ? masterTable({ countries: core.countries, wgiTrend: core.wgiTrend, config }, core.values, ctx.scores(), ctx.history(),
        { assessments: assessments() })
      : core.master)),
    go(path, params = {}) {
      const p = new URLSearchParams(params instanceof URLSearchParams ? params
        : Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ""));
      history.pushState(null, "", path + queryString(withWeights(p)));
      render({ navigated: true });
    },
    setParam(name, value) {
      const p = ctx.params;
      if (value === null || value === undefined || value === "") p.delete(name);
      else p.set(name, value);
      replace(p);
      onParam(name, value);
    },
    // The address's ?w= back in line with the weights in use (after Back/Forward to an entry with other ?w=)
    syncAddress: () => replace(withWeights(ctx.params)),
    fetchJSON(url) {
      if (!cache.has(url)) {
        const p = fetch(url).then((r) => {
          if (!r.ok) throw new Error(`${r.status} ${url}`);
          return r.json();
        });
        p.catch(() => cache.delete(url)); // a failed file can be tried again
        cache.set(url, p);
      }
      return cache.get(url);
    },
    // The page error boundary for the page on screen (set by app.js). Pages get it through forPage().
    fail: (err) => { throw err; },
    // The ctx a page's render gets (app.js makes one per draw): the same ctx, except that fail(err, where) shows the
    // error boundary only while that draw is still the one on screen (isCurrent()) and `where`, the element that
    // failed (optional), is still in the page; a late failure after the visitor moved on or the page was redrawn is
    // only logged.
    forPage(isCurrent) {
      return Object.create(ctx, { fail: { value: (err, where = null) => {
        if (isCurrent() && (!where || where.isConnected)) ctx.fail(err);
        else console.warn("a section failed after its page was left or redrawn", err);
      } } });
    },
  };
  ctx.syncAddress(); // a bad or default ?w= leaves the address
  return ctx;
}
