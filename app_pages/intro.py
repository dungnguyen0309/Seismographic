"""Introduction: what Seismographic is, how the score is built, and how to find your way around the tool."""

import html

import streamlit as st

from prm import config, interpret, ui
from prm.config import PILLARS, TIERS

core, year, values, scores = ui.load()
n_scored = int(scores["composite"].notna().sum())
weights = ui.weights()
total_weight = sum(weights.values()) or 1

CARD = "background:#0f1012;border:1px solid #2c2c2a;border-radius:10px;padding:14px 16px"


def grid(cards: list[str], min_width: int = 220) -> None:
    st.markdown(f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax({min_width}px,1fr));'
                f'gap:10px;margin:6px 0 14px">{"".join(cards)}</div>', unsafe_allow_html=True)


ui.hero("Introduction", "What Seismographic is, how it works, and how to get the most out of it.")

# --- What it is ------------------------------------------------------------------------------------------
st.header("What it is")
st.markdown(
    f"**{config.APP_TITLE}** is a transparent, open-data index of **political, governance, economic and social "
    f"risk** for {n_scored} economies. It is built the way professional country-risk models are: indicators are "
    "grouped into pillars, and the pillars are combined into one weighted score, with absolute red flags and room "
    "for an analyst's judgment on top. Every figure comes from a public source you can check, and every step of the "
    "method is written down."
)
stats = [
    (n_scored, "economies scored"), (len(config.SCORED_INDICATORS), "indicators"), (len(PILLARS), "pillars"),
    (len(config.INDEX_SOURCES), "open datasets"), (year - config.HISTORY_START + 1, f"years of history ({config.HISTORY_START}–{year})"),
]
grid([f'<div style="{CARD}"><div style="font-size:1.8rem;font-weight:700;line-height:1.1">{n}</div>'
      f'<div style="font-size:0.8rem;color:#a3a29a;margin-top:2px">{html.escape(label)}</div></div>'
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
grid([f'<div style="{CARD};border-top:3px solid #fd8078">'
      f'<div style="font-size:0.72rem;color:#fd8078;letter-spacing:0.08em">STEP {n}</div>'
      f'<div style="font-weight:700;margin:2px 0 6px">{html.escape(title)}</div>'
      f'<div style="font-size:0.86rem;color:#c3c2b7;line-height:1.5">{html.escape(text)}</div></div>'
      for n, title, text in steps])
st.markdown(f"**Tiers:** {tiers}", unsafe_allow_html=True)
st.markdown(
    "On top of the score: **red flags** mark absolute danger lines (such as inflation above 20% or an active war) "
    "that matter wherever a country ranks, and an **analyst assessment** can add the judgment no dataset captures. "
    "Scores are **relative**: 0 is the lowest risk in the sample and 100 the highest, so a low score means *safer "
    "than most*, not *safe*."
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
        f'<div style="{CARD};border-left:4px solid {color}">'
        f'<div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px">'
        f'<span style="font-weight:700;color:{color}">{html.escape(p.label)}</span>'
        f'<span style="font-size:0.8rem;color:#a3a29a;white-space:nowrap">{share:.0%} of the score</span></div>'
        f'<div style="font-size:0.86rem;color:#d6d5cc;margin:6px 0;line-height:1.5">{html.escape(p.question)}</div>'
        f'<div style="font-size:0.75rem;color:#898781;line-height:1.5">{html.escape(inds)}</div></div>'
    )
grid(cards, min_width=260)

# --- Find your way around --------------------------------------------------------------------------------------
st.header("Find your way around")
SECTIONS = {
    "Monitor": [
        ("app_pages/overview.py", "Global overview", ":material/public:",
         "The 3D globe, headline numbers, hotspots to watch and the full ranking."),
        ("app_pages/country.py", "Country profile", ":material/flag:",
         "One country in depth: score, drivers, what-if simulator, news and video. ★ Follow it to keep it close."),
        ("app_pages/compare.py", "Compare countries", ":material/compare_arrows:", "Up to six countries side by side, with a link you can share."),
        ("app_pages/watchlist.py", "Events watchlist", ":material/event:",
         "Elections and other dated events that could move risk."),
        ("app_pages/video.py", "Live TV & video", ":material/live_tv:",
         "Live international news channels and the latest video analysis."),
    ],
    "Briefings": [
        ("app_pages/guide.py", "How to analyze Seismographic data?", ":material/lightbulb:",
         "What the numbers mean on the ground, and what to do about them."),
        ("app_pages/cases.py", "Did it see it coming?", ":material/history:",
         "Eight shocks since 2020 and what the index said the year before."),
        ("app_pages/changes.py", "What changed", ":material/trending_up:",
         "This year against last: risers, fallers and new red flags."),
        ("app_pages/regions.py", "Regional briefings", ":material/travel_explore:", "One region at a time."),
        ("app_pages/conflict.py", "Conflict & displacement", ":material/crisis_alert:",
         "Wars, refugees and where they go, and the chance of new conflict next year."),
        ("app_pages/economy.py", "Economic stress", ":material/monitoring:",
         "Inflation, growth, debt and the countries under pressure."),
        ("app_pages/explorer.py", "Indicator explorer", ":material/explore:", "Any single indicator on the globe."),
    ],
    "Analyst desk & reference": [
        ("app_pages/builder.py", "Assessment builder", ":material/edit_note:",
         "Write a structured risk assessment and download it."),
        ("app_pages/stress.py", "Stress test", ":material/bolt:",
         "Hit many countries with one economic shock and see who crosses a line."),
        ("app_pages/methodology.py", "Methodology", ":material/functions:",
         "Every formula and weight, the track record and a benchmark against another index."),
        ("app_pages/glossary.py", "Glossary & legend", ":material/help:", "Every term, colour and symbol explained."),
        ("app_pages/sources.py", "Sources & citations", ":material/verified:",
         "Where every number comes from, with links."),
        ("app_pages/downloads.py", "Download data", ":material/download:",
         "Every table behind the index as CSV, Excel or JSON."),
    ],
}
for section, pages in SECTIONS.items():
    st.subheader(section)
    for start in range(0, len(pages), 3):  # row by row, so the cards in a row line up
        for col, (path, title, icon, blurb) in zip(st.columns(3), pages[start:start + 3]):
            with col.container(border=True, height="stretch"):
                st.page_link(path, label=title, icon=icon)
                st.caption(blurb)

# --- Quick start -------------------------------------------------------------------------------------------------
st.header("Quick start")
st.markdown(
    "1. Open the **Global overview** and click any country on the globe to see its score.\n"
    "2. Open its **Country profile** and read the *In real life* tab: what the numbers mean on the ground.\n"
    "3. Use the bar at the bottom of every page to jump between Home, Compare, Live and Guide; **Find** searches "
    "any country. The country on the left of the bar is the last one you opened.\n"
    "4. **☆ Follow** the countries you care about: they stay at the top of the Global overview, in this browser.\n"
    "5. Not sure what a term means? The **Glossary & legend** explains every one."
)
st.page_link("app_pages/overview.py", label="Go to the global overview", icon=":material/arrow_forward:")

# --- Before you use it -------------------------------------------------------------------------------------------
st.header("Before you rely on it")
st.markdown("\n".join(f"- {c}" for c in interpret.CAVEATS))
ui.cite("index", "oecd_jrc")
ui.footer()
