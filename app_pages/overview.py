"""Global overview: the headline numbers, the globe and the news, then hotspots, changes, the ranking and the risk
matrix in tabs."""

import pandas as pd
import streamlit as st

from prm import a11y, charts, config, content, data, globe, interpret, scoring, ui
from prm.config import PILLARS


core, year, values, scores = ui.load()
hist = ui.history(core)
table = ui.master_table(core, values, scores, hist)


# The headlines are a network call: on a full page run they are filled in last, so the rest of the page shows first.
# Globe clicks re-run only the fragment, after the page is drawn, and fill them at once.
_page_drawn = False
_deferred_news: list = []


def _fill_news(slot, query: str | None) -> None:
    with slot.container():
        ui.news_list(query, limit=12)


def _show_flat() -> None:
    st.session_state["ov_map_style"] = "Flat map"
    a11y.keep_focus("ov_map_style")  # the globe and its focused button leave the page; the keyboard lands on the switch


@st.fragment(run_every="10m")
def globe_with_news(metric: str, map_title: str, in_view: set[str], region: str | None) -> None:
    """The 3D globe plus a news column that follows the country clicked on it (re-checked every 10 minutes)."""
    split = st.container(key="split_ov_globe")  # the news column moves under the globe when space is short
    g_col, n_col = split.columns([2.2, 1], gap="small")
    open_iso3, selected = None, st.session_state.get("globe_selected")
    with g_col, ui.guard("The 3D globe"):
        open_iso3, selected = globe.risk_globe(
            table, hist, core.get("flows"), metric, map_title, in_view, region=region,
            selected=st.session_state.get("globe_selected"), on_flat=_show_flat,
        )
    if st.session_state.get("ov_map_style") == "Flat map":  # "Show the flat map" in the globe's failure note
        st.rerun()  # the whole page: the map style control sits outside this fragment
    st.session_state["globe_selected"] = selected
    if open_iso3:
        ui.go_to_country(open_iso3)
    names = dict(zip(table["iso3"], table["name"]))
    with n_col, st.container(height=globe.HEIGHT, border=True, key="ov_news"):
        if selected in names:
            row = table.set_index("iso3").loc[selected]
            ui.country_heading(names[selected], row["iso2"], level=2, css="sg-panel-title")
            news = config.NEWS_NAMES.get(selected, names[selected])
        else:
            st.markdown('<h2 class="sg-panel-title">Global risk news</h2>', unsafe_allow_html=True)
            news = None
        slot = st.empty()
        slot.caption("Loading headlines…")
        st.page_link("app_pages/video.py", label="Watch live TV news", icon=":material/live_tv:")
    if _page_drawn:
        _fill_news(slot, news)
    else:
        _deferred_news.append((slot, news))


def _pick_region() -> None:
    """Clicking a region's bar in the tier chart filters the page to that region."""
    points = st.session_state["tier_click"]["selection"]["points"]
    if points and points[0].get("y"):
        full = {config.region_short(r): r for r in table["region"].dropna().unique()}
        st.session_state["ov_region"] = full.get(points[0]["y"], points[0]["y"])


head = st.container()  # the title and the headline numbers count the filtered view: filled once the filters are read

# --- Map controls: what the map shows, and one filter for the whole page ---------------------------------------
regions = sorted(table["region"].dropna().unique())
incomes = [i for i in ["Low income", "Lower middle income", "Upper middle income", "High income"] if i in set(table["income"])]
metric_options = {"composite": "Composite risk index", **{p.key: p.label for p in PILLARS}}
picked_region = st.session_state.get("ov_region", "All regions")
picked_incomes = st.session_state.get("ov_income") or []
active = ([config.region_short(picked_region)] if picked_region != "All regions" else []) + (
    [f"{len(picked_incomes)} income group{'s' if len(picked_incomes) > 1 else ''}"] if picked_incomes else [])

# The controls sit on the map's top edge, borders shared, so they read as one panel with the globe's own buttons
st.html('<style>.st-key-ov_controls { gap: 8px !important; padding: 10px 12px; background: var(--sg-raised);'
        ' border: 1px solid var(--sg-line); border-radius: 14px 14px 0 0; }'
        '@media (max-width: 640px) { .st-key-ov_controls { padding: 8px; } }'  # Map style and Filter share a row
        '[data-testid="stLayoutWrapper"]:has(> .st-key-ov_controls) { margin-bottom: calc(-1rem - 1px); }'
        '.st-key-split_ov_globe .rg-wrap, .st-key-ov_news { border-top-left-radius: 0 !important;'
        ' border-top-right-radius: 0 !important; }'
        '@container sgsplit (max-width: 780px) { .st-key-ov_news { border-radius: 0.5rem !important; } }</style>')
