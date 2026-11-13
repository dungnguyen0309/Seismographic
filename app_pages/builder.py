"""Assessment builder: write a structured country assessment and download it as a Markdown file."""

import datetime as dt

import pandas as pd
import streamlit as st

from prm import config, content, scoring, ui
from prm.config import ESTIMATIVE_LANGUAGE, TIER_ORDER

core, year, values, scores = ui.load()
countries = core["countries"]
options, names = ui.country_options(countries)

# Streamlit forgets a page's widgets when the visitor opens another page. Every field is copied to a "_draft_" key,
# which it keeps, and put back on return, so a half-written assessment survives a look at a country profile.
TEXT = ["b_bluf", "b_watch", "b_divergence", "b_implications", "b_sources", "j1", "j2", "j3",
        "drv_political", "drv_security", "drv_economic", "drv_social",
        *[f"{k}_{label}" for label in ("Base case", "Upside", "Downside") for k in ("sd", "ss")]]
DRAFT = [*TEXT, "b_iso3", "b_rating", "b_outlook", "b_confidence", "b_horizon", "b_author", "jp1", "jp2", "jp3",
         "sp_Base case", "sp_Upside", "sp_Downside"]


def _typed(key: str) -> bool:
    """The analyst wrote something here (figures the button filled in do not count)."""
    text = str(st.session_state.get(f"_draft_{key}", "")).strip()
    return bool(text) and text != str(st.session_state.get(f"_filled_{key}", "")).strip()


# Without anything typed there is no draft to keep, so the builder opens on the visitor's current country again
if any(_typed(k) for k in TEXT) or st.session_state.get("_draft_b_author", config.AUTHOR) != config.AUTHOR:
    for k in DRAFT:
        if k not in st.session_state and f"_draft_{k}" in st.session_state:
            st.session_state[k] = st.session_state[f"_draft_{k}"]


def _model_tier(code: str) -> str:
    tier = scores.loc[code, "tier"]
    return tier if tier in TIER_ORDER else "Elevated"


def _new_country() -> None:
    st.session_state["b_rating"] = _model_tier(st.session_state["b_iso3"])  # the rating starts from the model again


# Defaults go into session state (not the widgets), so a restored draft never clashes with them
st.session_state.setdefault("b_iso3", ui.current_country(countries))
st.session_state.setdefault("b_rating", _model_tier(st.session_state["b_iso3"]))
for key, default in {"b_outlook": content.OUTLOOKS[1], "b_confidence": content.CONFIDENCE[1], "b_horizon": "12 months",
                     "b_author": config.AUTHOR, "jp1": 65, "jp2": 50, "jp3": 50,
                     "sp_Base case": 60, "sp_Upside": 15, "sp_Downside": 25}.items():
    st.session_state.setdefault(key, default)

ui.hero("Assessment builder")

iso3 = st.selectbox("Country", options, key="b_iso3", on_change=_new_country, format_func=lambda i: names.get(i, i))
name = names[iso3]
s = scores.loc[iso3]

with st.container(border=True):
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown("**Model view**")
        st.markdown(ui.tier_badge(s["tier"]), unsafe_allow_html=True)
        st.caption("Score " + ("—" if pd.isna(s["composite"]) else f"{s['composite']:.0f}/100"))
    with c2:
        st.markdown("**Latest data**")
        for line in scoring.country_brief(iso3, name, values, scores, core["series"], countries, year)[:5]:
            st.markdown(f"- {line}")
    ui.cite("index")

with st.expander("Estimative language (ICD 203)"):
    st.dataframe(
        pd.DataFrame(
            [{"Term": t, "Alternative": alt, "Probability": f"{lo}–{hi}%"} for t, alt, lo, hi in ESTIMATIVE_LANGUAGE]
        ),
        hide_index=True,
    )
    st.caption("Pick a probability and the builder inserts the matching term, so words and numbers agree.")
    ui.cite("icd203")

st.header("1 · Rating")
r1, r2, r3, r4 = st.columns(4)
analyst_rating = r1.selectbox("Your risk rating", TIER_ORDER, key="b_rating",
                              help="Defaults to the model tier. Change it if your judgment differs, and explain why below.")
outlook = r2.selectbox("Outlook", content.OUTLOOKS, key="b_outlook")
confidence = r3.selectbox("Confidence", content.CONFIDENCE, key="b_confidence",
                          help="How solid is the evidence base? Low = thin or conflicting sources.")
horizon = r4.selectbox("Time horizon", ["6 months", "12 months", "24 months"], key="b_horizon")
author = st.text_input("Author", key="b_author")

st.header("2 · Bottom line up front")
bluf = st.text_area(
    "Bottom line (required)", help="Two or three sentences a busy reader can act on.",
    placeholder=f"e.g. {name}'s risk is likely to rise over the next 12 months as … The main threat to operations is … "
                "A shift to … would signal a worse path.",
    height=110, key="b_bluf",
)

st.header("3 · Key judgments")
judgments = []
for i in range(1, 4):
    j1, j2 = st.columns([4, 1])
    text = j1.text_input(f"Judgment {i}" + (" (required)" if i == 1 else ""), key=f"j{i}", placeholder="A specific, checkable statement about the future")
    prob = j2.slider("Probability %", 1, 99, key=f"jp{i}")
    j2.caption(f"→ *{config.estimative_term(prob)}*")
    judgments.append({"text": text, "probability": prob, "term": config.estimative_term(prob)})

