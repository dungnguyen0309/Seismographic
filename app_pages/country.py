"""Country profile: score, red flags, automatic brief, what-if simulator, trends, economy, news and the analyst view."""

import html
import math

import pandas as pd
import streamlit as st

from prm import a11y, charts, config, content, data, follow, interpret, report, scoring, ui
from prm.config import INDICATORS, PILLARS, SEVERITY_LABEL, TIER_ORDER, WGI_DIMENSIONS

core, year, values, scores = ui.load()
hist = ui.history(core)
table = ui.master_table(core, values, scores, hist)
countries = core["countries"]
options, names = ui.country_options(countries)

# The picker's label sits beside it; on phones the actions share one row of 44px buttons, so the tabs start higher
st.html("""<style>
.st-key-country_pick [data-testid="stSelectbox"] { display: flex; align-items: center; gap: 10px; }
.st-key-country_pick [data-testid="stWidgetLabel"] { margin: 0 !important; flex: none; }
.st-key-country_pick [data-testid="stSelectbox"] > :last-child { flex: 1 1 auto; min-width: 0; }
@media (max-width: 640px) {
  .st-key-country_actions { flex-wrap: wrap !important; gap: 8px !important; }
  .st-key-country_actions > * { flex: 1 1 calc(33% - 8px) !important; min-width: 0 !important; width: auto !important; }
  .st-key-country_actions :is([data-testid="stButton"], [data-testid="stDownloadButton"], [data-testid="stPageLink"], button, a) {
    width: 100% !important; }
  .st-key-country_actions :is(button, a) { min-height: 44px; height: auto; padding: 4px 8px; }
  .st-key-country_actions :is(button, a) p { font-size: 0.8125rem; white-space: normal; line-height: 1.2; }
  .st-key-country_actions :is(button, a) [data-testid="stMarkdownContainer"] { line-height: 1.2; }  /* sets the line box */
  .st-key-country_actions .sg-follow { height: auto; min-height: 44px; }
}
</style>""")

# --- Country selector (kept in the URL so profiles can be shared: ?country=NGA) -----------
chosen = ui.current_country(countries, fallback=None)  # None on a first visit that has picked nothing yet
default = chosen or ui.current_country(countries)
if st.session_state.get("country_pick") != default:  # arrived from search, a click or the dock: show that country
    st.session_state["country_pick"] = default


def _picked() -> None:
    # Runs before the re-run, so the dock at the bottom already shows the new country
    st.session_state["country"] = st.session_state["country_pick"]


iso3 = st.selectbox("Country", options, key="country_pick", on_change=_picked, format_func=lambda i: names.get(i, i),
                    width=420)
if chosen or iso3 != default:  # the fallback country is shown, not tracked, until the visitor picks one
    st.session_state["country"] = iso3
    st.query_params["country"] = iso3

row = table.set_index("iso3").loc[iso3]
v = values.loc[iso3]
s = scores.loc[iso3]
name = names[iso3]
st.set_page_config(page_title=f"{name} · {config.APP_TITLE}")
assessment = ui.assessments().get(iso3)

flags = scoring.red_flags(v) + scoring.stability_flags(core["series"], iso3)  # also in the Summary and the PDF brief

# Tabs: text only, so they fit one row. An assessment comes second; without one, its empty state goes last
TABS = {"summary": "Summary", "assessment": "Assessment", "peers": "Peers", "whatif": "What-if", "data": "Data",
        "news": "News"}
if not assessment:
    TABS["assessment"] = TABS.pop("assessment")
PEERS_VIEWS = {"ranking": "Ranking", "map": "Map & refugees"}  # kept in the address as ?view=
DATA_VIEWS = {"indicators": "Indicators", "governance": "Governance", "economy": "Economy"}
# links made before tabs were merged: ?tab=map opens Peers on its map, ?tab=real the Summary's real-life reading
OLD_TABS = {"map": "peers", "indicators": "data", "governance": "data", "economy": "data"}  # old slug: its tab now
if (old := st.query_params.get("tab")) == "real":
    st.query_params["tab"] = "summary"
    st.session_state["real_life"] = True
elif old in OLD_TABS:
    st.query_params["tab"], st.query_params["view"] = OLD_TABS[old], old


