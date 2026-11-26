// The reference pages' calculations, ported from Python and checked against it (web/tests/reference.test.mjs), and
// the few display pieces those pages share.
import { asRows, na } from "../lib/scoring.js";
import { FLAG_MEANING, TIER_MEANING } from "../lib/interpret.js";
import { h } from "../lib/dom.js";
import { urlTabs } from "../lib/ui.js";

// ---------------------------------------------------------------------------------------------------------------
// Track record (prm/validation.py)
// ---------------------------------------------------------------------------------------------------------------
// onset_panel: one row per country at peace in year t: its score in t and whether armed conflict started in t+1.
// hist: the history for the weights in use; conflict: data/reference/methodology.json "conflict" ({last, years:
// {year: [ISO3 in armed conflict]}}), null when there is no conflict data.
export function onsetPanel(hist, conflict, score = "stability") {
  if (!conflict) return [];
  const rows = asRows(hist);
  const sets = new Map(Object.entries(conflict.years).map(([y, list]) => [Number(y), new Set(list)]));
  const none = new Set();
  const out = [];
  for (const year of [...new Set(rows.map((r) => r.year))].sort((a, b) => a - b)) {
    if (year + 1 > conflict.last) continue; // no conflict data after this year: not counted as peace
    const now = sets.get(year) ?? none, next = sets.get(year + 1) ?? none;
    for (const r of rows) {
      if (r.year === year && !na(r[score]) && !now.has(r.iso3)) out.push({ iso3: r.iso3, year, score: r[score], onset: next.has(r.iso3) });
    }
  }
  return out;
}

// the next float above x (numpy.nextafter(x, 1) for 0 < x < 1)
function nextUp(x) {
  const f = new Float64Array([x]);
  new BigInt64Array(f.buffer)[0] += 1n;
  return f[0];
}

// pd.qcut(ranks 1..n, 5)'s bin edges: np.quantile of the ranks at linspace(0, 1, 6), nudged up where not exact,
// with numpy's linear interpolation done the same way (so a rank on an edge falls in the same fifth)
function fifthEdges(n) {
  return [0, 1, 2, 3, 4, 5].map((j) => {
    let q = j === 5 ? 1 : j * 0.2;
    if (5 * q !== j) q = nextUp(q);
    const v = (n - 1) * q;
    if (v >= n - 1) return n;
    const lo = Math.floor(v), g = v - lo;
    return g >= 0.5 ? lo + 2 - (1 - g) : lo + 1 + g;
  });
}
// searchsorted(edges, x, side="left"), the lowest value counted in the first bin
const fifthOf = (x, edges) => (x === edges[0] ? 1 : edges.filter((e) => e < x).length);

// pandas rank(method="average")
function averageRanks(values) {
  const order = values.map((v, i) => i).sort((a, b) => values[a] - values[b]);
  const ranks = new Array(values.length);
  for (let i = 0; i < order.length;) {
    let j = i;
    while (j + 1 < order.length && values[order[j + 1]] === values[order[i]]) j++;
    for (let k = i; k <= j; k++) ranks[order[k]] = (i + j) / 2 + 1;
    i = j + 1;
  }
  return ranks;
}

// validation.summary: headline numbers and the onset rate per fifth of the score (fifths set within each year);
// null for an empty panel. Shares with no onset are null (Python: NaN).
export function trackRecord(panel) {
  if (!panel.length) return null;
  const fifth = new Array(panel.length);
  const byYear = new Map();
  panel.forEach((r, i) => byYear.set(r.year, [...(byYear.get(r.year) ?? []), i]));
  for (const idx of byYear.values()) {
    const order = [...idx].sort((a, b) => panel[a].score - panel[b].score || a - b); // rank "first": ties in order
    const edges = fifthEdges(idx.length);
    order.forEach((i, k) => { fifth[i] = fifthOf(k + 1, edges); });
  }
  const rows = panel.map((r, i) => ({ iso3: r.iso3, year: r.year, score: r.score, onset: r.onset, fifth: fifth[i] }));
  const onsets = rows.filter((r) => r.onset);
  const pos = onsets.length, neg = rows.length - pos;
  let auc = null;
  if (pos && neg) {
    const ranks = averageRanks(rows.map((r) => r.score));
    auc = (rows.reduce((s, r, i) => s + (r.onset ? ranks[i] : 0), 0) - (pos * (pos + 1)) / 2) / (pos * neg);
  }
  const share = (test) => (pos ? onsets.filter(test).length / pos : null);
  const years = rows.map((r) => r.year);
  return {
    years: [Math.min(...years), Math.max(...years) + 1],
    cases: rows.length,
    onsets: pos,
    base_rate: pos / rows.length,
    auc,
    top_fifth_share: share((r) => r.fifth === 5),
    top_two_fifths_share: share((r) => r.fifth >= 4),
    by_fifth: [1, 2, 3, 4, 5].map((f) => {
      const group = rows.filter((r) => r.fifth === f);
      const sum = group.filter((r) => r.onset).length;
      return group.length ? { fifth: f, mean: sum / group.length, sum, size: group.length } : { fifth: f, mean: null, sum: null, size: null };
    }),
    onset_list: onsets.sort((a, b) => a.year - b.year || b.score - a.score),
  };
}

