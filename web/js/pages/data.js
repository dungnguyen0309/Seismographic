// Data downloads: the index, its inputs, red flags, history and the conflict outlook (app_pages/downloads.py).
// CSV and JSON files are written here from the tables the page shows, so they follow the visitor's weights; the
// Excel workbook is built ahead of time with the default weights (files/seismographic.xlsx).
import * as ui from "../lib/ui.js";
import { h, clear } from "../lib/dom.js";
import { na } from "../lib/scoring.js";
import { fixed } from "../lib/format.js";
import { countryTable } from "../lib/table.js";
import { BOM, exportMeta, historyTable, indexTable, npRound, nowIso, toCsv, toJson } from "../group10/export.js";
import { withIcon } from "../group10/icons.js";

export const title = "Data downloads";
export const required = ["data/group10/tables.json", "files/seismographic.xlsx"];

// The table under Preview: kept when the page is drawn again while the visitor stays (a weights change), back to the
// index on a new visit, as Streamlit keeps a page's widgets only while the visitor is on it
let preview = "index";
let here = false;
const label = (name) => { const s = name.replaceAll("_", " "); return s.charAt(0).toUpperCase() + s.slice(1); };

export async function render(main, ctx) {
  if (!here) preview = "index";
  here = true;
  await ui.loadCss("/css/group10.css");
  const year = ctx.core.meta.year;
  main.append(...[ui.weightsNote(ctx), ui.hero(title, "Credit the original publishers when you reuse these tables."),
    h("div", null, ui.pageLink("/sources", "Sources", "verified"))].filter(Boolean));
  const excel = withIcon(ui.download("Download all tables (Excel)", { href: `/files/seismographic.xlsx?v=${encodeURIComponent(ctx.core.meta.version ?? "")}`,
    filename: `seismographic-${year}.xlsx`, type: "primary", icon: null }), "table_view");
  const buttons = h("div", { class: "sg-row sg-row-tight g10-dl-all" }, excel);
  main.append(buttons);

  let file = null;
  try {
    file = await ctx.fetchJSON("/data/group10/tables.json");
  } catch (err) {
    console.warn("section failed: the data tables", err);
  }
  if (file) {
    const tables = {
      index: indexTable(ctx.table(), file.dtypes.index),
      indicators: { ...file.indicators, dtypes: file.dtypes.indicators },
      red_flags: { ...file.red_flags, dtypes: file.dtypes.red_flags },
      history: historyTable(ctx.history(), ctx.core.countries, file.bd_last_year, file.dtypes.history),
      conflict_outlook: { ...file.conflict_outlook, dtypes: file.dtypes.conflict_outlook },
      dictionary: { ...file.dictionary, dtypes: file.dtypes.dictionary },
    };
    const names = Object.keys(file.descriptions);
    buttons.append(withIcon(ui.download("Download all tables (JSON)", { filename: `seismographic-${year}.json`, mime: "application/json", icon: null,
      data: () => toJson(Object.fromEntries(names.map((n) => [n, tables[n]])), exportMeta(file.meta, ctx.weights(), nowIso())) }), "data_object"));
    if (ctx.customLabel()) main.append(ui.caption("The Excel workbook uses the default weights; the CSV and JSON files use yours."));

    main.append(h("h2", null, "Tables"), h("div", { class: "sg-card g10-tables" }, names.map((name) => {
      const t = tables[name];
      let rows = `${fixed(t.rows.length, 0, { group: true })} rows`;
      const at = t.columns.indexOf("composite");
      if (name === "index" && at >= 0) {
        rows += ` (${t.rows.filter((r) => !na(r[at])).length} with a score; the rest have too little data)`;
      }
      return h("div", { class: "g10-table-row" },
        h("div", null, h("p", null, h("b", null, label(name)), ` · ${rows}`), h("p", { class: "g10-muted" }, file.descriptions[name])),
        ui.download("Download CSV", { data: () => `${BOM}${toCsv(t)}`, filename: `seismographic-${name}-${year}.csv`, mime: "text/csv",
          type: "tertiary", icon: "download" }));
    })));

    const box = h("div", { class: "g10-nowrap" });
    const draw = () => {
      const t = tables[preview];
      const d = preview === "conflict_outlook" ? 3 : 1;
      const show = (v, c) => (na(v) ? h("span", { class: "g10-none" }, "None") : t.dtypes[c] === "float" ? String(npRound(v, d)) : String(v));
      countryTable(clear(box), { columns: t.columns, rows: t.rows.slice(0, 300) }, { key: t.columns[0], height: "360px",
        columns: t.columns.map((c) => ({ key: c, label: c, fmtNull: true, fmt: (v) => show(v, c), align: t.dtypes[c] === "str" ? null : "right" })) });
    };
    if (!names.includes(preview)) preview = "index";
    main.append(h("h2", null, "Preview"),
      ui.segmented({ label: "Table", labelHidden: true, options: names, value: preview, format: label, onChange: (v) => { preview = v; draw(); } }), box);
    draw();
  } else {
    main.append(ui.emptyState("The tables can't be shown right now. The Excel workbook above has them all."));
  }

  const base = `${location.origin}/api/v1`;
  main.append(h("h2", null, "JSON API"),
    h("pre", { class: "sg-code g10-code" }, [`${base}/countries`, `${base}/countries?region=South Asia`, `${base}/countries/KEN`, `${base}/dictionary`].join("\n")),
    ui.caption("Read-only, no key needed, default weights. Filter the list with ?region=, ?income= or ?tier=. An unknown country or path gets the site's 404 page."));
  return () => { here = location.pathname === "/data"; };
}
