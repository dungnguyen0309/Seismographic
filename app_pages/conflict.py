"""Conflict & displacement: battle deaths (UCDP via the World Bank) and forced displacement (UNHCR)."""

import pandas as pd
import streamlit as st

from prm import charts, config, data, forecast, ui

core, year, values, scores = ui.load()
hist = ui.history(core)
table = ui.master_table(core, values, scores, hist)
names = dict(zip(table["iso3"], table["name"]))
known = set(names)

ui.hero("Conflict & displacement", "Where people are being killed in armed conflict and forced from their homes.")

# --- Data -------------------------------------------------------------------------------------------
bd = core["series"].get("battle_deaths", pd.DataFrame(columns=["iso3", "year", "value"]))
bd = bd[bd["iso3"].isin(known)]
dp = core["series"].get("displaced", pd.DataFrame(columns=["iso3", "year", "value"]))
dp = dp[dp["iso3"].isin(known)]
flows = core.get("flows")
bd_year = int(bd["year"].max()) if len(bd) else None
dp_year = int(dp["year"].max()) if len(dp) else None
latest_bd = bd[bd["year"] == bd_year].set_index("iso3")["value"] if bd_year else pd.Series(dtype=float)
prev_bd = bd[bd["year"] == bd_year - 1].set_index("iso3")["value"] if bd_year else pd.Series(dtype=float)

# --- Headline numbers ----------------------------------------------------------------------------------
deaths_by_year = bd.groupby("year")["value"].sum()
displaced_by_year = dp.groupby("year")["value"].sum()
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Active armed conflicts", int((latest_bd >= 25).sum()), border=True, height="stretch",
          delta=None if prev_bd.empty else int((latest_bd >= 25).sum() - (prev_bd >= 25).sum()), delta_color="inverse",
          help=f"Countries with at least 25 battle-related deaths in {bd_year}: the Uppsala Conflict Data "
               "Program's threshold for state-based armed conflict (via the World Bank)")
k2.metric("At war", int((latest_bd >= 1000).sum()), border=True, height="stretch",
          delta=None if prev_bd.empty else int((latest_bd >= 1000).sum() - (prev_bd >= 1000).sum()),
          delta_color="inverse", help=f"At least 1,000 battle-related deaths in {bd_year}")
k3.metric(f"Battle deaths, {bd_year}", f"{latest_bd.sum():,.0f}", border=True, height="stretch",
          delta=None if prev_bd.empty else f"{(latest_bd.sum() / prev_bd.sum() - 1):+.0%}" if prev_bd.sum() else None,
          delta_color="inverse")
k4.metric(f"Forcibly displaced, {dp_year}", ui.fmt_population(displaced_by_year.iloc[-1]) if len(displaced_by_year) else "—",
          border=True, height="stretch",
          delta=f"{(displaced_by_year.iloc[-1] / displaced_by_year.iloc[-2] - 1):+.0%}" if len(displaced_by_year) > 1 else None,
          delta_color="inverse", help="Refugees, asylum seekers, others in need of international protection and internally displaced "
               "people (UNHCR)")
k5.metric("Refugees across borders", ui.fmt_population(flows["value"].sum()) if flows is not None else "—", border=True,
          height="stretch",
          help="Refugees, asylum seekers and others in need of protection living outside their country (UNHCR)")
ui.cite("ucdp", "ucdp_def", "unhcr")

# --- The globe: stability risk, conflict rings, refugee arcs -------------------------------------------------
st.header("On the globe")
displaced_now = dp[dp["year"] == dp_year].set_index("iso3")["value"] if dp_year else pd.Series(dtype=float)
notes = {}
for iso3 in known:
    parts = []
    if latest_bd.get(iso3, 0) >= 25:
        parts.append(f"{latest_bd[iso3]:,.0f} battle deaths in {bd_year}")
    if displaced_now.get(iso3, 0) >= 100_000:
        parts.append(f"{ui.fmt_population(displaced_now[iso3])} people displaced ({dp_year})")
    if parts:
        notes[iso3] = " · ".join(parts)
ui.globe_panel(table=table, hist=hist, flows=flows, metric="stability", metric_label="Stability", key="cf_globe",
               notes=notes, layers={"spin": True, "flows": True, "conflict": True},
               hint="Rings = armed conflict · arcs = refugee flows · ▶ replays since " + str(config.HISTORY_START))
st.caption("Countries coloured by the Political Stability & Violence pillar (brighter = riskier). Rings mark "
           "armed conflict (bigger and faster = more deaths); arcs run from refugees' origin to their host country. "
           "Click a country to see only its flows.")
ui.cite("index", "ucdp", "unhcr", "natural_earth")

TABS = {"conflict": ":material/swords: Armed conflict", "displacement": ":material/luggage: Displacement & refugees",
        "outlook": ":material/insights: Outlook"}
