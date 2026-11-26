"""Country profiles: data/country/<ISO3>.json for every country, holding what app_pages/country.py shows that depends
on no visitor choice: the WGI and macro figures (the WGI series and their confidence intervals are drawn in the WGI
figure), the governance trend table, the stability flag, the conflict outlook line, the next-year IMF growth figure
for the brief, the news name, the What-if controls and the "Elsewhere" links.

fixtures(ctx) writes web/tests/fixtures/country_cases.json: what the page computes from the visitor's weights, preset
or peer group (peer ranking, similar profiles, What-if results, sensitivity, regional medians), the indicators CSV and
the refugee-flow lists, for the parity tests of web/js/charts/country.js. The page-level steps are restated here
(page_* functions) and checked against the running page by tests/test_staticbuild_country.py."""

from __future__ import annotations

import math

import pandas as pd

from prm import charts, config, data, scoring, ui
from staticbuild.charts import _stable_sorts, figure

BATTLE_DEATH_STEPS = [0, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000]
WHATIF_PRESETS = {  # app_pages/country.py
    "Currency crisis": {"inflation": ("max", 40), "reserves_months": ("min", 2), "gdp_growth": ("min", -3),
                        "current_account": ("min", -6)},
    "Armed conflict": {"battle_deaths_raw": ("max", 2500), "wgi_pv": ("add", -15), "displaced_share": ("max", 5)},
    "Democratic backsliding": {"wgi_va": ("add", -15), "wgi_rl": ("add", -10), "wgi_cc": ("add", -10),
                               "wgi_ge": ("add", -5)},
    "Reform & recovery": {"inflation": ("min", 5), "gdp_growth": ("max", 4), "wgi_ge": ("add", 10),
                          "wgi_rl": ("add", 10), "wgi_cc": ("add", 10)},
}


def wgi_ci() -> dict[str, pd.DataFrame]:
    """The WGI confidence intervals from the snapshot (data.load_wgi_ci without its live fallback)."""
    return {key: df for key in config.WGI_CI_SERIES if (df := data._read_snapshot(key)) is not None and not df.empty}


def whatif_controls(values: pd.DataFrame, iso3: str) -> dict:
    """The What-if sliders (_whatif_controls in the page), in its order, and the indicators it has no data for."""
    v = values.loc[iso3]
    controls = []
    for ind in config.SCORED_INDICATORS:
        if ind.key == "battle_deaths_100k":  # people think in deaths, not deaths per 100k
            raw, pop = v.get("battle_deaths_raw"), v.get("population")
            if pd.isna(raw) or pd.isna(pop) or pop <= 0:
                continue
            current = int(round(raw))
            controls.append({
                "key": "battle_deaths_raw", "pillar": ind.pillar, "label": "Battle-related deaths per year",
                "kind": "select", "current": current, "options": sorted(set(BATTLE_DEATH_STEPS) | {current}),
                "per_death": v["battle_deaths_100k"] / raw if raw > 0 else 100_000 / pop,
            })
            continue
        current = v.get(ind.key)
        if pd.isna(current):
            continue
        column = pd.to_numeric(values[ind.key], errors="coerce").dropna()
        lo, hi = (0.0, 100.0) if ind.key.startswith("wgi_") else (column.quantile(0.01), column.quantile(0.99))
        controls.append({
            "key": ind.key, "pillar": ind.pillar, "label": f"{ind.short} ({ind.unit})", "kind": "slider",
            "current": round(float(current), 1), "min": float(math.floor(min(lo, current))),
            "max": float(math.ceil(max(hi, current))),
            "help": "Higher = riskier" if ind.higher_is_riskier else "Lower = riskier",
        })
    keys = {c["key"] for c in controls}
    missing = [i.short for i in config.SCORED_INDICATORS
               if i.key not in keys and not (i.key == "battle_deaths_100k" and "battle_deaths_raw" in keys)]
    return {"controls": controls, "missing": missing}


