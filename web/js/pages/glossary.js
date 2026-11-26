// Glossary & legend: every term, abbreviation, colour and symbol used in Seismographic (app_pages/glossary.py).
import * as ui from "../lib/ui.js";
import { h, clear } from "../lib/dom.js";
import { cardGrid, glossarySearch, highlight } from "../charts/reference.js";

export const title = "Glossary & legend";
export const required = ["data/reference/glossary.json"];

// the search, kept for the visit as the app keeps its widgets (a redraw for new weights keeps it)
let kept = "";
const LEGEND = ["Legend", "#e8e6dc", "Tiers, pillar colours, colour scales and symbols."];
const slug = (name) => `g-${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "")}`;

// the text with the search query marked
const marked = (text, query) => (query ? highlight(text, query).map((p, i) => (i % 2 ? h("mark", { class: "sg-ref-mark" }, p) : p)) : text);

// A category header: name, term count, what it covers and the sources behind it
function band(name, color, blurb, { count = null, sources = [], compact = false } = {}) {
  return h("div", { id: slug(name), class: `sg-ref-band${compact ? " compact" : ""}`, style: `--c:${color}` },
    h("span", { class: "sg-ref-band-dot" }),
    h("div", { class: "sg-ref-band-body" },
      h("div", { class: "sg-ref-band-name" }, h("span", null, name), count === null ? null : h("span", { class: "sg-ref-count" }, `${count} term${count !== 1 ? "s" : ""}`)),
      h("div", { class: "sg-ref-band-blurb" }, blurb),
      sources.length ? h("div", { class: "sg-ref-backed" }, "Backed by: ", sources.flatMap((k, i) => [i ? " · " : null, ui.sourceLink(k)])) : null));
}

function termCard(t, color, query, config) {
  return h("div", { class: "sg-ref-term", style: `--c:${t.pillar ? config.PILLAR_COLORS[t.pillar] : color}` },
    h("div", { class: "sg-ref-term-name" }, marked(t.term, query)),
    h("div", { class: "sg-ref-term-def" }, marked(t.definition, query)),
    t.tags.map((tag) => h("span", { class: "sg-ref-tag" }, marked(tag, query))),
    t.link ? h("div", { class: "sg-ref-term-link" }, h("a", { href: t.link.url, target: "_blank", rel: "noopener" }, `${t.link.label} ↗`)) : null);
}

// A category's cards; the indicators are split by pillar, each in its pillar's colour
function categoryTerms(category, terms, color, query, doc, config) {
  const grid = (items) => cardGrid(items.map((t) => termCard(t, color, query, config)), 270, "sg-ref-terms");
  if (category !== doc.indicators_category) return [grid(terms)];
  return config.pillars.flatMap((p) => {
    const items = terms.filter((t) => t.pillar === p.key);
    return items.length ? [h("div", { class: "sg-ref-chip-row" }, ui.pillarChip(p.key)), grid(items)] : [];
  });
}

function scale(colours, name, low, high) {
  return h("div", { class: "sg-ref-scale" }, h("div", { class: "sg-ref-scale-title" }, name),
    h("div", { class: "sg-ref-blocks" }, colours.map((c) => h("i", { style: `background:${c}` }))),
    h("div", { class: "sg-ref-scale-ends" }, h("span", null, low), h("span", null, high)));
}

