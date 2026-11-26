// Presentational pieces shared by the pages: ports of prm/ui.py helpers, plus form controls drawn like Streamlit's.
// Every function returns a DOM node (or null for "nothing to show"); class names are sg-* and styled by css/app.css.
import { h, clear } from "./dom.js";
import { countdown, fixed, trendLabel, trendSaid, TREND_THRESHOLD } from "./format.js";
import { asRows, na } from "./scoring.js";
import { countryTable, flagUrl } from "./table.js";
import { conf } from "./ctx.js";
import * as follow from "./follow.js";

let seq = 0;
const uid = (p = "sg") => `${p}-${++seq}`;
const text = (v) => (v instanceof Node ? v : v === null || v === undefined ? "" : String(v));

// ---------------------------------------------------------------------------------------------------------------
// Small pieces
// ---------------------------------------------------------------------------------------------------------------
// A Material icon from /vendor/icons, painted in the text colour (decoration: hidden from screen readers)
export const icon = (name) => h("span", { class: "sg-icon", "aria-hidden": "true", style: `--i:url(/vendor/icons/${name}.svg)` });

// Inline SVGs for the few interface glyphs that are not in /vendor/icons (Material Symbols paths, viewBox 0 -960 960 960)
const GLYPHS = {
  chevron: "M480-345 240-585l56-56 184 184 184-184 56 56-240 240Z",
  close: "m256-200-56-56 224-224-224-224 56-56 224 224 224-224 56 56-224 224 224 224-56 56-224-224-224 224Z",
  expand: "M383-480 200-664l56-56 240 240-240 240-56-56 183-184Zm264 0L464-664l56-56 240 240-240 240-56-56 183-184Z",
  collapse: "M440-240 200-480l240-240 56 56-183 184 183 184-56 56Zm264 0L464-480l240-240 56 56-183 184 183 184-56 56Z",
};
export function glyph(name, cls = "sg-glyph") {
  const span = h("span", { class: cls, "aria-hidden": "true" });
  span.innerHTML = `<svg viewBox="0 -960 960 960" width="1em" height="1em" fill="currentColor"><path d="${GLYPHS[name]}"/></svg>`;
  return span;
}

// st.caption, st.info / st.warning / st.error / st.success
export const caption = (...children) => h("p", { class: "sg-caption" }, children.map(text));
export const callout = (kind, ...children) => h("div", { class: `sg-callout sg-${kind}`, role: kind === "error" ? "alert" : null }, children.map(text));
export const emptyState = (message) => callout("info", message);

// Screen-reader-only text
export const sr = (t) => h("span", { class: "sg-sr" }, t);

// ---- floating panels (popovers, tooltips, select menus) ----------------------------------------------------------
// They open in the browser's top layer (the Popover API), at a fixed spot next to what opened them, so no clipping or
// containing box around them (the KPI strip, the sidebar's scroll box, a table) can cut them and nothing covers them.
// They follow their anchor when the page scrolls, and scroll inside themselves when taller than the room. Without the
// Popover API they are fixed-position boxes in place.
const TOP_LAYER = typeof HTMLElement !== "undefined" && "showPopover" in HTMLElement.prototype;
const WIDE = "(min-width: 768px)"; // the sidebar sits beside the page from here up (app.js)

// The room a floating panel may use: the sidebar's box for one opened from the sidebar, else the window beside the
// open sidebar. viewport {width, height}; sidebar: the sidebar's rect when it is open beside the page (or holds the
// panel's anchor), else null.
export function visibleArea(viewport, sidebar = null, inSidebar = false) {
  if (sidebar && inSidebar) return { left: sidebar.left, right: sidebar.right, top: 0, bottom: viewport.height };
  return { left: sidebar ? Math.max(0, sidebar.right) : 0, right: viewport.width, top: 0, bottom: viewport.height };
}

// Where a panel of `size` goes beside `anchor` (a rect) inside `area`: below it ("down") or above it ("up"), or on the
// side with more room when it does not fit where asked; its start ("start") or end ("end") lined up with the anchor's,
// then moved sideways to stay `margin` inside the area (its left edge wins when it is wider than the area). It is not
// held inside the area vertically: it stays with its anchor, also when the anchor scrolls away. maxHeight: the room on
// its side, for a panel taller than that to scroll inside itself.
export function floatPosition(anchor, size, area, { placement = "down", align = "start", gap = 8, margin = 8 } = {}) {
  const wanted = align === "end" ? anchor.right - size.width : anchor.left;
  const left = Math.max(area.left + margin, Math.min(wanted, area.right - margin - size.width));
  const roomBelow = area.bottom - margin - (anchor.bottom + gap), roomAbove = anchor.top - gap - (area.top + margin);
  const first = placement === "up" ? roomAbove : roomBelow, other = placement === "up" ? roomBelow : roomAbove;
  const keep = size.height <= first || (size.height > other && first >= other);
  const up = (placement === "up") === keep;
  const maxHeight = Math.max(0, Math.floor(up ? roomAbove : roomBelow));
  const top = up ? anchor.top - gap - Math.min(size.height, maxHeight) : anchor.bottom + gap;
  return { left, top, maxHeight };
}

// A fixed box inside a layout-contained ancestor (container queries, without the top layer) is placed against that
// ancestor, not the window: the style that puts it where it was wanted, or null when it is already there
export function floatCorrection(wanted, got, styled) {
  const dx = wanted.left - got.left, dy = wanted.top - got.top;
  return Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5 ? null : { left: styled.left + dx, top: styled.top + dy };
}

function areaFor(anchor) {
  const side = document.getElementById("sidebar");
  const inSide = !!side?.contains(anchor);
  const beside = document.body.dataset.sidebar === "open" && matchMedia(WIDE).matches;
  return visibleArea({ width: document.documentElement.clientWidth, height: innerHeight },
    side && (inSide || beside) ? side.getBoundingClientRect() : null, inSide);
}

// Marks a new element as a floating panel (closed)
function floating(panel) {
  panel.setAttribute("data-float", "");
  if (TOP_LAYER) panel.setAttribute("popover", "manual");
  else panel.hidden = true;
  return panel;
}
const isFloatOpen = (panel) => (TOP_LAYER ? panel.matches(":popover-open") : !panel.hidden);

// The element, or its first ancestor that has a box: a display: contents wrapper has none (its rect is all zeros)
export function layoutBox(el) {
  while (el && !el.getClientRects().length) el = el.parentElement;
  return el ?? null;
}

// Puts a shown panel beside its anchor (opts as floatPosition; matchWidth: as wide as the anchor)
function placeFloat(panel, anchor, opts = {}) {
  const box = (layoutBox(anchor) ?? anchor).getBoundingClientRect();
  if (opts.matchWidth) panel.style.width = `${box.width}px`;
  const scrolled = panel.scrollTop; // measuring without the height limit would lose it
  panel.style.maxHeight = "";
  const r = panel.getBoundingClientRect(), cap = parseFloat(getComputedStyle(panel).maxHeight); // a menu's own 300px
  const p = floatPosition(box, { width: r.width, height: r.height }, areaFor(anchor), opts);
  const maxHeight = Number.isFinite(cap) ? Math.min(cap, p.maxHeight) : p.maxHeight;
  Object.assign(panel.style, { left: `${p.left}px`, top: `${p.top}px`, maxHeight: `${maxHeight}px` });
  const fix = floatCorrection(p, panel.getBoundingClientRect(), p);
  if (fix) Object.assign(panel.style, { left: `${fix.left}px`, top: `${fix.top}px` });
  panel.scrollTop = scrolled;
}

