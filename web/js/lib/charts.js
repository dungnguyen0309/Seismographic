// Port of prm/charts.py: the figures that depend on a visitor's choice, as Plotly {data, layout} objects equal to the
// Python figure's plotly.io.to_json (minus the template), and plot(), which draws a figure the way st.plotly_chart does
// in this app (the Streamlit dark theme, the container width, no mode bar). Figures with no visitor choice are built
// in Python (staticbuild/charts.py figure()) and only drawn here. Call setConfig(data/config.json) once at start.
import { asRows } from "./scoring.js";
import { fixed, pyRound, signed } from "./format.js";

let C = null;
export const setConfig = (config) => { C = config; };
export const config = () => {
  if (!C) throw new Error("charts: call setConfig(config) first");
  return C;
};

// ---- Plotly, loaded once on the first chart ------------------------------------------------------------------
const PLOTLY_URL = "/vendor/plotly/plotly.min.js";
let plotlyPromise = null;
export function loadPlotly() {
  if (window.Plotly) return Promise.resolve(window.Plotly);
  plotlyPromise ??= new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = PLOTLY_URL;
    script.async = true;
    script.onload = () => resolve(window.Plotly);
    script.onerror = () => { plotlyPromise = null; script.remove(); reject(new Error("the chart library could not be downloaded")); };
    document.head.append(script);
  });
  return plotlyPromise;
}

// The template every st.plotly_chart figure gets in this app: Python's "streamlit" template with its placeholder
// colours resolved and Streamlit's theme layout merged in (read from the running app, .streamlit/config.toml dark theme).
const TEMPLATE = '{"data":{"candlestick":[{"decreasing":{"line":{"color":"#ffabab"}},"increasing":{"line":{"color":"#7defa1"}},"type":"candlestick"}],"contourcarpet":[{"colorscale":[[0,"#004280"],[0.1111111111111111,"#0054a3"],[0.2222222222222222,"#0068c9"],[0.3333333333333333,"#1c83e1"],[0.4444444444444444,"#3d9df3"],[0.5555555555555556,"#60b4ff"],[0.6666666666666666,"#83c9ff"],[0.7777777777777778,"#a6dcff"],[0.8888888888888888,"#c7ebff"],[1,"#e4f5ff"]],"type":"contourcarpet"}],"contour":[{"colorscale":[[0,"#004280"],[0.1111111111111111,"#0054a3"],[0.2222222222222222,"#0068c9"],[0.3333333333333333,"#1c83e1"],[0.4444444444444444,"#3d9df3"],[0.5555555555555556,"#60b4ff"],[0.6666666666666666,"#83c9ff"],[0.7777777777777778,"#a6dcff"],[0.8888888888888888,"#c7ebff"],[1,"#e4f5ff"]],"type":"contour"}],"heatmap":[{"colorscale":[[0,"#004280"],[0.1111111111111111,"#0054a3"],[0.2222222222222222,"#0068c9"],[0.3333333333333333,"#1c83e1"],[0.4444444444444444,"#3d9df3"],[0.5555555555555556,"#60b4ff"],[0.6666666666666666,"#83c9ff"],[0.7777777777777778,"#a6dcff"],[0.8888888888888888,"#c7ebff"],[1,"#e4f5ff"]],"type":"heatmap"}],"histogram2d":[{"colorscale":[[0,"#004280"],[0.1111111111111111,"#0054a3"],[0.2222222222222222,"#0068c9"],[0.3333333333333333,"#1c83e1"],[0.4444444444444444,"#3d9df3"],[0.5555555555555556,"#60b4ff"],[0.6666666666666666,"#83c9ff"],[0.7777777777777778,"#a6dcff"],[0.8888888888888888,"#c7ebff"],[1,"#e4f5ff"]],"type":"histogram2d"}],"icicle":[{"textfont":{"color":"white"},"type":"icicle"}],"sankey":[{"textfont":{"color":"#e6eaf1"},"type":"sankey"}],"scatter":[{"marker":{"line":{"width":0}},"type":"scatter"}],"table":[{"cells":{"fill":{"color":"#000000"},"font":{"color":"#fafafa"},"line":{"color":"rgba(236, 236, 236, 0.1)"}},"header":{"fill":{"color":"rgba(10, 10, 10, 1)"},"font":{"color":"#e6eaf1"},"line":{"color":"rgba(236, 236, 236, 0.1)"}},"type":"table"}],"waterfall":[{"connector":{"line":{"color":"#e6eaf1","width":2}},"decreasing":{"marker":{"color":"#ffabab"}},"increasing":{"marker":{"color":"#7defa1"}},"totals":{"marker":{"color":"#83c9ff"}},"type":"waterfall"}]},"layout":{"coloraxis":{"colorscale":[[0,"#004280"],[0.1111111111111111,"#0054a3"],[0.2222222222222222,"#0068c9"],[0.3333333333333333,"#1c83e1"],[0.4444444444444444,"#3d9df3"],[0.5555555555555556,"#60b4ff"],[0.6666666666666666,"#83c9ff"],[0.7777777777777778,"#a6dcff"],[0.8888888888888888,"#c7ebff"],[1,"#e4f5ff"]],"colorbar":{"thickness":16,"xpad":24,"ticklabelposition":"outside","outlinecolor":"transparent","outlinewidth":8,"len":0.75,"y":0.5745,"title":{"font":{"color":"#e6eaf1","size":14}},"tickfont":{"color":"#e6eaf1","size":12}}},"colorscale":{"diverging":[[0,"#7d353b"],[0.1111111111111111,"#bd4043"],[0.2222222222222222,"#ff4b4b"],[0.3333333333333333,"#ff8c8c"],[0.4444444444444444,"#ffc7c7"],[0.5555555555555556,"#a6dcff"],[0.6666666666666666,"#60b4ff"],[0.7777777777777778,"#1c83e1"],[0.8888888888888888,"#0054a3"],[1,"#004280"]],"sequential":[[0,"#004280"],[0.1111111111111111,"#0054a3"],[0.2222222222222222,"#0068c9"],[0.3333333333333333,"#1c83e1"],[0.4444444444444444,"#3d9df3"],[0.5555555555555556,"#60b4ff"],[0.6666666666666666,"#83c9ff"],[0.7777777777777778,"#a6dcff"],[0.8888888888888888,"#c7ebff"],[1,"#e4f5ff"]],"sequentialminus":[[0,"#004280"],[0.1111111111111111,"#0054a3"],[0.2222222222222222,"#0068c9"],[0.3333333333333333,"#1c83e1"],[0.4444444444444444,"#3d9df3"],[0.5555555555555556,"#60b4ff"],[0.6666666666666666,"#83c9ff"],[0.7777777777777778,"#a6dcff"],[0.8888888888888888,"#c7ebff"],[1,"#e4f5ff"]]},"colorway":["#83c9ff","#0068c9","#ffabab","#ff2b2b","#7defa1","#29b09d","#ffd16a","#ff8700","#6d3fc0","#d5dae5"],"font":{"color":"#e6eaf1","family":"JetBrains Mono, \\"Source Sans\\", sans-serif","size":12,"weight":400},"title":{"color":"#ececec","subtitleColor":"#ececec","font":{"family":"JetBrains Mono, \\"Source Sans\\", sans-serif","size":16,"color":"#ececec"},"pad":{"l":4},"xanchor":"left","x":0},"legend":{"title":{"font":{"size":12,"color":"#e6eaf1"},"side":"top"},"valign":"top","bordercolor":"transparent","borderwidth":0,"font":{"size":12,"color":"#fafafa"}},"paper_bgcolor":"#000000","plot_bgcolor":"#000000","yaxis":{"ticklabelposition":"outside","zerolinecolor":"#31333F","title":{"font":{"color":"#e6eaf1","size":14},"standoff":24},"tickcolor":"#31333F","tickfont":{"color":"#e6eaf1","size":12},"gridcolor":"#31333F","minor":{"gridcolor":"#31333F"},"automargin":true},"xaxis":{"zerolinecolor":"#31333F","gridcolor":"#31333F","showgrid":false,"tickfont":{"color":"#e6eaf1","size":12},"tickcolor":"#31333F","title":{"font":{"color":"#e6eaf1","size":14},"standoff":20},"minor":{"gridcolor":"#31333F"},"zeroline":false,"automargin":true,"rangeselector":{"bgcolor":"#000000","bordercolor":"#31333F","borderwidth":1,"x":0}},"margin":{"pad":8,"r":0,"l":0},"hoverlabel":{"bgcolor":"#000000","bordercolor":"#2c2c2a","font":{"color":"#e6eaf1","family":"JetBrains Mono, \\"Source Sans\\", sans-serif","size":12}},"ternary":{"gridcolor":"#e6eaf1","bgcolor":"#000000","title":{"font":{"family":"JetBrains Mono, \\"Source Sans\\", sans-serif","size":14}},"color":"#e6eaf1","aaxis":{"gridcolor":"#e6eaf1","linecolor":"#e6eaf1","tickfont":{"family":"JetBrains Mono, \\"Source Sans\\", sans-serif","size":12}},"baxis":{"linecolor":"#e6eaf1","gridcolor":"#e6eaf1","tickfont":{"family":"JetBrains Mono, \\"Source Sans\\", sans-serif","size":12}},"caxis":{"linecolor":"#e6eaf1","gridcolor":"#e6eaf1","tickfont":{"family":"JetBrains Mono, \\"Source Sans\\", sans-serif","size":12}}}}}';

