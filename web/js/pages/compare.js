// Compare up to six countries side by side (app_pages/compare.py). ?c=NGA,KEN holds the comparison.
import * as ui from "../lib/ui.js";
import { h, clear } from "../lib/dom.js";
import { compareLines, plot, radar } from "../lib/charts.js";
import { countryTable, flagUrl } from "../lib/table.js";
import { asMap, asRows } from "../lib/scoring.js";
import * as follow from "../lib/follow.js";
import * as g8 from "../charts/group8.js";

export const title = "Compare countries";
export const required = ["data/group8/series/NGA.json"];

const SAVED = "sg-compare"; // sessionStorage: the list built here and with the profile's "Add to compare"
const LAST = "sg-country"; // sessionStorage (app.js): the country opened last in this visit
const ECON = { gdp_growth: "Real GDP growth (%)", inflation: "Inflation (%)", gov_debt: "Public debt (% of GDP)",
  current_account: "Current account (% of GDP)" };
const store = (fn) => { try { return fn(); } catch { return null; } }; // storage blocked: nothing kept
// st.header(help=...): the app hides header help marks (prm/ui.py GLOBAL_CSS), so the help text is not drawn
const h2 = (text) => h("h2", null, text);

export async function render(main, ctx) {
  await ui.loadCss("/css/group8.css");
  const c = ctx.core.config, year = ctx.core.meta.year, max = c.MAX_COMPARE;
  const countries = asRows(ctx.core.countries);
  const names = Object.fromEntries(countries.map((r) => [r.iso3, r.name]));
  const options = countries.map((r) => r.iso3).sort((a, b) => (names[a] < names[b] ? -1 : names[a] > names[b] ? 1 : 0));
  const valid = new Set(options);
  const current = [store(() => sessionStorage.getItem(LAST)), ctx.params.get("country"), follow.following()[0], "NGA"]
    .map((x) => (x ? String(x).toUpperCase() : x)).find((x) => x && valid.has(x));
  const saved = store(() => JSON.parse(sessionStorage.getItem(SAVED) ?? "[]"));
  let picked = g8.seedPicks({ c: ctx.params.get("c"), saved: Array.isArray(saved) ? saved : [], current }, options, max);

  const body = h("div", { class: "sg-page g8-body" });
  let cleanups = [];
  const picker = ui.multiselect({ label: "Countries", options, value: picked, format: (i) => names[i] ?? i, max,
    placeholder: "Choose countries", onChange: (v) => { picked = v; draw(); } });
  picker.classList.add("g8-picker");
  main.append(...[ui.weightsNote(ctx), ui.hero(title), picker, body].filter(Boolean));

  const scores = ctx.scores(), hist = ctx.history(), rows = asMap(ctx.table());
  const seriesOf = (iso3s) => Promise.all(iso3s.map((i) => ctx.fetchJSON(`/data/group8/series/${i}.json`)))
    .then((files) => g8.seriesFrom(Object.fromEntries(iso3s.map((i, k) => [i, files[k]]))));
  const chart = (el, fig) => cleanups.push(plot(el, fig));

  function draw(focusAt = null) {
    cleanups.forEach((f) => f());
    cleanups = [];
    store(() => sessionStorage.setItem(SAVED, JSON.stringify(picked)));
    body.style.minHeight = `${body.offsetHeight}px`; // keep the scroll position while the charts come back
    clear(body);
    if (!picked.length) {
      ctx.setParam("c", null);
      body.append(ui.emptyState("Choose at least one country."));
      body.style.minHeight = "";
      return;
    }
    ctx.setParam("c", picked.join(",")); // the address holds a link to this exact comparison

    const like = g8.similarTo(scores, picked, max);
    if (like.length) {
      const buttons = like.map((iso3, k) => ui.button(`Add ${names[iso3]}`, { type: "tertiary",
        help: "A country with a close risk profile across the four pillars",
        onClick: () => {
          if (picked.includes(iso3) || picked.length >= max) return;
          picked = [...picked, iso3];
          picker.value = picked;
          draw(k); // the button used disappears: focus moves to the next suggestion
        } }));
      body.append(h("div", { class: "g8-similar" }, ui.caption(`Similar to ${names[picked[0]]}:`), buttons));
      if (focusAt !== null) (buttons[Math.min(focusAt, buttons.length - 1)]).focus();
    } else if (focusAt !== null) picker.querySelector("input").focus(); // no suggestion left: back to the picker

    // --- Scorecards
    body.append(h("div", { class: "sg-row g8-cards" }, picked.map((iso3, i) => {
      const r = rows.get(iso3) ?? { iso3, flags: 0 };
      const s = g8.scorecard(r, year);
      const url = flagUrl(r.iso2, c.NO_FLAG);
      const rank = s.rank === null ? "—" : h("span", { title: "1 is the highest risk" }, `#${s.rank}`);
      const trend = s.said === null ? `${s.trend} in a year`
        : h("span", { title: s.said }, h("span", { "aria-hidden": "true", style: "white-space:nowrap" }, `${s.trend} in a year`), ui.sr(s.said));
      return h("div", { class: "sg-card" },
        h("div", null, h("span", { class: "sg-swatch", style: `--c:${c.COUNTRY_COLORS[i]}` }),
          url ? h("img", { class: "sg-flag-inline", src: url, alt: "", style: "height:1em" }) : null, h("span", { class: "g8-card-name" }, names[iso3])),
        h("div", { class: "sg-cmp-score" }, h("span", { class: "sg-cs-num" }, s.score), ui.tierBadge(s.tier)),
        h("div", { class: "sg-cmp-meta" }, "Rank ", rank, ` · ${s.flags} red flag${s.flags === 1 ? "" : "s"} · `, trend));
    })));

    // --- Risk index over time
    const composite = h("div");
    body.append(h2("Risk index over time"), composite);
    chart(composite, compareLines(g8.compositeSeries(hist), "composite", picked, names, "Composite risk score (0–100)"));

    // --- Pillar profile and governance over time
    const radarBox = h("div"), wgiBox = h("div");
    let dim = g8.recall("wgi", "pv");
    const series = seriesOf(picked);
    const drawSeries = (box, fn) => {
      const mine = cleanups;
      series.then((s) => {
        if (mine !== cleanups || !box.isConnected) return;
        box.dispose?.(); // a new pick in the select: the old chart goes first
        clear(box);
        box.dispose = plot(box, fn(s));
        cleanups.push(box.dispose);
      })
        .catch((err) => { console.warn("section failed: the series", err); clear(box).append(ui.emptyState("These figures can't be shown right now. The rest of the page is unaffected.")); });
    };
    const wgiLines = () => drawSeries(wgiBox, (s) => compareLines(s, `wgi_${dim}`, picked, names, "WGI score (0–100, higher = better)"));
    const dims = ui.select({ label: "WGI dimension", options: Object.keys(c.WGI_DIMENSIONS), value: dim, format: (d) => c.WGI_DIMENSIONS[d],
      onChange: (d) => { dim = d; g8.remember("wgi", d); wgiLines(); } });
    body.append(h("div", { class: "sg-pair" }, h("div", { class: "sg-row" },
      h("div", { class: "g8-wide-1" }, h2("Pillar profile"), radarBox),
      h("div", { class: "g8-wide-12 sg-stack" }, h2("Governance over time"), dims, wgiBox))));
    chart(radarBox, radar(new Map(picked.map((i) => [i, rows.get(i) ?? {}])), names));
    wgiLines();

    // --- Indicator table
    const tableBox = h("div", { class: "g8-pinned" });
    body.append(h2("Indicators"), tableBox);
    countryTable(tableBox, g8.indicatorRows(ctx.core.values, rows, picked, names, c), { key: "Indicator",
      columns: [{ key: "Indicator", label: "Indicator" }, ...picked.map((i) => ({ key: names[i], label: names[i], align: "right" })),
        { key: "Unit", label: "Unit" }] });

    // --- Economy over time
    let econ = g8.recall("econ", "gdp_growth");
    const econBox = h("div");
    const econLines = () => drawSeries(econBox, (s) => compareLines(s, econ, picked, names, ECON[econ], year - 12, year + 5, year));
    body.append(h2("Economic trajectory"),
      ui.select({ label: "Indicator", options: Object.keys(ECON), value: econ, format: (k) => ECON[k],
        onChange: (k) => { econ = k; g8.remember("econ", k); econLines(); } }),
      econBox, ui.cite(["index", "wgi", "imf", "flags"]), ui.footer());
    econLines();
    requestAnimationFrame(() => { body.style.minHeight = ""; });
  }

  draw();
  return () => cleanups.forEach((f) => f());
}
