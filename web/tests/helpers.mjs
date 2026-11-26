import { readFileSync } from "node:fs";
import assert from "node:assert/strict";

const read = (p) => JSON.parse(readFileSync(new URL(p, import.meta.url), "utf8"));
export const data = (name) => read(`../data/${name}.json`);
export const fixture = (name) => read(`./fixtures/${name}.json`);

export const objects = (t) => t.rows.map((r) => Object.fromEntries(t.columns.map((c, i) => [c, r[i]])));

// Equal strings/booleans/nulls, numbers within tol (the model must match Python to 1e-9).
export function same(actual, expected, path = "", tol = 1e-9) {
  if (typeof expected === "number" && typeof actual === "number") {
    assert.ok(Math.abs(actual - expected) <= tol * Math.max(1, Math.abs(expected)), `${path}: ${actual} != ${expected}`);
  } else if (Array.isArray(expected)) {
    assert.ok(Array.isArray(actual), `${path}: not an array`);
    assert.equal(actual.length, expected.length, `${path}: length`);
    expected.forEach((e, i) => same(actual[i], e, `${path}[${i}]`, tol));
  } else if (expected && typeof expected === "object") {
    assert.deepEqual(Object.keys(actual).sort(), Object.keys(expected).sort(), `${path}: keys`);
    for (const k of Object.keys(expected)) same(actual[k], expected[k], `${path}.${k}`, tol);
  } else assert.equal(actual ?? null, expected ?? null, path);
}

// Compare a table ({columns, rows}) or a Map of row objects with a fixture table, row by row, column by column.
export function sameTable(actual, expected, key = "iso3", tol = 1e-9) {
  const exp = objects(expected);
  const act = actual instanceof Map ? actual : new Map(objects(actual).map((r) => [r[key], r]));
  assert.equal(act.size, exp.length, "row count");
  for (const e of exp) {
    const a = act.get(e[key]);
    assert.ok(a, `missing ${e[key]}`);
    for (const c of expected.columns) if (c !== key) same(a[c] ?? null, e[c], `${e[key]}.${c}`, tol);
  }
}
