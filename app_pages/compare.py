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
st.caption(
    f"Pick up to {MAX_COMPARE} countries, or use Add to compare on any country profile. "
    "Colours follow the order you pick them in."
)

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
            rank = "—" if pd.isna(r["rank"]) else f"#{int(r['rank'])}"
            tier_colour = config.TIER_COLORS.get(r["tier"], config.INK["faint"])
            st.markdown(f'<div class="sg-cmp-score"><span class="sg-cs-num" style="--c:{tier_colour}">{score}</span>'
                        f'{ui.tier_badge(r["tier"])}</div>'
                        f'<div class="sg-cmp-meta"><span>Rank {rank}</span> · '
                        f'<span>{int(r["flags"])} red flag{"" if int(r["flags"]) == 1 else "s"}</span> · '
                        f'<span>{r.get("trend", "—")} in a year</span></div>',
                        unsafe_allow_html=True)

st.header("On the globe")
ui.globe_panel(table=table.reset_index(), hist=hist, flows=core.get("flows"), metric="composite",
               metric_label="Composite", key="cmp_globe", in_view=set(picked), height=480,
               layers={"spin": True, "flows": False, "conflict": False})
ui.cite("index", "natural_earth")

st.header("Risk index over time")
st.plotly_chart(
    charts.compare_lines({"composite": hist.rename(columns={"composite": "value"})}, "composite", picked, names,
                         "Composite risk score (0–100)"),
    config={"displayModeBar": False},
)
st.caption(f"The index recomputed for every year since {config.HISTORY_START} (relative to all countries that year). "
           "Higher = riskier.")
ui.cite("index")

left, right = st.columns([1, 1.2])
with left:
    st.header("Pillar profile")
    st.plotly_chart(charts.radar(sel[[p.key for p in PILLARS]], names), config={"displayModeBar": False})
    st.caption("Further from the centre = higher risk.")
    ui.cite("index")
with right:
    st.header("Governance over time")
    dim = st.selectbox("WGI dimension", list(WGI_DIMENSIONS), index=1, format_func=WGI_DIMENSIONS.get)
    st.plotly_chart(
        charts.compare_lines(core["series"], f"wgi_{dim}", picked, names, "WGI score (0–100, higher = better)"),
        config={"displayModeBar": False},
    )
    ui.cite("wgi")

# --- Indicator table -------------------------------------------------------------
st.header("Indicators")
rows = []
for ind in INDICATORS:
    label = ind.short if "(" in ind.short or "/" in ind.short else f"{ind.short} ({ind.unit})"  # no doubled units
    entry = {"Pillar": config.PILLAR_BY_KEY[ind.pillar].short, "Indicator": label}
    for iso3 in picked:
        entry[names[iso3]] = ind.fmt(values.loc[iso3].get(ind.key))
    rows.append(entry)
for p in PILLARS:
    entry = {"Pillar": "Score", "Indicator": f"{p.label} (0–100 risk)"}
    for iso3 in picked:
        val = sel.loc[iso3, p.key]
        entry[names[iso3]] = "—" if pd.isna(val) else f"{val:.0f}"
    rows.append(entry)
st.dataframe(pd.DataFrame(rows), hide_index=True, height=min(38 * (len(rows) + 1), 820))
ui.cite("index")

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
ui.cite("imf")

ui.footer()
