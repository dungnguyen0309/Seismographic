// Sources: every dataset, definition and feed behind Seismographic, with links and update dates, and further reading
// (app_pages/sources.py).
import * as ui from "../lib/ui.js";
import { h } from "../lib/dom.js";
import { countryTable } from "../lib/table.js";
import { cardGrid, localTabs } from "../charts/reference.js";

export const title = "Sources";
export const required = ["data/reference/sources.json"];

const READING = {
  "Open data used or worth adding": [
    ["Worldwide Governance Indicators (World Bank)", "https://www.worldbank.org/en/publication/worldwide-governance-indicators",
      "Six governance dimensions for about 200 countries since 1996, revised in 2025 onto a 0–100 scale. Used in this app."],
    ["World Development Indicators (World Bank)", "https://datatopics.worldbank.org/world-development-indicators/",
      "1,400+ development series with a free API. Source of conflict, homicide, reserves and labour data here."],
    ["IMF World Economic Outlook DataMapper", "https://www.imf.org/external/datamapper",
      "Growth, inflation, debt and balance-of-payments estimates with five-year projections. Used in this app."],
    ["UNHCR Refugee Data Finder", "https://www.unhcr.org/refugee-statistics/",
      "Refugees, asylum seekers and IDPs by origin and destination, with a free API. Used in this app."],
    ["Uppsala Conflict Data Program (UCDP)", "https://ucdp.uu.se/",
      "The academic standard for armed-conflict data. Its API needs a free access token and would allow event-level maps."],
    ["ACLED", "https://acleddata.com/",
      "Near-real-time data on political violence and protest events. Requires registration; check its terms before publishing derived data."],
    ["GDELT Project", "https://www.gdeltproject.org/", "Global news monitoring with a free API. The backup news source and media-tone chart here."],
    ["V-Dem", "https://v-dem.net/", "The most detailed dataset on democracy and regime characteristics, free for download."],
    ["Fragile States Index (Fund for Peace)", "https://fragilestatesindex.org/",
      "Annual fragility index across 12 indicators, useful as a benchmark for these scores."],
    ["Bertelsmann Transformation Index", "https://bti-project.org/",
      "Expert country reports on political and economic transformation in 137 countries."],
    ["Quality of Government Data Finder", "https://datafinder.qog.gu.se/",
      "Searchable catalogue of hundreds of governance datasets with variable-level documentation."],
    ["OpenSanctions", "https://www.opensanctions.org/", "Consolidated sanctions lists and politically exposed persons. Free for non-commercial use."],
    ["IFES ElectionGuide", "https://www.electionguide.org/elections/type/upcoming/",
      "Calendar of upcoming national elections and referendums, and the source for the event calendar on Hotspots."],
  ],
  "Free outlooks from professional risk firms and institutions": [
    ["Eurasia Group: Top Risks", "https://www.eurasiagroup.net/issues/top-risks-2026", "The best-known annual list of geopolitical risks. Read it every January."],
    ["Control Risks: RiskMap", "https://www.controlrisks.com/riskmap/maps", "Annual forecast and interactive map of political, security and operational risk."],
    ["World Economic Forum: Global Risks Report", "https://www.weforum.org/publications/global-risks-report-2026/",
      "Annual survey of experts on the most severe global risks over short and long horizons."],
    ["Crisis Group: CrisisWatch", "https://www.crisisgroup.org/crisiswatch",
      "Monthly tracker of conflicts worldwide, flagging deteriorations, improvements and risk alerts. Useful for the event calendar."],
    ["OECD Country Risk Classification", "https://www.oecd.org/en/topics/country-risk-classification",
      "Export-credit risk categories (0–7), updated several times a year. A benchmark for the economic pillar."],
    ["Allianz Trade: Country Risk Atlas", "https://www.allianz-trade.com/en_global/news-insights/news/allianz-trade-country-risk-atlas-2026.html",
      "Country risk ratings combining political, economic and business-environment factors."],
    ["Coface: Country risk map", "https://coface.com/news-economy-and-insights/business-risk-dashboard/country-risk-map",
      "Credit-insurer country assessments, updated quarterly."],
    ["INFORM Risk Index (EU JRC)", "https://drmkc.jrc.ec.europa.eu/inform-index",
      "Open humanitarian-risk model; its methodology documentation is a template for transparency."],
  ],
  "Methods and analytic tradecraft": [
    ["OECD/JRC Handbook on Constructing Composite Indicators",
      "https://www.oecd.org/en/publications/handbook-on-constructing-composite-indicators-methodology-and-user-guide_9789264043466-en.html",
      "The reference text on normalisation, weighting, aggregation and sensitivity analysis."],
    ["WGI 2025 Methodology Revision",
      "https://www.worldbank.org/content/dam/sites/govindicators/doc/The%20Worldwide%20Governance%20Indicators%202025%20Methodology%20Revision.pdf",
      "How the governance scores and their confidence intervals are produced."],
    ["ICD 203: Analytic Standards (ODNI)", "https://www.dni.gov/files/documents/ICD/ICD-203.pdf",
      "The US intelligence community's standards, including the estimative-language scale used in the assessment builder."],
    ["Psychology of Intelligence Analysis, by Richards Heuer (CIA, free)", "https://www.cia.gov/resources/csi/static/Pyschology-of-Intelligence-Analysis.pdf",
      "Cognitive biases in analysis and the origin of Analysis of Competing Hypotheses."],
  ],
  Books: [
    ["Political Risk, by Condoleezza Rice & Amy Zegart (2018)", null,
      "How organisations identify, assess and mitigate political risk; accessible and case-driven."],
    ["The Fat Tail, by Ian Bremmer & Preston Keat (2009)", null,
      "The founder of Eurasia Group on why political risk is under-priced and how to analyse it."],
    ["Superforecasting, by Philip Tetlock & Dan Gardner (2015)", null,
      "What makes forecasts accurate; the basis for putting probabilities on your key judgments."],
    ["Structured Analytic Techniques for Intelligence Analysis, by Heuer & Pherson", null,
      "The toolkit: key assumptions check, ACH, indicators, scenarios, red-teaming."],
  ],
  "Practise and build a track record": [
    ["Good Judgment Open", "https://www.gjopen.com/", "Free forecasting tournaments on geopolitical questions. A Brier score is a credible line on a CV."],
    ["Metaculus", "https://www.metaculus.com/", "Forecasting platform with many geopolitics questions and public track records."],
  ],
};
const IDEAS = [
  "Write quarterly assessments for 5–10 countries in one region and track how your ratings compare with what happened.",
  "Benchmark the index against the OECD's fragility classification: where do they disagree, and why?",
  "Add a conflict-events map with a free UCDP access token or an ACLED account.",
  "Add a sanctions pillar from OpenSanctions or official lists for a compliance angle.",
];

