"""Economic stress monitor: inflation, growth, debt, deficits, external balance and reserves for every country."""

import pandas as pd
import streamlit as st

from prm import charts, config, scoring, ui
from prm.charts import ECON_COLUMNS

core, year, values, scores = ui.load()
hist = ui.history(core)
table = ui.master_table(core, values, scores, hist)
econ_keys = [k for k, _ in ECON_COLUMNS]
df = table.join(values[econ_keys], on="iso3")  # table already carries the n_* risk scores

ui.hero("Economic stress", "Where an economic crisis could trigger political trouble.")
edition = core["meta"].get("gdp_growth", {}).get("edition") or "IMF World Economic Outlook"
st.caption(
    f"Figures are {year} estimates from the {edition}, plus World Bank reserves data."
)

regions = sorted(df["region"].dropna().unique())
f1, f2 = st.columns([1, 1])
region = f1.selectbox("Region", ["All regions", *regions], key="eco_region")
view = df if region == "All regions" else df[df["region"] == region]

# --- Headline numbers -----------------------------------------------------------------------------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("High inflation (≥ 20%)", int((view["inflation"] >= 20).sum()), border=True, height="stretch")
k2.metric("Economy shrinking", int((view["gdp_growth"] < 0).sum()), border=True,
          height="stretch", help="Negative real GDP growth")
k3.metric("Public debt ≥ 90% of GDP", int((view["gov_debt"] >= 90).sum()), border=True, height="stretch")
k4.metric("Deficit ≥ 5% of GDP", int((view["fiscal_balance"] <= -5).sum()), border=True, height="stretch")
k5.metric("Reserves < 3 months of imports", int((view["reserves_months"] < 3).sum()), border=True, height="stretch")
ui.cite("imf", "wdi", "imf_ara")
st.page_link("app_pages/stress.py", label="Stress test: apply one shock to many countries", icon=":material/bolt:")

# Economic red flags per country (used by the globe and the warning-lights table)
econ_flag_keys = {"inflation", "gdp_growth", "gov_debt", "fiscal_balance", "current_account", "reserves_months"}
econ_flags = {
    iso3: [f for f in scoring.red_flags(values.loc[iso3]) if f["key"] in econ_flag_keys]
    for iso3 in view["iso3"] if iso3 in values.index
}

# --- Globe ------------------------------------------------------------------------------------------------
st.header("On the globe")
ui.globe_panel(
    table=df, hist=hist, flows=None, metric="economic", metric_label="Economy", key="eco_globe",
    in_view=set(view["iso3"]), region=None if region == "All regions" else region,
    notes={iso3: " · ".join(f"⚑ {f['label']}" for f in hits) for iso3, hits in econ_flags.items() if hits},
    layers={"spin": True, "flows": False, "conflict": False},
)
st.caption("Countries coloured by the Macroeconomic & Financial pillar (brighter = riskier) and raised by it in 3D. "
           "Hover for the warning thresholds a country crosses; ▶ replays since " + str(config.HISTORY_START) + ".")
ui.cite("imf", "wdi")

# --- Heatmap ------------------------------------------------------------------------------------------
st.header("Stress heatmap")
how_many = f2.select_slider("Countries in the heatmap", options=[20, 40, 60, 100, 250], value=40,
                            help="The most economically stressed first (highest Economy pillar score)")
heat = view.dropna(subset=["economic"]).nlargest(how_many, "economic").reset_index(drop=True)
event = st.plotly_chart(charts.econ_heatmap(heat), config={"displayModeBar": False}, on_select="rerun",
                        selection_mode="points", key="eco_heat")
points = getattr(getattr(event, "selection", None), "points", None) or []
if points and points[0].get("y") in set(heat["name"]):
    ui.go_to_country(heat.loc[heat["name"] == points[0]["y"], "iso3"].iloc[0])
st.caption("Each cell shows the actual value; its colour is the risk score relative to all countries (brighter = "
           "riskier). Countries sorted by Economy pillar score. Click a cell to open the country.")
ui.cite("imf", "wdi")

# --- Stagflation scatter and the IMF outlook ---------------------------------------------------------
s_col, o_col = st.columns([1.15, 1])
with s_col:
    st.header("Growth vs inflation")
    event = st.plotly_chart(charts.stagflation_scatter(view), config={"displayModeBar": False}, on_select="rerun",
                            selection_mode="points", key="eco_scatter")
    if iso3 := ui.clicked_iso3(event):
        ui.go_to_country(iso3)
    st.caption("Top-left = prices rising fast while the economy shrinks. Bubble size = population.")
    ui.cite("imf", "wdi")
with o_col:
    st.header("IMF outlook")
    outlook_key = st.segmented_control("Show", ["Inflation", "Growth", "Public debt"], default="Inflation",
                                       key="eco_outlook") or "Inflation"
    series_key, label = {"Inflation": ("inflation", "Inflation (%)"), "Growth": ("gdp_growth", "Real GDP growth (%)"),
                         "Public debt": ("gov_debt", "Public debt (% of GDP)")}[outlook_key]
    series = core["series"][series_key]
    series = series[series["iso3"].isin(view["iso3"])]
    st.plotly_chart(charts.imf_outlook(series, year, label, year - 12, year + 5), config={"displayModeBar": False})
    st.caption(f"Median across the selected countries, with the middle half shaded. Dashed = IMF projections to {year + 5}.")
    ui.cite("imf")

# --- Warning lights -------------------------------------------------------------------------------------
st.header("Countries crossing several warning thresholds")
rows = []
for r in view.itertuples(index=False):
    hits = econ_flags.get(r.iso3, [])
    if len(hits) >= 2:
        rows.append({"iso3": r.iso3, "flag": r.flag, "name": r.name, "count": len(hits),
                     "warnings": " · ".join(f"{f['short']} ({config.SEVERITY_LABEL[f['severity']].lower()})" for f in hits),
                     "economic": r.economic})
warnings = pd.DataFrame(rows, columns=["iso3", "flag", "name", "count", "warnings", "economic"])
if warnings.empty:
    st.caption("No country crosses two or more economic warning thresholds.")
else:
    warnings = warnings.sort_values(["count", "economic"], ascending=False).reset_index(drop=True)
    event = st.dataframe(
        warnings, hide_index=True, height=min(460, 38 * (len(warnings) + 1)), on_select="rerun",
        selection_mode="single-row", key="eco_warnings",
        column_config={
            "iso3": None, "flag": ui.FLAG_COLUMN, "name": "Country", "count": "Warnings",
            "warnings": st.column_config.TextColumn("Thresholds crossed", width="large"),
            "economic": st.column_config.ProgressColumn("Economy risk", min_value=0, max_value=100, format="%.0f",
                                                        color=config.PILLAR_COLORS["economic"]),
        },
    )
    ui.open_selected(event, warnings, "economy_warnings")
    st.caption("Thresholds: inflation ≥ 20%, negative growth, debt ≥ 90% of GDP, deficit or current-account deficit "
               "≥ 5% of GDP, reserves under 3 months of imports. See the Methodology page.")
    ui.cite("imf", "wdi", "imf_ara")

ui.footer()
