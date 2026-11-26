// Methodology: how the index is built, how it is tested, and its limits (app_pages/methodology.py).
import * as ui from "../lib/ui.js";
import { h, clear } from "../lib/dom.js";
import { asRows } from "../lib/scoring.js";
import { fixed, pyRound } from "../lib/format.js";
import { countryTable } from "../lib/table.js";
import { onsetFifths, plot } from "../lib/charts.js";
import { localTabs, onsetPanel, staticTable, trackRecord } from "../charts/reference.js";

export const title = "Methodology";
export const required = ["data/reference/methodology.json"];

const HANDBOOK = "https://www.oecd.org/en/publications/handbook-on-constructing-composite-indicators-methodology-and-user-guide_9789264043466-en.html";
// the score tested, kept for the visit as the app keeps its widgets (a redraw for new weights does not reset it)
let basis = "Stability pillar";
const FIFTHS = ["Safest fifth", "2nd fifth", "Middle fifth", "4th fifth", "Riskiest fifth"];
const g = (x) => String(x); // Python's :g for the page's whole and short numbers

const list = (items) => h("ul", { class: "sg-ref-list" }, items.map((t) => h("li", null, t)));
const link = (href, ...text) => h("a", { href, target: "_blank", rel: "noopener" }, text);
const pct = (x) => (x === null ? "—" : `${fixed(x * 100, 0)}%`);
// a "large" dataframe column: one line cut at 25rem as the app's grid does, the full text on hover and for screen readers
const long = (v) => h("span", { class: "sg-ref-long", title: v }, v);
const openLink = (url) => (url ? h("a", { class: "sg-ref-link", href: url, target: "_blank", rel: "noopener" }, "Open ↗") : "—");

