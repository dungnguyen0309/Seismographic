"""Python outputs the JS ports are checked against: web/tests/fixtures/*.json (written with --fixtures).

scores_*, history_*, master_* are tables like data/scores.json; interpret_<ISO3>[_w50_20_20_10].json hold the full
interpret.Reading plus the inputs the port needs beyond data/{master,values,scores,history}.json for those weights:
today, the country's events and outbound flows, and its political-stability trend. Chart fixtures (charts_<name>)
come from a `fixtures(ctx)` function in a staticbuild module (charts.py); every module that defines one is called."""

import importlib
import math
import pkgutil

import pandas as pd

import staticbuild
from prm import content, data, interpret, scoring, ui

CUSTOM = (("stability", 50.0), ("governance", 20.0), ("economic", 20.0), ("social", 10.0))  # ?w=50,20,20,10
CUSTOM_NAME = "w50_20_20_10"
COUNTRIES = ["NGA", "SYR", "NOR", "USA", "VNM"]  # plus one economy with no composite
NAN = float("nan")


def call(fn, *args):
    try:
        return fn(*args)
    except Exception as exc:  # the fixture records what Python does, including failing on None
        return None, type(exc).__name__


def cases(fn, inputs, extra=()) -> list[dict]:
    out = []
    for v in inputs:
        for e in extra or [()]:
            r = call(fn, v, *e)
            row = {"in": "None" if v is None else "NaN" if isinstance(v, float) and math.isnan(v) else v}
            if extra:
                row["digits" if fn is interpret.signed else "year"] = e[0]
            if isinstance(r, tuple) and len(r) == 2 and r[0] is None:
                row["error"] = r[1]
            else:
                row["out"] = r
            out.append(row)
    return out


def format_fixture() -> dict:
    spread = [0, -0.04, 0.04, 0.05, -0.05, 0.5, -0.5, 0.95, 2.25, -2.25, -1.0, 1.0, 6.2, 99.95, 1234.567, -1234.5, 1e6,
              None, NAN]
    deltas = [None, NAN, -12.34, -5, -1.0, -0.99, -0.04, 0, 0.05, 0.95, 1.0, 2.25, 6.2]
    pops = [None, NAN, 0, 999, 1000, 12345, 499999, 999999, 1e6, 1234567, 9.99e8, 1e9, 1.4e9, 1.2345e10]
    return {
        "signed": cases(interpret.signed, spread, [(1,), (0,)]),
        "fmt_population": cases(ui.fmt_population, pops),
        "trend_label": cases(ui.trend_label, deltas),
        "trend_said": cases(ui.trend_said, deltas, [(2026,)]),
        "countdown": cases(interpret.countdown, [0, 1, 2, 30, 365, -1]),
    }


def reading_fixture(ctx, iso3: str, table, values, scores, hist, events) -> dict:
    reading = interpret.country_reading(iso3, table, values, scores, hist, events, ctx.core.get("flows"), ctx.year,
                                        ctx.core["series"])
    flows = ctx.core.get("flows")
    flows = flows[flows["origin"] == iso3][["host", "value"]] if flows is not None else pd.DataFrame(columns=["host", "value"])
    return {"reading": reading, "inputs": {
        "iso3": iso3, "year": ctx.year, "today": str(pd.Timestamp.today().normalize().date()),
        "events": ctx.table(events[events["iso3"] == iso3]), "flows": ctx.table(flows),
        "wgi_trend": scoring.wgi_trend(ctx.core["series"], iso3, "pv"),
    }}


def build(ctx) -> None:
    w, core, version = ctx.write_json, ctx.core, ctx.core["version"]
    out = "tests/fixtures/"
    scores_w = data.get_scores(core, ctx.year, CUSTOM, version)
    hist_w = data.get_history(core, CUSTOM, version)  # what the app shows for these weights
    w(out + "scores_default.json", ctx.table(ctx.scores))
    w(out + f"scores_{CUSTOM_NAME}.json", ctx.table(scores_w))
    w(out + f"history_{CUSTOM_NAME}.json", ctx.table(hist_w))
    w(out + "flag_counts.json", scoring.flag_counts(ctx.values, core["series"]).astype(int).to_dict())
    w(out + "format.json", format_fixture())

    master = ui.master_table(core, ctx.values, ctx.scores, ctx.history)
    master_w = ui.master_table(core, ctx.values, scores_w, hist_w)
    w(out + f"master_{CUSTOM_NAME}.json", ctx.table(master_w.drop(columns="flag")))
    unscored = sorted(ctx.scores.index[ctx.scores["composite"].isna()])[0]
    events = content.load_events()
    for iso3 in [*COUNTRIES, unscored]:
        w(out + f"interpret_{iso3}.json",
          reading_fixture(ctx, iso3, master, ctx.values, ctx.scores, ctx.history, events))
        w(out + f"interpret_{iso3}_{CUSTOM_NAME}.json",
          reading_fixture(ctx, iso3, master_w, ctx.values, scores_w, hist_w, events))

    for info in sorted(pkgutil.iter_modules(staticbuild.__path__), key=lambda m: m.name):
        if info.name.startswith("_") or info.name == "fixtures":
            continue
        hook = getattr(importlib.import_module(f"staticbuild.{info.name}"), "fixtures", None)
        if hook:
            hook(ctx)
