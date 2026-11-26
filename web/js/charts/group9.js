// Conflict, economy and hotspots: the figures and numbers that depend on a visitor's choice (region, heatmap size,
// outlook view, weights, today's date), ported from prm/charts.py, prm/hotspots.py and the three app_pages with the
// Python names. Figures equal plotly.io.to_json of the Python figure minus the template (web/tests/group9.test.mjs).
// Call charts.setConfig(config) first (the app does at start).
import { base, config, mapColorscale, yearlyBars } from "../lib/charts.js";
import { asMap, asRows, na, redFlags } from "../lib/scoring.js";
import { fixed, pyRound } from "../lib/format.js";
import { h } from "../lib/dom.js";

// ---- page pieces the three pages share (promote to lib) ---------------------------------------------------------------
// st.header: the app hides a header's help mark (prm/ui.py hides stHeaderActionElements), so none is drawn
export const heading = (text) => h("h2", null, text);
// st.dataframe's default height: ten 35 px rows under the header, then it scrolls
export const TEN_ROWS = `${35 * 11 + 3}px`;
// A TextColumn with width="large": cut at 400 px (the whole text on hover)
export const large = (text) => h("span", { class: "g9-large", title: text }, text);
// ui.NAME_COLUMN (width "medium"): a plain name cut at 200 px; nameTitle (countryTable's extra) puts the whole name
// on a country link's hover
export const medium = (text) => h("span", { class: "g9-medium", title: text }, text);
export const nameTitle = (tr, row) => tr.querySelector(".sg-row-link")?.setAttribute("title", row.name);
// A st.column_config.ProgressColumn cell: a bar on a 0..max track, then the value
export const progress = (v, max, color, text) => h("span", { class: "g9-progress" },
  h("span", { class: "g9-bar", style: `--p:${Math.max(0, Math.min(1, v / max))};--c:${color}`, "aria-hidden": "true" }), h("span", null, text));
// config.reversed_scale: the same colours, bright end first
export const reversedScale = (scale) => [...scale].reverse().map(([t, col]) => [pyRound(1 - t, 4), col]);

