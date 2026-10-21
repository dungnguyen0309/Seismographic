"""How to analyze Seismographic data: what Seismographic's numbers mean in real life, and how to put them to work."""

import pandas as pd
import streamlit as st

from prm import config, content, interpret, ui

core, year, values, scores = ui.load()
hist = ui.history(core)
table = ui.master_table(core, values, scores, hist)
countries = core["countries"]
options, names = ui.country_options(countries)
events = content.load_events()

ui.hero("🧭 How to analyze Seismographic data?", kicker="Briefings")
st.markdown(
    "Seismographic turns open data into numbers: a 0–100 score, a tier, four pillars and a set of red flags. This "
    "page translates those numbers into real life — what they usually look like for the people living, working or "
    "travelling there — and into practical steps for businesses, NGOs, travellers and researchers."
)

# --- 1. Any country, in plain language ------------------------------------------------------------
st.header("1 · Read any country in plain language")
iso3 = st.selectbox("Country", options, index=options.index(ui.current_country(countries)),
                    format_func=lambda i: names.get(i, i), key="guide_country")
reading = interpret.country_reading(iso3, table, values, scores, hist, events, core.get("flows"), year)
ui.render_reading(reading, key="guide")
ui.cite("index", "ifes", "ucdp_def", "imf_ara")
st.page_link(ui.COUNTRY_PAGE, label=f"Open the full {names[iso3]} profile", icon=":material/flag:")

# --- 2. Tiers ---------------------------------------------------------------------------------------------
st.header("2 · What the scores mean on the ground")
st.caption("Scores are relative: a tier says how a country compares with the rest of the world this year.")
rows = []
for tier, upper in zip(config.TIERS, [t.lower for t in config.TIERS[1:]] + [100]):
    in_tier = table[table["tier"] == tier.label].sort_values("composite", ascending=False)
    summary, ground = interpret.TIER_MEANING[tier.label]
    rows.append({
        "Tier": tier.label,
        "Score": f"{int(tier.lower)}–{int(upper)}",
        "What it usually looks like": f"{summary} {ground}",
        "Countries now": len(in_tier),
        "For example": ", ".join(in_tier["name"].head(3)),
    })
st.table(pd.DataFrame(rows), hide_index=True, border="horizontal")  # static: long text wraps
ui.cite("index")

# --- 3. Pillars ------------------------------------------------------------------------------------------
st.header("3 · The four pillars in daily life")
cols = st.columns(2)
for i, p in enumerate(config.PILLARS):
    meaning = interpret.PILLAR_MEANING[p.key]
    with cols[i % 2], st.container(border=True):
        st.markdown(ui.pillar_chip(p.key), unsafe_allow_html=True)
        st.markdown(f"**A high score looks like:** {meaning['ground']}")
        st.markdown(f"**Felt first by:** {meaning['felt_by']}")
        st.caption("Measured with: " + ", ".join(i.short for i in config.indicators_for(p.key)) + ".")

# --- 4. Red flags ---------------------------------------------------------------------------------------
st.header("4 · Warning thresholds, translated")
st.caption("Unlike the relative score, these are absolute lines: crossing one matters wherever the country ranks.")
ops = {">=": lambda a, b: a >= b, "<": lambda a, b: a < b, "<=": lambda a, b: a <= b}
flag_rows = []
for key, op, threshold, severity, label in config.RED_FLAGS:
    if key not in interpret.FLAG_MEANING or key not in values:
        continue
    crossing = int(ops[op](pd.to_numeric(values[key], errors="coerce"), threshold).sum())
    meaning, response = interpret.FLAG_MEANING[key]
    flag_rows.append({
        "Severity": f"{config.SEVERITY_ICON[severity]} {config.SEVERITY_LABEL[severity]}",
        "Threshold": label,
        "What it means in real life": meaning,
        "What people typically do": response,
        "Countries now": crossing,
    })
st.table(pd.DataFrame(flag_rows), hide_index=True, border="horizontal")
ui.cite("ucdp_def", "imf_ara", "imf", "wdi", "unhcr")

# --- 5. Workflows ---------------------------------------------------------------------------------------
st.header("5 · Putting it to work, step by step")
workflows = {
    "🏢 Screening a market (business & investors)": [
        ("Shortlist", "Rank candidate countries on the Global overview; set the pillar weights in the sidebar to "
                      "match your exposure (e.g. more weight on Economy for trade, Governance for long-term assets).",
         "app_pages/overview.py"),
        ("Check the trend", "Look for countries getting riskier on *What changed* — a mid-tier country sliding fast "
                            "can be a bigger worry than a stable high-tier one.", "app_pages/changes.py"),
        ("Understand the drivers", "Open each profile's *In real life* tab, then *Peers* to compare with neighbours.",
         ui.COUNTRY_PAGE),
        ("Stress-test", "Use the What-if simulator to see how a currency crisis or conflict would change the picture.",
         ui.COUNTRY_PAGE),
        ("Time it", "Check the Events watchlist for elections or deadlines before committing.", "app_pages/watchlist.py"),
    ],
    "🤝 Planning a programme (NGOs & humanitarian)": [
        ("Find the need", "Conflict & displacement shows where people are being killed and displaced, and where "
                          "refugees are hosted.", "app_pages/conflict.py"),
        ("Read the context", "The *In real life* tab spells out access, safety and price pressures.", ui.COUNTRY_PAGE),
        ("Watch the economy", "Economic stress flags inflation and currency problems that erode cash assistance.",
         "app_pages/economy.py"),
        ("Track events", "Add elections and deadlines to the watchlist; plan field movements around them.",
         "app_pages/watchlist.py"),
    ],
    "🧳 Preparing a trip, posting or study abroad": [
        ("Get the picture", "Read the country's *In real life* tab and its latest news.", ui.COUNTRY_PAGE),
        ("Check official advice", "Always confirm with your government's current travel advice — it moves faster "
                                  "than this data.", None),
        ("Mind the calendar", "Avoid travelling around high-significance events in the watchlist.",
         "app_pages/watchlist.py"),
    ],
    "🔎 Writing an analysis (policy, journalism, research)": [
        ("Start from the drivers", "The profile's Summary and Indicators tabs show exactly what pushes the score.",
         ui.COUNTRY_PAGE),
        ("Separate signal from noise", "Governance trends show whether a change is outside the margin of error.",
         ui.COUNTRY_PAGE),
        ("Compare", "Regional briefings and Compare put a country in its neighbourhood.", "app_pages/regions.py"),
        ("Write it up", "The Assessment builder turns your judgment into a structured brief with probabilities.",
         "app_pages/builder.py"),
    ],
}
for title, steps in workflows.items():
    with st.expander(title):
        for n, (step, text, page) in enumerate(steps, start=1):
            st.markdown(f"**{n}. {step}.** {text}")
            if page:
                st.page_link(page, label="Go there", icon=":material/arrow_forward:")

# --- 6. Limits --------------------------------------------------------------------------------------------
st.header("6 · When not to rely on it")
st.markdown(
    """
* **Fast-moving events.** Annual data cannot see last week's coup or last night's protest — read the news pulse,
  official advice and local sources.
* **Relative, not absolute.** A *Low* score means "safer than most", not "safe"; a global shock can leave rankings
  unchanged while every country gets worse. The red flags cover the absolute side.
* **National averages.** A country score hides regions: a conflict in one province may not touch the capital, and
  the reverse.
* **Missing data.** Countries with little data are often the riskiest — check the coverage figure on each profile.
* **Not advice.** This guide describes what such conditions usually mean and how people commonly respond. It is
  general and educational, not investment, legal or security advice.
"""
)
ui.footer()
