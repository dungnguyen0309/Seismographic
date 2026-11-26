// masterTable: port of ui.master_table. countryTable: a small sortable table component.
import { asMap, asRows, flagCounts, na, toTable } from "./scoring.js";
import { trendLabel } from "./format.js";
import { h, clear } from "./dom.js";

// numpy's Series.round(1): scale, round half to even, scale back (not the same as Python's round on exact ties)
function rint(y) {
  const f = Math.floor(y), d = y - f;
  return d < 0.5 ? f : d > 0.5 ? f + 1 : f % 2 === 0 ? f : f + 1;
}
const round1 = (x) => rint(x * 10) / 10;

// One row per country with names, groups, flags, scores and analyst info (+ change vs last year); {columns, rows}.
// core: {countries, wgiTrend, config}; extras.assessments: Map<iso3, analyst rating> for countries with an assessment.
export function masterTable(core, values, scores, hist, { assessments = new Map() } = {}) {
  const countries = asRows(core.countries);
  const sc = asMap(scores), vals = asMap(values);
  const scoreCols = (scores.columns ?? Object.keys([...sc.values()][0] ?? {})).filter((c) => c !== "iso3");
  const histRows = asRows(hist);
  const lastYear = histRows.length ? Math.max(...histRows.map((r) => r.year)) - 1 : null;
  const prev = new Map(histRows.filter((r) => r.year === lastYear).map((r) => [r.iso3, r]));
  const flags = flagCounts(vals, core.wgiTrend, core.config);
  const columns = ["iso3", "name", "region", "income", "iso2", "lat", "lng", ...scoreCols, "population", "gdppc", "battle_deaths_raw",
    "prev_composite", "prev_tier", "delta_1y", "trend", "flags", "assessment", "analyst_rating", "rank_label"];
  const rows = countries.map((c) => {
    const s = sc.get(c.iso3) ?? {}, v = vals.get(c.iso3) ?? {}, p = prev.get(c.iso3);
    const prevComposite = p?.composite ?? null;
    const delta = !na(s.composite) && !na(prevComposite) ? round1(s.composite - prevComposite) : null;
    return {
      iso3: c.iso3, name: c.name, region: c.region, income: c.income, iso2: c.iso2, lat: c.lat, lng: c.lng,
      ...Object.fromEntries(scoreCols.map((k) => [k, s[k] ?? null])),
      population: v.population ?? null, gdppc: v.gdppc ?? null, battle_deaths_raw: v.battle_deaths_raw ?? null,
      prev_composite: prevComposite, prev_tier: p?.tier ?? null, delta_1y: delta, trend: trendLabel(delta),
      flags: flags[c.iso3] ?? 0,
      assessment: assessments.has(c.iso3) ? "✓" : "", analyst_rating: assessments.get(c.iso3) ?? "",
      rank_label: !na(s.rank) ? `${Math.trunc(s.rank)} of ${Math.trunc(s.n_ranked)}` : "not ranked",
    };
  });
  return toTable(rows, columns);
}

// Codes with no flag file (config.NO_FLAG; a test keeps this in step)
export const NO_FLAG_DEFAULT = ["JG"];

// The flag file for a country, or null (ui.flag_url): none for codes that are not two letters or are in noFlag
export function flagUrl(iso2, noFlag = []) {
  const code = String(iso2 ?? "").trim().toUpperCase();
  if (!/^[A-Z]{2}$/.test(code) || noFlag.includes(code)) return null;
  return `/vendor/flags/${code.toLowerCase()}.svg`;
}

// The text of a cell: a dash for a missing value (unscored countries), unless the column sets fmtNull
export function cellText(v, row, col) {
  if (na(v) && !col.fmtNull) return "—";
  if (col.fmt) return col.fmt(v, row);
  return na(v) ? "—" : typeof v === "number" ? v.toLocaleString("en", { maximumFractionDigits: 1 }) : String(v);
}

// A sortable, accessible table.
//   rows:    array of row objects (or a {columns, rows} table)
//   columns: [{key, label, type, fmt, align}]; type "country" = flag + name linking to the country page,
//            "tier" = cell coloured with the tier's colour (needs opts.tiers = config.tiers); opts.noFlag = config.NO_FLAG; fmt is skipped for missing values (shows a dash) unless the column sets fmtNull, default text/number
//   key:     row field holding the ISO3 code (default "iso3"); height: max height of the scrolling box (CSS length)
//   extra:   optional (tr, row) callback to add classes or attributes to a body row
// Returns {render(rows), sort(key, dir)}. Class names are sg-*; the shell's CSS styles them.
export function countryTable(el, rows, { columns, key = "iso3", height = null, extra = null, tiers = [], noFlag = NO_FLAG_DEFAULT, sortKey = null, sortDir = "asc" } = {}) {
  let data = asRows(rows);
  const state = { key: sortKey, dir: sortDir };
  const tierOf = new Map(tiers.map((t) => [t.label, t]));
  const th = new Map();

  const value = (row, c) => row[c.key];
  const compare = (a, b) => {
    const x = a[state.key], y = b[state.key];
    if (na(x) || x === "") return na(y) || y === "" ? 0 : 1; // missing last, whichever the direction
    if (na(y) || y === "") return -1;
    const r = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), "en", { numeric: true });
    return state.dir === "asc" ? r : -r;
  };

  function cell(row, c) {
    const v = value(row, c);
    const text = cellText(v, row, c);
    const align = c.align ?? (typeof v === "number" ? "right" : null);
    if (c.type === "country") {
      const url = flagUrl(row.iso2, noFlag);
      const flag = url ? h("img", { class: "sg-flag", src: url, alt: "", loading: "lazy", onerror: (e) => e.target.remove() }) : null;
      return h("td", { class: "sg-cell-country" }, h("a", { class: "sg-row-link", href: `/country?country=${encodeURIComponent(row[key])}` }, flag, " ", text));
    }
    if (c.type === "tier") {
      const t = tierOf.get(v);
      return h("td", { class: "sg-cell-tier", style: t ? { background: t.color, color: t.text_on } : null }, text);
    }
    return h("td", { style: align ? { textAlign: align } : null }, text);
  }

  const head = h("tr", null, columns.map((c) => {
    const btn = h("button", { type: "button", class: "sg-sort", onclick: () => sort(c.key) }, c.label);
    const el = h("th", { scope: "col", "aria-sort": "none", style: { position: "sticky", top: "0", background: "var(--sg-bg, #000)", textAlign: c.align ?? null } }, btn);
    th.set(c.key, el);
    return el;
  }));
  const body = h("tbody");
  const table = h("table", { class: "sg-table" }, h("thead", null, head), body);
  const wrap = h("div", { class: "sg-table-wrap", style: { overflow: "auto", maxHeight: height } }, table);
  clear(el).append(wrap);

  function render(next) {
    if (next) data = asRows(next);
    const list = state.key ? [...data].sort(compare) : data;
    clear(body);
    for (const row of list) {
      const tr = h("tr", null, columns.map((c) => cell(row, c)));
      extra?.(tr, row);
      body.append(tr);
    }
    for (const [k, node] of th) node.setAttribute("aria-sort", k === state.key ? (state.dir === "asc" ? "ascending" : "descending") : "none");
  }

  function sort(k, dir) {
    state.dir = dir ?? (state.key === k && state.dir === "asc" ? "desc" : "asc");
    state.key = k;
    render();
  }

  render();
  return { render, sort };
}
