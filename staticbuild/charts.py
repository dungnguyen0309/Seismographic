"""Plotly figures as JSON, and the parity fixtures for web/js/lib/charts.js and globe.js.

`figure(fig)` is what a page group writes for a chart that depends on no visitor choice: the figure JSON without its
template (the browser's plot() applies the Streamlit theme every figure in the app gets).

`fixtures(ctx)` writes tests/fixtures/charts_<name>.json ({cases: [{args, figure}]}, arrays as plain lists) for every
chart the JS ports, with fixed inputs taken from the snapshot, and globe_overview.json (the Overview's globe data)."""

from __future__ import annotations

import base64
import contextlib
import functools
import json

import numpy as np
import pandas as pd
import plotly.io as pio

from prm import charts, config, globe, scoring, ui

PICKED = ["NGA", "SYR", "NOR"]


def build(ctx) -> None:
    """Nothing to export: the pages write their own figures with figure()."""


def figure(fig) -> dict:
    """The figure as plotly.io.to_json writes it, minus layout.template (plot() in charts.js sets it)."""
    out = json.loads(pio.to_json(fig))
    out.get("layout", {}).pop("template", None)
    return out


def _plain(obj):
    """Typed arrays ({dtype, bdata, shape}) as nested lists, so the tests compare plain values."""
    if isinstance(obj, dict):
        if "bdata" in obj and "dtype" in obj:
            arr = np.frombuffer(base64.b64decode(obj["bdata"]), dtype=np.dtype(obj["dtype"]))
            shape = obj.get("shape")
            if shape:
                arr = arr.reshape([int(s) for s in str(shape).split(",")] if isinstance(shape, str) else shape)
            return arr.tolist()
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_plain(v) for v in obj]
    return obj


def _rows(df: pd.DataFrame, cols: list[str] | None = None) -> list[dict]:
    d = df if cols is None else df[cols]
    return d.astype(object).where(d.notna(), None).to_dict("records")


def _series(s: pd.Series) -> dict:
    return {str(k): (None if pd.isna(v) else v) for k, v in s.items()}


def _list(values) -> list:
    return [None if pd.isna(v) else v for v in values]


@contextlib.contextmanager
def _stable_sorts():
    """sort_values as a stable sort while the expected figures are drawn. pandas' default quicksort orders equal values
    by CPU (numpy's AVX2 / AVX-512 sorting networks), so the app itself orders ties differently on different machines;
    the JS port keeps ties in their original order, and so do the fixtures."""
    real = pd.DataFrame.sort_values, pd.Series.sort_values

    def stable(fn):
        return functools.wraps(fn)(lambda self, *a, **kw: fn(self, *a, **{"kind": "mergesort", **kw}))

    pd.DataFrame.sort_values, pd.Series.sort_values = stable(real[0]), stable(real[1])
    try:
        yield
    finally:
        pd.DataFrame.sort_values, pd.Series.sort_values = real


def _case(fn, *args, js_args=None):
    with _stable_sorts():
        fig = fn(*args)
    return {"args": js_args if js_args is not None else list(args), "figure": _plain(figure(fig))}