with st.container(horizontal=True, vertical_alignment="bottom", wrap=True, key="ov_controls"):
    metric = st.selectbox("Map shows", list(metric_options), format_func=metric_options.get, width=290,
                          help="Composite: the weighted average of the four pillar scores. Each pillar scores one area "
                               "of risk (stability, governance, economy, social) from 0 to 100. Higher is riskier.")
    st.session_state.setdefault("ov_map_style", "3D globe")  # seeded, not a default: the globe's note can set it
    map_style = st.segmented_control("Map style", ["3D globe", "Flat map"], key="ov_map_style",
                                     help="3D globe: drag to rotate, Ctrl/⌘ + scroll or +/− to zoom, click a country. "
                                          "On a touch screen, tap the globe first.") or "3D globe"
    with st.popover("Filter: " + " · ".join(active) if active else "Filter", icon=":material/filter_list:",
                    help="Limit the whole page to a region or income group"
                         + (". The globe dims the countries outside it." if active and map_style == "3D globe" else "")):
        region = st.selectbox("Region", ["All regions", *regions], key="ov_region")
        income = st.multiselect("Income group", incomes, placeholder="All income groups", key="ov_income")

view = table.copy()
if region != "All regions":
    view = view[view["region"] == region]
if income:
    view = view[view["income"].isin(income)]
scored = view.dropna(subset=["composite"])
n_high = int(scored["tier"].isin(["High", "Severe"]).sum())

# --- Title and headline numbers (delta = vs last year) ------------------------------------------------------
yearly = hist[hist["iso3"].isin(view["iso3"])].groupby("year").agg(
    high=("tier", lambda s: int(s.isin(["High", "Severe"]).sum())),
    median=("composite", "median"),
    conflict=("battle_deaths_raw", lambda s: int((s >= 25).sum())),
)
last = yearly.loc[year - 1] if year - 1 in yearly.index else None
vs = f"vs {year - 1}"
n_conflict = int((scored["battle_deaths_raw"] >= 25).sum())
median_now = scored["composite"].median() if len(scored) else None
with head:
    ui.hero("Global overview", " · ".join([str(year), *active]))
    if not st.session_state.get("_explored"):  # until the visitor opens the Introduction
        st.page_link("app_pages/intro.py", label="Introduction: how the index works", icon=":material/info:")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Countries scored", f"{len(scored)}")
    k2.metric("High or Severe risk", n_high,
              delta=None if last is None else int(n_high - last["high"]), delta_color="inverse", delta_description=vs)
    k3.metric("Median score", "—" if median_now is None else f"{median_now:.0f}", **ui.median_delta(median_now, last),
              delta_description=vs)
    k4.metric("In armed conflict", n_conflict,
              delta=None if last is None else int(n_conflict - last["conflict"]), delta_color="inverse",
              delta_description=vs, help="Countries with at least 25 battle-related deaths in the latest UCDP year.")
    n_assessed = int((view["assessment"] == "✓").sum())
    if n_assessed:
        k5.metric("Assessments", n_assessed, help="Countries with a written assessment in the assessments/ folder.")
    else:  # until assessments are written, the most severe warnings (most countries have some lesser flag)
        critical = sum(any(f["severity"] == "critical" for f in scoring.red_flags(values.loc[i]))
                       for i in scored["iso3"])
        k5.metric("Critical red flag", critical,
                  help="War-level violence (1,000+ battle deaths in a year) or inflation of 50% or more. "
                       f"{int((scored['flags'] > 0).sum())} of {len(scored)} have at least one red flag.")

# --- Map ---------------------------------------------------------------------
map_title = "Composite" if metric == "composite" else config.PILLAR_BY_KEY[metric].short
if map_style == "3D globe":
    globe_with_news(metric, map_title, set(view["iso3"]), None if region == "All regions" else region)
    picked_iso3 = None
else:
    flat = charts.choropleth(view, metric, map_title, zoom_to_data=region != "All regions")
    if metric == "composite":
        flat.update_traces(showscale=False)  # the tier legend under the map is the one legend
    map_event = st.plotly_chart(flat, config={"displayModeBar": False}, on_select="rerun", selection_mode="points",
                                key="map_click")
    picked_iso3 = ui.clicked_iso3(map_event)
if picked_iso3:
    ui.go_to_country(picked_iso3)
if metric == "composite":
    st.markdown(ui.tier_legend(), unsafe_allow_html=True)  # its last swatch is the maps' no-data grey
else:
    st.markdown(ui.pillar_chip(metric, f"{config.PILLAR_BY_KEY[metric].label}: brighter = riskier, grey = no data"),
                unsafe_allow_html=True)
# the page's one Sources line: the tabs' event calendar, country facts and flags are named here too
ui.cite("index", "natural_earth", *(["news", "gdelt"] if map_style == "3D globe" else []), "ifes", "wb_countries",
        "flags")
ui.following_strip(table)

