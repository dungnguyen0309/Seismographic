"""Methodology: how the index is built, how it is tested, and its limits."""

import pandas as pd
import streamlit as st

from prm import charts, config, data, hotspots, ui
from prm.config import INDICATORS, PILLARS, RED_FLAGS, SEVERITY_LABEL, TIERS

ui.hero("Methodology")
st.markdown(
    "Seismographic follows the [OECD/JRC *Handbook on Constructing Composite Indicators*]"
    "(https://www.oecd.org/en/publications/handbook-on-constructing-composite-indicators-methodology-and-user-guide_9789264043466-en.html)."
)
# the page's top level: its tab labels take the h2 size (prm/ui.py), so they never read smaller than the sections inside
st.html('<style>.st-key-method_tabs [role="tab"] { height: 3rem; }'
        '.st-key-method_tabs [role="tab"], .st-key-method_tabs [role="tab"] p {'
        ' font-size: clamp(1.12rem, 2.2vw, 1.32rem) !important; font-weight: 600; letter-spacing: -0.01em; }</style>')
built, tests, limits = st.tabs(["How it is built", "Tests", "Limits"], key="method_tabs")

with built:
    st.header("The question")
    st.markdown(
        "> *How exposed is this country to political, governance, economic and social shocks that could harm people, "
        "organisations and investments operating there, compared with other countries?*\n\n"
        "Four pillars break that question down:"
    )
    # a list, not a table: on a phone a three-column table wrapped the questions word by word
    st.markdown("\n".join(f"* **{p.label}**, {p.default_weight}% of the weight: {p.question}" for p in PILLARS))
    st.caption(
        "Political stability weighs most as the core of political risk; social pressure least, as its indicators are "
        "the noisiest. Change the weights in the sidebar."
    )

    st.header("The indicators")
    ind_rows = [
        {
            "Indicator": i.label,
            "Pillar": config.PILLAR_BY_KEY[i.pillar].short,
            "Unit": i.unit,
            "Riskier when": "higher" if i.higher_is_riskier else "lower",
            "Source": i.source,
            "Why it is here": i.description,
        }
        for i in INDICATORS
    ]
    st.dataframe(pd.DataFrame(ind_rows), hide_index=True, height=640,
                 # large: on a phone the grid unpins it (pins over 60% of the width), so every column stays reachable
                 column_config={"Indicator": st.column_config.TextColumn(pinned=True, width="large"),
                                "Why it is here": st.column_config.TextColumn(width="large")})
    st.markdown(
        """
WGI scores come from the latest annual release (perceptions collected the year before). IMF figures are the
current-year estimate from the latest World Economic Outlook, which makes the economic pillar the most
forward-looking part of the index. World Bank figures use the most recent year within a look-back window (shown
in each profile's *Data* tab). Battle deaths use the latest UCDP year; displacement the latest UNHCR annual
statistics. The app downloads every dataset live through its public API.
"""
    )
    ui.cite("index", "wgi_method", "oecd_jrc")

    st.header("Normalisation")
    st.markdown(
        f"""
Indicators come in different units (percent, deaths, months), so each becomes a 0–100 risk score.

Most use a percentile rank: the riskiest country in the sample scores 100, the safest 0, the rest evenly in
between. Percentiles resist outliers, so one country with 200% inflation does not squash everyone else, but they
drop the size of the gaps between countries.

Battle deaths per 100k and the displacement share use a log scale. Most countries have no conflict deaths, so a
percentile rank would bunch them together in the middle. The score is `log(1 + x)` divided by the value at the
{config.LOG_CAP_QUANTILE:.0%} percentile of non-zero cases, capped at 100. Zero means zero, and scores rise
steeply from the first deaths, then flatten.

Where lower is riskier (growth, reserves, governance scores) the ranking is reversed, so 100 always means the
most risk.
"""
    )

    st.header("Aggregation and weights")
    st.markdown(
        f"""
A pillar score is the simple average of its indicator scores. A pillar needs at least
{config.PILLAR_MIN_SHARE:.0%} of its indicators; with fewer, it stays blank and nothing is guessed.

The composite score is the weighted average of the pillar scores, with the weights rescaled over the pillars a
country has. A country needs at least {config.COMPOSITE_MIN_PILLARS} of the 4 pillars to be ranked. Data coverage,
shown on every profile, is the share of the {len(config.SCORED_INDICATORS)} indicators available.

An arithmetic mean lets a strength in one pillar offset a weakness in another, which suits a broad screening
tool. A crisis-risk model might use a geometric mean, which penalises one very weak pillar more, as the EU's
INFORM Risk Index does.
"""
    )

    st.header("Tiers")
    bounds = [t.lower for t in TIERS] + [100]  # a tier runs from its lower bound up to, not including, the next
    st.table(
        pd.DataFrame([{"Tier": t.label, "Composite score": f"{lo:g} to {'under ' if hi < 100 else ''}{hi:g}"}
                      for t, lo, hi in zip(TIERS, bounds, bounds[1:])]),
        hide_index=True, border="horizontal", width="content",
    )
    st.caption(
        "Averaging many indicators pulls composites toward the middle, so the outer tiers hold only countries at the "
        "extremes on most dimensions at once. 'Low' is low relative to other countries; it does not mean risk-free."
    )

    st.header("Red flags")
    st.markdown(
        "The composite is relative, so it cannot say whether a situation is bad in absolute terms. Red flags use fixed "
        "thresholds from common practice, for example UCDP's 25 battle deaths for an active armed conflict and 1,000 "
        "for war, and the 3-months-of-imports rule of thumb for reserves."
    )
    st.dataframe(
        pd.DataFrame(
            [{"Flag": label, "Severity": SEVERITY_LABEL[sev], "Indicator": key, "Rule": f"{op} {thr:g}",
              "Basis": config.FLAG_BASIS.get((key, thr), (None, "Seismographic line"))[1],
              "Reference": config.SOURCES[src].url if (src := config.FLAG_BASIS.get((key, thr), (None, ""))[0]) else None}
             for key, op, thr, sev, label in RED_FLAGS]
            + [{"Flag": "Political stability deteriorating", "Severity": "Watch", "Indicator": "wgi_pv",
                "Rule": f"falls ≥ {config.WGI_TREND_THRESHOLD:g} points in {config.WGI_TREND_YEARS} years",
                "Basis": "Seismographic line, larger than most year-to-year noise in the WGI",
                "Reference": config.SOURCES["wgi_method"].url}]
        ),
        hide_index=True,
        column_config={"Flag": st.column_config.TextColumn(pinned=True, width=560),  # full labels; unpinned on a phone
                       "Basis": st.column_config.TextColumn(width="large"),
                       "Reference": st.column_config.LinkColumn(display_text="Open ↗")},
    )
    ui.cite("ucdp_def", "rr_inflation", "rr_debt", "freund", "imf_ara")
    st.page_link(ui.SOURCES_PAGE, label="Every source and threshold reference", icon=":material/verified:")

    st.header("Escalation signal")
    st.markdown(
        f"""
The Hotspots page reads recent change from two sources refreshed every day. UCDP's candidate events count organised
violence with at least one death, published about six weeks after each month ends. GDELT counts the English-language
articles about each country that mention attacks, clashes, airstrikes, shelling, killings or coups, and divides them
by all the articles GDELT monitored that day, so a busy news day does not look like an escalation.

* The signal compares the average share of the last {hotspots.RECENT_DAYS} days with the median share of the
  {hotspots.WINDOW_DAYS - hotspots.RECENT_DAYS} days before them. A day GDELT returns no figure for counts as zero.
* Escalating: the recent share is at least {hotspots.ESCALATING_RATIO:g} times the usual level and at least
  {hotspots.ESCALATING_Z:g} robust standard deviations above it ({hotspots.MAD_SCALE} × the median absolute
  deviation, and never less than one article a day). A country with no conflict news on most days only has to
  pass the second test.
* Easing: {hotspots.EASING_RATIO:g} times the usual level or less.
* Quiet: fewer than {hotspots.MIN_ARTICLES_7D} articles in the last week, too few to read a change.
* Steady: everything else.

News volume is not a count of events. Coverage also rises with a summit, an anniversary or a famous victim, and
English-language media cover some countries far more than others, so a country reported mostly in other languages
can look quieter than it is. Treat Escalating as a reason to read the news and check UCDP's events.
"""
    )
    ui.cite("ucdp_ged", "gdelt")

    st.header("Reproducibility")
    st.markdown(
        "Everything needed to recompute the scores is on this page, and all the data come from the public sources "
        "linked above."
    )