// Opens a floating panel beside its anchor and keeps it there while the page scrolls. onGone: called instead of a
// placement once the anchor has left the page (the page was replaced). Returns {place, close}.
function openFloat(panel, anchor, opts, onGone = null) {
  if (TOP_LAYER) panel.showPopover();
  else panel.hidden = false;
  const place = () => {
    if (anchor.isConnected && panel.isConnected) placeFloat(panel, anchor, opts);
    else (onGone ?? close)();
  };
  const onScroll = (e) => { if (!(e.target instanceof Node && panel.contains(e.target))) place(); }; // not its own scrolling
  const close = () => {
    removeEventListener("scroll", onScroll, true);
    removeEventListener("resize", place);
    if (!TOP_LAYER) panel.hidden = true;
    else if (panel.matches(":popover-open")) panel.hidePopover();
  };
  place();
  addEventListener("scroll", onScroll, true);
  addEventListener("resize", place);
  return { place, close };
}

// The tooltip on screen (one at a time): {tip, anchor, close}. Escape closes it however it opened, and only it: the
// Escape is used up (a popover or the phone sidebar under it stays open), unless the tip had already left the page.
let activeTip = null;
const openPopovers = new Set(); // their close()
// The page is being replaced: close its tooltip and popovers, and drop their listeners
export function closeFloats() {
  activeTip?.close();
  for (const close of [...openPopovers]) close();
}
export const tipIsLive = (t) => !!t && t.anchor.isConnected && t.tip.isConnected && isFloatOpen(t.tip);
if (typeof document !== "undefined") {
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape" || !activeTip) return;
    const live = tipIsLive(activeTip);
    activeTip.close();
    if (live) e.stopPropagation();
  }, true);
}

// A tooltip for `anchor`: shows while the pointer is over hoverTarget (default the anchor) or the tip, and while the
// anchor has keyboard focus; Escape closes it. Its id is added to the anchor's aria-describedby. Returns the tip: put
// it in the page next to the anchor, outside any <label> (if it is not in the page when it first shows, it is added
// right after the anchor). placement/align/gap as floatPosition.
export function tooltip(anchor, text, { hoverTarget = anchor, placement = "down", align = "end", gap = 6 } = {}) {
  const tip = floating(h("span", { class: "sg-tip", role: "tooltip", id: uid("tip") }, text));
  anchor.setAttribute("aria-describedby", [anchor.getAttribute("aria-describedby"), tip.id].filter(Boolean).join(" "));
  let handle = null, timer = 0;
  const state = { tip, anchor, close: () => hide() };
  const hide = () => {
    clearTimeout(timer);
    handle?.close();
    handle = null;
    if (activeTip === state) activeTip = null;
  };
  const show = () => {
    clearTimeout(timer);
    if (handle) return;
    if (!tip.isConnected) anchor.after(tip);
    if (activeTip && activeTip !== state) activeTip.close();
    handle = openFloat(tip, anchor, { placement, align, gap }, hide);
    activeTip = state;
  };
  // a short grace on leaving, so the pointer can cross the gap onto the tip without it closing
  const leave = () => {
    clearTimeout(timer);
    if (document.activeElement !== anchor) timer = setTimeout(hide, 150);
  };
  anchor.addEventListener("focus", show);
  anchor.addEventListener("blur", hide);
  for (const el of new Set([hoverTarget, tip])) {
    el.addEventListener("mouseenter", show);
    el.addEventListener("mouseleave", leave);
  }
  return tip;
}

// Deprecated (use tooltip() or popover()): a hand-made .sg-tip shown by its parent's "open" class goes in the top layer
// below the first box around it (the header cell for a display: contents parent), inside the visible area, and follows
// it while the page scrolls, until the parent loses "open". Kept so callers written against the first shell still work.
const kept = new WeakMap(); // such tips on screen -> their close()
export function keepInView(panel, margin = 8) {
  const parent = panel?.parentElement;
  if (!parent?.classList.contains("open")) return;
  kept.get(panel)?.();
  if (TOP_LAYER) panel.popover = "manual";
  let float = null;
  const watch = new MutationObserver(() => { if (!parent.classList.contains("open")) close(); });
  const close = () => { watch.disconnect(); float?.close(); kept.delete(panel); };
  float = openFloat(panel, parent, { placement: "down", align: "start", margin }, close);
  watch.observe(parent, { attributeFilter: ["class"] });
  kept.set(panel, close);
}

// Touch screens: a help mark's tap area grows to 44px on each side where that does not reach another control, measured
// when the mark comes on screen (a hidden tab's marks have no layout before) and again after a resize
const CONTROLS = "a[href], button, input, select, textarea, summary, label, .sg-select, [tabindex], [onclick], " +
  "[role=button], [role=tab], [role=radio], [role=switch], [role=combobox], [role=option], [role=slider]";
const helpAreas = typeof matchMedia === "function" && matchMedia("(pointer: coarse)").matches && typeof IntersectionObserver === "function"
  ? new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) { helpAreas.unobserve(e.target); fitHelpArea(e.target); }
  })
  : null;
if (helpAreas) {
  let wait = 0;
  addEventListener("resize", () => {
    clearTimeout(wait);
    wait = setTimeout(() => document.querySelectorAll(".sg-help-wrap[style*='--hit']").forEach(fitHelpArea), 200);
  });
}
export function fitHelpArea(wrap) {
  const box = wrap.getBoundingClientRect();
  if (!box.width) return;
  const cx = (box.left + box.right) / 2, cy = (box.top + box.bottom) / 2, R = 22; // half of 44
  const reach = { top: R - box.height / 2, right: R - box.width / 2, bottom: R - box.height / 2, left: R - box.width / 2 };
  for (const el of document.querySelectorAll(CONTROLS)) {
    if (wrap.contains(el) || el.contains(wrap)) continue;
    for (const r of el.getClientRects()) {
      if (!r.width || !r.height || r.right < cx - R - 2 || r.left > cx + R + 2 || r.bottom < cy - R - 2 || r.top > cy + R + 2) continue;
      // keep 2px clear of it on the side it is on
      if (r.top < cy + R && r.bottom > cy - R && r.right <= box.left) reach.left = Math.min(reach.left, box.left - r.right - 2);
      else if (r.top < cy + R && r.bottom > cy - R && r.left >= box.right) reach.right = Math.min(reach.right, r.left - box.right - 2);
      else if (r.bottom <= box.top) reach.top = Math.min(reach.top, box.top - r.bottom - 2);
      else if (r.top >= box.bottom) reach.bottom = Math.min(reach.bottom, r.top - box.bottom - 2);
    }
  }
  // never under 24px across (the minimum target size): a side with no room gives its share to the other
  const pair = (a, b) => {
    [a, b] = [Math.max(0, Math.floor(a)), Math.max(0, Math.floor(b))];
    const short = 8 - a - b;
    return short <= 0 ? [a, b] : a >= b ? [a + short, b] : [a, b + short];
  };
  const [top, bottom] = pair(reach.top, reach.bottom), [left, right] = pair(reach.left, reach.right);
  wrap.style.setProperty("--hit", [top, right, bottom, left].map((v) => `${-v}px`).join(" "));
}