def governance_table(series: dict, ci: dict, iso3: str) -> dict | None:
    """The table under the WGI figure: start and end of the trend window per dimension and whether the change is clear."""
    rows = []
    for dim in config.WGI_DIMENSIONS:
        t = scoring.wgi_trend(series, iso3, dim)
        if not t:
            continue
        overlap = scoring.ci_overlap(series, ci, iso3, dim, t["start_year"], t["end_year"])
        rows.append({
            "Dimension": config.INDICATOR_BY_KEY[f"wgi_{dim}"].short,
            f"Score {t['start_year']}": round(t["start"], 1),
            f"Score {t['end_year']}": round(t["end"], 1),
            "Change": round(t["change"], 1),
            "Statistically clear?": "—" if overlap is None else ("No (intervals overlap)" if overlap else "Yes"),
        })
    if not rows:
        return None
    frame = pd.DataFrame(rows)  # dimensions with other windows leave gaps, as in the page's table
    return {"columns": list(frame.columns),
            "rows": [[None if isinstance(x, float) and math.isnan(x) else x for x in r] for r in frame.itertuples(index=False)]}


def outlook_line(outlook, iso3: str) -> dict | None:
    """The Summary's conflict outlook: {level: severity mark or null, text} (None: no outlook for the country)."""
    mine = outlook.predictions.set_index("iso3").reindex([iso3]).iloc[0]
    if not isinstance(mine["status"], str):
        return None
    if mine["status"] == "In armed conflict":
        return {"level": None, "text": f"In armed conflict in the latest data ({outlook.data_year})."}
    level = ("serious" if mine["relative"] >= 3 else "warning") if mine["relative"] >= 1 else None
    return {"level": level, "text": f"A {mine['probability']:.1%} chance that armed conflict breaks out in "
                                    f"{outlook.index_year + 1}: {mine['relative']:.1f}× the average for a country at peace."}


def elsewhere(row: pd.Series, iso3: str) -> list[list[str]]:
    """Other profiles of the country (the caption under the tabs)."""
    links = ([["World Bank", f"https://data.worldbank.org/country/{row['iso2']}"]] if isinstance(row["iso2"], str) else []) + [
        ["IMF", f"https://www.imf.org/en/countries/{iso3.lower()}"],
        ["ReliefWeb", f"https://reliefweb.int/country/{iso3.lower()}"]]
    if row["income"] != "High income":  # FAO's food-security briefs cover developing countries
        links.append(["FAO food security", f"https://www.fao.org/giews/countrybrief/country.jsp?code={iso3}"])
    return links


def profile(ctx, iso3: str, ci: dict, countries: pd.DataFrame) -> dict:
    series = ctx.core["series"]
    row = countries.loc[iso3]
    nxt = scoring._next_year_value(series, "gdp_growth", iso3, ctx.year + 1)
    return {
        "iso3": iso3,
        "news_name": config.NEWS_NAMES.get(iso3, row["name"]),
        "next_growth": nxt,
        "stability_flags": scoring.stability_flags(series, iso3),
        "outlook": outlook_line(ctx.outlook, iso3),
        "whatif": whatif_controls(ctx.values, iso3),
        "governance": governance_table(series, ci, iso3),
        "elsewhere": elsewhere(row, iso3),
        "figures": {"wgi": figure(charts.wgi_small_multiples(series, ci, iso3)),
                    "macro": figure(charts.macro_small_multiples(series, iso3, ctx.year))},
    }


def build(ctx, only: list[str] | None = None) -> None:
    ci = wgi_ci()
    countries = ctx.core["countries"].set_index("iso3", drop=False)
    for iso3 in only or countries.index:
        ctx.write_json(f"data/country/{iso3}.json", profile(ctx, iso3, ci, countries))


