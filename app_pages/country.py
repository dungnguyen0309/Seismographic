"""Country profile: score, red flags, automatic brief, what-if simulator, trends, economy, news and the analyst view."""

import html
import math

import pandas as pd
import streamlit as st

from prm import charts, config, content, data, follow, interpret, report, scoring, ui
from prm.config import INDICATORS, PILLARS, SEVERITY_LABEL, TIER_ORDER, WGI_DIMENSIONS

core, year, values, scores = ui.load()
hist = ui.history(core)
table = ui.master_table(core, values, scores, hist)
countries = core["countries"]
options, names = ui.country_options(countries)

# --- Country selector (kept in the URL so profiles can be shared: ?country=NGA) -----------
default = ui.current_country(countries)
if st.session_state.get("country_pick") != default:  # arrived from search, a click or the dock: show that country
    st.session_state["country_pick"] = default


def _picked() -> None:
    # Runs before the re-run, so the dock at the bottom already shows the new country
    st.session_state["country"] = st.session_state["country_pick"]


iso3 = st.selectbox(
    "Country", options, key="country_pick", on_change=_picked, format_func=lambda i: names.get(i, i),
    label_visibility="collapsed",
)
st.session_state["country"] = iso3
st.query_params["country"] = iso3

row = table.set_index("iso3").loc[iso3]
v = values.loc[iso3]
s = scores.loc[iso3]
name = names[iso3]
st.set_page_config(page_title=f"{name} · {config.APP_TITLE}")
assessment = ui.assessments().get(iso3)

# --- Header -----------------------------------------------------------------
country_hist = hist[hist["iso3"] == iso3].sort_values("year")
prev = country_hist[country_hist["year"] == year - 1]
prev = prev.iloc[0] if len(prev) else None
score_delta = None if prev is None or pd.isna(s["composite"]) or pd.isna(prev["composite"])     else round(float(s["composite"] - prev["composite"]), 1)
gdppc = v.get("gdppc")
meta = [str(row["region"]), str(row["income"]), f"{ui.fmt_population(v.get('population'))} people"]
if pd.notna(gdppc):
    meta.append(f"${gdppc:,.0f} per person (IMF, {year})")
if s["coverage"] < 75:
    meta.append(f"data coverage {s['coverage']:.0f}%: read with care")
ui.country_header(name, row,
                  country_hist.set_index("year")["composite"], score_delta, year, " · ".join(meta),
                  analyst_rating=(assessment or {}).get("meta", {}).get("analyst_rating") or None)


def _add_to_compare() -> None:
    ui.add_to_compare(iso3)
    st.session_state["_compare_toast"] = f"{name} added to your comparison"


def _brief_pdf() -> bytes:
    """Built only when the button is clicked."""
    reading = interpret.country_reading(iso3, table, values, scores, hist, content.load_events(), core.get("flows"), year)
    return report.country_pdf(reading, row, country_hist, scoring.red_flags(v), year, ui.custom_weights_label())


if toast := st.session_state.pop("_compare_toast", None):
    st.toast(toast, icon=":material/check:")
compare_list = st.session_state.get(ui.COMPARE_LIST, [])
with st.container(horizontal=True, vertical_alignment="center", key="country_actions"):
    if iso3 in compare_list:
        st.button("✓ In your comparison", disabled=True, key="compare_added")
    elif len(compare_list) >= config.MAX_COMPARE:
        st.button("Comparison is full", disabled=True, key="compare_full",
                  help=f"You can compare up to {config.MAX_COMPARE} countries. Remove one on the Compare page.")
    else:
        st.button("Add to compare", key="compare_add", on_click=_add_to_compare)
    st.download_button("Download PDF brief", data=_brief_pdf, file_name=f"{iso3}_risk_brief_{year}.pdf",
                       mime="application/pdf", on_click="ignore", key="brief_pdf",
                       help="A one-page brief: score, pillars, trend, red flags and what it means in real life.")
    follow.follow_button(iso3, name)
    if compare_list:
        st.page_link(ui.COMPARE_PAGE, label=f"Open comparison ({len(compare_list)})", icon=":material/compare_arrows:")