// A help mark (the (?) after a label): its text shows on hover and on keyboard focus, and describes the control
// (pass the mark's tipId to aria-describedby).
export function helpMark(help) {
  if (!help) return null;
  const mark = h("span", { class: "sg-icon sg-help", style: "--i:url(/vendor/icons/help.svg)", role: "img", "aria-label": "Help", tabindex: "0" });
  const wrap = h("span", { class: "sg-help-wrap" }, mark);
  const tip = tooltip(mark, help, { hoverTarget: wrap });
  wrap.append(tip);
  wrap.tipId = tip.id;
  helpAreas?.observe(wrap);
  return wrap;
}

// Loads a page group's stylesheet once (web/css/<group>.css); resolves when it has loaded (or failed)
const sheets = new Map();
export function loadCss(href) {
  if (!sheets.has(href)) {
    sheets.set(href, new Promise((resolve) => {
      const link = h("link", { rel: "stylesheet", href });
      link.onload = link.onerror = () => resolve(link);
      document.head.append(link);
    }));
  }
  return sheets.get(href);
}

// ui.guard: draws an optional section; if it throws (or its promise rejects, e.g. a missing data file), a one-line
// note takes its place and the rest of the page carries on. fn(box) fills the returned box.
function sectionFailed(box, what, err) {
  console.warn(`section failed: ${what}`, err);
  clear(box).append(caption(`${what} can't be shown right now. The rest of the page is unaffected.`));
}

export function guard(what, fn) {
  const box = h("div", { class: "sg-guard" });
  const fail = (err) => sectionFailed(box, what, err);
  try {
    const r = fn(box);
    if (r && typeof r.then === "function") r.catch(fail);
  } catch (err) {
    fail(err);
  }
  return box;
}

// ---------------------------------------------------------------------------------------------------------------
// Headings, badges, flags
// ---------------------------------------------------------------------------------------------------------------
// The page title (the screen's one h1) and an optional line about the data under it
export const hero = (title, subtitle = "") =>
  h("div", { class: "sg-head" }, h("h1", { class: "sg-head-title" }, title), subtitle ? h("p", { class: "sg-head-sub" }, subtitle) : null);

// The tier as a pill whose weight rises with the risk: Low and Moderate outlined, Elevated and up filled, Severe ringed
export function tierBadge(tier, prefix = "") {
  const tiers = conf().tiers;
  const i = tiers.findIndex((t) => t.label === tier);
  if (i < 0) return h("span", { class: "sg-not-rated" }, "Not rated");
  const t = tiers[i];
  const style = i >= 2 ? `border-color:${t.color};background:${t.color};color:${t.text_on}` : `border-color:${t.color}`;
  return h("span", { class: `sg-pill${i === tiers.length - 1 ? " sg-pill-top" : ""}`, style }, `${prefix}${tier}`);
}

// The five tiers with their lower bounds, then the grey a country without enough data gets on the maps
export function tierLegend() {
  const c = conf();
  return h("div", { class: "sg-tier-legend" },
    c.tiers.map((t) => [tierBadge(t.label), h("span", { class: "sg-tier-lower" }, `${Math.trunc(t.lower)}+`)]),
    h("span", { class: "sg-pill sg-pill-nodata", style: `border-color:${c.NO_DATA_COLOR};background:${c.NO_DATA_COLOR}` }, "No data"));
}

// A small label in the pillar's colour, tying headings to the pillar charts and maps
export function pillarChip(key, label = null) {
  const c = conf();
  const color = c.PILLAR_COLORS[key];
  return h("span", { class: "sg-chip", style: `border-left-color:${color};background:${color}1f` },
    label ?? c.pillars.find((p) => p.key === key)?.label ?? key);
}

// A flag image (none for codes without a flag, e.g. JG)
export function flagImg(iso2, height = "1em") {
  const url = flagUrl(iso2, conf().NO_FLAG);
  return url ? h("img", { class: "sg-flag-inline", src: url, alt: "", style: `height:${height}` }) : null;
}

// A heading with the country's flag in front (css: an extra class, e.g. sg-panel-title)
export const countryHeading = (name, iso2, level = 1, css = "") =>
  h(`h${level}`, { class: css || null }, flagImg(iso2, "0.85em"), name);

// The coloured severity dot; spoken: screen readers hear the word instead ("Serious: ")
export function sevMark(severity, spoken = true) {
  const c = conf();
  const frag = document.createDocumentFragment();
  frag.append(h("span", { class: "sg-sev", style: `--c:${c.SEVERITY_COLOR[severity]}`, "aria-hidden": "true" }));
  if (spoken) frag.append(sr(`${c.SEVERITY_LABEL[severity]}: `));
  return frag;
}

// ---------------------------------------------------------------------------------------------------------------
// Sources
// ---------------------------------------------------------------------------------------------------------------
const sourceLabel = (key) => conf().CITE_LABELS[key] ?? conf().SOURCES[key]?.name ?? key;

// A link to a source that opens in a new tab
export function sourceLink(key, label = null) {
  const s = conf().SOURCES[key];
  return h("a", { href: s?.url ?? "#", target: "_blank", rel: "noopener" }, `${label ?? sourceLabel(key)} ↗`);
}

// A linked "Sources:" line under a number, chart or table; "index" stands for the datasets the index is built from
export function cite(keys, { note = null } = {}) {
  const c = conf();
  const all = [...new Set([keys].flat().flatMap((k) => (k === "index" ? c.INDEX_SOURCES : [k])))].filter((k) => c.SOURCES[k]);
  const links = all.map((k) => h("a", { href: c.SOURCES[k].url, target: "_blank", rel: "noopener" }, sourceLabel(k)));
  const parts = [];
  links.forEach((a, i) => {
    if (i) parts.push(i === links.length - 1 ? " · " : " · "); // the last two share a line
    parts.push(a);
  });
  return h("p", { class: "sg-caption" }, "Sources: ", parts, note ? `. ${note}` : "");
}

