// Port of prm/globe.py: the interactive 3D risk globe (globe.gl, WebGL) and the data it draws.
// buildGlobeData(...) is risk_globe()'s data dict; riskGlobe(el, data, callbacks) mounts the globe in el (load
// css/globe.css on the page). The globe code is the component's _JS with the Streamlit wiring replaced by callbacks
// and every file served from /vendor. Call charts.setConfig(data/config.json) before buildGlobeData.
import { asRows } from "./scoring.js";
import { pyRound } from "./format.js";
import { config, mapColorscale } from "./charts.js";

const GLOBE_JS = "/vendor/globe/globe.gl.min.js";
const COUNTRIES = "/vendor/geo/ne_110m.geojson";  // 1:110m: shown immediately
const COUNTRIES_DETAILED = "/vendor/geo/ne_50m.geojson";  // 1:50m: swapped in once loaded (not on phones)
const EARTH_IMAGE = "/vendor/earth/earth-night.jpg";
const EARTH_BUMP = "/vendor/earth/earth-topology.png";
export const HEIGHT = 550;
const OUT_OF_VIEW_COLOR = "#1b1b1a";  // countries outside the current region / income filter
const TOP_FLOWS = 40;  // largest refugee flows drawn when no country is selected
const CONFLICT_THRESHOLD = 25;  // UCDP: 25 battle deaths a year = active armed conflict
const DEFAULT_LAYERS = { spin: true, extrude: true, flows: true, conflict: true };

// ---- the data (risk_globe) ---------------------------------------------------------------------------------------
const na = (v) => v === null || v === undefined || Number.isNaN(v);
const num = (v, digits = 1) => (na(v) ? null : pyRound(Number(v), digits));
const lookup = (m, k) => (m instanceof Map ? m.get(k) : m[k]);

function flagUrl(iso2) {  // config.flag_url, pointed at the vendored flags
  const code = String(iso2 ?? "").trim().toUpperCase();
  if (code.length !== 2 || !/^[A-Z]{2}$/.test(code) || config().NO_FLAG.includes(code)) return null;
  return `/vendor/flags/${code.toLowerCase()}.svg`;
}

function byYear(hist, column, years, digits = 0) {
  const at = new Map(years.map((y, i) => [y, i]));
  const out = new Map();
  for (const r of hist) {
    if (na(r[column]) || !at.has(r.year)) continue;
    if (!out.has(r.iso3)) out.set(r.iso3, years.map(() => null));
    const row = out.get(r.iso3);
    if (row[at.get(r.year)] === null) row[at.get(r.year)] = num(r[column], digits);
  }
  return out;
}

// stable, ties in their original order (see staticbuild/charts.py)
const largest = (rows, n) => rows.map((r, i) => [r, i]).sort(([a, i], [b, j]) => b.value - a.value || i - j).slice(0, n).map(([r]) => r);

// Largest origin -> host flows (top 300 overall, plus the focus country's own top 30); the globe draws the top 40
function topFlows(flows, names, focus) {
  const all = flows ? asRows(flows) : [];
  if (!all.length) return [[], null];
  const known = all.filter((f) => names.has(f.origin) && names.has(f.host) && !na(f.value));
  let top = largest(known, 300);
  if (focus) {
    const own = largest(known.filter((f) => f.origin === focus || f.host === focus), 30);
    const seen = new Set();
    top = largest([...top, ...own].filter((f) => !seen.has(f.origin + ">" + f.host) && seen.add(f.origin + ">" + f.host)), Infinity);
  }
  const year = Math.max(...all.map((f) => f.year).filter((y) => !na(y)));
  return [top.map((f) => ({ from: f.origin, to: f.host, value: Number(f.value), fromName: names.get(f.origin),
    toName: names.get(f.host) })), Math.trunc(year)];
}

// The globe's data (prm/globe.py risk_globe). table: the master table, hist: the history (both {columns, rows} or row
// arrays), flows: {origin, host, value, year} rows or null. By default countries are coloured by `metric` (composite
// or a pillar key) with the year slider; `custom` ({iso3: value}) colours by anything else, with its own colorscale,
// valueRange and valueFormat ("score", "signed", "days" or plain). onFlat (truthy) adds "Show the flat map" to the note.
export function buildGlobeData(table, hist, flows, metric, metricLabel, {
  inView = null, region = null, selected = null, key = "risk_globe", custom = null, colorscale = null,
  valueRange = [0, 100], valueFormat = "score", ticks = null, notes = null, emptyLabel = "No data", extrudeAbs = false,
  layers = null, height = HEIGHT, focus = null, hint = null, fallback = null, onFlat = null,
} = {}) {
  const c = config();
  const rows = asRows(table), histRows = asRows(hist);
  // shortcut: the Overview, the one caller on the default key, has its own tier legend; a new direct caller on that
  // key would lose the colour key drawn on the globe
  const overview = key === "risk_globe";
  if (fallback === null || fallback === undefined) {
    fallback = onFlat ? "The flat map shows the same data."
      : focus ? "The charts below show the same refugee flows." : "Everything else on the page still works.";
  }
  const years = [...new Set(histRows.map((r) => Math.trunc(r.year)))].sort((a, b) => a - b);
  const composite = byYear(histRows, "composite", years, 6);  // tiers, the yearly change and the 0-dp score need it unrounded
  const rank = byYear(histRows, "rank", years);
  const deaths = byYear(histRows, "battle_deaths_raw", years);
  const value = metric === "composite" || custom !== null ? null : byYear(histRows, metric, years);
  const shown = inView === null ? new Set(rows.map((r) => r.iso3)) : new Set(inView);
  const nRanked = years.map((y) => histRows.filter((r) => r.year === y && !na(r.composite)).length);
  const blank = years.map(() => null);
  const countries = rows.map((r) => {
    const entry = {
      iso3: r.iso3, name: r.name, region: r.region, flag: flagUrl(r.iso2), lat: num(r.lat, 3), lng: num(r.lng, 3),
      composite: composite.get(r.iso3) ?? blank, rank: rank.get(r.iso3) ?? blank, deaths: deaths.get(r.iso3) ?? blank,
      pillars: Object.fromEntries(c.pillars.map((p) => [p.key, num(r[p.key], 0)])),  // rounded once, as in the tables
      flags: Math.trunc(r.flags || 0), inView: shown.has(r.iso3),
    };
    if (value !== null) entry.value = value.get(r.iso3) ?? blank;
    if (custom !== null) entry.custom = num(lookup(custom, r.iso3), 2);
    const note = notes ? lookup(notes, r.iso3) : null;
    if (note) entry.note = String(note);
    return entry;
  });
  const [flowList, flowsYear] = topFlows(flows, new Map(rows.map((r) => [r.iso3, r.name])), focus);
  const centre = c.regions.find((x) => x.name === (region || ""))?.center ?? null;
  return {
    key, height, years, showTime: custom === null, nRanked, metric, metricLabel, custom: custom !== null,
    range: [...valueRange], valueFormat, emptyLabel, extrudeAbs, ticks: ticks || ["0 · lower", "50", "higher · 100"],
    colorscale: colorscale || mapColorscale(metric), noData: c.NO_DATA_COLOR, ink: c.INK.text, outOfView: OUT_OF_VIEW_COLOR,
    centre: centre ? [...centre] : null, focus, hint, fallback, flatLink: !!onFlat,
    ramp: !overview,  // the Overview shows the tiers under the map, so the globe keeps only its layer keys
    layers: { ...DEFAULT_LAYERS, ...(layers || {}) }, selected,
    pillars: c.pillars.map((p) => ({ key: p.key, short: p.short, color: c.PILLAR_COLORS[p.key] })),
    tierList: c.tiers.map((t) => ({ label: t.label, lower: t.lower, color: t.color, text: t.text_on })),
    conflictThreshold: CONFLICT_THRESHOLD, flows: flowList, flowsYear, topFlows: TOP_FLOWS, countries,
  };
}

