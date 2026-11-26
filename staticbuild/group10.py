"""Case studies, stress test, assessment builder and data downloads (Task 10).

data/group10/cases.json    the cases, with the red flags of the year before (no weights in them) and any commentary
data/group10/stress.json   the shocks and the preset scenarios (prm/stress.py)
data/group10/builder.json  the IMF's growth figure for next year, for the builder's Latest data (country_brief)
data/group10/tables.json   the open-data tables that do not depend on the weights, column types, descriptions
files/seismographic.xlsx   every table with the default weights; an unchanged snapshot gives the same bytes

Everything that follows the visitor's weights (readings, the stress test, the index and history tables) is computed in
the browser; `fixtures(ctx)` writes what the JS ports are checked against (web/tests/fixtures/group10_*.json)."""

from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from prm import cases, config, content, data, export, interpret, scoring, stress, ui
from staticbuild.common import ROOT

CUSTOM = (("stability", 50.0), ("governance", 20.0), ("economic", 20.0), ("social", 10.0))  # ?w=50,20,20,10
FIXED_GENERATED = "2026-01-01T00:00:00+00:00"


def _kind(s: pd.Series) -> str:
    if pd.api.types.is_float_dtype(s):
        return "float"
    return "int" if pd.api.types.is_integer_dtype(s) else "str"


def _stamp(ctx) -> str:
    return f"{ctx.core['snapshot_date']}T00:00:00"


