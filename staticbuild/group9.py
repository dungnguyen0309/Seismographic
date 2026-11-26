"""web/data/group9/{conflict,economy}.json: what the Conflict & displacement and Economic stress pages need that no
shared file holds.

conflict.json: the battle-death and displacement figures (no visitor choice, so built here as the app draws them,
plus the outlook tab's two charts), the headline numbers, the globe notes and the table rows; the page adds each
country's tier for the visitor's weights. economy.json: the IMF series the outlook chart summarises (that chart, the
heatmap and the scatter depend on the region picked, so web/js/charts/group9.js draws them).

fixtures(ctx) writes web/tests/fixtures/group9_*.json, the Python outputs the JS ports are checked against."""

from __future__ import annotations

import datetime as dt

import pandas as pd

from prm import charts, config, content, data, forecast, hotspots, interpret, scoring, ui
from staticbuild import charts as figs
from staticbuild.fixtures import CUSTOM

ECON_KEYS = [k for k, _ in charts.ECON_COLUMNS]  # also app_pages/economy.py econ_flag_keys (the same six)
OUTLOOK_SERIES = ["inflation", "gdp_growth", "gov_debt"]  # the IMF outlook's three views
HISTORY_YEARS = 12  # the IMF outlook starts this many years before the analysis year


def _table(ctx, scores=None, hist=None) -> pd.DataFrame:
    return ui.master_table(ctx.core, ctx.values, ctx.scores if scores is None else scores,
                           ctx.history if hist is None else hist)


def pct_delta(now: float, before: float):
    """app_pages/conflict.py pct_delta: a whole-percent change, a plain 0 when it rounds to nothing."""
    if not before:
        return None
    change = int(round((now / before - 1) * 100))
    return f"{change:+d}%" if change else 0


