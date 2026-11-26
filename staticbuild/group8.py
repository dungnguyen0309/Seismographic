"""Data for the Compare, Score changes, Regions and Indicator explorer pages, and their parity fixtures.

build(ctx) writes what the core files do not hold:
- data/group8/series/<ISO3>.json: {key: [[year, value], ...]} for the six WGI dimensions (every year) and the four
  indicators of Compare's "Economic trajectory" (year - 12 to year + 5, all charts.compare_lines draws of them);
- data/group8/flag_changes.json: the red flags new or cleared since last year (scoring.flag_changes of last year's
  values against this year's), table order; they depend on no weights, so the page only filters them by region.

fixtures(ctx) writes tests/fixtures/group8_<page>.json: what each page shows for fixed choices, with the default
weights and ?w=50,20,20,10, computed as app_pages/{compare,changes,regions,explorer}.py do."""

from __future__ import annotations

import pandas as pd

from prm import charts, config, content, data, interpret, scoring, ui
from prm.config import INDICATORS, MAX_COMPARE, PILLARS, TIER_ORDER, WGI_DIMENSIONS
from staticbuild.charts import _plain, _stable_sorts, figure

WGI_KEYS = [f"wgi_{d}" for d in WGI_DIMENSIONS]
ECON = ["gdp_growth", "inflation", "gov_debt", "current_account"]
CUSTOM = (("stability", 50.0), ("governance", 20.0), ("economic", 20.0), ("social", 10.0))  # ?w=50,20,20,10


def series_files(core: dict, year: int) -> dict[str, dict[str, list]]:
    out = {iso3: {k: [] for k in WGI_KEYS + ECON} for iso3 in core["countries"]["iso3"]}
    for key in WGI_KEYS + ECON:
        df = core["series"].get(key)
        if df is None or df.empty:
            continue
        if key in ECON:
            df = df[(df["year"] >= year - 12) & (df["year"] <= year + 5)]
        for iso3, g in df.sort_values("year", kind="mergesort").groupby("iso3", sort=False):
            if iso3 in out:
                out[iso3][key] = [[int(y), v] for y, v in zip(g["year"], g["value"])]
    return out


def flag_changes(ctx) -> pd.DataFrame:
    """changes.py's flag rows for every country (the page keeps those of the region picked)."""
    prev = data.get_values(ctx.core, ctx.year - 1, ctx.core["version"])
    rows = []
    for iso3 in ctx.core["countries"]["iso3"]:
        worse, eased = scoring.flag_changes(prev.loc[iso3], ctx.values.loc[iso3])
        rows += [{"iso3": iso3, "change": "New", "severity": f["severity"], "flag_label": f["label"]} for f in worse]
        rows += [{"iso3": iso3, "change": "Cleared", "severity": "", "flag_label": f["label"]} for f in eased]
    return pd.DataFrame(rows, columns=["iso3", "change", "severity", "flag_label"])


def build(ctx) -> None:
    for iso3, s in series_files(ctx.core, ctx.year).items():
        ctx.write_json(f"data/group8/series/{iso3}.json", s)
    ctx.write_json("data/group8/flag_changes.json", ctx.table(flag_changes(ctx)))


# ---------------------------------------------------------------------------------------------------------------
# Fixtures: the pages' own computations, for fixed choices
# ---------------------------------------------------------------------------------------------------------------
def _fig(fig) -> dict:
    return _plain(figure(fig))


def _none(v):
    return None if v is None or (not isinstance(v, str) and pd.isna(v)) else v


def _records(df: pd.DataFrame, cols: list[str]) -> list[dict]:
    return [{c: _none(v) for c, v in zip(cols, row)} for row in df[cols].itertuples(index=False)]


def _weighted(ctx, weights):
    if weights is None:
        scores, hist = ctx.scores, ctx.history
    else:
        scores = data.get_scores(ctx.core, ctx.year, weights, ctx.core["version"])
        hist = data.get_history(ctx.core, weights, ctx.core["version"])
    return scores, hist, ui.master_table(ctx.core, ctx.values, scores, hist)


def _picked(c: str, options) -> list[str]:  # compare.py's reading of ?c=
    return list(dict.fromkeys(x.strip() for x in str(c).upper().split(",") if x.strip() in options))[:MAX_COMPARE]