if st.query_params.get("tab") in TABS:  # e.g. ?tab=outlook, from the country profile and the Methodology page
    st.session_state["conflict_tab"] = TABS[st.query_params["tab"]]
    del st.query_params["tab"]
tab_conflict, tab_displacement, tab_outlook = st.tabs(list(TABS.values()), key="conflict_tab", on_change="rerun")

# --- Armed conflict ------------------------------------------------------------------------------------------
with tab_conflict:
    if tab_conflict.open:
        c1, c2 = st.columns(2)
        with c1:
            st.header("Battle deaths worldwide")
            recent = deaths_by_year[deaths_by_year.index >= 1990]
            st.plotly_chart(charts.yearly_bars(recent.index, recent.values, "Battle-related deaths", charts.WORSE, "deaths"),
                            config={"displayModeBar": False})
            st.caption("Sum over all countries of deaths in state-based armed conflict (UCDP), by the country where they occurred.")
            ui.cite("ucdp", "ucdp_def")
        with c2:
            st.header("Deadliest conflicts over time")
            top = latest_bd.nlargest(6).index.tolist()
            st.plotly_chart(charts.compare_lines(core["series"], "battle_deaths", top, names, "Battle-related deaths",
                                                 start_year=2010), config={"displayModeBar": False})
            st.caption(f"The six countries with the most battle deaths in {bd_year}.")
            ui.cite("ucdp")

        st.header(f"Countries in armed conflict ({bd_year})")
        st.caption("At least 25 battle-related deaths in the year. Tick a row to open the country.")
        conflict = table[table["iso3"].isin(latest_bd[latest_bd >= 25].index)].copy()
        conflict["deaths"] = conflict["iso3"].map(latest_bd)
        conflict["deaths_prev"] = conflict["iso3"].map(prev_bd).fillna(0)
        conflict["deaths_change"] = conflict["deaths"] - conflict["deaths_prev"]
        conflict = conflict.join(values[["battle_deaths_100k", "displaced_share"]], on="iso3")
        conflict["level"] = conflict["deaths"].map(lambda d: "War" if d >= 1000 else "Armed conflict")
        conflict["change_text"] = conflict["deaths_change"].map(lambda d: f"{d:+,.0f}")
        conflict = conflict.sort_values("deaths", ascending=False).reset_index(drop=True)
        event = st.dataframe(
            conflict[["iso3", "flag", "name", "level", "deaths", "change_text", "battle_deaths_100k", "displaced_share",
                      "stability", "tier"]],
            hide_index=True, height=460, on_select="rerun", selection_mode="single-row", key="cf_table",
            column_config={
                "iso3": None, "flag": ui.FLAG_COLUMN, "name": "Country",
                "level": st.column_config.TextColumn("Level", help="War = 1,000 or more battle deaths in the year (UCDP)"),
                "deaths": st.column_config.NumberColumn(f"Deaths {bd_year}", format="localized"),
                "change_text": st.column_config.TextColumn(f"vs {bd_year - 1}"),
                "battle_deaths_100k": st.column_config.NumberColumn("Per 100k", format="%.2f"),
                "displaced_share": st.column_config.NumberColumn("Displaced", format="%.1f%%", help="Share of the population"),
                "stability": st.column_config.ProgressColumn("Stability risk", min_value=0, max_value=100, format="%.0f",
                                                             color=config.PILLAR_COLORS["stability"]),
                "tier": "Tier",
            },
        )
        ui.cite("ucdp", "ucdp_def", "unhcr", "wgi")
        ui.open_selected(event, conflict, "conflict_conflict")

# --- Displacement ----------------------------------------------------------------------------------------------
with tab_displacement:
    if tab_displacement.open:
        d1, d2 = st.columns(2)
        with d1:
            st.header("Forcibly displaced people")
            st.plotly_chart(charts.yearly_bars(displaced_by_year.index, displaced_by_year.values, "People",
                                               config.PILLAR_COLORS["social"], "people"), config={"displayModeBar": False})
            st.caption("Refugees, asylum seekers, others in need of protection and internally displaced people, by year (UNHCR).")
            ui.cite("unhcr")
        with d2:
            st.header(f"Largest displaced populations ({dp_year})")
            origins = dp[dp["year"] == dp_year].nlargest(10, "value").assign(name=lambda d: d["iso3"].map(names))
            event = st.plotly_chart(charts.ranked_bars(origins, "value", "name", charts.WORSE, "people displaced"),
                                    config={"displayModeBar": False}, on_select="rerun", selection_mode="points",
                                    key="cf_origins")
            ui.cite("unhcr")
            if iso3 := ui.clicked_iso3(event):
                ui.go_to_country(iso3)

        if flows is not None and not flows.empty:
            flows_year = int(flows["year"].max())
            h1, h2 = st.columns([1, 1.6])
            with h1:
                st.header(f"Largest host countries ({flows_year})")
                hosts = (flows[flows["host"].isin(known)].groupby("host", as_index=False)["value"].sum()
                         .nlargest(10, "value").rename(columns={"host": "iso3"}))
                hosts["name"] = hosts["iso3"].map(names)
                event = st.plotly_chart(charts.ranked_bars(hosts, "value", "name", charts.BETTER, "refugees hosted"),
                                        config={"displayModeBar": False}, on_select="rerun", selection_mode="points",
                                        key="cf_hosts")
                ui.cite("unhcr")
                if iso3 := ui.clicked_iso3(event):
                    ui.go_to_country(iso3)
            with h2:
                st.header("The 25 largest refugee corridors")
                st.plotly_chart(charts.refugee_sankey(flows, names), config={"displayModeBar": False})
                st.caption("Origins (red, left) to host countries (blue, right); band width = people. Hover for numbers. "
                           "Internally displaced people are not included, as they never cross a border.")
                ui.cite("unhcr")
        else:
            st.info("Refugee flow data is not available right now.")

