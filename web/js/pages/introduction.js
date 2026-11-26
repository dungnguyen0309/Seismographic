// Introduction: what Seismographic is, how the score is built, and how to start (app_pages/intro.py).
import * as ui from "../lib/ui.js";
import { h } from "../lib/dom.js";
import { na } from "../lib/scoring.js";
import { fixed } from "../lib/format.js";
import { CAVEATS } from "../lib/interpret.js";
import { card, cardGrid } from "../charts/reference.js";

export const title = "Introduction";
export const required = [];

const STEPS = (n) => [
  ["1", "Indicators", `${n} measures, such as inflation, battle deaths and rule of law, from the World Bank, IMF, UNHCR and UCDP.`],
  ["2", "Risk scores", "Each indicator becomes a 0–100 risk score: where the country sits among all countries that year (0 = safest, 100 = riskiest)."],
  ["3", "Pillars", "Indicators are averaged into four pillars: stability, governance, economy and social pressure."],
  ["4", "Composite", "A weighted average of the pillars gives the headline score from 0 to 100, which sets the country's tier."],
];

const QUICK_START = [
  "Open the Global overview and click any country on the globe to see its score.",
  "On its Country profile, What it means in real life (under the Summary) gives the numbers on the ground.",
  "Move between pages with the sidebar or the bar at the bottom of every page. Find in the bar searches every country and page. "
    + "The country on the left of the bar is the last one you opened in this visit (on a new visit, the first country you follow).",
  "Press ☆ Follow on the countries you care about: they stay at the top of the Global overview, in this browser.",
  "The Glossary & legend explains every term.",
];

export async function render(main, ctx) {
  try { sessionStorage.setItem("sg-explored", "1"); } catch { /* storage blocked: the overview keeps its Introduction link */ }
  await ui.loadCss("/css/reference.css");
  const c = ctx.core.config;
  const year = ctx.core.meta.year;
  const nScored = [...ctx.scores().values()].filter((r) => !na(r.composite)).length;
  const shares = ctx.weights();
  const nInd = c.indicators.length;

  const stats = [[nScored, "countries scored"], [nInd, "indicators"], [c.pillars.length, "pillars"], [c.INDEX_SOURCES.length, "open datasets"],
    [year - c.HISTORY_START + 1, `years of history (${c.HISTORY_START}–${year})`]];
  const pillars = c.pillars.map((p) => card(
    h("div", { class: "sg-ref-pillar-head" }, h("span", { style: `color:${c.PILLAR_COLORS[p.key]}` }, p.label),
      h("span", null, `${fixed((shares[p.key] / 100) * 100, 0)}% of the score`)),
    h("div", { class: "sg-ref-pillar-q" }, p.question),
    h("div", { class: "sg-ref-pillar-ind" }, c.indicators.filter((i) => i.pillar === p.key).map((i) => i.short).join(", "))));

  main.append(...[
    ui.weightsNote(ctx),
    ui.hero(title),
    h("h2", null, "What it is"),
    h("p", null, `${c.APP_TITLE} is an open-data index of political, governance, economic and social risk for ${nScored} countries and territories, `
      + "built like the country-risk models professionals use. Every figure comes from a public source, and the Methodology page documents each step."),
    cardGrid(stats.map(([n, label]) => card(h("div", { class: "sg-ref-big" }, String(n)), h("div", { class: "sg-ref-small" }, label))), 140),
    h("h2", null, "How the score is built"),
    cardGrid(STEPS(nInd).map(([n, name, text]) => card(h("div", { class: "sg-ref-card-title" }, `${n}. ${name}`), h("div", { class: "sg-ref-card-text" }, text)))),
    h("p", null, "Tiers: ", c.tiers.flatMap((t, i) => [i ? " " : null, ui.tierBadge(t.label)])),
    h("p", null, "Red flags and an analyst's judgment sit on top of the score. Red flags mark absolute danger lines, such as inflation above 20% "
      + "or an active war, wherever a country ranks. An analyst assessment can add judgment the data can't capture. Scores are relative, so a "
      + "low score means safer than most countries; such a country can still be dangerous."),
    h("h2", { class: "sg-ref-help-h" }, "The four pillars", ui.helpMark(ctx.customLabel() ? "Your weights from Index weights in the sidebar."
      : "Default weights. Change them under Index weights in the sidebar.")),
    cardGrid(pillars, 260),
    h("h2", null, "Quick start"),
    h("ol", { class: "sg-ref-list" }, QUICK_START.map((t) => h("li", null, t))),
    ui.pageLink("/", "Go to the global overview", "arrow_forward"),
    h("h2", null, "Before you rely on it"),
    h("ul", { class: "sg-ref-list" }, CAVEATS.map((t) => h("li", null, t))),
    ui.cite(["index", "oecd_jrc"]),
    ui.footer(true),
  ].filter(Boolean));
}