# ---------------------------------------------------------------------------------------------------------------------
# The page's own steps, restated for the fixtures (tests/test_staticbuild_country.py checks them against the page)
# ---------------------------------------------------------------------------------------------------------------------
def page_meta(values, scores, table, iso3: str) -> str:
    """The line under the country's name, after the top flag."""
    row, v, s = table.set_index("iso3").loc[iso3], values.loc[iso3], scores.loc[iso3]
    meta = [str(row["region"]), str(row["income"]), f"{ui.fmt_population(v.get('population'))} people"]
    if pd.notna(v.get("gdppc")):
        meta.append(f"${v['gdppc']:,.0f} per person (IMF, {int(v['gdppc__year'])})")
    if ui.thin_data(table[table["iso3"] == iso3]).any():
        missing = [p.short for p in config.PILLARS if pd.isna(row[p.key])]
        meta.append(f"data coverage {s['coverage']:.0f}%" + (f", no {' or '.join(missing)} score" if missing else "")
                    + ": read with care")
    return " · ".join(meta)


def page_peers(table, scores, iso3: str) -> dict:
    """Peer ranking for each "Compare with" group: the place line, the 11 rows shown and the caption."""
    row, s = table.set_index("iso3").loc[iso3], scores.loc[iso3]
    name = row["name"]
    groups = {
        f"Region · {row['region']}": table[table["region"] == row["region"]],
        f"Income group · {row['income']}": table[table["income"] == row["income"]],
        "All countries": table,
    }
    out = {}
    for label, peer_df in groups.items():
        ranked = peer_df.dropna(subset=["composite"]).sort_values("composite", ascending=False).reset_index(drop=True)
        position = ranked.index[ranked["iso3"] == iso3]
        place = sr = None
        if len(position):
            place = (f"Highest risk of {len(ranked)}" if position[0] == 0
                     else f"{scoring._ordinal(position[0] + 1)} highest risk of {len(ranked)}")
            place = f"{place} in this group (group median {ranked['composite'].median():.0f})."
            sr = (f" In the chart, {name} scores {s['composite']:.0f} of 100; the group's scores run from "
                  f"{ranked['composite'].min():.0f} to {ranked['composite'].max():.0f}.")
        start = max(0, min((position[0] if len(position) else 0) - 5, len(ranked) - 11))
        shown = ranked.iloc[start:start + 11]
        out[label] = {"place": place, "sr": sr, "rows": [[i, start + k + 1] for k, i in enumerate(shown["iso3"])],
                      "caption": f"▶ marks {name}. Group ranks {start + 1} to {start + len(shown)} of {len(ranked)}."}
    return out


def page_similar(scores, iso3: str) -> list:
    like = scoring.similar(scores, iso3, n=8)
    return [[i, float(min(max(100 - d, 0), 100))] for i, d in like["distance"].items()]


def apply_preset(name: str, controls: list[dict]) -> dict:
    """_apply_preset: the slider values a preset button sets (from the country's own values)."""
    specs = {c["key"]: c for c in controls}
    out = {}
    for key, (op, amount) in WHATIF_PRESETS[name].items():
        if key not in specs:
            continue
        spec = specs[key]
        base = spec["current"]
        new = max(base, amount) if op == "max" else min(base, amount) if op == "min" else base + amount
        out[key] = (min(spec["options"], key=lambda o: abs(o - new)) if spec["kind"] == "select"
                    else round(min(max(new, spec["min"]), spec["max"]), 1))
    return out