const ext = (href, text) => h("a", { href, target: "_blank", rel: "noopener" }, text);
const openLink = (url) => (url ? h("a", { class: "sg-ref-link", href: url, target: "_blank", rel: "noopener" }, "Open ↗") : "—");
// a "large" dataframe column: one line cut at 25rem as the app's grid does, the full text on hover and for screen readers
const long = (v) => h("span", { class: "sg-ref-long", title: v }, v);
const missing = () => ui.emptyState("This list can't be shown right now. The rest of the page is unaffected.");

// A source as a card: publisher, linked name, what it is used for, update and terms; extra: nodes under it
function card(config, key, ...extra) {
  const s = config.SOURCES[key];
  const details = [s.updates && `Updates: ${s.updates}`, s.terms && `Terms: ${s.terms}`].filter(Boolean).join(" · ");
  return h("div", { class: "sg-ref-card src" },
    h("div", { class: "sg-ref-src-pub" }, s.publisher),
    h("div", { class: "sg-ref-src-name" }, ui.sourceLink(key, s.name)),
    h("div", { class: "sg-ref-src-use" }, s.used_for),
    details ? h("div", { class: "sg-ref-src-meta" }, details) : null,
    extra);
}

function indexTab(panel, ctx, src) {
  const c = ctx.core.config;
  panel.append(h("h2", { class: "sg-ref-help-h" }, "The data behind the index",
    ui.helpMark("The risk scores are Seismographic's own calculation from these datasets, explained on the Methodology page.")));
  if (!src) {
    panel.append(missing(), h("h2", null, "Data status"), ui.dataStatus(ctx.core.meta));
    return;
  }
  panel.append(cardGrid(src.index_cards.map((k) => card(c, k.key,
    k.status ? h("div", { class: "sg-ref-src-load" }, k.status) : null,
    k.indicators.length ? h("div", { class: "sg-ref-src-inds" }, "Indicators: ", k.indicators.flatMap((i, n) => [n ? " · " : null, ext(i.url, i.label)])) : null)), 270));
  const table = h("div", { class: "sg-ref-wide" });
  countryTable(table, src.indicators, { key: "Indicator", columns: [
    { key: "Pillar", label: "Pillar" }, { key: "Indicator", label: "Indicator" }, { key: "Original source", label: "Original source" },
    { key: "Series code", label: "Series code" },
    { key: "Most common data year", label: "Most common data year", fmt: String },
    { key: "Source updated", label: "Source updated" }, { key: "Status", label: "Status" },
    { key: "Data", label: "Data", fmt: openLink, fmtNull: true }] });
  panel.append(h("h3", null, "Indicator by indicator"), table,
    ui.caption("IMF figures for the current year are estimates and are revised twice a year. World Bank and UNHCR series run a year or two "
      + "behind, so each indicator uses the latest year available for each country."),
    h("h2", null, "Data status"), ui.dataStatus(ctx.core.meta));
}

