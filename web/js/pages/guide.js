// Guide: what Seismographic's numbers mean in real life, and how to put them to work (app_pages/guide.py).
import * as ui from "../lib/ui.js";
import * as follow from "../lib/follow.js";
import { h, clear } from "../lib/dom.js";
import { asRows } from "../lib/scoring.js";
import { fixed } from "../lib/format.js";
import { AUDIENCES, PILLAR_MEANING, countryReading, readingMarkdown } from "../lib/interpret.js";
import { flagRows, localTabs, staticTable, tierRows } from "../charts/reference.js";

export const title = "Guide";
export const required = ["data/events.json", "data/flows.json"];

// the country picked here, kept for the visit as the app keeps its widgets (a redraw for new weights keeps it)
let kept = null;
const PAGES = { // app_pages path -> [link, name]
  overview: ["/", "Global overview"], changes: ["/changes", "Score changes"], country: ["/country", "Country profile"],
  hotspots: ["/hotspots?tab=calendar", "the event calendar"], conflict: ["/conflict", "Conflict & displacement"],
  economy: ["/economy", "Economic stress"], regions: ["/regions", "Regions"], builder: ["/builder", "Assessment builder"],
};
const WORKFLOWS = {
  "Screening a market (business & investors)": [
    ["Rank candidate countries on the Global overview; set the pillar weights in the sidebar to match your exposure (e.g. more weight on "
      + "Economy for trade, Governance for long-term assets).", "overview"],
    ["Look for countries getting riskier on *Score changes*: a mid-tier country sliding fast can be a bigger worry than a stable high-tier one.", "changes"],
    ["Open *What it means in real life* on each profile's Summary, then *Peers* to compare with neighbours.", "country"],
    ["Use the What-if simulator to see how a currency crisis or conflict would change the picture.", "country"],
    ["Check the event calendar on Hotspots for elections or deadlines before committing.", "hotspots"],
  ],
  "Planning a programme (NGOs & humanitarian)": [
    ["Conflict & displacement shows where people are being killed and displaced, and where refugees are hosted.", "conflict"],
    ["*What it means in real life*, on each profile's Summary, spells out access, safety and price pressures.", "country"],
    ["Economic stress flags inflation and currency problems that erode cash assistance.", "economy"],
    ["Check the event calendar for elections and deadlines; plan field movements around them.", "hotspots"],
  ],
  "Preparing a trip, posting or study abroad": [
    ["Read *What it means in real life* on the country's Summary, then its latest news.", "country"],
    ["Check your government's current travel advice, which changes faster than this data.", null],
    ["Avoid travelling around high-significance events on the event calendar.", "hotspots"],
  ],
  "Writing an analysis (policy, journalism, research)": [
    ["The profile's Summary and Data tabs show exactly what pushes the score.", "country"],
    ["Governance trends show whether a change is outside the margin of error.", "country"],
    ["Regions and Compare put a country in its neighbourhood.", "regions"],
    ["The Assessment builder turns your judgment into a structured brief with probabilities.", "builder"],
  ],
};
const LIMITS = [
  "Annual data cannot see last week's coup or last night's protest. Read the news pulse, official advice and local sources as well.",
  "Scores are relative. A Low score means safer than most countries, and such a country can still be dangerous. A global shock can leave "
    + "rankings unchanged while every country gets worse; the red flags cover that side.",
  "A country score is a national average and hides regions: a conflict in one province may not touch the capital, and the reverse.",
  "Countries with little data are often the riskiest. Check the coverage figure on each profile.",
  "This guide is educational. It is not investment, legal or security advice.",
];

// *words* in the workflow steps are italic (markdown)
const emphasis = (text) => text.split(/\*([^*]+)\*/).map((part, i) => (i % 2 ? h("em", null, part) : part));
const list = (items, tag = "ul") => h(tag, { class: "sg-ref-list" }, items.map((t) => h("li", null, t)));
const h4 = (text) => h("h4", { class: "sg-ref-h4" }, text);

// ui.current_country: the country opened last in this visit, else ?country=, else the first followed, else Nigeria
function currentCountry(ctx, valid) {
  let last = null;
  try { last = sessionStorage.getItem("sg-country"); } catch { /* storage blocked */ }
  return [last, ctx.params.get("country"), follow.following()[0], "NGA"].map((c) => (c ? String(c).toUpperCase() : null))
    .find((c) => c && valid.has(c)) ?? [...valid][0];
}