elsewhere = ([("World Bank", f"https://data.worldbank.org/country/{row['iso2']}")] if isinstance(row["iso2"], str) else []) + [
    ("IMF", f"https://www.imf.org/en/countries/{iso3.lower()}"),
    ("ReliefWeb", f"https://reliefweb.int/country/{iso3.lower()}")]
if row["income"] != "High income":  # FAO's food-security briefs cover developing countries
    elsewhere.append(("FAO food security", f"https://www.fao.org/giews/countrybrief/country.jsp?code={iso3}"))
sources = " · ".join(f"[{ui.source_label(k)}]({config.SOURCES[k].url})" for k in ("wb_countries", "wdi", "imf"))
st.caption(f"Sources: {sources}  \nElsewhere: " + " · ".join(f"[{label} ↗]({url})" for label, url in elsewhere))

flags = scoring.red_flags(v)
trend = scoring.wgi_trend(core["series"], iso3, "pv")

TABS = {"summary": ":material/summarize: Summary", "real": ":material/explore: In real life",
        "peers": ":material/groups: Peers", "map": ":material/map: Map & refugees", "whatif": ":material/tune: What-if",
        "indicators": ":material/list_alt: Indicators", "governance": ":material/account_balance: Governance",
        "economy": ":material/monitoring: Economy", "news": ":material/newspaper: News",
        "assessment": ":material/edit_note: Assessment"}
if st.query_params.get("tab") in TABS:  # e.g. ?country=KEN&tab=news
    st.session_state["country_tab"] = TABS[st.query_params["tab"]]
    del st.query_params["tab"]
(t_summary, t_real, t_peers, t_map, t_whatif, t_indicators, t_governance, t_economy, t_news,
 t_analyst) = st.tabs(list(TABS.values()), key="country_tab", on_change="rerun")  # only the open tab is built