// ---- helpers private to lib/charts.js (promote to lib) --------------------------------------------------------------
const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
function merge(target, src) {  // plotly's update semantics: nested objects merge, anything else replaces
  for (const [k, v] of Object.entries(src)) {
    if (v === undefined) continue;
    target[k] = isObj(v) ? merge(isObj(target[k]) ? target[k] : {}, v) : v;
  }
  return target;
}
const trace = (type, props) => merge({ type }, props);
const figure = (...data) => ({ data, layout: {} });
const updateLayout = (fig, props) => { merge(fig.layout, props); return fig; };
const addShape = (fig, s) => { (fig.layout.shapes ??= []).push(merge({}, s)); return fig; };
const addAnnotation = (fig, a) => { (fig.layout.annotations ??= []).push(merge({}, a)); return fig; };
const addVline = (fig, x, line) => addShape(fig, { type: "line", x0: x, x1: x, xref: "x", y0: 0, y1: 1, yref: "y domain", line });
const addHline = (fig, y, line) => addShape(fig, { type: "line", x0: 0, x1: 1, xref: "x domain", y0: y, y1: y, yref: "y", line });
const val = (v) => (na(v) ? null : v);
const npRound = (v, d = 0) => {  // numpy round: half to even on value * 10^d
  if (na(v)) return null;
  const k = 10 ** d, y = v * k, r = Math.round(y);
  return (Math.abs(y % 1) === 0.5 ? 2 * Math.round(y / 2) : r) / k;
};
// stable sort on keys [[key, desc]], missing values last (pandas' na_position) whatever the direction
const sortBy = (rows, keys) => rows.map((r, i) => [r, i]).sort(([a, i], [b, j]) => {
  for (const [k, desc] of keys) {
    const d = (na(a[k]) - na(b[k])) || (na(a[k]) ? 0 : a[k] < b[k] ? (desc ? 1 : -1) : a[k] > b[k] ? (desc ? -1 : 1) : 0);
    if (d) return d;
  }
  return i - j;
}).map(([r]) => r);
const median = (xs) => {
  const s = xs.filter((v) => !na(v)).sort((a, b) => a - b);
  if (!s.length) return NaN;
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};
const quantile = (xs, q) => {  // pandas / numpy linear interpolation, missing values skipped
  const s = xs.filter((v) => !na(v)).sort((a, b) => a - b);
  if (!s.length) return null;
  const at = q * (s.length - 1), lo = Math.floor(at), frac = at - lo;
  return lo + 1 < s.length ? s[lo] + (s[lo + 1] - s[lo]) * frac : s[lo];
};
const unique = (xs) => [...new Set(xs.filter((v) => !na(v)))].sort();
function darkGeo(fig, zoom, height = 520) {  // charts._dark_geo
  const c = config();
  const HOVER = { bgcolor: c.INK.hover, bordercolor: c.INK["line-strong"], font: { color: c.INK.strong, family: c.MONO_FONT, size: 12 } };
  updateLayout(fig, { geo: {
    showframe: false, showcoastlines: false, showland: true, landcolor: c.NO_DATA_COLOR, showcountries: true,
    countrycolor: c.INK.bg, countrywidth: 0.6, showocean: true, oceancolor: c.OCEAN_COLOR, showlakes: true,
    lakecolor: c.OCEAN_COLOR, bgcolor: "rgba(0,0,0,0)", projection: { type: "natural earth" },
    ...(zoom ? { fitbounds: "locations" } : { lataxis: { range: [-58, 84] } }),
  } });
  return updateLayout(fig, { height, margin: { l: 0, r: 0, t: 0, b: 0 }, font: { family: c.MONO_FONT, size: 12 },
    geo: { bgcolor: "rgba(0,0,0,0)" }, hoverlabel: HOVER });
}

