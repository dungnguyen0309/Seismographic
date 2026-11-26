"""Overview page data, web/data/overview/:
- wgi_changes.json: scoring.wgi_changes for political stability (the Changes tab's movers chart; the page filters it
  by region and income);
- new_flags.json: {ISO3: [labels]}, the red flags each country crossed since last year (the Hotspots tab's "New").

fixtures(ctx) writes the parity cases for web/js/charts/overview.js. Their expected values come from headline(),
hotspot_rows() and the ranking CSV below, which copy app_pages/overview.py line for line (the page computes them
inline); tests/test_staticbuild_overview.py checks them against the running page."""

from __future__ import annotations

import pandas as pd

from prm import charts, config, content, data, interpret, scoring, ui
from staticbuild import charts as chart_fixtures
from staticbuild import fixtures as core_fixtures

ALL = "All regions"


def new_flags(ctx) -> dict[str, list[str]]:
    prev = data.get_values(ctx.core, ctx.year - 1, ctx.core["version"])
    out = {}
    for iso3 in ctx.values.index:
        if iso3 in prev.index:
            labels = [f["label"] for f in scoring.flag_changes(prev.loc[iso3], ctx.values.loc[iso3])[0]]
            if labels:
                out[iso3] = labels
    return out


def build(ctx) -> None:
    changes = scoring.wgi_changes(ctx.core["series"], ctx.core["countries"], "pv")
    ctx.write_json("data/overview/wgi_changes.json", ctx.table(changes))
    ctx.write_json("data/overview/new_flags.json", new_flags(ctx))


# ---- the page's calculations, as app_pages/overview.py does them ----------------------------------------------------
def filter_view(table: pd.DataFrame, region: str, income: list[str]) -> pd.DataFrame:
    view = table.copy()
    if region != ALL:
        view = view[view["region"] == region]
    if income:
        view = view[view["income"].isin(income)]
    return view


def headline(view: pd.DataFrame, hist: pd.DataFrame, values: pd.DataFrame, year: int) -> dict:
    scored = view.dropna(subset=["composite"])
    n_high = int(scored["tier"].isin(["High", "Severe"]).sum())
    yearly = hist[hist["iso3"].isin(view["iso3"])].groupby("year").agg(
        high=("tier", lambda s: int(s.isin(["High", "Severe"]).sum())),
        median=("composite", "median"),
        conflict=("battle_deaths_raw", lambda s: int((s >= 25).sum())),
    )
    last = yearly.loc[year - 1] if year - 1 in yearly.index else None
    n_conflict = int((scored["battle_deaths_raw"] >= 25).sum())
    median_now = scored["composite"].median() if len(scored) else None
    median = ui.median_delta(median_now, last)
    critical = sum(any(f["severity"] == "critical" for f in scoring.red_flags(values.loc[i])) for i in scored["iso3"])
    return {
        "scored": len(scored), "high": n_high, "high_delta": None if last is None else int(n_high - last["high"]),
        "median": "—" if median_now is None else f"{median_now:.0f}", "median_delta": median["delta"],
        "median_color": median["delta_color"], "conflict": n_conflict,
        "conflict_delta": None if last is None else int(n_conflict - last["conflict"]),
        "assessed": int((view["assessment"] == "✓").sum()), "critical": int(critical),
        "flagged": int((scored["flags"] > 0).sum()),
    }


def hotspot_rows(view: pd.DataFrame, values: pd.DataFrame, prev_values: pd.DataFrame, year: int,
                 today: pd.Timestamp) -> list[dict]:
    events = content.load_events()
    soon = events[(events["date"] >= today) & (events["date"] <= today + pd.Timedelta(days=120))
                  & (events["significance"].str.title() == "High")].sort_values("date").groupby("iso3").first()
    hotspots = []
    for r in view[view["composite"] >= 50].itertuples(index=False):
        reasons = []
        if pd.notna(r.delta_1y) and r.delta_1y >= 2:
            reasons.append(f"▲ {r.delta_1y:+.1f} since {year - 1}")
        new = [f["label"] for f in scoring.flag_changes(prev_values.loc[r.iso3], values.loc[r.iso3])[0]]
        if new:
            reasons.append("⚑ New: " + new[0] + (f" (+{len(new) - 1} more)" if len(new) > 1 else ""))
        if r.iso3 in soon.index:
            e = soon.loc[r.iso3]
            reasons.append(f"{e['event']} {interpret.countdown((e['date'] - today).days)}")
        if reasons:
            hotspots.append({"iso3": r.iso3, "name": r.name, "composite": r.composite,
                             "tier": r.tier, "signals": len(reasons), "why": " · ".join(reasons)})
    hotspots = pd.DataFrame(hotspots, columns=["iso3", "name", "composite", "why", "tier", "signals"])
    if hotspots.empty:
        return []
    hotspots = hotspots.sort_values(["signals", "composite"], ascending=False).head(6).reset_index(drop=True)
    return hotspots.to_dict("records")