// ---- the globe (prm/globe.py _HTML / _JS) ----------------------------------------------------------------------
const HTML = `
<div class="rg-wrap">
  <div class="rg-canvas"></div>
  <button class="rg-lock" type="button" hidden><span>Tap to explore the globe</span></button>
  <div class="rg-toast" role="status" aria-live="polite"></div>
  <div class="rg-status" role="status">Loading the 3D globe…</div>
  <div class="rg-controls">
    <div class="rg-group" role="group" aria-label="View">
      <button data-act="in" title="Zoom in" aria-label="Zoom in">+</button>
      <button data-act="out" title="Zoom out" aria-label="Zoom out">−</button>
      <button data-act="reset" title="Reset the view" aria-label="Reset the view">↺</button>
    </div>
    <!-- the name says what each switch does (the tooltip says the same, so it is not read twice); aria-pressed its state -->
    <div class="rg-group" role="group" aria-label="Layers">
      <button data-act="spin" aria-label="Spin: turn the globe slowly on its own"
        title="Spin: turn the globe slowly on its own">Spin</button>
      <button data-act="extrude" aria-label="3D: raise each country by the value shown"
        title="3D: raise each country by the value shown">3D</button>
      <button data-act="flows" aria-label="Flows: show the largest refugee flows, from origin to host country"
        title="Flows: show the largest refugee flows, from origin to host country">Flows</button>
      <button data-act="conflict" aria-label="Conflict: ring the countries with 25 or more battle deaths a year"
        title="Conflict: ring the countries with 25 or more battle deaths a year">Conflict</button>
    </div>
    <div class="rg-group rg-done-group" hidden>
      <button data-act="lock" title="Lock the globe so swiping scrolls the page again">Done</button>
    </div>
  </div>
  <div class="rg-hint">Drag to rotate · +/− to zoom · click a country</div>
  <div class="rg-legend">
    <div class="rg-legend-title"></div>
    <div class="rg-legend-bar"></div>
    <div class="rg-legend-ticks"><span>0 · lower</span><span>50</span><span>higher · 100</span></div>
    <div class="rg-legend-keys"></div>
  </div>
  <div class="rg-time">
    <button class="rg-play" title="Replay the index year by year" aria-label="Replay the index year by year">▶</button>
    <input class="rg-year-input" type="range" min="0" max="0" value="0" step="1" aria-label="Year">
    <span class="rg-year"></span>
  </div>
  <div class="rg-panel" hidden aria-live="polite"></div>
</div>
`;

// Natural Earth codes that differ from the World Bank's (Somaliland and Northern Cyprus are drawn
// as part of Somalia and Cyprus)
const CODE_FIX = { CYN: "CYP", KOS: "XKX", SOL: "SOM" };
let libraryPromise = null;
const countriesPromises = {};  // per outline file
const lastViews = {};  // per globe (data.key): the camera survives the globe being rebuilt
const BROWSER = typeof window !== "undefined";  // the data half also runs in node (tests)
const media = (q) => (BROWSER ? window.matchMedia(q) : { matches: false, addEventListener() {}, removeEventListener() {} });
// Phones, tablets and low-power PCs get a lighter globe: simple outlines, no relief map, fewer pixels, no spin
const LITE = BROWSER && (media("(pointer: coarse)").matches || Math.min(screen.width, screen.height) < 700 ||
  (navigator.hardwareConcurrency || 8) <= 4);
const PIXEL_RATIO = BROWSER ? Math.min(window.devicePixelRatio || 1, LITE ? 1.5 : 1.75) : 1;
// Reduced motion: no spin, no camera flights and solid flow lines
const REDUCED = media("(prefers-reduced-motion: reduce)");
const flyMs = (ms) => (REDUCED.matches ? 0 : ms);
const IDLE_MS = 1500;  // with nothing moving for this long, the globe stops drawing frames
// Touch screens: the globe stays still until tapped, so a one-finger swipe scrolls the page instead of turning it
const TOUCH = media("(hover: none) and (pointer: coarse)").matches;
const ZOOM_KEY = BROWSER && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent) ? "⌘" : "Ctrl";
const defaultHint = () => (TOUCH ? "Tap to explore · pinch to zoom · tap a country"
                                 : "Drag to rotate · " + ZOOM_KEY + " + scroll or +/− to zoom · click a country");

function lockGlobe(root, ctx, locked) {
  ctx.locked = locked;
  root.classList.toggle("rg-locked", locked);
  root.querySelector(".rg-lock").hidden = !locked;
  root.querySelector(".rg-done-group").hidden = locked || !TOUCH;
  if (ctx.setActive) ctx.setActive();  // locked on a touch screen, the flow dashes stop
}

function toast(root, text) {
  const el = root.querySelector(".rg-toast");
  if (Date.now() - (el.shownAt || 0) < 6000) return;  // once in a while, not on every wheel tick
  el.shownAt = Date.now();
  el.textContent = text;
  el.classList.add("on");
  clearTimeout(el.timer);
  el.timer = setTimeout(() => el.classList.remove("on"), 1800);
}

function loadLibrary() {
  if (window.Globe) return Promise.resolve(window.Globe);
  if (!libraryPromise) {
    libraryPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = GLOBE_JS;
      script.async = true;
      // While it loads, globe.gl makes a throwaway copy of each layer to read its defaults, and the arc, path and ring
      // copies start frame loops that nothing ever stops. Dropping the frame requests made by the script itself means
      // those loops never start; the globes built later run their own loops as usual.
      const raf = window.requestAnimationFrame;
      window.requestAnimationFrame = (cb) => (document.currentScript === script ? 0 : raf.call(window, cb));
      const restore = () => { window.requestAnimationFrame = raf; };
      script.onload = () => { restore(); resolve(window.Globe); };
      script.onerror = () => {
        restore();
        libraryPromise = null;
        script.remove();
        reject(new Error("the 3D library could not be downloaded"));
      };
      document.head.appendChild(script);
    });
  }
  return libraryPromise;
}