# --- Summary --------------------------------------------------------------------
with t_summary:
    if t_summary.open:
        st.header("Risk over time")
        if country_hist["composite"].notna().sum() >= 2:
            st.plotly_chart(charts.risk_history(country_hist, marks=True), config={"displayModeBar": False})
            ui.cite("index")
            st.caption(
                f"The index recomputed for every year since {config.HISTORY_START}, each time with only the data "
                "available for that year. Scores are relative to the other countries that year, so a rising line means "
                f"{name} moved up the risk ranking. Marks = a new tier or armed conflict entering or leaving the data; "
                f"bands = tiers; the pillars can be switched on in the legend. {year} uses IMF estimates."
            )
        else:
            st.info("Not enough history to draw a trend for this country.")

        c1, c2 = st.columns([1.1, 1])
        with c1:
            st.header("What the data says")
            for line in scoring.country_brief(iso3, name, values, scores, core["series"], countries, year):
                st.markdown(f"- {line}")
            ui.cite("index")
        with c2:
            outlook = data.get_outlook(core, core["version"])
            mine = None if outlook is None else outlook.predictions.set_index("iso3").reindex([iso3]).iloc[0]
            if mine is not None and isinstance(mine["status"], str):
                st.header("Conflict outlook")
                if mine["status"] == "In armed conflict":
                    st.markdown(f"**In armed conflict** in the latest data ({outlook.data_year}).")
                else:
                    level = ui.sev_mark("serious" if mine["relative"] >= 3 else "warning", spoken=False) \
                        if mine["relative"] >= 1 else ""
                    st.markdown(f"{level}**{mine['probability']:.1%}** chance that armed conflict breaks out in "
                                f"{outlook.index_year + 1} — {mine['relative']:.1f}× the average for a country at peace.",
                                unsafe_allow_html=True)
                st.page_link("app_pages/conflict.py", label="How this is estimated (Conflict outlook)",
                             icon=":material/insights:", query_params={"tab": "outlook"})
            st.header("Red flags")
            if trend and trend["change"] <= -config.WGI_TREND_THRESHOLD:
                flags.append({"severity": "warning",
                              "label": f"Political stability deteriorating ({trend['change']:+.1f} points since {trend['start_year']})"})
            if flags:
                for f in sorted(flags, key=lambda f: config.SEVERITY_ORDER[f["severity"]]):
                    st.markdown(f"{ui.sev_mark(f['severity'], spoken=False)}**{SEVERITY_LABEL[f['severity']]}** — "
                                f"{html.escape(f['label'])}", unsafe_allow_html=True)
            else:
                st.markdown("No absolute warning thresholds crossed.")
            st.caption("Red flags use fixed thresholds (e.g. inflation ≥ 20%), independent of how other countries score.")
            ui.cite("index", "ucdp_def", "imf_ara")

            st.header("Upcoming events")
            country_events = content.load_events()
            ui.upcoming_events(country_events[country_events["iso3"] == iso3].assign(country=name), limit=5)
            st.page_link("app_pages/watchlist.py", label="Events watchlist", icon=":material/event:")
            ui.cite("ifes")

        st.header("Pillar scores")
        peers = table[table["region"] == row["region"]]
        st.plotly_chart(charts.pillar_bars(s, peers[[p.key for p in PILLARS]].median()), config={"displayModeBar": False})
        ui.cite("index")

        with st.expander("How robust is this score? (sensitivity to the weights)"):
            sens = data.get_sensitivity(core, year, iso3, ui.weights_tuple(), core["version"])
            st.dataframe(
                sens, hide_index=True,
                column_config={
                    "Score": st.column_config.NumberColumn(format="%.1f"),
                    "Rank": st.column_config.NumberColumn(format="%d"),
                },
            )
            st.caption(
                "If the rank barely moves when a pillar is dropped, the result does not hinge on one modelling choice. "
                "Large swings tell you which dimension drives the score."
            )

# --- In real life ------------------------------------------------------------------
with t_real:
    if t_real.open:
        st.header(f"What the data means for {name} in real life")
        st.caption("The scores, red flags, trend and upcoming events in plain language, and how people commonly "
                   "act on them. General guidance only.")
        reading = interpret.country_reading(iso3, table, values, scores, hist, content.load_events(), core.get("flows"),
                                            year)
        ui.render_reading(reading, key=f"real_{iso3}")
        ui.cite("index", "ifes", "ucdp_def", "imf_ara")
        st.page_link("app_pages/guide.py", label="Guide: reading the numbers",
                     icon=":material/explore:")

# --- Peers ------------------------------------------------------------------------
with t_peers:
    if t_peers.open:
        groups = {
            f"Region · {row['region']}": table[table["region"] == row["region"]],
            f"Income group · {row['income']}": table[table["income"] == row["income"]],
            "All countries": table,
        }
        group = st.segmented_control("Compare with", list(groups), default=list(groups)[0], key="peer_group") \
            or list(groups)[0]
        peer_df = groups[group]
        ranked = peer_df.dropna(subset=["composite"]).sort_values("composite", ascending=False).reset_index(drop=True)
        position = ranked.index[ranked["iso3"] == iso3]
        if len(position):
            st.markdown(
                f"**{name}** is **{position[0] + 1} of {len(ranked)}** in this group "
                f"(1 = highest risk; group median {ranked['composite'].median():.0f})."
            )
        st.plotly_chart(charts.peer_strip(s, peer_df[peer_df["iso3"] != iso3], name), config={"displayModeBar": False})
        st.caption("Grey dots = the other countries in the group (hover for names), white tick = group median, "
                   f"big dot = {name}.")
        ui.cite("index", "wb_countries")

        st.header("Peer ranking")
        peer_table = ranked.assign(name=[f"▶ {n}" if i == iso3 else n for i, n in zip(ranked["iso3"], ranked["name"])],
                                   group_rank=range(1, len(ranked) + 1))
        ui.country_table(
            peer_table, key="peer_table", height=min(460, 38 * (len(peer_table) + 1)),
            extra={"group_rank": st.column_config.NumberColumn("Rank in group", format="%d")},
        )
        st.caption(f"▶ marks {name}. Tick a row to open another country.")

        st.header("Most similar risk profiles")
        like = scoring.similar(scores, iso3, n=8)
        if like.empty:
            st.caption("Not enough data to compare profiles.")
        else:
            similar_table = table.set_index("iso3").loc[like.index].reset_index().assign(
                closeness=(100 - like["distance"].to_numpy()).clip(0, 100))
            ui.country_table(
                similar_table, key="similar_table", height=min(360, 38 * (len(similar_table) + 1)),
                sort="closeness", ascending=False,
                extra={"closeness": st.column_config.ProgressColumn(
                    "Similarity", min_value=0, max_value=100, format="%.0f",
                    help="100 = the same four pillar scores; based on the distance between the profiles")},
            )
            st.caption(f"Countries anywhere in the world whose stability, governance, economic and social scores are "
                       f"closest to {name}'s. Tick a row to open one.")

