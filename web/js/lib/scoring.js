// Port of prm/scoring.py. Tables come in as {columns, rows} (or a Map<iso3, row object>); missing is null.
// Functions take the parsed data/config.json as their last argument, or use the one given to setConfig().
import { fixed, pyRound, signed, ordinal } from "./format.js";

let CFG = null;
export const setConfig = (c) => { CFG = c; };
const cfgOf = (c) => {
  const x = c ?? CFG;
  if (!x) throw new Error("scoring: pass config (data/config.json) or call setConfig first");
  return x;
};

export const na = (v) => v === null || v === undefined || Number.isNaN(v);

// ---- tables ----------------------------------------------------------------------------------------------
export const asRows = (t) => (Array.isArray(t) ? t : t instanceof Map ? [...t.values()]
  : t.rows.map((r) => Object.fromEntries(t.columns.map((c, i) => [c, r[i]]))));
export const asMap = (t, key = "iso3") => (t instanceof Map ? t : new Map(asRows(t).map((r) => [r[key], r])));
export const toTable = (rows, columns) => {
  const list = rows instanceof Map ? [...rows.values()] : rows;
  const cols = columns ?? Object.keys(list[0] ?? {});
  return { columns: cols, rows: list.map((r) => cols.map((c) => r[c] ?? null)) };
};

// ---- normalising --------------------------------------------------------------------------------------------
// pandas Series.quantile, linear interpolation (xs sorted ascending)
function quantile(xs, q) {
  const pos = (xs.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.min(lo + 1, xs.length - 1);
  return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo);
}
const capOf = (x, config) => {
  const positive = x.filter((v) => v > 0).sort((a, b) => a - b);
  return positive.length ? quantile(positive, config?.LOG_CAP_QUANTILE ?? CFG?.LOG_CAP_QUANTILE ?? 0.9) : 0;
};
const logScale = (v, cap) => (cap > 0 ? Math.min((Math.log1p(Math.max(v, 0)) / cap) * 100, 100) : 0);

// 0-100 risk score (100 = riskiest) within the list; ties share the lowest rank ("min")
export function normalise(values, higherIsRiskier, method = "percentile", config = null) {
  const valid = values.filter((v) => !na(v));
  if (valid.length < 2) return values.map(() => null);
  if (method === "log") {
    const cap = capOf(valid.map((v) => Math.log1p(Math.max(v, 0))), config);
    return values.map((v) => (na(v) ? null : higherIsRiskier ? logScale(v, cap) : 100 - logScale(v, cap)));
  }
  return values.map((v) => {
    if (na(v)) return null;
    const rank = 1 + valid.reduce((n, o) => n + (higherIsRiskier ? o < v : o > v), 0);
    return ((rank - 1) / (valid.length - 1)) * 100;
  });
}

// Like normalise, but every value is scored against a fixed reference distribution (the stress test, what-if)
export function normaliseAgainst(values, reference, higherIsRiskier, method = "percentile", config = null) {
  const ref = reference.filter((v) => !na(v));
  if (ref.length < 2) return values.map(() => null);
  if (method === "log") {
    const cap = capOf(ref.map((v) => Math.log1p(Math.max(v, 0))), config);
    return values.map((v) => (na(v) ? null : higherIsRiskier ? logScale(v, cap) : 100 - logScale(v, cap)));
  }
  const ordered = Float64Array.from(ref).sort();
  const search = (v, right) => {
    let lo = 0, hi = ordered.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (right ? ordered[mid] <= v : ordered[mid] < v) lo = mid + 1; else hi = mid;
    }
    return lo;
  };
  return values.map((v) => {
    if (na(v)) return null;
    const less = higherIsRiskier ? search(v, false) : ordered.length - search(v, true);
    return Math.min(Math.max((less / (ordered.length - 1)) * 100, 0), 100);
  });
}

export function tierFor(score, config = null) {
  if (na(score)) return null;
  const tiers = cfgOf(config).tiers;
  let label = tiers[0].label;
  for (const t of tiers) if (score >= t.lower) label = t.label;
  return label;
}

export const defaultWeights = (config = null) => Object.fromEntries(cfgOf(config).pillars.map((p) => [p.key, Number(p.default_weight)]));

// "?w=50,20,20,10" as ui.decode_weights: four ints, 0..100, multiples of 5, sum above 0; else null
export function decodeWeights(text, config = null) {
  const pillars = cfgOf(config).pillars;
  const parts = String(text).split(",");
  if (parts.length !== pillars.length || !parts.every((x) => /^\s*[+-]?\d+\s*$/.test(x))) return null;
  const nums = parts.map(Number);
  if (nums.some((x) => x < 0 || x > 100 || x % 5) || !nums.reduce((a, b) => a + b, 0)) return null;
  return Object.fromEntries(pillars.map((p, i) => [p.key, nums[i]]));
}