function centreOf(geometry) {
  // Bounding-box centre of the largest ring: good enough to point the camera at a country
  const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
  let ring = polygons[0][0];
  for (const polygon of polygons) if (polygon[0].length > ring.length) ring = polygon[0];
  let minX = 180, maxX = -180, minY = 90, maxY = -90;
  for (const [x, y] of ring) {
    minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y);
  }
  return { lng: (minX + maxX) / 2, lat: (minY + maxY) / 2 };
}

function loadCountries(url) {
  if (!countriesPromises[url]) {
    countriesPromises[url] = fetch(url)
      .then((r) => { if (!r.ok) throw new Error("country shapes: HTTP " + r.status); return r.json(); })
      .then((geojson) => geojson.features
        .map((f) => {
          const p = f.properties;
          const code = /^[A-Z]{3}$/.test(p.ISO_A3) ? p.ISO_A3 : p.ADM0_A3;
          f.properties = { ADMIN: p.ADMIN };  // drop the ~170 other attributes
          f.iso3 = CODE_FIX[code] || code;
          f.centre = centreOf(f.geometry);
          return f;
        })
        .filter((f) => f.iso3 !== "ATA"))  // Antarctica stays as bare terrain
      .catch((err) => { delete countriesPromises[url]; throw err; });
  }
  return countriesPromises[url];
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function colourAt(scale, t) {
  t = Math.max(0, Math.min(1, t));
  for (let i = 1; i < scale.length; i++) {
    const [t1, c1] = scale[i];
    if (t <= t1) {
      const [t0, c0] = scale[i - 1];
      const k = t1 > t0 ? (t - t0) / (t1 - t0) : 0;
      const a = hexToRgb(c0), b = hexToRgb(c1);
      return rgbToHex(a.map((v, j) => v + (b[j] - v) * k));
    }
  }
  return scale[scale.length - 1][1];
}

function rgbToHex(rgb) {
  return "#" + rgb.map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, "0")).join("");
}

function shade(hex, k) {
  // Darken towards black by k (0..1): the extruded walls of a country
  return rgbToHex(hexToRgb(hex).map((v) => v * (1 - k)));
}

function fmtPeople(n) {
  if (n >= 1e6) return (n / 1e6).toFixed(1) + " m";
  if (n >= 1e3) return Math.round(n / 1e3) + " k";
  return String(Math.round(n));
}

// ---- data helpers --------------------------------------------------------------
// A globe either colours by the index (history arrays, with the year slider) or by a custom
// current value per country (data.custom: e.g. change since last year, days to the next election).
const isLatest = (ctx) => ctx.yearIndex === ctx.data.years.length - 1;
function valueOf(ctx, c) {
  if (ctx.data.custom) return c.custom ?? null;
  return c.value ? c.value[ctx.yearIndex] : c.composite[ctx.yearIndex];
}
function norm(ctx, v) {
  const [lo, hi] = ctx.data.range;
  return hi > lo ? (v - lo) / (hi - lo) : 0;
}
function fmtValue(ctx, v) {
  const f = ctx.data.valueFormat;
  if (f === "signed") {
    const r = Math.round(v * 10) / 10;  // round first, so -0.04 prints 0.0, not -0.0
    return r === 0 ? "0.0" : (r > 0 ? "+" : "") + r.toFixed(1);
  }
  if (f === "days") return v <= 0 ? "today" : Math.round(v) === 1 ? "tomorrow" : "in " + Math.round(v) + " days";
  if (f === "score") return v.toFixed(0) + "/100";
  return v.toFixed(1);
}
function tierFor(ctx, score) {
  if (score == null) return null;
  let tier = ctx.data.tierList[0];
  for (const t of ctx.data.tierList) if (score >= t.lower) tier = t;
  return tier;
}
function locate(ctx, iso3) {
  const f = ctx.featureByIso.get(iso3);
  if (f) return f.centre;
  const c = ctx.byIso.get(iso3);
  return c && c.lat != null && c.lng != null ? { lat: c.lat, lng: c.lng } : null;
}

function nearestCountry(ctx, view) {
  // The country whose centre is closest to the middle of the view (for picking by keyboard)
  const rad = Math.PI / 180;
  let best = null;
  let bestD = Infinity;
  for (const c of ctx.data.countries) {
    const at = locate(ctx, c.iso3);
    if (!at) continue;
    const d = Math.acos(Math.min(1, Math.sin(view.lat * rad) * Math.sin(at.lat * rad)
      + Math.cos(view.lat * rad) * Math.cos(at.lat * rad) * Math.cos((view.lng - at.lng) * rad)));
    if (d < bestD) { bestD = d; best = c.iso3; }
  }
  return best;
}

function startView(ctx) {
  const data = ctx.data;
  const at = data.focus && ctx.featureByIso ? locate(ctx, data.focus) : null;
  if (at) return { lat: at.lat, lng: at.lng, altitude: 1.9 };
  if (data.centre) return { lng: data.centre[0], lat: data.centre[1], altitude: 1.6 };
  return { lng: 20, lat: 15, altitude: 2.3 };
}

function colourFor(ctx, c) {
  if (!c) return ctx.data.noData;
  const v = valueOf(ctx, c);
  if (v == null) return ctx.data.noData;
  if (!c.inView) return ctx.data.outOfView;
  return colourAt(ctx.data.colorscale, norm(ctx, v));
}

function heightFor(ctx, iso3, base) {
  const c = ctx.byIso.get(iso3);
  const v = c ? valueOf(ctx, c) : null;
  let h = base;
  if (ctx.extrude && c && c.inView && v != null) {
    const [lo, hi] = ctx.data.range;
    const t = ctx.data.extrudeAbs ? Math.abs(v) / Math.max(Math.abs(lo), Math.abs(hi), 1e-9) : norm(ctx, v);
    h += Math.max(0, Math.min(1, t)) * 0.035;
  }
  if (iso3 === ctx.selected) h += 0.018;
  return h;
}

// ---- layers --------------------------------------------------------------------
// Each country owns a lit (Phong) cap and wall material. Colours change by editing those materials
// in place (paintColours), which is instant and needs no geometry work — so hovering stays smooth even
// with the detailed outlines. paint() also resets heights and borders (year, selection, 3D toggle);
// the rings and arcs are redrawn by drawLayers().
function materialsFor(ctx, f) {
  if (!f.__materials) {
    const Phong = ctx.globe.globeMaterial().constructor;  // three.js MeshPhongMaterial, from the bundle
    f.__materials = {
      cap: new Phong({ side: 2, shininess: 22, specular: 0x2a2a2a }),
      wall: new Phong({ side: 2, shininess: 8, specular: 0x111111 }),
    };
  }
  return f.__materials;
}

function paintOne(ctx, f) {
  const m = materialsFor(ctx, f);
  const base = colourFor(ctx, ctx.byIso.get(f.iso3));
  const lit = f.iso3 === ctx.hover || f.iso3 === ctx.selected;
  m.cap.color.set(base);
  m.cap.emissive.set(lit ? base : "#000000");
  m.cap.emissiveIntensity = f.iso3 === ctx.selected ? 0.45 : 0.3;
  m.wall.color.set(shade(base, 0.45));
}