// What st.plotly_chart hands plotly.js: the figure with the template above (every figure in the app uses the default
// "streamlit" template, so a template in pre-built JSON is replaced), a bold title, the container width (150 px at
// least), the figure height (450 px without one) and, on clickable charts, Streamlit's point-selection modes.
export function themed(fig, width, { clickable = false } = {}) {
  const layout = { ...structuredClone(fig.layout ?? {}), template: JSON.parse(TEMPLATE) };
  if (layout.title !== undefined && layout.title !== null) {
    const title = typeof layout.title === "string" ? { text: layout.title } : layout.title;
    layout.title = { ...title, text: `<b>${typeof title.text === "string" ? title.text : ""}</b>` };
  }
  if (clickable) {
    layout.clickmode ||= "event+select";
    layout.hovermode ||= "closest";
    layout.dragmode ||= "pan";
  }
  layout.width = Math.max(width, 150);
  layout.height ??= 450;
  const config = { displayModeBar: false, showSendToCloud: false, displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d", "sendChartToCloud"],
    topojsonURL: "/vendor/plotly/topojson/" };  // the geo base map (world_110m.json), not cdn.plot.ly
  return { data: fig.data ?? [], layout, config };
}

// ISO3 code of a clicked point: clickable charts put it last in customdata (ui.clicked_iso3).
export const clickedIso3 = (point) => {
  const custom = point?.customdata;
  return Array.isArray(custom) && custom.length ? String(custom[custom.length - 1]) : null;
};

// Draw a figure into el; resizes with el; returns a cleanup that releases it. onClick(point) makes points clickable.
export function plot(el, fig, { onClick = null } = {}) {
  let gone = false;
  let resize = null;
  loadPlotly().then((Plotly) => {
    if (gone) return;
    const { data, layout, config } = themed(fig, el.clientWidth, { clickable: !!onClick });
    return Plotly.newPlot(el, data, layout, config).then(() => {
      if (gone) { Plotly.purge(el); return; }
      if (onClick) el.on("plotly_click", (e) => { if (e?.points?.length) onClick(e.points[0]); });
      resize = new ResizeObserver(() => {
        const w = el.clientWidth;  // 0 while hidden: keep the last size
        if (w && Math.max(w, 150) !== el.layout?.width) Plotly.relayout(el, { width: Math.max(w, 150) });
      });
      resize.observe(el);
    });
  }).catch((err) => {
    if (gone) return;
    console.error("chart:", err);
    el.textContent = "This chart could not be drawn.";
  });
  return () => {
    gone = true;
    if (resize) resize.disconnect();
    if (window.Plotly && el.data) window.Plotly.purge(el);
  };
}

// ---- constants and small helpers --------------------------------------------------------------------------------
const K = () => {
  const c = config();
  return {
    c, INK: c.INK, FONT: { family: c.MONO_FONT, size: 12 }, SURFACE: c.INK.bg, GRID: c.INK.line, MUTED: c.INK.faint,
    WORSE: c.INK.worse, BETTER: c.INK.better,
    HOVER: { bgcolor: c.INK.hover, bordercolor: c.INK["line-strong"], font: { color: c.INK.strong, family: c.MONO_FONT, size: 12 } },
    PILLARS: c.pillars, TIERS: c.tiers, TIER_ORDER: c.tiers.map((t) => t.label),
    TIER_COLORS: Object.fromEntries(c.tiers.map((t) => [t.label, t.color])),
  };
};
const FIFTHS = ["Safest fifth", "2nd fifth", "Middle fifth", "4th fifth", "Riskiest fifth"];

const na = (v) => v === null || v === undefined || Number.isNaN(v);
const val = (v) => (na(v) ? null : v);
const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const pyStr = (v) => (v === null || v === undefined ? "None" : Number.isNaN(v) ? "nan" : String(v));
// numpy's round (Series.round): half to even on value * 10^d
const npRound = (v, d = 0) => {
  if (na(v)) return null;
  const k = 10 ** d, y = v * k, r = Math.round(y);
  return (Math.abs(y % 1) === 0.5 ? 2 * Math.round(y / 2) : r) / k;
};
const median = (xs) => {
  const s = xs.filter((v) => !na(v)).sort((a, b) => a - b);
  if (!s.length) return NaN;
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};
// stable sorts, missing values last (pandas' na_position): pandas' quicksort orders ties by CPU, the fixtures keep
// them in their original order
const sortBy = (rows, key, desc = false) => rows.map((r, i) => [r, i]).sort(([a, i], [b, j]) =>
  (na(a[key]) - na(b[key])) || (na(a[key]) ? 0 : desc ? b[key] - a[key] : a[key] - b[key]) || i - j).map(([r]) => r);
