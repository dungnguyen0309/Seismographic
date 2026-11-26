// What the Compare, Score changes, Regions and Indicator explorer pages compute from a visitor's choices (countries,
// region, indicator, weights): ports of app_pages/{compare,changes,regions,explorer}.py, checked against the Python
// pages by web/tests/group8.test.mjs. The figures themselves are js/lib/charts.js ports.
import { asMap, asRows, na, similar } from "../lib/scoring.js";
import { fixed, fmtPopulation, pyRound, signed, trendSaid, TREND_THRESHOLD } from "../lib/format.js";
import { h } from "../lib/dom.js";

const ALL = "All regions";
const stable = (rows, cmp) => rows.map((r, i) => [r, i]).sort((a, b) => cmp(a[0], b[0]) || a[1] - b[1]).map(([r]) => r);
const byStr = (a, b) => (a < b ? -1 : a > b ? 1 : 0); // Python's string order (code points), not the locale's
const median = (xs) => {
  const s = xs.filter((v) => !na(v)).sort((a, b) => a - b), m = s.length >> 1;
  return !s.length ? null : s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};
// numpy's round to 0 dp (half to even), as DataFrame.round()
const rint = (x) => {
  if (na(x)) return null;
  const f = Math.floor(x), d = x - f;
  return d < 0.5 ? f : d > 0.5 ? f + 1 : f % 2 === 0 ? f : f + 1;
};
// largest / smallest n by a column, ties in their original order, missing values left out (pandas nlargest / nsmallest)
const nlargest = (rows, n, k) => stable(rows.filter((r) => !na(r[k])), (a, b) => b[k] - a[k]).slice(0, n);
const nsmallest = (rows, n, k) => stable(rows.filter((r) => !na(r[k])), (a, b) => a[k] - b[k]).slice(0, n);

// config.Indicator.fmt: f"{value:,.{decimals}f}", a dash when missing
export const fmtInd = (ind, v) => (na(v) ? "—" : fixed(v, ind.decimals, { group: true }));
// str() of a Python float, as st.metric shows a float delta ("0.7", "2.0")
export const floatText = (x) => (Number.isInteger(x) ? fixed(x, 1) : String(x));
// ui.thin_data: under 75% of the indicators, or a whole pillar missing
export const thin = (r, config) => (!na(r.coverage) && r.coverage < 75) || config.pillars.some((p) => na(r[p.key]));

// ---- Compare ---------------------------------------------------------------------------------------------------------
// ?c=: known ISO3 codes, any case, each once, at most max
export function parsePicks(text, options, max) {
  const known = new Set(options), out = [];
  for (const part of String(text ?? "").toUpperCase().split(",")) {
    const c = part.trim();
    if (known.has(c) && !out.includes(c)) out.push(c);
  }
  return out.slice(0, max);
}

// A shared link first, then the list built with "Add to compare", then the current country with Kenya, South Africa, Ethiopia
export function seedPicks({ c = null, saved = [], current = null }, options, max) {
  const known = new Set(options);
  const shared = parsePicks(c, options, max);
  const kept = [...new Set((saved ?? []).filter((i) => known.has(i)))].slice(0, max);
  const fallback = [...new Set([current, "KEN", "ZAF", "ETH"].filter((i) => known.has(i)))].slice(0, 3);
  return shared.length ? shared : kept.length ? kept : fallback;
}

// Up to four countries with a close pillar profile to the first pick (none once the list is full)
export const similarTo = (scores, picked, max) => (picked.length >= max ? []
  : similar(scores, picked[0], 8).map((s) => s.iso3).filter((i) => !picked.includes(i)).slice(0, 4));

// One score card: the master-table row's numbers as the page writes them
export function scorecard(row, year) {
  return {
    iso3: row.iso3, score: na(row.composite) ? "—" : fixed(row.composite, 0), tier: row.tier ?? null,
    rank: na(row.rank) ? null : Math.trunc(row.rank), flags: Math.trunc(row.flags ?? 0), trend: row.trend ?? "—",
    said: na(row.delta_1y) ? null : trendSaid(row.delta_1y, year),
  };
}