function paintPoints(ctx) {
  // The small-state dots are rebuilt whenever their accessors are set, so only do it when they change
  const key = ctx.points.map((c) => c.iso3 + (c.iso3 === ctx.selected ? "s" : "") + (c.iso3 === ctx.hover ? "h" : "") +
    colourFor(ctx, c)).join();
  if (key === ctx.pointsKey) return;
  ctx.pointsKey = key;
  ctx.globe
    .pointColor((c) => (c.iso3 === ctx.selected ? "#ffffff" : colourFor(ctx, c)))
    .pointRadius((c) => (c.iso3 === ctx.selected || c.iso3 === ctx.hover ? 0.55 : 0.38));
}

function paintColours(ctx) {
  for (const f of ctx.features) paintOne(ctx, f);
  paintPoints(ctx);
}

function hoverTo(ctx, iso3) {
  // Repaint only the country left and the one entered, not all of them
  if (ctx.hover === iso3) return;
  const prev = ctx.hover;
  ctx.hover = iso3;
  let dots = false;
  for (const code of [prev, iso3]) {
    if (!code) continue;
    if (!ctx.featureByIso.has(code)) dots = true;
    else for (const f of ctx.features) if (f.iso3 === code) paintOne(ctx, f);  // Somalia and Cyprus have two shapes
  }
  if (dots) paintPoints(ctx);
}

function paint(ctx) {
  const g = ctx.globe;
  if (!g) return;
  ctx.wake(LITE ? 0 : 300);  // the shapes take 250 ms to change
  paintColours(ctx);
  // Heights and borders rebuild every country's 3D shape, so skip that when nothing has changed
  const shape = ctx.features.length + "|" + ctx.points.length + "|" + ctx.selected + "|" +
    ctx.features.map((f) => heightFor(ctx, f.iso3, 0.004).toFixed(4)).join() + "|" +
    ctx.points.map((c) => heightFor(ctx, c.iso3, 0.008).toFixed(4)).join();
  if (shape === ctx.shapeKey) return;
  ctx.shapeKey = shape;
  g.polygonStrokeColor((f) => (f.iso3 === ctx.selected ? "#ffffff" : "rgba(0,0,0,0.55)"))
    .polygonAltitude((f) => heightFor(ctx, f.iso3, 0.004))
    .pointAltitude((c) => heightFor(ctx, c.iso3, 0.008));
}

function useOutlines(ctx, features) {
  // Swap in a set of country outlines (the detailed set arrives after the first draw)
  ctx.features = features;
  ctx.featureByIso = new Map(features.map((f) => [f.iso3, f]));
  // States too small for the outlines (most islands; fewer with the detailed set) are drawn as dots
  ctx.points = ctx.data.countries.filter((c) => !ctx.featureByIso.has(c.iso3) && c.lat != null && c.lng != null);
  ctx.globe.polygonsData(features);
}

function followCamera(ctx) {
  // Keep the sun just above and behind the viewer, so the side you look at is always lit
  if (!ctx.sun) return;
  const cam = ctx.globe.camera().position;
  ctx.sun.position.set(cam.x, cam.y + cam.length() * 0.35, cam.z);
}

function drawLayers(ctx) {
  if (!ctx.globe) return;
  ctx.wake();
  const dots = ctx.points.map((c) => c.iso3).join();
  if (dots !== ctx.dotsKey) { ctx.dotsKey = dots; ctx.globe.pointsData(ctx.points); }
  drawRings(ctx);
  drawArcs(ctx);
}

function circle(at, r, alt) {
  // A ring r degrees around a point, as path points [lat, lng, altitude]
  const k = 1 / Math.cos(at.lat * Math.PI / 180);
  return Array.from({ length: 41 }, (_, i) => {
    const a = (i / 40) * 2 * Math.PI;
    return [at.lat + r * Math.sin(a), at.lng + r * k * Math.cos(a), alt];
  });
}

function drawRings(ctx) {
  // One still ink ring per armed conflict, wider for more battle deaths
  const rings = [];
  if (ctx.showConflict) {
    for (const c of ctx.data.countries) {
      const deaths = c.deaths ? c.deaths[ctx.yearIndex] : null;
      if (deaths == null || deaths < ctx.data.conflictThreshold) continue;
      const at = locate(ctx, c.iso3);
      if (at) rings.push({ iso3: c.iso3, at, deaths, alt: heightFor(ctx, c.iso3, 0.006) + 0.002 });
    }
  }
  const key = rings.map((r) => r.iso3 + ":" + r.deaths + ":" + r.alt.toFixed(4)).join();
  if (key === ctx.ringsKey) return;
  ctx.ringsKey = key;
  ctx.globe.pathsData(rings)
    .pathPoints((r) => circle(r.at, 0.6 + Math.log10(r.deaths) * 0.6, r.alt))
    .pathPointAlt((p) => p[2])
    .pathColor(() => ctx.data.ink)
    .pathStroke(0.25)
    .pathTransitionDuration(0);
}

function drawArcs(ctx) {
  let flows = [];
  if (ctx.showFlows) {
    const all = ctx.data.flows || [];
    const pick = ctx.selected || ctx.data.focus;
    flows = pick ? all.filter((f) => f.from === pick || f.to === pick).slice(0, 20) : all.slice(0, ctx.data.topFlows);
  }
  const max = Math.max(1, ...flows.map((f) => f.value));
  const arcs = [];
  for (const f of flows) {
    const a = locate(ctx, f.from), b = locate(ctx, f.to);
    if (a && b) arcs.push({ ...f, startLat: a.lat, startLng: a.lng, endLat: b.lat, endLng: b.lng, w: Math.sqrt(f.value / max) });
  }
  const still = REDUCED.matches;  // reduced motion: solid lines, no travelling dashes
  ctx.arcsMoving = arcs.length > 0 && !still;
  const key = (still ? "still|" : "") + arcs.map((d) => d.from + ">" + d.to + ":" + d.value).join();
  if (key === ctx.arcsKey) return;
  ctx.arcsKey = key;
  ctx.globe.arcsData(arcs)
    .arcColor(() => ["rgba(116,177,254,0.08)", "rgba(185,215,254,0.95)"])
    .arcStroke((d) => 0.25 + 1.2 * d.w)
    .arcAltitudeAutoScale(0.35)
    .arcDashLength(still ? 1 : 0.45).arcDashGap(still ? 0 : 0.2)
    .arcDashInitialGap(() => (still ? 0 : Math.random()))
    .arcDashAnimateTime(still ? 0 : 2600)
    .arcLabel((d) => '<div class="rg-tip"><b>' + esc(d.fromName) + " → " + esc(d.toName) + "</b><br>" +
      fmtPeople(d.value) + " refugees &amp; asylum seekers <span>(UNHCR " + ctx.data.flowsYear + ")</span></div>");
}