# --- The rest, one tab at a time (only the open tab is computed) -----------------------------------------------
TABS = {"hotspots": ":material/warning: Hotspots", "changes": ":material/trending_up: Changes",
        "ranking": ":material/format_list_numbered: Ranking", "matrix": ":material/scatter_plot: Risk matrix"}
tab_hot, tab_changes, tab_rank, tab_matrix = ui.url_tabs(TABS, key="ov_tab")  # ?tab=ranking opens the ranking

with tab_hot:
    if tab_hot.open:
        st.caption(
            "Countries scoring 50 or more that also got at least 2 points riskier "
            f"since {year - 1}, crossed a new red-flag threshold, or face a high-significance event in the next 120 days."
        )
        prev_values = data.get_values(core, year - 1, core["version"])
        today = pd.Timestamp.today().normalize()
        events = content.load_events()
        soon = events[(events["date"] >= today) & (events["date"] <= today + pd.Timedelta(days=120))
                      & (events["significance"].str.title() == "High")].sort_values("date").groupby("iso3").first()
        hotspots = []
        for r in view[view["composite"] >= 50].itertuples(index=False):
            reasons = []
            if pd.notna(r.delta_1y) and r.delta_1y >= 2:
                reasons.append(f"▲ {r.delta_1y:+.1f} since {year - 1}")
            new = [f["label"] for f in scoring.flag_changes(prev_values.loc[r.iso3], values.loc[r.iso3])[0]]
            if new:
                reasons.append("⚑ New: " + new[0] + (f" (+{len(new) - 1} more)" if len(new) > 1 else ""))
            if r.iso3 in soon.index:
                e = soon.loc[r.iso3]
                reasons.append(f"{e['event']} {interpret.countdown((e['date'] - today).days)}")
            if reasons:
                hotspots.append({"iso3": r.iso3, "name": r.name, "composite": r.composite,
                                 "tier": r.tier, "signals": len(reasons), "why": " · ".join(reasons)})
        hotspots = pd.DataFrame(hotspots, columns=["iso3", "name", "composite", "why", "tier", "signals"])
        if hotspots.empty:
            st.info("No hotspots with the current filters.")
        else:
            hotspots = hotspots.sort_values(["signals", "composite"], ascending=False).head(6).reset_index(drop=True)
            hot_event = st.dataframe(
                ui.tier_cells(hotspots.round({"composite": 0})), hide_index=True, on_select="rerun",
                selection_mode="single-row",
                key="ov_hotspots", row_height=66, height=38 + 66 * len(hotspots),  # over 64 px, text wraps
                # Fixed widths that fit the 810 px table at 1280 px; auto-sized columns get squeezed and cut mid-word.
                # No flag: at this row height it was the loudest mark. The signal count is hidden: the reasons list
                # them, and it still sets the order.
                column_config={
                    "iso3": None, "signals": None,
                    "name": st.column_config.TextColumn("Country", width=190, pinned=True),
                    "composite": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.0f",
                                                                 color=ui.BAR_COLOR, width=100),
                    "why": st.column_config.TextColumn(
                        "Why it is on the list", width=365,
                        help=f"▲ = riskier since {year - 1}. ⚑ = a red-flag threshold crossed this year that was not "
                             f"crossed in {year - 1}."),
                    "tier": st.column_config.TextColumn("Tier", width=100),
                },
            )
            ui.open_selected(hot_event, hotspots, "overview_hotspots")
            st.page_link("app_pages/overview.py", label="Full ranking", icon=":material/format_list_numbered:",
                         query_params={"tab": "ranking"})

with tab_changes:
    if tab_changes.open:
        st.header(f"Biggest moves since {year - 1}")
        ui.movers_lists(view, n=5, key="ov_movers")
        st.page_link("app_pages/changes.py", label="All score changes this year", icon=":material/trending_up:")

        st.header("Biggest movers in political stability",
                  help="From the World Bank's Worldwide Governance Indicators (WGI), which combine surveys and expert "
                       "assessments of how each country is governed.")
        changes = scoring.wgi_changes(core["series"], core["countries"], "pv")
        if region != "All regions" or income:
            changes = changes[changes["iso3"].isin(view["iso3"])]
        if changes.empty:
            st.info("Not enough governance data to show changes.")
        else:
            names = dict(zip(table["iso3"], table["name"]))
            changes = changes.assign(name=changes["iso3"].map(names))
            y0, y1 = int(changes["start_year"].iloc[0]), int(changes["end_year"].iloc[0])
            st.caption(
                f"Change in the World Bank's *Political Stability & Absence of Violence* score, {y0} → {y1}. "
                "Red = worse, blue = better. Small changes may be within the margin of error, shown on each country "
                "profile."
            )
            movers_event = st.plotly_chart(charts.movers(changes), config={"displayModeBar": False},
                                           on_select="rerun", selection_mode="points", key="movers_click")
            if iso3 := ui.clicked_iso3(movers_event):
                ui.go_to_country(iso3)

