// The country profile's own steps (app_pages/country.py), without the DOM: header line, peers, similar profiles,
// What-if, sensitivity, indicators and their CSV, refugee lists, the videos about a country, and a small Markdown
// renderer. Tables come in as row objects or {columns, rows}; config is data/config.json.
import { asMap, asRows, flagChanges, na, sensitivity, similar, simulate } from "../lib/scoring.js";
import { fixed, fmtPopulation, ordinal, pyRound } from "../lib/format.js";
import { esc } from "../lib/dom.js";

export const WHATIF_PRESETS = {
  "Currency crisis": { inflation: ["max", 40], reserves_months: ["min", 2], gdp_growth: ["min", -3], current_account: ["min", -6] },
  "Armed conflict": { battle_deaths_raw: ["max", 2500], wgi_pv: ["add", -15], displaced_share: ["max", 5] },
  "Democratic backsliding": { wgi_va: ["add", -15], wgi_rl: ["add", -10], wgi_cc: ["add", -10], wgi_ge: ["add", -5] },
  "Reform & recovery": { inflation: ["min", 5], gdp_growth: ["max", 4], wgi_ge: ["add", 10], wgi_rl: ["add", 10], wgi_cc: ["add", 10] },
};

// pandas median (missing values skipped; null when nothing is left)
export function median(xs) {
  const s = xs.filter((x) => !na(x)).sort((a, b) => a - b), m = s.length >> 1;
  return !s.length ? null : s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

// numpy's round(x, 1): scale, round half to even, scale back (DataFrame.round)
const npRound1 = (x) => {
  const y = x * 10, f = Math.floor(y), d = y - f;
  return (d < 0.5 ? f : d > 0.5 ? f + 1 : f % 2 === 0 ? f : f + 1) / 10;
};

// scoring._about: a head count as a person would say it (12.9 million, 345,000, 512)
export function about(n) {
  if (n >= 999500) return fixed(n / 1e6, 1).replace(/\.0$/, "") + " million";
  let x = n;
  if (n >= 1000) { // round(n, -3), half to even
    const r = n % 1000, lo = n - r;
    x = r > 500 ? lo + 1000 : r < 500 ? lo : (lo / 1000) % 2 === 0 ? lo : lo + 1000;
  }
  return fixed(x, 0, { group: true });
}

// ---- header ------------------------------------------------------------------------------------------------------
// The line under the name (after the top flag): region · income · people · GDP per person · thin-data warning.
// row: the master-table row; v: the values row; s: the scores row.
export function headerMeta(row, v, s, config) {
  const meta = [String(row.region), String(row.income), `${fmtPopulation(v.population ?? null)} people`];
  if (!na(v.gdppc)) meta.push(`$${fixed(v.gdppc, 0, { group: true })} per person (IMF, ${Math.trunc(v.gdppc__year)})`);
  const missing = config.pillars.filter((p) => na(row[p.key])).map((p) => p.short);
  if (row.coverage < 75 || missing.length) { // ui.thin_data
    meta.push(`data coverage ${fixed(s.coverage, 0)}%` + (missing.length ? `, no ${missing.join(" or ")} score` : "") + ": read with care");
  }
  return meta.join(" · ");
}

// The median of each pillar among the countries of a region (the ticks of the pillar chart)
export function regionalMedian(table, region, config) {
  const rows = asRows(table).filter((r) => r.region === region);
  return Object.fromEntries(config.pillars.map((p) => [p.key, median(rows.map((r) => r[p.key]))]));
}

// ---- peers -------------------------------------------------------------------------------------------------------
// The three "Compare with" groups: {label: rows}
export function peerGroups(table, row) {
  const rows = asRows(table);
  return {
    [`Region · ${row.region}`]: rows.filter((r) => r.region === row.region),
    [`Income group · ${row.income}`]: rows.filter((r) => r.income === row.income),
    "All countries": rows,
  };
}

// The place line, the 11 rows around the country (with ▶ and the group rank) and the caption under them
export function peerRanking(groupRows, iso3, name, composite) {
  const ranked = groupRows.filter((r) => !na(r.composite)).map((r, i) => [r, i])
    .sort((a, b) => b[0].composite - a[0].composite || a[1] - b[1]).map(([r]) => r); // stable, as the fixtures
  const position = ranked.findIndex((r) => r.iso3 === iso3);
  let place = null, sr = null;
  if (position >= 0) {
    const scores = ranked.map((r) => r.composite);
    place = `${position === 0 ? `Highest risk of ${ranked.length}` : `${ordinal(position + 1)} highest risk of ${ranked.length}`} in this group (group median ${fixed(median(scores), 0)}).`;
    sr = ` In the chart, ${name} scores ${fixed(composite, 0)} of 100; the group's scores run from ${fixed(Math.min(...scores), 0)} to ${fixed(Math.max(...scores), 0)}.`;
  }
  const start = Math.max(0, Math.min((position >= 0 ? position : 0) - 5, ranked.length - 11));
  const shown = ranked.slice(start, start + 11).map((r, k) => ({ ...r, name: r.iso3 === iso3 ? `▶ ${r.name}` : r.name, group_rank: start + k + 1 }));
  return { place, sr, start, rows: shown, ranked,
    caption: `▶ marks ${name}. Group ranks ${start + 1} to ${start + shown.length} of ${ranked.length}.` };
}

// The 8 most similar profiles: [{iso3, closeness}] (100 = the same four pillar scores)
export const similarRows = (scores, iso3, config) =>
  similar(scores, iso3, 8, config).map(({ iso3: i, distance }) => ({ iso3: i, closeness: Math.min(Math.max(100 - distance, 0), 100) }));

// The "Sensitivity to the weights" table, rounded as the page shows it
export const sensitivityRows = (values, iso3, weights, config) => sensitivity(values, iso3, weights, config)
  .map((r) => ({ Scenario: r.Scenario, Score: na(r.Score) ? null : npRound1(r.Score), Rank: na(r.Rank) ? null : r.Rank }));

// ---- What-if -----------------------------------------------------------------------------------------------------
// A slider value inside its range at 0.1, or the nearest death count on the list
export function snap(spec, value) {
  if (spec.kind === "select") return spec.options.reduce((best, o) => (Math.abs(o - value) < Math.abs(best - value) ? o : best));
  return pyRound(Math.min(Math.max(value, spec.min), spec.max), 1);
}

// The values a preset sets, from the country's own (controls: the country file's whatif.controls)
export function applyPreset(name, controls) {
  const specs = new Map(controls.map((c) => [c.key, c]));
  const out = {};
  for (const [key, [op, amount]] of Object.entries(WHATIF_PRESETS[name])) {
    const spec = specs.get(key);
    if (!spec) continue;
    const base = spec.current;
    out[key] = snap(spec, op === "max" ? Math.max(base, amount) : op === "min" ? Math.min(base, amount) : base + amount);
  }
  return out;
}

// What the What-if shows for some slider values (setTo: {key: value}; a key left out keeps its start value).
// s: the country's scores row under the visitor's weights; weights: the shares in use.
export function whatifResult(values, s, weights, iso3, name, controls, setTo, picked, config) {
  const changes = {}, moved = [];
  for (const p of config.pillars) {
    for (const spec of controls.filter((c) => c.pillar === p.key)) {
      const value = setTo[spec.key] ?? spec.current;
      if (value === spec.current) continue;
      moved.push(spec.label.split(" (")[0]);
      if (spec.key === "battle_deaths_raw") {
        changes.battle_deaths_raw = value;
        changes.battle_deaths_100k = na(spec.per_death) ? null : value * spec.per_death;
      } else changes[spec.key] = value;
    }
  }
  if (na(s.composite)) return { changes, moved, scored: false };
  const { scores, row } = simulate(values, iso3, changes, weights, config);
  const n = scores.get(iso3);
  const scoreDelta = n.composite - s.composite, rankDelta = n.rank - s.rank;
  const riskier = rankDelta < 0;
  const [worse, eased] = flagChanges(asMap(values).get(iso3), row, config);
  const caption = moved.length ? (picked ? `Scenario: ${picked}. ` : "") + "Changed: " + moved.join(", ") + "."
    : picked ? `Scenario: ${picked}. No value differs from ${name}'s own data.` : null;
  return {
    changes, moved, scored: true, composite: n.composite, rank: n.rank, n_ranked: n.n_ranked, tier: n.tier,
    pillars: Object.fromEntries(config.pillars.map((p) => [p.key, n[p.key]])),
    score_value: fixed(n.composite, 0),
    score_change: pyRound(scoreDelta, 1) ? fixed(scoreDelta, 1, { sign: true }) : null,
    places: rankDelta ? `${Math.abs(rankDelta)} place${Math.abs(rankDelta) > 1 ? "s" : ""} ${riskier ? "riskier" : "safer"}` : null,
    riskier, was: n.tier !== s.tier ? s.tier : null, scenario: n, flags: worse,
    new_flags: worse.map((f) => f.label), cleared: [...new Set(eased.map((f) => f.label))].sort(), caption,
  };
}

// ---- indicators ----------------------------------------------------------------------------------------------------
// Every indicator behind the score (the Data tab's table and its CSV). v: values row; s: scores row
export function indicatorRows(v, s, config) {
  const pillars = Object.fromEntries(config.pillars.map((p) => [p.key, p.short]));
  return config.indicators.map((ind) => {
    const raw = v[ind.key], yr = v[`${ind.key}__year`];
    return {
      Indicator: ind.short, Value: na(raw) ? "—" : fixed(raw, ind.decimals, { group: true }), "Risk score": s[`n_${ind.key}`] ?? null,
      Year: na(yr) ? "—" : String(Math.trunc(yr)), Pillar: pillars[ind.pillar], Unit: ind.unit, Source: ind.source, Data: ind.url,
      "Full name": ind.label, Direction: ind.higher_is_riskier ? "Higher = riskier" : "Lower = riskier",
    };
  });
}

// A float as pandas writes it in a CSV (Python repr: 93.0, 0.64, 1e-05)
function pyFloat(x) {
  if (na(x)) return "";
  if (Number.isInteger(x) && Math.abs(x) < 1e16) return x.toFixed(1);
  const a = Math.abs(x);
  if (a >= 1e16 || a < 1e-4) {
    const [m, e] = x.toExponential().split("e");
    return `${m}e${e[0] === "-" ? "-" : "+"}${e.replace(/^[+-]/, "").padStart(2, "0")}`;
  }
  return String(x);
}
const csvField = (f) => (/[",\r\n]/.test(f) ? `"${f.replace(/"/g, '""')}"` : f);

// "Download indicators (CSV)" (without the byte-order mark the download adds)
export function indicatorsCsv(v, s, name, iso3, config) {
  const rows = indicatorRows(v, s, config).map((r) => ({ ...r, Country: name, ISO3: iso3 }));
  const cols = Object.keys(rows[0]);
  return [cols, ...rows.map((r) => cols.map((c) => (c === "Risk score" ? pyFloat(r[c]) : String(r[c]))))]
    .map((line) => line.map(csvField).join(",")).join("\n") + "\n";
}

// ---- refugees ------------------------------------------------------------------------------------------------------
// The two lists under the Peers map: {origin|host: {rows: [{iso3, value}], total}, year}. names: Map iso3 -> name
export function flowLists(flows, names, iso3) {
  const all = asRows(flows);
  const year = Math.max(...all.map((f) => f.year));
  const out = { year };
  for (const [side, other] of [["origin", "host"], ["host", "origin"]]) {
    const mine = all.filter((f) => f[side] === iso3);
    const rows = mine.filter((f) => names.has(f[other])).map((f, i) => [f, i])
      .sort((a, b) => b[0].value - a[0].value || a[1] - b[1]).slice(0, 10)
      .map(([f]) => ({ iso3: f[other], name: names.get(f[other]), value: f.value }));
    const total = mine.reduce((a, f) => a + f.value, 0);
    out[side] = { rows, total: `${total >= 1000 ? "About " : ""}${about(total)} people in total (${year}, UNHCR: refugees, asylum seekers and others in need of international protection).` };
  }
  return out;
}

// ---- videos ----------------------------------------------------------------------------------------------------------
// Python's \b (Unicode word characters), so "U.S." and "Côte d'Ivoire" match where the app matches them
const W = "[\\p{L}\\p{N}_]";
const B = `(?:(?<=${W})(?!${W})|(?<!${W})(?=${W}))`;
const reEsc = (s) => s.replace(/[\^$\\.*+?()[\]{}|/]/g, "\\$&");
const isUpper = (t) => t === t.toUpperCase() && t !== t.toLowerCase();

// ui.videos_about: the videos whose title or description name the country (names: Map iso3 -> name)
export function videosAbout(videos, iso3, names, newsName, official, aliases = []) {
  const name = names.get(iso3) ?? iso3;
  const terms = new Set([name, newsName ?? name, ...(official ? [official] : [])]);
  const loose = [...new Set([...terms, ...aliases])].filter((t) => !isUpper(t));
  const exact = aliases.filter(isUpper);
  const byLength = (list) => [...list].sort((a, b) => b.length - a.length);
  const pattern = new RegExp(`${B}(${byLength(loose).map(reEsc).join("|")})${B}`, "iu");
  const patternExact = exact.length ? new RegExp(`${B}(${exact.map(reEsc).join("|")})${B}`, "u") : null;
  const longer = [...names.values()].filter((n) => n !== name && n.toLowerCase().includes(name.toLowerCase()));
  const strip = longer.length ? new RegExp(byLength(longer).map(reEsc).join("|"), "giu") : null;
  return (videos ?? []).filter((v) => {
    let text = `${v.title ?? ""} \n ${v.description ?? ""}`;
    if (strip) text = text.replace(strip, " ");
    return pattern.test(text) || (patternExact !== null && patternExact.test(text));
  });
}

// ---- Markdown ----------------------------------------------------------------------------------------------------------
// The Markdown the app's texts use (assessments, the real-life reading), as HTML with every text escaped:
// headings, paragraphs, lists, tables, rules, **bold**, *italic*, `code`, [links](https://…) and bare https:// links.
const link = (url, html) => `<a href="${esc(url)}" target="_blank" rel="noopener">${html}</a>`;

export function inline(text) {
  const kept = [];
  const keep = (html) => `\u0000${kept.push(html) - 1}\u0000`;
  const s = String(text ?? "")
    .replace(/`([^`]+)`/g, (_, c) => keep(`<code>${esc(c)}</code>`))
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_, t, u) => keep(link(u, inline(t))))
    .replace(/https?:\/\/[^\s<>]*[^\s<>.,;:!?)'"*_]/g, (u) => keep(link(u, esc(u))));
  return esc(s)
    .replace(/\\([\\`*_{}[\]()#+\-.!$])/g, "$1")
    .replace(/\*\*(?=\S)(.+?)(?<=\S)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])/g, "$1<em>$2</em>")
    .replace(/(^|[^\w])_(?=\S)(.+?)(?<=\S)_(?!\w)/g, "$1<em>$2</em>")
    .replace(/\u0000(\d+)\u0000/g, (_, i) => kept[Number(i)]);
}

const LIST = /^\s*([-*+]|\d+[.)])\s+(.*)$/;
const RULE = /^\s*([-*_])(\s*\1){2,}\s*$/;
const DIVIDER = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/;
const cells = (line) => line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => inline(c.trim()));

export function markdown(src) {
  const lines = String(src ?? "").replace(/\r\n?/g, "\n").split("\n");
  const html = [];
  let i = 0;
  const isBlock = (l) => /^#{1,6}\s/.test(l) || RULE.test(l) || LIST.test(l);
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    const heading = line.match(/^(#{1,6})\s+(.*?)\s*#*\s*$/);
    if (heading) { html.push(`<h${heading[1].length}>${inline(heading[2])}</h${heading[1].length}>`); i++; continue; }
    if (RULE.test(line)) { html.push("<hr>"); i++; continue; }
    if (line.includes("|") && DIVIDER.test(lines[i + 1] ?? "")) {
      const head = cells(line);
      const body = [];
      for (i += 2; i < lines.length && lines[i].includes("|") && lines[i].trim(); i++) body.push(cells(lines[i]));
      html.push(`<div class="sg-cp-md-table"><table><thead><tr>${head.map((c) => `<th>${c}</th>`).join("")}</tr></thead><tbody>`
        + body.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("") + "</tbody></table></div>");
      continue;
    }
    const item = line.match(LIST);
    if (item) {
      const ordered = /\d/.test(item[1]);
      const items = [];
      while (i < lines.length) {
        const m = lines[i].match(LIST);
        if (m && /\d/.test(m[1]) === ordered) { items.push(m[2]); i++; }
        else if (lines[i].trim() && /^\s+\S/.test(lines[i]) && items.length) { items[items.length - 1] += `\n${lines[i].trim()}`; i++; }
        else break;
      }
      const start = ordered && parseInt(item[1], 10) !== 1 ? ` start="${parseInt(item[1], 10)}"` : "";
      const tag = ordered ? "ol" : "ul";
      html.push(`<${tag}${start}>${items.map((t) => `<li>${breaks(t)}</li>`).join("")}</${tag}>`);
      continue;
    }
    const para = [];
    while (i < lines.length && lines[i].trim() && !isBlock(lines[i]) && !(lines[i].includes("|") && DIVIDER.test(lines[i + 1] ?? ""))) para.push(lines[i++]);
    html.push(`<p>${breaks(para.join("\n"))}</p>`);
  }
  return html.join("");
}

// A line ending in two spaces (or a backslash) breaks the line; other newlines are spaces
const breaks = (text) => text.split("\n").map((l, k, all) => {
  const hard = k < all.length - 1 && /( {2,}|\\)$/.test(l);
  return inline(hard ? l.replace(/( {2,}|\\)$/, "") : l) + (k < all.length - 1 ? (hard ? "<br>" : "\n") : "");
}).join("");
