"""Sources: every dataset, definition and feed behind Seismographic, with links and update dates, and further reading."""

import datetime as dt
import html

import pandas as pd
import streamlit as st

from prm import config, ui
from prm.config import INDICATORS, RAW_SERIES, SOURCES

core, year, values, scores = ui.load()
meta = core["meta"]

ui.hero("Sources",
        "Every number, map, headline and video in Seismographic, traced back to the organisation that published it.")
st.markdown(
    "Seismographic does not collect data itself. Everything comes from international organisations, academic "
    "research centres and the broadcasters themselves, and every chart in the tool names its source underneath. "
    "This page lists them all, with links to the originals so you can check any figure."
)

references = [k for keys in config.SOURCE_GROUPS.values() for k in keys]
cross_checks = list(dict.fromkeys(k for keys in config.CROSS_CHECKS.values() for k in keys))
stats = [
    (len(config.INDEX_SOURCES), "datasets in the index"), (len(INDICATORS), "indicators"),
    (len(references), "definitions, methods & feeds"), (len(cross_checks), "independent cross-checks"),
    (len(config.NEWS_VIDEO_CHANNELS) + len(config.ANALYSIS_VIDEO_CHANNELS) + len(config.INSTITUTION_VIDEO_CHANNELS),
     "official video channels"),
]
st.markdown(
    '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:10px;margin:4px 0 8px">'
    + "".join(f'<div style="border:1px solid var(--sg-line);border-radius:10px;padding:10px 12px">'
              f'<div style="font-size:1.7rem;font-weight:700;line-height:1.1">{n}</div>'
              f'<div style="font-size:0.78rem;color:var(--sg-muted);margin-top:2px">{label}</div></div>' for n, label in stats)
    + "</div>",
    unsafe_allow_html=True,
)


def card(key: str, extra: str = "") -> str:
    s = SOURCES[key]
    details = " · ".join(x for x in (s.updates and f"Updates: {s.updates}", s.terms and f"Terms: {s.terms}") if x)
    return (
        f'<div style="background:var(--sg-raised);border:1px solid var(--sg-line);border-radius:10px;'
        'padding:12px 14px">'
        f'<div style="font-size:0.78rem;color:var(--sg-faint)">'
        f'{html.escape(s.publisher)}</div>'
        f'<div style="font-weight:700;margin:3px 0 6px;line-height:1.35">{ui.source_link(key, s.name)}</div>'
        f'<div style="font-size:0.86rem;color:var(--sg-soft);line-height:1.45">{html.escape(s.used_for)}</div>'
        + (f'<div style="font-size:0.74rem;color:var(--sg-faint);margin-top:8px">{html.escape(details)}</div>' if details else "")
        + extra + "</div>"
    )


def grid(cards: list[str], min_width: int = 270) -> None:
    st.markdown(f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax({min_width}px,1fr));'
                f'gap:10px;margin:4px 0 14px">{"".join(cards)}</div>', unsafe_allow_html=True)


def status(keys: list[str]) -> str:
    """Source update dates and live/snapshot status of the series loaded right now."""
    loaded = [meta[k] for k in keys if k in meta]
    if not loaded:
        return ""
    dates = sorted({str(m.get("edition") or m.get("last_updated")) for m in loaded
                    if m.get("edition") or m.get("last_updated")})
    live = sum(1 for m in loaded if not m["from_snapshot"] and not m["error"])
    state = "live" if live == len(loaded) else ("saved snapshot" if live == 0 else f"{live} of {len(loaded)} live")
    updated = f"source updated {', '.join(dates)}" if dates else "update date not published"
    return (f'<div style="font-size:0.74rem;color:#5fb98a;margin-top:6px">● In this copy: {html.escape(updated)} · '
            f'{state}</div>')