def _open_assessment() -> None:
    st.session_state["country_tab"] = TABS["assessment"]


# --- Header -----------------------------------------------------------------
country_hist = hist[hist["iso3"] == iso3].sort_values("year")
gdppc = v.get("gdppc")
meta = [str(row["region"]), str(row["income"]), f"{ui.fmt_population(v.get('population'))} people"]
if pd.notna(gdppc):
    meta.append(f"${gdppc:,.0f} per person (IMF, {int(v['gdppc__year'])})")
if ui.thin_data(table[table["iso3"] == iso3]).any():  # the same rule as the "(limited data)" marks elsewhere
    missing = [p.short for p in PILLARS if pd.isna(row[p.key])]
    meta.append(f"data coverage {s['coverage']:.0f}%" + (f", no {' or '.join(missing)} score" if missing else "")
                + ": read with care")
top_flag = (f"{ui.sev_mark(flags[0]['severity'])}{html.escape(flags[0].get('short', flags[0]['label']))} · "
            if flags else "")  # flags come most severe first
ui.country_header(name, row, row.get("delta_1y"), year, top_flag + html.escape(" · ".join(meta)),
                  analyst_rating=(assessment or {}).get("meta", {}).get("analyst_rating") or None,
                  on_analyst=_open_assessment)


def _add_to_compare() -> None:
    ui.add_to_compare(iso3)
    st.session_state["_compare_toast"] = f"{name} added to your comparison"
    st.session_state["_compare_just_added"] = True
    a11y.keep_focus("compare_add")  # the button is redrawn as "Open comparison"; keep the keyboard on it


weights_label = ui.custom_weights_label()  # read now: the PDF is built later, outside this run


def _brief_pdf() -> bytes:
    """Built only when the button is clicked."""
    reading = interpret.country_reading(iso3, table, values, scores, hist, content.load_events(), core.get("flows"), year,
                                       core["series"])
    return report.country_pdf(reading, row, country_hist, flags, year, weights_label)


if toast := st.session_state.pop("_compare_toast", None):
    st.toast(toast, icon=":material/check:")
compare_list = st.session_state.get(ui.COMPARE_LIST, [])
with st.container(horizontal=True, vertical_alignment="center", key="country_actions"):
    # One enabled button in one place (same key), so keyboard focus stays on it after adding: a disabled or a new
    # button would drop focus back to the top of the page
    if iso3 in compare_list:
        just_added = st.session_state.pop("_compare_just_added", False)  # the adding press must not also open it
        if st.button(f"Open comparison ({len(compare_list)})", key="compare_add", icon=":material/compare_arrows:",
                     help=f"{name} is in your comparison") and not just_added:
            st.switch_page(ui.COMPARE_PAGE)
    elif len(compare_list) >= config.MAX_COMPARE:
        st.button("Comparison is full", disabled=True, key="compare_add",
                  help=f"You can compare up to {config.MAX_COMPARE} countries. Remove one on the Compare page.")
    else:
        st.button("Add to compare", key="compare_add", on_click=_add_to_compare)
    st.download_button("Download PDF brief", data=_brief_pdf, file_name=f"{iso3}_risk_brief_{year}.pdf",
                       mime="application/pdf", on_click="ignore", key="brief_pdf",
                       help="A one-page brief: score, pillars, trend, red flags and what it means in real life.")
    follow.follow_button(iso3, name)
    if compare_list and iso3 not in compare_list:  # once this country is in, the button above opens the comparison
        st.page_link(ui.COMPARE_PAGE, label=f"Open comparison ({len(compare_list)})", icon=":material/compare_arrows:")

tabs = dict(zip(TABS, ui.url_tabs(TABS, key="country_tab")))  # only the open tab is built
if not (tabs["peers"].open or tabs["data"].open):
    st.query_params.pop("view", None)  # ?view belongs to those two tabs