RANKING = ["iso3", "name", "composite", "trend", "flag", "tier", "rank", *[p.key for p in config.PILLARS], "flags",
           "region", "coverage", "assessment", "analyst_rating"]


def ranking(view: pd.DataFrame) -> pd.DataFrame:
    return view.sort_values("rank", na_position="last")[RANKING].reset_index(drop=True)


# ---- fixtures ---------------------------------------------------------------------------------------------------
FILTERS = [(ALL, []), ("Sub-Saharan Africa", []), ("Europe & Central Asia", ["High income"]),
           (ALL, ["Low income", "Lower middle income"]), ("North America", ["Low income"])]  # the last one is empty


def _no_assessment_filter(table: pd.DataFrame) -> tuple[str, list[str]]:
    """A region and income group with scored countries but no written assessment ("Critical red flag" shows)."""
    for region in sorted(table["region"].dropna().unique()):
        for income in sorted(table["income"].dropna().unique()):
            view = filter_view(table, region, [income])
            if view["composite"].notna().any() and not (view["assessment"] == "✓").any():
                return region, [income]
    raise AssertionError("every region and income group has an assessment")


def fixtures(ctx) -> None:
    core, year = ctx.core, ctx.year
    custom = core_fixtures.CUSTOM_NAME
    scores_w = data.get_scores(core, year, core_fixtures.CUSTOM, core["version"])
    hist_w = data.get_history(core, core_fixtures.CUSTOM, core["version"])
    tables = {
        "default": (ui.master_table(core, ctx.values, ctx.scores, ctx.history), ctx.history),
        custom: (ui.master_table(core, ctx.values, scores_w, hist_w), hist_w),
    }
    default = tables["default"][0]
    filters = [*FILTERS, _no_assessment_filter(default)]
    cases = [(w, region, income) for w in tables for region, income in filters]

    head = []
    for w, region, income in cases:
        table, hist = tables[w]
        view = filter_view(table, region, income)
        head.append({"weights": w, "region": region, "incomes": income, "view": list(view["iso3"]),
                     "top": list(view.dropna(subset=["composite"]).nsmallest(12, "rank")["iso3"]),
                     "expected": headline(view, hist, ctx.values, year)})
    ctx.write_json("tests/fixtures/overview_headline.json", {"cases": head})

    today = pd.Timestamp.today().normalize()
    prev = data.get_values(core, year - 1, core["version"])
    hot = []
    with chart_fixtures._stable_sorts():
        for w, region, income in cases:
            view = filter_view(tables[w][0], region, income)
            hot.append({"weights": w, "region": region, "incomes": income,
                        "expected": hotspot_rows(view, ctx.values, prev, year, today)})
    ctx.write_json("tests/fixtures/overview_hotspots.json", {"today": str(today.date()), "cases": hot})

    csv = []
    with chart_fixtures._stable_sorts():
        for w, region, income in [("default", ALL, []), (custom, "Middle East, North Africa, Afghanistan & Pakistan", []),
                                  (custom, ALL, ["Low income"])]:
            rows = ranking(filter_view(tables[w][0], region, income))
            text = rows.drop(columns=["iso3", "flag"]).to_csv(index=False, lineterminator="\n")
            csv.append({"weights": w, "region": region, "incomes": income, "order": list(rows["iso3"]),
                        "expected": "﻿" + text})
    ctx.write_json("tests/fixtures/overview_ranking_csv.json", {"cases": csv})

    changes = scoring.wgi_changes(core["series"], core["countries"], "pv")
    names = dict(zip(default["iso3"], default["name"]))
    movers = []
    for region, income in [(ALL, []), ("Sub-Saharan Africa", []), (ALL, ["High income"])]:
        view = filter_view(default, region, income)
        c = changes[changes["iso3"].isin(view["iso3"])] if region != ALL or income else changes
        c = c.assign(name=c["iso3"].map(names))
        movers.append({"region": region, "incomes": income, **chart_fixtures._case(charts.movers, c, js_args=[])})
    ctx.write_json("tests/fixtures/overview_movers.json", {"cases": movers})