// ui.weights_tuple: weights as shares of 100 (only proportions count)
export function weightShares(w, config = null) {
  const pillars = cfgOf(config).pillars;
  let total = pillars.reduce((a, p) => a + (w[p.key] ?? 0), 0);
  if (total <= 0) { w = defaultWeights(config); total = pillars.reduce((a, p) => a + w[p.key], 0); }
  return Object.fromEntries(pillars.map((p) => [p.key, (w[p.key] * 100) / total]));
}

// ---- composite from pillars (shared by computeScores and historyFor) ---------------------------------------------------
function composite(pillarScores, w, config) {
  let wsum = 0, num = 0, count = 0;
  for (const [i, p] of pillarScores.entries()) {
    if (na(p)) continue;
    count++;
    wsum += w[i];
    num += p * w[i];
  }
  return count >= config.COMPOSITE_MIN_PILLARS && wsum > 0 ? num / wsum : null;
}
const pillarWeights = (weights, config) => {
  let w = weights ?? {};
  if (config.pillars.reduce((a, p) => a + Math.max(w[p.key] ?? 0, 0), 0) <= 0) w = defaultWeights(config);
  return config.pillars.map((p) => Math.max(Number(w[p.key] ?? 0), 0));
};
const ranksMin = (comps) => comps.map((c) => (na(c) ? null : 1 + comps.reduce((n, o) => n + (!na(o) && o > c), 0)));

// Indicator scores (n_*), pillar scores, composite, tier, rank and coverage; Map<iso3, row>.
// reference: score the values against this table's distribution instead of their own.
export function computeScores(values, weights = null, { reference = null, config = null } = {}) {
  const cfg = cfgOf(config);
  const vals = asMap(values);
  const ref = reference ? asMap(reference) : null;
  const isos = [...vals.keys()];
  const rows = isos.map(() => ({}));
  const column = (m, key) => [...m.values()].map((r) => r[key] ?? null);
  for (const ind of cfg.indicators) {
    const col = column(vals, ind.key);
    const out = ref
      ? normaliseAgainst(col, column(ref, ind.key), ind.higher_is_riskier, ind.norm, cfg)
      : normalise(col, ind.higher_is_riskier, ind.norm, cfg);
    out.forEach((v, i) => { rows[i][`n_${ind.key}`] = v; });
  }
  for (const p of cfg.pillars) {
    const cols = cfg.indicators.filter((i) => i.pillar === p.key).map((i) => `n_${i.key}`);
    const needed = Math.max(1, Math.ceil(cols.length * cfg.PILLAR_MIN_SHARE));
    for (const r of rows) {
      const ok = cols.map((c) => r[c]).filter((v) => !na(v));
      r[p.key] = ok.length >= needed ? ok.reduce((a, b) => a + b, 0) / ok.length : null;
    }
  }
  const w = pillarWeights(weights, cfg);
  const comps = rows.map((r) => composite(cfg.pillars.map((p) => r[p.key]), w, cfg));
  const ranks = ranksMin(comps);
  const nRanked = comps.filter((c) => !na(c)).length;
  rows.forEach((r, i) => {
    r.composite = comps[i];
    r.coverage = (cfg.indicators.filter((ind) => !na(r[`n_${ind.key}`])).length / cfg.indicators.length) * 100;
    r.tier = tierFor(comps[i], cfg);
    r.rank = ranks[i];
    r.n_ranked = nRanked;
  });
  return new Map(isos.map((iso, i) => [iso, rows[i]]));
}

// The index for every year, recomputed from the stored pillars (as data.get_history does for these weights)
export function historyFor(history, weights, config = null) {
  const cfg = cfgOf(config);
  const rows = asRows(history).map((r) => ({ ...r }));
  const w = pillarWeights(weights, cfg);
  const byYear = new Map();
  for (const r of rows) {
    r.composite = composite(cfg.pillars.map((p) => r[p.key]), w, cfg);
    r.tier = tierFor(r.composite, cfg);
    if (!byYear.has(r.year)) byYear.set(r.year, []);
    byYear.get(r.year).push(r);
  }
  for (const list of byYear.values()) {
    const ranks = ranksMin(list.map((r) => r.composite));
    const n = list.filter((r) => !na(r.composite)).length;
    list.forEach((r, i) => { r.rank = ranks[i]; r.n_ranked = n; });
  }
  return toTable(rows, history.columns ?? Object.keys(rows[0] ?? {}));
}

