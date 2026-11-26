"""data/reference/*.json: what the reference pages (introduction, guide, methodology, glossary, sources, video) need
beyond the core files.

- glossary.json: every category and term (prm.glossary.all_terms) with its link, and the legend's colour blocks.
- sources.json: the index cards' load status and indicator links, the indicator-by-indicator rows, the video channel
  rows, and the citation's author and IMF edition.
- video.json: the 24/7 live channels, their regions and the news names used to find videos about a country.
- methodology.json: the escalation-signal constants and, for the track record, the countries in armed conflict each
  year (UCDP's 25 battle deaths), so the browser rebuilds the onset panel for any weights.
- fsi.json: the Fragile States Index benchmark as aggregate statistics only ({compared, spearman, top20_overlap,
  year}, default weights); its data is never stored. A failed download keeps the last good file.

`fixtures(ctx)` writes tests/fixtures/reference_*.json for web/js/charts/reference.js."""

from __future__ import annotations

import re

import pandas as pd
from plotly.colors import sample_colorscale

from prm import charts, config, data, glossary, hotspots, interpret, sources, ui, validation
from staticbuild.charts import _plain, figure
from staticbuild.fixtures import CUSTOM, CUSTOM_NAME

OUT = "data/reference/"
DERIVED = {"battle_deaths_100k": "battle_deaths", "displaced_share": "displaced"}
ORGS = {  # app_pages/sources.py: think tanks, institutions and NGOs (based in, type)
    "Council on Foreign Relations": ("United States", "Non-profit think tank"),
    "International Crisis Group": ("Belgium", "Non-profit think tank"),
    "Carnegie Endowment": ("United States", "Non-profit think tank"),
    "Brookings Institution": ("United States", "Non-profit think tank"),
    "Atlantic Council": ("United States", "Non-profit think tank"),
    "CSIS": ("United States", "Non-profit think tank"),
    "United Nations": ("International", "Intergovernmental organisation"),
    "IMF": ("International", "Intergovernmental organisation"),
    "World Bank": ("International", "Intergovernmental organisation"),
    "ICRC (Red Cross)": ("Switzerland", "Humanitarian organisation"),
    "Human Rights Watch": ("United States", "Non-profit NGO"),
}


def build(ctx) -> None:
    w = ctx.write_json
    w(OUT + "glossary.json", glossary_data())
    w(OUT + "sources.json", sources_data(ctx))
    w(OUT + "video.json", {"live": live_channels(), "regions": config.LIVE_REGIONS, "news_names": config.NEWS_NAMES})
    w(OUT + "methodology.json", {"escalation": escalation(), "conflict": conflict_years(ctx.core)})
    bench = fsi_benchmark(ctx)
    if bench:
        w(OUT + "fsi.json", bench)


# --- Glossary ------------------------------------------------------------------------------------------------------
def _term(t: glossary.Term) -> dict:
    link = None
    if t.source:
        link = {"url": t.url or config.SOURCES[t.source].url,
                "label": "See the data" if t.url else ui.source_label(t.source)}
    return {"term": t.term, "definition": t.definition, "tags": list(t.tags), "pillar": t.pillar, "link": link}


def glossary_data() -> dict:
    blocks = lambda scale: sample_colorscale(scale, [0.2, 0.4, 0.6, 0.8, 1])  # one per tier, as the globe legend
    return {
        "categories": [{"name": name, "color": glossary.CATEGORIES[name].color, "blurb": glossary.CATEGORIES[name].blurb,
                        "sources": list(glossary.CATEGORIES[name].sources), "terms": [_term(t) for t in items]}
                       for name, items in glossary.all_terms().items()],
        "indicators_category": glossary.INDICATORS_CATEGORY,
        "scales": {
            "composite": blocks(config.MAP_COLORSCALE),
            "pillars": {p.key: blocks(config.map_colorscale(p.key)) for p in config.PILLARS},
            "change": [c for _, c in config.CHANGE_COLORSCALE],
            "next_event": [c for _, c in config.reversed_scale(config.map_colorscale("social"))],
        },
    }


