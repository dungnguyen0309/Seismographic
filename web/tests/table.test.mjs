import test from "node:test";
import assert from "node:assert/strict";
import { masterTable, cellText, flagUrl, NO_FLAG_DEFAULT } from "../js/lib/table.js";
import { data, fixture, objects, sameTable } from "./helpers.mjs";

const config = data("config");
const core = { countries: data("countries"), wgiTrend: data("wgi_trend"), config };
// assessment content is not part of the model: the page passes it in
const extra = (m) => ({ assessments: new Map(objects(m).filter((r) => r.assessment).map((r) => [r.iso3, r.analyst_rating])) });

test("masterTable equals data/master.json", () => {
  const m = data("master");
  const t = masterTable(core, data("values"), data("scores"), data("history"), extra(m));
  assert.deepEqual(t.columns, m.columns);
  sameTable(t, m);
});
test("masterTable with custom weights equals the Python fixture", () => {
  const m = fixture("master_w50_20_20_10");
  const t = masterTable(core, data("values"), fixture("scores_w50_20_20_10"), fixture("history_w50_20_20_10"), extra(data("master")));
  assert.deepEqual(t.columns, m.columns);
  sameTable(t, m);
});
test("unscored rows say not ranked with a dash trend", () => {
  const t = masterTable(core, data("values"), data("scores"), data("history"));
  const asm = objects(t).find((r) => r.iso3 === "ASM");
  assert.equal(asm.rank_label, "not ranked");
  assert.equal(asm.trend, "—");
});

test("cellText shows a dash for missing values and never calls fmt on them", () => {
  const col = { fmt: (v) => v.toFixed(0) };
  for (const v of [null, NaN, undefined]) assert.equal(cellText(v, {}, col), "—");
  assert.equal(cellText(0, {}, col), "0");
  assert.equal(cellText(58.4, {}, col), "58");
  assert.equal(cellText(null, {}, {}), "—");
  assert.equal(cellText(12.34, {}, {}), "12.3");
  assert.equal(cellText("x", {}, {}), "x");
});
test("cellText passes missing values and the row to fmt when fmtNull is set", () => {
  const col = { fmtNull: true, fmt: (v, row) => (v == null ? `no score (${row.name})` : String(v)) };
  assert.equal(cellText(null, { name: "Jersey" }, col), "no score (Jersey)");
  assert.equal(cellText(3, {}, col), "3");
});
test("flagUrl: none for NO_FLAG codes or anything but two letters", () => {
  const noFlag = data("config").NO_FLAG;
  assert.ok(noFlag.includes("JG"));
  assert.equal(flagUrl("JG", noFlag), null);
  assert.equal(flagUrl("no", noFlag), "/vendor/flags/no.svg");
  for (const bad of [null, undefined, "", "N", "NOR", "1A"]) assert.equal(flagUrl(bad, noFlag), null);
});
test("NO_FLAG_DEFAULT equals config NO_FLAG", () => {
  assert.deepEqual([...NO_FLAG_DEFAULT].sort(), [...data("config").NO_FLAG].sort());
});
