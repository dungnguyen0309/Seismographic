// Port of prm/stress.py: one economic shock applied to many countries at once, scored against today's values.
// defs: the shocks from data/group10/stress.json ([{key, label, unit, low, high, step, relative}]).
import { asMap, asRows, computeScores, na, redFlags } from "../lib/scoring.js";
import { toCsv, npRound } from "./export.js";

const CLIP_0_100 = new Set(["unemployment", "youth_unemployment"]);
const CLIP_LOW = new Set(["gov_debt", "reserves_months"]);

// Shock.apply for one value (a missing value stays missing)
function apply(def, value, size) {
  if (na(value)) return value;
  const out = def.relative ? value * (1 + size / 100) : value + size;
  if (CLIP_0_100.has(def.key)) return Math.min(Math.max(out, 0), 100);
  return CLIP_LOW.has(def.key) ? Math.max(out, 0) : out;
}

// stress.run: one row per country (values order) with scores and tiers today and under stress, the change, and new
// or worse red flags. scope: ISO3 codes hit (null = all). opts.before: today's scores for these weights (ctx.scores()).
export function run(values, weights, shocks, scope, defs, config, { before = null } = {}) {
  const byKey = new Map(defs.map((d) => [d.key, d]));
  const active = Object.entries(shocks).filter(([k, v]) => byKey.has(k) && v);
  const vals = asMap(values);
  const inScope = scope === null || scope === undefined ? null : new Set(scope);
  const hit = (iso) => inScope === null || inScope.has(iso);
  const shocked = new Map([...vals].map(([iso, row]) => {
    if (!hit(iso)) return [iso, row];
    const r = { ...row };
    for (const [k, size] of active) if (k in r) r[k] = apply(byKey.get(k), r[k], size);
    return [iso, r];
  }));
  const today = before ?? computeScores(vals, weights, { config });
  const after = computeScores(shocked, weights, { reference: vals, config });
  const order = Object.fromEntries(config.tiers.map((t, i) => [t.label, i]));
  const rank = config.SEVERITY_ORDER;
  return [...vals.keys()].map((iso) => {
    const b = today.get(iso) ?? {}, a = after.get(iso) ?? {};
    const row = { iso3: iso, hit: hit(iso) };
    for (const c of ["composite", "economic", "social", "tier"]) {
      row[`${c}_before`] = b[c] ?? null;
      row[`${c}_after`] = a[c] ?? null;
    }
    row.delta = na(row.composite_before) || na(row.composite_after) ? null : row.composite_after - row.composite_before;
    const tb = order[row.tier_before], ta = order[row.tier_after];
    row.tier_move = tb === undefined || ta === undefined ? null : ta - tb;
    const was = redFlags(vals.get(iso), config);
    if (!row.hit) {
      Object.assign(row, { flags_before: was.length, flags_after: was.length, new_flags: [] });
    } else {
      const prev = new Map(was.map((f) => [f.key, f]));
      const now = redFlags(shocked.get(iso), config);
      const worse = now.filter((f) => !prev.has(f.key) || rank[f.severity] < rank[prev.get(f.key).severity])
        .sort((x, y) => rank[x.severity] - rank[y.severity]);
      row.flags_before = was.length;
      row.flags_after = now.length;
      row.new_flags = worse.map((f) => `${f.short} (${config.SEVERITY_LABEL[f.severity].toLowerCase()})`);
    }
    row.new_flag_count = row.new_flags.length;
    return row;
  });
}

// stress.summary: headline numbers for the countries hit (mean_delta null when none is hit)
export function summary(rows, config) {
  const hit = rows.filter((r) => r.hit && !na(r.composite_before));
  const severe = config.tiers[config.tiers.length - 1].label;
  const deltas = hit.map((r) => r.delta).filter((d) => !na(d));
  const count = (fn) => hit.filter(fn).length;
  return {
    countries: hit.length, tier_up: count((r) => r.tier_move > 0), tier_down: count((r) => r.tier_move < 0),
    new_flags: hit.reduce((a, r) => a + r.new_flag_count, 0), with_new_flags: count((r) => r.new_flag_count > 0),
    mean_delta: deltas.length ? deltas.reduce((a, b) => a + b, 0) / deltas.length : null,
    severe_before: count((r) => r.tier_before === severe), severe_after: count((r) => r.tier_after === severe),
  };
}