# --- Summary --------------------------------------------------------------------
with tabs["summary"]:
    if tabs["summary"].open:
        st.header("Risk over time", help=f"Recomputed for every year since {config.HISTORY_START} with the data "
                                         "available that year, relative to the other countries that year.")
        if country_hist["composite"].notna().sum() >= 2:
            st.plotly_chart(charts.risk_history(country_hist, marks=True), config={"displayModeBar": False})
            st.caption(f"{year} uses IMF estimates."
                       f'<span class="sg-sr"> {html.escape(charts.history_summary(country_hist))}</span>',
                       unsafe_allow_html=True)
        else:
            st.info("Not enough history to draw a trend for this country.")

        c1, c2 = st.columns([1.1, 1])
        with c1:
            st.header("What the data says")
            for line in scoring.country_brief(iso3, name, values, scores, core["series"], countries, year):
                st.markdown(f"- {line}")
        with c2:
            outlook = data.get_outlook(core, core["version"])
            mine = None if outlook is None else outlook.predictions.set_index("iso3").reindex([iso3]).iloc[0]
            if mine is not None and isinstance(mine["status"], str):
                st.header("Conflict outlook")
                if mine["status"] == "In armed conflict":
                    st.markdown(f"In armed conflict in the latest data ({outlook.data_year}).")
                else:
                    level = ui.sev_mark("serious" if mine["relative"] >= 3 else "warning", spoken=False) \
                        if mine["relative"] >= 1 else ""
                    st.markdown(f"{level}A {mine['probability']:.1%} chance that armed conflict breaks out in "
                                f"{outlook.index_year + 1}: {mine['relative']:.1f}× the average for a country at peace.",
                                unsafe_allow_html=True)
                st.page_link("app_pages/conflict.py", label="How this is estimated",
                             icon=":material/insights:", query_params={"tab": "outlook"})
            st.header("Red flags", help="Fixed thresholds (e.g. inflation ≥ 20%), independent of how other "
                                        "countries score.")
            if flags:
                for f in sorted(flags, key=lambda f: config.SEVERITY_ORDER[f["severity"]]):
                    st.markdown(f"{ui.sev_mark(f['severity'], spoken=False)}{SEVERITY_LABEL[f['severity']]}: "
                                f"{html.escape(f['label'])}", unsafe_allow_html=True)
            else:
                st.markdown("No absolute warning thresholds crossed.")

            st.header("Upcoming events")
            country_events = content.load_events()
            ui.upcoming_events(country_events[country_events["iso3"] == iso3].assign(country=name), limit=5)
            st.page_link("app_pages/hotspots.py", label="Event calendar", icon=":material/event:",
                         query_params={"tab": "calendar"})

        real_life = st.expander("What it means in real life", key="real_life", on_change="rerun")
        with real_life:
            if real_life.open:  # built only when opened
                reading = interpret.country_reading(iso3, table, values, scores, hist, content.load_events(),
                                                    core.get("flows"), year, core["series"])
                ui.render_reading(reading, key=f"real_{iso3}")
                st.page_link("app_pages/guide.py", label="Guide: reading the numbers", icon=":material/explore:")

        st.header("Pillar scores")
        peers = table[table["region"] == row["region"]]
        st.plotly_chart(charts.pillar_bars(s, peers[[p.key for p in PILLARS]].median()), config={"displayModeBar": False})

        with st.expander("Sensitivity to the weights"):
            sens = data.get_sensitivity(core, year, iso3, ui.weights_tuple(), core["version"])
            st.dataframe(
                sens.round(1), hide_index=True,
                column_config={
                    "Score": st.column_config.NumberColumn(format="%.1f"),
                    "Rank": st.column_config.NumberColumn(format="%d"),
                },
            )
            st.caption(
                "If the rank barely moves when a pillar is dropped, the result does not hinge on that choice. "
                "Large swings show which pillar drives the score."
            )
        ui.cite("index", "ucdp_def", "imf_ara", "ifes")