const nsmallest = (rows, n, key) => sortBy(rows.filter((r) => !na(r[key])), key).slice(0, n);
const nlargest = (rows, n, key) => sortBy(rows.filter((r) => !na(r[key])), key, true).slice(0, n);
const dedupe = (rows, key) => {
  const seen = new Set();
  return rows.filter((r) => !seen.has(r[key] ?? null) && seen.add(r[key] ?? null));
};
const fmt = (v, spec) => {  // Python's f"{v:{spec}}" for the specs the charts use (",.0f", ".1f")
  const m = /^(,?)\.(\d+)f$/.exec(spec);
  if (!m) throw new Error(`charts: unsupported format ${spec}`);
  return fixed(v, Number(m[2]), { group: m[1] === "," });
};

// plotly's update semantics: nested objects merge, anything else replaces; inputs are copied, not shared
function merge(target, src) {
  for (const [k, v] of Object.entries(src)) {
    if (v === undefined) continue;
    target[k] = isObj(v) ? merge(isObj(target[k]) ? target[k] : {}, v) : v;
  }
  return target;
}
const trace = (type, props) => merge({ type }, props);
const updateLayout = (fig, props) => { merge(fig.layout, props); return fig; };
const updateXaxes = (fig, props) => updateLayout(fig, { xaxis: props });
const updateYaxes = (fig, props) => updateLayout(fig, { yaxis: props });
const addShape = (fig, s) => { (fig.layout.shapes ??= []).push(merge({}, s)); return fig; };
const addAnnotation = (fig, a) => { (fig.layout.annotations ??= []).push(merge({}, a)); return fig; };
const addVline = (fig, x, line) => addShape(fig, { type: "line", x0: x, x1: x, xref: "x", y0: 0, y1: 1, yref: "y domain", line });
const addHline = (fig, y, line) => addShape(fig, { type: "line", x0: 0, x1: 1, xref: "x domain", y0: y, y1: y, yref: "y", line });
const figure = (...data) => ({ data, layout: {} });

const pillarBy = (key) => config().pillars.find((p) => p.key === key);
export const mapColorscale = (metric) => {
  const ramp = config().PILLAR_RAMPS[metric];
  return ramp ? ramp.map((c, i) => [i / (ramp.length - 1), c]) : config().MAP_COLORSCALE;
};
const regionShort = (name) => config().regions.find((r) => r.name === name)?.short ?? name;

// ---- shared layout (charts._base, _label_room, _value_room, _dark_geo) -----------------------------------------
export function base(fig, height = 420, legend = false) {
  const { INK, FONT, GRID, MUTED, HOVER } = K();
  updateLayout(fig, {
    height, margin: { l: 8, r: 8, t: 36, b: 8 }, font: FONT, showlegend: legend,
    legend: { orientation: "h", yanchor: "bottom", y: 1.02, xanchor: "left", x: 0, title: {}, font: { color: INK.text } },
    hoverlabel: HOVER,
  });
  const axis = { gridcolor: GRID, zeroline: false, tickfont: { color: MUTED }, title: { font: { color: MUTED } } };
  updateXaxes(fig, axis);
  return updateYaxes(fig, axis);
}

// Reserve the y-label width up front (7.5 px a character in the 12 px mono face, plus slack)
const labelRoom = (fig, labels) =>
  updateLayout(fig, { margin: { l: 12 + pyRound(7.5 * Math.max(0, ...labels.map((s) => [...pyStr(s)].length))) } });

// Room past the longest bars for their outside value labels
function valueRoom(fig, x) {
  const known = x.filter((v) => !na(v));
  if (x.some((v) => v !== 0) && known.length) {  // all zero (or empty): keep autorange
    const lo = Math.min(Math.min(...known), 0), hi = Math.max(Math.max(...known), 0);
    const pad = 0.45 * ((hi - lo) || 1);
    updateXaxes(fig, { range: [lo < 0 ? lo - pad : 0, hi > 0 ? hi + pad : 0] });
  }
  return fig;
}

function darkGeo(fig, zoom, height = 520) {
  const { c, FONT, SURFACE, HOVER } = K();
  updateLayout(fig, { geo: {
    showframe: false, showcoastlines: false, showland: true, landcolor: c.NO_DATA_COLOR, showcountries: true,
    countrycolor: SURFACE, countrywidth: 0.6, showocean: true, oceancolor: c.OCEAN_COLOR, showlakes: true,
    lakecolor: c.OCEAN_COLOR, bgcolor: "rgba(0,0,0,0)", projection: { type: "natural earth" },
    ...(zoom ? { fitbounds: "locations" } : { lataxis: { range: [-58, 84] } }),
  } });
  return updateLayout(fig, { height, margin: { l: 0, r: 0, t: 0, b: 0 }, font: FONT, geo: { bgcolor: "rgba(0,0,0,0)" }, hoverlabel: HOVER });
}

// ---- Overview --------------------------------------------------------------------------------------------------
// Flat world map of a 0-100 risk score; rows need iso3, name, tier, rank_label and valueCol. ISO3 is last in customdata.
export function choropleth(df, valueCol, colorbarTitle, zoomToData = false) {
  const { SURFACE } = K();
  const d = asRows(df).filter((r) => !na(r[valueCol]));
  return darkGeo(figure(trace("choropleth", {
    locations: d.map((r) => r.iso3), z: d.map((r) => r[valueCol]), locationmode: "ISO-3", zmin: 0, zmax: 100,
    colorscale: mapColorscale(valueCol), marker: { line: { color: SURFACE, width: 0.6 } },
    colorbar: { title: { text: `${colorbarTitle} risk (0–100)`, side: "top" }, orientation: "h", x: 0.5, xanchor: "center",
      y: -0.02, yanchor: "top", thickness: 10, len: 0.55, tickvals: [0, 20, 40, 60, 80, 100], outlinewidth: 0 },
    customdata: d.length ? d.map((r) => [pyStr(r.name), pyStr(r.tier ?? "—"), pyStr(r.rank_label), pyStr(r.iso3)]) : undefined,
    hovertemplate: "<b>%{customdata[0]}</b><br>Score: %{z:.0f} / 100<br>Tier: %{customdata[1]}<br>Rank: %{customdata[2]}"
      + "<br><i>Click to open the profile</i><extra></extra>",
  })), zoomToData && d.length > 0);
}