function built(panel, ctx, method) {
  const c = ctx.core.config;
  const short = Object.fromEntries(c.pillars.map((p) => [p.key, p.short]));
  const indicators = h("div", { class: "sg-ref-wide" });
  countryTable(indicators, c.indicators.map((i) => ({ key: i.key, indicator: i.label, pillar: short[i.pillar], unit: i.unit,
    riskier: i.higher_is_riskier ? "higher" : "lower", source: i.source, why: i.description })), {
    key: "key", height: "640px", columns: [
      { key: "indicator", label: "Indicator" }, { key: "pillar", label: "Pillar" }, { key: "unit", label: "Unit" },
      { key: "riskier", label: "Riskier when" }, { key: "source", label: "Source" },
      { key: "why", label: "Why it is here", fmt: long }],
  });
  const basis = new Map(c.FLAG_BASIS.map((b) => [`${b.key}|${b.threshold}`, b]));
  const flags = h("div", { class: "sg-ref-wide" });
  countryTable(flags, [
    ...c.RED_FLAGS.map(([key, op, thr, sev, label]) => {
      const b = basis.get(`${key}|${thr}`);
      return { flag: label, severity: c.SEVERITY_LABEL[sev], indicator: key, rule: `${op} ${g(thr)}`, basis: b?.basis ?? "Seismographic line",
        reference: b?.source ? c.SOURCES[b.source].url : null };
    }),
    { flag: "Political stability deteriorating", severity: "Watch", indicator: "wgi_pv",
      rule: `falls ≥ ${g(c.WGI_TREND_THRESHOLD)} points in ${c.WGI_TREND_YEARS} years`,
      basis: "Seismographic line, larger than most year-to-year noise in the WGI", reference: c.SOURCES.wgi_method.url },
  ], { key: "flag", columns: [
    { key: "flag", label: "Flag" }, { key: "severity", label: "Severity" },
    { key: "indicator", label: "Indicator" }, { key: "rule", label: "Rule" },
    { key: "basis", label: "Basis", fmt: long },
    { key: "reference", label: "Reference", fmt: openLink, fmtNull: true }] });

  const bounds = [...c.tiers.map((t) => t.lower), 100];
  const escalation = ui.guard("The escalation signal", async (box) => {
    const e = (await method).escalation;
    box.append(h("div", { class: "sg-stack" },
      h("p", null, "The Hotspots page reads recent change from two sources refreshed every day. UCDP's candidate events count organised "
        + "violence with at least one death, published about six weeks after each month ends. GDELT counts the English-language articles "
        + "about each country that mention attacks, clashes, airstrikes, shelling, killings or coups, and divides them by all the articles "
        + "GDELT monitored that day, so a busy news day does not look like an escalation."),
      list([
        `The signal compares the average share of the last ${e.recent_days} days with the median share of the ${e.window_days - e.recent_days} `
          + "days before them. A day GDELT returns no figure for counts as zero.",
        `Escalating: the recent share is at least ${g(e.escalating_ratio)} times the usual level and at least ${g(e.escalating_z)} robust standard `
          + `deviations above it (${g(e.mad_scale)} × the median absolute deviation, and never less than one article a day). A country with no `
          + "conflict news on most days only has to pass the second test.",
        `Easing: ${g(e.easing_ratio)} times the usual level or less.`,
        `Quiet: fewer than ${e.min_articles_7d} articles in the last week, too few to read a change.`,
        "Steady: everything else.",
      ]),
      h("p", null, "News volume is not a count of events. Coverage also rises with a summit, an anniversary or a famous victim, and "
        + "English-language media cover some countries far more than others, so a country reported mostly in other languages can look "
        + "quieter than it is. Treat Escalating as a reason to read the news and check UCDP's events.")));
  });

  panel.append(
    h("h2", null, "The question"),
    h("blockquote", { class: "sg-ref-quote" }, h("p", null, "How exposed is this country to political, governance, economic and social shocks that "
      + "could harm people, organisations and investments operating there, compared with other countries?")),
    h("p", null, "Four pillars break that question down:"),
    list(c.pillars.map((p) => [h("b", null, p.label), `, ${p.default_weight}% of the weight: ${p.question}`])),
    ui.caption("Political stability weighs most as the core of political risk; social pressure least, as its indicators are the noisiest. "
      + "Change the weights in the sidebar."),
    h("h2", null, "The indicators"),
    indicators,
    h("p", null, "WGI scores come from the latest annual release (perceptions collected the year before). IMF figures are the current-year "
      + "estimate from the latest World Economic Outlook, which makes the economic pillar the most forward-looking part of the index. World "
      + "Bank figures use the most recent year within a look-back window (shown in each profile's ", h("em", null, "Data"), " tab). Battle "
      + "deaths use the latest UCDP year; displacement the latest UNHCR annual statistics. The site downloads every dataset through its "
      + "public API when it is rebuilt each week."),
    ui.cite(["index", "wgi_method", "oecd_jrc"]),
    h("h2", null, "Normalisation"),
    h("p", null, "Indicators come in different units (percent, deaths, months), so each becomes a 0–100 risk score."),
    h("p", null, "Most use a percentile rank: the riskiest country in the sample scores 100, the safest 0, the rest evenly in between. "
      + "Percentiles resist outliers, so one country with 200% inflation does not squash everyone else, but they drop the size of the gaps "
      + "between countries."),
    h("p", null, "Battle deaths per 100k and the displacement share use a log scale. Most countries have no conflict deaths, so a percentile "
      + "rank would bunch them together in the middle. The score is ", h("code", { class: "sg-ref-inline-code" }, "log(1 + x)"),
    ` divided by the value at the ${fixed((c.LOG_CAP_QUANTILE) * 100, 0)}% percentile of non-zero cases, capped at 100. Zero means zero, and `
      + "scores rise steeply from the first deaths, then flatten."),
    h("p", null, "Where lower is riskier (growth, reserves, governance scores) the ranking is reversed, so 100 always means the most risk."),
    h("h2", null, "Aggregation and weights"),
    h("p", null, `A pillar score is the simple average of its indicator scores. A pillar needs at least ${fixed(c.PILLAR_MIN_SHARE * 100, 0)}% `
      + "of its indicators; with fewer, it stays blank and nothing is guessed."),
    h("p", null, "The composite score is the weighted average of the pillar scores, with the weights rescaled over the pillars a country has. "
      + `A country needs at least ${c.COMPOSITE_MIN_PILLARS} of the 4 pillars to be ranked. Data coverage, shown on every profile, is the share `
      + `of the ${c.indicators.length} indicators available.`),
    h("p", null, "An arithmetic mean lets a strength in one pillar offset a weakness in another, which suits a broad screening tool. A "
      + "crisis-risk model might use a geometric mean, which penalises one very weak pillar more, as the EU's INFORM Risk Index does."),
    h("h2", null, "Tiers"),
    h("div", { class: "sg-ref-fit" }, staticTable(["Tier", "Composite score"], c.tiers.map((t, i) => {
      const lo = bounds[i], hi = bounds[i + 1];
      return { Tier: t.label, "Composite score": `${g(lo)} to ${hi < 100 ? "under " : ""}${g(hi)}` };
    }))),
    ui.caption("Averaging many indicators pulls composites toward the middle, so the outer tiers hold only countries at the extremes on most "
      + "dimensions at once. 'Low' is low relative to other countries; it does not mean risk-free."),
    h("h2", null, "Red flags"),
    h("p", null, "The composite is relative, so it cannot say whether a situation is bad in absolute terms. Red flags use fixed thresholds "
      + "from common practice, for example UCDP's 25 battle deaths for an active armed conflict and 1,000 for war, and the "
      + "3-months-of-imports rule of thumb for reserves."),
    flags,
    ui.cite(["ucdp_def", "rr_inflation", "rr_debt", "freund", "imf_ara"]),
    ui.pageLink("/sources", "Every source and threshold reference", "verified"),
    h("h2", null, "Escalation signal"),
    escalation,
    ui.cite(["ucdp_ged", "gdelt"]),
    h("h2", null, "Reproducibility"),
    h("p", null, "Everything needed to recompute the scores is on this page, and all the data come from the public sources linked above."),
  );
}