DRIVER_FACTS = {  # which indicators feed each driver box when pre-filling
    "drv_political": ["wgi_va", "wgi_ge", "wgi_rl", "wgi_cc", "wgi_rq"],
    "drv_security": ["wgi_pv", "battle_deaths_100k", "homicide"],
    "drv_economic": ["inflation", "gdp_growth", "gov_debt", "fiscal_balance", "current_account", "reserves_months"],
    "drv_social": ["unemployment", "youth_unemployment", "displaced_share"],
}


def _facts(keys: list[str]) -> str:
    """The data behind one driver, as bullet points to rewrite into analysis."""
    v, flags = values.loc[iso3], {f["key"]: f["label"] for f in scoring.red_flags(values.loc[iso3])}
    lines = []
    for key in keys:
        ind = config.INDICATOR_BY_KEY[key]
        raw, yr, risk = v.get(key), v.get(f"{key}__year"), s.get(f"n_{key}")
        if raw is None or pd.isna(raw):
            continue
        line = f"- {ind.short}: {ind.fmt(raw)} {ind.unit}" + ("" if pd.isna(yr) else f" ({int(yr)})")
        if risk is not None and pd.notna(risk):
            line += f", risk score {risk:.0f}/100"
        if key in flags or (key == "battle_deaths_100k" and "battle_deaths_raw" in flags):
            line += f" ⚑ {flags.get(key) or flags['battle_deaths_raw']}"
        lines.append(line)
    return "\n".join(lines + ["→ Why, and which way is it heading? (your analysis)"]) if lines else ""


def _prefill() -> None:
    for widget_key, keys in DRIVER_FACTS.items():
        current = st.session_state.get(widget_key, "")
        # never over what the analyst has written, but figures filled in earlier (another country) are refreshed
        if not current.strip() or current == st.session_state.get(f"_filled_{widget_key}"):
            st.session_state[widget_key] = st.session_state[f"_filled_{widget_key}"] = _facts(keys)


st.header("4 · Drivers")
st.button("Fill in the latest figures", on_click=_prefill,
          help="Puts the latest figures in the driver boxes you have not written in. "
               "Replace them with your analysis: why it is happening and what comes next.")
d1, d2 = st.columns(2)
drv_political = d1.text_area("Political", height=150, key="drv_political",
                             placeholder="Elections, succession, coalition dynamics, protest…")
drv_security = d2.text_area("Security", height=150, key="drv_security",
                            placeholder="Insurgency, crime, border disputes, military's role…")
drv_economic = d1.text_area("Economic", height=150, key="drv_economic",
                            placeholder="Inflation, debt, IMF programme, commodity exposure…")
drv_social = d2.text_area("Social", height=150, key="drv_social",
                          placeholder="Youth unemployment, displacement, ethnic or religious cleavages…")

st.header("5 · Scenarios", help="Probabilities should add up to 100%.")
scenarios = []
for label in ("Base case", "Upside", "Downside"):
    with st.container(border=True):
        s1, s2 = st.columns([1, 3])
        p = s1.number_input(f"{label} probability %", 0, 100, step=5, key=f"sp_{label}")
        desc = s2.text_area(f"{label}: what it looks like", height=80, key=f"sd_{label}")
        signs = s2.text_input(f"{label}: signposts", key=f"ss_{label}")
        scenarios.append({"name": label, "probability": int(p), "description": desc, "signposts": signs})
total = sum(x["probability"] for x in scenarios)
if total != 100:
    st.warning(f"Scenario probabilities add up to {total}%. Adjust them so they total 100%.")

st.header("6 · Indicators, implications and sources")
watch = st.text_area("Indicators to watch (one per line)", height=110, key="b_watch",
                     placeholder="Central bank reserves below 3 months of imports\nArmy statements on the election timetable")
divergence = st.text_area(
    "Why your rating differs from the model (if it does)", height=100, key="b_divergence",
    placeholder="The model is backward-looking: WGI data runs to last year and does not yet capture …",
)
implications = st.text_area("Implications for businesses, NGOs or governments", height=100, key="b_implications")
sources_txt = st.text_area("Sources, one per line (required)", height=110, key="b_sources",
                           placeholder="IMF Article IV report, 2026\nCrisis Group, CrisisWatch, September 2026")

for k in DRAFT:
    if k in st.session_state:
        st.session_state[f"_draft_{k}"] = st.session_state[k]

fields = {
    "country": name, "iso3": iso3, "author": author, "date": dt.date.today().isoformat(),
    "analyst_rating": analyst_rating, "outlook": outlook, "confidence": confidence, "horizon": horizon,
    "model_score": "" if pd.isna(s["composite"]) else f"{s['composite']:.0f} ({s['tier']})",
    "bluf": bluf, "judgments": judgments, "drv_political": drv_political, "drv_security": drv_security,
    "drv_economic": drv_economic, "drv_social": drv_social, "scenarios": scenarios,
    "indicators_to_watch": watch, "divergence": divergence, "implications": implications, "sources": sources_txt,
}
markdown = content.build_assessment_markdown(fields)

st.header("7 · Preview and download")
p1, p2 = st.columns([1, 1])
with p1:
    st.download_button("Download " + f"{iso3}.md", markdown.encode("utf-8"), file_name=f"{iso3}.md",
                       mime="text/markdown", type="primary")
    st.caption(f"Add `{iso3}.md` to the project's `assessments/` folder; it shows on the country profile within "
               "about 10 minutes.")
with p2:
    missing = [n for n, val in [("bottom line", bluf), ("a key judgment", judgments[0]["text"]), ("sources", sources_txt)] if not val.strip()]
    if missing:
        st.warning("Still missing: " + ", ".join(missing))
    else:
        st.success("All core sections filled in.")
with st.container(border=True):
    _meta, body = content.parse_front_matter(markdown)
    st.markdown(ui.money(body))

ui.footer()