// Scatter of two pillar scores; colour = tier, size = population
export function riskMatrix(df, xKey, yKey) {
  const { SURFACE, WORSE, BETTER, MUTED, TIER_ORDER, TIER_COLORS } = K();
  const [px, py] = [pillarBy(xKey), pillarBy(yKey)];
  const d = asRows(df).filter((r) => !na(r[xKey]) && !na(r[yKey]) && !na(r.tier));
  const pops = d.map((r) => r.population).filter((v) => !na(v));
  const fill = pops.length ? median(pops) : 1e6;
  const pop = d.map((r) => Math.max(na(r.population) ? fill : r.population, 1e5));
  const top = Math.sqrt(Math.max(...pop));
  const size = new Map(d.map((r, i) => [r, Math.max(Math.sqrt(pop[i]) / top * 38, 8)]));
  const fig = figure();
  for (const tier of TIER_ORDER) {
    const t = d.filter((r) => r.tier === tier);
    if (!t.length) continue;
    fig.data.push(trace("scatter", {
      x: t.map((r) => r[xKey]), y: t.map((r) => r[yKey]), mode: "markers", name: tier,
      marker: { size: t.map((r) => size.get(r)), color: TIER_COLORS[tier], line: { color: SURFACE, width: 2 }, opacity: 0.92 },
      customdata: t.map((r) => [r.name, npRound(r.composite, 0), r.iso3]),
      hovertemplate: "<b>%{customdata[0]}</b><br>" + px.short + ": %{x:.0f}<br>" + py.short + ": %{y:.0f}<br>Composite: "
        + "%{customdata[1]}<br><i>Click to open the profile</i><extra></extra>",
    }));
  }
  addShape(fig, { type: "rect", x0: 50, x1: 103, y0: 50, y1: 103, fillcolor: WORSE, opacity: 0.10, line: { width: 0 }, layer: "below" });
  addShape(fig, { type: "rect", x0: -3, x1: 50, y0: -3, y1: 50, fillcolor: BETTER, opacity: 0.10, line: { width: 0 }, layer: "below" });
  addAnnotation(fig, { x: 101, y: 101, text: "Higher risk on both", showarrow: false, xanchor: "right", yanchor: "top",
    font: { color: WORSE, size: 12 } });
  addAnnotation(fig, { x: -1, y: -1, text: "Lower risk on both", showarrow: false, xanchor: "left", yanchor: "bottom",
    font: { color: BETTER, size: 12 } });
  addVline(fig, 50, { color: MUTED, width: 1, dash: "dot" });
  addHline(fig, 50, { color: MUTED, width: 1, dash: "dot" });
  updateXaxes(fig, { title: { text: `${px.label} risk →` }, range: [-3, 103] });
  updateYaxes(fig, { title: { text: `${py.label} risk →` }, range: [-3, 103] });
  return base(fig, 470, true);
}

// Stacked bars: number of countries in each tier, by region (riskiest share last)
export function tierDistribution(df) {
  const { SURFACE, TIER_ORDER, TIER_COLORS } = K();
  const d = asRows(df).filter((r) => !na(r.tier) && !na(r.region));
  const counts = new Map([...new Set(d.map((r) => r.region))].sort().map((reg) => [reg, Object.fromEntries(TIER_ORDER.map((t) => [t, 0]))]));
  for (const r of d) if (r.tier in counts.get(r.region)) counts.get(r.region)[r.tier] += 1;
  const share = [...counts].map(([region, c]) => ({ region, c,
    share: (c.High + c.Severe) / TIER_ORDER.reduce((s, t) => s + c[t], 0) }));
  const order = sortBy(share, "share");
  const labels = order.map((o) => regionShort(o.region));
  const fig = figure(...TIER_ORDER.map((tier) => trace("bar", {
    y: labels, x: order.map((o) => o.c[tier]), name: tier, orientation: "h",
    marker: { color: TIER_COLORS[tier], line: { color: SURFACE, width: 2 } },
    hovertemplate: "%{y}<br>" + tier + ": %{x} countries<extra></extra>",
  })));
  updateLayout(fig, { barmode: "stack", bargap: 0.35 });
  updateXaxes(fig, { title: { text: "Countries" } });
  updateYaxes(fig, { title: {}, automargin: true });
  return base(fig, 470, true);
}

// Largest falls and rises in a WGI score (rows: iso3, name, start, end, change)
export function movers(df, n = 8) {
  const { SURFACE, WORSE, BETTER, MUTED } = K();
  const rows = asRows(df);
  const d = sortBy(dedupe([...nsmallest(rows, n, "change"), ...nlargest(rows, n, "change")], "name"), "change");
  const fig = figure(trace("bar", {
    x: d.map((r) => r.change), y: d.map((r) => r.name), orientation: "h",
    marker: { color: d.map((r) => (r.change < 0 ? WORSE : BETTER)), line: { color: SURFACE, width: 1 } },
    customdata: d.map((r) => [npRound(r.start, 1), npRound(r.end, 1), r.iso3]),
    text: d.map((r) => signed(r.change)), textposition: "outside", cliponaxis: false,
    hovertemplate: "<b>%{y}</b><br>Change: %{x:+.1f} points<br>%{customdata[0]} → %{customdata[1]}"
      + "<br><i>Click to open the profile</i><extra></extra>",
  }));
  addVline(fig, 0, { color: MUTED, width: 1 });
  updateXaxes(fig, { title: { text: "Change in score (points)" } });
  updateYaxes(fig, { title: {}, automargin: true });
  return valueRoom(labelRoom(base(fig, Math.max(320, 26 * d.length + 80)), d.map((r) => r.name)), d.map((r) => r.change));
}

// ---- Country profile ---------------------------------------------------------------------------------------------
const reversedPillars = () => [...config().pillars].reverse();

// row, regionalMedian: {pillar key: score}
export function pillarBars(row, regionalMedian) {
  const ps = reversedPillars();
  const labels = ps.map((p) => p.short);
  const vals = ps.map((p) => val(row[p.key]));
  const fig = figure(
    trace("bar", {
      x: vals, y: labels, orientation: "h", name: "Country", showlegend: false,
      marker: { color: ps.map((p) => config().PILLAR_COLORS[p.key]) },
      text: vals.map((v) => (na(v) ? "—" : fixed(v, 0))), textposition: "outside", cliponaxis: false,
      hovertemplate: "%{y}: %{x:.0f}<extra></extra>", width: 0.55,
    }),
    trace("scatter", {
      x: ps.map((p) => val(regionalMedian[p.key])), y: labels, mode: "markers", name: "Regional median",
      marker: { symbol: "line-ns-open", size: 26, color: "#ffffff", line: { width: 2.5 } },
      hovertemplate: "Regional median: %{x:.0f}<extra></extra>",
    }),
  );
  updateXaxes(fig, { range: [0, 108], title: { text: "Risk score (0–100)" } });
  updateYaxes(fig, { title: {}, automargin: true });
  return base(fig, 300, true);
}

// The years something changed for one country: a new tier, armed conflict (25 battle deaths) or war (1,000) starting,
// or armed conflict ending. Map<year, labels[]>
export function historyMarks(hist) {
  const order = K().TIER_ORDER;
  const marks = new Map();
  const add = (y, m) => { if (!marks.has(y)) marks.set(y, []); marks.get(y).push(m); };
  let prev = null;
  for (const r of sortBy(asRows(hist), "year")) {
    if (prev) {
      if (typeof r.tier === "string" && typeof prev.tier === "string" && r.tier !== prev.tier)
        add(Math.trunc(r.year), `${order.indexOf(r.tier) > order.indexOf(prev.tier) ? "▲" : "▼"} ${r.tier}`);
      const now = r.battle_deaths_raw, before = prev.battle_deaths_raw;
      if (!na(now) && !na(before)) {
        if (now >= 1000 && 1000 > before) add(Math.trunc(r.year), "war");
        else if (now >= 25 && 25 > before) add(Math.trunc(r.year), "armed conflict");
        else if (before >= 25 && 25 > now) add(Math.trunc(r.year), "conflict ends");
      }
    }
    prev = r;
  }
  return marks;
}