// ---- flags -----------------------------------------------------------------------------------------------------------------
const OPS = { ">=": (a, b) => a >= b, ">": (a, b) => a > b, "<=": (a, b) => a <= b, "<": (a, b) => a < b };

// Absolute-threshold warnings for one country (most severe per indicator only)
export function redFlags(row, config = null) {
  const cfg = cfgOf(config);
  const flags = [], seen = new Set();
  for (const [key, op, threshold, severity, label] of cfg.RED_FLAGS) {
    if (seen.has(key)) continue;
    const value = row[key];
    if (na(value)) continue;
    if (OPS[op](Number(value), threshold)) {
      seen.add(key);
      const short = cfg.FLAG_SHORT.find((f) => f.key === key && f.threshold === threshold)?.short ?? label;
      flags.push({ key, severity, label, value: Number(value), short });
    }
  }
  return flags.sort((a, b) => cfg.SEVERITY_ORDER[a.severity] - cfg.SEVERITY_ORDER[b.severity]);
}

// Flags new or more severe in `after`, and flags of `before` that went or eased: [worse, eased]
export function flagChanges(before, after, config = null) {
  const cfg = cfgOf(config);
  const rank = cfg.SEVERITY_ORDER;
  const was = new Map(redFlags(before, cfg).map((f) => [f.key, f]));
  const now = new Map(redFlags(after, cfg).map((f) => [f.key, f]));
  const worse = [...now].filter(([k, f]) => !was.has(k) || rank[f.severity] < rank[was.get(k).severity]).map(([, f]) => f);
  const eased = [...was].filter(([k, f]) => !now.has(k) || rank[now.get(k).severity] > rank[f.severity]).map(([, f]) => f);
  return [worse, eased];
}

// Red flags per country, plus the falling political-stability trend (wgiTrend: {iso3: {change}})
export function flagCounts(values, wgiTrend = null, config = null) {
  const cfg = cfgOf(config);
  const out = {};
  for (const [iso, row] of asMap(values)) {
    const t = wgiTrend?.[iso];
    out[iso] = redFlags(row, cfg).length + (t && t.change <= -cfg.WGI_TREND_THRESHOLD ? 1 : 0);
  }
  return out;
}

// ---- what-if, sensitivity, similar --------------------------------------------------------------------------------------------
// Change some of one country's raw values and re-score everyone: {scores, row}
export function simulate(values, iso3, changes, weights, config = null) {
  const scenario = new Map(asMap(values));
  const row = { ...scenario.get(iso3), ...changes };
  scenario.set(iso3, row);
  return { scores: computeScores(scenario, weights, { config }), row };
}

// The country's score and rank under your weights, equal weights, and each pillar dropped in turn
export function sensitivity(values, iso3, weights, config = null) {
  const cfg = cfgOf(config);
  const vals = asMap(values);
  const at = (w, scenario) => {
    const r = computeScores(vals, w, { config: cfg }).get(iso3);
    return { Scenario: scenario, Score: r.composite, Rank: r.rank };
  };
  const rows = [at(weights, "Your weights"), at(Object.fromEntries(cfg.pillars.map((p) => [p.key, 25])), "Equal weights")];
  for (const p of cfg.pillars) {
    const alt = { ...weights, [p.key]: 0 };
    if (Object.values(alt).reduce((a, b) => a + b, 0) <= 0) continue;
    rows.push(at(alt, `Without ${p.short}`));
  }
  return rows;
}

// The n countries whose four pillar scores are closest (Euclidean distance): [{iso3, distance}]
export function similar(scores, iso3, n = 6, config = null) {
  const keys = cfgOf(config).pillars.map((p) => p.key);
  const block = [...asMap(scores)].filter(([, r]) => keys.every((k) => !na(r[k])));
  const me = block.find(([i]) => i === iso3)?.[1];
  if (!me) return [];
  return block.filter(([i]) => i !== iso3)
    .map(([i, r]) => ({ iso3: i, distance: Math.sqrt(keys.reduce((a, k) => a + (r[k] - me[k]) ** 2, 0)) }))
    .sort((a, b) => a.distance - b.distance).slice(0, n);
}

