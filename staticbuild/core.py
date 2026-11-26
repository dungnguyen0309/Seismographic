"""The shared data files (web/data/*.json, tokens.css) and the static API (web/api/v1/*), see docs/static-site.md."""

import dataclasses
import itertools
import json
import re

from prm import api, export, scoring, ui

API = "api/v1"
FILTERS = ("region", "income", "tier")  # query keys of /api/v1/countries, also the columns of the index table


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def pattern(text: str) -> str:
    """A regex valid in JS, PCRE and RE2 that matches `text` case-insensitively, a space also as '+': no (?i) flag."""
    def one(ch: str) -> str:
        if ch == " ":
            return "[ +]"
        if ch.isalpha():
            return f"[{ch.upper()}{ch.lower()}]"
        return "\\" + ch if ch in r".*+?^${}()|[]\/" else ch
    return "^" + "".join(map(one, text)) + "$"


def config_json(ctx) -> dict:
    """Everything a JS port of the scoring and the pages reads from prm/config.py."""
    c = ctx.config
    regions = sorted(ctx.core["countries"]["region"].dropna().unique())
    return {
        "APP_TITLE": c.APP_TITLE, "APP_TAGLINE": c.APP_DESCRIPTION, "AUTHOR": c.AUTHOR, "MONO_FONT": c.MONO_FONT,
        "pillars": [{**dataclasses.asdict(p), "color": c.PILLAR_COLORS[p.key], "ramp": c.PILLAR_RAMPS[p.key]}
                    for p in c.PILLARS],
        "indicators": [{**dataclasses.asdict(i), "source_key": c.indicator_source(i), "url": c.indicator_url(i)}
                       for i in c.INDICATORS],
        "series": {k: {"provider": p, "code": code, "options": opt, "source_key": c.series_source(k),
                       "url": c.series_url(k)} for k, (p, code, opt) in c.RAW_SERIES.items()},
        "WGI_DIMENSIONS": c.WGI_DIMENSIONS,
        "tiers": [dataclasses.asdict(t) for t in c.TIERS],
        "INK": c.INK, "PILLAR_COLORS": c.PILLAR_COLORS, "PILLAR_RAMPS": c.PILLAR_RAMPS,
        "COUNTRY_COLORS": c.COUNTRY_COLORS, "MAX_COMPARE": c.MAX_COMPARE, "FORECAST_GREY": c.FORECAST_GREY,
        "MAP_COLORSCALE": c.MAP_COLORSCALE, "CHANGE_COLORSCALE": c.CHANGE_COLORSCALE,
        "NO_DATA_COLOR": c.NO_DATA_COLOR, "OCEAN_COLOR": c.OCEAN_COLOR,
        "SEVERITY_COLOR": c.SEVERITY_COLOR, "SEVERITY_LABEL": c.SEVERITY_LABEL, "SEVERITY_ORDER": c.SEVERITY_ORDER,
        "RED_FLAGS": [list(f) for f in c.RED_FLAGS],
        "FLAG_BASIS": [{"key": k, "threshold": t, "source": s, "basis": b} for (k, t), (s, b) in c.FLAG_BASIS.items()],
        "FLAG_SHORT": [{"key": k, "threshold": t, "short": s} for (k, t), s in c.FLAG_SHORT.items()],
        "ESTIMATIVE_LANGUAGE": [list(e) for e in c.ESTIMATIVE_LANGUAGE],
        "LOG_CAP_QUANTILE": c.LOG_CAP_QUANTILE, "PILLAR_MIN_SHARE": c.PILLAR_MIN_SHARE,
        "COMPOSITE_MIN_PILLARS": c.COMPOSITE_MIN_PILLARS, "HISTORY_START": c.HISTORY_START,
        "WGI_TREND_YEARS": c.WGI_TREND_YEARS, "WGI_TREND_THRESHOLD": c.WGI_TREND_THRESHOLD,
        "TREND_THRESHOLD": ui.TREND_THRESHOLD,
        "regions": [{"name": r, "short": c.region_short(r), "center": list(c.REGION_CENTERS[r])} for r in regions],
        "SOURCE_LABELS": c.SOURCE_LABELS, "SOURCES": {k: dataclasses.asdict(s) for k, s in c.SOURCES.items()},
        "CITE_LABELS": c.CITE_LABELS, "INDEX_SOURCES": c.INDEX_SOURCES, "SOURCE_GROUPS": c.SOURCE_GROUPS,
        "CROSS_CHECKS": c.CROSS_CHECKS, "NO_FLAG": sorted(c.NO_FLAG),
    }


def tokens_css(ctx) -> str:
    c = ctx.config
    vars_ = {**c.INK, **{f"pillar-{k}": v for k, v in c.PILLAR_COLORS.items()},
             **{f"tier-{t.label.lower()}": t.color for t in c.TIERS},
             **{f"country-{i}": v for i, v in enumerate(c.COUNTRY_COLORS, 1)},
             **{f"severity-{k}": v for k, v in c.SEVERITY_COLOR.items()}}
    return ":root{" + ";".join(f"--sg-{k}:{v}" for k, v in vars_.items()) + "}\n"


def wgi_trends(ctx) -> dict:
    """The political-stability trend per economy: the red flag on the profile and flag_counts need the raw WGI series."""
    out = {i: scoring.wgi_trend(ctx.core["series"], i, "pv") for i in ctx.core["countries"]["iso3"]}
    return {i: t for i, t in out.items() if t}


