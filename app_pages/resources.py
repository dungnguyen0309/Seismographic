"""Curated resources for political risk analysis."""

import streamlit as st

from prm import ui

ui.hero("📚 Resources", kicker="About")
st.markdown(
    "A curated reading and data list for political risk analysis — the sources behind Seismographic, the free "
    "outlooks professionals publish, and the methods that make analysis rigorous."
)

SECTIONS = {
    "Open data used or worth adding": [
        ("Worldwide Governance Indicators (World Bank)", "https://www.worldbank.org/en/publication/worldwide-governance-indicators",
         "Six governance dimensions for about 200 economies since 1996, revised in 2025 onto a 0–100 scale. Used in this app."),
        ("World Development Indicators (World Bank)", "https://datatopics.worldbank.org/world-development-indicators/",
         "1,400+ development series with a free API. Source of conflict, homicide, reserves and labour data here."),
        ("IMF World Economic Outlook — DataMapper", "https://www.imf.org/external/datamapper",
         "Growth, inflation, debt and balance-of-payments estimates with five-year projections. Used in this app."),
        ("UNHCR Refugee Data Finder", "https://www.unhcr.org/refugee-statistics/",
         "Refugees, asylum seekers and IDPs by origin and destination, with a free API. Used in this app."),
        ("Uppsala Conflict Data Program (UCDP)", "https://ucdp.uu.se/",
         "The academic standard for armed-conflict data. Its API requires a free access token — a good upgrade for event-level maps."),
        ("ACLED", "https://acleddata.com/",
         "Near-real-time data on political violence and protest events. Requires registration; check its terms before publishing derived data."),
        ("GDELT Project", "https://www.gdeltproject.org/",
         "Global news monitoring with a free API. The backup news source and media-tone chart here."),
        ("V-Dem", "https://v-dem.net/",
         "The most detailed dataset on democracy and regime characteristics, free for download."),
        ("Fragile States Index (Fund for Peace)", "https://fragilestatesindex.org/",
         "Annual fragility index across 12 indicators — a useful benchmark to validate your scores against."),
        ("Bertelsmann Transformation Index", "https://bti-project.org/",
         "Expert country reports on political and economic transformation in 137 countries."),
        ("Quality of Government Data Finder", "https://datafinder.qog.gu.se/",
         "Searchable catalogue of hundreds of governance datasets with variable-level documentation."),
        ("OpenSanctions", "https://www.opensanctions.org/",
         "Consolidated sanctions lists and politically exposed persons. Free for non-commercial use."),
        ("IFES ElectionGuide", "https://www.electionguide.org/elections/type/upcoming/",
         "Calendar of upcoming national elections and referendums — feed for the watchlist."),
    ],
    "Free outlooks from professional risk firms and institutions": [
        ("Eurasia Group — Top Risks", "https://www.eurasiagroup.net/issues/top-risks-2026",
         "The best-known annual list of geopolitical risks. Read it every January."),
        ("Control Risks — RiskMap", "https://www.controlrisks.com/riskmap/maps",
         "Annual forecast and interactive map of political, security and operational risk."),
        ("World Economic Forum — Global Risks Report", "https://www.weforum.org/publications/global-risks-report-2026/",
         "Annual survey of experts on the most severe global risks over short and long horizons."),
        ("Crisis Group — CrisisWatch", "https://www.crisisgroup.org/crisiswatch",
         "Monthly tracker of conflicts worldwide, flagging deteriorations, improvements and risk alerts. Ideal for the watchlist."),
        ("OECD Country Risk Classification", "https://www.oecd.org/en/topics/country-risk-classification",
         "Export-credit risk categories (0–7), updated several times a year. A benchmark for the economic pillar."),
        ("Allianz Trade — Country Risk Atlas", "https://www.allianz-trade.com/en_global/news-insights/news/allianz-trade-country-risk-atlas-2026.html",
         "Country risk ratings combining political, economic and business-environment factors."),
        ("Coface — Country risk map", "https://coface.com/news-economy-and-insights/business-risk-dashboard/country-risk-map",
         "Credit-insurer country assessments, updated quarterly."),
        ("INFORM Risk Index (EU JRC)", "https://drmkc.jrc.ec.europa.eu/inform-index",
         "Open humanitarian-risk model; its methodology documentation is a template for transparency."),
    ],
    "Methods and analytic tradecraft": [
        ("OECD/JRC Handbook on Constructing Composite Indicators", "https://www.oecd.org/en/publications/handbook-on-constructing-composite-indicators-methodology-and-user-guide_9789264043466-en.html",
         "The reference text on normalisation, weighting, aggregation and sensitivity analysis."),
        ("WGI 2025 Methodology Revision", "https://www.worldbank.org/content/dam/sites/govindicators/doc/The%20Worldwide%20Governance%20Indicators%202025%20Methodology%20Revision.pdf",
         "How the governance scores and their confidence intervals are produced."),
        ("ICD 203: Analytic Standards (ODNI)", "https://www.dni.gov/files/documents/ICD/ICD-203.pdf",
         "The US intelligence community's standards, including the estimative-language scale used in the assessment builder."),
        ("Psychology of Intelligence Analysis — Richards Heuer (CIA, free)", "https://www.cia.gov/resources/csi/static/Pyschology-of-Intelligence-Analysis.pdf",
         "Cognitive biases in analysis and the origin of Analysis of Competing Hypotheses."),
    ],
    "Books": [
        ("Political Risk — Condoleezza Rice & Amy Zegart (2018)", None,
         "How organisations identify, assess and mitigate political risk; accessible and case-driven."),
        ("The Fat Tail — Ian Bremmer & Preston Keat (2009)", None,
         "The founder of Eurasia Group on why political risk is under-priced and how to analyse it."),
        ("Superforecasting — Philip Tetlock & Dan Gardner (2015)", None,
         "What makes forecasts accurate; the basis for putting probabilities on your key judgments."),
        ("Structured Analytic Techniques for Intelligence Analysis — Heuer & Pherson", None,
         "The toolkit: key assumptions check, ACH, indicators, scenarios, red-teaming."),
    ],
    "Practise and build a track record": [
        ("Good Judgment Open", "https://www.gjopen.com/",
         "Free forecasting tournaments on geopolitical questions. A Brier score is a credible line on a CV."),
        ("Metaculus", "https://www.metaculus.com/",
         "Forecasting platform with many geopolitics questions and public track records."),
    ],
}

for section, items in SECTIONS.items():
    st.header(section)
    for title, url, note in items:
        heading = f"[{title}]({url})" if url else title
        st.markdown(f"**{heading}** — {note}")

st.header("Ideas to extend this project")
st.markdown(
    """
1. **Write quarterly assessments** for 5–10 countries in one region and track how your ratings compare with what happened.
2. **Benchmark the index** against the Fragile States Index or OECD classification: where do they disagree, and why?
3. **Add a conflict-events map** with a free UCDP access token or an ACLED account.
4. **Back-test**: compute the index for earlier years and check whether high scores preceded coups, defaults or mass protest.
5. **Add a sanctions pillar** from OpenSanctions or official lists for a compliance angle.
"""
)
ui.footer()