with tests:
    st.header("Robustness")
    st.markdown(
        "Each country profile has a sensitivity check that recomputes the rank with equal weights and with each "
        "pillar dropped in turn. If the rank swings widely, the result depends on a modelling choice, and any report "
        "on it should say so. WGI changes are tested against the WGI 90% confidence intervals, to show whether a "
        "change is statistically clear or within the margin of error."
    )

    st.header("Track record")
    st.markdown(
        f"For every year since {config.HISTORY_START}, take the countries not in armed conflict and see where "
        "conflict broke out the next year (25 or more battle deaths, the UCDP threshold). If the index works, those "
        "countries should already have scored high."
    )
    tr_core, tr_year, _tr_values, _tr_scores = ui.load()
    names = dict(zip(tr_core["countries"]["iso3"], tr_core["countries"]["name"]))
    basis = st.segmented_control("Score tested", ["Stability pillar", "Composite score"], default="Stability pillar",
                                 key="track_basis") or "Stability pillar"
    track = data.get_track_record(tr_core, ui.weights_tuple(), tr_core["version"],
                                  "stability" if basis == "Stability pillar" else "composite")
    if not track:
        st.info("Not enough conflict data to run the test right now.")
    else:
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("New conflicts tested", track["onsets"],
                  help=f"Out of {track['cases']:,} country-years at peace, {track['years'][0]}–{track['years'][1]}.")
        t2.metric("In riskiest fifth", f"{track['top_fifth_share']:.0%}",
                  help="Share of new conflicts in countries that scored in the riskiest fifth the year before.")
        t3.metric("In riskiest two fifths", f"{track['top_two_fifths_share']:.0%}")
        t4.metric("AUC", "—" if track["auc"] is None else f"{track['auc']:.2f}",
                  help="The chance that a country where conflict started had scored higher than one where it did "
                       "not. 0.5 = a coin flip, 1 = perfect.")
        st.plotly_chart(charts.onset_fifths(track["by_fifth"], track["base_rate"], config.PILLAR_COLORS["stability"]),
                        config={"displayModeBar": False})
        with st.expander(f"The {track['onsets']} new conflicts"):
            onsets = track["onset_list"].assign(
                country=lambda d: d["iso3"].map(names), started=lambda d: d["year"] + 1,
                fifth=lambda d: d["fifth"].map(lambda f: charts.FIFTHS[int(f) - 1]))
            st.dataframe(onsets[["country", "started", "score", "fifth"]].round({"score": 0}), hide_index=True,
                         column_config={"country": st.column_config.TextColumn("Country", pinned=True, width=230),
                                        "started": st.column_config.NumberColumn("Conflict began", format="%d"),
                                        "score": st.column_config.NumberColumn("Score the year before", format="%.0f"),
                                        "fifth": "Where it ranked"})
        st.caption(
            "Read with care: the scores are rebuilt from data as published today, including later revisions; "
            "governance scores for a year are only published the following year; and a few dozen cases is a small "
            "sample. The test shows the index ranks countries sensibly. It does not show it can predict a single "
            "event."
        )
        ui.cite("ucdp", "ucdp_def", "wgi")
        st.page_link("app_pages/conflict.py", label="Conflict outlook, tested on unseen years",
                     icon=":material/insights:", query_params={"tab": "outlook"})

    st.header("Benchmark: the Fragile States Index")
    st.markdown(
        "The [Fragile States Index](https://fragilestatesindex.org/) from The Fund for Peace is an independent index "
        "of something similar, rating states on 12 indicators with expert review. Broad agreement is reassuring; "
        "the countries where they disagree show what each index picks up and the other misses."
    )
    with ui.guard("The benchmark"):
        fsi, _ = data.load_fsi()
        if fsi is None or fsi.empty:
            st.info("The Fragile States Index can't be downloaded from its publisher right now. The app retries in a "
                    "few minutes.")
        else:
            fsi_year = int(fsi["year"].mode().iloc[0])
            tr_hist = ui.history(tr_core)
            ours = tr_hist[tr_hist["year"] == fsi_year][["iso3", "composite", "tier"]].dropna(subset=["composite"])
            both = fsi.merge(ours, on="iso3").rename(columns={"total": "fsi", "composite": "score"})
            both["name"] = both["iso3"].map(names)
            both["fsi_pct"] = both["fsi"].rank(pct=True) * 100
            both["our_pct"] = both["score"].rank(pct=True) * 100
            both["gap"] = both["our_pct"] - both["fsi_pct"]
            top_fsi, top_ours = set(both.nlargest(20, "fsi")["iso3"]), set(both.nlargest(20, "score")["iso3"])
            b1, b2, b3 = st.columns(3)
            b1.metric("Countries compared", len(both))
            b2.metric("Rank correlation", f"{both['fsi'].rank().corr(both['score'].rank()):.2f}",
                      help="Spearman correlation of the two rankings: 1 = identical order, 0 = unrelated.")
            b3.metric("Riskiest 20 in both", f"{len(top_fsi & top_ours)} of 20",
                      help="Countries in the riskiest 20 of both rankings.")
            st.plotly_chart(charts.benchmark_scatter(both, fsi_year), config={"displayModeBar": False})
            cols = {"name": ui.NAME_COLUMN,
                    "fsi": st.column_config.NumberColumn("FSI", format="%.1f"),
                    "score": st.column_config.NumberColumn("Seismographic", format="%.0f"),
                    "gap": st.column_config.NumberColumn("Gap", format="%+.0f",
                                                         help="Difference in position between the two rankings, "
                                                              "percentile points")}
            decimals = {"fsi": 1, "score": 0, "gap": 0}  # as displayed
            g1, g2 = st.columns(2)
            with g1:
                st.markdown("**Riskier in Seismographic**")
                st.dataframe(both.nlargest(8, "gap")[list(cols)].round(decimals), hide_index=True, column_config=cols)
            with g2:
                st.markdown("**Riskier in the Fragile States Index**")
                st.dataframe(both.nsmallest(8, "gap")[list(cols)].round(decimals), hide_index=True, column_config=cols)
            st.caption(
                f"Both for {fsi_year}. The Fragile States Index also weighs group grievance, demographic pressure and "
                "outside intervention, which Seismographic does not measure; Seismographic gives more weight to economic and financial stress. "
                "The FSI data is downloaded from its publisher when the page opens and is not stored in this project."
            )
            ui.cite("fsi")