function thresholdsTab(panel, ctx) {
  const c = ctx.core.config;
  const label = (k) => c.CITE_LABELS[k] ?? c.SOURCES[k].name;
  const basis = new Map(c.FLAG_BASIS.map((b) => [`${b.key}|${b.threshold}`, b]));
  const rows = c.RED_FLAGS.map(([key, , thr, sev, flag]) => {
    const b = basis.get(`${key}|${thr}`);
    return { severity: c.SEVERITY_LABEL[sev], flag, basis: b?.basis ?? "Seismographic line", reference: b?.source ? label(b.source) : "—",
      link: b?.source ? c.SOURCES[b.source].url : null };
  });
  rows.push({ severity: c.SEVERITY_LABEL.warning,
    flag: `Political stability deteriorating (WGI down ${c.WGI_TREND_THRESHOLD}+ points in ${c.WGI_TREND_YEARS} years)`,
    basis: "Seismographic line, chosen to be larger than most year-to-year noise in the WGI", reference: label("wgi_method"), link: c.SOURCES.wgi_method.url });
  const table = h("div", { class: "sg-ref-wide" });
  countryTable(table, rows, { key: "flag", columns: [
    { key: "severity", label: "Severity" }, { key: "flag", label: "Red flag", fmt: long }, { key: "basis", label: "Basis", fmt: long },
    { key: "reference", label: "Reference" }, { key: "link", label: "Link", fmt: openLink, fmtNull: true }] });
  panel.append(h("h2", null, "Where the warning thresholds come from"),
    ui.caption("Red flags are fixed thresholds that do not depend on other countries. Some come from a definition or a well-known study; "
      + "others are Seismographic's own lines."),
    table,
    ui.caption("The risk tiers (Low to Severe) are equal 20-point bands of the composite score, a Seismographic convention."));
}

function crossTab(panel, ctx) {
  const c = ctx.core.config;
  panel.append(h("h2", null, "Cross-check the scores"),
    ui.caption("Not used in the score. Where one disagrees with Seismographic about a country, find out why before relying on either."),
    ...Object.entries(c.CROSS_CHECKS).flatMap(([pillar, keys]) => [
      pillar === "composite" ? h("p", { class: "sg-strong" }, "Overall fragility") : h("div", null, ui.pillarChip(pillar)),
      cardGrid(keys.map((k) => card(c, k)), 240)]));
}

