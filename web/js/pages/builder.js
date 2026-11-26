// Assessment builder: write a structured country assessment and download it as a Markdown file
// (app_pages/builder.py). The file is written here exactly as prm/content.py build_assessment_markdown writes it.
import * as ui from "../lib/ui.js";
import * as follow from "../lib/follow.js";
import { h, clear } from "../lib/dom.js";
import { asRows, countryBrief, na } from "../lib/scoring.js";
import { fixed } from "../lib/format.js";
import { countryTable } from "../lib/table.js";
import { CONFIDENCE, DRIVER_FACTS, OUTLOOKS, buildAssessmentMarkdown, estimativeTerm, facts, parseFrontMatter, pyStrip } from "../group10/content.js";
import { markdown } from "../group10/markdown.js";

export const title = "Assessment builder";
export const required = ["data/group10/builder.json"];

const HORIZONS = ["6 months", "12 months", "24 months"];
const SCENARIOS = ["Base case", "Upside", "Downside"];
const TEXT = ["bluf", "j1", "j2", "j3", "drv_political", "drv_security", "drv_economic", "drv_social", "watch", "divergence", "implications",
  "sources", ...SCENARIOS.flatMap((s) => [`sd_${s}`, `ss_${s}`])];

// The form as the visitor left it in this visit (Streamlit keeps a draft in the session): a new visit restores it when
// something was typed or the author changed; a redraw while the visitor stays (a weights change) keeps it whole
let draft = null;
let here = false;

// ui.current_country: the country opened last in this visit, the address's ?country=, the first followed, else NGA
function currentCountry(ctx, valid) {
  let last = null;
  try { last = sessionStorage.getItem("sg-country"); } catch { /* storage blocked */ }
  return [last, ctx.params.get("country"), follow.following()[0], "NGA"].map((c) => (c ? String(c).toUpperCase() : null))
    .find((c) => c && valid.has(c)) ?? [...valid][0];
}

// Text controls drawn like Streamlit's (ui.js has none yet)
let seq = 0;
function field(label, control, help = null) {
  control.id = `g10-${++seq}`;
  const mark = ui.helpMark(help);
  if (mark) control.setAttribute("aria-describedby", mark.tipId);
  return h("div", { class: "sg-field" }, h("div", { class: "sg-label-row" }, h("label", { class: "sg-label", for: control.id }, label), mark), control);
}
function textInput(label, value, onInput, { placeholder = null, help = null } = {}) {
  const input = h("input", { type: "text", class: "g10-input", placeholder, autocomplete: "off" });
  input.value = value;
  input.addEventListener("input", () => onInput(input.value));
  return field(label, input, help);
}
function textArea(label, value, onInput, { placeholder = null, help = null, height = 110 } = {}) {
  // st.text_area's height is the whole field with its label; the box gets the rest, at least 68px (measured in the app)
  const area = h("textarea", { class: "g10-input g10-textarea", placeholder, style: `height:${Math.max(68, height - 30)}px` });
  area.value = value;
  area.addEventListener("input", () => onInput(area.value));
  const wrap = field(label, area, help);
  wrap.input = area;
  return wrap;
}
function numberInput(label, value, onChange, { min = 0, max = 100, step = 5 } = {}) {
  const input = h("input", { type: "number", class: "g10-input g10-num-input", min, max, step, inputmode: "numeric" });
  input.value = value;
  const set = (v) => {
    const n = Math.min(max, Math.max(min, Math.round(Number.isFinite(v) ? v : min)));
    input.value = n;
    onChange(n);
  };
  input.addEventListener("change", () => set(Number(input.value)));
  const btn = (text, delta, what) => h("button", { type: "button", class: "g10-num-btn", "aria-label": `${what} ${label}`,
    onclick: () => set(Number(input.value) + delta) }, text);
  const wrap = field(label, input);
  wrap.querySelector(".sg-label-row").after(h("div", { class: "g10-num" }, input, btn("−", -step, "Decrease"), btn("+", step, "Increase")));
  return wrap;
}

