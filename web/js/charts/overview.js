// The overview page's numbers that depend on the visitor's filter and weights, as app_pages/overview.py computes them
// (staticbuild/overview.py keeps the Python side for the parity tests). Rows are master-table / history row objects.
import { na, redFlags } from "../lib/scoring.js";
import { countdown, fixed, pyRound } from "../lib/format.js";

export const ALL = "All regions";
export const INCOMES = ["Low income", "Lower middle income", "Upper middle income", "High income"];
const HIGH = new Set(["High", "Severe"]);

// stable sort (pandas' quicksort orders ties by CPU, see staticbuild/charts.py), missing values last
const sortBy = (rows, keys) => rows.map((r, i) => [r, i]).sort(([a, i], [b, j]) => {
  for (const [k, desc] of keys) {
    if (na(a[k]) !== na(b[k])) return na(a[k]) ? 1 : -1;
    if (!na(a[k]) && a[k] !== b[k]) return (a[k] < b[k] ? -1 : 1) * (desc ? -1 : 1);
  }
  return i - j;
}).map(([r]) => r);

const median = (xs) => {
  const s = xs.filter((v) => !na(v)).sort((a, b) => a - b);
  if (!s.length) return NaN;
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

const day = (d) => Math.floor(Date.parse(`${String(d).slice(0, 10)}T00:00:00Z`) / 864e5);

// The Filter popover: one region (or all) and any income groups
export const filtered = (region, incomes) => region !== ALL || incomes.length > 0;
export const filterView = (rows, region, incomes) =>
  rows.filter((r) => (region === ALL || r.region === region) && (!incomes.length || incomes.includes(r.income)));

// The headline numbers and their change since last year (deltas null without last year's rows; median "—" if none)
export function headline(view, hist, values, year) {
  const scored = view.filter((r) => !na(r.composite));
  const inView = new Set(view.map((r) => r.iso3));
  const last = hist.filter((r) => r.year === year - 1 && inView.has(r.iso3));
  const high = scored.filter((r) => HIGH.has(r.tier)).length;
  const conflict = scored.filter((r) => r.battle_deaths_raw >= 25).length;
  const now = scored.length ? median(scored.map((r) => r.composite)) : null;
  let medianDelta = null;
  if (now !== null && last.length) {
    const d = now - median(last.map((r) => r.composite));
    medianDelta = Number.isNaN(d) ? null : pyRound(d, 1) || 0; // ui.median_delta: no "-0.0"
  }
  return {
    scored: scored.length, high, high_delta: last.length ? high - last.filter((r) => HIGH.has(r.tier)).length : null,
    median: now === null ? "—" : fixed(now, 0), median_delta: medianDelta,
    median_color: medianDelta !== null && Math.abs(medianDelta) >= 1 ? "inverse" : "off",
    conflict, conflict_delta: last.length ? conflict - last.filter((r) => r.battle_deaths_raw >= 25).length : null,
    assessed: view.filter((r) => r.assessment === "✓").length,
    critical: scored.filter((r) => redFlags(values.get(r.iso3) ?? {}).some((f) => f.severity === "critical")).length,
    flagged: scored.filter((r) => r.flags > 0).length,
  };
}

// Hotspots: scores 50+ and got 2+ points riskier, crossed a new red flag, or faces a high-significance event in the
// next 120 days; most reasons first, then the highest score; six at most. today: "YYYY-MM-DD"
export function hotspotRows(view, { newFlags, events, today, year }) {
  const t = day(today);
  const soon = new Map();
  for (const e of sortBy(events.filter((e) => day(e.date) >= t && day(e.date) <= t + 120
    && String(e.significance).toLowerCase() === "high"), [["date", false]])) {
    if (!soon.has(e.iso3)) soon.set(e.iso3, e);
  }
  const rows = [];
  for (const r of view.filter((r) => r.composite >= 50)) {
    const reasons = [];
    if (!na(r.delta_1y) && r.delta_1y >= 2) reasons.push(`▲ ${fixed(r.delta_1y, 1, { sign: true })} since ${year - 1}`);
    const fresh = newFlags[r.iso3] ?? [];
    if (fresh.length) reasons.push(`⚑ New: ${fresh[0]}${fresh.length > 1 ? ` (+${fresh.length - 1} more)` : ""}`);
    const e = soon.get(r.iso3);
    if (e) reasons.push(`${e.event} ${countdown(day(e.date) - t)}`);
    if (reasons.length) rows.push({ iso3: r.iso3, name: r.name, composite: r.composite, why: reasons.join(" · "), tier: r.tier, signals: reasons.length });
  }
  return sortBy(rows, [["signals", true], ["composite", true]]).slice(0, 6);
}

// The Ranking tab: by rank, unscored last
export const rankingRows = (view) => sortBy(view, [["rank", false]]);

// "Highest risk in <region>": the 12 lowest ranks among the scored
export const topRisk = (view) => rankingRows(view.filter((r) => !na(r.composite))).slice(0, 12);

// pandas' to_csv for a float: Python's repr ("97.0", "3.2e-05"), empty when missing
export function pyFloat(v) {
  if (na(v)) return "";
  if (Number.isInteger(v)) return `${v}.0`; // shortcut: Python writes 1e+16 from 1e16 up; scores never get there
  if (v !== 0 && Math.abs(v) < 1e-4) return v.toExponential().replace(/e([+-])(\d)$/, "e$10$2");
  return String(v);
}
const CSV_FLOATS = new Set(["composite", "rank", "stability", "governance", "economic", "social", "coverage"]);
const CSV_COLUMNS = ["name", "composite", "trend", "tier", "rank", "stability", "governance", "economic", "social", "flags",
  "region", "coverage", "assessment", "analyst_rating"];
const csvCell = (s) => (/[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);

// "Download ranking (CSV)": the ranking's full values, UTF-8 with a byte-order mark (Excel), as the app writes it
export function rankingCsv(rows) {
  const lines = rows.map((r) => CSV_COLUMNS.map((c) => csvCell(CSV_FLOATS.has(c) ? pyFloat(r[c]) : na(r[c]) ? "" : String(r[c]))).join(","));
  return `﻿${[CSV_COLUMNS.join(","), ...lines].join("\n")}\n`;
}

// The political stability movers (data/overview/wgi_changes.json) for the countries in view, with their names
export function wgiMovers(changes, table, view, isFiltered) {
  const names = new Map(table.map((r) => [r.iso3, r.name]));
  const inView = new Set(view.map((r) => r.iso3));
  return (isFiltered ? changes.filter((c) => inView.has(c.iso3)) : changes).map((c) => ({ ...c, name: names.get(c.iso3) ?? null }));
}
