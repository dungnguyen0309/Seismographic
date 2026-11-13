"""Compare up to six countries side by side."""

import html

import pandas as pd
import streamlit as st

from prm import a11y, charts, config, scoring, ui
from prm.config import COUNTRY_COLORS, INDICATORS, MAX_COMPARE, PILLARS, WGI_DIMENSIONS

core, year, values, scores = ui.load()
hist = ui.history(core)
table = ui.master_table(core, values, scores, hist).set_index("iso3")
options, names = ui.country_options(core["countries"])

ui.hero("Compare countries")

# The widget's own state is dropped when you leave the page, so seed it each visit: a shared link (?c=NGA,KEN) first,
# then the list built with "Add to compare", then a default
if "compare_picked" not in st.session_state:
    shared = list(dict.fromkeys(c.strip() for c in str(st.query_params.get("c", "")).upper().split(",")
                                if c.strip() in options))[:MAX_COMPARE]  # a hand-edited link may repeat a country
    saved = list(dict.fromkeys(c for c in st.session_state.get(ui.COMPARE_LIST, []) if c in options))[:MAX_COMPARE]
    fallback = [c for c in [ui.current_country(core["countries"]), "KEN", "ZAF", "ETH"] if c in options]
    st.session_state["compare_picked"] = shared or saved or list(dict.fromkeys(fallback))[:3]


def _add_similar(iso3: str) -> None:
    if iso3 not in st.session_state["compare_picked"] and len(st.session_state["compare_picked"]) < MAX_COMPARE:
        st.session_state["compare_picked"] = [*st.session_state["compare_picked"], iso3]
        a11y.keep_focus("similar_row")  # the button just used disappears: focus moves to the next suggestion


# Each chip wears its country's colour, the same one its lines use in every chart on this page
st.html("<style>" + "".join(
    f'.st-key-compare_picked [data-tag-index="{i}"] {{ background: {c} !important; }}'
    for i, c in enumerate(COUNTRY_COLORS)) + "</style>")
picked = st.multiselect(
    "Countries", options, key="compare_picked", format_func=lambda i: names.get(i, i),
    max_selections=MAX_COMPARE, placeholder="Choose countries",
)
st.session_state[ui.COMPARE_LIST] = list(picked)
if not picked:
    st.query_params.pop("c", None)
    st.info("Choose at least one country.")
    ui.end_page()
st.query_params["c"] = ",".join(picked)  # the address bar now holds a link to this exact comparison
if len(picked) < MAX_COMPARE:
    like = scoring.similar(scores, picked[0], n=8)
    like = [i for i in like.index if i not in picked][:4]
    if like:
        with st.container(horizontal=True, vertical_alignment="center", key="similar_row"):
            st.caption(f"Similar to {names[picked[0]]}:")
            for iso3 in like:
                st.button(f"Add {names[iso3]}", key=f"add_like_{iso3}", on_click=_add_similar, args=(iso3,),
                          type="tertiary", help="A country with a close risk profile across the four pillars")

sel = table.loc[picked]

# --- Scorecards -----------------------------------------------------------------
cols = st.columns(len(picked))
for col, iso3, colour in zip(cols, picked, COUNTRY_COLORS):
    r = sel.loc[iso3]
    with col:
        with st.container(border=True, height="stretch"):
            st.markdown(f'<span class="sg-swatch" style="--c:{colour}"></span>{ui.flag_img(r["iso2"])}'
                        f"<b>{html.escape(names[iso3])}</b>", unsafe_allow_html=True)
            score = "—" if pd.isna(r["composite"]) else f"{r['composite']:.0f}"
            rank = ("—" if pd.isna(r["rank"]) else
                    f'<span title="1 is the highest risk">#{int(r["rank"])}</span>')
            trend = r.get("trend", "—")
            if pd.notna(r.get("delta_1y")):
                said = ui.trend_said(r["delta_1y"], year)
                trend = (f'<span title="{said}"><span aria-hidden="true" style="white-space:nowrap">'
                         f'{trend} in a year</span><span class="sg-sr">{said}</span></span>')
            else:
                trend += " in a year"
            st.markdown(f'<div class="sg-cmp-score"><span class="sg-cs-num">{score}</span>'
                        f'{ui.tier_badge(r["tier"])}</div>'
                        f'<div class="sg-cmp-meta">Rank {rank} · {int(r["flags"])} red flag'
                        f'{"" if int(r["flags"]) == 1 else "s"} · {trend}</div>',
                        unsafe_allow_html=True)

st.header("Risk index over time", help=f"The index recomputed for every year since {config.HISTORY_START}, relative "
                                      "to all countries that year. Higher = riskier.")
st.plotly_chart(
    charts.compare_lines({"composite": hist.rename(columns={"composite": "value"})}, "composite", picked, names,
                         "Composite risk score (0–100)"),
    config={"displayModeBar": False},
)

left, right = st.columns([1, 1.2])
with left:
    st.header("Pillar profile", help="Further from the centre = higher risk.")
    st.plotly_chart(charts.radar(sel[[p.key for p in PILLARS]], names), config={"displayModeBar": False})
with right:
    st.header("Governance over time")
    dim = st.selectbox("WGI dimension", list(WGI_DIMENSIONS), index=1, format_func=WGI_DIMENSIONS.get)
    st.plotly_chart(
        charts.compare_lines(core["series"], f"wgi_{dim}", picked, names, "WGI score (0–100, higher = better)"),
        config={"displayModeBar": False},
    )

# --- Indicator table -------------------------------------------------------------
st.header("Indicators")
rows = []
for ind in INDICATORS:  # short names and the unit last, so the country columns fit beside them on a phone
    rows.append({"Indicator": ind.short, **{names[i]: ind.fmt(values.loc[i].get(ind.key)) for i in picked},
                 "Unit": ind.unit})
for p in PILLARS:
    rows.append({"Indicator": f"{p.short} pillar",
                 **{names[i]: "—" if pd.isna(sel.loc[i, p.key]) else f"{sel.loc[i, p.key]:.0f}" for i in picked},
                 "Unit": "risk score, 0–100"})
st.dataframe(pd.DataFrame(rows), hide_index=True, height="content", column_config={
    "Indicator": st.column_config.TextColumn(pinned=True),
    **{names[i]: st.column_config.TextColumn(alignment="right") for i in picked},
})

# --- Economy over time ----------------------------------------------------------------
st.header("Economic trajectory")
econ = {
    "gdp_growth": "Real GDP growth (%)",
    "inflation": "Inflation (%)",
    "gov_debt": "Public debt (% of GDP)",
    "current_account": "Current account (% of GDP)",
}
key = st.selectbox("Indicator", list(econ), format_func=econ.get)
st.plotly_chart(
    charts.compare_lines(core["series"], key, picked, names, econ[key], start_year=year - 12, end_year=year + 5,
                         projected_from=year),
    config={"displayModeBar": False},
)
ui.cite("index", "wgi", "imf", "flags")

ui.footer()
