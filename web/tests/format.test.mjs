import test from "node:test";
import assert from "node:assert/strict";
import { signed, fmtPopulation, trendLabel, trendSaid, countdown, ordinal, fixed } from "../js/lib/format.js";
import { fixture } from "./helpers.mjs";

const fx = fixture("format");
const val = (x) => (x === "None" ? null : x === "NaN" ? NaN : x);

function run(fn, c, ...args) {
  if (c.error) return assert.throws(() => fn(val(c.in), ...args), TypeError, `${c.in}`);
  assert.equal(fn(val(c.in), ...args), c.out, `${fn.name}(${c.in}, ${args})`);
}

test("signed matches Python", () => {
  assert.equal(signed(0), "0.0");
  assert.equal(signed(-0.04), "0.0");
  for (const c of fx.signed) run(signed, c, c.digits);
});
test("fmtPopulation", () => fx.fmt_population.forEach((c) => run(fmtPopulation, c)));
test("trendLabel", () => fx.trend_label.forEach((c) => run(trendLabel, c)));
test("trendSaid", () => fx.trend_said.forEach((c) => run(trendSaid, c, c.year)));
test("countdown", () => fx.countdown.forEach((c) => run(countdown, c)));
test("ordinal", () => {
  const got = [1, 2, 3, 4, 11, 12, 13, 21, 22, 101, 111].map(ordinal);
  assert.deepEqual(got, ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "101st", "111th"]);
});
test("fixed rounds the binary value half to even, like Python", () => {
  assert.equal(fixed(2.25, 1), "2.2");
  assert.equal(fixed(0.125, 2), "0.12");
  assert.equal(fixed(2.675, 2), "2.67");
  assert.equal(fixed(1234.5, 0, { group: true }), "1,234");
  assert.equal(fixed(-0.04, 1), "-0.0");
  assert.equal(fixed(5, 1, { sign: true }), "+5.0");
});