# --- Sources -------------------------------------------------------------------------------------------------------
def _status(meta: dict, keys: list[str]) -> str:
    """app_pages/sources.py status(): source update dates and live/snapshot state of the series."""
    loaded = [meta[k] for k in keys if k in meta]
    if not loaded:
        return ""
    dates = sorted({str(m.get("edition") or m.get("last_updated")) for m in loaded
                    if m.get("edition") or m.get("last_updated")})
    live = sum(1 for m in loaded if not m["from_snapshot"] and not m["error"])
    state = "live" if live == len(loaded) else ("saved snapshot" if live == 0 else f"{live} of {len(loaded)} live")
    updated = f"source updated {', '.join(dates)}" if dates else "update date not published"
    return f"Loaded now: {updated} · {state}"


def live_channels() -> dict:
    return {n: {"id": c.id, "region": c.region, "origin": c.origin, "funding": c.funding} for n, c in config.LIVE_CHANNELS.items()}


def sources_data(ctx) -> dict:
    meta, values = ctx.core["meta"], ctx.values
    cards = [{"key": key, "status": _status(meta, [k for k in config.RAW_SERIES if config.series_source(k) == key]),
              "indicators": [{"label": i.short, "url": config.indicator_url(i)}
                             for i in config.INDICATORS if config.indicator_source(i) == key]}
             for key in config.INDEX_SOURCES]
    rows = []
    for ind in config.INDICATORS:
        series = ind.series or DERIVED.get(ind.key)
        m = meta.get(series, {})
        years = values[f"{ind.key}__year"].dropna() if f"{ind.key}__year" in values else pd.Series(dtype=float)
        state = ("Unavailable" if m.get("error") and not m.get("from_snapshot")
                 else "Snapshot" if m.get("from_snapshot") else "Live")
        rows.append({
            "Pillar": config.PILLAR_BY_KEY[ind.pillar].short,
            "Indicator": ind.label,
            "Original source": ind.source,
            "Series code": config.RAW_SERIES[ind.series][1] if ind.series else f"derived from {series} and population",
            "Most common data year": None if years.empty else int(years.astype(int).mode().iloc[0]),
            "Source updated": m.get("edition") or m.get("last_updated") or "—",
            "Status": state,
            "Data": config.indicator_url(ind),
        })
    channels = [
        {"Channel": name, "Content": "24/7 live stream and news reports", "Region": c.region, "Based in": c.origin,
         "Ownership": c.funding, "YouTube": f"https://www.youtube.com/channel/{c.id}"}
        for name, c in config.LIVE_CHANNELS.items()
    ] + [
        {"Channel": name, "Content": "News reports", "Region": c.region, "Based in": c.origin, "Ownership": c.funding,
         "YouTube": f"https://www.youtube.com/channel/{c.id}"}
        for name, c in config.OTHER_NEWS_CHANNELS.items()
    ] + [
        {"Channel": name, "Content": "Analysis and explainers" if name in config.ANALYSIS_VIDEO_CHANNELS
         else "Institutional briefings", "Region": "—", "Based in": ORGS.get(name, ("—", "—"))[0],
         "Ownership": ORGS.get(name, ("—", "—"))[1], "YouTube": f"https://www.youtube.com/channel/{cid}"}
        for name, cid in {**config.ANALYSIS_VIDEO_CHANNELS, **config.INSTITUTION_VIDEO_CHANNELS}.items()
    ]
    parts = config.AUTHOR.split()
    edition = (meta.get("gdp_growth", {}).get("edition") or "World Economic Outlook").replace(" (", ", ").rstrip(")")
    return {
        "index_cards": cards,
        "indicators": ctx.table(pd.DataFrame(rows)),
        "channels": channels,
        "countries_state": "saved snapshot" if ctx.core.get("countries_from_snapshot") else "live",
        "cite": {"author": f"{parts[-1]}, {' '.join(p[0] + '.' for p in parts[:-1])}", "edition": edition},
    }


# --- Methodology ---------------------------------------------------------------------------------------------------
def escalation() -> dict:
    return {"window_days": hotspots.WINDOW_DAYS, "recent_days": hotspots.RECENT_DAYS,
            "escalating_ratio": hotspots.ESCALATING_RATIO, "escalating_z": hotspots.ESCALATING_Z,
            "mad_scale": hotspots.MAD_SCALE, "easing_ratio": hotspots.EASING_RATIO,
            "min_articles_7d": hotspots.MIN_ARTICLES_7D}