// historyMarks for the years with a composite score (the ones riskHistory can put on its line), by year
function drawnMarks(hist) {
  const at = new Map(asRows(hist).map((r) => [r.year, r.composite]));
  return new Map([...historyMarks(hist)].sort(([a], [b]) => a - b).filter(([y]) => !na(at.get(y))));
}

// Mark labels laid out for a phone plot (about 200 x 270 px); a label with no free spot is left off
const PHONE_W = 200, PHONE_H = 270, CHAR_W = 7.2, LABEL_H = 20;
function placeMarks(at, found, first, last) {
  const perYear = PHONE_W / Math.max(last - first, 1);
  const boxes = [], placed = [];
  const key = ([y, ls]) => [!ls.includes("war"), !ls.some((m) => m.startsWith("▲")), !ls.includes("armed conflict"), -y];
  const order = [...found].map((kv, i) => [kv, key(kv), i]).sort(([, a, i], [, b, j]) => {
    for (let k = 0; k < a.length; k++) if (a[k] !== b[k]) return a[k] < b[k] ? -1 : 1;
    return i - j;
  }).map(([kv]) => kv);
  for (const [year, labels] of order) {
    const text = labels.join(" · ");
    const w = [...text].length * CHAR_W + 8, x = (year - first) * perYear;
    const anchor = x < w / 2 ? "left" : x > PHONE_W - w / 2 ? "right" : "center";
    const x0 = { left: x, right: x - w, center: x - w / 2 }[anchor];
    const y = (100 - at.get(year)) / 100 * PHONE_H;
    const down = labels.every((m) => m.startsWith("▼") || m === "conflict ends");
    for (const ay of down ? [30, 62, -30, -62] : [-30, -62, 30, 62]) {
      const top = y + ay - LABEL_H / 2;
      const box = [x0, top, x0 + w, top + LABEL_H];
      if (top < -30 || box[3] > PHONE_H) continue;
      if (boxes.every((b) => box[2] <= b[0] || box[0] >= b[2] || box[3] + 4 <= b[1] || box[1] >= b[3] + 4)) {
        boxes.push(box);
        placed.push([year, text, ay, anchor]);
        break;
      }
    }
  }
  return placed;
}

// One country's composite (bold) and pillar scores per year over the tier bands; marks=true: the seismogram view
export function riskHistory(hist, marks = false) {
  const { INK, SURFACE, MUTED, TIERS, PILLARS } = K();
  const rows = asRows(hist);
  const years = rows.map((r) => r.year);
  const fig = figure();
  TIERS.forEach((tier, i) => {
    const upper = i + 1 < TIERS.length ? TIERS[i + 1].lower : 100;
    addShape(fig, { type: "rect", x0: 0, x1: 1, xref: "x domain", y0: tier.lower, y1: upper, yref: "y",
      fillcolor: tier.color, opacity: 0.06, line: { width: 0 }, layer: "below" });
    addAnnotation(fig, { x: 1, xref: "paper", y: (tier.lower + upper) / 2, text: tier.label, showarrow: false,
      xanchor: "left", xshift: 6, font: { color: MUTED, size: 12 } });
  });
  for (const p of PILLARS) {
    fig.data.push(trace("scatter", {
      x: years, y: rows.map((r) => val(r[p.key])), name: p.short, mode: "lines",
      line: { color: config().PILLAR_COLORS[p.key], width: 1.5 }, opacity: 0.85,
      hovertemplate: p.short + " %{x}: %{y:.0f}<extra></extra>", visible: marks ? "legendonly" : true,
    }));
  }
  const found = marks ? drawnMarks(rows) : new Map();
  const at = new Map(rows.map((r) => [r.year, r.composite]));
  const placed = found.size ? placeMarks(at, found, Math.min(...years), Math.max(...years)) : [];
  for (const [year, text, ay, anchor] of placed) {
    addAnnotation(fig, { x: year, y: at.get(year), text, showarrow: true, arrowhead: 0, arrowcolor: INK.faint,
      arrowwidth: 1, ax: 0, ay, xanchor: anchor, font: { color: INK.soft, size: 12 }, bgcolor: "rgba(0,0,0,0.7)" });
  }
  fig.data.push(trace("scatter", {
    x: years, y: rows.map((r) => val(r.composite)), name: "Composite", mode: "lines", line: { color: "#ffffff", width: 3 },
    showlegend: !marks,
    customdata: rows.map((r) => [r.tier ?? "—", Math.trunc(r.rank ?? 0), found.has(r.year) ? "<br>" + found.get(r.year).join(" · ") : ""]),
    hovertemplate: "<b>Composite %{x}: %{y:.0f}</b> · %{customdata[0]} · rank %{customdata[1]}%{customdata[2]}<extra></extra>",
  }));
  if (found.size) {
    fig.data.push(trace("scatter", {
      x: [...found.keys()], y: [...found.keys()].map((y) => at.get(y)), mode: "markers", showlegend: false,
      hoverinfo: "skip", cliponaxis: false, marker: { size: 7, color: INK.strong, line: { color: SURFACE, width: 1.5 } },
    }));
    updateXaxes(fig, { range: [Math.min(...years), Math.max(...years)] });
  }
  updateYaxes(fig, { range: [0, 100], title: { text: "Risk score (0–100)" } });
  updateXaxes(fig, { dtick: 2, tickformat: "d", tickangle: 0 });
  updateLayout(fig, { hovermode: "x unified" });
  return updateLayout(base(fig, 400, true), {
    margin: { r: 72 },
    legend: { x: -0.001, xanchor: "left", y: -0.1, yanchor: "top", itemwidth: 30, entrywidth: 70, font: { size: 11 } },
  });
}

// What riskHistory(hist, true) shows, in words (for a screen reader, beside the chart)
export function historySummary(countryHist) {
  const scored = sortBy(asRows(countryHist).filter((r) => !na(r.composite)), "year");
  if (!scored.length) return "No composite score in any year.";
  const first = scored[0], latest = scored[scored.length - 1];
  const point = (r) => (typeof r.tier === "string" ? `${fixed(r.composite, 0)} (${r.tier})` : fixed(r.composite, 0));
  const words = { war: "war began", "armed conflict": "armed conflict began", "conflict ends": "armed conflict ended" };
  const say = (m) => (m[0] === "▲" || m[0] === "▼" ? (m[0] === "▲" ? "rose to " : "fell to ") + m.slice(2) : words[m] ?? m);
  let text = `Composite risk score ${Math.trunc(first.year)}: ${point(first)}.`;
  if (latest.year !== first.year) text += ` ${Math.trunc(latest.year)}: ${point(latest)}.`;
  const found = drawnMarks(countryHist);
  text += found.size
    ? " Marked years: " + [...found].map(([y, ms]) => `${y} ${ms.map(say).join(" and ")}`).join("; ") + "."
    : " No tier changes or conflict events marked.";
  return text;
}