// The track record for the chosen score with the weights in use; returns the chart's cleanup
function track(box, ctx, conflict, basis) {
  clear(box);
  const names = Object.fromEntries(asRows(ctx.core.countries).map((r) => [r.iso3, r.name]));
  const t = trackRecord(onsetPanel(ctx.history(), conflict, basis === "Stability pillar" ? "stability" : "composite"));
  if (!t) {
    box.append(ui.emptyState("Not enough conflict data to run the test right now."));
    return null;
  }
  const chart = h("div");
  const list = h("div");
  countryTable(list, t.onset_list.map((r) => ({ ...r, country: names[r.iso3] ?? r.iso3, started: r.year + 1, score: pyRound(r.score, 0),
    where: FIFTHS[r.fifth - 1] })), { key: "iso3", columns: [
    { key: "country", label: "Country" }, { key: "started", label: "Conflict began", fmt: String },
    { key: "score", label: "Score the year before", fmt: (v) => fixed(v, 0) }, { key: "where", label: "Where it ranked" }] });
  box.append(
    ui.kpiRow([
      { label: "New conflicts tested", value: String(t.onsets),
        help: `Out of ${fixed(t.cases, 0, { group: true })} country-years at peace, ${t.years[0]}–${t.years[1]}.` },
      { label: "In riskiest fifth", value: pct(t.top_fifth_share), help: "Share of new conflicts in countries that scored in the riskiest fifth the year before." },
      { label: "In riskiest two fifths", value: pct(t.top_two_fifths_share) },
      { label: "AUC", value: t.auc === null ? "—" : fixed(t.auc, 2),
        help: "The chance that a country where conflict started had scored higher than one where it did not. 0.5 = a coin flip, 1 = perfect." },
    ]),
    chart,
    ui.expander(`The ${t.onsets} new conflicts`, {}, list),
    ui.caption("Read with care: the scores are rebuilt from data as published today, including later revisions; governance scores for a year "
      + "are only published the following year; and a few dozen cases is a small sample. The test shows the index ranks countries sensibly. "
      + "It does not show it can predict a single event."),
    ui.cite(["ucdp", "ucdp_def", "wgi"]),
    ui.pageLink("/conflict?tab=outlook", "Conflict outlook, tested on unseen years"));
  return plot(chart, onsetFifths(t.by_fifth, t.base_rate, ctx.core.config.PILLAR_COLORS.stability));
}