// ---------------------------------------------------------------------------------------------------------------
// Country header and readouts
// ---------------------------------------------------------------------------------------------------------------
// The top of a country profile: identity on the left; the score with tier, rank, change (and analyst) on the right.
// row: the country's master-table row; meta: text or a node under the name; onAnalyst: opens the assessment.
export function countryHeader(name, row, delta, year, meta, { analystRating = null, onAnalyst = null } = {}) {
  let rank = null, change = null;
  if (!na(row.rank)) {
    const said = `Rank ${Math.trunc(row.rank)} of ${Math.trunc(row.n_ranked)}; 1 is the highest risk`;
    rank = h("span", { title: said }, h("span", { "aria-hidden": "true" }, `#${Math.trunc(row.rank)} of ${Math.trunc(row.n_ranked)}`), sr(said));
  }
  if (!na(delta)) {
    const tone = delta >= TREND_THRESHOLD ? "var(--sg-worse)" : delta <= -TREND_THRESHOLD ? "var(--sg-better)" : "var(--sg-faint)";
    const said = trendSaid(delta, year);
    change = h("span", { title: said }, h("span", { "aria-hidden": "true" }, h("span", { style: `color:${tone}` }, trendLabel(delta)), ` vs ${year - 1}`), sr(said));
  }
  let analyst = null;
  if (analystRating) {
    const line = [h("span", { class: "sg-cs-link" }, "Analyst"), ": ", tierBadge(analystRating)];
    analyst = onAnalyst
      ? h("button", { type: "button", class: "sg-cs-line sg-cs-analyst", "aria-label": `Analyst: ${analystRating}. Open the assessment`, onclick: onAnalyst }, line)
      : h("div", { class: "sg-cs-line" }, line);
  }
  return h("div", { class: "sg-country-head" },
    h("div", { class: "sg-country-id" }, flagUrl(row.iso2, conf().NO_FLAG) ? h("img", { src: flagUrl(row.iso2, conf().NO_FLAG), alt: "" }) : null,
      h("div", null, h("h1", { class: "sg-country-name" }, name), h("div", { class: "sg-country-meta" }, text(meta)))),
    h("div", { class: "sg-country-score" },
      h("div", { class: "sg-cs-num" }, na(row.composite) ? "—" : fixed(row.composite, 0), h("span", null, "/100")),
      h("div", { class: "sg-cs-side" }, tierBadge(row.tier), h("div", { class: "sg-cs-line" }, rank), h("div", { class: "sg-cs-line" }, change), analyst)));
}

// A row of headline numbers (st.metric in columns): one bordered strip split by 1px rules, reflowing by its own width.
// items: [{label, value, delta, deltaColor: "normal"|"inverse"|"off", note, help}]
export function metric({ label, value, delta = null, deltaColor = "normal", note = null, help = null }) {
  let deltaEl = null;
  if (delta !== null && delta !== undefined && delta !== "") {
    const s = String(delta);
    const down = typeof delta === "number" ? delta < 0 : s.startsWith("-");
    const zero = typeof delta === "number" ? delta === 0 : /^[+-]?0(\.0+)?$/.test(s);
    const good = deltaColor === "inverse" ? down : !down;
    const tone = zero || deltaColor === "off" ? "off" : good ? "better" : "worse";
    deltaEl = h("span", { class: `sg-delta sg-delta-${tone}` }, zero ? "" : h("span", { "aria-hidden": "true" }, down ? "↓ " : "↑ "), s);
  }
  return h("div", { class: "sg-metric" },
    h("div", { class: "sg-metric-label" }, label, helpMark(help)),
    h("div", { class: "sg-metric-value" }, text(value)),
    deltaEl || note ? h("div", { class: "sg-metric-delta" }, deltaEl, note ? h("span", { class: "sg-metric-note" }, note) : null) : null);
}
export const kpiRow = (items) => h("div", { class: `sg-kpis${items.length === 4 ? " sg-kpis-4" : ""}` }, items.map(metric));

// ---------------------------------------------------------------------------------------------------------------
// Tabs and views bound to the address
// ---------------------------------------------------------------------------------------------------------------
// Lazy tabs ({slug: label}) kept in the address as ?tab=<slug>. A tab's content is drawn the first time it opens:
// urlTabs(el, tabs, ctx).on("map", (panel) => ...).on("news", ...). An unknown ?tab= opens the first tab.
export function urlTabs(el, tabs, ctx) {
  const slugs = Object.keys(tabs);
  const asked = ctx.params.get("tab");
  let open = slugs.includes(asked) ? asked : slugs[0];
  if (asked !== null && asked !== open) ctx.setParam("tab", open);
  const renderers = new Map(), drawn = new Set(), buttons = {}, panels = {};
  const list = h("div", { class: "sg-tablist", role: "tablist" });
  const box = h("div", { class: "sg-tabs" }, list);
  for (const slug of slugs) {
    const id = uid("tab");
    buttons[slug] = h("button", { type: "button", role: "tab", class: "sg-tab", id: `${id}-t`, "aria-controls": `${id}-p`, onclick: () => select(slug, true) }, text(tabs[slug]));
    panels[slug] = h("div", { role: "tabpanel", class: "sg-tabpanel", id: `${id}-p`, "aria-labelledby": `${id}-t`, tabindex: "0", hidden: true });
    list.append(buttons[slug]);
    box.append(panels[slug]);
  }
  list.addEventListener("keydown", (e) => {
    const step = { ArrowRight: 1, ArrowLeft: -1, Home: -Infinity, End: Infinity }[e.key];
    if (step === undefined) return;
    e.preventDefault();
    const i = Math.max(0, Math.min(slugs.length - 1, Number.isFinite(step) ? slugs.indexOf(open) + step : step < 0 ? 0 : slugs.length - 1));
    select(slugs[i], true);
    buttons[slugs[i]].focus();
  });
  el.append(box);
  // phones: the tab row scrolls sideways, so a tab opened from a link (?tab=map) is brought into view once
  requestAnimationFrame(() => {
    if (list.scrollWidth <= list.clientWidth) return;
    const r = buttons[open].getBoundingClientRect(), row = list.getBoundingClientRect();
    if (r.left < row.left || r.right > row.right) list.scrollLeft += r.left - row.left - (row.width - r.width) / 2;
  });
  // a tab that fails shows a one-line note in its panel; the other tabs and the rest of the page keep working
  function draw(slug) {
    if (drawn.has(slug) || !renderers.has(slug)) return;
    drawn.add(slug);
    const fail = (err) => {
      if (panels[slug].isConnected) sectionFailed(panels[slug], tabs[slug], err);
      else console.warn("a section failed after its page was left or redrawn", err);
    };
    try {
      const r = renderers.get(slug)(panels[slug]);
      if (r && typeof r.then === "function") r.catch(fail);
    } catch (err) {
      sectionFailed(panels[slug], tabs[slug], err); // drawn just now: the panel may not be in the page yet
    }
  }
  function select(slug, byUser) {
    open = slug;
    for (const s of slugs) {
      buttons[s].setAttribute("aria-selected", String(s === slug));
      buttons[s].tabIndex = s === slug ? 0 : -1;
      panels[s].hidden = s !== slug;
    }
    if (byUser) {
      ctx.setParam("view", null); // a view belongs to its tab: it comes back with the tab (sg:show)
      ctx.setParam("tab", slug);
      panels[slug].dispatchEvent(new Event("sg:show"));
    }
    draw(slug);
  }
  select(open, false);
  const api = {
    get open() { return open; },
    on(slug, render) { renderers.set(slug, render); if (slug === open) draw(slug); return api; },
    select: (slug) => select(slug, true),
  };
  return api;
}