def compare_case(ctx, picked, scores, hist, table) -> dict:
    year, core = ctx.year, ctx.core
    names = dict(zip(core["countries"]["iso3"], core["countries"]["name"]))
    t = table.set_index("iso3")
    sel = t.loc[picked]
    like = []
    if len(picked) < MAX_COMPARE:
        like = [i for i in scoring.similar(scores, picked[0], n=8).index if i not in picked][:4]
    cards = []
    for iso3 in picked:
        r = sel.loc[iso3]
        cards.append({"iso3": iso3, "score": "—" if pd.isna(r["composite"]) else f"{r['composite']:.0f}",
                      "tier": _none(r["tier"]), "rank": None if pd.isna(r["rank"]) else int(r["rank"]),
                      "flags": int(r["flags"]), "trend": r.get("trend", "—"),
                      "said": ui.trend_said(r["delta_1y"], year) if pd.notna(r.get("delta_1y")) else None})
    rows = [{"Indicator": ind.short, **{names[i]: ind.fmt(ctx.values.loc[i].get(ind.key)) for i in picked},
             "Unit": ind.unit} for ind in INDICATORS]
    rows += [{"Indicator": f"{p.short} pillar",
              **{names[i]: "—" if pd.isna(sel.loc[i, p.key]) else f"{sel.loc[i, p.key]:.0f}" for i in picked},
              "Unit": "risk score, 0–100"} for p in PILLARS]
    lines = {"composite": charts.compare_lines({"composite": hist.rename(columns={"composite": "value"})}, "composite",
                                               picked, names, "Composite risk score (0–100)")}
    for dim in ["pv", "cc"]:
        lines[f"wgi_{dim}"] = charts.compare_lines(core["series"], f"wgi_{dim}", picked, names,
                                                   "WGI score (0–100, higher = better)")
    for key, label in [("gdp_growth", "Real GDP growth (%)"), ("gov_debt", "Public debt (% of GDP)")]:
        lines[key] = charts.compare_lines(core["series"], key, picked, names, label, start_year=year - 12,
                                          end_year=year + 5, projected_from=year)
    return {"picked": picked, "similar": like, "cards": cards, "indicators": rows,
            "radar": _fig(charts.radar(sel[[p.key for p in PILLARS]], names)),
            "lines": {k: _fig(v) for k, v in lines.items()}}


def _driver(row) -> str:  # changes.py
    deltas = {p.short: row[f"d_{p.key}"] for p in PILLARS if pd.notna(row[f"d_{p.key}"])}
    if not deltas or pd.isna(row["delta_1y"]):
        return "—"
    sign = 1 if row["delta_1y"] >= 0 else -1
    pillar = max(deltas, key=lambda k: sign * deltas[k])
    return f"{pillar} {interpret.signed(deltas[pillar], 0)}"


