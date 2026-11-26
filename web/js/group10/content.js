// Ports of prm/content.py (assessment Markdown, the events.csv line, front matter), config.estimative_term and the
// assessment builder's figures for the driver boxes (app_pages/builder.py _facts).
import { asMap, na, redFlags } from "../lib/scoring.js";
import { fixed } from "../lib/format.js";

// Python's whitespace (str.strip / str.split)
const WS = "\\t\\n\\x0b\\x0c\\r\\x1c-\\x1f \\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000";
const STRIP = new RegExp(`^[${WS}]+|[${WS}]+$`, "g");
const SPLIT = new RegExp(`[${WS}]+`);
export const pyStrip = (s) => String(s).replace(STRIP, "");
const lstrip = (s) => String(s).replace(new RegExp(`^[${WS}]+`), "");
const QUOTED = new RegExp(`^[${WS}]*(["'])([^\\n]*?)\\1[${WS}]*(?:#[^\\n]*)?$`);

export const OUTLOOKS = ["Improving", "Stable", "Deteriorating"];
export const CONFIDENCE = ["Low", "Moderate", "High"];

// The indicators behind each driver box when the builder fills in the latest figures
export const DRIVER_FACTS = {
  drv_political: ["wgi_va", "wgi_ge", "wgi_rl", "wgi_cc", "wgi_rq"],
  drv_security: ["wgi_pv", "battle_deaths_100k", "homicide"],
  drv_economic: ["inflation", "gdp_growth", "gov_debt", "fiscal_balance", "current_account", "reserves_months"],
  drv_social: ["unemployment", "youth_unemployment", "displaced_share"],
};

// config.estimative_term: the ICD 203 term for a probability (0-100)
export function estimativeTerm(p, config) {
  const terms = config.ESTIMATIVE_LANGUAGE;
  for (const [term, , , high] of terms) if (p <= high) return term;
  return terms[terms.length - 1][0];
}

// One Markdown table cell: one line, "|" escaped
const cell = (text) => String(text).split(SPLIT).filter(Boolean).join(" ").replace(/\|/g, "\\|");
const bullets = (text) => String(text).split("\n").filter((w) => pyStrip(w)).map((w) => `- ${pyStrip(w)}`).join("\n") || "- ";
const localDay = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

// content.build_assessment_markdown: the builder's form as the standard assessment file
export function buildAssessmentMarkdown(f) {
  const g = (k, d = "") => f[k] ?? d;
  const judgments = (f.judgments ?? []).map((j, i) => (pyStrip(j.text ?? "") ? `${i + 1}. ${pyStrip(j.text)} (${j.term}, ~${j.probability}%)` : null))
    .filter((x) => x !== null).join("\n") || "1. ";
  const scenarios = (f.scenarios ?? []).map((s) => `| ${s.name} | ${s.probability}% | ${cell(s.description)} | ${cell(s.signposts)} |`).join("\n");
  return `---
country: ${g("country")}
iso3: ${g("iso3")}
author: "${g("author")}"
date: ${f.date || localDay()}
analyst_rating: ${g("analyst_rating")}
outlook: ${g("outlook")}
confidence: ${g("confidence")}
horizon: ${g("horizon", "12 months")}
model_score_at_writing: ${g("model_score")}
---

## Bottom line up front
${pyStrip(g("bluf"))}

## Key judgments
${judgments}

## Drivers
### Political
${pyStrip(g("drv_political"))}

### Security
${pyStrip(g("drv_security"))}

### Economic
${pyStrip(g("drv_economic"))}

### Social
${pyStrip(g("drv_social"))}

## Scenarios (${g("horizon", "12 months")})
| Scenario | Probability | What it looks like | Signposts |
|---|---|---|---|
${scenarios}

## Indicators to watch
${bullets(g("indicators_to_watch"))}

## Why my rating differs from the model
${pyStrip(g("divergence")) || "My rating matches the model tier."}

## Implications
${pyStrip(g("implications"))}

## Sources
${bullets(g("sources"))}
`;
}

// content.csv_row: one events.csv line (standard CSV quoting, no line end)
const EVENT_COLUMNS = ["date", "iso3", "country", "event", "category", "significance", "source_url", "notes"];
export const csvRow = (values) => EVENT_COLUMNS.map((c) => {
  const s = String(values[c] ?? "");
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}).join(",");

// content.parse_front_matter: [meta, body]
export function parseFrontMatter(text) {
  const meta = {};
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  if (pyStrip(lines[0]) !== "---") return [meta, text];
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i];
    if (pyStrip(line) === "---") return [meta, pyStrip(lines.slice(i + 1).join("\n"))];
    if (line.includes(":") && !lstrip(line).startsWith("#")) {
      const at = line.indexOf(":");
      const value = line.slice(at + 1);
      const q = QUOTED.exec(value);
      meta[pyStrip(line.slice(0, at)).toLowerCase()] = q ? q[2]
        : pyStrip(value.split(" #")[0]).replace(/^"+|"+$/g, "").replace(/^'+|'+$/g, "");
    }
  }
  return [{}, text]; // no closing '---': everything is body
}

// The figures behind one driver box, as bullet points to rewrite into analysis ("" when there are none)
export function facts(iso3, keys, values, scores, config) {
  const v = asMap(values).get(iso3) ?? {}, s = asMap(scores).get(iso3) ?? {};
  const flags = Object.fromEntries(redFlags(v, config).map((f) => [f.key, f.label]));
  const lines = [];
  for (const key of keys) {
    const ind = config.indicators.find((i) => i.key === key);
    const raw = v[key], year = v[`${key}__year`], risk = s[`n_${key}`];
    if (na(raw)) continue;
    let line = `- ${ind.short}: ${fixed(raw, ind.decimals, { group: true })} ${ind.unit}${na(year) ? "" : ` (${Math.trunc(year)})`}`;
    if (!na(risk)) line += `, risk score ${fixed(risk, 0)}/100`;
    if (key in flags || (key === "battle_deaths_100k" && "battle_deaths_raw" in flags)) line += ` ⚑ ${flags[key] || flags.battle_deaths_raw}`;
    lines.push(line);
  }
  return lines.length ? [...lines, "→ Why, and which way is it heading? (your analysis)"].join("\n") : "";
}
