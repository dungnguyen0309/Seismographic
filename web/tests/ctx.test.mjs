import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { setConfig, decodeWeights, weightsShares, customWeightsLabel, ROUTES, route, makeCtx } from "../js/lib/ctx.js";
import { floatCorrection, floatPosition, layoutBox, tipIsLive, visibleArea } from "../js/lib/ui.js";
import { data, fixture, objects, same, sameTable } from "./helpers.mjs";

const config = data("config");
setConfig(config);
const defaults = Object.fromEntries(config.pillars.map((p) => [p.key, p.default_weight]));

test("bad_params: ?w= decodes only as ui.decode_weights does", () => {
  assert.deepEqual(decodeWeights("50,20,20,10"), { stability: 50, governance: 20, economic: 20, social: 10 });
  for (const bad of ["1,2,3", "0,0,0,0", "7,20,20,10", "a", "", "50,20,20,10,5", "105,0,0,0", "-5,20,20,10", null]) {
    assert.equal(decodeWeights(bad), null, String(bad));
  }
});

test("customWeightsLabel is empty for the defaults and for the same proportions", () => {
  assert.equal(customWeightsLabel(defaults), "");
  assert.equal(customWeightsLabel({ stability: 70, governance: 50, economic: 50, social: 30 }), "");
  assert.equal(customWeightsLabel({ stability: 0, governance: 0, economic: 0, social: 0 }), "");
  assert.equal(customWeightsLabel({ stability: 50, governance: 20, economic: 20, social: 10 }),
    "Stability 50% · Governance 20% · Economy 20% · Social 10%");
  assert.equal(customWeightsLabel({ stability: 50, governance: 50, economic: 20, social: 0 }),
    "Stability 42% · Governance 42% · Economy 17% · Social 0%");
});

test("weightsShares rescales to 100 and falls back to the defaults", () => {
  assert.deepEqual(weightsShares({ stability: 70, governance: 50, economic: 50, social: 30 }), defaults);
  assert.deepEqual(weightsShares({ stability: 0, governance: 0, economic: 0, social: 0 }), defaults);
});

test("routes: the 19 pages in the Streamlit order, unknown paths give null", () => {
  assert.equal(ROUTES.length, 19);
  assert.deepEqual([...new Set(ROUTES.map((r) => r.section))], ["Monitor", "Briefings", "Tools", "Reference"]);
  assert.deepEqual(route("/"), ROUTES[0]);
  assert.equal(route("/").title, "Global overview");
  assert.equal(route("/data").module, "data");
  assert.equal(route("/data").title, "Data downloads");
  assert.equal(route("/country/").title, "Country profile");
  for (const bad of ["/nope", "/overview", "/country/NGA", "/index.html", "", "/data.json"]) assert.equal(route(bad), null, bad);
});

function fakeWindow(search) {
  globalThis.location = new URL(`http://localhost/${search}`);
  globalThis.history = { replaceState: (_s, _t, url) => { globalThis.location = new URL(url, globalThis.location); } };
}
const core = () => ({ config, countries: data("countries"), values: data("values"), scores: data("scores"),
  history: data("history"), master: data("master"), wgiTrend: data("wgi_trend"), meta: data("meta") });

test("ctx: default weights use the precomputed files", () => {
  fakeWindow("?w=70,50,50,30");
  const c = core();
  const ctx = makeCtx(c);
  assert.deepEqual(ctx.weights(), defaults);
  assert.equal(ctx.history(), c.history);
  assert.equal(ctx.table(), c.master);
  assert.equal(ctx.scores().get("NGA").composite, ctx.scores().get("NGA").composite);
  assert.equal(globalThis.location.search, "", "default proportions drop ?w=");
});

test("ctx: custom weights from ?w= recompute scores and history; bad ?w= falls back", () => {
  fakeWindow("?w=50,20,20,10&country=NGA");
  const ctx = makeCtx(core());
  sameTable(ctx.scores(), fixture("scores_w50_20_20_10"));
  const byKey = (t) => new Map(objects(t).map((r) => [`${r.iso3}-${r.year}`, r]));
  const got = byKey(ctx.history()), want = byKey(fixture("history_w50_20_20_10"));
  assert.equal(got.size, want.size);
  for (const [k, r] of want) same(got.get(k)?.composite ?? null, r.composite, k);
  sameTable(ctx.table(), fixture("master_w50_20_20_10"));
  assert.equal(ctx.scores(), ctx.scores(), "cached per weights key");
  assert.equal(ctx.params.get("w"), "50,20,20,10");
  fakeWindow("?w=1,2,3");
  const bad = makeCtx(core());
  assert.deepEqual(bad.weights(), defaults);
  assert.equal(globalThis.location.search, "");
});