def chart_cases(ctx) -> dict[str, list[dict]]:
    core, year = ctx.core, ctx.year
    table = ui.master_table(core, ctx.values, ctx.scores, ctx.history)
    names = dict(zip(table["iso3"], table["name"]))
    scored = table.dropna(subset=["composite"])
    hist = ctx.history
    out: dict[str, list[dict]] = {}

    view_cols = ["iso3", "name", "tier", "rank_label", "composite", "economic", "region"]
    africa = table[table["region"] == "Sub-Saharan Africa"]
    out["choropleth"] = [
        _case(charts.choropleth, table[view_cols], "composite", "Composite",
              js_args=[_rows(table, view_cols), "composite", "Composite"]),
        _case(charts.choropleth, africa[view_cols], "economic", "Economy", True,
              js_args=[_rows(africa, view_cols), "economic", "Economy", True]),
    ]
    m_cols = ["iso3", "name", "tier", "composite", "population", "stability", "governance", "economic", "social"]
    out["risk_matrix"] = [_case(charts.risk_matrix, scored[m_cols], "stability", "economic",
                                js_args=[_rows(scored, m_cols), "stability", "economic"])]
    out["tier_distribution"] = [_case(charts.tier_distribution, scored[["region", "tier"]],
                                      js_args=[_rows(scored, ["region", "tier"])])]

    changes = scoring.wgi_changes(core["series"], core["countries"], "pv")
    changes = changes.assign(name=changes["iso3"].map(names))
    mv_cols = ["iso3", "name", "start", "end", "change"]
    out["movers"] = [_case(charts.movers, changes[mv_cols], js_args=[_rows(changes, mv_cols)])]

    h_cols = ["year", "composite", *[p.key for p in config.PILLARS], "tier", "rank", "battle_deaths_raw"]
    country_hist = {iso3: hist[hist["iso3"] == iso3].sort_values("year")[h_cols] for iso3 in [*PICKED, "UKR", "ASM"]}
    out["risk_history"] = [
        *[_case(charts.risk_history, country_hist[i], True, js_args=[_rows(country_hist[i]), True])
          for i in ["NGA", "SYR", "UKR"]],
        _case(charts.risk_history, country_hist["NOR"], js_args=[_rows(country_hist["NOR"])]),
    ]
    with _stable_sorts():
        out["history_summary"] = [{"args": [_rows(h)], "text": charts.history_summary(h)}
                                  for h in country_hist.values()]
    out["case_history"] = [_case(charts.case_history, country_hist["UKR"], "2022-02-24", "Russian invasion",
                                 js_args=[_rows(country_hist["UKR"]), "2022-02-24", "Russian invasion"])]

    p_keys = [p.key for p in config.PILLARS]
    nga = table.set_index("iso3").loc["NGA"]
    peers = table[table["region"] == nga["region"]]
    median = peers[p_keys].median()
    out["pillar_bars"] = [_case(charts.pillar_bars, nga, median, js_args=[_series(nga[p_keys]), _series(median)])]
    scenario = nga[p_keys].copy()
    scenario["stability"] -= 7.6
    scenario["economic"] += 0.3
    scenario["social"] = np.nan
    out["whatif_pillars"] = [_case(charts.whatif_pillars, nga[p_keys], scenario,
                                   js_args=[_series(nga[p_keys]), _series(scenario)])]

    sel = table.set_index("iso3").loc[PICKED + ["ASM"], p_keys]
    out["radar"] = [_case(charts.radar, sel, names,
                          js_args=[{i: _series(sel.loc[i]) for i in sel.index}, {i: names[i] for i in sel.index}])]

    def series_rows(key):
        s = core["series"].get(key)
        return _rows(s[s["iso3"].isin(PICKED)][["iso3", "year", "value"]])

    comp = {"composite": hist.rename(columns={"composite": "value"})}
    comp_js = {"composite": _rows(hist[hist["iso3"].isin(PICKED)].rename(columns={"composite": "value"}),
                                  ["iso3", "year", "value"])}
    pick_names = {i: names[i] for i in PICKED}
    out["compare_lines"] = [
        _case(charts.compare_lines, comp, "composite", PICKED, names, "Composite risk score (0–100)",
              js_args=[comp_js, "composite", PICKED, pick_names, "Composite risk score (0–100)"]),
        _case(charts.compare_lines, core["series"], "gdp_growth", PICKED, names, "Real GDP growth (%)", year - 12,
              year + 5, year,
              js_args=[{"gdp_growth": series_rows("gdp_growth")}, "gdp_growth", PICKED, pick_names,
                       "Real GDP growth (%)", year - 12, year + 5, year]),
    ]

    moved = table.dropna(subset=["delta_1y"])
    moved = moved.assign(thin=ui.thin_data(moved))
    cb_cols = ["iso3", "name", "delta_1y", "prev_composite", "composite", "thin"]
    out["change_bars"] = [_case(charts.change_bars, moved[cb_cols], js_args=[_rows(moved, cb_cols)])]

    rh = hist[hist["iso3"].isin(table.loc[table["region"] == "South Asia", "iso3"])][["year", "tier"]]
    out["tier_mix"] = [_case(charts.tier_mix, rh, js_args=[_rows(rh)])]

    before = scored["tier"]
    after = scored["composite"].add(9).clip(upper=100).map(scoring.tier_for)
    out["tier_shift"] = [_case(charts.tier_shift, before, after, js_args=[_list(before), _list(after)])]

    flows = core.get("flows")
    hosts = (flows[flows["host"].isin(names)].groupby("host", as_index=False)["value"].sum()
             .nlargest(10, "value").rename(columns={"host": "iso3"}))
    hosts = hosts.assign(name=hosts["iso3"].map(names), value=hosts["value"] / 1e6)
    counts = pd.DataFrame({"flag": ["Inflation 50%+", "War", "Debt over 100% of GDP"], "count": [12, 3, 7]})
    links = flows[(flows["origin"] == "SYR") & flows["host"].isin(names)].nlargest(10, "value").rename(
        columns={"host": "iso3"})
    links = links.assign(name=links["iso3"].map(names))
    out["ranked_bars"] = [
        _case(charts.ranked_bars, hosts, "value", "name", charts.BETTER, "million refugees hosted", ".1f",
              js_args=[_rows(hosts, ["iso3", "name", "value"]), "value", "name", charts.BETTER,
                       "million refugees hosted", ".1f"]),
        _case(charts.ranked_bars, counts, "count", "flag", charts.WORSE, "countries",
              js_args=[_rows(counts), "count", "flag", charts.WORSE, "countries"]),
        _case(charts.ranked_bars, links, "value", "name", charts.WORSE, "refugees",
              js_args=[_rows(links, ["iso3", "name", "value"]), "value", "name", charts.WORSE, "refugees"]),
    ]

    deaths = core["series"]["battle_deaths"]
    by_year = deaths.groupby("year")["value"].sum().loc[lambda s: s.index >= year - 12]
    months = ["Jan 2025", "Feb 2025", "Mar 2025"]
    out["yearly_bars"] = [
        _case(charts.yearly_bars, by_year.index, by_year.values, "Battle-related deaths", charts.WORSE, "deaths",
              js_args=[_list(by_year.index), _list(by_year.values), "Battle-related deaths", charts.WORSE, "deaths"]),
        _case(charts.yearly_bars, months, np.array([41, 7, 19]), "Events", charts.WORSE, "events",
              js_args=[months, [41, 7, 19], "Events", charts.WORSE, "events"]),
    ]

    bd = ctx.values["battle_deaths_100k"]
    infl = ctx.values["inflation"]
    color = config.PILLAR_COLORS["economic"]
    out["distribution"] = [
        _case(charts.distribution, infl, "Inflation (%)", color, js_args=[_list(infl), "Inflation (%)", color]),
        _case(charts.distribution, bd, "Battle deaths (per 100k)", config.PILLAR_COLORS["stability"], True,
              js_args=[_list(bd), "Battle deaths (per 100k)", config.PILLAR_COLORS["stability"], True]),
        _case(charts.distribution, pd.Series([5.0, 5.0, 5.0]), "Flat", color,
              js_args=[[5.0, 5.0, 5.0], "Flat", color]),
    ]

    ps_cols = ["iso3", "name", "composite", "tier", *p_keys]
    region_peers = peers[peers["iso3"] != "NGA"]
    out["peer_strip"] = [_case(charts.peer_strip, nga, region_peers[ps_cols], "Nigeria",
                               js_args=[_series(nga[["composite", "tier", *p_keys]]), _rows(region_peers, ps_cols),
                                        "Nigeria"])]

    by_fifth = pd.DataFrame({"mean": [0.004, 0.012, np.nan, 0.035, 0.081], "sum": [1, 3, np.nan, 9, 21],
                             "size": [250, 251, 0, 257, 259]}, index=range(1, 6))
    out["onset_fifths"] = [_case(charts.onset_fifths, by_fifth, 0.0265, config.PILLAR_COLORS["stability"],
                                 js_args=[_rows(by_fifth), 0.0265, config.PILLAR_COLORS["stability"]])]
    return out