def conflict_years(core: dict) -> dict | None:
    """validation.onset_panel's inputs beyond the history: the last UCDP year and, per year, the countries in armed
    conflict (the same pivot and threshold)."""
    deaths = core["series"].get("battle_deaths")
    if deaths is None or deaths.empty:
        return None
    table = deaths.pivot_table(index="iso3", columns="year", values="value", aggfunc="first")
    in_conflict = table.fillna(0) >= validation.CONFLICT_DEATHS
    return {"last": int(deaths["year"].max()),
            "years": {str(int(y)): sorted(in_conflict.index[in_conflict[y]]) for y in in_conflict.columns
                      if y >= config.HISTORY_START}}


def fsi_benchmark(ctx) -> dict | None:
    """The page's three numbers with the default weights, or None (the last good fsi.json stays) if the download
    fails. Only these aggregates are written; the FSI values themselves never leave this function."""
    try:
        fsi = sources.fetch_fsi(config.FSI_URL, ctx.core["countries"])
    except Exception as exc:  # any failure: keep what was there
        print(f"fsi: {exc}")
        return None
    if fsi is None or fsi.empty:
        print("fsi: empty answer")
        return None
    year = int(fsi["year"].mode().iloc[0])
    ours = ctx.history[ctx.history["year"] == year][["iso3", "composite", "tier"]].dropna(subset=["composite"])
    both = fsi.merge(ours, on="iso3").rename(columns={"total": "fsi", "composite": "score"})
    if both.empty:
        print(f"fsi: no country in common for {year}")
        return None
    top_fsi, top_ours = set(both.nlargest(20, "fsi")["iso3"]), set(both.nlargest(20, "score")["iso3"])
    return {"compared": len(both), "spearman": float(both["fsi"].rank().corr(both["score"].rank())),
            "top20_overlap": len(top_fsi & top_ours), "year": year}


# --- Parity fixtures -----------------------------------------------------------------------------------------------
def _track(t: dict) -> dict | None:
    if not t:
        return None
    by = t["by_fifth"]
    return {
        "years": list(t["years"]), "cases": t["cases"], "onsets": t["onsets"], "base_rate": t["base_rate"],
        "auc": t["auc"], "top_fifth_share": t["top_fifth_share"], "top_two_fifths_share": t["top_two_fifths_share"],
        "by_fifth": [{"fifth": f, **{k: (None if pd.isna(by.loc[f, k]) else by.loc[f, k]) for k in ("mean", "sum", "size")}}
                     for f in range(1, 6)],
        "onset_list": [{"iso3": r.iso3, "year": int(r.year), "score": r.score, "onset": bool(r.onset), "fifth": int(r.fifth)}
                       for r in t["onset_list"].itertuples()],
    }


VIDEOS = [  # made-up titles covering the matching rules of ui.videos_about
    ("South Sudan talks resume in Juba", ""), ("Sudan: fighting near Khartoum", ""),
    ("Sudanese refugees cross into Chad", "Aid groups warn of shortages."),
    ("US election results", ""), ("Inside the U.S. Senate", ""), ("Why the us vs them story sells", ""),
    ("American voters on prices", ""), ("Britain and the EU", "A UK view."), ("British farmers protest", ""),
    ("Türkiye's central bank", ""), ("Turkey hikes rates", "Turkish lira slides."), ("Côte d'Ivoire votes", ""),
    ("Ivory Coast election", ""), ("DRC: M23 advance", ""), ("Congolese troops", ""), ("Republic of the Congo port", ""),
    ("Niger coup anniversary", ""), ("Nigerien junta", ""), ("Nigeria fuel subsidy", ""), ("Nigerian banks", ""),
    ("India and Pakistan", "New Delhi and Islamabad talk."), ("Gaza ceasefire", "Palestinian officials said."),
    ("Weather today", "Nothing about any country."), ("Guinea-Bissau result", ""), ("Equatorial Guinea oil", ""),
    ("Guinea junta sets a vote", ""), ("Dominica after the storm", ""), ("Dominican Republic tourism", ""),
]
VIDEO_COUNTRIES = ["SDN", "SSD", "TCD", "USA", "GBR", "TUR", "CIV", "COD", "COG", "NER", "NGA", "IND", "PAK", "PSE",
                   "GIN", "GNB", "GNQ", "DMA", "DOM", "NOR"]