function tooltip(ctx, iso3, fallbackName) {
  const c = ctx.byIso.get(iso3);
  const name = esc(c ? c.name : fallbackName);
  const v = c ? valueOf(ctx, c) : null;
  const note = c && c.note ? "<br>" + esc(c.note) : "";
  if (ctx.data.custom) {
    const shown = v == null ? "<span>" + esc(ctx.data.emptyLabel) + "</span>" : esc(ctx.data.metricLabel) + ": " + fmtValue(ctx, v);
    return '<div class="rg-tip"><b>' + name + "</b><br>" + shown + note + "<br><span>Click for the index</span></div>";
  }
  if (v == null) return '<div class="rg-tip"><b>' + name + "</b><br><span>No score</span>" + note + "</div>";
  const tier = tierFor(ctx, c.composite[ctx.yearIndex]);
  return '<div class="rg-tip"><b>' + name + "</b> <span>" + ctx.data.years[ctx.yearIndex] + "</span><br>" +
    esc(ctx.data.metricLabel) + ": " + v.toFixed(0) + "/100" + (tier ? " · " + esc(tier.label) : "") + note +
    "<br><span>Click for the index</span></div>";
}

function renderLegend(root, ctx) {
  const data = ctx.data;
  // Scores: one flat block per tier (the colour at its top score); other scales: one block per colour stop
  const blocks = data.valueFormat === "score" ? [0.2, 0.4, 0.6, 0.8, 1].map((t) => colourAt(data.colorscale, t))
                                              : data.colorscale.map(([, c]) => c);
  root.querySelector(".rg-legend-bar").innerHTML = blocks.map((c) => '<i style="background:' + c + '"></i>').join("");
  root.querySelector(".rg-legend-title").textContent =
    data.custom ? data.metricLabel : data.metricLabel + " risk · " + data.years[ctx.yearIndex];
  root.querySelector(".rg-legend-ticks").innerHTML = data.ticks.map((t) => "<span>" + esc(t) + "</span>").join("");
  const keys =
    (ctx.showConflict ? '<div><i style="border:2px solid ' + data.ink + ';box-sizing:border-box"></i>Armed conflict (≥ ' +
      data.conflictThreshold + " battle deaths)</div>" : "") +
    (ctx.showFlows && data.flows.length ? '<div><i style="background:#b9d7fe"></i>Refugee flows, origin → host (' +
      data.flowsYear + ")</div>" : "");
  root.querySelector(".rg-legend-keys").innerHTML = keys;
  root.classList.toggle("rg-noramp", !data.ramp);
  root.querySelector(".rg-legend").hidden = !data.ramp && !keys;  // nothing left to explain
}

function customLine(ctx, c) {
  let html = "";
  if (ctx.data.custom) {
    const v = valueOf(ctx, c);
    html += '<div class="rg-custom">' + esc(ctx.data.metricLabel) + ": <b>" +
      (v == null ? esc(ctx.data.emptyLabel) : fmtValue(ctx, v)) + "</b></div>";
  }
  if (c.note) html += '<div class="rg-note">' + esc(c.note) + "</div>";
  return html;
}

function renderPanel(root, ctx) {
  const panel = root.querySelector(".rg-panel");
  const iso = ctx.selected;
  if (!iso) { panel.hidden = true; panel.innerHTML = ""; return; }
  const c = ctx.byIso.get(iso);
  const feature = ctx.featureByIso.get(iso);
  const yi = ctx.yearIndex, year = ctx.data.years[yi];
  const flag = c && c.flag ? '<img src="' + esc(c.flag) + '" alt="">' : "";
  let html = '<button class="rg-close" aria-label="Close">×</button><div class="rg-name">' + flag + "<span>" +
    esc(c ? c.name : feature ? feature.properties.ADMIN : iso) + "</span></div>";
  const score = c ? c.composite[yi] : null;
  if (score == null) {
    html += '<div class="rg-sub">' + esc(c ? c.region : "") + '</div><p class="rg-note">Not enough data to score this country in ' +
      year + ".</p>" + (c ? customLine(ctx, c) : "");
  } else {
    const tier = tierFor(ctx, score);
    const prev = yi > 0 ? c.composite[yi - 1] : null;
    const d = prev == null ? null : Math.round((score - prev) * 10) / 10;  // rounded as in the tables
    const tone = d >= 1 ? "worse" : d <= -1 ? "better" : "faint";
    const delta = d == null ? "" : '<span class="rg-delta" style="color:var(--sg-' + tone + ')">' +
      (d >= 1 ? "▲" : d <= -1 ? "▼" : "■") + " " + (d > 0 ? "+" : "") + d.toFixed(1) + " vs " + (year - 1) + "</span>";
    html += '<div class="rg-sub">' + esc(c.region) + " · " + year + "</div>" +
      '<div class="rg-score"><span class="rg-big">' + score.toFixed(0) + '</span><span class="rg-of">/100</span>' +
      '<span class="rg-badge" style="background:' + tier.color + ";color:" + tier.text + '">' + esc(tier.label) + "</span></div>" +
      '<div class="rg-rank">Rank <b>' + c.rank[yi] + "</b> of " + ctx.data.nRanked[yi] + " " + delta + "</div>" +
      customLine(ctx, c) +
      '<div class="rg-section">Pillars · ' + ctx.data.years[ctx.data.years.length - 1] + "</div>" +
      '<div class="rg-pillars">' + ctx.data.pillars.map((p) => {
        const v = c.pillars[p.key];
        return '<div class="rg-prow' + (ctx.data.metric === p.key ? " rg-active" : "") + '"><span class="rg-plabel">' +
          esc(p.short) + '</span><span class="rg-ptrack"><span class="rg-pbar" style="width:' + (v == null ? 0 : v) +
          "%;background:" + p.color + '"></span></span><span class="rg-pval">' + (v == null ? "—" : v.toFixed(0)) + "</span></div>";
      }).join("") + "</div>" +
      (c.flags ? '<div class="rg-flags">⚑ ' + c.flags + " red flag" + (c.flags > 1 ? "s" : "") + " today</div>"
               : '<div class="rg-flags ok">✓ No red flags today</div>');
  }
  if (c && iso !== ctx.data.focus) html += '<button class="rg-open">Open country profile</button>';
  panel.innerHTML = html;
  panel.hidden = false;
  panel.querySelector(".rg-close").onclick = () => select(root, ctx, null, false);
  const open = panel.querySelector(".rg-open");
  if (open) open.onclick = () => ctx.trigger("open", iso);
}

function renderTime(root, ctx) {
  const input = root.querySelector(".rg-year-input");
  input.max = String(ctx.data.years.length - 1);
  input.value = String(ctx.yearIndex);
  root.querySelector(".rg-year").textContent = ctx.data.years[ctx.yearIndex];
  const play = root.querySelector(".rg-play");
  play.textContent = ctx.timer ? "❚❚" : "▶";
  play.setAttribute("aria-label", ctx.timer ? "Pause the replay" : "Replay the index year by year");
  play.title = play.getAttribute("aria-label");
}