def _globe(ctx, table, flows, metric: str, label: str, options: dict, **kwargs) -> dict:
    """globe.risk_globe's data dict (its component call captured), with flag URLs pointed at the vendored copies.
    The inputs beyond data/master.json and data/history.json: whether the flows (globe_flows.json) are passed, the
    metric and the JS options."""
    captured = {}

    def component(**kw):
        captured.update(kw["data"])

    real, globe._component = globe._component, component
    try:
        with _stable_sorts():
            globe.risk_globe(table, ctx.history, flows, metric, label, **kwargs)
    finally:
        globe._component = real
    for c in captured["countries"]:
        if c["flag"]:
            c["flag"] = "/vendor/flags/" + c["flag"].rsplit("/", 1)[-1]
    return {"inputs": {"flows": flows is not None, "metric": metric, "metricLabel": label, "options": options},
            "data": captured}


def globe_cases(ctx) -> dict[str, dict]:
    table = ui.master_table(ctx.core, ctx.values, ctx.scores, ctx.history)
    flows = ctx.core.get("flows")
    africa = sorted(table.loc[table["region"] == "Sub-Saharan Africa", "iso3"])
    moved = table.dropna(subset=["delta_1y"]).set_index("iso3")["delta_1y"]
    notes = {"NGA": "▲ test note", "SYR": "war"}
    return {
        # the Overview: composite, every country in view, the flat-map link
        "overview": _globe(ctx, table, flows, "composite", "Composite", {"onFlat": True}, in_view=set(table["iso3"]),
                           region=None, selected=None, on_flat=lambda: None),
        # Score changes: a custom value with its own scale, notes, a region
        "changes": _globe(ctx, table, None, "composite", "Change vs 2025", {
            "key": "chg_globe", "inView": africa, "region": "Sub-Saharan Africa", "custom": _series(moved),
            "colorscale": config.CHANGE_COLORSCALE, "valueRange": [-10, 10], "valueFormat": "signed",
            "ticks": ["−10 · safer", "0", "riskier · +10"], "notes": notes, "emptyLabel": "no comparison",
            "extrudeAbs": True, "layers": {"spin": True, "flows": False, "conflict": False}},
            key="chg_globe", in_view=set(africa), region="Sub-Saharan Africa", custom=moved,
            colorscale=config.CHANGE_COLORSCALE, value_range=(-10, 10), value_format="signed",
            ticks=["−10 · safer", "0", "riskier · +10"], notes=notes, empty_label="no comparison", extrude_abs=True,
            layers={"spin": True, "flows": False, "conflict": False}),
        # a profile-style globe: a pillar metric, a focus country and its flows
        "focus": _globe(ctx, table, flows, "stability", "Stability", {
            "key": "profile_globe_SYR", "focus": "SYR", "height": 520, "selected": "SYR", "hint": "Arcs",
            "layers": {"spin": False, "flows": True, "conflict": True}},
            key="profile_globe_SYR", focus="SYR", height=520, selected="SYR", hint="Arcs",
            layers={"spin": False, "flows": True, "conflict": True}),
    }


def fixtures(ctx) -> None:
    for name, cases in chart_cases(ctx).items():
        ctx.write_json(f"tests/fixtures/charts_{name}.json", {"cases": cases})
    for name, case in globe_cases(ctx).items():
        ctx.write_json(f"tests/fixtures/globe_{name}.json", case)
    ctx.write_json("tests/fixtures/globe_flows.json", ctx.table(ctx.core["flows"][["origin", "host", "value", "year"]]))