// Python's format(v, "g") for a non-zero v (6 significant digits, no trailing zeros): the shocks in a link and label
export function fmtG(v) {
  const [m, e] = v.toExponential(5).split("e");
  const exp = Number(e);
  if (exp < -4 || exp >= 6) return `${m.replace(/\.?0+$/, "")}e${exp < 0 ? "-" : "+"}${String(Math.abs(exp)).padStart(2, "0")}`;
  const s = v.toFixed(Math.max(0, 5 - exp));
  return s.includes(".") ? s.replace(/\.?0+$/, "") : s;
}

// stress.encode: "gdp_growth:-4,gov_debt:10" (zero and unknown shocks left out)
export const encode = (shocks, defs) => Object.entries(shocks)
  .filter(([k, v]) => defs.some((d) => d.key === k) && v).map(([k, v]) => `${k}:${fmtG(v)}`).join(",");

// Python's float(): its whitespace, underscores between digits, inf and nan; no hex. undefined = not a number.
const WS = "\\t\\n\\x0b\\x0c\\r\\x1c-\\x1f \\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000";
const STRIP = new RegExp(`^[${WS}]+|[${WS}]+$`, "g");
const DIGITS = "\\d(?:_?\\d)*";
const FLOAT = new RegExp(`^[+-]?(?:${DIGITS}(?:\\.(?:${DIGITS})?)?|\\.${DIGITS})(?:[eE][+-]?${DIGITS})?$`);
// shortcut: Python also reads non-ASCII digits (e.g. full-width); a link with them falls back here instead
function pyFloat(raw) {
  const s = raw.replace(STRIP, "");
  if (FLOAT.test(s)) return Number(s.replace(/_/g, ""));
  return /^[+-]?(?:inf|infinity|nan)$/i.test(s) ? NaN : undefined;
}
const rint = (y) => {
  const f = Math.floor(y), d = y - f;
  return d < 0.5 ? f : d > 0.5 ? f + 1 : f % 2 === 0 ? f : f + 1;
};

// stress.decode: ?shock= read back; garbage or unknown parts are skipped, values clipped to the slider and its step
export function decode(text, defs) {
  const byKey = new Map(defs.map((d) => [d.key, d]));
  const out = {};
  for (const part of String(text ?? "").split(",")) {
    const at = part.indexOf(":");
    const shock = byKey.get((at < 0 ? part : part.slice(0, at)).replace(STRIP, ""));
    const value = pyFloat(at < 0 ? "" : part.slice(at + 1));
    if (value === undefined || !shock || !Number.isFinite(value)) continue;
    out[shock.key] = (rint(Math.min(Math.max(value, shock.low), shock.high) / shock.step) || 0) * shock.step;
  }
  return out;
}

// The page's "Download results (CSV)": the countries hit, in the table's order, figures to 2 decimals
const CSV = { iso3: "str", name: "str", region: "str", income: "str", composite_before: "float", composite_after: "float",
  delta: "float", tier_before: "str", tier_after: "str", flags_before: "int", flags_after: "int", new_flags: "str" };
export function resultsCsv(rows, table) {
  const byIso = new Map(rows.map((r) => [r.iso3, r]));
  const hit = asRows(table).map((t) => ({ ...t, ...byIso.get(t.iso3) })).filter((r) => r.hit && !na(r.composite_before));
  const columns = Object.keys(CSV);
  return toCsv({ columns, dtypes: CSV, rows: hit.map((r) => columns.map((c) => (c === "new_flags" ? r.new_flags.join(" | ")
    : CSV[c] === "float" ? npRound(r[c], 2) : r[c]))) });
}