// ---- the automatic brief ----------------------------------------------------------------------------------------------------------
// A head count as a person would say it: 12.9 million, 345,000, or the exact figure below a thousand
function about(n) {
  if (n >= 999500) return fixed(n / 1e6, 1).replace(/\.0$/, "") + " million";
  let x = n;
  if (n >= 1000) { // round(n, -3), half to even
    const r = n % 1000, lo = n - r;
    x = r > 500 ? lo + 1000 : r < 500 ? lo : (lo / 1000) % 2 === 0 ? lo : lo + 1000;
  }
  return fixed(x, 0, { group: true });
}

function median(xs) {
  const s = [...xs].sort((a, b) => a - b), m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

// Plain-English, data-only observations for one country. nextGrowth: the IMF's growth figure for year + 1 (or null).
export function countryBrief(iso3, name, values, scores, countries, year, { wgiTrend = null, nextGrowth = null, config = null } = {}) {
  const cfg = cfgOf(config);
  const lines = [];
  const sc = asMap(scores), vals = asMap(values), cn = asMap(countries);
  if (!sc.has(iso3)) return lines;
  const s = sc.get(iso3), v = vals.get(iso3) ?? {};
  const f0 = (x) => fixed(x, 0), f1 = (x) => fixed(x, 1);

  if (!na(s.composite)) {
    lines.push(`${name} ranks ${ordinal(s.rank)} of ${s.n_ranked} countries on the composite index (score ${f0(s.composite)}/100, ${s.tier} tier; 1st = highest risk).`);
    const region = cn.get(iso3).region;
    const peerScores = [...cn.values()].filter((c) => c.region === region && sc.has(c.iso3) && !na(sc.get(c.iso3).composite)).map((c) => sc.get(c.iso3).composite);
    if (peerScores.length > 1) {
      const peerRank = peerScores.filter((x) => x > s.composite).length + 1;
      lines.push(`Within ${region} it is ${ordinal(peerRank)} of ${peerScores.length} (regional median ${f0(median(peerScores))}).`);
    }
  } else lines.push(`There is not enough data to compute a composite score for ${name}.`);

  const ps = cfg.pillars.filter((p) => !na(s[p.key]));
  if (ps.length >= 2) {
    let worst = ps[0], best = ps[0];
    for (const p of ps) { if (s[p.key] > s[worst.key]) worst = p; if (s[p.key] < s[best.key]) best = p; }
    lines.push(`Highest-risk pillar: ${worst.short} (${f0(s[worst.key])}); lowest-risk pillar: ${best.short} (${f0(s[best.key])}).`);
  }

  if (wgiTrend) {
    const change = pyRound(wgiTrend.change, 1);
    const direction = change > 0 ? "improved" : change < 0 ? "deteriorated" : "was unchanged";
    lines.push(`Political stability (World Bank governance indicators) ${direction} from ${f1(wgiTrend.start)} (${wgiTrend.start_year}) to ${f1(wgiTrend.end)} (${wgiTrend.end_year}), a change of ${signed(change)} points.`);
  }

  const growth = v.gdp_growth, infl = v.inflation;
  if (!na(growth) && !na(infl)) {
    const gy = Math.trunc(v.gdp_growth__year), iy = Math.trunc(v.inflation__year);
    let text;
    if (gy === year && iy === year) text = `The IMF projects real GDP growth of ${f1(growth)}% and inflation of ${f1(infl)}% for ${year}`;
    else if (gy === iy) text = `The latest IMF figures, for ${gy}, show real GDP growth of ${f1(growth)}% and inflation of ${f1(infl)}%`;
    else text = `The latest IMF figures show real GDP growth of ${f1(growth)}% (${gy}) and inflation of ${f1(infl)}% (${iy})`;
    if (!na(nextGrowth)) text += `, with growth of ${f1(nextGrowth)}% in ${year + 1}`;
    lines.push(text + ".");
  }

  const bd = v.battle_deaths_raw, bdYear = v.battle_deaths_100k__year;
  if (!na(bd) && !na(bdYear)) {
    lines.push(bd > 0 ? `UCDP recorded ${fixed(bd, 0, { group: true })} battle-related deaths in ${Math.trunc(bdYear)}.`
      : `No battle-related deaths from state-based conflict were recorded in ${Math.trunc(bdYear)}.`);
  }

  const share = v.displaced_share;
  if (!na(share) && share >= 0.5) {
    lines.push(`About ${about(v.displaced_total)} people (${f1(share)}% of the population) from ${name} were forcibly displaced in ${Math.trunc(v.displaced_share__year)} (UNHCR).`);
  }

  if (!na(s.coverage) && s.coverage < 75) lines.push(`Only ${f0(s.coverage)}% of indicators are available, so treat the score with caution.`);
  return lines;
}