def conflict(ctx) -> dict:
    """Everything app_pages/conflict.py computes without the visitor's weights."""
    core, values = ctx.core, ctx.values
    table = _table(ctx)
    names = dict(zip(table["iso3"], table["name"]))
    known = set(names)
    empty = pd.DataFrame(columns=["iso3", "year", "value"])
    bd = core["series"].get("battle_deaths", empty)
    bd = bd[bd["iso3"].isin(known)]
    dp = core["series"].get("displaced", empty)
    dp = dp[dp["iso3"].isin(known)]
    flows = core.get("flows")
    bd_year = int(bd["year"].max()) if len(bd) else None
    dp_year = int(dp["year"].max()) if len(dp) else None
    latest_bd = bd[bd["year"] == bd_year].set_index("iso3")["value"] if bd_year else pd.Series(dtype=float)
    prev_bd = bd[bd["year"] == bd_year - 1].set_index("iso3")["value"] if bd_year else pd.Series(dtype=float)

    deaths_by_year = bd.groupby("year")["value"].sum()
    displaced_by_year = dp.groupby("year")["value"].sum()
    in_conflict, at_war = int((latest_bd >= 25).sum()), int((latest_bd >= 1000).sum())
    vs_bd = None if prev_bd.empty else f"vs {bd_year - 1}"
    two_years = len(displaced_by_year) > 1
    kpis = [
        {"label": "Armed conflicts", "value": in_conflict,
         "delta": None if prev_bd.empty else in_conflict - int((prev_bd >= 25).sum()), "deltaColor": "inverse",
         "note": vs_bd, "help": f"Countries with at least 25 battle-related deaths in {bd_year}: the Uppsala Conflict "
                                "Data Program's threshold for state-based armed conflict (via the World Bank)"},
        {"label": "At war", "value": at_war,
         "delta": None if prev_bd.empty else at_war - int((prev_bd >= 1000).sum()), "deltaColor": "inverse",
         "note": vs_bd, "help": f"At least 1,000 battle-related deaths in {bd_year}"},
        {"label": f"Battle deaths, {bd_year}", "value": f"{latest_bd.sum():,.0f}",
         "delta": pct_delta(latest_bd.sum(), prev_bd.sum()), "deltaColor": "inverse", "note": vs_bd},
        {"label": f"Displaced, {dp_year}",
         "value": ui.fmt_population(displaced_by_year.iloc[-1]) if len(displaced_by_year) else "—",
         "delta": pct_delta(displaced_by_year.iloc[-1], displaced_by_year.iloc[-2]) if two_years else None,
         "deltaColor": "inverse", "note": f"vs {displaced_by_year.index[-2]}" if two_years else None,
         "help": "Refugees, asylum seekers, others in need of international protection and internally displaced "
                 "people (UNHCR)"},
        {"label": "Refugees abroad", "value": ui.fmt_population(flows["value"].sum()) if flows is not None else "—",
         "help": "Refugees, asylum seekers and others in need of protection living outside their country (UNHCR)"},
    ]

    displaced_now = dp[dp["year"] == dp_year].set_index("iso3")["value"] if dp_year else pd.Series(dtype=float)
    notes = {}
    for iso3 in sorted(known):
        parts = []
        if latest_bd.get(iso3, 0) >= 25:
            parts.append(f"{latest_bd[iso3]:,.0f} battle deaths in {bd_year}")
        if displaced_now.get(iso3, 0) >= 100_000:
            parts.append(f"{ui.fmt_population(displaced_now[iso3])} people displaced ({dp_year})")
        if parts:
            notes[iso3] = " · ".join(parts)
    deadliest = latest_bd[latest_bd >= 25].nlargest(10)

    rows = table[table["iso3"].isin(latest_bd[latest_bd >= 25].index)].copy()
    rows["deaths"] = rows["iso3"].map(latest_bd)
    rows["deaths_prev"] = rows["iso3"].map(prev_bd).fillna(0)
    rows["deaths_change"] = rows["deaths"] - rows["deaths_prev"]
    rows = rows.join(values[["battle_deaths_100k", "displaced_share"]], on="iso3")
    rows["level"] = rows["deaths"].map(lambda d: "War" if d >= 1000 else "Armed conflict")
    rows["change_text"] = rows["deaths_change"].map(lambda d: interpret.signed(d, 0))
    rows = rows.sort_values("deaths", ascending=False).reset_index(drop=True)
    rows = rows[["iso3", "name", "iso2", "deaths", "change_text", "battle_deaths_100k", "displaced_share", "stability",
                 "level"]].round({"deaths": 0, "battle_deaths_100k": 2, "displaced_share": 1, "stability": 0})

    has_flows = flows is not None and not flows.empty
    flows_year = int(flows["year"].max()) if has_flows else None
    with figs._stable_sorts():  # equal values in the same order on every machine
        recent = deaths_by_year[deaths_by_year.index >= 1990]
        out = {
            "deaths": charts.yearly_bars(recent.index, recent.values, "Battle-related deaths", charts.WORSE, "deaths"),
            "deadliest": charts.compare_lines(core["series"], "battle_deaths", latest_bd.nlargest(3).index.tolist(),
                                              names, "Battle-related deaths", start_year=2010),
            "displaced": charts.yearly_bars(displaced_by_year.index, displaced_by_year.values, "People", charts.WORSE,
                                            "people"),
        }
        origins = (dp[dp["year"] == dp_year].nlargest(10, "value")
                   .assign(name=lambda d: d["iso3"].map(names), value=lambda d: d["value"] / 1e6))
        out["origins"] = charts.ranked_bars(origins, "value", "name", charts.WORSE, "million people displaced", fmt=".1f")
        if has_flows:
            hosts = (flows[flows["host"].isin(known)].groupby("host", as_index=False)["value"].sum()
                     .nlargest(10, "value").rename(columns={"host": "iso3"}))
            hosts = hosts.assign(name=hosts["iso3"].map(names), value=hosts["value"] / 1e6)
            out["hosts"] = charts.ranked_bars(hosts, "value", "name", charts.BETTER, "million refugees hosted", fmt=".1f")
            out["sankey"] = charts.refugee_sankey(flows, names)
        if ctx.outlook is not None:  # data.get_outlook: the default-weight history, so no visitor choice
            out["drivers"] = charts.outlook_drivers(ctx.outlook.coefficients, forecast.FEATURE_LABELS)
            out["calibration"] = charts.calibration_bars(ctx.outlook.calibration)
    return {
        "bd_year": bd_year, "dp_year": dp_year, "flows_year": flows_year, "in_conflict": in_conflict, "kpis": kpis,
        "notes": notes, "deadliest": [{"iso3": i, "name": names[i], "deaths": v} for i, v in deadliest.items()],
        "rows": ctx.table(rows), "figures": {k: figs.figure(f) for k, f in out.items()},
    }