def whatif_result(values, scores, weights: dict, iso3: str, name: str, controls: list[dict], set_to: dict,
                  picked: str | None) -> dict:
    """What the What-if shows for some slider values: the changed inputs and the scenario's numbers and lines."""
    changes, moved = {}, []
    for pillar in config.PILLARS:
        for spec in [c for c in controls if c["pillar"] == pillar.key]:
            value = set_to.get(spec["key"], spec["current"])
            if value != spec["current"]:
                moved.append(spec["label"].split(" (")[0])
                if spec["key"] == "battle_deaths_raw":
                    changes["battle_deaths_raw"] = float(value)
                    changes["battle_deaths_100k"] = value * spec["per_death"]
                else:
                    changes[spec["key"]] = float(value)
    s = scores.loc[iso3]
    out = {"changes": changes, "moved": moved}
    if pd.isna(s["composite"]):
        return {**out, "scored": False}
    new_scores, new_values = scoring.simulate(values, iso3, changes, weights)
    n = new_scores.loc[iso3]
    score_delta = n["composite"] - s["composite"]
    rank_delta = int(n["rank"] - s["rank"])
    riskier = rank_delta < 0
    new_flags, eased = scoring.flag_changes(values.loc[iso3], new_values)
    caption = None
    if moved:
        caption = (f"Scenario: {picked}. " if picked else "") + "Changed: " + ", ".join(moved) + "."
    elif picked:
        caption = f"Scenario: {picked}. No value differs from {name}'s own data."
    return {**out, "scored": True, "composite": n["composite"], "rank": int(n["rank"]), "n_ranked": int(n["n_ranked"]),
            "tier": n["tier"], "pillars": {p.key: n[p.key] for p in config.PILLARS},
            "score_value": f"{n['composite']:.0f}",
            "score_change": f"{score_delta:+.1f}" if round(score_delta, 1) else None,
            "places": (f"{abs(rank_delta)} place{'s' if abs(rank_delta) > 1 else ''} {'riskier' if riskier else 'safer'}"
                       if rank_delta else None),
            "riskier": riskier, "was": s["tier"] if n["tier"] != s["tier"] else None,
            "new_flags": [f["label"] for f in new_flags], "cleared": sorted({f["label"] for f in eased}),
            "caption": caption}


def indicator_rows(values, scores, iso3: str) -> list[dict]:
    v, s = values.loc[iso3], scores.loc[iso3]
    rows = []
    for ind in config.INDICATORS:
        yr = v.get(f"{ind.key}__year")
        rows.append({
            "Indicator": ind.short, "Value": ind.fmt(v.get(ind.key)), "Risk score": s.get(f"n_{ind.key}"),
            "Year": "—" if pd.isna(yr) else str(int(yr)), "Pillar": config.PILLAR_BY_KEY[ind.pillar].short,
            "Unit": ind.unit, "Source": ind.source, "Data": config.indicator_url(ind), "Full name": ind.label,
            "Direction": "Higher = riskier" if ind.higher_is_riskier else "Lower = riskier",
        })
    return rows


def indicators_csv(values, scores, name: str, iso3: str) -> str:
    """The "Download indicators (CSV)" file (Linux line ends, as the deployed app wrote it), without the BOM."""
    return pd.DataFrame(indicator_rows(values, scores, iso3)).assign(Country=name, ISO3=iso3).to_csv(
        index=False, lineterminator="\n")


def page_flows(flows: pd.DataFrame, names: dict, iso3: str) -> dict:
    """The two refugee lists under the Peers map: the top 10 rows of each side and the total line."""
    year = int(flows["year"].max())
    out = {}
    for side, other in (("origin", "host"), ("host", "origin")):
        links = flows[(flows[side] == iso3) & flows[other].isin(names)].nlargest(10, "value")
        total = flows.loc[flows[side] == iso3, "value"].sum()
        out[side] = {"rows": [[o, int(val)] for o, val in zip(links[other], links["value"])],
                     "total": (f"{'About ' if total >= 1000 else ''}{scoring._about(total)} people in total ({year}, "
                               "UNHCR: refugees, asylum seekers and others in need of international protection).")}
    return out


CASES = ["NGA", "SYR", "NOR", "USA", "TUR", "ASM"]  # TUR: high inflation (a flag clears); ASM: no composite score