# --- Further reading ------------------------------------------------------------------------------------
READING = {
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


# --- One tab per kind of source ----------------------------------------------------------------------------
t_index, t_thresholds, t_cross, t_refs, t_reading, t_cite = st.tabs([
    ":material/dataset: Index data", ":material/flag: Thresholds", ":material/fact_check: Cross-checks",
    ":material/menu_book: References", ":material/library_books: Further reading", ":material/format_quote: Citing",
])

with t_index:
    # --- The index ----------------------------------------------------------------------------------------------
    st.header("The data behind the index")
    st.caption("The five datasets the 17 indicators come from. The risk scores are Seismographic's own calculation on "
               "top of them, explained on the Methodology page.")
    DERIVED = {"battle_deaths_100k": "battle_deaths", "displaced_share": "displaced"}
    index_cards = []
    for key in config.INDEX_SOURCES:
        inds = [i for i in INDICATORS if config.indicator_source(i) == key]
        links = " · ".join(f'<a href="{html.escape(config.indicator_url(i))}" target="_blank" rel="noopener">'
                           f'{html.escape(i.short)}</a>' for i in inds)
        extra = status([k for k in RAW_SERIES if not k.endswith(("_lb", "_ub")) and config.series_source(k) == key])
        if links:
            extra += f'<div style="font-size:0.78rem;margin-top:6px;line-height:1.6">Indicators: {links}</div>'
        index_cards.append(card(key, extra))
    grid(index_cards)

    st.subheader("Indicator by indicator")
    rows = []
    for ind in INDICATORS:
        series = ind.series or DERIVED.get(ind.key)
        m = meta.get(series, {})
        years = values[f"{ind.key}__year"].dropna() if f"{ind.key}__year" in values else pd.Series(dtype=float)
        if m.get("error") and not m.get("from_snapshot"):
            state = "Unavailable"
        elif m.get("from_snapshot"):
            state = "Snapshot"
        else:
            state = "Live"
        rows.append({
            "Pillar": config.PILLAR_BY_KEY[ind.pillar].short,
            "Indicator": ind.label,
            "Original source": ind.source,
            "Series code": RAW_SERIES[ind.series][1] if ind.series else f"derived from {series} and population",
            "Most common data year": None if years.empty else int(years.astype(int).mode().iloc[0]),
            "Source updated": m.get("edition") or m.get("last_updated") or "—",
            "Status": state,
            "Data": config.indicator_url(ind),
        })
    st.dataframe(
        pd.DataFrame(rows), hide_index=True,
        column_config={
            "Most common data year": st.column_config.NumberColumn(format="%d",
                                                                   help="The year most countries' latest value is from"),
            "Data": st.column_config.LinkColumn("Data", display_text="Open ↗", help="The publisher's page for this series"),
        },
    )
    st.caption("IMF figures for the current year are estimates and are revised twice a year. World Bank and UNHCR series "
               "run a year or two behind, so each indicator uses the latest year available for each country.")

    st.header("Status of the data loaded now")
    ui.data_status(core)


with t_thresholds:
    # --- Thresholds -------------------------------------------------------------------------------------------
    st.header("Where the warning thresholds come from")
    st.caption("Red flags are fixed lines, not relative scores. Some come straight from a definition or a well-known "
               "study; others are Seismographic's own lines, set out here so you can judge them.")
    flag_rows = []
    for key, op, threshold, severity, label in config.RED_FLAGS:
        source, basis = config.FLAG_BASIS.get((key, threshold), (None, "Seismographic line"))
        flag_rows.append({"Severity": f"{config.SEVERITY_ICON[severity]} {config.SEVERITY_LABEL[severity]}",
                          "Red flag": label, "Basis": basis,
                          "Reference": ui.source_label(source) if source else "—",
                          "Link": SOURCES[source].url if source else None})
    flag_rows.append({"Severity": f"{config.SEVERITY_ICON['warning']} {config.SEVERITY_LABEL['warning']}",
                      "Red flag": f"Political stability deteriorating (WGI down {config.WGI_TREND_THRESHOLD:g}+ points in "
                                  f"{config.WGI_TREND_YEARS} years)",
                      "Basis": "Seismographic line, chosen to be larger than most year-to-year noise in the WGI",
                      "Reference": ui.source_label("wgi_method"), "Link": SOURCES["wgi_method"].url})
    st.dataframe(pd.DataFrame(flag_rows), hide_index=True,
                 column_config={"Red flag": st.column_config.TextColumn(width="large"),
                                "Basis": st.column_config.TextColumn(width="large"),
                                "Link": st.column_config.LinkColumn("Link", display_text="Open ↗")})
    st.caption("The risk tiers (Low to Severe) are equal 20-point bands of the composite score, a Seismographic convention.")


with t_cross:
    # --- Cross-checks -----------------------------------------------------------------------------------------
    st.header("Cross-check the scores")
    st.caption("Respected independent indices measuring similar things. They are not used in the score; if Seismographic "
               "and they disagree about a country, find out why before you rely on either.")
    for pillar_key, keys in config.CROSS_CHECKS.items():
        if pillar_key == "composite":
            st.markdown("**Overall fragility**")
        else:
            st.markdown(ui.pillar_chip(pillar_key), unsafe_allow_html=True)
        grid([card(k) for k in keys], min_width=240)


with t_refs:
    # --- References -------------------------------------------------------------------------------------------
    st.header("Definitions, methods and other references")
    countries_state = "saved snapshot" if core.get("countries_from_snapshot") else "live"
    for group, keys in config.SOURCE_GROUPS.items():
        st.subheader(group)
        grid([card(k, f'<div style="font-size:0.74rem;color:#5fb98a;margin-top:6px">● In this copy: {countries_state}'
                      '</div>' if k == "wb_countries" else "") for k in keys])

    # --- Video channels -----------------------------------------------------------------------------------------
    st.header("Video channels")
    st.caption("Live TV and video reports come straight from each organisation's official YouTube channel. Ownership "
               "matters when you weigh what you watch: state-owned and state-funded channels can reflect their "
               "government's view.")
    ORGS = {  # think tanks, institutions and NGOs: (based in, type)
        "Council on Foreign Relations": ("United States", "Non-profit think tank"),
        "International Crisis Group": ("Belgium", "Non-profit think tank"),
        "Carnegie Endowment": ("United States", "Non-profit think tank"),
        "Brookings Institution": ("United States", "Non-profit think tank"),
        "Atlantic Council": ("United States", "Non-profit think tank"),
        "CSIS": ("United States", "Non-profit think tank"),
        "United Nations": ("International", "Intergovernmental organisation"),
        "IMF": ("International", "Intergovernmental organisation"),
        "World Bank": ("International", "Intergovernmental organisation"),
        "ICRC (Red Cross)": ("Switzerland", "Humanitarian organisation"),
        "Human Rights Watch": ("United States", "Non-profit NGO"),
    }
    channel_rows = [
        {"Channel": name, "Content": "24/7 live stream and news reports", "Region": c.region, "Based in": c.origin,
         "Ownership": c.funding, "YouTube": f"https://www.youtube.com/channel/{c.id}"}
        for name, c in config.LIVE_CHANNELS.items()
    ] + [
        {"Channel": name, "Content": "News reports", "Region": c.region, "Based in": c.origin, "Ownership": c.funding,
         "YouTube": f"https://www.youtube.com/channel/{c.id}"}
        for name, c in config.OTHER_NEWS_CHANNELS.items()
    ] + [
        {"Channel": name, "Content": "Analysis and explainers" if name in config.ANALYSIS_VIDEO_CHANNELS
         else "Institutional briefings", "Region": "—", "Based in": ORGS.get(name, ("—", "—"))[0],
         "Ownership": ORGS.get(name, ("—", "—"))[1], "YouTube": f"https://www.youtube.com/channel/{cid}"}
        for name, cid in {**config.ANALYSIS_VIDEO_CHANNELS, **config.INSTITUTION_VIDEO_CHANNELS}.items()
    ]
    st.dataframe(pd.DataFrame(channel_rows), hide_index=True, height=420,
                 column_config={"YouTube": st.column_config.LinkColumn("YouTube", display_text="Open ↗")})
    st.caption("Headlines in the news feeds link to the original publisher; Bing News and Google News only find them.")


with t_reading:
    st.caption("A reading and data list for political risk analysis: open data worth adding, the free outlooks "
               "professionals publish, and the methods that make analysis rigorous.")
    for section, items in READING.items():
        st.header(section)
        for title, url, note in items:
            heading = f"[{title}]({url})" if url else title
            st.markdown(f"**{heading}** — {note}")
    st.header("Ideas to extend this project")
    st.markdown("\n".join([
        "1. **Write quarterly assessments** for 5–10 countries in one region and track how your ratings compare with "
        "what happened.",
        "2. **Benchmark the index** against the Fragile States Index or OECD classification: where do they disagree, "
        "and why?",
        "3. **Add a conflict-events map** with a free UCDP access token or an ACLED account.",
        "4. **Back-test**: compute the index for earlier years and check whether high scores preceded coups, defaults "
        "or mass protest.",
        "5. **Add a sanctions pillar** from OpenSanctions or official lists for a compliance angle.",
    ]))

with t_cite:
    st.header("How to cite Seismographic")
    parts = config.AUTHOR.split()
    author = f"{parts[-1]}, {' '.join(p[0] + '.' for p in parts[:-1])}"
    edition = (meta.get("gdp_growth", {}).get("edition") or "World Economic Outlook").replace(" (", ", ").rstrip(")")
    st.code(
        f"{author} ({dt.date.today().year}). {config.APP_TITLE}: a country political risk index built from open data "
        f"[Web application]. Data from the World Bank (Worldwide Governance Indicators, World Development Indicators), "
        f"the IMF ({edition}), UNHCR and the Uppsala Conflict Data Program. Retrieved {dt.date.today():%d %B %Y}.",
        language=None, wrap_lines=True,
    )
    st.caption("When you quote a figure, cite the original source too: it is named under every chart and in the "
               "*Index data* tab.")
ui.footer()