# --- Peers ------------------------------------------------------------------------
def peer_ranking() -> None:
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
        place = (f"Highest risk of {len(ranked)}" if position[0] == 0
                 else f"{scoring._ordinal(position[0] + 1)} highest risk of {len(ranked)}")
        st.markdown(
            f"{place} in this group (group median {ranked['composite'].median():.0f})."
            f'<span class="sg-sr"> In the chart, {html.escape(name)} scores {s["composite"]:.0f} of 100; the group\'s '
            f"scores run from {ranked['composite'].min():.0f} to {ranked['composite'].max():.0f}.</span>",
            unsafe_allow_html=True,
        )
    st.plotly_chart(charts.peer_strip(s, peer_df[peer_df["iso3"] != iso3], name), config={"displayModeBar": False})
    ui.cite("index", "wb_countries")

    st.header("Peer ranking")
    peer_table = ranked.assign(name=[f"▶ {n}" if i == iso3 else n for i, n in zip(ranked["iso3"], ranked["name"])],
                               group_rank=range(1, len(ranked) + 1))
    start = max(0, min((position[0] if len(position) else 0) - 5, len(peer_table) - 11))  # 11 rows around it
    peer_table = peer_table.iloc[start:start + 11]
    ui.country_table(
        peer_table, key="peer_table", height="content", sort="group_rank",
        extra={"group_rank": st.column_config.NumberColumn("Group rank", format="%d", width=100)},
    )
    st.caption(f"▶ marks {name}. Group ranks {start + 1} to {start + len(peer_table)} of {len(ranked)}.")

    st.header("Most similar risk profiles", help=f"Countries anywhere in the world whose stability, governance, "
                                                 f"economic and social scores are closest to {name}'s.")
    like = scoring.similar(scores, iso3, n=8)
    if like.empty:
        st.caption("Not enough data to compare profiles.")
    else:
        similar_table = table.set_index("iso3").loc[like.index].reset_index().assign(
            closeness=(100 - like["distance"].to_numpy()).clip(0, 100))
        ui.country_table(
            similar_table, key="similar_table", height="content",
            sort="closeness", ascending=False,
            extra={"closeness": st.column_config.ProgressColumn(
                "Similarity", min_value=0, max_value=100, format="%.0f", width=100,
                help="100 = the same four pillar scores; based on the distance between the profiles")},
        )


def peer_map() -> None:
    flows = core.get("flows")
    ui.globe_panel(table=table, hist=hist, flows=flows, metric="composite", metric_label="Composite",
                   key=f"profile_globe_{iso3}", focus=iso3, height=520,
                   layers={"spin": False, "flows": True, "conflict": True},
                   hint=f"Arcs = refugees from or hosted by {name} · ▶ replays since {config.HISTORY_START}",
                   # with no flow data there are no charts below for the globe's failure note to point to
                   fallback=None if flows is not None and not flows.empty else "Everything else on the page still works.")
    ui.cite("unhcr", "ucdp", "natural_earth")
    if flows is None or flows.empty:
        return
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
            st.caption(f"{'About ' if total >= 1000 else ''}{scoring._about(total)} people in total ({flows_year}, UNHCR: "
                       "refugees, asylum seekers and others in need of international protection).")