# --- Map & refugee links ------------------------------------------------------------
with t_map:
    if t_map.open:
        flows = core.get("flows")
        ui.globe_panel(table=table, hist=hist, flows=flows, metric="composite", metric_label="Composite",
                       key=f"profile_globe_{iso3}", focus=iso3, height=520,
                       layers={"spin": False, "flows": True, "conflict": True},
                       hint=f"Arcs = refugees from or hosted by {name} · ▶ replays since {config.HISTORY_START}")
        st.caption(f"The globe opens on {name} with its refugee flows: arcs run from the country people fled to the "
                   "country hosting them. Click any other country for its index.")
        ui.cite("unhcr", "ucdp", "natural_earth")
        if flows is not None and not flows.empty:
            flows_year = int(flows["year"].max())
            out_col, in_col = st.columns(2)
            for col, title, side, other, colour, hover in (
                (out_col, f"Where refugees from {name} are", "origin", "host", charts.WORSE, "people from " + name),
                (in_col, f"Who {name} hosts", "host", "origin", charts.BETTER, "people hosted"),
            ):
                with col:
                    st.header(title)
                    links = (flows[(flows[side] == iso3) & flows[other].isin(names)]
                             .nlargest(10, "value").rename(columns={other: "iso3"}))
                    if links.empty:
                        st.caption(f"No recorded flows ({flows_year}).")
                        continue
                    links = links.assign(name=links["iso3"].map(names))
                    event = st.plotly_chart(charts.ranked_bars(links, "value", "name", colour, hover),
                                            config={"displayModeBar": False}, on_select="rerun", selection_mode="points",
                                            key=f"links_{side}")
                    if clicked := ui.clicked_iso3(event):
                        ui.go_to_country(clicked)
                    total = flows.loc[flows[side] == iso3, "value"].sum()
                    st.caption(f"{total:,.0f} people in total ({flows_year}, UNHCR: refugees, asylum seekers and others "
                               "in need of international protection). Click a bar to open that country.")

# --- What-if simulator ------------------------------------------------------------
WHATIF_PRESETS = {
    "Currency crisis": {"inflation": ("max", 40), "reserves_months": ("min", 2), "gdp_growth": ("min", -3),
                          "current_account": ("min", -6)},
    "Armed conflict": {"battle_deaths_raw": ("max", 2500), "wgi_pv": ("add", -15), "displaced_share": ("max", 5)},
    "Democratic backsliding": {"wgi_va": ("add", -15), "wgi_rl": ("add", -10), "wgi_cc": ("add", -10),
                                  "wgi_ge": ("add", -5)},
    "Reform & recovery": {"inflation": ("min", 5), "gdp_growth": ("max", 4), "wgi_ge": ("add", 10),
                            "wgi_rl": ("add", 10), "wgi_cc": ("add", 10)},
}
BATTLE_DEATH_STEPS = [0, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000]
WHATIF_PREFIX = f"wi_{iso3}_"