test("ctx.setParam replaces one query value without touching the rest", () => {
  fakeWindow("?country=NGA&tab=map");
  const ctx = makeCtx(core());
  ctx.setParam("tab", "news");
  assert.equal(globalThis.location.search, "?country=NGA&tab=news");
  ctx.setParam("tab", null);
  assert.equal(globalThis.location.search, "?country=NGA");
});

test("ctx.syncAddress: after Back or Forward the address carries the weights in use", () => {
  fakeWindow("?w=50,20,20,10");
  const ctx = makeCtx(core());
  globalThis.location = new URL("http://localhost/guide?country=NGA"); // Back to an entry made before the change
  ctx.syncAddress();
  assert.equal(globalThis.location.search, "?country=NGA&w=50,20,20,10");
  assert.deepEqual(decodeWeights(ctx.params.get("w")), ctx.rawWeights());
  ctx.setWeights(defaults);
  globalThis.location = new URL("http://localhost/?w=50,20,20,10&tab=map"); // Forward to an entry with the old weights
  ctx.syncAddress();
  assert.equal(globalThis.location.search, "?tab=map");
  assert.equal(ctx.table(), ctx.core.master, "the scores shown are the default ones, as the address now says");
});

test("ctx.setParam tells the shell which value changed", () => {
  fakeWindow("?country=NGA");
  const seen = [];
  const ctx = makeCtx(core(), { onParam: (name, value) => seen.push([name, value]) });
  ctx.setParam("country", "KEN");
  ctx.setParam("tab", null);
  assert.deepEqual(seen, [["country", "KEN"], ["tab", null]]);
});

test("ctx.forPage: a page's fail() acts only while its draw is on screen and its element is in the page", () => {
  fakeWindow("");
  const ctx = makeCtx(core());
  const shown = [];
  ctx.fail = (err) => shown.push(err.message);
  let current = true;
  const page = ctx.forPage(() => current);
  assert.equal(page.scores(), ctx.scores(), "the rest of ctx is the same");
  assert.equal(page.core, ctx.core);
  const warn = console.warn;
  console.warn = () => {};
  try {
    page.fail(new Error("now"));
    page.fail(new Error("gone element"), { isConnected: false });
    page.fail(new Error("live element"), { isConnected: true });
    current = false; // the visitor moved on, or the weights redrew the page
    page.fail(new Error("late"));
    page.fail(new Error("late element"), { isConnected: true });
  } finally {
    console.warn = warn;
  }
  assert.deepEqual(shown, ["now", "live element"]);
});

// ---- floating panels (ui.js): the room they may use and where they go ----
const viewport = { width: 1280, height: 900 };
const sidebar = { left: 0, right: 300, top: 0, bottom: 900 };
const rect = (left, top, width, height) => ({ left, top, right: left + width, bottom: top + height, width, height });

test("visibleArea: beside the open sidebar, or inside it for its own panels", () => {
  assert.deepEqual(visibleArea(viewport), { left: 0, right: 1280, top: 0, bottom: 900 });
  assert.deepEqual(visibleArea(viewport, sidebar), { left: 300, right: 1280, top: 0, bottom: 900 });
  assert.deepEqual(visibleArea(viewport, sidebar, true), { left: 0, right: 300, top: 0, bottom: 900 });
  // the sidebar sliding out (left of the window) still covers only what it covers
  assert.deepEqual(visibleArea(viewport, { left: -400, right: -100 }), { left: 0, right: 1280, top: 0, bottom: 900 });
});

test("floatPosition: a tooltip at the page's left edge stays clear of the open sidebar", () => {
  const area = visibleArea(viewport, sidebar);
  // a first-column metric's (?) at x 380..396, tip 288 wide, lined up by its end
  const p = floatPosition(rect(380, 100, 16, 16), { width: 288, height: 60 }, area, { align: "end", gap: 6 });
  assert.equal(p.left, 308);
  assert.equal(p.top, 122);
});

test("floatPosition: an up popover at the page's left goes right of the sidebar, an end-aligned one at the right stays in", () => {
  const area = visibleArea(viewport, sidebar);
  const up = floatPosition(rect(380, 800, 80, 40), { width: 384, height: 200 }, area, { placement: "up", align: "end" });
  assert.deepEqual(up, { left: 308, top: 592, maxHeight: 784 });
  const find = floatPosition(rect(1124, 830, 64, 52), { width: 292, height: 116 }, area, { placement: "up", align: "end" });
  assert.deepEqual(find, { left: 896, top: 706, maxHeight: 814 });
});

