"""Regions: one region at a time — scores, trend, risers and fallers, ranking, events and news."""

import pandas as pd
import streamlit as st

from prm import charts, config, content, ui

core, year, values, scores = ui.load()
hist = ui.history(core)
table = ui.master_table(core, values, scores, hist)
table = table.join(values[["displaced_total"]], on="iso3")

regions = sorted(table["region"].dropna().unique())
default = st.query_params.get("region")
region = st.selectbox("Region", regions, index=regions.index(default) if default in regions else 0, key="reg_region")
st.query_params["region"] = region

rv = table[table["region"] == region]
scored = rv.dropna(subset=["composite"])
rh = hist[hist["iso3"].isin(rv["iso3"])]
yearly = rh.groupby("year").agg(median=("composite", "median"),
                                high=("tier", lambda s: int(s.isin(["High", "Severe"]).sum())))
last = yearly.loc[year - 1] if year - 1 in yearly.index else None

ui.hero(f"{region}", f"{len(scored)} economies scored · {year}")

# --- Headline numbers -------------------------------------------------------------------------
median_now = scored["composite"].median() if len(scored) else None
n_high = int(scored["tier"].isin(["High", "Severe"]).sum())
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Median score", "—" if median_now is None else f"{median_now:.0f}", border=True,
          delta=None if last is None or median_now is None else round(float(median_now - last["median"]), 1),
          delta_color="inverse", delta_description=f"vs {year - 1}")
k2.metric("High or Severe risk", n_high, border=True,
          delta=None if last is None else int(n_high - last["high"]), delta_color="inverse",
          delta_description=f"vs {year - 1}")
k3.metric("In armed conflict", int((scored["battle_deaths_raw"] >= 25).sum()), border=True,
          help="At least 25 battle-related deaths in the latest UCDP year")
k4.metric("People displaced from the region", ui.fmt_population(rv["displaced_total"].sum()), border=True,
          help="Refugees, asylum seekers, others in need of protection and IDPs originating from the region (UNHCR)")
riskiest = scored.nsmallest(1, "rank")
k5.metric("Highest risk", riskiest["name"].iloc[0] if len(riskiest) else "—", border=True,
          help="Highest composite score in the region")
ui.cite("index", "unhcr")

# --- Map and tier mix -----------------------------------------------------------------------------
left, right = st.columns([1.3, 1])
with left:
    st.header("Risk globe")
    ui.globe_panel(table=table, hist=hist, flows=core.get("flows"), metric="composite", metric_label="Composite",
                   in_view=set(rv["iso3"]), region=region, key="reg_globe", height=520,
                   layers={"spin": False, "flows": False})
    st.caption("Turned to the region; countries elsewhere are dimmed. Click a country for its index, ▶ to replay "
               f"since {config.HISTORY_START}.")
    ui.cite("index", "natural_earth")
with right:
    st.header(f"Tier mix since {config.HISTORY_START}")
    st.plotly_chart(charts.tier_mix(rh), config={"displayModeBar": False})
    st.caption("How many of the region's countries sat in each tier, year by year.")
    ui.cite("index")

# --- Risers and fallers ---------------------------------------------------------------------------------
st.header(f"Biggest moves since {year - 1}")
ui.movers_lists(rv, n=5, key="reg_movers")
ui.cite("index")

# --- Ranking ----------------------------------------------------------------------------------------------
st.header("Ranking")
st.caption("Click a row to open the country profile.")
ui.country_table(rv, key="reg_table", height=min(460, 38 * (len(rv) + 1)))
ui.cite("index", "wb_countries", "flags")

# --- Events and news ---------------------------------------------------------------------------------------
e_col, n_col = st.columns(2)
with e_col:
    st.header("Upcoming events")
    events = content.load_events()
    events = events[events["iso3"].isin(rv["iso3"])]
    if not events.empty:
        names = dict(zip(table["iso3"], table["name"]))
        events = events.assign(country=events["iso3"].map(names).fillna(events["country"]))
    ui.upcoming_events(events, limit=10)
    ui.cite("ifes")
    st.page_link("app_pages/watchlist.py", label="Full events watchlist", icon=":material/event:")
with n_col:
    st.header("Regional news")
    with st.container(height=520, border=False):
        ui.news_list(config.REGION_NEWS.get(region, region), limit=12)
        ui.cite("news", "gdelt")

ui.footer()