with tabs["peers"]:
    if tabs["peers"].open:
        if ui.url_view("Peers view", PEERS_VIEWS, key="peers_view") == PEERS_VIEWS["map"]:
            peer_map()
        else:
            peer_ranking()

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
WHATIF_PREFIX = f"wi_{iso3}_{core['version']}_"  # new data starts the sliders afresh, not as edits


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
    st.session_state[WHATIF_PREFIX + "preset"] = name  # shown as selected until the next preset or a reset
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
    st.header("What-if simulator", help="Every country is re-scored, as in the real index.")
    specs = _whatif_controls()
    picked = st.session_state.get(WHATIF_PREFIX + "preset")
    with st.container(horizontal=True, wrap=True, key="whatif_presets"):  # full names; they wrap instead of truncating
        for preset in WHATIF_PRESETS:
            st.button(preset, on_click=_apply_preset, args=(preset, specs), key=f"preset_{preset}",
                      type="primary" if preset == picked else "secondary")
        st.button("Reset indicators", on_click=_reset_whatif, key="whatif_reset", icon=":material/restart_alt:")

    controls, results = st.container(key="split_whatif").columns([1, 1.15], gap="large")
    changes, moved = {}, []
    with controls:
        live = st.empty()  # the result in one line, kept in view over the sliders when the split stacks (ui.py)
        # a pillar opens once one of its values is changed and stays open until a reset or the next preset:
        # following the values instead would close it under the user when a slider goes back to its start
        opened = st.session_state.setdefault(WHATIF_PREFIX + "opened", set())
        for i, pillar in enumerate(PILLARS):
            keys = [k for k, s in specs.items() if s["ind"].pillar == pillar.key]
            if not keys:
                continue
            if any(st.session_state.get(WHATIF_PREFIX + k, specs[k]["current"]) != specs[k]["current"] for k in keys):
                opened.add(pillar.key)
            with st.expander(pillar.label, expanded=i == 0 or pillar.key in opened):
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
        riskier = rank_delta < 0  # rank 1 = highest risk: riskier reads as up, like the score
        places = f"{abs(rank_delta)} place{'s' if abs(rank_delta) > 1 else ''} {'riskier' if riskier else 'safer'}"
        score_change = f"{score_delta:+.1f}" if round(score_delta, 1) else None
        live.markdown(f'<div class="sg-whatif-live" aria-hidden="true"><span>Score {n["composite"]:.0f}'  # short enough for one phone line
                      f'{f" ({score_change})" if score_change else ""} · Rank {int(n["rank"])}</span>{ui.tier_badge(n["tier"])}</div>',
                      unsafe_allow_html=True)
        r1, r2 = st.columns(2)  # two figures fit a half-width panel; the tier goes on its own line below
        r1.metric("Composite score (of 100)", f"{n['composite']:.0f}", delta=score_change, delta_color="inverse")
        r2.metric(f"Global rank (of {int(n['n_ranked'])})", f"{int(n['rank'])}", delta=places if rank_delta else None,
                  delta_color="red" if riskier else "green", delta_arrow="up" if riskier else "down",
                  help="1 = highest risk, so a smaller number means riskier.")
        was = f" <span style='color:var(--sg-muted)'>was {s['tier']}</span>" if n["tier"] != s["tier"] else ""
        st.markdown(f"Risk tier&nbsp; {ui.tier_badge(n['tier'])}{was}", unsafe_allow_html=True)
        st.plotly_chart(charts.whatif_pillars(s, n), config={"displayModeBar": False}, key="whatif_chart")
        ui.cite("index")

        new_flags, eased = scoring.flag_changes(v, new_values)  # a worse flag is new; one that eases or goes is cleared
        cleared = {f["label"] for f in eased}
        if new_flags or cleared:
            st.markdown("**Red flags in this scenario**")
            for f in new_flags:
                st.markdown(f"{ui.sev_mark(f['severity'])}New: {html.escape(f['label'])}", unsafe_allow_html=True)
            for label in sorted(cleared):
                st.markdown(f"Cleared: {label}")
        if moved:
            st.caption((f"Scenario: {picked}. " if picked else "") + "Changed: " + ", ".join(moved) + ".")
        elif picked:  # no data for it, already past its values, or every slider moved back
            st.caption(f"Scenario: {picked}. No value differs from {name}'s own data.")


with tabs["whatif"]:
    if tabs["whatif"].open:
        what_if_simulator()


# --- Data: indicators, governance trends and the economy ---------------------------------
def indicators() -> None:
    st.header("Every indicator behind the score")
    rows = []
    for ind in INDICATORS:
        raw = v.get(ind.key)
        yr = v.get(f"{ind.key}__year")
        rows.append({
            "Indicator": ind.short,
            "Value": ind.fmt(raw),
            "Risk score": s.get(f"n_{ind.key}"),
            "Year": "—" if pd.isna(yr) else str(int(yr)),
            "Pillar": config.PILLAR_BY_KEY[ind.pillar].short,
            "Unit": ind.unit,
            "Source": ind.source,
            "Data": config.indicator_url(ind),
            "Full name": ind.label,
            "Direction": "Higher = riskier" if ind.higher_is_riskier else "Lower = riskier",
        })
    st.dataframe(
        pd.DataFrame(rows).round({"Risk score": 0}), hide_index=True, height=640,
        column_config={
            "Indicator": st.column_config.TextColumn(pinned=True),
            "Value": st.column_config.TextColumn(alignment="right"),
            "Risk score": st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%.0f",
                help="Position relative to all other countries (0–100). Battle deaths and displacement use a log "
                     "scale so that countries without conflict score 0."),
            # capped so the grid fits a 970px column; the long ones show in full in the download
            "Unit": st.column_config.TextColumn(width=140),
            "Source": st.column_config.TextColumn(width=180),
            "Data": st.column_config.LinkColumn("Data", display_text="Open ↗", width="small",
                                                help="The source's own page for this indicator"),
            # hidden to fit the screen: in the download below, and Show/hide columns brings them back
            "Full name": None, "Direction": None,
        },
    )
    ui.cite("index")
    with st.expander(f"Cross-check {name} with independent sources"):
        st.caption("Indices that measure similar things but are not used in the score.")
        for pillar_key, keys in config.CROSS_CHECKS.items():
            label = ("**Overall fragility**" if pillar_key == "composite" else ui.pillar_chip(pillar_key))
            st.markdown(f"{label} &nbsp; " + " · ".join(ui.source_link(k, config.SOURCES[k].name) for k in keys),
                        unsafe_allow_html=True)
        st.page_link(ui.SOURCES_PAGE, label="All sources and cross-checks", icon=":material/verified:")
    export = pd.DataFrame(rows).assign(Country=name, ISO3=iso3)
    st.download_button("Download indicators (CSV)", export.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"{iso3}_indicators_{year}.csv", mime="text/csv")