QUERIES = ["tier", "Inflation", "WGI", "IDP", "red flag", "  rank ", "zzz", "(", "ü", "c.i.", "%"]
MARKS = [("Rule of law", "law"), ("Inflation (annual %)", "("), ("WGI score, WGI", "wgi"), ("Türkiye", "Ü"),
         ("a.b.c", "."), ("No match", "zzz")]


def _tier_rows(table: pd.DataFrame) -> list[dict]:
    """app_pages/guide.py, section 2."""
    rows = []
    for tier, upper in zip(config.TIERS, [t.lower for t in config.TIERS[1:]] + [100]):
        in_tier = table[table["tier"] == tier.label].sort_values("composite", ascending=False)
        summary, ground = interpret.TIER_MEANING[tier.label]
        rows.append({"Tier": tier.label, "Score": f"{int(tier.lower)}–{int(upper)}",
                     "What it looks like": f"{summary} {ground}", "Countries now": len(in_tier),
                     "For example": ", ".join(in_tier["name"].head(3))})
    return rows


def _flag_rows(values: pd.DataFrame) -> list[dict]:
    """app_pages/guide.py, section 4."""
    ops = {">=": lambda a, b: a >= b, "<": lambda a, b: a < b, "<=": lambda a, b: a <= b}
    rows = []
    for key, op, threshold, severity, label in config.RED_FLAGS:
        if key not in interpret.FLAG_MEANING or key not in values:
            continue
        meaning, response = interpret.FLAG_MEANING[key]
        rows.append({"Severity": config.SEVERITY_LABEL[severity], "Threshold": label, "In real life": meaning,
                     "Common response": response,
                     "Countries now": int(ops[op](pd.to_numeric(values[key], errors="coerce"), threshold).sum())})
    return rows


def _search(query: str) -> dict:
    """app_pages/glossary.py search: the hits per category and the caption."""
    q = query.strip().lower()
    hits = {cat: [t.term for t in items if q in t.text.lower()] for cat, items in glossary.all_terms().items()}
    hits = {cat: items for cat, items in hits.items() if items}
    found = sum(len(v) for v in hits.values())
    return {"query": query, "caption": f"{found} matching term{'s' if found != 1 else ''} in {len(hits)} "
                                       f"categor{'ies' if len(hits) != 1 else 'y'}.",
            "categories": [{"name": cat, "terms": items} for cat, items in hits.items()]}


def fixtures(ctx) -> None:
    w, core, version = ctx.write_json, ctx.core, ctx.core["version"]
    out = "tests/fixtures/"
    deaths = core["series"].get("battle_deaths")
    cases = []
    for name, weights in (("default", tuple((k, float(v)) for k, v in ctx.weights.items())), (CUSTOM_NAME, CUSTOM)):
        hist = data.get_history(core, weights, version)
        for score in ("stability", "composite"):
            t = validation.summary(validation.onset_panel(hist, deaths, score))
            fig = charts.onset_fifths(t["by_fifth"], t["base_rate"], config.PILLAR_COLORS["stability"])
            cases.append({"weights": name, "score": score, "summary": _track(t), "figure": _plain(figure(fig))})
    w(out + "reference_track.json", {"conflict": conflict_years(core), "cases": cases})

    countries = core["countries"]
    names = dict(zip(countries["iso3"], countries["name"]))
    official = dict(zip(countries["iso3"], countries["official_name"]))
    videos = pd.DataFrame(VIDEOS, columns=["title", "description"])
    w(out + "reference_videos.json", {
        "videos": videos.to_dict("records"), "aliases": config.VIDEO_ALIASES, "news_names": config.NEWS_NAMES,
        "cases": [{"iso3": i, "hits": [int(k) for k in ui.videos_about(videos, i, names, official.get(i)).index]}
                  for i in VIDEO_COUNTRIES]})

    w(out + "reference_glossary.json", {
        "cases": [_search(q) for q in QUERIES],
        "marks": [{"text": t, "query": q, "parts": re.split(f"({re.escape(q)})", t, flags=re.I)} for t, q in MARKS]})

    scores_w = data.get_scores(core, ctx.year, CUSTOM, version)
    master = ui.master_table(core, ctx.values, ctx.scores, ctx.history)
    master_w = ui.master_table(core, ctx.values, scores_w, data.get_history(core, CUSTOM, version))
    w(out + "reference_guide.json", {"tiers": {"default": _tier_rows(master), CUSTOM_NAME: _tier_rows(master_w)},
                                     "flags": _flag_rows(ctx.values)})