def fixtures(ctx) -> None:
    from staticbuild.fixtures import CUSTOM, CUSTOM_NAME

    names = dict(zip(ctx.core["countries"]["iso3"], ctx.core["countries"]["name"]))
    flows = ctx.core.get("flows")
    weightings = {"default": (dict(ctx.weights), ctx.scores, ctx.history)}
    custom_scores = scoring.compute_scores(ctx.values, dict(CUSTOM))
    weightings[CUSTOM_NAME] = (dict(CUSTOM), custom_scores, data.get_history(ctx.core, CUSTOM, ctx.core["version"]))
    out = {"countries": {}, "weights": {}}
    with _stable_sorts():
        for iso3 in CASES:
            controls = whatif_controls(ctx.values, iso3)["controls"]
            out["countries"][iso3] = {
                "meta": page_meta(ctx.values, ctx.scores, ui.master_table(ctx.core, ctx.values, ctx.scores, ctx.history), iso3),
                "csv": indicators_csv(ctx.values, ctx.scores, names[iso3], iso3),
                "flows": page_flows(flows, names, iso3),
                "presets": {p: apply_preset(p, controls) for p in WHATIF_PRESETS},
            }
        for label, (weights, scores, hist) in weightings.items():
            table = ui.master_table(ctx.core, ctx.values, scores, hist)
            per = out["weights"][label] = {}
            for iso3 in CASES:
                controls = whatif_controls(ctx.values, iso3)["controls"]
                region = table[table["region"] == table.set_index("iso3").loc[iso3, "region"]]
                sens = scoring.sensitivity(ctx.values, iso3, weights).round(1)
                whatif = {"none": whatif_result(ctx.values, scores, weights, iso3, names[iso3], controls, {}, None)}
                for p in WHATIF_PRESETS:
                    whatif[p] = whatif_result(ctx.values, scores, weights, iso3, names[iso3], controls,
                                              apply_preset(p, controls), p)
                per[iso3] = {
                    "sensitivity": sens.astype(object).where(sens.notna(), None).to_dict("records"),
                    "regional_median": {p.key: region[p.key].median() for p in config.PILLARS},
                    "peers": page_peers(table, scores, iso3),
                    "similar": page_similar(scores, iso3),
                    "whatif": whatif,
                }
    out["videos"] = videos_fixture(ctx.core["countries"])
    ctx.write_json("tests/fixtures/country_cases.json", out)


VIDEO_TITLES = [  # made-up titles that test the matching rules of ui.videos_about
    "South Sudan: fighting near Juba", "Sudan's army retakes Khartoum", "Inside the U.S. election", "US tariffs explained",
    "The u.s. view", "Nigerian markets slide", "NIGERIA votes", "Côte d'Ivoire after the vote", "Cote d'Ivoire cocoa",
    "DRC: M23 talks", "drc mining", "Türkiye and the Kurds", "Turkish lira falls", "North Korea fires a missile",
    "South Korean exports", "Congo-Brazzaville oil", "Republic of the Congo votes", "Americana music", "Sudanese refugees",
]


def videos_fixture(countries: pd.DataFrame) -> dict:
    names = dict(zip(countries["iso3"], countries["name"]))
    official = dict(zip(countries["iso3"], countries["official_name"]))
    videos = pd.DataFrame({"video_id": [f"v{i}" for i in range(len(VIDEO_TITLES))], "title": VIDEO_TITLES,
                           "description": ["" if i % 3 else "A report from the region." for i in range(len(VIDEO_TITLES))]})
    picked = ["SDN", "SSD", "USA", "NGA", "CIV", "COD", "COG", "TUR", "KOR", "PRK"]
    return {"videos": videos.to_dict("records"),
            "about": {iso3: {"news_name": config.NEWS_NAMES.get(iso3, names[iso3]), "official": official[iso3],
                             "aliases": config.VIDEO_ALIASES.get(iso3, []),
                             "ids": list(ui.videos_about(videos, iso3, names, official[iso3])["video_id"])}
                      for iso3 in picked}}