function referencesTab(panel, ctx, src) {
  const c = ctx.core.config;
  panel.append(h("h2", null, "Definitions, methods and other references"),
    ...Object.entries(c.SOURCE_GROUPS).flatMap(([group, keys]) => [h("h3", null, group),
      cardGrid(keys.map((k) => card(c, k, k === "wb_countries" && src ? h("div", { class: "sg-ref-src-load" }, `Loaded now: ${src.countries_state}`) : null)), 270)]),
    h("h2", null, "Video channels"),
    ui.caption("All video comes from each organisation's official YouTube channel. State-owned and state-funded channels can reflect their "
      + "government's view."));
  if (src) {
    const table = h("div", { class: "sg-ref-wide" });
    countryTable(table, src.channels, { key: "Channel", height: "420px", columns: [
      ...["Channel", "Content", "Region", "Based in", "Ownership"].map((k) => ({ key: k, label: k })),
      { key: "YouTube", label: "YouTube", fmt: openLink }] });
    panel.append(table);
  } else panel.append(missing());
  panel.append(ui.caption("Headlines in the news feeds link to the original publisher; Bing News and Google News only find them."));
}

function readingTab(panel) {
  for (const [section, items] of Object.entries(READING)) {
    panel.append(h("h2", null, section), ...items.map(([name, url, note]) => h("p", null, url ? ext(url, name) : name, `. ${note}`)));
  }
  panel.append(h("h2", null, "Ideas to extend this project"), h("ol", { class: "sg-ref-list" }, IDEAS.map((t) => h("li", null, t))));
}

function citeTab(panel, ctx, src) {
  const c = ctx.core.config;
  const today = new Date();
  const retrieved = today.toLocaleDateString("en-GB", { day: "2-digit", month: "long", year: "numeric" });
  const author = src?.cite.author ?? c.AUTHOR;
  const edition = src?.cite.edition ?? "World Economic Outlook";
  panel.append(h("h2", null, "How to cite Seismographic"),
    h("pre", { class: "sg-code" }, `${author} (${today.getFullYear()}). ${c.APP_TITLE}: a country political risk index built from open data `
      + "[Web application]. Data from the World Bank (Worldwide Governance Indicators, World Development Indicators), "
      + `the IMF (${edition}), UNHCR and the Uppsala Conflict Data Program. Retrieved ${retrieved}.`),
    ui.caption("When you quote a figure, cite the original source too: it is named on the page or tab the figure comes from and in the ",
      h("em", null, "Index data"), " tab."));
}

export async function render(main, ctx) {
  await ui.loadCss("/css/reference.css");
  const c = ctx.core.config;
  const src = await ctx.fetchJSON("/data/reference/sources.json").catch((err) => console.warn("section data missing: sources", err));
  const references = Object.values(c.SOURCE_GROUPS).flat().length;
  const crossChecks = new Set(Object.values(c.CROSS_CHECKS).flat()).size;
  const stats = [[c.INDEX_SOURCES.length, "datasets in the index"], [c.indicators.length, "indicators"],
    [references, "definitions, methods & feeds"], [crossChecks, "independent cross-checks"], [src ? src.channels.length : "—", "official video channels"]];
  const tabsBox = h("div");
  main.append(...[
    ui.weightsNote(ctx),
    ui.hero(title, "Seismographic collects no data of its own. Each page also names its sources where they are used."),
    cardGrid(stats.map(([n, label]) => h("div", { class: "sg-ref-stat" }, h("div", { class: "sg-ref-big" }, String(n)), h("div", { class: "sg-ref-small" }, label))), 130),
    tabsBox,
  ].filter(Boolean));
  localTabs(tabsBox, { index: "Index data", thresholds: "Thresholds", cross: "Cross-checks", references: "References",
    reading: "Further reading", citing: "Citing" }, ctx, "sources")
    .on("index", (p) => indexTab(p, ctx, src))
    .on("thresholds", (p) => thresholdsTab(p, ctx))
    .on("cross", (p) => crossTab(p, ctx))
    .on("references", (p) => referencesTab(p, ctx, src))
    .on("reading", readingTab)
    .on("citing", (p) => citeTab(p, ctx, src));
  main.append(ui.footer(true));
}