function setYear(root, ctx, index) {
  ctx.yearIndex = index;
  renderTime(root, ctx);
  renderLegend(root, ctx);
  paint(ctx);
  drawLayers(ctx);
  renderPanel(root, ctx);
}

function togglePlay(root, ctx) {
  if (ctx.timer) { clearInterval(ctx.timer); ctx.timer = null; renderTime(root, ctx); return; }
  if (isLatest(ctx)) setYear(root, ctx, 0);
  ctx.timer = setInterval(() => {
    if (isLatest(ctx)) { clearInterval(ctx.timer); ctx.timer = null; renderTime(root, ctx); return; }
    setYear(root, ctx, ctx.yearIndex + 1);
  }, 900);
  renderTime(root, ctx);
}

function stopSpin(root, ctx) {
  if (!ctx.spin) return;
  ctx.spin = false;
  ctx.globe.controls().autoRotate = false;
  syncButtons(root, ctx);
}

function select(root, ctx, iso, fly) {
  const changed = ctx.selected !== iso;
  ctx.selected = iso;
  if (changed) ctx.setState("selected", iso);  // the page shows this country's news
  paint(ctx);
  drawLayers(ctx);  // arcs follow the selected country
  renderPanel(root, ctx);
  if (!iso) return;
  stopSpin(root, ctx);
  const at = fly && locate(ctx, iso);
  if (at) {
    const view = ctx.globe.pointOfView();
    ctx.globe.pointOfView({ lat: at.lat, lng: at.lng, altitude: Math.min(view.altitude, 1.7) }, flyMs(900));
  }
}

function syncButtons(root, ctx) {
  // The tint shows the state; aria-pressed tells assistive tech the same thing
  for (const [act, on] of [["spin", ctx.spin], ["extrude", ctx.extrude], ["flows", ctx.showFlows],
                           ["conflict", ctx.showConflict]]) {
    const button = root.querySelector('[data-act="' + act + '"]');
    button.classList.toggle("on", !!on);
    button.setAttribute("aria-pressed", on ? "true" : "false");
  }
}

function control(root, ctx, action) {
  const g = ctx.globe;
  if (!g) return;  // being rebuilt after a failure
  const view = g.pointOfView();
  if (action === "in") g.pointOfView({ ...view, altitude: Math.max(0.2, view.altitude * 0.65) }, flyMs(450));
  if (action === "out") g.pointOfView({ ...view, altitude: Math.min(5.5, view.altitude / 0.65) }, flyMs(450));
  if (action === "reset") { select(root, ctx, null, false); g.pointOfView(startView(ctx), flyMs(900)); }
  if (action === "spin") { ctx.spin = !ctx.spin; g.controls().autoRotate = ctx.spin; }
  if (action === "lock") lockGlobe(root, ctx, true);
  if (action === "extrude") ctx.extrude = !ctx.extrude;
  if (action === "flows") ctx.showFlows = !ctx.showFlows;
  if (action === "conflict") ctx.showConflict = !ctx.showConflict;
  if (["extrude", "flows", "conflict"].includes(action)) { paint(ctx); drawLayers(ctx); renderLegend(root, ctx); }
  syncButtons(root, ctx);
  ctx.wake();  // spin on or off
}

function fitSize(root, ctx) {
  ctx.globe.width(root.clientWidth).height(root.clientHeight);
  ctx.wake();
  // A narrow globe (a half-width column on a laptop) stacks its legend over the year bar, as on a phone
  root.classList.toggle("rg-narrow", root.clientWidth < 640);
}