def _whatif_controls() -> dict[str, dict]:
    """One control per scored indicator this country has data for: {value key: spec}."""
    specs = {}
    for ind in config.SCORED_INDICATORS:
        if ind.key == "battle_deaths_100k":  # people think in deaths, not deaths per 100k
            raw, pop = v.get("battle_deaths_raw"), v.get("population")
            if pd.isna(raw) or pd.isna(pop) or pop <= 0:
                continue
            current = int(round(raw))
            per_death = v["battle_deaths_100k"] / raw if raw > 0 else 100_000 / pop
            specs["battle_deaths_raw"] = {
                "ind": ind, "label": "Battle-related deaths per year", "kind": "select", "current": current,
                "options": sorted(set(BATTLE_DEATH_STEPS) | {current}), "per_death": per_death,
            }
            continue
        current = v.get(ind.key)
        if pd.isna(current):
            continue
        column = pd.to_numeric(values[ind.key], errors="coerce").dropna()
        lo, hi = (0.0, 100.0) if ind.key.startswith("wgi_") else (column.quantile(0.01), column.quantile(0.99))
        specs[ind.key] = {
            "ind": ind, "label": f"{ind.short} ({ind.unit})", "kind": "slider", "current": round(float(current), 1),
            "min": float(math.floor(min(lo, current))), "max": float(math.ceil(max(hi, current))),
        }
    return specs


def _snap(spec: dict, value: float):
    if spec["kind"] == "select":
        return min(spec["options"], key=lambda o: abs(o - value))
    return round(min(max(value, spec["min"]), spec["max"]), 1)


def _apply_preset(name: str, specs: dict[str, dict]) -> None:
    _reset_whatif()
    for key, (op, amount) in WHATIF_PRESETS[name].items():
        if key not in specs:
            continue
        base = specs[key]["current"]
        new = max(base, amount) if op == "max" else min(base, amount) if op == "min" else base + amount
        st.session_state[WHATIF_PREFIX + key] = _snap(specs[key], new)


def _reset_whatif() -> None:
    for key in [k for k in st.session_state if str(k).startswith(WHATIF_PREFIX)]:
        del st.session_state[key]