test("floatPosition: phones keep the panel inside the window and flip when there is no room", () => {
  const area = visibleArea({ width: 390, height: 844 });
  const right = floatPosition(rect(267, 400, 107, 40), { width: 358, height: 150 }, area);
  assert.equal(right.left, 24); // 390 - 8 - 358
  const wide = floatPosition(rect(16, 400, 80, 40), { width: 500, height: 150 }, area);
  assert.equal(wide.left, 8); // wider than the window: its start stays in view
  const low = floatPosition(rect(16, 760, 80, 40), { width: 200, height: 150 }, area);
  assert.equal(low.top, 760 - 8 - 150); // no room below: above
  const high = floatPosition(rect(16, 20, 80, 40), { width: 200, height: 150 }, area, { placement: "up" });
  assert.equal(high.top, 20 + 40 + 8); // no room above: below
});

test("floatPosition: a panel taller than the room scrolls inside itself, on the side with more room", () => {
  const area = visibleArea({ width: 844, height: 390 }); // a phone on its side
  const p = floatPosition(rect(16, 100, 120, 40), { width: 300, height: 600 }, area);
  assert.equal(p.top, 148); // below: 234 px of room against 84 above
  assert.equal(p.maxHeight, 390 - 8 - 148);
  const up = floatPosition(rect(16, 300, 120, 40), { width: 300, height: 600 }, area);
  assert.deepEqual([up.maxHeight, up.top], [300 - 8 - 8, 8]); // above: 284 px against 34 below
});

test("floatPosition: a panel stays with its anchor when the anchor scrolls out of view", () => {
  const area = visibleArea({ width: 390, height: 844 });
  const p = floatPosition(rect(16, -300, 80, 40), { width: 200, height: 150 }, area);
  assert.equal(p.top, -300 + 40 + 8); // not held at the top of the window
});

test("floatCorrection: a fixed box placed against a contained ancestor is moved by the difference", () => {
  // asked for 24,600; the dock (container-type) made it land at 24,1444
  assert.deepEqual(floatCorrection({ left: 24, top: 600 }, { left: 24, top: 1444 }, { left: 24, top: 600 }), { left: 24, top: -244 });
  assert.equal(floatCorrection({ left: 24, top: 600 }, { left: 24.2, top: 600.3 }, { left: 24, top: 600 }), null);
});

test("tipIsLive: Escape is used up only by a tip that is still in the page and open", () => {
  const node = (connected, extra = {}) => ({ isConnected: connected, hidden: false, matches: () => true, ...extra });
  assert.equal(tipIsLive(null), false);
  assert.equal(tipIsLive({ tip: node(true), anchor: node(true) }), true);
  assert.equal(tipIsLive({ tip: node(false), anchor: node(false) }), false, "the page was replaced under it");
  assert.equal(tipIsLive({ tip: node(true), anchor: node(false) }), false);
  assert.equal(tipIsLive({ tip: node(true, { hidden: true }), anchor: node(true) }), false, "closed (no top layer here)");
});

test("layoutBox: a panel beside a box-less wrapper (display: contents) is placed against the first ancestor with a box", () => {
  const el = (rects, parentElement = null) => ({ getClientRects: () => rects, parentElement });
  const th = el([{}]), wrap = el([], th); // the overview's span.ov-th-help inside its header cell
  assert.equal(layoutBox(wrap), th);
  assert.equal(layoutBox(th), th);
  assert.equal(layoutBox(el([])), null);
});

test("help marks: on touch screens only a real (?) gets a hit area, of at least 24px", () => {
  const css = readFileSync(new URL("../css/app.css", import.meta.url), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
  const rules = [...css.matchAll(/([^{}]*\.sg-help-wrap[^{}]*::after[^{}]*)\{([^}]*)\}/g)];
  assert.ok(rules.length, "a hit area rule");
  for (const [, sel, body] of rules) {
    for (const s of sel.split(",")) assert.match(s, /\.sg-help-wrap:has\(> \.sg-help\)::after/, `not scoped to a real mark: ${s.trim()}`);
    // until ui.js fitHelpArea measures the room around it, the var()'s fallback applies
    const inset = body.match(/inset:\s*([^;]+)/)?.[1].trim().replace(/^var\(--hit,\s*(.*)\)$/, "$1").split(/\s+/).map(parseFloat);
    if (!inset) continue;
    const [t, r = t, b = t, l = r] = inset; // the (?) is 16px
    assert.ok(16 - t - b >= 24 && 16 - l - r >= 24, `${sel.trim()}: inset ${inset.join(" ")}`);
  }
});