def governance() -> None:
    st.header("Governance over time", help="World Bank WGI scores (0–100, higher = better governance) with the 90% "
                                           "confidence interval. When intervals for two years overlap, the change may "
                                           "be within the margin of error.")
    with st.spinner("Loading confidence intervals…"):
        ci = data.load_wgi_ci()
    st.plotly_chart(charts.wgi_small_multiples(core["series"], ci, iso3), config={"displayModeBar": False})
    ui.cite("wgi")
    trend_rows = []
    for dim in WGI_DIMENSIONS:
        t = scoring.wgi_trend(core["series"], iso3, dim)
        if not t:
            continue
        overlap = scoring.ci_overlap(core["series"], ci, iso3, dim, t["start_year"], t["end_year"])
        trend_rows.append({
            "Dimension": config.INDICATOR_BY_KEY[f"wgi_{dim}"].short,
            f"Score {t['start_year']}": round(t["start"], 1),
            f"Score {t['end_year']}": round(t["end"], 1),
            "Change": round(t["change"], 1),
            "Statistically clear?": "—" if overlap is None else ("No (intervals overlap)" if overlap else "Yes"),
        })
    if trend_rows:
        trend_df = pd.DataFrame(trend_rows)
        # Change shows signed but stays a number, so it sorts as one
        st.dataframe(trend_df.style.format(interpret.signed, subset=["Change"], na_rep="—"), hide_index=True,
                     placeholder="—",  # the grid draws missing cells itself
                     column_config={
                         "Dimension": st.column_config.TextColumn(pinned=True),
                         **{c: st.column_config.NumberColumn(format="%.1f") for c in trend_df
                            if c.startswith("Score ")},
                     })


def economy() -> None:
    edition = core["meta"].get("gdp_growth", {}).get("edition") or "IMF World Economic Outlook"
    st.header("Macroeconomic picture")
    st.caption(f"Dashed lines are IMF projections ({edition}).")
    st.plotly_chart(charts.macro_small_multiples(core["series"], iso3, year), config={"displayModeBar": False})
    ui.cite("imf", "wdi", "unhcr")
    # a missing figure reads "No data" in small grey, not a big dash. Only the inline p shrinks, so the value's
    # line box keeps its height and the text sits on the same bottom line as its neighbours
    st.html('<style>[class*="st-key-econ_nodata_"] [data-testid="stMetricValue"] p { font-size: 0.875rem !important;'
            ' color: var(--sg-muted) !important; }</style>')
    for col, (key, label, tip) in zip(st.columns(3), (
        ("reserves_months", "FX reserves (months of imports)", "World Bank WDI. Below 3 months is a common warning line."),
        ("youth_unemployment", "Youth unemployment (%)", None),
        ("displaced_share", "Displaced (% of population)",
         "Refugees, asylum seekers, others in need of protection and IDPs from this country (UNHCR)."),
    )):
        raw = v.get(key)
        with col.container(key=f"econ_{'nodata_' if pd.isna(raw) else ''}{key}"):
            st.metric(label, "No data" if pd.isna(raw) else config.INDICATOR_BY_KEY[key].fmt(raw), help=tip)


with tabs["data"]:
    if tabs["data"].open:
        data_view = ui.url_view("Data view", DATA_VIEWS, key="data_view")
        if data_view == DATA_VIEWS["governance"]:
            governance()
        elif data_view == DATA_VIEWS["economy"]:
            economy()
        else:
            indicators()

