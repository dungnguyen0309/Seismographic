// Port of prm/cases.py reading(): what the index showed the year before a case, and the verdict.
// c: a case from data/group10/cases.json (its red flags of the year before come with it); hist: ctx.history().
import { asRows, na } from "../lib/scoring.js";

export function reading(c, hist, config) {
  const before = Number(c.date.slice(0, 4)) - 1;
  const rows = new Map(asRows(hist).filter((r) => r.iso3 === c.iso3).map((r) => [r.year, r]));
  const r = rows.get(before);
  if (!r || na(r.composite)) return { before, verdict: null };
  const start = rows.get(before - 3);
  const change = na(start?.composite) ? null : r.composite - start.composite;
  const moves = {};
  if (start) {
    for (const p of config.pillars) if (!na(start[p.key]) && !na(r[p.key])) moves[p.short] = r[p.key] - start[p.key];
  }
  const rank = Math.trunc(r.rank), n = Math.trunc(r.n_ranked);
  const verdict = ["High", "Severe"].includes(r.tier) || rank <= 25 ? "Flagged"
    : r.tier === "Elevated" || rank <= 50 || (change !== null && change >= 5) ? "Partly flagged" : "Missed";
  return {
    before, score: r.composite, tier: r.tier, rank, n, change,
    pillars: Object.fromEntries(config.pillars.map((p) => [p.short, na(r[p.key]) ? null : r[p.key]])),
    pillar_moves: moves, flags: c.flags, verdict,
  };
}
