// Case studies: what the index showed the year before major political shocks (app_pages/cases.py). The readings
// follow the visitor's weights (computed here from ctx.history()); the cases and their red flags come from
// data/group10/cases.json.
import * as ui from "../lib/ui.js";
import * as charts from "../lib/charts.js";
import { h, clear } from "../lib/dom.js";
import { asRows } from "../lib/scoring.js";
import { fixed, signed } from "../lib/format.js";
import { countryTable } from "../lib/table.js";
import { reading } from "../group10/cases.js";
import { markdown } from "../group10/markdown.js";

export const title = "Case studies";
export const required = ["data/group10/cases.json"];

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const parts = (iso) => iso.split("-").map(Number);
const shortDate = (iso) => { const [y, m, d] = parts(iso); return `${d} ${MONTHS[m - 1].slice(0, 3)} ${y}`; }; // D MMM YYYY
const longDate = (iso) => { const [y, m, d] = parts(iso); return `${String(d).padStart(2, "0")} ${MONTHS[m - 1]} ${y}`; }; // %d %B %Y

// The case on show: kept when the page is drawn again while the visitor stays (a weights change), back to the first
// case on a new visit, as Streamlit keeps a page's widgets only while the visitor is on it
let pick = null;
let here = false;

export async function render(main, ctx) {
  const redraw = here;
  here = true;
  const leave = () => { here = location.pathname === "/cases"; };
  await ui.loadCss("/css/group10.css");
  main.append(...[ui.weightsNote(ctx), ui.hero(title)].filter(Boolean));
  const tail = () => [
    ui.caption("Scores are rebuilt with data as published today, including later revisions, and a year's governance scores "
      + "are only published the next year. These cases show how the index behaves; for a test of prediction, see the "
      + "track record on the Methodology page."),
    ui.cite(["index", "wikipedia", "ucdp_def"]),
    ui.footer(),
  ];
  let file;
  try {
    file = await ctx.fetchJSON("/data/group10/cases.json");
  } catch (err) {
    console.warn("section failed: case studies", err);
    main.append(ui.emptyState("The case studies can't be shown right now. The rest of the app still works."), ...tail());
    return leave;
  }
  const config = ctx.core.config;
  const hist = ctx.history();
  const countries = new Map(asRows(ctx.core.countries).map((c) => [c.iso3, c]));
  const name = (iso3) => countries.get(iso3)?.name ?? iso3;
  const readings = new Map(file.cases.map((c) => [c.key, reading(c, hist, config)]));

  // Scorecard and table
  const n = file.cases.length;
  main.append(h("div", { class: "g10-scorecard" }, Object.entries(file.verdicts).map(([v, [color]]) =>
    h("div", { class: "g10-score" }, h("div", { class: "g10-score-n" }, `${file.cases.filter((c) => readings.get(c.key).verdict === v).length} of ${n}`),
      h("div", { class: "g10-score-label", style: `color:${color}` }, v)))));
  const tableBox = h("div", { class: "g10-cases-table g10-nowrap" });
  main.append(tableBox);
  const rows = file.cases.map((c) => {
    const r = readings.get(c.key);
    return { key: c.key, country: name(c.iso3), event: c.title, date: c.date, verdict: r.verdict ?? "No data", tier: r.tier ?? null, rank: r.rank ?? null };
  });
  countryTable(tableBox, rows, { key: "key", columns: [
    { key: "country", label: "Country" }, { key: "event", label: "Event" },
    { key: "date", label: "Date", fmt: shortDate }, { key: "verdict", label: "Verdict" }, { key: "tier", label: "Tier" },
    { key: "rank", label: "Rank", fmt: (v) => String(Math.trunc(v)) },
  ] });
  const help = { 3: "Set by a fixed rule from the year before; each case shows it", 4: "In the year before the event",
    5: "In the year before the event. 1 = riskiest" };
  tableBox.querySelectorAll("thead th").forEach((th, i) => { if (help[i]) th.append(ui.helpMark(help[i])); });

  // One case
  const keys = file.cases.map((c) => c.key);
  if (!redraw || !keys.includes(pick)) pick = keys[0];
  const box = h("div", { class: "sg-stack" });
  const cleanups = [];
  const draw = () => {
    cleanups.splice(0).forEach((fn) => fn());
    drawCase(clear(box), file.cases.find((c) => c.key === pick), readings.get(pick), { file, hist, countries, name, cleanups });
  };
  main.append(ui.select({ label: "Case", options: keys, value: pick,
    format: (k) => { const c = file.cases.find((x) => x.key === k); return `${name(c.iso3)} · ${c.title} (${c.date.slice(0, 4)})`; },
    onChange: (k) => { pick = k; draw(); } }), box, ...tail());
  draw();
  return () => {
    leave();
    cleanups.splice(0).forEach((fn) => fn());
  };
}

function drawCase(box, c, r, { file, hist, countries, name, cleanups }) {
  const who = name(c.iso3);
  box.append(ui.countryHeading(`${who}: ${c.title}`, countries.get(c.iso3)?.iso2, 2),
    h("p", null, `${longDate(c.date)} · ${c.kind} · ${c.what} `, h("a", { href: c.source, target: "_blank", rel: "noopener" }, "Background ↗")));
  if (!r.verdict) {
    box.append(ui.callout("info", `The index has too little data on ${who} for ${r.before} to judge this case.`));
    return;
  }
  const [color, meaning] = file.verdicts[r.verdict];
  box.append(h("p", { class: "g10-verdict" }, h("span", { class: "g10-verdict-pill", style: `border-color:${color};color:${color}` }, r.verdict),
    " ", h("span", { class: "g10-verdict-meaning" }, meaning)));
  box.append(ui.kpiRow([
    { label: `Score in ${r.before} (of 100)`, value: fixed(r.score, 0), help: r.tier },
    { label: `Global rank (of ${r.n})`, value: String(r.rank), help: "1 = the riskiest economy that year" },
    { label: `Change since ${r.before - 3}`, value: r.change === null ? "—" : signed(r.change),
      help: "Composite score, three years before the year before the event" },
  ]));
  const chart = h("div", { class: "g10-chart" });
  box.append(chart);
  const rows = asRows(hist).filter((x) => x.iso3 === c.iso3).sort((a, b) => a.year - b.year);
  cleanups.push(charts.plot(chart, charts.caseHistory(rows, c.date, c.title)));

  const moves = Object.entries(r.pillar_moves).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  const left = h("div", { class: "sg-stack g10-tight" }, h("p", { class: "sg-strong" }, `What moved in the three years before (${r.before - 3}–${r.before})`),
    moves.length ? h("ul", null, moves.map(([p, m]) => h("li", null, `${m >= 1 ? "▲" : m <= -1 ? "▼" : "■"} ${p}: ${signed(m)} points`)))
      : ui.caption("Not enough history."));
  const right = h("div", { class: "sg-stack g10-tight" }, h("p", { class: "sg-strong" }, `Red flags in ${r.before}`),
    h("ul", null, r.flags.length ? r.flags.map((f) => h("li", null, ui.sevMark(f.severity), f.label)) : h("li", null, "None")));
  box.append(h("div", { class: "sg-pair" }, h("div", { class: "sg-row" }, left, right)));
  const note = file.cases.find((x) => x.key === c.key).commentary;
  if (note) box.append(h("h3", null, "Analyst commentary"), h("div", { class: "g10-md" }, markdown(note)));
}