# --- News pulse -------------------------------------------------------------------------
with tabs["news"]:
    if tabs["news"].open:
        news_name = config.NEWS_NAMES.get(iso3, name)
        st.header("Risk-related news, last 7 days",
                  help=f"Live headlines matching '{news_name}' plus risk keywords (protest, election, coup, sanctions, "
                       "clashes…), newest first, from Bing News and Google News, with GDELT as a backup.")
        ui.news_list(news_name, limit=20)

        with ui.guard("Video reports"):
            st.header(f"Video reports on {name}",
                      help="From the latest uploads of international broadcasters and think tanks.")
            all_videos = data.load_videos()
            about = (ui.videos_about(all_videos, iso3, names, countries.set_index("iso3").get("official_name", pd.Series())
                                     .get(iso3)) if all_videos is not None else None)
            if about is None or about.empty:
                st.caption(f"None of the latest videos mention {name}.")
            else:
                ui.video_gallery(about, key=f"profile_videos_{iso3}", limit=6)
            st.page_link("app_pages/video.py", label="Live TV and all video reports", icon=":material/live_tv:")
        with ui.guard("Media tone"):
            if st.toggle("Media tone, last 3 months (GDELT)",
                         help="GDELT average tone of English-language coverage. A sustained fall often precedes or "
                              "accompanies crises."):
                tone, terr = data.load_tone(news_name)
                if terr:
                    st.info("GDELT's tone data can't be reached right now. Try again in a few minutes.")
                elif tone is None or tone.empty:
                    st.info("No tone data returned.")
                else:
                    st.plotly_chart(charts.tone_chart(tone), config={"displayModeBar": False})
        with ui.guard("Protest coverage"):
            if st.toggle("Protest coverage, last 3 months (GDELT)",
                         help=f"Share of all English-language news GDELT monitors that mentions {name} together with "
                              "protests, riots, strikes or unrest, smoothed over a week."):
                protests, perr = data.load_protests(news_name)
                if perr:
                    st.info("GDELT's protest data can't be reached right now (it allows few requests). Try again in a few "
                            "minutes.")
                elif protests is None or protests.empty:
                    st.info("No protest coverage found.")
                else:
                    st.plotly_chart(charts.protest_chart(protests), config={"displayModeBar": False})
        ui.cite("news", "gdelt", "youtube")

# --- Analyst assessment -------------------------------------------------------------------
with tabs["assessment"]:
    if tabs["assessment"].open:
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
                    f"The analyst rates {name} {abs(gap)} tier{'s' if abs(gap) > 1 else ''} "
                    f"{'higher' if gap > 0 else 'lower'} than the model ({model_tier}). "
                    "The reasoning is under *Why my rating differs from the model*."
                )
            st.caption(f"By {m.get('author') or 'the analyst'} · horizon {m.get('horizon') or '—'}")
            st.divider()
            st.markdown(ui.money(assessment["body"]))
        else:
            st.info(f"No analyst assessment for {name} yet.")
            st.markdown("Write one in the Assessment builder and add the file to the project's `assessments/` folder.")
            st.page_link("app_pages/builder.py", label="Open the assessment builder", icon=":material/edit_note:")

# The header's sources and other profiles of the country, under the tabs so the tabs sit right below the header
elsewhere = ([("World Bank", f"https://data.worldbank.org/country/{row['iso2']}")] if isinstance(row["iso2"], str) else []) + [
    ("IMF", f"https://www.imf.org/en/countries/{iso3.lower()}"),
    ("ReliefWeb", f"https://reliefweb.int/country/{iso3.lower()}")]
if row["income"] != "High income":  # FAO's food-security briefs cover developing countries
    elsewhere.append(("FAO food security", f"https://www.fao.org/giews/countrybrief/country.jsp?code={iso3}"))
sources = " · ".join(f"[{ui.source_label(k)}]({config.SOURCES[k].url})" for k in ("wb_countries", "wdi", "imf"))
st.caption(f"Region, income, population and GDP: {sources}  \nElsewhere: " + " · ".join(f"[{label} ↗]({url})" for label, url in elsewhere))

ui.footer()