function legend(config, scales) {
  const sev = (k) => ui.sevMark(k, false);
  return h("div", { class: "sg-ref-legend" },
    h("div", { class: "sg-stack" },
      h("p", null, h("b", null, "Risk tiers"), " (composite score)"), ui.tierLegend(),
      h("p", null, h("b", null, "Pillars")), h("p", null, config.pillars.flatMap((p, i) => [i ? " " : null, ui.pillarChip(p.key, p.short)])),
      h("p", null, h("b", null, "Symbols")),
      h("ul", { class: "sg-ref-list" },
        h("li", null, sev("critical"), "Critical · ", sev("serious"), "Serious · ", sev("warning"), "Watch: red-flag severity"),
        ["⚑ a red-flag threshold crossed · ⚑ New: crossed since last year",
          "▲ riskier · ▼ safer · ■ moved less than 1 point: the change since last year",
          "Rank 1 = the highest risk, in every ranking", "✓ a written analyst assessment exists",
          "☆ follow · ★ following (kept in your browser)", "▶ play (replay the years on the globe, or play a video)"].map((t) => h("li", null, t)))),
    h("div", { class: "sg-stack" },
      h("p", null, h("b", null, "Colour scales")),
      h("div", null,
        scale(scales.composite, "Composite risk", "0 · lower risk", "higher risk · 100"),
        config.pillars.map((p) => scale(scales.pillars[p.key], `${p.short} pillar risk`, "lower", "higher")),
        scale(scales.change, "Change since last year (map of change)", "▼ safer", "riskier ▲"),
        scale(scales.next_event, "Next event (event calendar globe)", "now", "in a year")),
      ui.caption("Dim = low, bright = high. Dark grey = not enough data; near-black = outside your filters.")));
}

export async function render(main, ctx) {
  await ui.loadCss("/css/reference.css");
  const config = ctx.core.config;
  const doc = await ctx.fetchJSON("/data/reference/glossary.json").catch((err) => console.warn("section data missing: the glossary", err));
  if (!doc) {
    main.append(ui.hero(title), ui.emptyState("The glossary can't be shown right now. The rest of the app is unaffected."), ui.footer());
    return;
  }
  const body = h("div", { class: "sg-stack" });
  const input = h("input", { id: "sg-glossary-search", class: "sg-select-input", type: "text", autocomplete: "off",
    placeholder: "e.g. tier, inflation, WGI, IDP, red flag…" });
  const search = h("div", { class: "sg-field sg-ref-search" },
    h("div", { class: "sg-label-row" }, h("label", { class: "sg-label", for: input.id }, "Search the glossary")),
    h("div", { class: "sg-select" }, input));

  const contents = () => {
    const tiles = [[...LEGEND, null], ...doc.categories.map((c) => [c.name, c.color, c.blurb, c.terms.length])];
    clear(body).append(
      cardGrid(tiles.map(([name, , blurb, n]) => h("a", { class: "sg-ref-tile", href: `#${slug(name)}` },
        h("div", { class: "sg-ref-tile-head" }, h("span", null, name), h("span", null, n === null ? "" : `${n} terms`)),
        h("div", { class: "sg-ref-small" }, blurb))), 185),
      band(...LEGEND),
      legend(config, doc.scales),
      ...doc.categories.flatMap((c) => [
        band(c.name, c.color, c.blurb, { count: c.terms.length, sources: c.sources }),
        ...categoryTerms(c.name, c.terms, c.color, "", doc, config),
        c.sources.length ? null : ui.pageLink("/sources", "All sources and update dates", "verified"),
      ]).filter(Boolean),
      ui.footer());
  };
  const results = (query) => {
    const { hits, caption } = glossarySearch(doc.categories, query);
    clear(body).append(ui.caption(caption), ...(hits.length ? [] : [ui.emptyState("Nothing matches. Try a shorter word.")]),
      ...hits.flatMap((c) => [band(c.name, c.color, c.blurb, { count: c.terms.length, compact: true }),
        ...categoryTerms(c.name, c.terms, c.color, query, doc, config)]),
      ui.footer());
  };
  // as st.text_input: the search runs on Enter or when the box loses focus
  const apply = () => {
    const query = kept = input.value.trim();
    if (query) results(query);
    else contents();
  };
  input.addEventListener("change", apply);
  input.value = kept;
  apply();
  // the contents tiles jump to their category here: the address takes the #anchor without a history entry, whose
  // popstate would redraw the page
  body.addEventListener("click", (e) => {
    const a = e.target.closest?.("a.sg-ref-tile");
    const target = a && document.getElementById(a.getAttribute("href").slice(1));
    if (!target) return;
    e.preventDefault();
    history.replaceState(history.state, "", a.getAttribute("href"));
    target.scrollIntoView({ block: "start" });
  });
  main.append(ui.hero(title), search, body);
  const jump = () => document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView({ block: "start" });
  if (location.hash) document.fonts.ready.then(() => requestAnimationFrame(jump)); // after the font swap moves the text
}