// The Indicators table: every indicator (short name, a column per country, unit), then the four pillar scores
export function indicatorRows(values, rows, picked, names, config) {
  const vals = asMap(values);
  const cols = (fn) => Object.fromEntries(picked.map((i) => [names[i], fn(i)]));
  return [
    ...config.indicators.map((ind) => ({ Indicator: ind.short, ...cols((i) => fmtInd(ind, vals.get(i)?.[ind.key])), Unit: ind.unit })),
    ...config.pillars.map((p) => ({ Indicator: `${p.short} pillar`,
      ...cols((i) => (na(rows.get(i)?.[p.key]) ? "—" : fixed(rows.get(i)[p.key], 0))), Unit: "risk score, 0–100" })),
  ];
}

// compare_lines input: the composite per country-year
export const compositeSeries = (hist) => ({ composite: asRows(hist).map((r) => ({ iso3: r.iso3, year: r.year, value: r.composite })) });
// compare_lines input from data/group8/series/<ISO3>.json files ({iso3: {key: [[year, value]]}})
export function seriesFrom(files) {
  const out = {};
  for (const [iso3, file] of Object.entries(files)) {
    for (const [key, pairs] of Object.entries(file ?? {})) (out[key] ??= []).push(...pairs.map(([year, value]) => ({ iso3, year, value })));
  }
  return out;
}

// ---- Score changes -------------------------------------------------------------------------------------------------------
// The pillar that moved most in the same direction as the composite
function driver(row, config) {
  const deltas = config.pillars.filter((p) => !na(row[`d_${p.key}`])).map((p) => [p.short, row[`d_${p.key}`]]);
  if (!deltas.length || na(row.delta_1y)) return "—";
  const sign = row.delta_1y >= 0 ? 1 : -1;
  const best = deltas.reduce((a, d) => (sign * d[1] > sign * a[1] ? d : a));
  return `${best[0]} ${signed(best[1], 0)}`;
}

// view: the region's rows; moved: those with a change vs last year, with the tier move, pillar changes and main driver
export function changesView(table, hist, region, year, config) {
  const rows = asRows(table);
  const view = region === ALL ? rows : rows.filter((r) => r.region === region);
  const rank = new Map(config.tiers.map((t, i) => [t.label, i]));
  const prev = new Map(asRows(hist).filter((r) => r.year === year - 1).map((r) => [r.iso3, r]));
  const moved = view.filter((r) => !na(r.delta_1y)).map((r) => {
    const row = { ...r, tier_move: rank.has(r.tier) && rank.has(r.prev_tier) ? rank.get(r.tier) - rank.get(r.prev_tier) : null };
    for (const p of config.pillars) {
      const before = prev.get(r.iso3)?.[p.key];
      row[`d_${p.key}`] = na(r[p.key]) || na(before) ? null : r[p.key] - before;
    }
    row.driver = driver(row, config);
    return row;
  });
  return { view, moved };
}

// Red flags new or cleared since last year in the view (data/group8/flag_changes.json), New first, then by name
export function changesFlags(flagTable, view, config) {
  const names = new Map(view.map((r) => [r.iso3, r.name]));
  const rows = asRows(flagTable).filter((f) => names.has(f.iso3)).map((f) => ({ ...f, name: names.get(f.iso3),
    severity: f.change === "New" ? config.SEVERITY_LABEL[f.severity] : "Cleared" }));
  return stable(rows, (a, b) => byStr(b.change, a.change) || byStr(a.name, b.name));
}

// Riskier, Safer, To a riskier tier, To a safer tier, New red flags
export const changesKpis = (moved, flags) => [
  moved.filter((r) => r.delta_1y >= TREND_THRESHOLD).length, moved.filter((r) => r.delta_1y <= -TREND_THRESHOLD).length,
  moved.filter((r) => r.tier_move > 0).length, moved.filter((r) => r.tier_move < 0).length,
  flags.filter((f) => f.change === "New").length,
];

// Whether a bar change_bars draws (the 10 largest falls and rises) rests on limited data
export const thinNote = (moved, config) =>
  [...nsmallest(moved, 10, "delta_1y"), ...nlargest(moved, 10, "delta_1y")].some((r) => thin(r, config));