const dayOfYear = (date) => {
  const [y, m, d] = String(date).slice(0, 10).split("-").map(Number);
  return { year: y, day: (Date.UTC(y, m - 1, d) - Date.UTC(y, 0, 1)) / 86400000 + 1 };
};

// A country's risk over time with the year before the event shaded and the event marked (eventDate "YYYY-MM-DD")
export function caseHistory(hist, eventDate, label) {
  const { FONT } = K();
  const fig = riskHistory(hist);
  const when = dayOfYear(eventDate);
  const x = when.year + (when.day - 1) / 365;
  addShape(fig, { type: "rect", x0: when.year - 1.5, x1: when.year - 0.5, xref: "x", y0: 0, y1: 1, yref: "y domain",
    fillcolor: "#fd8078", opacity: 0.08, line: { width: 0 }, layer: "below" });
  addVline(fig, x, { color: "#fd8078", dash: "dash", width: 1.5 });
  return addAnnotation(fig, { x, y: 100, yref: "y", text: label, showarrow: false, xanchor: "left", yanchor: "top",
    font: { color: "#fd8078", ...FONT }, bgcolor: "rgba(0,0,0,0.6)" });
}

// Pillar scores in the what-if scenario (bars), with today's as a white tick
export function whatifPillars(baseRow, scenario) {
  const ps = reversedPillars();
  const labels = ps.map((p) => p.short);
  const before = ps.map((p) => val(baseRow[p.key])), after = ps.map((p) => val(scenario[p.key]));
  const fig = figure(
    trace("bar", {
      x: after, y: labels, orientation: "h", name: "Scenario", showlegend: false, width: 0.55,
      marker: { color: ps.map((p) => config().PILLAR_COLORS[p.key]) },
      text: after.map((a, i) => {
        const b = before[i];
        return na(a) ? "—" : fixed(a, 0) + (na(b) || pyRound(a - b) === 0 ? "" : ` (${fixed(a - b, 0, { sign: true })})`);
      }),
      textposition: "outside", cliponaxis: false, hovertemplate: "%{y} in scenario: %{x:.0f}<extra></extra>",
    }),
    trace("scatter", {
      x: before, y: labels, mode: "markers", name: "Today",
      marker: { symbol: "line-ns-open", size: 26, color: "#ffffff", line: { width: 2.5 } },
      hovertemplate: "%{y} today: %{x:.0f}<extra></extra>",
    }),
  );
  updateXaxes(fig, { range: [0, 112], title: { text: "Risk score (0–100)" } });
  updateYaxes(fig, { title: {}, automargin: true });
  return base(fig, 320, true);
}

// ---- Compare -------------------------------------------------------------------------------------------------------
// scores: {iso3: {pillar key: score}} (or a Map) in the order to draw; names: {iso3: name}
export function radar(scores, names) {
  const { GRID, MUTED, PILLARS } = K();
  const labels = PILLARS.map((p) => p.short);
  const fig = figure();
  [...(scores instanceof Map ? scores : Object.entries(scores))].forEach(([iso3, row], i) => {
    const vals = PILLARS.map((p) => (na(row[p.key]) ? 0 : row[p.key]));
    const name = names[iso3] ?? iso3;
    fig.data.push(trace("scatterpolar", {
      r: [...vals, vals[0]], theta: [...labels, labels[0]], name, mode: "lines+markers",
      line: { color: config().COUNTRY_COLORS[i], width: 2 }, marker: { size: 8 },
      hovertemplate: "%{theta}: %{r:.0f}<extra>" + name + "</extra>",
    }));
  });
  updateLayout(fig, { polar: {
    radialaxis: { range: [0, 100], tickvals: [20, 40, 60, 80], gridcolor: GRID, tickfont: { color: MUTED } },
    angularaxis: { gridcolor: GRID, tickfont: { color: MUTED } }, bgcolor: "rgba(0,0,0,0)" } });
  base(fig, 440, true);
  return updateLayout(fig, { margin: { l: 84, r: 84, t: 48, b: 24 } });
}

// charts._country: one country's {year, value} rows, by year
const countrySeries = (rows, iso3) => (rows ? sortBy(asRows(rows).filter((r) => r.iso3 === iso3), "year") : []);

// One line per country; series: {key: rows of {iso3, year, value}}; with projectedFrom, later years are dashed and shaded
export function compareLines(series, key, iso3s, names, title, startYear = null, endYear = null, projectedFrom = null) {
  const { c, MUTED, FONT } = K();
  const fig = figure();
  iso3s.forEach((iso3, i) => {
    let s = countrySeries(series[key], iso3);
    if (startYear) s = s.filter((r) => r.year >= startYear);
    if (endYear) s = s.filter((r) => r.year <= endYear);
    const name = names[iso3] ?? iso3;
    const line = { color: c.COUNTRY_COLORS[i], width: 2 };
    const shown = projectedFrom === null ? s : s.filter((r) => r.year <= projectedFrom - 1);
    fig.data.push(trace("scatter", { x: shown.map((r) => r.year), y: shown.map((r) => val(r.value)), mode: "lines", name,
      legendgroup: iso3, line, hovertemplate: name + "<br>%{x}: %{y:.1f}<extra></extra>" }));
    if (projectedFrom !== null) {
      const ahead = s.filter((r) => r.year >= projectedFrom - 1);
      fig.data.push(trace("scatter", { x: ahead.map((r) => r.year), y: ahead.map((r) => val(r.value)), mode: "lines", name,
        legendgroup: iso3, showlegend: false, line: { ...line, dash: "dash" },
        hovertemplate: name + " (projection)<br>%{x}: %{y:.1f}<extra></extra>" }));
    }
  });
  if (projectedFrom !== null) {
    const ends = fig.data.filter((t) => t.x.length).map((t) => Math.max(...t.x));
    const last = ends.length ? Math.max(...ends) : projectedFrom;
    addShape(fig, { type: "rect", x0: projectedFrom - 0.5, x1: Math.max(last, projectedFrom) + 0.5, xref: "x", y0: 0, y1: 1,
      yref: "y domain", fillcolor: c.FORECAST_GREY, opacity: 0.12, line: { width: 0 } });
    addAnnotation(fig, { text: "IMF estimates & projections", x: projectedFrom - 0.5, xanchor: "left", xref: "x", y: 1,
      yanchor: "top", yref: "y domain", showarrow: false, font: { color: MUTED, ...FONT } });
  }
  updateYaxes(fig, { title: { text: title }, rangemode: "tozero" });
  updateLayout(fig, { hovermode: "x unified" });
  return base(fig, 400, true);
}