// A segmented control of views ({slug: label}) inside a tab, kept as ?view=<slug>.
// urlView(el, "Show", views, ctx).on((slug) => draw(slug)) calls back now and on every change.
export function urlView(el, label, views, ctx) {
  const slugs = Object.keys(views);
  const asked = ctx.params.get("view");
  let value = slugs.includes(asked) ? asked : slugs[0];
  const listeners = [];
  const control = segmented({ label, labelHidden: true, options: slugs, value, format: (s) => views[s],
    onChange: (s) => { value = s; ctx.setParam("view", s); listeners.forEach((fn) => fn(s, views[s])); } });
  el.append(control);
  ctx.setParam("view", value);
  queueMicrotask(() => control.closest(".sg-tabpanel")?.addEventListener("sg:show", () => ctx.setParam("view", value)));
  const api = { get value() { return value; }, on(fn) { listeners.push(fn); fn(value, views[value]); return api; } };
  return api;
}

// ---------------------------------------------------------------------------------------------------------------
// News, video, events, movers, followed countries, data status, footer
// ---------------------------------------------------------------------------------------------------------------
export function timeAgo(when, now = Date.now()) {
  const t = typeof when === "number" ? when : Date.parse(when);
  if (!Number.isFinite(t)) return "";
  const minutes = Math.floor((now - t) / 60000);
  if (minutes < 60) return `${Math.max(minutes, 1)} min ago`;
  if (minutes < 60 * 24) return `${Math.floor(minutes / 60)} h ago`;
  return `${Math.floor(minutes / (60 * 24))} d ago`;
}

// Latest headlines. news: {articles: [{title, url, domain, seen, image}], error, source, fetched} or null (no file)
export function newsList(news, { limit = 10 } = {}) {
  if (!news || news.error) return callout("info", "Headlines are unavailable right now. They refresh every day.");
  const articles = (news.articles ?? []).slice(0, limit);
  if (!articles.length) return callout("info", "No matching headlines in the last 7 days.");
  const items = articles.map((a) => {
    const meta = [a.domain ? h("bdi", null, a.domain) : null, timeAgo(a.seen).replace(/ /g, " ")].filter(Boolean);
    const image = typeof a.image === "string" && a.image.startsWith("https://")
      ? h("img", { class: "sg-news-thumb", src: a.image, alt: "", loading: "lazy" }) : null;
    const body = [image, h("span", { class: "sg-news-text" }, h("span", { class: "sg-news-title" }, a.title ?? ""),
      h("span", { class: "sg-news-meta" }, meta.flatMap((m, i) => (i ? [" · ", m] : [m]))))];
    return h("li", null, String(a.url ?? "").startsWith("http") ? h("a", { href: a.url, target: "_blank", rel: "noopener" }, body) : h("span", null, body));
  });
  return h("div", { class: "sg-news-box" }, h("ul", { class: "sg-news" }, items),
    caption(`${news.source ?? "News feeds"} · fetched ${news.fetched ?? "recently"} · refreshed daily. Collected automatically and unchecked: verify before citing.`));
}

// A channel's 24/7 live stream through YouTube's privacy-enhanced embed
export const livePlayer = (channelId, height = 460) =>
  h("iframe", { class: "sg-video-frame", style: `height:${height}px`, title: "Live news", allowfullscreen: true,
    src: `https://www.youtube-nocookie.com/embed/live_stream?channel=${encodeURIComponent(channelId)}&rel=0`,
    allow: "autoplay; encrypted-media; picture-in-picture; fullscreen", referrerpolicy: "strict-origin-when-cross-origin" });

// Video thumbnails; "Play here" plays one in a player above the grid.
// videos: [{video_id, title, channel, published, thumbnail, views}]
export function videoGallery(videos, { limit = 9, columns = 3 } = {}) {
  const shown = (videos ?? []).slice(0, limit);
  const player = h("div", { class: "sg-video-player" });
  const play = (v) => {
    clear(player).append(
      h("iframe", { class: "sg-video-frame", title: v.title, allowfullscreen: true, referrerpolicy: "strict-origin-when-cross-origin",
        src: `https://www.youtube-nocookie.com/embed/${encodeURIComponent(v.video_id)}?autoplay=1&rel=0`,
        allow: "autoplay; encrypted-media; picture-in-picture; fullscreen" }),
      caption(h("b", null, v.title), ` · ${v.channel} · ${timeAgo(v.published)}`));
    player.scrollIntoView({ block: "nearest", behavior: "smooth" });
  };
  const cards = shown.map((v) => {
    const url = `https://www.youtube.com/watch?v=${encodeURIComponent(v.video_id)}`;
    const views = Number(v.views) >= 1000 ? ` · ${fixed(v.views / 1000, 0, { group: true })}k views` : "";
    return h("div", { class: "sg-card sg-vidcard" },
      h("img", { class: "sg-vid-thumb", src: v.thumbnail, alt: "", loading: "lazy" }),
      h("a", { class: "sg-vid-title", href: url, target: "_blank", rel: "noopener" }, v.title),
      caption(`${v.channel} · ${timeAgo(v.published)}${views}`),
      button("Play here", { icon: "play_arrow", width: "stretch", onClick: () => play(v) }));
  });
  return h("div", { class: "sg-videos" }, player, h("div", { class: "sg-grid", style: `--cols:${columns}` }, cards));
}

// Upcoming events from the calendar with a countdown. events: [{date: "YYYY-MM-DD", event, country, significance, source_url}]
export function upcomingEvents(events, { limit = 8, today = new Date() } = {}) {
  const day = (d) => Math.floor(Date.parse(`${String(d).slice(0, 10)}T00:00:00Z`) / 864e5);
  const now = Math.floor(Date.UTC(today.getFullYear(), today.getMonth(), today.getDate()) / 864e5);
  const upcoming = (events ?? []).filter((e) => day(e.date) >= now).sort((a, b) => day(a.date) - day(b.date)).slice(0, limit);
  if (!upcoming.length) return caption("No upcoming events on the calendar.");
  const fmt = (d) => new Date(`${String(d).slice(0, 10)}T00:00:00Z`).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" });
  return h("ul", { class: "sg-events" }, upcoming.map((e) => {
    const high = String(e.significance).toLowerCase() === "high";
    const source = String(e.source_url ?? "").startsWith("http") ? [" · ", h("a", { href: e.source_url, target: "_blank", rel: "noopener" }, "source")] : [];
    return h("li", null, h("b", null, e.event), h("br"),
      h("span", { class: "sg-events-meta" }, `${e.country} · ${fmt(e.date)} · `,
        h("span", { class: high ? "sg-events-high" : null }, `${countdown(day(e.date) - now)} · ${e.significance} significance`), source));
  }));
}

// ui.thin_data: under 75% of the indicators or a whole pillar missing
export const thinData = (r) => r.coverage < 75 || conf().pillars.some((p) => na(r[p.key]));