function build(root, ctx, Globe, features) {
  const el = root.querySelector(".rg-canvas");
  const lastView = lastViews[ctx.data.key];
  const options = { animateIn: false,
                    rendererConfig: { antialias: !LITE, alpha: true, powerPreference: "high-performance" } };
  let g;
  try { g = new Globe(el, options); } catch (err) { g = Globe(options)(el); }
  ctx.globe = g;
  // The graphics card can drop the drawing context (a driver reset, too many 3D views open) or refuse a shader:
  // the globe then says so instead of freezing or going blank, and redraws itself if the context comes back
  const renderer = g.renderer();
  const broke = (err) => {
    if (ctx.globe !== g || ctx.failed) return;
    if (err instanceof Error) console.error("3D globe:", err);
    fail(root, ctx, "The 3D globe stopped drawing.");
  };
  renderer.domElement.addEventListener("webglcontextlost", broke);
  renderer.domElement.addEventListener("webglcontextrestored", () => {
    if (ctx.globe === g && ctx.failed) { teardown(root, ctx); startGlobe(root, ctx); }
  });
  if (renderer.debug) renderer.debug.onShaderError = () => broke(new Error("a shader did not compile"));
  const draw = renderer.render.bind(renderer);
  renderer.render = (scene, camera) => { try { draw(scene, camera); } catch (err) { broke(err); } };
  renderer.setPixelRatio(PIXEL_RATIO);  // sharp enough on high-DPI screens without rendering 4-9x the pixels
  g.backgroundColor("rgba(0,0,0,0)")
    .globeImageUrl(EARTH_IMAGE)
    .showAtmosphere(false)
    .showGraticules(false)
    .polygonCapCurvatureResolution(LITE ? 6 : 4)
    .polygonCapMaterial((f) => materialsFor(ctx, f).cap)
    .polygonSideMaterial((f) => materialsFor(ctx, f).wall)
    .polygonsTransitionDuration(LITE ? 0 : 250)
    .polygonLabel((f) => tooltip(ctx, f.iso3, f.properties.ADMIN))
    .onPolygonHover((f) => { el.style.cursor = f ? "pointer" : "grab"; hoverTo(ctx, f ? f.iso3 : null); })
    .onPolygonClick((f) => select(root, ctx, f.iso3, true))
    .pointLat("lat").pointLng("lng").pointsMerge(false).pointsTransitionDuration(LITE ? 0 : 250).pointResolution(12)
    .pointLabel((c) => tooltip(ctx, c.iso3, c.name))
    .onPointHover((c) => { el.style.cursor = c ? "pointer" : "grab"; hoverTo(ctx, c ? c.iso3 : null); })
    .onPointClick((c) => select(root, ctx, c.iso3, true))
    .pathLabel((r) => tooltip(ctx, r.iso3, r.iso3))
    .onPathHover((r) => { el.style.cursor = r ? "pointer" : "grab"; hoverTo(ctx, r ? r.iso3 : null); })
    .onPathClick((r) => select(root, ctx, r.iso3, true))
    .onGlobeClick(() => select(root, ctx, null, false));
  useOutlines(ctx, features);
  // The Earth: night lights at full strength, deep-navy oceans, terrain relief from the bump map
  const material = g.globeMaterial();
  material.color.set("#ffffff");
  material.emissive.set("#04111f");
  material.emissiveIntensity = 1;
  material.shininess = 9;
  material.specular.set("#0b1524");  // matte sea: a faint sheen, no washed-out glare up close
  if (!LITE) { g.bumpImageUrl(EARTH_BUMP); material.bumpScale = 5; }  // terrain relief: desktops only
  // Softer ambient light and a "sun" that follows the camera, so countries get depth and highlights
  for (const light of typeof g.lights === "function" ? g.lights() : []) {
    if (light.isAmbientLight) light.intensity = 0.8 * Math.PI;
    if (light.isDirectionalLight) { light.intensity = 1.1 * Math.PI; ctx.sun = light; }
  }
  // Draw only while something moves (spin, travelling flow dashes, a camera flight, input, new data or textures
  // still loading), and only while the globe is on screen in a visible tab; otherwise ask for no frames at all
  ctx.active = true;
  ctx.visible = true;
  ctx.setActive = () => {
    const moving = ctx.awake || ctx.spin || (ctx.arcsMoving && !(TOUCH && ctx.locked));
    const on = !!ctx.globe && !ctx.failed && ctx.visible && !document.hidden && moving;
    if (on === ctx.active) return;
    ctx.active = on;
    if (on) g.resumeAnimation(); else g.pauseAnimation();
  };
  const texturesReady = () => !!material.map && (LITE || !!material.bumpMap);
  ctx.texturesReady = false;
  ctx.textureRounds = 0;
  ctx.wake = (ms = 0) => {
    ctx.awake = true;
    clearTimeout(ctx.idleTimer);
    ctx.idleTimer = setTimeout(() => {
      if (!ctx.texturesReady && ctx.textureRounds++ < 20) {  // the Earth images may still be on their way (up to 30 s)
        ctx.texturesReady = texturesReady();
        return ctx.wake();  // and one more round once they are in
      }
      ctx.awake = false;
      ctx.setActive();
    }, ms + IDLE_MS);
    ctx.setActive();
  };
  const pov = g.pointOfView;
  g.pointOfView = function (view, ms) {  // a camera flight: keep drawing until it lands
    if (view) ctx.wake(ms || 0);
    return pov.apply(this, arguments);
  };
  ctx.watch = new IntersectionObserver((entries) => {
    ctx.visible = entries[entries.length - 1].isIntersecting;
    ctx.wake();  // back on screen: draw what changed meanwhile
    if (TOUCH && !ctx.visible && !ctx.locked) lockGlobe(root, ctx, true);  // scrolled away: lock it again
  });
  ctx.watch.observe(root);
  ctx.onVisibility = () => ctx.wake();
  document.addEventListener("visibilitychange", ctx.onVisibility);
  const controls = g.controls();
  controls.addEventListener("change", () => { followCamera(ctx); ctx.wake(); });  // also fires while it spins or glides
  controls.autoRotate = ctx.spin;
  controls.autoRotateSpeed = 0.35;
  controls.minDistance = 110;  // the 1:50m outlines hold up to about this close
  controls.maxDistance = 650;
  controls.zoomSpeed = 0.9;
  controls.addEventListener("start", () => stopSpin(root, ctx));
  // The wheel scrolls the page; Ctrl/⌘ + wheel zooms the globe (a trackpad pinch arrives as Ctrl + wheel too).
  // Stopped in the capture phase, a plain wheel never reaches the globe's controls, so nothing blocks the scroll.
  el.addEventListener("wheel", (e) => {
    if (e.ctrlKey || e.metaKey) return;
    e.stopPropagation();
    toast(root, "Hold " + ZOOM_KEY + " and scroll to zoom the globe");
  }, { capture: true });
  // Keyboard: the globe is one tab stop; arrows turn it, + and - zoom, Enter picks the country in the middle
  el.tabIndex = 0;
  el.setAttribute("role", "application");
  el.setAttribute("aria-label", "3D globe. Arrow keys turn it, plus and minus zoom, Enter opens the country in the "
    + "middle, Escape closes it.");
  el.addEventListener("keydown", (e) => {
    const view = g.pointOfView();
    const step = Math.max(2, Math.min(20, view.altitude * 8));  // finer steps when zoomed in
    const turn = { ArrowLeft: [0, -step], ArrowRight: [0, step], ArrowUp: [step, 0], ArrowDown: [-step, 0] }[e.key];
    if (turn) {
      stopSpin(root, ctx);
      g.pointOfView({ lat: Math.max(-80, Math.min(80, view.lat + turn[0])), lng: view.lng + turn[1],
                      altitude: view.altitude }, flyMs(250));
    } else if (e.key === "+" || e.key === "=") control(root, ctx, "in");
    else if (e.key === "-" || e.key === "_") control(root, ctx, "out");
    else if (e.key === "Enter" || e.key === " ") {
      const iso = nearestCountry(ctx, view);
      if (iso) select(root, ctx, iso, true);
    } else if (e.key === "Escape" && ctx.selected) select(root, ctx, null, false);
    else return;
    e.preventDefault();
  });
  if (TOUCH) lockGlobe(root, ctx, true);
  root.querySelector(".rg-lock").onclick = () => lockGlobe(root, ctx, false);
  // The motion setting can change while the page is open
  ctx.motion = () => {
    ctx.arcsKey = null;
    drawLayers(ctx);
    if (REDUCED.matches) stopSpin(root, ctx);
  };
  REDUCED.addEventListener("change", ctx.motion);
  g.pointOfView(lastView || startView(ctx), 0);
  followCamera(ctx);
  ctx.centreKey = JSON.stringify([ctx.data.centre, ctx.data.focus]);
  fitSize(root, ctx);
  ctx.resize = new ResizeObserver(() => fitSize(root, ctx));
  ctx.resize.observe(root);
  root.querySelectorAll(".rg-controls button").forEach((b) => { b.onclick = () => control(root, ctx, b.dataset.act); });
  root.querySelector(".rg-play").onclick = () => togglePlay(root, ctx);
  root.querySelector(".rg-year-input").oninput = (e) => {
    if (ctx.timer) togglePlay(root, ctx);
    setYear(root, ctx, Number(e.target.value));
  };
  syncButtons(root, ctx);
  setYear(root, ctx, ctx.yearIndex);
  setControls(root, true);
  if (renderer.getContext().isContextLost()) broke();  // it never got a working context
}

// Draw (or redraw with new data) a globe in root; the component's render, called once per data
function render(root, ctx, data) {
  const newYears = !ctx.data || ctx.data.years.join() !== data.years.join() || !data.showTime;
  ctx.data = data;
  ctx.byIso = new Map(data.countries.map((c) => [c.iso3, c]));
  if (newYears) ctx.yearIndex = data.years.length - 1;
  root.style.height = data.height + "px";
  root.style.setProperty("--rg-mobile-h", Math.min(520, data.height) + "px");
  root.querySelector(".rg-time").hidden = !data.showTime;
  root.querySelector('[data-act="flows"]').hidden = !data.flows.length;
  root.querySelector(".rg-hint").textContent = data.hint || defaultHint();

  if (ctx.failed) {
    // the note stays until Try again, or until the graphics card hands the context back
  } else if (ctx.globe) {
    ctx.points = data.countries.filter((c) => !ctx.featureByIso.has(c.iso3) && c.lat != null && c.lng != null);
    setYear(root, ctx, ctx.yearIndex);
    const key = JSON.stringify([data.centre, data.focus]);
    if (key !== ctx.centreKey) { ctx.centreKey = key; ctx.globe.pointOfView(startView(ctx), flyMs(1200)); }
  } else if (!ctx.loading && !webglAvailable()) {
    fail(root, ctx, "This browser can't draw the 3D globe (WebGL is off or not supported).", false);
  } else if (!ctx.loading) {
    startGlobe(root, ctx);
  }
}