def _workbook(ctx) -> bytes:
    """export.to_excel with the default weights, made repeatable: the snapshot date as the time it was made (about
    sheet, document properties) and on every zip entry."""
    info = {**export.meta(ctx.core, ctx.year, dict(ctx.weights)), "generated": _stamp(ctx) + "+00:00"}
    blob = export.to_excel(ctx.tables, info)
    when = tuple(int(x) for x in ctx.core["snapshot_date"].split("-")) + (0, 0, 0)
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(blob)) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            body = src.read(item.filename)
            if item.filename == "docProps/core.xml":
                body = re.sub(rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*", lambda m: m.group(1) + (_stamp(ctx) + "Z").encode(), body)
            entry = zipfile.ZipInfo(item.filename, when)
            entry.compress_type, entry.external_attr = zipfile.ZIP_DEFLATED, item.external_attr
            dst.writestr(entry, body)
    return out.getvalue()


def _write_bytes(path: Path, blob: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")  # as common.write_json: a crash never leaves half a file
    try:
        tmp.write_bytes(blob)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _values_before(ctx, year: int) -> pd.DataFrame:
    return scoring.build_values(ctx.core["series"], ctx.core["countries"], year)


def build(ctx) -> None:
    w = ctx.write_json
    out = []
    for case in cases.CASES:
        before = _values_before(ctx, int(case.date[:4]) - 1)
        flags = scoring.red_flags(before.loc[case.iso3]) if case.iso3 in before.index else []
        out.append({"key": case.key, "iso3": case.iso3, "date": case.date, "kind": case.kind, "title": case.title,
                    "what": case.what, "source": case.source, "flags": flags, "commentary": cases.commentary(case)})
    w("data/group10/cases.json", {"verdicts": cases.VERDICTS, "cases": out})

    w("data/group10/stress.json", {
        "shocks": [{"key": s.key, "label": s.label, "unit": s.unit, "low": s.low, "high": s.high, "step": s.step,
                    "relative": s.relative} for s in stress.SHOCKS],
        "scenarios": stress.SCENARIOS,
    })

    growth = ctx.core["series"].get("gdp_growth")
    nxt = growth[growth["year"] == ctx.year + 1].drop_duplicates("iso3") if growth is not None else pd.DataFrame()
    growth_by = {r.iso3: float(r.value) for r in nxt.itertuples() if pd.notna(r.value)}
    w("data/group10/builder.json", {"next_growth": dict(sorted(growth_by.items()))})  # sorted: no churn between rebuilds

    meta = export.meta(ctx.core, ctx.year, dict(ctx.weights))
    tables = {
        "meta": {k: meta[k] for k in ("title", "index_year", "data_version", "scale", "terms")},
        "descriptions": export.TABLES,
        "dtypes": {name: {c: _kind(df[c]) for c in df.columns} for name, df in ctx.tables.items()},
        "bd_last_year": int(ctx.core["series"]["battle_deaths"]["year"].max()),
        **{name: ctx.table(ctx.tables[name]) for name in ("indicators", "red_flags", "conflict_outlook", "dictionary")},
    }
    w("data/group10/tables.json", tables)
    _write_bytes(ctx.web / "files" / "seismographic.xlsx", _workbook(ctx))


# ---- fixtures --------------------------------------------------------------------------------------------------------
def _page_code(name: str, *defs: str) -> tuple[dict, dict]:
    """Constants and functions of an app page, taken from its source, so the fixtures run the page's own code."""
    tree = ast.parse((ROOT / "app_pages" / name).read_text(encoding="utf-8"))
    consts, funcs = {}, []
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in defs:
            consts[node.targets[0].id] = ast.literal_eval(node.value)
        elif isinstance(node, ast.FunctionDef) and node.name in defs:
            funcs.append(node)
    ns = {"config": config, "scoring": scoring, "pd": pd, "interpret": interpret}
    exec(compile(ast.Module(funcs, []), name, "exec"), ns)
    return consts, ns


def _normalise_cases(ctx) -> list[dict]:
    v = ctx.values
    lst = lambda s: [None if pd.isna(x) else float(x) for x in s]  # noqa: E731
    out = []
    for key, change in (("wgi_pv", -7.5), ("inflation", 4.0), ("reserves_months", 0.6), ("battle_deaths_100k", 2.5),
                        ("displaced_share", 1.4), ("gov_debt", 10.0)):
        ind = config.INDICATOR_BY_KEY[key]
        ref = v[key]
        shocked = ref * change if key in ("reserves_months", "battle_deaths_100k", "displaced_share") else ref + change
        out.append({"name": key, "values": lst(shocked), "reference": lst(ref), "higher_is_riskier": ind.higher_is_riskier,
                    "method": ind.norm})
    nan = float("nan")
    synthetic = [
        ("ties and outside the range", [-5, 1, 2, 2, 3, 99, nan], [1, 2, 2, 3, nan, 4], True, "percentile"),
        ("lower is riskier", [-5, 1, 2, 2, 3, 99, nan], [1, 2, 2, 3, nan, 4], False, "percentile"),
        ("one reference value", [1, 2, 3], [5, nan], True, "percentile"),
        ("log, negatives and zeros", [-3, 0, 0.5, 10, 1e6, nan], [0, 0, 1, 3, 8, 20, nan], True, "log"),
        ("log, lower is riskier", [-3, 0, 0.5, 10, 1e6, nan], [0, 0, 1, 3, 8, 20], False, "log"),
        ("log, no positive reference", [0, 1, 2], [0, 0, -1], True, "log"),
    ]
    for name, vals, ref, hir, method in synthetic:
        out.append({"name": name, "values": vals, "reference": ref, "higher_is_riskier": hir, "method": method})
    for c in out:
        s = pd.Series(c["values"], dtype=float)
        c["out"] = lst(scoring.normalise_against(s, pd.Series(c["reference"], dtype=float), c["higher_is_riskier"], c["method"]))
        c["values"], c["reference"] = lst(pd.Series(c["values"], dtype=float)), lst(pd.Series(c["reference"], dtype=float))
    return out


def _stress_fixture(ctx) -> dict:
    core, version = ctx.core, ctx.core["version"]
    _, page = _page_code("stress.py", "_csv")
    decode_in = ["garbage", "", None, "gdp_growth:-4,gov_debt:10", " gdp_growth : -4.3 ,inflation: 7 ",
                 "inflation:1e1", "inflation:1_0", "inflation:0x10", "inflation:inf", "inflation:nan", "inflation:+3",
                 "inflation:3.", "inflation:.5", "reserves_months:-1000", "reserves_months:-12.5", "gdp_growth:0.26",
                 "gdp_growth:0.25", "gdp_growth:0.75", "gdp_growth:-0", "unknown:5,gdp_growth:", "gdp_growth:1e400",
                 "gdp_growth:5,gdp_growth:-2,inflation:2", "youth_unemployment:3,gdp_growth:-1", "gdp_growth:-4:5",
                 "unemployment:1__0", "unemployment:_1", "unemployment:1_", "gov_debt:1e-3", "current_account:-6.25"]
    encode_in = [{}, {"gdp_growth": -4.0, "gov_debt": 10.0}, {"inflation": 0.0, "unemployment": 1.5},
                 {"nope": 3.0, "reserves_months": -10.0}, stress.SCENARIOS["Price surge (like 2022)"]]
    table_d = ui.master_table(core, ctx.values, ctx.scores, ctx.history)
    scores_w, hist_w = data.get_scores(core, ctx.year, CUSTOM, version), data.get_history(core, CUSTOM, version)
    table_w = ui.master_table(core, ctx.values, scores_w, hist_w)
    by = lambda col, val: sorted(table_d.loc[table_d[col] == val, "iso3"])  # noqa: E731
    runs = [
        (ctx.weights, stress.SCENARIOS["Global recession (like 2009)"], None, table_d),
        (dict(CUSTOM), stress.SCENARIOS["Price surge (like 2022)"], by("region", "Sub-Saharan Africa"), table_w),
        (ctx.weights, {"reserves_months": -60.0, "unemployment": 8.0, "youth_unemployment": 16.0, "gov_debt": -10.0,
                       "inflation": 30.0, "current_account": 3.0}, by("income", "High income"), table_d),
        (ctx.weights, {"gdp_growth": -8.0}, [], table_d),
    ]
    out_runs = []
    for weights, shocks, scope, table in runs:
        result = stress.run(ctx.values, dict(weights), dict(shocks), set(scope) if scope is not None else None)
        frame = table.join(result, on="iso3")
        page["hit"] = frame[frame["hit"] & frame["composite_before"].notna()]
        out_runs.append({"weights": list(dict(weights).items()), "shocks": shocks, "scope": scope,
                         "rows": ctx.table(result), "summary": stress.summary(result),
                         "csv": page["_csv"]().decode("utf-8-sig").replace("\r\n", "\n")})
    return {"decode": [{"in": t, "out": stress.decode(t)} for t in decode_in],
            "encode": [{"in": s, "out": stress.encode(s)} for s in encode_in], "runs": out_runs}


def _builder_fixture(ctx) -> dict:
    consts, page = _page_code("builder.py", "DRIVER_FACTS", "_facts")
    facts = {}
    for iso3 in ("NGA", "SYR", "USA", "VNM", "NOR", "ASM", "TUV"):
        page.update(values=ctx.values, iso3=iso3, s=ctx.scores.loc[iso3])
        facts[iso3] = {box: page["_facts"](keys) for box, keys in consts["DRIVER_FACTS"].items()}
    judgments = lambda *ts: [{"text": t, "probability": p, "term": config.estimative_term(p)}  # noqa: E731
                             for t, p in zip(ts, (65, 50, 12))]
    scen = lambda d, s: [{"name": n, "probability": p, "description": d, "signposts": s}  # noqa: E731
                         for n, p in (("Base case", 60), ("Upside", 15), ("Downside", 25))]
    plain = {"country": "Nigeria", "iso3": "NGA", "author": "Tuan Dung Nguyen", "date": "2026-11-25",
             "analyst_rating": "Elevated", "outlook": "Stable", "confidence": "Moderate", "horizon": "12 months",
             "model_score": "58 (Elevated)", "bluf": "", "judgments": judgments("", "", ""), "drv_political": "",
             "drv_security": "", "drv_economic": "", "drv_social": "", "scenarios": scen("", ""),
             "indicators_to_watch": "", "divergence": "", "implications": "", "sources": ""}
    full = {**plain, "author": 'An "analyst"', "horizon": "6 months", "model_score": "",
            "bluf": "  Risk rises.\n\nCosts $2bn.  ", "judgments": judgments("  First  ", "", "Third | piped"),
            "drv_political": "- Wgi: 3\n→ Why", "drv_security": " \t", "drv_economic": "x\r\ny", "drv_social": " s ",
            "scenarios": scen("multi\nline | pipe\t end", "a|b  c"), "indicators_to_watch": "a\n\n  b  \n\r\n",
            "divergence": "  ", "implications": "Firms: *care*.", "sources": "\nIMF, 2026\n Crisis Group \n"}
    markdown = [{"in": f, "out": content.build_assessment_markdown(f)} for f in
                (plain, full, {"date": "2026-01-02"}, {**full, "judgments": [], "scenarios": []})]
    rows = [{"date": "2026-12-01", "iso3": "NGA", "country": "Nigeria", "event": 'Election, "first" round',
             "category": "Election", "significance": "High", "source_url": "https://example.org/a", "notes": "two\nlines"},
            {"date": "2026-12-02", "iso3": "KEN", "event": " plain ", "notes": "cr\rhere"}, {},
            {"country": "Côte d'Ivoire", "event": "a;b", "notes": 'only "quotes"'}]
    front = [m["out"] for m in markdown] + ["no front matter", "---\nkey: value\nno close", "﻿---\na: b\n---\nx",
                                             "---\r\nA: 'q' # note\r\nb: \"x #y\"\r\nc: d #e\r\n# skip: me\r\nnocolon\r\n---\r\n\r\n body \r\n"]
    names = dict(zip(ctx.core["countries"]["iso3"], ctx.core["countries"]["name"]))
    brief = {i: scoring.country_brief(i, names[i], ctx.values, ctx.scores, ctx.core["series"], ctx.core["countries"], ctx.year)
             for i in ("NGA", "VNM", "USA", "SYR", "ASM")}
    return {"markdown": markdown, "csv_row": [{"in": r, "out": content.csv_row(r)} for r in rows],
            "front_matter": [{"in": t, "meta": content.parse_front_matter(t)[0], "body": content.parse_front_matter(t)[1]}
                             for t in front],
            "estimative": [{"p": p, "term": config.estimative_term(p)} for p in [*range(0, 101), 0.5, 5.5, 54.5, 55.5, 99.5]],
            "driver_facts": consts["DRIVER_FACTS"], "facts": facts, "brief": brief,
            "outlooks": content.OUTLOOKS, "confidence": content.CONFIDENCE}


def _export_fixture(ctx) -> dict:
    core, version = ctx.core, ctx.core["version"]
    rng = np.random.default_rng(10)
    floats = [0.1 + 0.2, 1e-5, 2.5e-7, 1e16, 1.2345e20, 3.0, -0.0, 0.0, 123456789.0, 1e15, 9999999999999998.0, 0.0001,
              0.00012345, -42.5, 5e-324, 1.7976931348623157e308, *rng.uniform(-1000, 1000, 60).tolist(),
              *(10.0 ** rng.uniform(-8, 18, 60)).tolist(), *ctx.values["population"].dropna().head(20).tolist()]
    ujson_in = [*rng.uniform(-1000, 1000, 200).tolist(), *rng.uniform(0, 1, 200).tolist(), *[x / 20000 for x in range(0, 400)],
                *[x + 0.00005 for x in range(0, 50)], 0.99995, 0.99996, 9.99995, -0.00001, 1.4e9, 25620427.0, 0.0, -0.0]
    raw = re.findall(r"\[([^\[\]]*)\]", pd.DataFrame({"v": ujson_in}).to_json(orient="values", double_precision=4))
    csv = {n: hashlib.sha1(df.to_csv(index=False, lineterminator="\n").encode()).hexdigest() for n, df in ctx.tables.items()}
    text = export.to_json(ctx.tables, {**export.meta(core, ctx.year, dict(ctx.weights)), "generated": FIXED_GENERATED})
    tables_w = data.get_export(core, ctx.year, CUSTOM, version)
    picked = ["NGA", "SYR", "ASM", "TUV"]
    hist_w = tables_w["history"]
    return {
        "repr": [{"in": x, "out": repr(float(x))} for x in floats],
        "ujson": [{"in": x, "out": r} for x, r in zip(ujson_in, raw, strict=True)],
        "csv_sha1": csv,
        "json": {"generated": FIXED_GENERATED, "sha1": hashlib.sha1(text).hexdigest(), "length": len(text.decode("utf-8"))},
        "custom": {"index": ctx.table(tables_w["index"]), "history_rows": len(hist_w), "history_iso3": picked,
                   "history_sample": ctx.table(hist_w[hist_w["iso3"].isin(picked)]),
                   "meta_json": export.to_json({}, {**export.meta(core, ctx.year, dict(CUSTOM)), "generated": "2026-01-01T00:00:00+00:00"}).decode()},
    }


def fixtures(ctx) -> None:
    w, version = ctx.write_json, ctx.core["version"]
    out = "tests/fixtures/group10_"
    w(out + "normalise_against.json", {"cases": _normalise_cases(ctx)})
    w(out + "stress.json", _stress_fixture(ctx))
    hist_w = data.get_history(ctx.core, CUSTOM, version)
    readings = {}
    for name, hist in (("default", ctx.history), ("w50_20_20_10", hist_w)):
        readings[name] = {c.key: cases.reading(c, hist, _values_before(ctx, int(c.date[:4]) - 1)) for c in cases.CASES}
    w(out + "cases.json", readings)
    w(out + "builder.json", _builder_fixture(ctx))
    w(out + "export.json", _export_fixture(ctx))