// The biggest rises and falls in the composite since last year. rows: the master table (ctx.table())
export function moversLists(rows, { n = 5 } = {}) {
  const valid = asRows(rows).filter((r) => !na(r.delta_1y));
  const risers = valid.filter((r) => r.delta_1y >= TREND_THRESHOLD).sort((a, b) => b.delta_1y - a.delta_1y).slice(0, n);
  const fallers = valid.filter((r) => r.delta_1y <= -TREND_THRESHOLD).sort((a, b) => a.delta_1y - b.delta_1y).slice(0, n);
  const columns = [
    { key: "name", label: "Country", type: "country" },
    { key: "composite", label: "Score", fmt: (v) => fixed(v, 0) },
    { key: "trend", label: "Change", align: "right" },
    { key: "tier_text", label: "Tier" },
  ];
  return h("div", { class: "sg-movers" }, [["▲ Biggest risers (riskier)", risers], ["▼ Biggest fallers (safer)", fallers]].map(([title, list]) => {
    const block = h("div", { class: "sg-stack" }, h("p", { class: "sg-strong" }, title));
    if (!list.length) block.append(caption("No country moved by a point or more."));
    else {
      const shown = list.map((r) => ({ ...r, name: thinData(r) ? `${r.name} (limited data)` : r.name,
        tier_text: typeof r.prev_tier === "string" && r.prev_tier !== r.tier ? `${r.prev_tier} → ${r.tier}` : r.tier }));
      const box = h("div");
      countryTable(box, shown, { columns, noFlag: conf().NO_FLAG });
      block.append(box);
    }
    return block;
  }));
}

// Cards for the countries this browser follows (★ on a profile); null when there are none. rows: ctx.table()
export function followingStrip(rows) {
  const byIso = new Map(asRows(rows).map((r) => [r.iso3, r]));
  const followed = follow.following().filter((i) => byIso.has(i));
  if (!followed.length) return null;
  return h("div", { class: "sg-following" },
    h("div", { class: "sg-follow-head" }, "★ Following"),
    h("div", { class: "sg-fol-row" }, followed.map((iso3) => {
      const r = byIso.get(iso3);
      const url = flagUrl(r.iso2, conf().NO_FLAG);
      return h("a", { class: "sg-fol", href: `/country?country=${iso3}`, "aria-label": `Open ${r.name}` },
        url ? h("img", { src: url, alt: "" }) : null,
        h("div", null, h("div", { class: "sg-fol-name" }, r.name),
          h("div", { class: "sg-fol-meta" }, h("b", null, na(r.composite) ? "—" : fixed(r.composite, 0)),
            ` · ${r.tier ?? "—"} ${na(r.delta_1y) ? "" : trendLabel(r.delta_1y)}`)));
    })));
}

// "Data status and provenance": where every series came from. meta: data/meta.json
export function dataStatus(meta) {
  const c = conf();
  const rows = Object.entries(meta.series ?? {}).map(([key, m]) => ({
    series: key,
    provider: c.SOURCE_LABELS[m.provider] ?? m.provider,
    code: m.code,
    updated: m.edition || m.last_updated || "—",
    rows: m.rows ?? 0,
    status: m.error && !m.from_snapshot ? "Unavailable" : m.from_snapshot ? `Snapshot (${m.snapshot_date || "saved copy"})` : "Live",
  }));
  const box = h("div");
  countryTable(box, rows, { key: "series", columns: [
    { key: "series", label: "Series" }, { key: "provider", label: "Provider" }, { key: "code", label: "Code" },
    { key: "updated", label: "Source updated" }, { key: "rows", label: "Rows", fmt: (v) => String(v) }, { key: "status", label: "Status" }] });
  const errors = Object.entries(meta.series ?? {}).filter(([, m]) => m.error);
  const built = String(meta.built ?? "").slice(0, 16).replace("T", " ");
  return expander("Data status and provenance", {}, box,
    caption(`Data loaded ${meta.loaded_at}; the site was built ${built} UTC and is rebuilt every week.`),
    errors.length ? caption("Errors: ", errors.flatMap(([k, m], i) => [i ? " · " : "", h("b", null, k), `: ${String(m.error).slice(0, 160)}`])) : null);
}

// A link drawn like st.page_link (icon + label)
export const pageLink = (href, label, iconName = null) => h("a", { class: "sg-page-link", href }, iconName ? icon(iconName) : null, h("span", null, label));

// The full footer on the Introduction and Sources pages; one line everywhere else
export function footer(full = false) {
  const c = conf();
  if (!full) {
    return h("footer", { class: "sg-footer" }, h("hr"), h("div", { class: "sg-footer-row" },
      caption("Educational project. Scores are relative and model-based and do not forecast specific events. Not investment or security advice."),
      pageLink("/sources", "Sources", "verified")));
  }
  return h("footer", { class: "sg-footer" }, h("hr"),
    caption(`${c.APP_TITLE}: ${c.APP_TAGLINE} Data: World Bank Worldwide Governance Indicators & World Development Indicators · `
      + "IMF World Economic Outlook · UNHCR · UCDP (via World Bank) · Bing News, Google News and GDELT. Scores are relative and "
      + `model-based, and they do not forecast specific events. Built by ${c.AUTHOR}.`),
    pageLink("/sources", "All sources, with links and update dates", "verified"));
}

// "Scores use your pillar weights: …" with a Reset button, on pages that show scores; null with the default weights
export function weightsNote(ctx) {
  const label = ctx.customLabel();
  if (!label) return null;
  const defaults = Object.fromEntries(conf().pillars.map((p) => [p.key, p.default_weight]));
  return h("div", { class: "sg-weights-note" }, caption(`Scores use your pillar weights: ${label}.`),
    button("Reset weights", { type: "tertiary", onClick: () => ctx.setWeights(defaults, { focusTitle: true }) }));
}

// The 3D globe (css/globe.css and js/lib/globe.js load only here). opts: buildGlobeData's options plus the
// riskGlobe callbacks onSelect(iso3|null) and onFlat(); "Open country profile" goes to /country.
// Returns the globe's {update(data), select(iso3), destroy()}, or null when it could not be drawn.
export async function globePanel(el, ctx, { table, hist, flows = null, metric = "composite", metricLabel = "Composite risk score",
  onSelect = null, onFlat = null, ...options } = {}) {
  try {
    const [g] = await Promise.all([import("./globe.js"), loadCss("/css/globe.css")]);
    const data = g.buildGlobeData(table, hist, flows, metric, metricLabel, { ...options, onFlat: onFlat ? true : null });
    return g.riskGlobe(el, data, { onSelect, onFlat, onOpen: (iso3) => ctx.go("/country", { country: iso3 }) });
  } catch (err) {
    console.warn("section failed: the 3D globe", err);
    clear(el).append(caption("The 3D globe can't be shown right now. The rest of the page is unaffected."));
    return null;
  }
}