// ---- dates -----------------------------------------------------------------------------------------------------------
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const parts = (iso) => String(iso).slice(0, 10).split("-").map(Number);
export const day = (iso) => { const [y, m, d] = parts(iso); return `${d} ${MONTHS[m - 1]} ${y}`; };  // 4 Oct 2026
export const dmy = (iso) => { const [y, m, d] = parts(iso); return `${String(d).padStart(2, "0")} ${MONTHS[m - 1]} ${y}`; };
export const monthLabel = (ym) => { const [y, m] = parts(ym); return `${MONTHS[m - 1]} ${y}`; };  // "2026-01" -> Jan 2026
export function addDays(iso, n) {
  const [y, m, d] = parts(iso);
  return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10);
}
const dayNumber = (iso) => { const [y, m, d] = parts(iso); return Date.UTC(y, m - 1, d) / 864e5; };
export const todayIso = (now = new Date()) =>  // the visitor's calendar day, as dt.date.today()
  `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;

// ---- Economic stress (app_pages/economy.py) ------------------------------------------------------------------------
export const ECON_COLUMNS = [["inflation", "Inflation"], ["gdp_growth", "Growth"], ["gov_debt", "Debt"],
  ["fiscal_balance", "Fiscal bal."], ["current_account", "Current acc."], ["reserves_months", "Reserves"]];
const ECON_KEYS = ECON_COLUMNS.map(([k]) => k);

// The master table joined with the economic indicators, for one region or all ("All regions")
export function econView(table, values, region) {
  const vals = asMap(values);
  const rows = asRows(table).map((r) => {
    const v = vals.get(r.iso3) ?? {};
    return { ...r, ...Object.fromEntries(ECON_KEYS.map((k) => [k, v[k] ?? null])) };
  });
  return region === "All regions" ? rows : rows.filter((r) => r.region === region);
}
export const regions = (rows) => unique(asRows(rows).map((r) => r.region));

// The five headline counts
export function econKpis(view) {
  const count = (k, ok) => view.filter((r) => !na(r[k]) && ok(r[k])).length;
  return [count("inflation", (v) => v >= 20), count("gdp_growth", (v) => v < 0), count("gov_debt", (v) => v >= 90),
    count("fiscal_balance", (v) => v <= -5), count("reserves_months", (v) => v < 3)];
}

// The economic red flags of each country in view: Map iso3 -> flags
export function econFlags(view, values, cfg = config()) {
  const vals = asMap(values);
  return new Map(view.map((r) => [r.iso3, redFlags(vals.get(r.iso3) ?? {}, cfg).filter((f) => ECON_KEYS.includes(f.key))]));
}
export const econNotes = (flags) =>
  Object.fromEntries([...flags].filter(([, hits]) => hits.length).map(([iso3, hits]) => [iso3, hits.map((f) => `⚑ ${f.label}`).join(" · ")]));

// "Several warning thresholds crossed": two or more flags, most flags first, then the riskiest economy
export function warningRows(view, flags, cfg = config()) {
  const rows = view.filter((r) => (flags.get(r.iso3) ?? []).length >= 2).map((r) => {
    const hits = flags.get(r.iso3);
    return { iso3: r.iso3, name: r.name, iso2: r.iso2, count: hits.length, economic: val(r.economic),
      warnings: hits.map((f) => `${f.short} (${cfg.SEVERITY_LABEL[f.severity].toLowerCase()})`).join(" · ") };
  });
  return sortBy(rows, [["count", true], ["economic", true]]);
}

// The most economically stressed countries first (highest Economy pillar score)
export const heatRows = (view, n) => sortBy(view.filter((r) => !na(r.economic)), [["economic", true]]).slice(0, n);

// plotly.colors.sample_colorscale for one point ("rgb(r, g, b)" with whole numbers) and charts._text_on
const rgb01 = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
const rint = (x) => { const f = Math.floor(x), d = x - f; return d < 0.5 ? f : d > 0.5 ? f + 1 : f % 2 === 0 ? f : f + 1; };
function sampleColor(scale, point) {
  let high = scale.findIndex(([t]) => t >= point);  // bisect_left
  if (high < 0) high = scale.length;
  const at = (i) => scale.at(i);
  const low = high - 1, t = (point - at(low)[0]) / (at(high)[0] - at(low)[0]);
  const a = rgb01(at(low)[1]), b = rgb01(at(high)[1]);
  return a.map((v, i) => rint((v + t * (b[i] - v)) * 255.0));
}
const textOn = ([r, g, b]) => {
  const lum = 0.2126 * (r / 255) ** 2.2 + 0.7152 * (g / 255) ** 2.2 + 0.0722 * (b / 255) ** 2.2;
  return lum > 0.22 ? "#0b0b0b" : "#f4f4f4";
};

// Rows = countries, columns = economic indicators; colour = risk score, text = the actual value
export function econHeatmap(df) {
  const c = config();
  const rows = asRows(df);
  const ind = (k) => c.indicators.find((i) => i.key === k);
  const labels = ECON_COLUMNS.map(([, l]) => l);
  const z = rows.map((r) => ECON_KEYS.map((k) => val(r[`n_${k}`])));
  const text = rows.map((r) => ECON_KEYS.map((k) => (na(r[k]) ? "—" : fixed(r[k], ind(k).decimals, { group: true }))));
  const units = ECON_KEYS.map((k) => ind(k).unit);
  const scale = mapColorscale("economic");
  const fig = figure(trace("heatmap", {
    z, x: labels, y: rows.map((r) => r.name), zmin: 0, zmax: 100, colorscale: scale, xgap: 2, ygap: 2, text,
    customdata: rows.map(() => [...units]),
    colorbar: { title: { text: "Risk", side: "right" }, thickness: 10, len: 0.6, tickvals: [0, 50, 100] },
    hovertemplate: "<b>%{y}</b> · %{x}<br>Value: %{text} %{customdata}<br>Risk score: %{z:.0f}/100<extra></extra>",
  }));
  const xs = [], ys = [], ts = [], cs = [];
  rows.forEach((r, i) => labels.forEach((label, j) => {
    xs.push(label); ys.push(r.name); ts.push(text[i][j]);
    cs.push(z[i][j] === null ? c.INK.faint : textOn(sampleColor(scale, z[i][j] / 100)));
  }));
  fig.data.push(trace("scatter", { x: xs, y: ys, mode: "text", text: ts, textfont: { size: 12, color: cs }, hoverinfo: "skip", showlegend: false }));
  updateLayout(fig, { yaxis: { range: [rows.length - 0.5, -0.5], automargin: true }, xaxis: { side: "top", range: [-0.5, labels.length - 0.5] } });
  return base(fig, Math.max(320, 24 * rows.length + 90));
}

// Growth vs inflation; bubble = population, colour = economic pillar risk; values past the edges are pinned there
export function stagflationScatter(df, cap = 60.0) {
  const c = config();
  const d = asRows(df).filter((r) => !na(r.gdp_growth) && !na(r.inflation));
  const popMedian = median(d.map((r) => r.population));
  const pop = d.map((r) => Math.max(na(r.population) ? popMedian : r.population, 1e5));
  const top = Math.sqrt(Math.max(...pop.filter((p) => !na(p))));
  const symbol = (r) => (r.inflation > cap ? "triangle-up" : r.gdp_growth > 15 ? "triangle-right" : r.gdp_growth < -15 ? "triangle-left" : "circle");
  const fig = figure(trace("scatter", {
    x: d.map((r) => Math.min(Math.max(r.gdp_growth, -15), 15)), y: d.map((r) => Math.min(r.inflation, cap)), mode: "markers",
    marker: { size: pop.map((p) => val(Math.max((Math.sqrt(p) / top) * 34, 7))), color: d.map((r) => val(r.economic)),
      colorscale: mapColorscale("economic"), cmin: 0, cmax: 100, symbol: d.map(symbol), line: { color: c.INK.bg, width: 1.5 },
      opacity: 0.92, colorbar: { title: { text: "Economy risk", side: "right" }, thickness: 10, len: 0.6 } },
    customdata: d.map((r) => [r.name, npRound(r.inflation, 1), npRound(r.gdp_growth, 1), r.iso3]),
    hovertemplate: "<b>%{customdata[0]}</b><br>Growth %{customdata[2]}% · inflation %{customdata[1]}%"
      + "<br><i>Click to open the profile</i><extra></extra>",
  }));
  addShape(fig, { type: "rect", x0: -16, x1: 0, y0: 20, y1: cap + 3, fillcolor: c.INK.worse, opacity: 0.10, line: { width: 0 }, layer: "below" });
  addAnnotation(fig, { x: -15.5, y: cap + 2, text: "Stagflation zone", showarrow: false, xanchor: "left", font: { color: c.INK.worse, size: 12 } });
  addVline(fig, 0, { color: c.INK.faint, width: 1, dash: "dot" });
  addHline(fig, 20, { color: c.INK.faint, width: 1, dash: "dot" });
  updateLayout(fig, { xaxis: { title: { text: "Real GDP growth (%, ◀ ▶ = beyond ±15)" }, range: [-16, 16] },
    yaxis: { title: { text: `Inflation (%, ▲ = above ${fixed(cap, 0)})` }, range: [-5, cap + 3] } });
  return base(fig, 460);
}

// An IMF series' rows ({iso3, year, value}) for the countries in view
export const inView = (series, view) => {
  const shown = new Set(view.map((r) => r.iso3));
  return asRows(series).filter((r) => shown.has(r.iso3));
};
// The last year of IMF projections the caption names (the WEO ends a year earlier from January to April)
export const outlookLast = (series, year) => (series.length ? Math.min(year + 5, Math.max(...series.map((r) => r.year))) : year + 5);

// Median across countries with the middle-half band; dashed after the last full year (IMF projections)
export function imfOutlook(series, year, title, start, end) {
  const c = config();
  const d = asRows(series).filter((r) => r.year >= start && r.year <= end);
  const years = [...new Set(d.map((r) => r.year))].sort((a, b) => a - b);
  const q = new Map(years.map((y) => {
    const v = d.filter((r) => r.year === y).map((r) => r.value);
    return [y, [0.25, 0.5, 0.75].map((p) => quantile(v, p))];
  }));
  const ys = (list, i) => list.map((y) => q.get(y)[i]);
  const actual = years.filter((y) => y <= year - 1), projected = years.filter((y) => y >= year - 1);
  const fig = figure(
    trace("scatter", { x: years, y: ys(years, 2), mode: "lines", line: { width: 0 }, hoverinfo: "skip", showlegend: false }),
    trace("scatter", { x: years, y: ys(years, 0), mode: "lines", line: { width: 0 }, fill: "tonexty", fillcolor: "rgba(255,255,255,0.09)",
      name: "Middle half of countries", hoverinfo: "skip" }),
    trace("scatter", { x: actual, y: ys(actual, 1), mode: "lines", name: "Median", line: { color: c.PILLAR_COLORS.economic, width: 2.5 },
      hovertemplate: "%{x}: %{y:.1f}%<extra>median</extra>" }),
    trace("scatter", { x: projected, y: ys(projected, 1), mode: "lines", name: "IMF projection",
      line: { color: c.FORECAST_GREY, width: 2.5, dash: "dash" }, hovertemplate: "%{x}: %{y:.1f}%<extra>projection</extra>" }),
  );
  updateLayout(fig, { xaxis: { tickformat: "d" }, yaxis: { title: { text: title } } });
  return base(fig, 340, true);
}

// ---- Hotspots (prm/hotspots.py) ------------------------------------------------------------------------------------
export const HOTSPOTS = {
  WINDOW_DAYS: 90, RECENT_DAYS: 7, MIN_ARTICLES_7D: 20, ESCALATING_RATIO: 1.5, EASING_RATIO: 0.67,
  STATUS_ORDER: ["Escalating", "Steady", "Easing", "Quiet"], MIN_EVENTS_90D: 5, MIN_DEATHS_90D: 25, MIN_COMPOSITE: 60,
  VIOLENCE: { 1: "State-based", 2: "Non-state", 3: "One-sided" },
};

// A news file the daily run stopped updating would keep showing an old reading as "now"
export const newsStale = (meta, today) => !!meta?.gdelt_through && String(meta.gdelt_through).slice(0, 10) < addDays(today, -3);

// hotspots.board: one row per hotspot, Escalating first, then deaths in the last 90 days, then composite.
// table: the master table for the visitor's weights; signal: hotspots.escalation rows, or null when stale or missing
export function board(table, monthly, cells, signal) {
  const C = HOTSPOTS;
  const recent = new Map();
  for (const c of asRows(cells)) {
    const r = recent.get(c.iso3) ?? { events: 0, deaths: 0, last: null };
    r.events += c.events; r.deaths += c.deaths;
    if (r.last === null || c.last_date > r.last) r.last = c.last_date;
    recent.set(c.iso3, r);
  }
  const sig = asMap(signal ?? []);
  const m = asRows(monthly);
  const months = unique(m.map((r) => r.month)).slice(-6, -3);
  const prev = new Map();
  for (const r of m) if (months.includes(r.month)) prev.set(r.iso3, (prev.get(r.iso3) ?? 0) + r.deaths);
  const rows = asRows(table).map((t) => {
    const r = recent.get(t.iso3), s = sig.get(t.iso3);
    return { iso3: t.iso3, name: t.name, iso2: t.iso2, region: t.region, composite: val(t.composite), tier: t.tier ?? null,
      analyst_rating: t.analyst_rating ?? "", events_90d: r?.events ?? 0, deaths_90d: r?.deaths ?? 0, last_event: r?.last ?? null,
      status: s?.status ?? "Quiet", ratio: val(s?.ratio), deaths_prev_3m: prev.get(t.iso3) ?? 0 };
  }).filter((r) => r.events_90d >= C.MIN_EVENTS_90D || r.deaths_90d >= C.MIN_DEATHS_90D || r.status === "Escalating"
    || (!na(r.composite) && r.composite >= C.MIN_COMPOSITE));
  const sorted = sortBy(rows.map((r) => ({ ...r, _esc: r.status !== "Escalating" ? 1 : 0 })), [["_esc", false], ["deaths_90d", true], ["composite", true]]);
  return sorted.map(({ _esc, ...r }, i) => ({ ...r, order: i + 1 }));
}

// The Map tab's cells, with their region, for one region or all
export function mapCells(cells, regionOf, region) {
  const rows = asRows(cells).map((c) => ({ ...c, region: regionOf[c.iso3] ?? null }));
  return region === "All regions" ? rows : rows.filter((c) => c.region === region);
}

// UCDP event cells: marker area by deaths, colour by the cell's main type of violence; ISO3 last in customdata
export function hotspotMap(cells, names, violence, zoom = false) {
  const c = config();
  const rows = asRows(cells);
  const top = rows.length ? Math.max(quantile(rows.map((r) => r.deaths), 0.99), 1.0) : 1.0;
  const fig = figure();
  for (const [kind, label] of Object.entries(violence)) {
    const d = rows.filter((r) => r.violence === Number(kind));
    if (!d.length) continue;
    fig.data.push(trace("scattergeo", {
      lat: d.map((r) => r.lat), lon: d.map((r) => r.lon), mode: "markers", name: label,
      marker: { size: d.map((r) => Math.min(r.deaths, 4 * top)), sizemode: "area", sizeref: top / 22 ** 2, sizemin: 3,
        color: c.COUNTRY_COLORS[Number(kind) - 1], opacity: 0.85, line: { color: c.INK.bg, width: 0.5 } },
      customdata: d.map((r) => [names[r.iso3] ?? r.iso3, fixed(r.events, 0, { group: true }), fixed(r.deaths, 0, { group: true }), dmy(r.last_date), r.iso3]),
      hovertemplate: "<b>%{customdata[0]}</b><br>" + label + " violence<br>%{customdata[1]} events · "
        + "%{customdata[2]} deaths<br>Last event %{customdata[3]}<br><i>Click to open the profile</i><extra></extra>",
    }));
  }
  updateLayout(fig, { showlegend: true, legend: { orientation: "h", x: 0, y: 0, yanchor: "top", title: {}, font: { color: c.INK.text }, itemsizing: "constant" } });
  return darkGeo(fig, zoom && rows.length > 0);
}

// UCDP events by month (for one region or all); null when there are none
export function monthlyBars(monthly, regionOf, region) {
  const rows = asRows(monthly).filter((r) => region === "All regions" || regionOf[r.iso3] === region);
  const months = unique(rows.map((r) => r.month));
  if (!months.length) return null;
  const sums = months.map((m) => rows.filter((r) => r.month === m).reduce((s, r) => s + r.events, 0));
  const fig = yearlyBars(months.map(monthLabel), sums, "Events", config().INK.worse, "events");
  fig.layout.xaxis.type = "category";
  return fig;
}

// The Calendar tab for a day: windows of events (rows keep their YYYY-MM-DD date) and each country's next event
export function calendar(events, names, today) {
  const rows = asRows(events).filter((e) => e.date).map((e) => ({ ...e, country: names[e.iso3] ?? (e.country || e.iso3) }));
  const upcoming = rows.filter((e) => e.date >= today), past = rows.filter((e) => e.date < today);
  const windows = {
    "Next 90 days": upcoming.filter((e) => e.date <= addDays(today, 90)),
    "Next 12 months": upcoming.filter((e) => e.date <= addDays(today, 365)),
    "All upcoming": upcoming,
    Past: sortBy(past, [["date", true]]),
  };
  const first = new Map();
  for (const e of sortBy(upcoming, [["date", false]])) if (!first.has(e.iso3)) first.set(e.iso3, e);
  const next = [...first.values()].sort((a, b) => (a.iso3 < b.iso3 ? -1 : 1)).map((e) => {
    const days = Math.max(dayNumber(e.date) - dayNumber(today), 0);
    return { iso3: e.iso3, days: days <= 365 ? days : null, note: `${e.event} · ${dmy(e.date)} · ${e.significance} significance` };
  });
  return { upcoming, past, windows, next };
}

// charts.events_timeline; today: the dotted line (YYYY-MM-DD)
export function eventsTimeline(df, today) {
  const c = config();
  const rows = asRows(df);
  const title = (s) => String(s ?? "").toLowerCase().replace(/(^|[^a-z])([a-z])/g, (_, p, ch) => p + ch.toUpperCase());
  const fig = figure();
  for (const level of ["Low", "Medium", "High"]) {
    const d = rows.filter((r) => title(r.significance) === level);
    if (!d.length) continue;
    fig.data.push(trace("scatter", {
      x: d.map((r) => `${r.date}T00:00:00.000000`), y: d.map((r) => r.country), mode: "markers", name: `${level} significance`,
      marker: { size: { Low: 10, Medium: 14, High: 18 }[level], color: c.INK.text, line: { color: c.INK.bg, width: 2 } },
      customdata: d.map((r) => [r.event, r.category]),
      hovertemplate: "<b>%{y}</b> · %{x|%d %b %Y}<br>%{customdata[0]}<br><i>%{customdata[1]}</i><extra></extra>",
    }));
  }
  addVline(fig, today, { color: c.INK.faint, width: 1, dash: "dot" });
  updateLayout(fig, { yaxis: { title: {}, automargin: true } });
  return base(fig, Math.max(280, 34 * new Set(rows.map((r) => r.country)).size + 120), true);
}

// ---- Conflict & displacement (app_pages/conflict.py) ----------------------------------------------------------------
// The tier for the visitor's weights on rows built without it
export function withTier(rows, table) {
  const t = asMap(table);
  return asRows(rows).map((r) => ({ ...r, tier: t.get(r.iso3)?.tier ?? null }));
}

// The Outlook tab's table: the 20 countries at peace with the highest chance of new conflict
export function outlookRows(outlook, table) {
  const t = asMap(table);
  const peaceful = sortBy(asRows(outlook.predictions).filter((p) => !na(p.probability)), [["probability", true]]);
  const shown = peaceful.slice(0, 20).map((p) => {
    const r = t.get(p.iso3) ?? {};
    return { iso3: p.iso3, name: r.name ?? p.iso3, iso2: r.iso2 ?? null, tier: r.tier ?? null, chance: p.probability * 100,
      relative: p.relative, recent: { 1: "yes", 0: "" }[p.recent_conflict] ?? null };
  });
  return { rows: shown.map((r) => ({ ...r, chance: npRound(r.chance, 1), relative: npRound(r.relative, 1) })),
    chanceMax: Math.max(30, ...shown.map((r) => r.chance)) };
}

// The numbers under it: average chance, AUC, and the back-test caption (null without a Brier skill)
export function outlookTexts(o) {
  const onsets = asRows(o.backtest).reduce((s, r) => s + (r.onset ? 1 : 0), 0);
  return [`${fixed(o.base_rate * 100, 1)}%`, na(o.auc) ? "—" : fixed(o.auc, 2),
    na(o.brier_skill) ? null : `${fixed(asRows(o.backtest).length, 0, { group: true })} country-years, ${onsets} new conflicts. `
      + `The predictions beat the average rate by ${fixed(o.brier_skill * 100, 0)}% (Brier skill score).`];
}