def economy(ctx) -> dict:
    """The IMF series behind the outlook chart: the table's countries, from the chart's first year on (later years
    too, so the caption can say where the projections end)."""
    known = set(ctx.core["countries"]["iso3"])
    start = ctx.year - HISTORY_YEARS
    out = {}
    for key in OUTLOOK_SERIES:
        s = ctx.core["series"].get(key, pd.DataFrame(columns=["iso3", "year", "value"]))
        out[key] = ctx.table(s[s["iso3"].isin(known) & (s["year"] >= start)][["iso3", "year", "value"]]
                             .reset_index(drop=True))
    return {"series": out}


def build(ctx) -> None:
    ctx.write_json("data/group9/conflict.json", conflict(ctx))
    ctx.write_json("data/group9/economy.json", economy(ctx))


# ---------------------------------------------------------------------------------------------------------------------
# Parity fixtures for web/js/charts/group9.js (inputs come from web/data, which the same snapshot built)
# ---------------------------------------------------------------------------------------------------------------------
def _fig(fn, *args) -> dict:
    return figs._case(fn, *args, js_args=[])["figure"]


def _economy_cases(ctx, table) -> list[dict]:
    df = table.join(ctx.values[ECON_KEYS], on="iso3")
    out = []
    for region, n, key in (("All regions", 40, "inflation"), ("Sub-Saharan Africa", 20, "gov_debt"),
                           ("North America", 250, "gdp_growth")):
        view = df if region == "All regions" else df[df["region"] == region]
        flags = {iso3: [f for f in scoring.red_flags(ctx.values.loc[iso3]) if f["key"] in ECON_KEYS]
                 for iso3 in view["iso3"]}
        rows = []
        for r in view.itertuples(index=False):
            hits = flags.get(r.iso3, [])
            if len(hits) >= 2:
                rows.append({"iso3": r.iso3, "name": r.name, "count": len(hits), "economic": r.economic,
                             "warnings": " · ".join(f"{f['short']} ({config.SEVERITY_LABEL[f['severity']].lower()})"
                                                    for f in hits)})
        warnings = pd.DataFrame(rows, columns=["iso3", "name", "count", "economic", "warnings"])
        with figs._stable_sorts():
            warnings = warnings.sort_values(["count", "economic"], ascending=False).reset_index(drop=True)
        heat = view.dropna(subset=["economic"]).nlargest(n, "economic").reset_index(drop=True)
        series = ctx.core["series"][key]
        series = series[series["iso3"].isin(view["iso3"])]
        label = {"inflation": "Inflation (%)", "gdp_growth": "Real GDP growth (%)",
                 "gov_debt": "Public debt (% of GDP)"}[key]
        out.append({
            "region": region, "n": n, "key": key, "label": label,
            "kpis": [int((view["inflation"] >= 20).sum()), int((view["gdp_growth"] < 0).sum()),
                     int((view["gov_debt"] >= 90).sum()), int((view["fiscal_balance"] <= -5).sum()),
                     int((view["reserves_months"] < 3).sum())],
            "notes": {iso3: " · ".join(f"⚑ {f['label']}" for f in hits) for iso3, hits in flags.items() if hits},
            "warnings": figs._rows(warnings),
            "heatmap": _fig(charts.econ_heatmap, heat),
            "scatter": _fig(charts.stagflation_scatter, view),
            "outlook": _fig(charts.imf_outlook, series, ctx.year, label, ctx.year - HISTORY_YEARS, ctx.year + 5),
            "last": min(ctx.year + 5, int(series["year"].max())) if len(series) else ctx.year + 5,
        })
    return out