// ---------------------------------------------------------------------------------------------------------------
// Form controls drawn like Streamlit's. Each returns its outer element with a `value` property (get/set, no event)
// and calls onChange(value) when the visitor changes it.
// ---------------------------------------------------------------------------------------------------------------
function field(label, control, { help = null, labelHidden = false, id = null, tag = "label" } = {}) {
  const lab = h(tag, { class: `sg-label${labelHidden ? " sg-sr" : ""}`, for: tag === "label" ? id : null, id: tag === "label" ? null : `${id}-l` }, label);
  const mark = labelHidden ? null : helpMark(help);
  if (mark) (control.matches("input, [role=radiogroup]") ? control : control.querySelector("input"))?.setAttribute("aria-describedby", mark.tipId);
  return h("div", { class: "sg-field" }, h("div", { class: "sg-label-row" }, lab, mark), control);
}

// st.button: type "secondary" | "primary" | "tertiary"; href makes it a link; width "stretch" fills the column
export function button(label, { type = "secondary", icon: iconName = null, onClick = null, href = null, help = null, disabled = false, width = null } = {}) {
  const attrs = { class: `sg-btn sg-btn-${type}${width === "stretch" ? " sg-btn-stretch" : ""}`, title: help, onclick: onClick };
  const body = [iconName ? icon(iconName) : null, h("span", null, label)];
  return href ? h("a", { ...attrs, href }, body) : h("button", { ...attrs, type: "button", disabled }, body);
}

// st.download_button: data is a string, a Blob or a function returning one; or href for a ready-made file
export function download(label, { data = null, href = null, filename = "download.txt", mime = "text/plain", type = "secondary", icon: iconName = "download" } = {}) {
  return button(label, { type, icon: iconName, onClick: () => {
    const value = typeof data === "function" ? data() : data;
    const url = href ?? URL.createObjectURL(value instanceof Blob ? value : new Blob([value ?? ""], { type: `${mime};charset=utf-8` }));
    const a = h("a", { href: url, download: filename, hidden: true });
    document.body.append(a);
    a.click();
    a.remove();
    if (!href) setTimeout(() => URL.revokeObjectURL(url), 1000);
  } });
}

// st.selectbox with type-to-search. options: values; format(value) -> label; value: undefined = the first option,
// null = nothing picked (shows the placeholder)
export function select({ label, options, value = undefined, format = String, placeholder = "Choose an option", onChange = null,
  help = null, labelHidden = false, disabled = false } = {}) {
  let current = value === undefined ? options[0] ?? null : value;
  const id = uid("sel");
  const input = h("input", { id, class: "sg-select-input", type: "text", role: "combobox", autocomplete: "off", spellcheck: "false",
    "aria-autocomplete": "list", "aria-expanded": "false", "aria-controls": `${id}-list`, placeholder, disabled });
  const list = floating(h("ul", { class: "sg-menu", id: `${id}-list`, role: "listbox" }));
  const box = h("div", { class: "sg-select" }, input, glyph("chevron", "sg-select-chev"), list);
  const wrap = field(label, box, { help, labelHidden, id });
  const pick = combo(input, list, box, {
    items: (q) => options.filter((o) => !q || String(format(o)).toLowerCase().includes(q)),
    format, isCurrent: (o) => o === current,
    choose: (o) => { current = o; show(); onChange?.(o); },
    restore: () => show(),
  });
  const show = () => { input.value = current === null ? "" : String(format(current)); };
  show();
  Object.defineProperty(wrap, "value", { get: () => current, set: (v) => { current = v; show(); } });
  wrap.open = pick.open;
  wrap.input = input;
  return wrap;
}

// st.multiselect: chips plus a search box. value: the picked values; max: most that can be picked
export function multiselect({ label, options, value = [], format = String, placeholder = "Choose options", max = null, onChange = null,
  help = null, labelHidden = false } = {}) {
  let picked = [...value];
  const id = uid("ms");
  const input = h("input", { id, class: "sg-select-input", type: "text", role: "combobox", autocomplete: "off", spellcheck: "false",
    "aria-autocomplete": "list", "aria-expanded": "false", "aria-controls": `${id}-list` });
  const chips = h("div", { class: "sg-chips" });
  const list = floating(h("ul", { class: "sg-menu", id: `${id}-list`, role: "listbox", "aria-multiselectable": "true" }));
  const box = h("div", { class: "sg-select sg-multi" }, chips, input, glyph("chevron", "sg-select-chev"), list);
  const wrap = field(label, box, { help, labelHidden, id });
  const changed = () => { draw(); onChange?.([...picked]); };
  const draw = () => {
    clear(chips).append(...picked.map((o) => h("span", { class: "sg-tag" }, h("span", null, String(format(o))),
      h("button", { type: "button", class: "sg-tag-x", "aria-label": `Remove ${format(o)}`,
        onclick: (e) => { e.stopPropagation(); picked = picked.filter((x) => x !== o); changed(); input.focus(); } }, glyph("close")))));
    input.placeholder = picked.length ? "" : placeholder;
  };
  combo(input, list, box, {
    items: (q) => (max !== null && picked.length >= max ? []
      : options.filter((o) => !picked.includes(o) && (!q || String(format(o)).toLowerCase().includes(q)))),
    empty: () => (max !== null && picked.length >= max ? `You can only select up to ${max} options. Remove an option first.` : "No results"),
    format, isCurrent: () => false,
    choose: (o) => { picked.push(o); input.value = ""; changed(); },
    restore: () => { input.value = ""; },
    keepOpen: true,
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Backspace" && !input.value && picked.length) { picked.pop(); changed(); }
  });
  draw();
  Object.defineProperty(wrap, "value", { get: () => [...picked], set: (v) => { picked = [...v]; draw(); } });
  return wrap;
}

// The list behaviour shared by select and multiselect (ARIA combobox with a listbox popup)
function combo(input, list, box, { items, format, isCurrent, choose, restore, empty = () => "No results", keepOpen = false }) {
  let shown = [], active = -1, isOpen = false, float = null;
  const render = (q) => {
    shown = items(q.trim().toLowerCase());
    active = Math.max(0, shown.findIndex(isCurrent));
    clear(list);
    if (!shown.length) list.append(h("li", { class: "sg-menu-empty", role: "presentation" }, empty()));
    shown.forEach((o, i) => list.append(h("li", { role: "option", id: `${list.id}-${i}`, class: "sg-option", "aria-selected": String(isCurrent(o)),
      onmousedown: (e) => { e.preventDefault(); pickAt(i); } }, String(format(o)))));
    float?.place(); // the list's height changed
    mark();
  };
  const mark = () => {
    [...list.children].forEach((li, i) => li.classList.toggle("active", i === active));
    const li = list.children[active];
    if (li && shown.length) {
      input.setAttribute("aria-activedescendant", li.id);
      // scroll the list only (the list is a fixed box: scrollIntoView could move the page)
      if (li.offsetTop < list.scrollTop) list.scrollTop = li.offsetTop;
      else if (li.offsetTop + li.offsetHeight > list.scrollTop + list.clientHeight) list.scrollTop = li.offsetTop + li.offsetHeight - list.clientHeight;
    } else input.removeAttribute("aria-activedescendant");
  };
  const open = () => {
    if (isOpen) return;
    isOpen = true;
    input.setAttribute("aria-expanded", "true");
    // below the box, or above it when there is no room (Find sits on the bottom bar); shown before it is filled, as a
    // hidden list cannot scroll its current option into view
    float = openFloat(list, box, { placement: "down", align: "start", gap: 4, matchWidth: true }, () => close());
    render("");
  };
  const close = () => {
    isOpen = false;
    float?.close();
    float = null;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  };
  const pickAt = (i) => {
    const o = shown[i];
    if (o === undefined) return;
    if (!keepOpen) close();
    choose(o);
    if (keepOpen) render("");
  };
  input.addEventListener("focus", () => { input.select(); open(); });
  input.addEventListener("click", open);
  input.addEventListener("input", () => { if (!isOpen) open(); render(input.value); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!isOpen) return open();
      active = Math.max(0, Math.min(shown.length - 1, active + (e.key === "ArrowDown" ? 1 : -1)));
      mark();
    } else if (e.key === "Enter") {
      if (isOpen && shown.length) { e.preventDefault(); pickAt(active); }
    } else if (e.key === "Escape") {
      if (isOpen) { e.preventDefault(); e.stopPropagation(); close(); restore(); }
    } else if (e.key === "Tab") {
      close();
      restore();
    }
  });
  input.addEventListener("blur", () => { close(); restore(); });
  box.addEventListener("mousedown", (e) => { if (e.target !== input && !list.contains(e.target)) { e.preventDefault(); input.focus(); open(); } });
  return { open: () => { input.focus(); open(); } };
}