export async function render(main, ctx) {
  const redraw = here;
  here = true;
  await ui.loadCss("/css/group10.css");
  main.classList.add("g10-builder");
  const config = ctx.core.config;
  const tiers = config.tiers.map((t) => t.label);
  const countries = asRows(ctx.core.countries);
  const names = new Map(countries.map((c) => [c.iso3, c.name]));
  const options = [...names.keys()].sort((a, b) => (names.get(a) < names.get(b) ? -1 : names.get(a) > names.get(b) ? 1 : 0));
  const scores = ctx.scores();
  const modelTier = (iso3) => (tiers.includes(scores.get(iso3)?.tier) ? scores.get(iso3).tier : "Elevated");
  let nextGrowth = {};
  try {
    nextGrowth = (await ctx.fetchJSON("/data/group10/builder.json")).next_growth;
  } catch (err) {
    console.warn("section failed: next year's growth figures", err); // the Latest data lines leave that clause out
  }

  const current = currentCountry(ctx, new Set(names.keys()));
  const typed = (d) => TEXT.some((k) => pyStrip(d.state[k]) && pyStrip(d.state[k]) !== pyStrip(d.filled[k] ?? ""))
    || d.state.author !== config.AUTHOR;
  if (!draft || !(redraw || typed(draft))) {
    draft = { filled: draft?.filled ?? {}, state: {
      iso3: current, rating: modelTier(current), outlook: OUTLOOKS[1], confidence: CONFIDENCE[1], horizon: "12 months",
      author: config.AUTHOR, jp1: 65, jp2: 50, jp3: 50, "sp_Base case": 60, sp_Upside: 15, sp_Downside: 25,
      ...Object.fromEntries(TEXT.map((k) => [k, ""])),
    } };
  }
  const f = draft.state, filled = draft.filled;
  const name = () => names.get(f.iso3);

  main.append(...[ui.weightsNote(ctx), ui.hero(title)].filter(Boolean));
  const country = ui.select({ label: "Country", options, value: f.iso3, format: (i) => names.get(i) ?? i,
    onChange: (iso3) => { f.iso3 = iso3; f.rating = modelTier(iso3); rating.value = f.rating; changed(); } });
  const modelBox = h("div", { class: "sg-card" });
  const drawModel = () => {
    const s = scores.get(f.iso3) ?? {};
    const lines = countryBrief(f.iso3, name(), ctx.core.values, scores, ctx.core.countries, ctx.core.meta.year,
      { wgiTrend: ctx.core.wgiTrend[f.iso3] ?? null, nextGrowth: nextGrowth[f.iso3] ?? null, config }).slice(0, 5);
    clear(modelBox).append(h("div", { class: "sg-row g10-model" },
      h("div", { class: "sg-stack g10-tight" }, h("p", { class: "sg-strong" }, "Model view"), h("div", null, ui.tierBadge(s.tier)),
        ui.caption(`Score ${na(s.composite) ? "—" : `${fixed(s.composite, 0)}/100`}`)),
      h("div", { class: "sg-stack g10-tight" }, h("p", { class: "sg-strong" }, "Latest data"), h("ul", null, lines.map((l) => h("li", null, l))))),
    ui.cite("index"));
  };

  const terms = h("div");
  countryTable(terms, config.ESTIMATIVE_LANGUAGE.map(([t, alt, lo, hi]) => ({ Term: t, Alternative: alt, Probability: `${lo}–${hi}%` })),
    { key: "Term", columns: [{ key: "Term", label: "Term" }, { key: "Alternative", label: "Alternative" }, { key: "Probability", label: "Probability" }] });

  // 1 · Rating
  const rating = ui.select({ label: "Your risk rating", options: tiers, value: f.rating,
    help: "Defaults to the model tier. Change it if your judgment differs, and explain why below.", onChange: (v) => { f.rating = v; changed(); } });
  const pick = (label, opts, key, help = null) => ui.select({ label, options: opts, value: f[key], help, onChange: (v) => { f[key] = v; changed(); } });
  const set = (key) => (v) => { f[key] = v; changed(); };

  // 2 · Bottom line
  const bluf = textArea("Bottom line (required)", f.bluf, set("bluf"), { height: 110, help: "Two or three sentences a busy reader can act on." });
  const blufPlaceholder = () => {
    bluf.input.placeholder = `e.g. ${name()}'s risk is likely to rise over the next 12 months as … The main threat to operations is … `
      + "A shift to … would signal a worse path.";
  };

  // 3 · Key judgments
  const judgments = [1, 2, 3].map((i) => {
    const term = h("em");
    const showTerm = () => { term.textContent = estimativeTerm(f[`jp${i}`], config); };
    showTerm();
    return h("div", { class: "sg-row g10-judgment" },
      textInput(`Judgment ${i}${i === 1 ? " (required)" : ""}`, f[`j${i}`], set(`j${i}`), { placeholder: "A specific, checkable statement about the future" }),
      h("div", { class: "sg-stack g10-tight" },
        ui.slider({ label: "Probability %", min: 1, max: 99, step: 1, value: f[`jp${i}`], onChange: (v) => { f[`jp${i}`] = v; showTerm(); changed(); } }),
        ui.caption("→ ", term)));
  });

  // 4 · Drivers
  const DRIVERS = {
    drv_political: ["Political", "Elections, succession, coalition dynamics, protest…"],
    drv_security: ["Security", "Insurgency, crime, border disputes, military's role…"],
    drv_economic: ["Economic", "Inflation, debt, IMF programme, commodity exposure…"],
    drv_social: ["Social", "Youth unemployment, displacement, ethnic or religious cleavages…"],
  };
  const boxes = Object.fromEntries(Object.entries(DRIVERS).map(([k, [label, placeholder]]) => [k, textArea(label, f[k], set(k), { height: 150, placeholder })]));
  const prefill = () => {
    for (const [k, keys] of Object.entries(DRIVER_FACTS)) {
      // never over what the analyst has written; figures filled in earlier (another country) are refreshed
      if (!pyStrip(f[k]) || f[k] === filled[k]) {
        f[k] = filled[k] = facts(f.iso3, keys, ctx.core.values, scores, config);
        boxes[k].input.value = f[k];
      }
    }
    changed();
  };

  // 5 · Scenarios
  const total = h("div");
  const scenarioCards = SCENARIOS.map((s) => h("div", { class: "sg-card" }, h("div", { class: "sg-row g10-scenario" },
    numberInput(`${s} probability %`, f[`sp_${s}`], set(`sp_${s}`)),
    h("div", { class: "sg-stack" }, textArea(`${s}: what it looks like`, f[`sd_${s}`], set(`sd_${s}`), { height: 80 }),
      textInput(`${s}: signposts`, f[`ss_${s}`], set(`ss_${s}`))))));

  // 7 · Preview and download
  const downloadBox = h("div", { class: "sg-stack g10-tight" }), statusBox = h("div"), preview = h("div", { class: "sg-card g10-md" });
  let text = "";
  function changed() {
    const s = scores.get(f.iso3) ?? {};
    const fields = {
      country: name(), iso3: f.iso3, author: f.author, date: undefined, analyst_rating: f.rating, outlook: f.outlook,
      confidence: f.confidence, horizon: f.horizon, model_score: na(s.composite) ? "" : `${fixed(s.composite, 0)} (${s.tier})`,
      bluf: f.bluf, judgments: [1, 2, 3].map((i) => ({ text: f[`j${i}`], probability: f[`jp${i}`], term: estimativeTerm(f[`jp${i}`], config) })),
      drv_political: f.drv_political, drv_security: f.drv_security, drv_economic: f.drv_economic, drv_social: f.drv_social,
      scenarios: SCENARIOS.map((n) => ({ name: n, probability: Math.trunc(f[`sp_${n}`]), description: f[`sd_${n}`], signposts: f[`ss_${n}`] })),
      indicators_to_watch: f.watch, divergence: f.divergence, implications: f.implications, sources: f.sources,
    };
    text = buildAssessmentMarkdown(fields);
    drawModel();
    blufPlaceholder();
    const sum = SCENARIOS.reduce((a, n) => a + Math.trunc(f[`sp_${n}`]), 0);
    clear(total).append(sum !== 100 ? ui.callout("warning", `Scenario probabilities add up to ${sum}%. Adjust them so they total 100%.`) : "");
    clear(downloadBox).append(
      ui.download(`Download ${f.iso3}.md`, { data: () => text, filename: `${f.iso3}.md`, mime: "text/markdown", type: "primary", icon: null }),
      ui.caption("Add ", h("code", null, `${f.iso3}.md`), " to the project's ", h("code", null, "assessments/"),
        " folder; it shows on the country profile once the site is rebuilt."));
    const missing = [["bottom line", f.bluf], ["a key judgment", f.j1], ["sources", f.sources]].filter(([, v]) => !pyStrip(v)).map(([n]) => n);
    clear(statusBox).append(missing.length ? ui.callout("warning", `Still missing: ${missing.join(", ")}`) : ui.callout("success", "All core sections filled in."));
    clear(preview).append(...markdown(parseFrontMatter(text)[1]));
  }

  const scenariosHead = h("h2", null, "5 · Scenarios");
  scenariosHead.append(ui.helpMark("Probabilities should add up to 100%."));
  main.append(
    country, modelBox,
    ui.expander("Estimative language (ICD 203)", {}, terms,
      ui.caption("Pick a probability and the builder inserts the matching term, so words and numbers agree."), ui.cite("icd203")),
    h("h2", null, "1 · Rating"),
    h("div", { class: "sg-inputs" }, h("div", { class: "sg-row" }, rating, pick("Outlook", OUTLOOKS, "outlook"),
      pick("Confidence", CONFIDENCE, "confidence", "How solid is the evidence base? Low = thin or conflicting sources."),
      pick("Time horizon", HORIZONS, "horizon"))),
    textInput("Author", f.author, set("author")),
    h("h2", null, "2 · Bottom line up front"), bluf,
    h("h2", null, "3 · Key judgments"), ...judgments,
    h("h2", null, "4 · Drivers"),
    h("div", null, ui.button("Fill in the latest figures", { onClick: prefill,
      help: "Puts the latest figures in the driver boxes you have not written in. Replace them with your analysis: why it is happening and what comes next." })),
    h("div", { class: "sg-row" }, h("div", { class: "sg-stack" }, boxes.drv_political, boxes.drv_economic),
      h("div", { class: "sg-stack" }, boxes.drv_security, boxes.drv_social)),
    scenariosHead, ...scenarioCards, total,
    h("h2", null, "6 · Indicators, implications and sources"),
    textArea("Indicators to watch (one per line)", f.watch, set("watch"), { height: 110,
      placeholder: "Central bank reserves below 3 months of imports\nArmy statements on the election timetable" }),
    textArea("Why your rating differs from the model (if it does)", f.divergence, set("divergence"), { height: 100,
      placeholder: "The model is backward-looking: WGI data runs to last year and does not yet capture …" }),
    textArea("Implications for businesses, NGOs or governments", f.implications, set("implications"), { height: 100 }),
    textArea("Sources, one per line (required)", f.sources, set("sources"), { height: 110,
      placeholder: "IMF Article IV report, 2026\nCrisis Group, CrisisWatch, September 2026" }),
    h("h2", null, "7 · Preview and download"),
    h("div", { class: "sg-row" }, downloadBox, statusBox),
    preview,
    ui.footer());
  changed();
  return () => { here = location.pathname === "/builder"; };
}