function tests(panel, ctx, method, cleanups) {
  const box = h("div", { class: "sg-stack" });
  let cleanup = null;
  const draw = async () => {
    cleanup?.();
    cleanup = null;
    try {
      cleanup = track(box, ctx, (await method).conflict, basis);
    } catch (err) {
      console.warn("section failed: the track record", err);
      clear(box).append(ui.caption("The track record can't be shown right now. The rest of the page is unaffected."));
    }
  };
  cleanups.push(() => cleanup?.());

  const benchmark = h("div", { class: "sg-stack" });
  ctx.fetchJSON("/data/reference/fsi.json").then((f) => {
    benchmark.append(...[
      ctx.customLabel() ? ui.caption("These figures use the default weights.") : null,
      ui.kpiRow([
        { label: "Countries compared", value: String(f.compared) },
        { label: "Rank correlation", value: fixed(f.spearman, 2), help: "Spearman correlation of the two rankings: 1 = identical order, 0 = unrelated." },
        { label: "Riskiest 20 in both", value: `${f.top20_overlap} of 20`, help: "Countries in the riskiest 20 of both rankings." },
      ]),
      ui.caption(`Both for ${f.year}. The Fragile States Index also weighs group grievance, demographic pressure and outside intervention, which `
        + "Seismographic does not measure; Seismographic gives more weight to economic and financial stress. The FSI data is downloaded from its "
        + "publisher when the site is built, and only these three figures are kept."),
      ui.cite(["fsi"]),
    ].filter(Boolean));
  }, (err) => {
    console.warn("section data missing: the Fragile States Index benchmark", err);
    benchmark.append(ui.emptyState("The Fragile States Index couldn't be downloaded from its publisher when the site was last built."));
  });

  panel.append(...[
    h("h2", null, "Robustness"),
    h("p", null, "Each country profile has a sensitivity check that recomputes the rank with equal weights and with each pillar dropped in turn. "
      + "If the rank swings widely, the result depends on a modelling choice, and any report on it should say so. WGI changes are tested "
      + "against the WGI 90% confidence intervals, to show whether a change is statistically clear or within the margin of error."),
    h("h2", null, "Track record"),
    h("p", null, `For every year since ${ctx.core.config.HISTORY_START}, take the countries not in armed conflict and see where conflict broke out `
      + "the next year (25 or more battle deaths, the UCDP threshold). If the index works, those countries should already have scored high."),
    ui.weightsNote(ctx),
    ui.segmented({ label: "Score tested", options: ["Stability pillar", "Composite score"], value: basis, onChange: (v) => { basis = v; draw(); } }),
    box,
    h("h2", null, "Benchmark: the Fragile States Index"),
    h("p", null, "The ", link("https://fragilestatesindex.org/", "Fragile States Index"), " from The Fund for Peace is an independent index of "
      + "something similar, rating states on 12 indicators with expert review. Broad agreement is reassuring; the countries where they disagree "
      + "show what each index picks up and the other misses."),
    benchmark,
  ].filter(Boolean));
  return draw();
}

function limits(panel) {
  panel.append(
    h("h2", null, "Limitations"),
    list([
      "The data look backwards. Governance data describe last year, and conflict and displacement data lag by up to two years. A coup last "
        + "month will not show in the score; the news pulse, the Hotspots page and the analyst assessment are there for that.",
      "Governance data are perceptions. The WGI aggregate expert and survey perceptions, with real margins of error. Their authors publish the "
        + "six dimensions separately; this index deliberately combines them into one pillar.",
      "Scores are relative. Percentiles show a country's position and drop the distance between countries, so a global shock that worsens "
        + "every country can leave the ranking unchanged.",
      "Data are thinnest where risk is highest. Small states and countries in conflict often have the least data, so check the coverage "
        + "figure before drawing conclusions.",
      "The weights are a judgment. Indicators count equally within a pillar and the pillar weights are a choice. Other choices are "
        + "defensible, and the sensitivity check on each profile shows how much they change the result.",
      "It is not a forecast. The index describes structural conditions; the probability of a specific event takes the analyst work the "
        + "assessments are for.",
    ]),
    h("h2", null, "How professional models compare"),
    list([
      "ICRG (PRS Group) is one of the longest-running commercial country-risk ratings. It scores political, financial and economic risk "
        + "separately and then combines them, with political risk carrying the most points.",
      ["The INFORM Risk Index (European Commission JRC) is an open humanitarian-risk model built from hazard and exposure, vulnerability and "
        + "lack of coping capacity, aggregated with geometric means. Its documentation sets a high bar for openness: ",
      link("https://drmkc.jrc.ec.europa.eu/inform-index/INFORM-Risk/Methodology", "methodology"), "."],
      ["The OECD Country Risk Classification is the export-credit agencies' 0–7 rating of the risk that a country cannot meet its external "
        + "debt payments. It combines a quantitative model with expert judgment: ",
      link("https://www.oecd.org/en/topics/country-risk-classification", "current list"), "."],
      "Commercial intelligence firms (Control Risks, Eurasia Group, Verisk Maplecroft, EIU and others) combine data models with networks of "
        + "country analysts, the same split between model and judgment that this project uses.",
    ]),
  );
}

export async function render(main, ctx) {
  await ui.loadCss("/css/reference.css");
  const method = ctx.fetchJSON("/data/reference/methodology.json");
  method.catch(() => {}); // each section that needs it shows its own note
  const cleanups = [];
  const tabsBox = h("div", { class: "sg-ref-bigtabs" });
  main.append(
    ui.hero(title),
    h("p", null, "Seismographic follows the ", link(HANDBOOK, "OECD/JRC ", h("em", null, "Handbook on Constructing Composite Indicators")), "."),
    tabsBox);
  localTabs(tabsBox, { built: "How it is built", tests: "Tests", limits: "Limits" }, ctx, "methodology")
    .on("built", (panel) => built(panel, ctx, method))
    .on("tests", (panel) => tests(panel, ctx, method, cleanups))
    .on("limits", limits);
  main.append(ui.footer());
  return () => cleanups.forEach((fn) => fn());
}