with limits:
    st.header("Limitations")
    st.markdown(
        """
* The data look backwards. Governance data describe last year, and conflict and displacement data lag by up to
  two years. A coup last month will not show in the score; the news pulse, the Hotspots page and the analyst
  assessment are there for that.
* Governance data are perceptions. The WGI aggregate expert and survey perceptions, with real margins of error.
  Their authors publish the six dimensions separately; this index deliberately combines them into one pillar.
* Scores are relative. Percentiles show a country's position and drop the distance between countries, so a global
  shock that worsens every country can leave the ranking unchanged.
* Data are thinnest where risk is highest. Small states and countries in conflict often have the least data, so
  check the coverage figure before drawing conclusions.
* The weights are a judgment. Indicators count equally within a pillar and the pillar weights are a choice. Other
  choices are defensible, and the sensitivity check on each profile shows how much they change the result.
* It is not a forecast. The index describes structural conditions; the probability of a specific event takes the
  analyst work the assessments are for.
"""
    )

    st.header("How professional models compare")
    st.markdown(
        """
* ICRG (PRS Group) is one of the longest-running commercial country-risk ratings. It scores political, financial
  and economic risk separately and then combines them, with political risk carrying the most points.
* The INFORM Risk Index (European Commission JRC) is an open humanitarian-risk model built from hazard and
  exposure, vulnerability and lack of coping capacity, aggregated with geometric means. Its documentation sets a
  high bar for openness: [methodology](https://drmkc.jrc.ec.europa.eu/inform-index/INFORM-Risk/Methodology).
* The OECD Country Risk Classification is the export-credit agencies' 0–7 rating of the risk that a country cannot
  meet its external debt payments. It combines a quantitative model with expert judgment:
  [current list](https://www.oecd.org/en/topics/country-risk-classification).
* Commercial intelligence firms (Control Risks, Eurasia Group, Verisk Maplecroft, EIU and others) combine data
  models with networks of country analysts, the same split between model and judgment that this project uses.
"""
    )
ui.footer()