// Mount a globe in el for buildGlobeData's data. Callbacks: onSelect(iso3 | null) when the picked country changes,
// onOpen(iso3) for "Open country profile", onFlat() for "Show the flat map" in the failure note (data.flatLink).
// Returns {update(data), select(iso3), destroy()}.
export function riskGlobe(el, data, { onSelect = null, onOpen = null, onFlat = null } = {}) {
  el.insertAdjacentHTML("beforeend", HTML);
  const root = el.lastElementChild;
  const ctx = {
    selected: data.selected || null, hover: null,
    spin: data.layers.spin && !data.selected && !data.focus && !LITE && !REDUCED.matches,
    extrude: data.layers.extrude,
    showFlows: data.layers.flows, showConflict: data.layers.conflict, globe: null, timer: null,
    yearIndex: data.years.length - 1,
    wake: () => {},  // until the globe is built
    trigger: (name, value) => { if (name === "open" && onOpen) onOpen(value); if (name === "flat" && onFlat) onFlat(); },
    setState: (name, value) => { if (name === "selected" && onSelect) onSelect(value); },
  };
  // Any input on the globe or its controls (hover, drag, keys, the year slider) wakes it up
  for (const type of ["pointermove", "pointerdown", "pointerout", "wheel", "keydown", "input", "focusin"]) {
    root.addEventListener(type, () => ctx.wake(), { capture: true, passive: true });
  }
  render(root, ctx, data);
  return {
    update: (next) => { if (!ctx.destroyed) render(root, ctx, next); },
    select: (iso3) => {
      if (ctx.destroyed) return;
      if (ctx.globe) select(root, ctx, iso3 || null, true);
      else ctx.selected = iso3 || null;  // shown, and flown to, once the globe is built
    },
    destroy: () => {
      ctx.destroyed = true;
      teardown(root, ctx);
      root.remove();
    },
  };
}

function setControls(root, on) {
  root.querySelectorAll(".rg-controls button").forEach((b) => { b.disabled = !on; });
}

function teardown(root, ctx) {
  // Stop and release the globe (it left the page, or a new one is about to replace it); its camera is kept
  const g = ctx.globe;
  ctx.globe = null;  // first, so the context loss that releasing it fires is not taken for a failure
  if (ctx.timer) { clearInterval(ctx.timer); ctx.timer = null; }
  clearTimeout(ctx.idleTimer);
  ctx.wake = () => {};
  if (ctx.resize) ctx.resize.disconnect();
  if (ctx.watch) ctx.watch.disconnect();
  if (ctx.onVisibility) document.removeEventListener("visibilitychange", ctx.onVisibility);
  if (ctx.motion) REDUCED.removeEventListener("change", ctx.motion);
  ctx.shapeKey = ctx.pointsKey = ctx.dotsKey = ctx.ringsKey = ctx.arcsKey = null;  // a new globe draws every layer
  if (g) {
    try { lastViews[ctx.data.key] = g.pointOfView(); } catch (err) { /* keep the last saved view */ }
    try {
      if (g._destructor) g._destructor();
      const renderer = g.renderer();
      renderer.dispose();
      // browsers allow only a few WebGL contexts at once: give this one back now (unless it is already gone)
      if (!renderer.getContext().isContextLost()) renderer.forceContextLoss();
    } catch (err) { /* already gone */ }
  }
  const el = root.querySelector(".rg-canvas");
  el.replaceWith(el.cloneNode(false));  // an empty holder, without the old canvas or its key and wheel listeners
}

function fail(root, ctx, cause, retry = true) {
  // The note says what happened and where else to see the data; the canvas, hints and legend go, the toolbar stays off
  ctx.failed = true;
  ctx.active = false;
  clearTimeout(ctx.idleTimer);
  if (ctx.timer) { clearInterval(ctx.timer); ctx.timer = null; }
  if (ctx.globe) { try { ctx.globe.pauseAnimation(); } catch (err) { /* nothing left to pause */ } }
  const hadFocus = root.contains(document.activeElement);
  root.classList.add("rg-failed");
  setControls(root, false);
  const status = root.querySelector(".rg-status");
  status.textContent = cause + " " + ctx.data.fallback;
  status.hidden = false;
  const acts = document.createElement("div");
  acts.className = "rg-acts";
  const act = (label, run) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "rg-retry";
    b.textContent = label;
    b.onclick = run;
    acts.append(b);
  };
  if (ctx.data.flatLink) act("Show the flat map", () => ctx.trigger("flat", true));  // the page switches the map style
  if (retry) act("Try again", () => { teardown(root, ctx); startGlobe(root, ctx); });
  if (!acts.firstChild) return;
  status.append(acts);
  if (hadFocus) acts.firstChild.focus();  // focus was on the globe or its toolbar, which are gone
}

function webglAvailable() {
  try {
    const canvas = document.createElement("canvas");
    return !!(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch (err) {
    return false;
  }
}

function startGlobe(root, ctx) {
  const status = root.querySelector(".rg-status");
  ctx.failed = false;
  root.classList.remove("rg-failed");
  setControls(root, false);  // until there is a globe to drive
  status.hidden = false;
  status.textContent = "Loading the 3D globe…";
  ctx.loading = Promise.all([loadLibrary(), loadCountries(COUNTRIES)])
    .then(([Globe, features]) => {
      if (ctx.destroyed) return;  // the page moved on while the files downloaded
      build(root, ctx, Globe, features);
      if (ctx.failed) return;  // it stopped drawing straight away: the note is up
      status.hidden = true;
      if (ctx.selected) {  // built with a country already picked: fly to it
        const at = locate(ctx, ctx.selected);
        if (at) ctx.globe.pointOfView({ lat: at.lat, lng: at.lng, altitude: 1.7 }, 0);
      }
      // Then swap in the detailed outlines (not on phones: 3x the shapes); if they fail, the simple ones stay
      if (LITE) return;
      loadCountries(COUNTRIES_DETAILED)
        .then((detailed) => {
          if (!ctx.globe) return;
          useOutlines(ctx, detailed);
          paint(ctx);
          drawLayers(ctx);
          renderPanel(root, ctx);
        })
        .catch(() => {});
    })
    .catch((err) => {  // a download failed, or the globe could not be set up (no WebGL context, for one)
      ctx.loading = null;
      if (ctx.destroyed) return;
      teardown(root, ctx);  // drop a half-built globe
      fail(root, ctx, "The 3D globe could not load (" + (err && err.message ? err.message : err) + ").");
    });
}