def changes_case(ctx, region, hist, table) -> dict:
    prev_year = ctx.year - 1
    view = table if region == "All regions" else table[table["region"] == region]
    moved = view.dropna(subset=["delta_1y"])
    tier_rank = {t: i for i, t in enumerate(TIER_ORDER)}
    moved = moved.assign(tier_move=moved["tier"].map(tier_rank) - moved["prev_tier"].map(tier_rank))
    pillar_keys = [p.key for p in PILLARS]
    prev_pillars = hist[hist["year"] == prev_year].set_index("iso3")[pillar_keys]
    for p in PILLARS:
        moved[f"d_{p.key}"] = pd.to_numeric(moved[p.key] - moved["iso3"].map(prev_pillars[p.key]), errors="coerce")
    moved["driver"] = moved.apply(_driver, axis=1) if len(moved) else pd.Series(dtype=object)

    prev_values = data.get_values(ctx.core, prev_year, ctx.core["version"])
    flag_rows = []
    for iso3 in view["iso3"]:
        worse, eased = scoring.flag_changes(prev_values.loc[iso3], ctx.values.loc[iso3])
        flag_rows += [{"iso3": iso3, "change": "New", "severity": f["severity"], "flag_label": f["label"]} for f in worse]
        flag_rows += [{"iso3": iso3, "change": "Cleared", "severity": "", "flag_label": f["label"]} for f in eased]
    flags = pd.DataFrame(flag_rows, columns=["iso3", "change", "severity", "flag_label"])
    flags = flags.merge(view[["iso3", "name"]], on="iso3", how="left")
    kpis = [int((moved["delta_1y"] >= ui.TREND_THRESHOLD).sum()), int((moved["delta_1y"] <= -ui.TREND_THRESHOLD).sum()),
            int((moved["tier_move"] > 0).sum()), int((moved["tier_move"] < 0).sum()), int((flags["change"] == "New").sum())]

    with _stable_sorts():
        bars = None if moved.empty else _fig(charts.change_bars(moved.assign(thin=ui.thin_data(moved))))
        drawn = pd.concat([moved.nsmallest(10, "delta_1y"), moved.nlargest(10, "delta_1y")])
        thin = bool(ui.thin_data(drawn).any())
        notes = {r.iso3: (f"{r.prev_tier} → {r.tier} · " if pd.notna(r.tier_move) and r.tier_move != 0 else "")
                 + f"main driver: {r.driver}" for r in moved.itertuples(index=False)}
        tiers = moved[moved["tier_move"].fillna(0) != 0].sort_values(["tier_move", "delta_1y"], ascending=False)
        tiers = tiers.assign(move=[f"{a} → {b}" for a, b in zip(tiers["prev_tier"], tiers["tier"])])
        drivers = moved[moved["delta_1y"].abs() >= ui.TREND_THRESHOLD].sort_values("delta_1y", ascending=False)
        d_cols = [f"d_{k}" for k in pillar_keys]
        drivers = drivers[["iso3", "name", "trend", *d_cols]].round()
        if not flags.empty:
            flags = flags.assign(severity=flags["severity"].map(lambda s: config.SEVERITY_LABEL[s] if s else "Cleared"))
            flags = flags.sort_values(["change", "name"], ascending=[False, True])
    return {"region": region, "kpis": kpis, "bars": bars, "thin": thin, "notes": notes,
            "custom": {r.iso3: r.delta_1y for r in moved.itertuples(index=False)},
            "tiers": _records(tiers, ["iso3", "name", "trend", "move", "driver"]),
            "drivers": _records(drivers, ["iso3", "name", "trend", *d_cols]),
            "flags": _records(flags, ["iso3", "name", "change", "severity", "flag_label"])}


def regions_case(ctx, asked, hist, table) -> dict:
    year = ctx.year
    table = table.join(ctx.values[["displaced_total"]], on="iso3")
    regions = sorted(table["region"].dropna().unique())
    region = regions[regions.index(asked) if asked in regions else 0]
    rv = table[table["region"] == region]
    scored = rv.dropna(subset=["composite"])
    rh = hist[hist["iso3"].isin(rv["iso3"])]
    yearly = rh.groupby("year").agg(median=("composite", "median"),
                                    high=("tier", lambda s: int(s.isin(["High", "Severe"]).sum())))
    last = yearly.loc[year - 1] if year - 1 in yearly.index else None
    median_now = scored["composite"].median() if len(scored) else None
    n_high = int(scored["tier"].isin(["High", "Severe"]).sum())
    md = ui.median_delta(median_now, last)
    riskiest = scored.nsmallest(1, "rank")
    kpis = [
        {"value": "—" if median_now is None else f"{median_now:.0f}", "delta": None if md["delta"] is None else str(md["delta"]),
         "color": md["delta_color"]},
        {"value": str(n_high), "delta": None if last is None else str(int(n_high - last["high"])), "color": "inverse"},
        {"value": str(int((scored["battle_deaths_raw"] >= 25).sum()))},
        {"value": ui.fmt_population(rv["displaced_total"].sum())},
        {"value": riskiest["name"].iloc[0] if len(riskiest) else "—"},
    ]
    with _stable_sorts():
        mix = _fig(charts.tier_mix(rh))
        ranking = list(rv.sort_values("rank", ascending=True, na_position="last")["iso3"])
    events = content.load_events()
    events = events[events["iso3"].isin(rv["iso3"])]
    if not events.empty:
        names = dict(zip(table["iso3"], table["name"]))
        events = events.assign(country=events["iso3"].map(names).fillna(events["country"]))
    events = events.assign(date=events["date"].dt.strftime("%Y-%m-%d"))
    return {"asked": asked, "region": region, "subtitle": f"{len(scored)} countries scored · {year}", "kpis": kpis,
            "tier_mix": mix, "ranking": ranking, "height": min(460, 35 * (len(rv) + 1) + 3),
            "events": _records(events, ["date", "iso3", "country", "event", "significance", "source_url"])}


