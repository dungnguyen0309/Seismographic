"""Indicator explorer: any one of the index's indicators on the 3D globe, with its distribution and leaders."""

import pandas as pd
import streamlit as st

from prm import charts, config, ui

core, year, values, scores = ui.load()
hist = ui.history(core)
table = ui.master_table(core, values, scores, hist)

ui.hero("Indicator explorer", "Any indicator behind the index, country by country.")

options = [i.key for i in config.SCORED_INDICATORS]
labels = {i.key: f"{config.PILLAR_BY_KEY[i.pillar].short} · {i.label}" for i in config.SCORED_INDICATORS}
c1, c2 = st.columns([2, 1])
key = c1.selectbox("Indicator", options, format_func=labels.get, key="exp_indicator")
regions = sorted(table["region"].dropna().unique())
region = c2.selectbox("Region", ["All regions", *regions], key="exp_region")
ind = config.INDICATOR_BY_KEY[key]

frame = table[["iso3", "flag", "name", "region"]].copy()
frame["value"] = frame["iso3"].map(values[key])
frame["year"] = frame["iso3"].map(values[f"{key}__year"]) if f"{key}__year" in values else year
frame["risk"] = frame["iso3"].map(scores[f"n_{key}"])
view = frame if region == "All regions" else frame[frame["region"] == region]
known = view.dropna(subset=["value"])

median = ind.fmt(known["value"].median()) if len(known) else "—"
st.caption(  # one caption and no KPI row, so on a phone the first list starts on the first screen
    f"{ind.description}  \n{ind.unit} · {'higher' if ind.higher_is_riskier else 'lower'} = riskier · "
    f"{len(known)} countries with data, median {median} · source: [{ind.source}]({ind.source_url})"
    f" · [see the data ↗]({config.indicator_url(ind)})"
)
source = config.indicator_source(ind)

# --- Leaders ----------------------------------------------------------------------------------------
n = min(10, len(known) // 2)  # a small region splits in two, so no country shows in both lists
lists = ((("risky", f"Riskiest {n}", known.nlargest(n, "risk")), ("safe", f"Safest {n}", known.nsmallest(n, "risk")))
         if n >= 2 else (("all", f"All {len(known)} countries", known.sort_values("risk", ascending=False)),))
for part, title, rows in lists:
    if rows.empty:
        break
    st.header(title)  # stacked: side by side, the half-width tables hid the risk score behind a sideways scroll
    rows = rows.assign(shown=rows["value"].map(ind.fmt)).reset_index(drop=True)
    event = st.dataframe(
        rows[["iso3", "name", "shown", "risk", "flag", "year"]].round({"risk": 0}), hide_index=True, on_select="rerun",
        selection_mode="single-row", key=f"exp_{part}",
        column_config={
            "iso3": None, "flag": ui.FLAG_COLUMN, "name": ui.NAME_COLUMN,
            "shown": st.column_config.TextColumn(ind.unit, alignment="right", width=100, help=ind.unit),
            "risk": st.column_config.ProgressColumn("Risk score", min_value=0, max_value=100, format="%.0f",
                                                    color=config.PILLAR_COLORS[ind.pillar]),
            "year": st.column_config.NumberColumn("Year", format="%d"),
        },
    )
    ui.open_selected(event, rows, f"exp_{part}")

# --- Globe ------------------------------------------------------------------------------------------
st.header("On the globe")
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
ui.cite(source, "natural_earth")

# --- Distribution ----------------------------------------------------------------------------------------
st.header("How countries are spread")
st.plotly_chart(charts.distribution(known["value"], f"{ind.short} ({ind.unit})", config.PILLAR_COLORS[ind.pillar],
                                    log=ind.norm == "log"), config={"displayModeBar": False})
ui.cite(source)

ui.footer()
