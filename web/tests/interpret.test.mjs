import test from "node:test";
import assert from "node:assert/strict";
import { countryReading } from "../js/lib/interpret.js";
import { data, fixture, same } from "./helpers.mjs";

const config = data("config");
const values = data("values");
const custom = { master: fixture("master_w50_20_20_10"), scores: fixture("scores_w50_20_20_10"), hist: fixture("history_w50_20_20_10"), sfx: "_w50_20_20_10" };
const dflt = { master: data("master"), scores: data("scores"), hist: data("history"), sfx: "" };

for (const iso of ["ASM", "NGA", "NOR", "SYR", "USA", "VNM"]) {
  for (const t of [dflt, custom]) {
    test(`countryReading ${iso}${t.sfx || " (default)"}`, () => {
      const i = fixture(`interpret_${iso}${t.sfx}`).inputs;
      const got = countryReading(iso, t.master, values, t.scores, t.hist,
        { events: i.events, flows: i.flows, year: i.year, today: i.today, wgiTrend: i.wgi_trend, config });
      same(got, fixture(`interpret_${iso}${t.sfx}`).reading, iso);
      assert.equal(got.tier === null, iso === "ASM");
    });
  }
}