with tab_rank:
    if tab_rank.open:
        ranking = view.sort_values("rank", na_position="last")[
            ["iso3", "name", "composite", "trend", "flag", "tier", "rank", *[p.key for p in PILLARS], "flags", "region",
             "coverage", "assessment", "analyst_rating"]
        ].reset_index(drop=True)
        pillar_cols = {
            p.key: st.column_config.ProgressColumn(p.short, min_value=0, max_value=100, format="%.0f", help=p.label,
                                                   color=config.PILLAR_COLORS[p.key])
            for p in PILLARS
        }
        weights = dict(ui.weights_tuple())
        event = st.dataframe(  # the CSV keeps full values
            ui.tier_cells(ranking.round().assign(region=ranking["region"].map(config.region_short))),
            hide_index=True,
            height=460,
            placeholder="—",
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "iso3": None,
                # after the figures and not pinned: on a phone the score sits next to the pinned name
                "flag": ui.FLAG_COLUMN,
                "name": ui.NAME_COLUMN,
                "region": st.column_config.TextColumn("Region", width="medium"),
                "rank": st.column_config.NumberColumn("Rank", format="%d", help="1 = highest risk"),
                "composite": st.column_config.ProgressColumn(
                    "Composite", min_value=0, max_value=100, format="%.0f", color=ui.BAR_COLOR, width=100,  # fits the name
                    help="Weighted average of the pillar scores ("
                         + ", ".join(f"{p.short} {weights[p.key] / 100:.0%}" for p in PILLARS)
                         + "), from 0 to 100. Higher is riskier."),
                "trend": st.column_config.TextColumn(
                    "1-yr change", alignment="right", width=110,  # auto-sizing cuts the header
                    help=f"Composite score vs {year - 1}. ▲ = riskier, ▼ = safer, ■ = under 1 point"),
                "tier": st.column_config.TextColumn("Tier", width=100),  # the filled cell needs the room
                **pillar_cols,
                "flags": st.column_config.NumberColumn("Red flags", format="%d",
                                                       help="Warning thresholds crossed, plus a falling political stability trend"),
                "coverage": st.column_config.NumberColumn("Data coverage", format="%.0f%%"),
                "assessment": st.column_config.TextColumn("Assessment", help="A written analyst assessment exists"),
                "analyst_rating": "Analyst rating",
            },
        )
        ui.open_selected(event, ranking, "overview_ranking")
        st.download_button(
            "Download ranking (CSV)",
            ranking.drop(columns=["iso3", "flag"]).to_csv(index=False).encode("utf-8-sig"),
            file_name=f"seismographic_risk_index_{year}.csv",
            mime="text/csv",
        )

with tab_matrix:
    if tab_matrix.open:
        left, right = st.columns(2)
        with left:
            st.header("Risk matrix")
            axis_labels = {p.key: p.label for p in PILLARS}
            a1, a2 = st.columns(2)
            x_key = a1.selectbox("Horizontal axis", list(axis_labels), index=0, format_func=axis_labels.get)
            y_key = a2.selectbox("Vertical axis", list(axis_labels), index=2, format_func=axis_labels.get)
            matrix_event = st.plotly_chart(
                charts.risk_matrix(scored, x_key, y_key), config={"displayModeBar": False},
                on_select="rerun", selection_mode="points", key="matrix_click",
            )
            if iso3 := ui.clicked_iso3(matrix_event):
                ui.go_to_country(iso3)
            st.caption("Bubble size = population.")
        with right:
            if region == "All regions":
                st.header("Risk tiers by region")
                st.plotly_chart(charts.tier_distribution(scored), config={"displayModeBar": False},
                                on_select=_pick_region, selection_mode="points", key="tier_click")
                st.caption("Regions sorted by the share of countries rated High or Severe.")
            else:
                st.header(f"Highest risk in {region}")
                top = scored.nsmallest(12, "rank").copy()
                st.dataframe(
                    ui.tier_cells(top[["name", "composite", "flag", "tier", "flags"]].round()),
                    hide_index=True,
                    column_config={
                        "flag": ui.FLAG_COLUMN,
                        "name": ui.NAME_COLUMN,
                        "composite": st.column_config.ProgressColumn("Score", min_value=0, max_value=100,
                                                                     format="%.0f", color=ui.BAR_COLOR),
                        "tier": st.column_config.TextColumn("Tier", width=100),
                        "flags": st.column_config.NumberColumn("Red flags", format="%d"),
                    },
                )

ui.data_status(core)
ui.footer()

for _slot, _news in _deferred_news:
    _fill_news(_slot, _news)
_deferred_news.clear()
_page_drawn = True