// ---------------------------------------------------------------------------------------------------------------
// Videos about a country (ui.videos_about)
// ---------------------------------------------------------------------------------------------------------------
const escape = (s) => String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const WORD = "[\\p{L}\\p{N}_]";
const EDGE = `(?:(?<=${WORD})(?!${WORD})|(?<!${WORD})(?=${WORD}))`; // Python's Unicode \b
const isUpper = (t) => t === t.toUpperCase() && t !== t.toLowerCase(); // str.isupper()
const byLength = (list) => [...list].sort((a, b) => b.length - a.length);

// Videos whose title or description mentions the country: its name, news name, official name or aliases (all-caps
// aliases match case-sensitively). Longer names that contain it ("South Sudan" for Sudan) are removed first.
// videos: [{title, description}]; names: {ISO3: name}; newsNames: config.NEWS_NAMES; aliases: config.VIDEO_ALIASES
export function videosAbout(videos, iso3, names, official = null, { newsNames = {}, aliases = {} } = {}) {
  const name = names[iso3] ?? iso3;
  const extra = aliases[iso3] ?? [];
  const terms = new Set([name, newsNames[iso3] ?? name, ...(official ? [official] : []), ...extra]);
  const loose = [...terms].filter((t) => !isUpper(t));
  const exact = extra.filter(isUpper);
  const pattern = new RegExp(`${EDGE}(?:${byLength(loose).map(escape).join("|")})${EDGE}`, "iu");
  const patternExact = exact.length ? new RegExp(`${EDGE}(?:${exact.map(escape).join("|")})${EDGE}`, "u") : null;
  const longer = Object.values(names).filter((n) => n !== name && n.toLowerCase().includes(name.toLowerCase()));
  const strip = longer.length ? new RegExp(byLength(longer).map(escape).join("|"), "giu") : null;
  return videos.filter((v) => {
    let text = `${v.title ?? ""} \n ${v.description ?? ""}`;
    if (strip) text = text.replace(strip, " ");
    return pattern.test(text) || (patternExact !== null && patternExact.test(text));
  });
}

// ---------------------------------------------------------------------------------------------------------------
// Glossary search (app_pages/glossary.py)
// ---------------------------------------------------------------------------------------------------------------
const termText = (t) => [t.term, t.definition, ...t.tags].join(" ");

// The categories with matching terms (only those terms), the number found and the caption
export function glossarySearch(categories, query) {
  const q = query.trim().toLowerCase();
  const hits = categories.map((c) => ({ ...c, terms: c.terms.filter((t) => termText(t).toLowerCase().includes(q)) }))
    .filter((c) => c.terms.length);
  const found = hits.reduce((s, c) => s + c.terms.length, 0);
  const n = hits.length;
  return { hits, found, caption: `${found} matching term${found !== 1 ? "s" : ""} in ${n} categor${n !== 1 ? "ies" : "y"}.` };
}

// re.split(f"({re.escape(query)})", text, flags=re.I): the matches are the odd parts
export const highlight = (text, query) => String(text).split(new RegExp(`(${escape(query)})`, "iu"));