# --- Outlook: chance of new armed conflict next year ----------------------------------------------------------
with tab_outlook:
    if tab_outlook.open:
        outlook = data.get_outlook(core, core["version"])
        if outlook is None:
            st.info("Not enough conflict history to run the outlook model right now.")
        else:
            nxt = outlook.index_year + 1
            preds = outlook.predictions.merge(table[["iso3", "flag", "name", "tier", "composite"]], on="iso3", how="left")
            peaceful = preds.dropna(subset=["probability"]).sort_values("probability", ascending=False)
            st.markdown(
                f"The chance that armed conflict (25+ battle deaths) breaks out in {nxt} in each country that is at "
                f"peace in the latest conflict data ({outlook.data_year}). A statistical model learned the pattern from "
                f"every year since {config.HISTORY_START}, and was tested on years it had not seen."
            )
            o1, o2, o3, o4 = st.columns(4)
            o1.metric("Average chance", f"{outlook.base_rate:.1%}", border=True, height="stretch",
                      help="How often armed conflict broke out the next year in a country at peace, since "
                           f"{config.HISTORY_START}.")
            top = peaceful.iloc[0] if len(peaceful) else None
            o2.metric("Highest chance", "—" if top is None else f"{top['probability']:.0%}", border=True,
                      height="stretch", help=None if top is None else str(top["name"]))
            o3.metric("Tested accuracy", "—" if outlook.auc is None else f"{outlook.auc:.2f}", border=True,
                      height="stretch",
                      help="On years the model had not seen: the chance a country where conflict broke out had a higher "
                           "prediction than one where it did not (the AUC). 0.5 = a coin flip, 1 = perfect.")
            o4.metric("Already in conflict", int((preds["status"] == "In armed conflict").sum()), border=True,
                      height="stretch",
                      help=f"25+ battle deaths in {outlook.data_year}: not given a chance of a new outbreak.")

            st.header(f"Highest chance of new conflict in {nxt}")
            shown = peaceful.head(20).assign(chance=lambda d: d["probability"] * 100,
                                             recent=lambda d: d["recent_conflict"].map({1.0: "yes", 0.0: ""}))
            event = st.dataframe(
                shown[["iso3", "flag", "name", "chance", "relative", "recent", "tier"]].reset_index(drop=True),
                hide_index=True, on_select="rerun", selection_mode="single-row", key="outlook_table",
                column_config={
                    "iso3": None, "flag": ui.FLAG_COLUMN, "name": "Country",
                    "chance": st.column_config.ProgressColumn("Chance", min_value=0, max_value=max(30.0, shown["chance"].max()),
                                                              format="%.1f%%", color="#fd8078"),
                    "relative": st.column_config.NumberColumn("× average", format="%.1f×"),
                    "recent": st.column_config.TextColumn("Conflict in past 5 yrs"), "tier": "Index tier",
                },
            )
            ui.open_selected(event, shown, "conflict_shown")
            g1, g2 = st.columns(2)
            with g1:
                st.header("What raises the chance")
                st.plotly_chart(charts.outlook_drivers(outlook.coefficients, forecast.FEATURE_LABELS),
                                config={"displayModeBar": False})
            with g2:
                st.header("Tested on unseen years")
                st.plotly_chart(charts.calibration_bars(outlook.calibration), config={"displayModeBar": False})
                if outlook.brier_skill is not None:
                    st.caption(f"{len(outlook.backtest):,} country-years, {int(outlook.backtest['onset'].sum())} new "
                               f"conflicts. The predictions beat the average rate by {outlook.brier_skill:.0%} "
                               "(Brier skill score).")
            st.caption(
                "A statistical estimate across countries; it cannot foresee any one event. Few conflicts break out "
                f"each year, the conflict data end in {outlook.data_year}, and coups or invasions can come without "
                "warning in this data. Use it to decide where to look closer."
            )
            ui.cite("ucdp", "ucdp_def", "index")

ui.footer()