// ---- Briefing pages ------------------------------------------------------------------------------------------------
// Largest rises (red) and falls (blue) in the composite vs last year; rows: iso3, name, delta_1y, prev_composite,
// composite and optionally thin (hatched bar)
export function changeBars(df, n = 10) {
  const { SURFACE, WORSE, BETTER, MUTED } = K();
  const valid = asRows(df).filter((r) => !na(r.delta_1y));
  const d = sortBy(dedupe([...nsmallest(valid, n, "delta_1y"), ...nlargest(valid, n, "delta_1y")], "iso3"), "delta_1y");
  const thin = d.map((r) => !!r.thin);
  const fig = figure(trace("bar", {
    x: d.map((r) => r.delta_1y), y: d.map((r) => r.name), orientation: "h",
    marker: { color: d.map((r) => (r.delta_1y > 0 ? WORSE : BETTER)), line: { color: SURFACE, width: 1 },
      pattern: { shape: thin.map((t) => (t ? "/" : "")), fgcolor: SURFACE } },
    text: d.map((r) => signed(r.delta_1y)), textposition: "outside", cliponaxis: false,
    customdata: d.map((r, i) => [npRound(r.prev_composite, 0), npRound(r.composite, 0),
      thin[i] ? "<br>Limited data: under 75% of the indicators, or a pillar missing" : "", r.iso3]),
    hovertemplate: "<b>%{y}</b><br>%{customdata[0]} → %{customdata[1]} (%{x:+.1f})%{customdata[2]}"
      + "<br><i>Click to open the profile</i><extra></extra>",
  }));
  addVline(fig, 0, { color: MUTED, width: 1 });
  updateXaxes(fig, { title: { text: "Points vs last year" } });
  updateYaxes(fig, { title: {}, automargin: true });
  return valueRoom(labelRoom(base(fig, Math.max(320, 24 * d.length + 90)), d.map((r) => r.name)), d.map((r) => r.delta_1y));
}

// Number of countries in each tier, per year (stacked); rows: year, tier
export function tierMix(hist) {
  const { SURFACE, TIER_ORDER, TIER_COLORS } = K();
  const d = asRows(hist).filter((r) => !na(r.tier));
  const years = [...new Set(d.map((r) => r.year))].sort((a, b) => a - b);
  const count = (y, t) => d.filter((r) => r.year === y && r.tier === t).length;
  const fig = figure(...TIER_ORDER.map((tier) => trace("bar", {
    x: years, y: years.map((y) => count(y, tier)), name: tier,
    marker: { color: TIER_COLORS[tier], line: { color: SURFACE, width: 1 } },
    hovertemplate: "%{x} · " + tier + ": %{y} countries<extra></extra>",
  })));
  updateLayout(fig, { barmode: "stack", bargap: 0.25 });
  updateXaxes(fig, { dtick: 2, tickformat: "d", tickangle: 0 });
  updateYaxes(fig, { title: { text: "Countries" } });
  return base(fig, 380, true);
}

// A single series per year (e.g. battle deaths worldwide)
export function yearlyBars(years, values, title, color, hover) {
  const fig = figure(trace("bar", { x: [...years], y: [...values], marker: { color, line: { color: K().SURFACE, width: 1 } },
    hovertemplate: "%{x}: %{y:,.0f} " + hover + "<extra></extra>" }));
  updateXaxes(fig, { tickformat: "d" });
  updateYaxes(fig, { title: { text: title } });
  return base(fig, 340);
}

const twoLines = (labels) => labels.map((l) => l.replace(" ", "<br>"));

// Share of countries at peace where armed conflict started the next year, by fifth of the risk score;
// byFifth: five rows of {mean, sum, size}
export function onsetFifths(byFifth, baseRate, color) {
  const { SURFACE, MUTED, FONT } = K();
  const rows = asRows(byFifth);
  const rate = rows.map((r) => (na(r.mean) ? 0 : r.mean) * 100);
  const fig = figure(trace("bar", {
    x: FIFTHS, y: rate, marker: { color, opacity: [0.35, 0.5, 0.65, 0.82, 1.0], line: { color: SURFACE, width: 1 } },
    text: rate.map((r) => `${fixed(r, 1)}%`), textposition: "outside", textfont: { color: "#c3c2b7", ...FONT },
    customdata: rows.map((r) => [Math.trunc(na(r.sum) ? 0 : r.sum), Math.trunc(na(r.size) ? 0 : r.size)]),
    hovertemplate: "%{x}: conflict started in %{customdata[0]} of %{customdata[1]} cases (%{y:.1f}%)<extra></extra>",
  }));
  addHline(fig, baseRate * 100, { color: MUTED, dash: "dash", width: 1 });
  addAnnotation(fig, { text: `average ${fixed(baseRate * 100, 1)}%`, x: 0, xanchor: "left", xref: "x domain", y: baseRate * 100,
    yanchor: "bottom", yref: "y", showarrow: false, font: { color: MUTED, ...FONT } });
  updateYaxes(fig, { title: { text: "Conflict started the next year (%)" }, rangemode: "tozero" });
  updateXaxes(fig, { title: { text: "Risk score the year before" }, tickangle: 0, tickvals: FIFTHS, ticktext: twoLines(FIFTHS) });
  return base(fig, 360);
}

// Stress test: number of countries in each tier today and under stress (before, after: tier labels)
export function tierShift(before, after) {
  const { SURFACE, MUTED, FONT, TIER_ORDER, TIER_COLORS } = K();
  const counts = (tiers) => TIER_ORDER.map((t) => tiers.filter((x) => x === t).length);
  const today = counts([...before]), stressed = counts([...after]);
  const fig = figure(
    trace("bar", { name: "Today", x: TIER_ORDER, y: today, marker: { color: "#4a4a47", line: { color: SURFACE, width: 1 } },
      text: today, textposition: "outside", textfont: { color: MUTED, ...FONT },
      hovertemplate: "%{x} today: %{y} countries<extra></extra>" }),
    trace("bar", { name: "Under stress", x: TIER_ORDER, y: stressed,
      marker: { color: TIER_ORDER.map((t) => TIER_COLORS[t]), line: { color: SURFACE, width: 1 } },
      text: stressed, textposition: "outside", textfont: { color: "#c3c2b7", ...FONT },
      hovertemplate: "%{x} under stress: %{y} countries<extra></extra>" }),
  );
  updateLayout(fig, { barmode: "group", bargap: 0.3, bargroupgap: 0.08 });
  updateYaxes(fig, { title: { text: "Countries" }, rangemode: "tozero" });
  return base(fig, 320, true);
}

// Horizontal bars, largest on top; clickable when the rows have iso3. Rows without a value are left out.
export function rankedBars(df, value, label, color, hover, format = ",.0f") {
  const { SURFACE } = K();
  const d = sortBy(asRows(df).filter((r) => !na(r[value])), value);
  const fig = figure(trace("bar", {
    x: d.map((r) => r[value]), y: d.map((r) => r[label]), orientation: "h", marker: { color, line: { color: SURFACE, width: 1 } },
    text: d.map((r) => fmt(r[value], format)), textposition: "outside", cliponaxis: false,
    customdata: d.length && "iso3" in d[0] ? d.map((r) => [r.iso3]) : undefined,
    hovertemplate: "<b>%{y}</b><br>%{x:" + format + "} " + hover + "<extra></extra>",
  }));
  updateYaxes(fig, { title: {}, automargin: true });
  updateXaxes(fig, { showticklabels: false });
  return valueRoom(labelRoom(base(fig, Math.max(300, 28 * d.length + 60)), d.map((r) => r[label])), d.map((r) => r[value]));
}