// ---------------------------------------------------------------------------------------------------------------
// Guide tables (app_pages/guide.py)
// ---------------------------------------------------------------------------------------------------------------
// Section 2: each tier's score band, meaning, how many countries are in it now and the three riskiest of them.
// table: the master table for the weights in use
export function tierRows(table, config) {
  const rows = asRows(table);
  const tiers = config.tiers;
  return tiers.map((t, i) => {
    const upper = i + 1 < tiers.length ? tiers[i + 1].lower : 100;
    const inTier = rows.filter((r) => r.tier === t.label).sort((a, b) => b.composite - a.composite);
    const [summary, ground] = TIER_MEANING[t.label];
    return { Tier: t.label, Score: `${Math.trunc(t.lower)}–${Math.trunc(upper)}`, "What it looks like": `${summary} ${ground}`,
      "Countries now": inTier.length, "For example": inTier.slice(0, 3).map((r) => r.name).join(", ") };
  });
}

const OPS = { ">=": (a, b) => a >= b, "<": (a, b) => a < b, "<=": (a, b) => a <= b };

// Section 4: each red flag with what it means and how many countries cross it now. values: data/values.json
export function flagRows(values, config) {
  const rows = asRows(values);
  const cols = new Set(values.columns ?? Object.keys(rows[0] ?? {}));
  return config.RED_FLAGS.filter(([key]) => FLAG_MEANING[key] && cols.has(key)).map(([key, op, threshold, severity, label]) => {
    const [meaning, response] = FLAG_MEANING[key];
    return { Severity: config.SEVERITY_LABEL[severity], Threshold: label, "In real life": meaning, "Common response": response,
      "Countries now": rows.filter((r) => !na(r[key]) && OPS[op](r[key], threshold)).length };
  });
}

// ---------------------------------------------------------------------------------------------------------------
// Display pieces shared by the reference pages (class names styled by css/reference.css)
// ---------------------------------------------------------------------------------------------------------------
// The app's HTML card grids: as many columns of at least minWidth px as fit
export const cardGrid = (cards, minWidth = 220, className = "") =>
  h("div", { class: `sg-ref-grid ${className}`.trim(), style: `--min:${minWidth}px` }, cards);
export const card = (...children) => h("div", { class: "sg-ref-card" }, children);

// st.table(hide_index=True, border="horizontal"): a static table whose long text wraps. columns: [key] or [{key, label}]
export function staticTable(columns, rows) {
  const cols = columns.map((c) => (typeof c === "string" ? { key: c, label: c } : c));
  const num = (c) => (typeof rows[0]?.[c.key] === "number" ? "sg-ref-num" : null); // numbers sit right, header too
  return h("div", { class: "sg-ref-static-wrap" }, h("table", { class: "sg-ref-static" },
    h("thead", null, h("tr", null, cols.map((c) => h("th", { scope: "col", class: num(c) }, c.label)))),
    h("tbody", null, rows.map((r) => h("tr", null, cols.map((c) => h("td", { class: num(c) }, c.fmt ? c.fmt(r[c.key], r) : r[c.key])))))));
}

// st.tabs: tabs that are not kept in the address (the shell's urlTabs, given a context of its own). With a key, the
// open tab is remembered for the visit, so a redraw (new weights) keeps it open as Streamlit does.
const openTabs = new Map();
export function localTabs(el, tabs, ctx, key = null) {
  const params = new URLSearchParams(key && openTabs.has(key) ? { tab: openTabs.get(key) } : {});
  return urlTabs(el, tabs, { params, setParam: (name, value) => { if (key && name === "tab") openTabs.set(key, value); },
    fail: (err, where) => ctx.fail(err, where) });
}

// st.pills (one choice; picking the chosen one again keeps it, as the page falls back to it).
// options: values; format(value) -> label
export function pills({ label, options, value = options[0], format = String, onChange = null }) {
  let current = value;
  const id = `sg-pills-${Math.random().toString(36).slice(2, 8)}`;
  const buttons = options.map((o) => h("button", { type: "button", class: "sg-ref-pill", "aria-pressed": String(o === current),
    onclick: () => { if (o === current) return; current = o; buttons.forEach((b, i) => b.setAttribute("aria-pressed", String(options[i] === o))); onChange?.(o); } },
  String(format(o))));
  return h("div", { class: "sg-field" }, h("div", { class: "sg-label-row" }, h("span", { class: "sg-label", id }, label)),
    h("div", { class: "sg-ref-pills", role: "group", "aria-labelledby": id }, buttons));
}