@st.fragment
def what_if_simulator() -> None:
    st.header("What if…?")
    st.caption(
        f"Change {name}'s indicators and watch the index react. Every country is re-scored, exactly as the real index "
        "would be — so you can see which levers move the score and how far a crisis or a reform would shift the rank."
    )
    specs = _whatif_controls()
    with st.container(horizontal=True, wrap=True, key="whatif_presets"):  # full names; they wrap instead of truncating
        for preset in WHATIF_PRESETS:
            st.button(preset, on_click=_apply_preset, args=(preset, specs), key=f"preset_{preset}")
        st.button("Reset indicators", on_click=_reset_whatif, key="whatif_reset", icon=":material/restart_alt:")

    controls, results = st.container(key="split_whatif").columns([1, 1.15], gap="large")
    changes, moved = {}, []
    with controls:
        for i, pillar in enumerate(PILLARS):
            keys = [k for k, s in specs.items() if s["ind"].pillar == pillar.key]
            if not keys:
                continue
            with st.expander(pillar.label, expanded=i == 0):
                for key in keys:
                    spec = specs[key]
                    widget_key = WHATIF_PREFIX + key
                    # Seed through session state only (presets write there too; passing value= as well would warn)
                    st.session_state.setdefault(widget_key, spec["current"])
                    if spec["kind"] == "select":
                        value = st.select_slider(spec["label"], spec["options"], key=widget_key,
                                                 format_func=lambda o: f"{o:,}")
                    else:
                        ind = spec["ind"]
                        value = st.slider(spec["label"], spec["min"], spec["max"], step=0.1, format="%.1f", key=widget_key,
                                          help="Higher = riskier" if ind.higher_is_riskier else "Lower = riskier")
                    if value != spec["current"]:  # untouched sliders keep the exact original value
                        moved.append(spec["label"].split(" (")[0])
                        if key == "battle_deaths_raw":
                            changes["battle_deaths_raw"] = float(value)
                            changes["battle_deaths_100k"] = value * spec["per_death"]
                        else:
                            changes[key] = float(value)
        missing = [i.short for i in config.SCORED_INDICATORS
                   if i.key not in specs and not (i.key == "battle_deaths_100k" and "battle_deaths_raw" in specs)]
        if missing:
            st.caption("No data to simulate: " + ", ".join(missing))

    with results:
        if pd.isna(s["composite"]):
            st.info(f"{name} has too little data for a composite score, so there is nothing to simulate.")
            return
        new_scores, new_values = scoring.simulate(values, iso3, changes, dict(ui.weights_tuple()))
        n = new_scores.loc[iso3]
        score_delta = n["composite"] - s["composite"]
        rank_delta = int(n["rank"] - s["rank"])
        r1, r2 = st.columns(2)  # two figures fit a half-width panel; the tier goes on its own line below
        r1.metric("Composite score", f"{n['composite']:.0f} / 100",
                  delta=f"{score_delta:+.1f}" if round(score_delta, 1) else None, delta_color="inverse", border=True)
        r2.metric("Global rank", f"{int(n['rank'])} of {int(n['n_ranked'])}",
                  delta=f"{rank_delta:+d} places" if rank_delta else None, border=True,
                  help="1 = highest risk, so a smaller number means riskier.")
        was = f" <span style='color:var(--sg-muted)'>was {s['tier']}</span>" if n["tier"] != s["tier"] else ""
        st.markdown(f"Risk tier&nbsp; {ui.tier_badge(n['tier'])}{was}", unsafe_allow_html=True)
        st.plotly_chart(charts.whatif_pillars(s, n), config={"displayModeBar": False}, key="whatif_chart")
        ui.cite("index")

        before = {f["label"] for f in scoring.red_flags(v)}
        after = scoring.red_flags(new_values)
        new_flags = [f for f in after if f["label"] not in before]
        cleared = before - {f["label"] for f in after}
        if new_flags or cleared:
            st.markdown("**Red flags in this scenario**")
            for f in new_flags:
                st.markdown(f"{ui.sev_mark(f['severity'])}**New:** {html.escape(f['label'])}", unsafe_allow_html=True)
            for label in sorted(cleared):
                st.markdown(f"**Cleared:** {label}")
        if moved:
            st.caption("Changed: " + ", ".join(moved) + ".")
        else:
            st.caption("Move a slider or pick a scenario above to start.")


with t_whatif:
    if t_whatif.open:
        what_if_simulator()

# --- Indicators -------------------------------------------------------------------
with t_indicators:
    if t_indicators.open:
        st.header("Every indicator behind the score")
        rows = []
        for ind in INDICATORS:
            raw = v.get(ind.key)
            yr = v.get(f"{ind.key}__year")
            rows.append({
                "Pillar": config.PILLAR_BY_KEY[ind.pillar].short,
                "Indicator": ind.label,
                "Value": ind.fmt(raw),
                "Unit": ind.unit,
                "Year": "—" if pd.isna(yr) else str(int(yr)),
                "Risk score": s.get(f"n_{ind.key}"),
                "Direction": "Higher = riskier" if ind.higher_is_riskier else "Lower = riskier",
                "Source": ind.source,
                "Data": config.indicator_url(ind),
            })
        st.dataframe(
            pd.DataFrame(rows), hide_index=True, height=640,
            column_config={
                "Risk score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
                "Data": st.column_config.LinkColumn("Data", display_text="Open ↗",
                                                    help="The source's own page for this indicator"),
            },
        )
        st.caption(
            "Risk score = position relative to all other economies (0–100). Battle deaths and displacement use a log "
            "scale so that countries without conflict score 0. See the Methodology page."
        )
        ui.cite("index")
        with st.expander(f"Cross-check {name} with independent sources"):
            st.caption("Respected indices that measure similar things but are not used in the score. Look the country up "
                       "in them: if they disagree with Seismographic, find out why.")
            for pillar_key, keys in config.CROSS_CHECKS.items():
                label = ("**Overall fragility**" if pillar_key == "composite" else ui.pillar_chip(pillar_key))
                st.markdown(f"{label} &nbsp; " + " · ".join(ui.source_link(k, config.SOURCES[k].name) for k in keys),
                            unsafe_allow_html=True)
            st.page_link(ui.SOURCES_PAGE, label="All sources and cross-checks", icon=":material/verified:")
        export = pd.DataFrame(rows).assign(Country=name, ISO3=iso3)
        st.download_button("Download indicators (CSV)", export.to_csv(index=False).encode("utf-8"),
                           file_name=f"{iso3}_indicators_{year}.csv", mime="text/csv")