// The globe's note per country: "Moderate → Elevated · main driver: Economy +4"
export const changeNotes = (moved) => Object.fromEntries(moved.map((r) => [r.iso3,
  (!na(r.tier_move) && r.tier_move !== 0 ? `${r.prev_tier} → ${r.tier} · ` : "") + `main driver: ${r.driver}`]));

// Countries that changed tier, the biggest move up first
export const tierRows = (moved) => stable(moved.filter((r) => (r.tier_move ?? 0) !== 0),
  (a, b) => b.tier_move - a.tier_move || b.delta_1y - a.delta_1y).map((r) => ({ ...r, move: `${r.prev_tier} → ${r.tier}` }));

// Countries whose composite moved a point or more, pillar changes rounded (shown signed)
export const driverRows = (moved, config) => stable(moved.filter((r) => Math.abs(r.delta_1y) >= TREND_THRESHOLD),
  (a, b) => b.delta_1y - a.delta_1y).map((r) => ({ ...r, ...Object.fromEntries(config.pillars.map((p) => [`d_${p.key}`, rint(r[`d_${p.key}`])])) }));

// ---- Regions -------------------------------------------------------------------------------------------------------------
export const regionList = (table) => [...new Set(asRows(table).map((r) => r.region).filter((r) => !na(r) && r !== ""))].sort(byStr);
export const pickRegion = (asked, regions) => (regions.includes(asked) ? asked : regions[0]);

const HIGH = new Set(["High", "Severe"]);
// rv: the region's rows (+ displaced_total), rh: their history, the hero line, the five headline numbers, the table height
export function regionSummary(table, hist, values, region, year) {
  const vals = asMap(values);
  const rv = asRows(table).filter((r) => r.region === region).map((r) => ({ ...r, displaced_total: vals.get(r.iso3)?.displaced_total ?? null }));
  const scored = rv.filter((r) => !na(r.composite));
  const ids = new Set(rv.map((r) => r.iso3));
  const rh = asRows(hist).filter((r) => ids.has(r.iso3));
  const before = rh.filter((r) => r.year === year - 1);
  const last = before.length ? { median: median(before.map((r) => r.composite)), high: before.filter((r) => HIGH.has(r.tier)).length } : null;
  const now = scored.length ? median(scored.map((r) => r.composite)) : null;
  const d = now === null || last === null ? null : pyRound(now - last.median, 1) || 0; // ui.median_delta: no "-0.0"
  const nHigh = scored.filter((r) => HIGH.has(r.tier)).length;
  const riskiest = nsmallest(scored, 1, "rank")[0];
  const note = `vs ${year - 1}`;
  const kpis = [
    { label: "Median score", value: now === null ? "—" : fixed(now, 0), delta: d === null ? null : floatText(d),
      color: d !== null && Math.abs(d) >= TREND_THRESHOLD ? "inverse" : "off", note },
    { label: "High or Severe risk", value: String(nHigh), delta: last === null ? null : String(nHigh - last.high), color: "inverse", note },
    { label: "In armed conflict", value: String(scored.filter((r) => r.battle_deaths_raw >= 25).length),
      help: "At least 25 battle-related deaths in the latest UCDP year" },
    { label: "Displaced people", value: fmtPopulation(rv.reduce((a, r) => a + (na(r.displaced_total) ? 0 : r.displaced_total), 0)),
      help: "Refugees, asylum seekers, others in need of protection and IDPs originating from the region (UNHCR)" },
    { label: "Highest risk", value: riskiest ? riskiest.name : "—", help: "Highest composite score in the region" },
  ];
  return { rv, scored, rh, kpis, subtitle: `${scored.length} countries scored · ${year}`, height: Math.min(460, 35 * (rv.length + 1) + 3) };
}

// The ranking's order: global rank, unranked last
export const byRank = (rows) => stable(rows, (a, b) => (na(a.rank) ? (na(b.rank) ? 0 : 1) : na(b.rank) ? -1 : a.rank - b.rank));

// The calendar's events in the region, the country named as in the tables
export function regionEvents(events, rv) {
  const names = new Map(rv.map((r) => [r.iso3, r.name]));
  return asRows(events).filter((e) => names.has(e.iso3)).map((e) => ({ ...e, country: names.get(e.iso3) ?? e.country }));
}

