"""Indicator explorer: any one of the index's indicators on the 3D globe, with its distribution and leaders."""

import pandas as pd
import streamlit as st

from prm import charts, config, ui

core, year, values, scores = ui.load()
hist = ui.history(core)
table = ui.master_table(core, values, scores, hist)

ui.hero("Indicator explorer", "Any indicator behind the index around the world: where it is worst, how countries "
                               "are spread, and the riskiest and safest countries.")

options = [i.key for i in config.SCORED_INDICATORS]
labels = {i.key: f"{config.PILLAR_BY_KEY[i.pillar].short} · {i.label}" for i in config.SCORED_INDICATORS}
c1, c2 = st.columns([2, 1])
key = c1.selectbox("Indicator", options, format_func=labels.get, key="exp_indicator")
regions = sorted(table["region"].dropna().unique())
region = c2.selectbox("Region", ["All regions", *regions], key="exp_region")
ind = config.INDICATOR_BY_KEY[key]
pillar = config.PILLAR_BY_KEY[ind.pillar]

frame = table[["iso3", "flag", "name", "region"]].copy()
frame["value"] = frame["iso3"].map(values[key])
frame["year"] = frame["iso3"].map(values[f"{key}__year"]) if f"{key}__year" in values else year
frame["risk"] = frame["iso3"].map(scores[f"n_{key}"])
view = frame if region == "All regions" else frame[frame["region"] == region]
known = view.dropna(subset=["value"])

st.markdown(
    f"{ui.pillar_chip(ind.pillar)} &nbsp; **{ind.label}** · {ind.unit} · "
    f"{'higher' if ind.higher_is_riskier else 'lower'} = riskier · source: [{ind.source}]({ind.source_url}) · "
    f"[see the data ↗]({config.indicator_url(ind)})",
    unsafe_allow_html=True,
)
st.caption(ind.description)
source = config.indicator_source(ind)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Countries with data", len(known), border=True)
k2.metric("Median", ind.fmt(known["value"].median()) if len(known) else "—", border=True, help=ind.unit)
worst = known.nlargest(1, "risk")
best = known.nsmallest(1, "risk")
k3.metric("Riskiest", worst["name"].iloc[0] if len(worst) else "—", border=True,
          help=None if worst.empty else f"{ind.fmt(worst['value'].iloc[0])} {ind.unit}")
k4.metric("Safest", best["name"].iloc[0] if len(best) else "—", border=True,
          help=None if best.empty else f"{ind.fmt(best['value'].iloc[0])} {ind.unit}")

# --- Globe ------------------------------------------------------------------------------------------
notes = {
    r.iso3: f"{ind.short}: {ind.fmt(r.value)} {ind.unit}" + ("" if pd.isna(r.year) else f" ({int(r.year)})")
    for r in known.itertuples(index=False)
}
ui.globe_panel(
    table=table, hist=hist, flows=None, metric=ind.pillar, metric_label=f"{ind.short} risk", key="exp_globe",
    in_view=set(view["iso3"]), region=None if region == "All regions" else region,
    custom=frame.set_index("iso3")["risk"], colorscale=config.map_colorscale(ind.pillar), notes=notes,
    layers={"spin": True, "flows": False, "conflict": False},
)
st.caption(f"Colour and height = risk score for this indicator (0 = safest country, 100 = riskiest), in the "
           f"{pillar.short} pillar's colours. Hover for the actual value.")
ui.cite(source, "natural_earth")

# --- Distribution and leaders ----------------------------------------------------------------------------
st.header("How countries are spread")
st.plotly_chart(charts.distribution(known["value"], f"{ind.short} ({ind.unit})", config.PILLAR_COLORS[ind.pillar],
                                    log=ind.norm == "log"), config={"displayModeBar": False})
ui.cite(source)

left, right = st.columns(2)
for col, title, rows in ((left, "Riskiest 10", known.nlargest(10, "risk")), (right, "Safest 10", known.nsmallest(10, "risk"))):
    with col:
        st.header(title)
        rows = rows.assign(shown=rows["value"].map(ind.fmt)).reset_index(drop=True)
        event = st.dataframe(
            rows[["iso3", "flag", "name", "shown", "year", "risk"]], hide_index=True, on_select="rerun",
            selection_mode="single-row", key=f"exp_{title}",
            column_config={
                "iso3": None, "flag": ui.FLAG_COLUMN, "name": "Country", "shown": ind.unit,
                "year": st.column_config.NumberColumn("Year", format="%d"),
                "risk": st.column_config.ProgressColumn("Risk score", min_value=0, max_value=100, format="%.0f",
                                                        color=config.PILLAR_COLORS[ind.pillar]),
            },
        )
        ui.open_selected(event, rows, "explorer_rows")

ui.footer()