// ui.render_reading: a country's numbers in real life (on the ground, warning signs, direction, what to do)
function renderReading(r, ctx) {
  const box = h("div", { class: "sg-stack" }, h("p", null, ui.tierBadge(r.tier), "   ", r.headline));
  if (r.tier === null) {
    box.append(ui.emptyState(r.ground));
    return box;
  }
  const left = h("div", { class: "sg-stack" }, h4("What it looks like on the ground"), h("p", null, r.ground),
    r.drivers.map((d) => h("div", { class: "sg-card sg-ref-box" },
      h("div", null, ui.pillarChip(d.pillar, `${d.label} · ${fixed(d.score, 0)}/100`)),
      h("p", null, d.ground),
      d.evidence.length ? ui.caption(`Driven by ${d.evidence.join("; ")}.`) : null,
      ui.caption(`Felt first by: ${d.felt_by}`))));
  const right = h("div", { class: "sg-stack" }, h4("Warning signs right now"));
  if (r.warnings.length) {
    for (const w of r.warnings) right.append(h("p", null, ui.sevMark(w.severity), h("b", null, w.label), h("br"), w.meaning), ui.caption(`Typical response: ${w.response}`));
  } else right.append(h("p", null, "No absolute warning thresholds crossed."));
  if (r.near.length) right.append(h4("Close to a red line"), list(r.near));
  if (r.direction.length) right.append(h4("Direction"), list(r.direction));
  right.append(h4("Coming up"), r.events.length ? list(r.events) : ui.caption("No events on the calendar for the next 12 months."));
  box.append(h("div", { class: "sg-ref-cols" }, left, right), h4("What to do with it"));
  const tabs = localTabs(box, AUDIENCES, ctx);
  for (const key of Object.keys(AUDIENCES)) tabs.on(key, (panel) => panel.append(list(r.actions[key] ?? [])));
  box.append(
    ui.download("Download reading (Markdown)", { data: () => readingMarkdown(r), filename: `${r.iso3}_real_life_reading.md`, mime: "text/markdown", icon: null }),
    ui.caption(r.caveats.join(" ")));
  return box;
}

export async function render(main, ctx) {
  await ui.loadCss("/css/reference.css");
  const c = ctx.core.config;
  const countries = asRows(ctx.core.countries);
  const names = Object.fromEntries(countries.map((r) => [r.iso3, r.name]));
  const options = countries.map((r) => r.iso3).sort((a, b) => (names[a] < names[b] ? -1 : names[a] > names[b] ? 1 : 0));
  const table = ctx.table();
  // events and flows add "Coming up" and refugee hosts; without them the reading still draws
  const [events, flows] = await Promise.all(["/data/events.json", "/data/flows.json"].map((u) => ctx.fetchJSON(u).catch((err) => {
    console.warn(`section data missing: ${u}`, err);
    return null;
  })));

  const reading = h("div", { class: "sg-stack" });
  const show = (iso3) => {
    const r = countryReading(iso3, table, ctx.core.values, ctx.scores(), ctx.history(),
      { events, flows, year: ctx.core.meta.year, wgiTrend: ctx.core.wgiTrend[iso3] ?? null, config: c });
    clear(reading).append(renderReading(r, ctx), ui.cite(["index", "ifes", "ucdp_def", "imf_ara"]),
      ui.pageLink(`/country?country=${iso3}`, `Open the ${names[iso3]} profile`, "flag"));
  };
  const picked = kept && names[kept] ? kept : currentCountry(ctx, new Set(options));
  const pick = ui.select({ label: "Country", options, value: picked, format: (i) => names[i] ?? i,
    onChange: (iso3) => { kept = iso3; show(iso3); } });
  show(picked);

  const columns = [[], []];
  c.pillars.forEach((p, i) => columns[i % 2].push(h("div", { class: "sg-card sg-ref-box" },
    h("div", null, ui.pillarChip(p.key)),
    h("p", null, `When high: ${PILLAR_MEANING[p.key].ground}`),
    h("p", null, `Felt first by: ${PILLAR_MEANING[p.key].felt_by}`),
    ui.caption(`Measured with: ${c.indicators.filter((ind) => ind.pillar === p.key).map((ind) => ind.short).join(", ")}.`))));

  const workflows = Object.entries(WORKFLOWS).map(([name, steps]) => ui.expander(name, {}, steps.flatMap(([text, page], n) => [
    h("ol", { class: "sg-ref-list", start: n + 1 }, h("li", null, emphasis(text))),
    page ? ui.pageLink(PAGES[page][0], `Open ${PAGES[page][1]}`, "arrow_forward") : null,
  ])));

  main.append(...[
    ui.weightsNote(ctx),
    ui.hero(title),
    h("h2", null, "1 · Any country in plain language"),
    pick,
    reading,
    h("h2", { class: "sg-ref-help-h" }, "2 · What the scores mean on the ground",
      ui.helpMark("Scores are relative: a tier says how a country compares with the rest of the world this year.")),
    staticTable(["Tier", "Score", "What it looks like", "Countries now", "For example"], tierRows(table, c)),
    ui.cite(["index"]),
    h("h2", null, "3 · The four pillars in daily life"),
    h("div", { class: "sg-ref-cols sg-ref-cols-even" }, columns.map((col) => h("div", { class: "sg-stack" }, col))),
    h("h2", { class: "sg-ref-help-h" }, "4 · Warning thresholds",
      ui.helpMark("Unlike the relative score, these are absolute lines: crossing one is a warning wherever the country ranks.")),
    staticTable(["Severity", "Threshold", "In real life", "Common response", "Countries now"], flagRows(ctx.core.values, c)),
    ui.cite(["ucdp_def", "imf_ara", "imf", "wdi", "unhcr"]),
    h("h2", null, "5 · Putting it to work"),
    ...workflows,
    h("h2", null, "6 · When not to rely on it"),
    list(LIMITS),
    ui.footer(),
  ].filter(Boolean));
}