// st.slider (one value). format(value) -> the text over the thumb and at the ends
export function slider({ label, min = 0, max = 100, step = 1, value = min, format = String, onChange = null, onInput = null, help = null, labelHidden = false } = {}) {
  const id = uid("sl");
  const input = h("input", { id, type: "range", class: "sg-range", min, max, step, value });
  const bubble = h("div", { class: "sg-slider-value", "aria-hidden": "true" });
  const wrap = field(label, h("div", { class: "sg-slider" }, bubble, input,
    h("div", { class: "sg-slider-ends", "aria-hidden": "true" }, h("span", null, format(min)), h("span", null, format(max)))), { help, labelHidden, id });
  const paint = () => {
    const p = max > min ? ((Number(input.value) - min) / (max - min)) * 100 : 0;
    wrap.style.setProperty("--pf", String(p / 100));
    bubble.textContent = format(Number(input.value));
    input.setAttribute("aria-valuetext", format(Number(input.value)));
  };
  input.addEventListener("input", () => { paint(); onInput?.(Number(input.value)); });
  input.addEventListener("change", () => onChange?.(Number(input.value)));
  paint();
  Object.defineProperty(wrap, "value", { get: () => Number(input.value), set: (v) => { input.value = v; paint(); } });
  return wrap;
}

// st.toggle
export function toggle({ label, value = false, onChange = null, help = null } = {}) {
  const mark = helpMark(help);
  const input = h("input", { type: "checkbox", role: "switch", class: "sg-toggle-input", checked: value, "aria-describedby": mark?.tipId ?? null });
  input.addEventListener("change", () => onChange?.(input.checked));
  const wrap = h("div", { class: "sg-field sg-toggle-field" }, h("label", { class: "sg-toggle" }, input, h("span", { class: "sg-toggle-track", "aria-hidden": "true" }),
    h("span", null, label)), mark);
  Object.defineProperty(wrap, "value", { get: () => input.checked, set: (v) => { input.checked = !!v; } });
  return wrap;
}

// st.segmented_control (one choice, always set). options: values; format(value) -> label
export function segmented({ label, options, value = options[0], format = String, onChange = null, labelHidden = false, help = null } = {}) {
  let current = value;
  const id = uid("seg");
  const group = h("div", { class: "sg-segmented", role: "radiogroup", "aria-labelledby": `${id}-l` });
  const buttons = options.map((o) => h("button", { type: "button", role: "radio", class: "sg-seg",
    onclick: () => set(o, true) }, String(format(o))));
  group.append(...buttons);
  group.addEventListener("keydown", (e) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!step) return;
    e.preventDefault();
    const i = (options.indexOf(current) + step + options.length) % options.length;
    set(options[i], true);
    buttons[i].focus();
  });
  const set = (o, byUser) => {
    const changed = o !== current;
    current = o;
    buttons.forEach((b, i) => { b.setAttribute("aria-checked", String(options[i] === o)); b.tabIndex = options[i] === o ? 0 : -1; });
    if (byUser && changed) onChange?.(o);
  };
  set(current, false);
  const wrap = field(label, group, { help, labelHidden, id, tag: "div" });
  Object.defineProperty(wrap, "value", { get: () => current, set: (v) => set(v, false) });
  return wrap;
}

// st.expander: a <details>; append more content to .body
export function expander(label, { expanded = false } = {}, ...children) {
  const body = h("div", { class: "sg-expander-body" }, children.map(text));
  const details = h("details", { class: "sg-expander", open: expanded }, h("summary", null, glyph("chevron", "sg-exp-chev"), h("span", null, label)), body);
  details.body = body;
  return details;
}

// st.popover: a button that opens a small panel (.body); Escape or a click elsewhere closes it.
// placement "up" opens it above the button (the bottom bar), its end lined up with the button's.
export function popover(label, { icon: iconName = null, type = "secondary", help = null, placement = "down", className = "" } = {}) {
  const id = uid("pop");
  const btn = h("button", { type: "button", class: `sg-btn sg-btn-${type} sg-pop-btn`, title: help, "aria-expanded": "false", "aria-controls": id },
    iconName ? icon(iconName) : null, h("span", null, label), type === "secondary" ? glyph("chevron", "sg-pop-chev") : null);
  const body = floating(h("div", { class: "sg-popover-panel", id, role: "dialog", "aria-label": label }));
  const wrap = h("div", { class: `sg-popover ${className}`.trim() }, btn, body);
  const outside = (e) => { if (!wrap.contains(e.target)) close(); };
  const keys = (e) => { if (e.key === "Escape") { close(); btn.focus(); } };
  let shown = null;
  const isOpen = () => isFloatOpen(body);
  const open = () => {
    if (isOpen()) return;
    if (shown) close(); // hidden by the browser without close() (moved in the page): drop its listeners first
    btn.setAttribute("aria-expanded", "true");
    document.addEventListener("pointerdown", outside, true);
    document.addEventListener("keydown", keys);
    shown = openFloat(body, btn, { placement, align: placement === "up" ? "end" : "start" }, () => close());
    openPopovers.add(close);
    wrap.dispatchEvent(new Event("sg:open")); // a listener may fill .body now: place it again for its new size
    shown.place();
  };
  function close() {
    shown?.close();
    shown = null;
    openPopovers.delete(close);
    btn.setAttribute("aria-expanded", "false");
    document.removeEventListener("pointerdown", outside, true);
    document.removeEventListener("keydown", keys);
  }
  btn.addEventListener("click", () => (isOpen() ? close() : open()));
  Object.assign(wrap, { body, button: btn, open, close, isOpen });
  return wrap;
}