// np.histogram(a, bins) with equal-width bins: counts and edges, binned exactly as numpy does
function histogram(a, bins) {
  let first = a.length ? Math.min(...a) : 0, last = a.length ? Math.max(...a) : 1;
  if (first === last) { first -= 0.5; last += 0.5; }
  const step = (last - first) / bins;
  const edges = Array.from({ length: bins + 1 }, (_, i) => i * step + first);
  edges[bins] = last;
  const counts = new Array(bins).fill(0);
  const denom = last - first;
  for (const x of a) {
    let i = Math.trunc(((x - first) / denom) * bins);
    if (i === bins) i -= 1;
    if (x < edges[i]) i -= 1;
    if (x >= edges[i + 1] && i !== bins - 1) i += 1;
    counts[i] += 1;
  }
  return { counts, edges };
}

// Histogram of one indicator across countries, with the median marked
export function distribution(values, title, color, log = false) {
  const { SURFACE } = K();
  const v = [...values].filter((x) => typeof x === "number" && !Number.isNaN(x));
  const x = log ? v.map((a) => Math.log10(Math.max(a, 0) + 1)) : v;
  const { counts, edges } = histogram(x, 40);
  const fig = figure(trace("bar", {
    x: counts.map((_, i) => (edges[i] + edges[i + 1]) / 2), y: counts, width: counts.map((_, i) => edges[i + 1] - edges[i]),
    marker: { color, line: { color: SURFACE, width: 1 } }, hovertemplate: "%{y} countries<extra></extra>",
  }));
  if (v.length) {
    const m = median(v);
    const at = log ? Math.log10(Math.max(m, 0) + 1) : m;
    addVline(fig, at, { color: "#ffffff", width: 1.5, dash: "dot" });
    addAnnotation(fig, { text: `median ${fixed(m, 1, { group: true })}`, font: { color: "#ffffff" }, x: at, xanchor: "left",
      xref: "x", y: 1, yanchor: "top", yref: "y domain", showarrow: false });
  }
  updateXaxes(fig, { title: { text: title + (log ? " (log scale: log10(1 + x))" : "") } });
  const peak = Math.max(...counts);
  const step = [1, 2, 5, 10, 20, 50, 100].find((s) => peak <= 4 * s);
  updateYaxes(fig, { title: { text: "Countries" }, dtick: step, range: [0, step * Math.max(1, Math.ceil(peak / step))] });
  return base(fig, 320);
}

// numpy's default_rng(seed).random(): SeedSequence + PCG64 (XSL-RR), so the peer strip's jitter matches Python's
function defaultRng(seed) {
  const M = 0xffffffffffffffffffffffffffffffffn;
  const imul = (a, b) => Math.imul(a, b) >>> 0;
  let hashA = 0x43b0d7e5;
  const hashmix = (value) => {
    value = (value ^ hashA) >>> 0;
    hashA = imul(hashA, 0x931e8875);
    value = imul(value, hashA);
    return (value ^ (value >>> 16)) >>> 0;
  };
  const mix = (x, y) => {
    const r = (imul(0xca01f9dd, x) - imul(0x4973f715, y)) >>> 0;
    return (r ^ (r >>> 16)) >>> 0;
  };
  const pool = [0, 1, 2, 3].map((i) => hashmix(i === 0 ? seed >>> 0 : 0));  // entropy: one 32-bit word
  for (let src = 0; src < 4; src++) for (let dst = 0; dst < 4; dst++) if (src !== dst) pool[dst] = mix(pool[dst], hashmix(pool[src]));
  let hashB = 0x8b51f9dd;
  const words = Array.from({ length: 8 }, (_, i) => {
    let v = (pool[i % 4] ^ hashB) >>> 0;
    hashB = imul(hashB, 0x58f38ded);
    v = imul(v, hashB);
    return BigInt((v ^ (v >>> 16)) >>> 0);
  });
  const u64 = (i) => words[2 * i] | (words[2 * i + 1] << 32n);  // little-endian pairs
  const MULT = (2549297995355413924n << 64n) + 4865540595714422341n;
  const inc = ((((u64(2) << 64n) | u64(3)) << 1n) | 1n) & M;
  let state = 0n;
  const step = () => { state = (state * MULT + inc) & M; };
  step();
  state = (state + ((u64(0) << 64n) | u64(1))) & M;
  step();
  const next64 = () => {
    step();
    const rot = state >> 122n;
    const x = ((state >> 64n) ^ state) & 0xffffffffffffffffn;
    return ((x >> rot) | (x << ((64n - rot) & 63n))) & 0xffffffffffffffffn;
  };
  return {
    random: () => Number(next64() >> 11n) * (1.0 / 9007199254740992.0),
    uniform(low, high, n) { const range = high - low; return Array.from({ length: n }, () => low + range * this.random()); },
  };
}

// Each row a score; grey dots = peers, white tick = peer median, big dot = this country
export function peerStrip(country, peers, name) {
  const { SURFACE, MUTED, TIER_COLORS, PILLARS } = K();
  const rows = [["composite", "Composite"], ...PILLARS.map((p) => [p.key, p.short])];
  const peerRows = asRows(peers);
  const rng = defaultRng(7);
  const fig = figure();
  rows.forEach(([key, label], i) => {
    const vals = peerRows.filter((r) => !na(r.name) && !na(r[key]));
    const jitter = rng.uniform(-0.18, 0.18, vals.length);
    fig.data.push(trace("scatter", {
      x: vals.map((r) => r[key]), y: jitter.map((j) => i + j), mode: "markers", showlegend: i === 0, name: "Peers",
      marker: { size: 7, color: "#5a5955", line: { color: SURFACE, width: 1 } }, text: vals.map((r) => r.name),
      hovertemplate: "%{text}: %{x:.0f}<extra>" + label + "</extra>",
    }));
    if (vals.length) {
      fig.data.push(trace("scatter", { x: [median(vals.map((r) => r[key]))], y: [i], mode: "markers", showlegend: i === 0,
        name: "Peer median", marker: { symbol: "line-ns-open", size: 24, color: "#ffffff", line: { width: 2.5 } },
        hovertemplate: "Peer median: %{x:.0f}<extra>" + label + "</extra>" }));
    }
    const value = country[key];
    if (!na(value)) {
      const color = key === "composite" ? TIER_COLORS[country.tier] ?? MUTED : config().PILLAR_COLORS[key];
      fig.data.push(trace("scatter", { x: [value], y: [i], mode: "markers+text", showlegend: false, text: [fixed(value, 0)],
        textposition: "top center", textfont: { color: "#ffffff" }, marker: { size: 16, color, line: { color: "#ffffff", width: 2 } },
        hovertemplate: name + ": %{x:.0f}<extra>" + label + "</extra>" }));
    }
  });
  updateYaxes(fig, { tickvals: rows.map((_, i) => i), ticktext: rows.map(([, l]) => l), autorange: "reversed", showgrid: false });
  updateXaxes(fig, { range: [-2, 102], title: { text: "Risk score (0–100)" } });
  return base(fig, 360, true);
}