// ---- Indicator explorer --------------------------------------------------------------------------------------------------
export function indicatorOptions(config) {
  const short = new Map(config.pillars.map((p) => [p.key, p.short]));
  return config.indicators.map((i) => ({ key: i.key, label: `${short.get(i.pillar)} · ${i.label}` }));
}

// frame: every country's value, its year and the indicator's risk score; view: the region's; known: those with a value
export function explorerFrame(table, values, scores, key, region, year) {
  const vals = asMap(values), sc = asMap(scores);
  const hasYear = !values.columns || values.columns.includes(`${key}__year`);
  const frame = asRows(table).map((r) => {
    const v = vals.get(r.iso3) ?? {};
    return { iso3: r.iso3, iso2: r.iso2, name: r.name, region: r.region, value: v[key] ?? null,
      year: hasYear ? v[`${key}__year`] ?? null : year, risk: sc.get(r.iso3)?.[`n_${key}`] ?? null };
  });
  const view = region === ALL ? frame : frame.filter((r) => r.region === region);
  return { frame, view, known: view.filter((r) => !na(r.value)) };
}

export const medianText = (known, ind) => (known.length ? fmtInd(ind, median(known.map((r) => r.value))) : "—");

// Riskiest n and safest n (n up to 10; a small region splits in two), or every country when fewer than four have data
export function leaderLists(known, ind) {
  const n = Math.min(10, Math.floor(known.length / 2));
  const lists = n >= 2
    ? [["risky", `Riskiest ${n}`, nlargest(known, n, "risk")], ["safe", `Safest ${n}`, nsmallest(known, n, "risk")]]
    : [["all", `All ${known.length} countries`, stable(known, (a, b) => (na(a.risk) ? (na(b.risk) ? 0 : 1) : na(b.risk) ? -1 : b.risk - a.risk))]];
  const out = [];
  for (const [part, title, rows] of lists) {
    if (!rows.length) break;
    out.push({ part, title, rows: rows.map((r) => ({ ...r, shown: fmtInd(ind, r.value), risk: rint(r.risk) })) });
  }
  return out;
}

export const explorerNotes = (known, ind) => Object.fromEntries(known.map((r) => [r.iso3,
  `${ind.short}: ${fmtInd(ind, r.value)} ${ind.unit}` + (na(r.year) ? "" : ` (${Math.trunc(r.year)})`)]));

// The globe's value per country: the indicator's risk score (null without one)
export const explorerCustom = (table, scores, key) => {
  const sc = asMap(scores);
  return Object.fromEntries(asRows(table).map((r) => [r.iso3, sc.get(r.iso3)?.[`n_${key}`] ?? null]));
};

// ---- Page pieces shared by the four pages (DOM) ---------------------------------------------------------------------------
// A choice kept with this history entry, as Streamlit keeps a widget's value: it survives a weights redraw and Back, and
// a fresh visit to the page starts from the default
export const recall = (key, fallback) => history.state?.[`g8:${key}`] ?? fallback;
export function remember(key, value) {
  history.replaceState({ ...(history.state ?? {}), [`g8:${key}`]: value }, "");
}

// st.column_config.ProgressColumn for countryTable: specs {column key: bar colour}; pass the result as `extra`
export function progressCells(columns, specs) {
  const at = columns.map((c, i) => [c.key, i]).filter(([k]) => k in specs);
  return (tr, row) => {
    for (const [k, i] of at) {
      const v = row[k], td = tr.children[i];
      if (na(v) || !td) continue;
      td.classList.add("g8-progress");
      td.prepend(h("span", { class: "g8-bar", "aria-hidden": "true", style: `--v:${Math.max(0, Math.min(100, v))}%;--c:${specs[k]}` }));
    }
  };
}

// data/news/<key>.json ({fetched, source, items}) as ui.newsList reads it; the build time stands where the app showed its fetch time
export const newsFrom = (file) => (file ? { articles: file.items ?? [], source: file.source,
  fetched: `${String(file.fetched ?? "").slice(0, 16).replace("T", " ")} UTC` } : null);