# --- Governance trends ---------------------------------------------------------------
with t_governance:
    if t_governance.open:
        st.header("Worldwide Governance Indicators over time")
        st.caption(
            "World Bank WGI governance scores (0–100, higher = better governance) with the 90% confidence interval. "
            "When intervals for two years overlap, the change may be within the margin of error."
        )
        with st.spinner("Loading confidence intervals…"):
            ci = data.load_wgi_ci()
        st.plotly_chart(charts.wgi_small_multiples(core["series"], ci, iso3), config={"displayModeBar": False})
        ui.cite("wgi")
        trend_rows = []
        for dim, label in WGI_DIMENSIONS.items():
            t = scoring.wgi_trend(core["series"], iso3, dim)
            if not t:
                continue
            overlap = scoring.ci_overlap(core["series"], ci, iso3, dim, t["start_year"], t["end_year"])
            trend_rows.append({
                "Dimension": label,
                f"Score {t['start_year']}": round(t["start"], 1),
                f"Score {t['end_year']}": round(t["end"], 1),
                "Change": round(t["change"], 1),
                "Statistically clear?": "—" if overlap is None else ("No (intervals overlap)" if overlap else "Yes"),
            })
        if trend_rows:
            st.dataframe(pd.DataFrame(trend_rows), hide_index=True)

# --- Economy --------------------------------------------------------------------------
with t_economy:
    if t_economy.open:
        edition = core["meta"].get("gdp_growth", {}).get("edition") or "IMF World Economic Outlook"
        st.header("Macroeconomic picture")
        st.caption(f"Source: {edition}. Dashed lines are IMF projections.")
        st.plotly_chart(charts.macro_small_multiples(core["series"], iso3, year), config={"displayModeBar": False})
        ui.cite("imf", "wdi", "unhcr")
        e1, e2, e3 = st.columns(3)
        e1.metric("FX reserves (months of imports)", config.INDICATOR_BY_KEY["reserves_months"].fmt(v.get("reserves_months")),
                  help="World Bank WDI. Below 3 months is a common warning line.", border=True)
        e2.metric("Youth unemployment", f"{config.INDICATOR_BY_KEY['youth_unemployment'].fmt(v.get('youth_unemployment'))}%",
                  border=True)
        e3.metric("Displaced (% of population)", f"{config.INDICATOR_BY_KEY['displaced_share'].fmt(v.get('displaced_share'))}%",
                  help="Refugees, asylum seekers, others in need of protection and IDPs from this country (UNHCR).",
                  border=True)

