// The open-data tables as the Data downloads page writes them (prm/export.py): the index and history follow the
// visitor's weights, and every CSV and the JSON file are written as pandas and Python's json write them.
import { asRows, na, toTable } from "../lib/scoring.js";

// Python's repr(float): the shortest digits that read back the same number; exponent below 1e-4 and from 1e16
export function pyRepr(x) {
  if (Number.isNaN(x)) return "nan";
  if (!Number.isFinite(x)) return x > 0 ? "inf" : "-inf";
  if (x === 0) return Object.is(x, -0) ? "-0.0" : "0.0";
  const [mant, e] = x.toExponential().split("e");
  const exp = Number(e), sign = x < 0 ? "-" : "", digits = mant.replace(/[-.]/g, "");
  if (exp < -4 || exp >= 16) {
    const m = digits.length > 1 ? `${digits[0]}.${digits.slice(1)}` : digits;
    return `${sign}${m}e${exp < 0 ? "-" : "+"}${String(Math.abs(exp)).padStart(2, "0")}`;
  }
  if (exp < 0) return `${sign}0.${"0".repeat(-exp - 1)}${digits}`;
  return `${sign}${digits.slice(0, exp + 1).padEnd(exp + 1, "0")}.${digits.slice(exp + 1) || "0"}`;
}

// numpy's round(x, d): scale, round half to even, scale back
const rint = (y) => {
  const f = Math.floor(y), d = y - f;
  return d < 0.5 ? f : d > 0.5 ? f + 1 : f % 2 === 0 ? f : f + 1;
};
export const npRound = (x, d) => (na(x) ? x : rint(x * 10 ** d) / 10 ** d);

// One float as pandas' to_json(double_precision=4) writes it (its ujson encoder: cut to 4 decimals, then its own
// rounding of the last one; trailing zeros dropped)
export function ujson(value, precision = 4) {
  if (na(value) || !Number.isFinite(value)) return "null";
  const neg = value < 0;
  const v = Math.abs(value);
  // shortcut: pandas prints these with C's %.4g (ties may round differently here); no value in the tables comes near
  if (v > 1e16 || (v !== 0 && v < 1e-15)) return pyRepr(Number(value.toPrecision(precision)));
  const pow10 = 10 ** precision;
  let whole = Math.trunc(v);
  const tmp = (v - whole) * pow10;
  let frac = Math.trunc(tmp);
  const diff = tmp - frac;
  if (diff > 0.5 || (diff === 0.5 && (frac === 0 || frac % 2 === 1))) frac += 1;
  if (frac >= pow10) { frac = 0; whole += 1; }
  const tail = frac ? String(frac).padStart(precision, "0").replace(/0+$/, "") : "0";
  return `${neg ? "-" : ""}${whole}.${tail}`;
}

// ---- writers ---------------------------------------------------------------------------------------------------
export const BOM = String.fromCharCode(0xfeff); // a CSV download starts with it, as the app's utf-8-sig files
// table: {columns, rows, dtypes: {column: "float" | "int" | "str"}} (tables.json gives the dtypes of every table)
const quote = (s) => (/[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);
const csvCell = (v, kind) => (na(v) ? "" : kind === "float" ? pyRepr(Number(v)) : kind === "int" ? String(Math.trunc(v)) : quote(String(v)));

// DataFrame.to_csv(index=False) with "\n" line ends (the app ran on Linux); the page adds the byte-order mark
export function toCsv(table) {
  const kinds = table.columns.map((c) => table.dtypes[c]);
  const lines = [table.columns.map((c) => quote(String(c))).join(",")];
  for (const row of table.rows) lines.push(row.map((v, i) => csvCell(v, kinds[i])).join(","));
  return lines.join("\n") + "\n";
}

// json.dumps (default separators, ensure_ascii=False); floats as repr
const dumps = (v, float = false) => (v === null || v === undefined || Number.isNaN(v) ? "null"
  : typeof v === "number" ? (float ? pyRepr(v) : String(v))
    : typeof v === "string" ? JSON.stringify(v)
      : Array.isArray(v) ? `[${v.map((x) => dumps(x, float)).join(", ")}]`
        : `{${Object.entries(v).map(([k, x]) => `${JSON.stringify(k)}: ${dumps(x, float)}`).join(", ")}}`);

const jsonCell = (v, kind) => (na(v) ? "null" : kind === "float" ? pyRepr(Number(ujson(Number(v))))
  : kind === "int" ? String(Math.trunc(v)) : JSON.stringify(String(v)));

function records(table) {
  const kinds = table.columns.map((c) => table.dtypes[c]);
  const keys = table.columns.map((c) => JSON.stringify(String(c)));
  return `[${table.rows.map((r) => `{${r.map((v, i) => `${keys[i]}: ${jsonCell(v, kinds[i])}`).join(", ")}}`).join(", ")}]`;
}

// export.to_json: {"meta": info, <table>: records rounded to 4 decimals, ...}
export function toJson(tables, info) {
  const meta = `{${Object.entries(info).map(([k, v]) => `${JSON.stringify(k)}: ${dumps(v, k === "weights")}`).join(", ")}}`;
  return `{"meta": ${meta}${Object.entries(tables).map(([k, t]) => `, ${JSON.stringify(k)}: ${records(t)}`).join("")}}`;
}

// export.meta for the weights in use (shares of 100); generated: the time of the download
export const exportMeta = (meta, weights, generated) => ({
  title: meta.title, index_year: meta.index_year, data_version: meta.data_version, generated,
  weights: Object.fromEntries(Object.entries(weights).map(([k, v]) => [k, Number(v)])), scale: meta.scale, terms: meta.terms,
});
export const nowIso = () => new Date().toISOString().replace(/\.\d+Z$/, "+00:00");

// ---- the two tables that follow the weights --------------------------------------------------------------------------
const FROM_MASTER = { red_flags: "flags", gdp_per_person: "gdppc" };

// export.index_table from the master table (ctx.table()): one row per economy, by rank, unranked last
export function indexTable(master, dtypes) {
  const columns = Object.keys(dtypes);
  const rows = asRows(master).map((r) => Object.fromEntries(columns.map((c) => [c, c === "change_1y"
    ? (na(r.composite) || na(r.prev_composite) ? null : r.composite - r.prev_composite)
    : r[FROM_MASTER[c] ?? c] ?? null])));
  rows.sort((a, b) => (na(a.rank) ? (na(b.rank) ? 0 : 1) : na(b.rank) ? -1 : a.rank - b.rank)); // stable: ties keep their order
  return { ...toTable(rows, columns), dtypes };
}

// export.history_table: every country-year, by country and year; battle deaths only up to UCDP's last year
export function historyTable(hist, countries, bdLastYear, dtypes) {
  const columns = Object.keys(dtypes);
  const names = new Map(asRows(countries).map((c) => [c.iso3, c.name]));
  const rows = asRows(hist).map((r) => Object.fromEntries(columns.map((c) => [c,
    c === "name" ? names.get(r.iso3) ?? null : c === "battle_deaths" ? (r.year > bdLastYear ? null : r.battle_deaths_raw ?? null) : r[c] ?? null])));
  rows.sort((a, b) => (a.iso3 < b.iso3 ? -1 : a.iso3 > b.iso3 ? 1 : a.year - b.year));
  return { ...toTable(rows, columns), dtypes };
}