def explorer_case(ctx, key, region, scores, table) -> dict:
    year, values = ctx.year, ctx.values
    ind = config.INDICATOR_BY_KEY[key]
    frame = table[["iso3", "flag", "name", "region"]].copy()
    frame["value"] = frame["iso3"].map(values[key])
    frame["year"] = frame["iso3"].map(values[f"{key}__year"]) if f"{key}__year" in values else year
    frame["risk"] = frame["iso3"].map(scores[f"n_{key}"])
    view = frame if region == "All regions" else frame[frame["region"] == region]
    known = view.dropna(subset=["value"])
    n = min(10, len(known) // 2)
    with _stable_sorts():
        lists = ((("risky", f"Riskiest {n}", known.nlargest(n, "risk")), ("safe", f"Safest {n}", known.nsmallest(n, "risk")))
                 if n >= 2 else (("all", f"All {len(known)} countries", known.sort_values("risk", ascending=False)),))
        shown = []
        for part, title, rows in lists:
            if rows.empty:
                break
            rows = rows.assign(shown=rows["value"].map(ind.fmt)).round({"risk": 0})
            shown.append({"part": part, "title": title, "rows": _records(rows, ["iso3", "name", "shown", "risk", "year"])})
        dist = _fig(charts.distribution(known["value"], f"{ind.short} ({ind.unit})", config.PILLAR_COLORS[ind.pillar],
                                        log=ind.norm == "log"))
    notes = {r.iso3: f"{ind.short}: {ind.fmt(r.value)} {ind.unit}" + ("" if pd.isna(r.year) else f" ({int(r.year)})")
             for r in known.itertuples(index=False)}
    return {"key": key, "region": region, "count": len(known),
            "median": ind.fmt(known["value"].median()) if len(known) else "—",
            "lists": shown, "notes": notes, "custom": {i: _none(v) for i, v in zip(frame["iso3"], frame["risk"])},
            "inView": list(view["iso3"]), "distribution": dist}


def fixtures(ctx) -> None:
    out = "tests/fixtures/group8_"
    runs = {"default": _weighted(ctx, None), "w50_20_20_10": _weighted(ctx, CUSTOM)}
    options = set(ctx.core["countries"]["iso3"])
    unscored = sorted(ctx.scores.index[ctx.scores["composite"].isna()])[0]
    texts = ["NGA,KEN", " nga, ken ,NGA", "XXX,YYY", "", "NGA,KEN,ZAF,ETH,SYR,NOR,USA", "XXX,nga", "NGA,,KEN"]
    compare = {"parse": [{"c": c, "picked": _picked(c, options)} for c in texts], "cases": []}
    for name, (scores, hist, table) in runs.items():
        for picked in (["NGA", "KEN", "ZAF"], [unscored, "SYR"], ["NOR", "USA", "VNM", "SYR", "KEN", "NGA"]):
            compare["cases"].append({"weights": name, **compare_case(ctx, picked, scores, hist, table)})
    ctx.write_json(out + "compare.json", compare)

    changes = {"cases": [{"weights": name, **changes_case(ctx, region, hist, table)}
                         for name, (_, hist, table) in runs.items()
                         for region in ("All regions", "Sub-Saharan Africa", "North America")]}
    ctx.write_json(out + "changes.json", changes)

    regions = {"cases": [{"weights": name, **regions_case(ctx, asked, hist, table)}
                         for name, (_, hist, table) in runs.items()
                         for asked in (None, "South Asia", "Nowhere", "Sub-Saharan Africa", "North America")]}
    ctx.write_json(out + "regions.json", regions)

    scores, _, table = runs["default"]
    explorer = {"cases": [explorer_case(ctx, key, region, scores, table) for key, region in (
        ("wgi_pv", "All regions"), ("battle_deaths_100k", "All regions"), ("homicide", "North America"),
        ("displaced_share", "South Asia"), ("reserves_months", "Sub-Saharan Africa"))]}
    ctx.write_json(out + "explorer.json", explorer)