# --- News pulse -------------------------------------------------------------------------
with t_news:
    if t_news.open:
        news_name = config.NEWS_NAMES.get(iso3, name)
        st.header("Risk-related news, last 7 days")
        st.caption(
            f"Live headlines matching “{news_name}” plus risk keywords (protest, election, coup, sanctions, clashes…), "
            "newest first, from Bing News and Google News (photos where the feed has one), with GDELT as a backup."
        )
        ui.news_list(news_name, limit=20, iso2=row["iso2"])
        ui.cite("news", "gdelt")

        with ui.guard("Video reports"):
            st.header(f"Video reports on {name}")
            all_videos = data.load_videos()
            about = (ui.videos_about(all_videos, iso3, names, countries.set_index("iso3").get("official_name", pd.Series())
                                     .get(iso3)) if all_videos is not None else None)
            if about is None or about.empty:
                st.caption(f"None of the latest videos from the international broadcasters and think tanks mention {name}.")
            else:
                st.caption("From the latest uploads of international broadcasters and think tanks; play one here or open it on YouTube.")
                ui.video_gallery(about, key=f"profile_videos_{iso3}", limit=6)
            st.page_link("app_pages/video.py", label="Live TV and all video reports", icon=":material/live_tv:")
            ui.cite("youtube")
        with ui.guard("Media tone"):
            if st.toggle("Show media tone over the last 3 months (GDELT)"):
                tone, terr = data.load_tone(news_name)
                if terr:
                    st.info("GDELT's tone data can't be reached right now. Try again in a few minutes.")
                elif tone is None or tone.empty:
                    st.info("No tone data returned.")
                else:
                    st.plotly_chart(charts.tone_chart(tone), config={"displayModeBar": False})
                    st.caption("GDELT average tone of English-language coverage. A sustained fall often precedes or accompanies crises.")
                    ui.cite("gdelt")
        with ui.guard("Protest coverage"):
            if st.toggle("Show protest coverage over the last 3 months (GDELT)"):
                protests, perr = data.load_protests(news_name)
                if perr:
                    st.info("GDELT's protest data can't be reached right now (it allows few requests). Try again in a few "
                            "minutes.")
                elif protests is None or protests.empty:
                    st.info("No protest coverage found.")
                else:
                    st.plotly_chart(charts.protest_chart(protests), config={"displayModeBar": False})
                    st.caption(f"Share of all English-language news GDELT monitors that mentions {name} together with protests, "
                               "riots, strikes or unrest, smoothed over a week. Spikes show unrest getting attention; compare "
                               "with the headlines above.")
                    ui.cite("gdelt")

# --- Analyst assessment -------------------------------------------------------------------
with t_analyst:
    if t_analyst.open:
        if assessment:
            m = assessment["meta"]
            a1, a2, a3, a4 = st.columns(4)
            a1.markdown("**Analyst rating**")
            a1.markdown(ui.tier_badge(m.get("analyst_rating")), unsafe_allow_html=True)
            a2.metric("Outlook", m.get("outlook") or "—")
            a3.metric("Confidence", m.get("confidence") or "—")
            a4.metric("Written", m.get("date") or "—")
            model_tier, analyst_tier = s["tier"], m.get("analyst_rating")
            if model_tier in TIER_ORDER and analyst_tier in TIER_ORDER and model_tier != analyst_tier:
                gap = TIER_ORDER.index(analyst_tier) - TIER_ORDER.index(model_tier)
                st.info(
                    f"The analyst rates {name} **{abs(gap)} tier{'s' if abs(gap) > 1 else ''} "
                    f"{'higher' if gap > 0 else 'lower'}** than the model ({model_tier}). "
                    "The reasoning is under *Why my rating differs from the model*."
                )
            st.caption(f"By {m.get('author') or 'the analyst'} · horizon {m.get('horizon') or '—'} · file assessments/{assessment['file']}")
            st.divider()
            st.markdown(assessment["body"])
        else:
            st.info(f"No analyst assessment for {name} yet.")
            st.markdown(
                "An assessment adds key judgments with probabilities, scenarios and the indicators that would change "
                "your mind. Write one in the **Assessment builder** and add the file to the project's `assessments/` "
                "folder."
            )
            st.page_link("app_pages/builder.py", label="Open the assessment builder", icon=":material/edit_note:")

ui.footer()