def _hotspot_cases(ctx, table, table_w) -> dict:
    h = hotspots.load()
    signal = hotspots.escalation(h["gdelt"])
    empty = hotspots.escalation(None)
    names = dict(zip(ctx.core["countries"]["iso3"], ctx.core["countries"]["name"]))
    region_of = dict(zip(table["iso3"], table["region"]))

    def board(t, s):
        b = hotspots.board(t, h["monthly"], h["cells"], s)
        b["last_event"] = b["last_event"].map(lambda d: d.isoformat() if d == d and d is not None else None)
        return figs._rows(b)

    maps, bars = [], []
    for region in ("All regions", "Sub-Saharan Africa"):
        cells = h["cells"].assign(region=h["cells"]["iso3"].map(region_of))
        monthly = h["monthly"]
        if region != "All regions":
            cells = cells[cells["region"] == region]
            monthly = monthly[monthly["iso3"].map(region_of) == region]
        maps.append({"region": region, "figure": _fig(charts.hotspot_map, cells, names, hotspots.VIOLENCE,
                                                      region != "All regions")})
        by_month = monthly.groupby("month")["events"].sum()
        fig = charts.yearly_bars(pd.to_datetime(by_month.index).strftime("%b %Y"), by_month.to_numpy(), "Events",
                                 charts.WORSE, "events").update_xaxes(type="category")
        bars.append({"region": region, "figure": figs._plain(figs.figure(fig))})
    return {
        "constants": {k: getattr(hotspots, k) for k in (
            "WINDOW_DAYS", "RECENT_DAYS", "MIN_ARTICLES_7D", "ESCALATING_RATIO", "EASING_RATIO", "STATUS_ORDER",
            "MIN_EVENTS_90D", "MIN_DEATHS_90D", "MIN_COMPOSITE")} | {"VIOLENCE": {str(k): v for k, v in hotspots.VIOLENCE.items()}},
        "boards": [{"weights": "default", "stale": False, "board": board(table, signal)},
                   {"weights": "w50_20_20_10", "stale": False, "board": board(table_w, signal)},
                   {"weights": "default", "stale": True, "board": board(table, empty)}],
        "maps": maps, "bars": bars,
    }


def _calendar_case(ctx) -> dict:
    """The Calendar tab for today's date (the JS test passes the same date)."""
    events = content.load_events()
    names = dict(zip(ctx.core["countries"]["iso3"], ctx.core["countries"]["name"]))
    events["country"] = events.apply(lambda r: names.get(r["iso3"], r["country"] or r["iso3"]), axis=1)
    today = pd.Timestamp(dt.date.today())
    upcoming = events[events["date"] >= today]
    past = events[events["date"] < today]
    with figs._stable_sorts():
        windows = {"Next 90 days": upcoming[upcoming["date"] <= today + pd.Timedelta(days=90)],
                   "Next 12 months": upcoming[upcoming["date"] <= today + pd.Timedelta(days=365)],
                   "All upcoming": upcoming, "Past": past.sort_values("date", ascending=False)}
        next_event = upcoming.sort_values("date").groupby("iso3").first()
        timeline = {w: _fig(charts.events_timeline, d) for w, d in windows.items() if not d.empty}
    days = (next_event["date"] - today).dt.days.clip(lower=0)
    return {
        "today": today.strftime("%Y-%m-%d"), "colorscale": config.reversed_scale(config.map_colorscale("social")),
        "windows": {w: [{**r, "date": r["date"].strftime("%d %b %Y")} for r in figs._rows(d)] for w, d in windows.items()},
        "timeline": timeline,
        "custom": {iso3: (None if v > 365 else int(v)) for iso3, v in days.items()},
        "notes": {iso3: f"{e.event} · {e.date:%d %b %Y} · {e.significance} significance" for iso3, e in next_event.iterrows()},
    }


def _outlook_case(ctx, table) -> dict:
    outlook = ctx.outlook
    preds = outlook.predictions.merge(table[["iso3", "iso2", "name", "tier", "composite"]], on="iso3", how="left")
    peaceful = preds.dropna(subset=["probability"]).sort_values("probability", ascending=False)
    shown = peaceful.head(20).assign(chance=lambda d: d["probability"] * 100,
                                     recent=lambda d: d["recent_conflict"].map({1.0: "yes", 0.0: ""}))
    return {
        "rows": figs._rows(shown[["iso3", "name", "chance", "relative", "recent", "tier"]].reset_index(drop=True).round(1)),
        "chance_max": max(30.0, shown["chance"].max()),
        "texts": [f"{outlook.base_rate:.1%}", "—" if outlook.auc is None else f"{outlook.auc:.2f}",
                  f"{len(outlook.backtest):,} country-years, {int(outlook.backtest['onset'].sum())} new conflicts. The "
                  f"predictions beat the average rate by {outlook.brier_skill:.0%} (Brier skill score)."],
    }


def fixtures(ctx) -> None:
    table = _table(ctx)
    version = ctx.core["version"]
    table_w = _table(ctx, data.get_scores(ctx.core, ctx.year, CUSTOM, version), data.get_history(ctx.core, CUSTOM, version))
    w = ctx.write_json
    w("tests/fixtures/group9_economy.json", {"cases": _economy_cases(ctx, table)})
    w("tests/fixtures/group9_hotspots.json", _hotspot_cases(ctx, table, table_w))
    w("tests/fixtures/group9_calendar.json", _calendar_case(ctx))
    w("tests/fixtures/group9_outlook.json", _outlook_case(ctx, table))