def api_files(ctx) -> None:
    """The prm/api.py payloads as files; ?region=, ?income=, ?tier= are pre-filtered files picked by vercel.json."""
    tables, meta = ctx.tables, ctx.api_meta
    index = tables["index"]
    records = lambda df: {"meta": meta, "count": len(df), "countries": export.records(df)}  # noqa: E731
    ctx.write_json(f"{API}/index.json", {"meta": meta, "endpoints": {
        "countries": f"/{API}/countries", "country": f"/{API}/countries/{{iso3}}", "dictionary": f"/{API}/dictionary",
    }, "filters": {"region": "World Bank region", "income": "World Bank income group",
                   "tier": ", ".join(ctx.config.TIER_ORDER)}})
    ctx.write_json(f"{API}/countries.json", records(index))
    ctx.write_json(f"{API}/dictionary.json", {"fields": export.records(export.dictionary_table())})
    for iso3 in index["iso3"]:
        pick = {name: tables[name][tables[name]["iso3"] == iso3].drop(columns=["iso3", "name"], errors="ignore")
                for name in ("indicators", "red_flags", "history", "conflict_outlook")}
        outlook = export.records(pick["conflict_outlook"])
        ctx.write_json(f"{API}/countries/{iso3}.json", {
            "meta": meta, "country": export.records(index[index["iso3"] == iso3])[0],
            "indicators": export.records(pick["indicators"]), "red_flags": export.records(pick["red_flags"]),
            "history": export.records(pick["history"]), "conflict_outlook": outlook[0] if outlook else None})
    write_rewrites(ctx, filter_rules(ctx, index, records))


def filter_rules(ctx, index, records) -> list[dict]:
    """Exact parity with prm/api.py's ?region=&income=&tier= (all given filters must match, case-insensitively, an
    unknown value gives an empty list) as pre-filtered files picked by `has`/`missing` rules, most specific first:
    all three keys, every pair (third key missing), every single key (others missing), then any other use of a
    filter key answers the empty list."""
    values = {k: sorted(index[k].dropna().unique()) for k in FILTERS}
    for key, vals in values.items():
        assert len({slug(v) for v in vals}) == len(vals), f"two {key} values share a slug"
    source = f"/{API}/countries"
    empty = f"{API}/countries.empty.json"
    ctx.write_json(empty, records(index.iloc[0:0]))
    rules = []
    for size in (3, 2, 1):
        for keys in itertools.combinations(FILTERS, size):
            for combo in itertools.product(*(values[k] for k in keys)):
                rows = index
                for key, value in zip(keys, combo):
                    rows = rows[rows[key].fillna("").str.lower() == value.lower()]
                if rows.empty:
                    continue  # the catch-alls answer the empty list
                name = f"{API}/countries." + ".".join(f"{k}-{slug(v)}" for k, v in zip(keys, combo)) + ".json"
                ctx.write_json(name, records(rows))
                rule = {"source": source, "has": [{"type": "query", "key": k, "value": pattern(v)}
                                                  for k, v in zip(keys, combo)]}
                if len(keys) < len(FILTERS):
                    rule["missing"] = [{"type": "query", "key": k} for k in FILTERS if k not in keys]
                rules.append({**rule, "destination": f"/{name}"})
    rules += [{"source": source, "has": [{"type": "query", "key": k}], "destination": f"/{empty}"} for k in FILTERS]
    return rules


def write_rewrites(ctx, rules: list[dict]) -> None:
    """Put the filter rules into web/vercel.json before the plain /api/v1/countries rewrite, keeping everything else.
    The plain rewrite serves only requests that use none of the filter keys."""
    path = ctx.web / "vercel.json"
    config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    plain = {"source": f"/{API}/countries", "destination": f"/{API}/countries.json"}
    keep = [r for r in config.get("rewrites", []) if not (r.get("source") == plain["source"] and r.get("has"))]
    at = next((i for i, r in enumerate(keep) if r == plain), None)
    if at is None:
        keep.append(plain)
        at = len(keep) - 1
    config["rewrites"] = keep[:at] + rules + keep[at:]
    lines = []
    for key, value in config.items():  # one rule per line, as the file is written by hand
        if isinstance(value, list):
            body = ",\n".join("    " + json.dumps(e, ensure_ascii=False) for e in value)
            lines.append(f'  "{key}": [\n{body}\n  ]')
        else:
            lines.append(f'  "{key}": {json.dumps(value, ensure_ascii=False)}')
    path.write_text("{\n" + ",\n".join(lines) + "\n}\n", encoding="utf-8", newline="\n")


def build(ctx) -> None:
    w, t = ctx.write_json, ctx.table
    outlook = ctx.outlook
    w("data/meta.json", {"built": ctx.built, "year": ctx.year, "version": ctx.core["version"],
                         "loaded_at": ctx.core["loaded_at"], "snapshot": ctx.core.get("snapshot_date"),
                         "series": ctx.core["meta"]})
    w("data/config.json", config_json(ctx))
    w("data/countries.json", t(ctx.core["countries"]))
    w("data/values.json", t(ctx.values))  # full precision: the JS scoring must reproduce Python to 1e-9
    w("data/scores.json", t(ctx.scores))
    w("data/history.json", t(ctx.history))
    w("data/master.json", t(ui.master_table(ctx.core, ctx.values, ctx.scores, ctx.history).drop(columns="flag")))
    w("data/outlook.json", {
        "predictions": t(outlook.predictions), "base_rate": outlook.base_rate, "coefficients": dict(outlook.coefficients),
        "backtest": t(outlook.backtest), "auc": outlook.auc, "brier_skill": outlook.brier_skill,
        "calibration": t(outlook.calibration), "data_year": outlook.data_year, "index_year": outlook.index_year,
    } if outlook is not None else None)
    w("data/wgi_trend.json", wgi_trends(ctx))
    (ctx.data / "tokens.css").write_text(tokens_css(ctx), encoding="utf-8", newline="\n")
    api_files(ctx)
