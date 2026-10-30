"""Introduction: what Seismographic is, how the score is built, and how to start."""

import html

import streamlit as st

from prm import config, interpret, ui
from prm.config import PILLARS, TIERS

core, year, values, scores = ui.load()
n_scored = int(scores["composite"].notna().sum())
weights = ui.weights()
total_weight = sum(weights.values()) or 1

CARD = "background:var(--sg-raised);border:1px solid var(--sg-line);border-radius:10px;padding:14px 16px"


def grid(cards: list[str], min_width: int = 220) -> None:
    st.markdown(f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax({min_width}px,1fr));'
                f'gap:10px;margin:6px 0 14px">{"".join(cards)}</div>', unsafe_allow_html=True)


ui.hero("Introduction", "What Seismographic is and how the score works.")

# --- What it is ------------------------------------------------------------------------------------------
st.header("What it is")
st.markdown(
    f"**{config.APP_TITLE}** is an open-data index of **political, governance, economic and social "
    f"risk** for {n_scored} economies. It is built like professional country-risk models: indicators are "
    "grouped into pillars, and the pillars are combined into one weighted score, with absolute red flags and room "
    "for an analyst's judgment on top. Every figure comes from a public source, and every step of the method is "
    "documented."
)
stats = [
    (n_scored, "economies scored"), (len(config.SCORED_INDICATORS), "indicators"), (len(PILLARS), "pillars"),
    (len(config.INDEX_SOURCES), "open datasets"), (year - config.HISTORY_START + 1, f"years of history ({config.HISTORY_START}–{year})"),
]
grid([f'<div style="{CARD}"><div style="font-size:1.8rem;font-weight:700;line-height:1.1">{n}</div>'
      f'<div style="font-size:0.8rem;color:var(--sg-muted);margin-top:2px">{html.escape(label)}</div></div>'
      for n, label in stats], min_width=140)

# --- How the score is built ----------------------------------------------------------------------------------
st.header("How the score is built")
tiers = " ".join(ui.tier_badge(t.label) for t in TIERS)
steps = [
    ("1", "Indicators", f"{len(config.SCORED_INDICATORS)} measures, such as inflation, battle deaths and rule of law, "
                        "from the World Bank, IMF, UNHCR and UCDP."),
    ("2", "Risk scores", "Each indicator becomes a 0–100 risk score: where the country sits among all countries "
                         "that year (0 = safest, 100 = riskiest)."),
    ("3", "Pillars", "Indicators are averaged into four pillars: stability, governance, economy and social "
                     "pressure."),
    ("4", "Composite", "A weighted average of the pillars gives the headline score from 0 to 100, which sets the "
                       "country's tier."),
]
grid([f'<div style="{CARD}">'
      f'<div style="font-weight:700;margin:0 0 6px">{n}. {html.escape(title)}</div>'
      f'<div style="font-size:0.86rem;color:var(--sg-soft);line-height:1.5">{html.escape(text)}</div></div>'
      for n, title, text in steps])
st.markdown(f"**Tiers:** {tiers}", unsafe_allow_html=True)
st.markdown(
    "On top of the score: **red flags** mark absolute danger lines (such as inflation above 20% or an active war) "
    "that matter wherever a country ranks, and an **analyst assessment** can add judgment the data cannot capture. "
    "Scores are **relative**: 0 is the lowest risk in the sample and 100 the highest, so a low score means *safer "
    "than most countries*, and such a country can still be dangerous."
)

# --- The four pillars ---------------------------------------------------------------------------------------
st.header("The four pillars")
st.caption("The weights are the defaults; you can change them under *Index weights* in the sidebar.")
cards = []
for p in PILLARS:
    color = config.PILLAR_COLORS[p.key]
    share = weights[p.key] / total_weight
    inds = ", ".join(i.short for i in config.indicators_for(p.key))
    cards.append(
        f'<div style="{CARD}">'
        f'<div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px">'
        f'<span style="font-weight:700;color:{color}">{html.escape(p.label)}</span>'
        f'<span style="font-size:0.8rem;color:var(--sg-muted);white-space:nowrap">{share:.0%} of the score</span></div>'
        f'<div style="font-size:0.86rem;color:var(--sg-text);margin:6px 0;line-height:1.5">{html.escape(p.question)}</div>'
        f'<div style="font-size:0.75rem;color:var(--sg-faint);line-height:1.5">{html.escape(inds)}</div></div>'
    )
grid(cards, min_width=260)

# --- Quick start -------------------------------------------------------------------------------------------------
st.header("Quick start")
st.markdown(
    "1. Open the **Global overview** and click any country on the globe to see its score.\n"
    "2. Open its **Country profile** and read the *In real life* tab: what the numbers mean on the ground.\n"
    "3. Use the bar at the bottom of every page to jump between Home, Compare, Live and Guide; **Find** searches "
    "every country and every page. The country on the left of the bar is the last one you opened in this visit "
    "(on a new visit, the first country you follow).\n"
    "4. **☆ Follow** the countries you care about: they stay at the top of the Global overview, in this browser.\n"
    "5. Not sure what a term means? The **Glossary & legend** explains every one."
)
st.page_link("app_pages/overview.py", label="Go to the global overview", icon=":material/arrow_forward:")

# --- Before you use it -------------------------------------------------------------------------------------------
st.header("Before you rely on it")
st.markdown("\n".join(f"- {c}" for c in interpret.CAVEATS))
ui.cite("index", "oecd_jrc")
ui.footer()
