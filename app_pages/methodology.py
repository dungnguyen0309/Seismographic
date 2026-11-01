"""Methodology: how the index is built, and its limits."""

import pandas as pd
import streamlit as st

from prm import charts, config, data, ui
from prm.config import INDICATORS, PILLARS, RED_FLAGS, SEVERITY_LABEL, TIERS

ui.hero("Methodology")
st.markdown(
    """
Seismographic follows the standard recipe for composite indicators set out in the
[OECD/JRC *Handbook on Constructing Composite Indicators*](https://www.oecd.org/en/publications/handbook-on-constructing-composite-indicators-methodology-and-user-guide_9789264043466-en.html):
choose indicators that answer a clear question, normalise them to a common scale, aggregate them into
pillars and a composite with explicit weights, and test how sensitive the result is to those choices.
Every step is shown below, so you can disagree with a specific choice.
"""
)

st.header("1 · The question")
st.markdown(
    "> *How exposed is this country to political, governance, economic and social shocks that could harm people, "
    "organisations and investments operating there, compared with other countries?*\n\n"
    "Four pillars break that question down:"
)
st.table(  # a static table: long text wraps instead of being cut off
    pd.DataFrame(
        [{"Pillar": p.label, "Question it answers": p.question, "Default weight": f"{p.default_weight}%"} for p in PILLARS]
    ),
    hide_index=True, border="horizontal",
)
st.caption(
    "Political stability carries the most weight because it is the core of political risk; social pressure the least "
    "because its indicators are the noisiest. You can change the weights in the sidebar and watch rankings move."
)

st.header("2 · The indicators")
ind_rows = [
    {
        "Pillar": config.PILLAR_BY_KEY[i.pillar].short,
        "Indicator": i.label,
        "Unit": i.unit,
        "Riskier when": "higher" if i.higher_is_riskier else "lower",
        "Scaling": "log scale" if i.norm == "log" else "percentile rank",
        "Source": i.source,
        "Why it is here": i.description,
    }
    for i in INDICATORS
]
st.dataframe(pd.DataFrame(ind_rows), hide_index=True, height=640)
ui.cite("index", "oecd_jrc")
st.markdown(
    f"""
WGI scores come from the latest annual release (perception data collected during the previous year).
IMF figures are the current-year estimate from the latest World Economic Outlook, which makes the economic
pillar the most forward-looking part of the index. World Bank figures use the most recent year available within
a look-back window (shown in the *Indicators* tab of each profile). Battle deaths use the latest UCDP year;
displacement uses the latest UNHCR annual statistics.

Sources: [World Bank WGI]({config.URL_WGI}) (2025 methodology revision:
[technical note]({config.URL_WGI_2025})) · [World Development Indicators]({config.URL_WDI}) ·
[IMF World Economic Outlook]({config.URL_IMF_WEO}) · [UNHCR Refugee Data Finder]({config.URL_UNHCR}) ·
[Uppsala Conflict Data Program]({config.URL_UCDP}) · news from the [GDELT Project]({config.URL_GDELT}).
The app downloads all of them live through their public APIs.
"""
)

st.header("3 · Normalisation")
st.markdown(
    f"""
Indicators come in different units (percent, deaths, months), so each becomes a 0–100 risk score.

Most indicators use a percentile rank. The riskiest country in the sample scores 100, the safest 0, and the
rest are spread evenly between them. Percentiles resist outliers: one country with 200% inflation does not
squash everyone else. They do drop the size of the gaps between countries.

Battle deaths per 100k and the displacement share use a log scale. Most countries have no conflict deaths, so a
percentile rank would bunch them together in the middle. The score is `log(1 + x)` divided by the value at the
{config.LOG_CAP_QUANTILE:.0%} percentile of non-zero cases, capped at 100. Zero means zero, and scores rise
steeply from the first deaths, then flatten.

Direction is set at this step too. For indicators where lower is riskier (growth, reserves, governance scores)
the ranking is reversed, so 100 always means the most risk.
"""
)

st.header("4 · Aggregation and weights")
st.markdown(
    f"""
A pillar score is the simple average of its indicator scores. A pillar needs at least
{config.PILLAR_MIN_SHARE:.0%} of its indicators; with fewer, it stays blank and nothing is guessed.

The composite score is the weighted average of the pillar scores, with the weights rescaled over the pillars a
country has. A country needs at least {config.COMPOSITE_MIN_PILLARS} of the 4 pillars to be ranked. Data coverage,
shown on every profile, is the share of the {len(config.SCORED_INDICATORS)} indicators available.

An arithmetic mean lets a strength in one pillar offset a weakness in another. That suits a broad screening
tool. A system built around crisis risk might use a geometric mean, which penalises one very weak pillar more;
the EU's INFORM Risk Index does this.
"""
)

st.header("5 · Tiers")
st.table(
    pd.DataFrame([{"Tier": t.label, "Composite score": f"{int(t.lower)}–{int(t.lower) + 20 if t.lower < 80 else 100}"} for t in TIERS]),
    hide_index=True, border="horizontal", width="content",
)
st.caption(
    "Averaging many indicator scores pulls composites toward the middle of the scale, so the outer tiers are "
    "reserved for countries that sit at the extremes on most dimensions at once. 'Low' means low relative to "
    "other countries; it does not mean risk-free."
)

st.header("6 · Red flags")
st.markdown(
    "The composite is relative, so it cannot say whether a situation is bad in absolute terms. Red flags fill that gap "
    "with fixed thresholds drawn from common practice, for example UCDP's 25 battle-death threshold for an active armed "
    "conflict and 1,000 for war, and the 3-months-of-imports rule of thumb for reserve adequacy."
)
st.dataframe(
    pd.DataFrame(
        [{"Severity": SEVERITY_LABEL[sev], "Flag": label, "Indicator": key, "Rule": f"{op} {thr:g}",
          "Basis": config.FLAG_BASIS.get((key, thr), (None, "Seismographic line"))[1],
          "Reference": config.SOURCES[src].url if (src := config.FLAG_BASIS.get((key, thr), (None, ""))[0]) else None}
         for key, op, thr, sev, label in RED_FLAGS]
        + [{"Severity": "Watch", "Flag": "Political stability deteriorating", "Indicator": "wgi_pv",
            "Rule": f"falls ≥ {config.WGI_TREND_THRESHOLD:g} points in {config.WGI_TREND_YEARS} years",
            "Basis": "Seismographic line, larger than most year-to-year noise in the WGI",
            "Reference": config.SOURCES["wgi_method"].url}]
    ),
    hide_index=True,
    column_config={"Basis": st.column_config.TextColumn(width="large"),
                   "Reference": st.column_config.LinkColumn(display_text="Open ↗")},
)
ui.cite("ucdp_def", "rr_inflation", "rr_debt", "freund", "imf_ara")
st.page_link(ui.SOURCES_PAGE, label="Every source and threshold reference", icon=":material/verified:")

st.header("7 · Robustness")
st.markdown(
    "Every country profile has a sensitivity check that recomputes the rank with equal weights and with each "
    "pillar dropped in turn. If a country's rank swings widely, the result depends on a modelling choice, and any "
    "report on it should say so. WGI changes are tested against the WGI 90% confidence intervals, so the app can say "
    "whether a change is statistically clear or within the margin of error."
)

st.header("8 · Track record")
st.markdown(
    "This test checks whether a high score means anything. For every year since "
    f"{config.HISTORY_START}, take the countries that were not in armed conflict and see where conflict broke out the next "
    "year (25 or more battle deaths, the UCDP threshold). If the index works, those countries should already have "
    "scored high."
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
    t1.metric("New conflicts tested", track["onsets"], border=True, height="stretch",
              help=f"Out of {track['cases']:,} country-years at peace, {track['years'][0]}–{track['years'][1]}.")
    t2.metric("Already in the riskiest fifth", f"{track['top_fifth_share']:.0%}", border=True, height="stretch",
              help="Share of new conflicts in countries that scored in the riskiest fifth the year before.")
    t3.metric("In the riskiest two fifths", f"{track['top_two_fifths_share']:.0%}", border=True, height="stretch")
    t4.metric("Accuracy (AUC)", "—" if track["auc"] is None else f"{track['auc']:.2f}", border=True, height="stretch",
              help="The chance that a country where conflict started had scored higher than one where it did not. "
                   "0.5 = a coin flip, 1 = perfect.")
    st.plotly_chart(charts.onset_fifths(track["by_fifth"], track["base_rate"], config.PILLAR_COLORS["stability"]),
                    config={"displayModeBar": False})
    with st.expander(f"The {track['onsets']} new conflicts"):
        onsets = track["onset_list"].assign(
            country=lambda d: d["iso3"].map(names), started=lambda d: d["year"] + 1,
            fifth=lambda d: d["fifth"].map(lambda f: charts.FIFTHS[int(f) - 1]))
        st.dataframe(onsets[["country", "started", "score", "fifth"]], hide_index=True,
                     column_config={"country": "Country", "started": st.column_config.NumberColumn("Conflict began", format="%d"),
                                    "score": st.column_config.NumberColumn("Score the year before", format="%.0f"),
                                    "fifth": "Where it ranked"})
    st.caption(
        "Read with care: the scores are rebuilt with data as published today, which includes later revisions; "
        "governance scores for a year are only published the following year; and a few dozen cases is a small sample. "
        "The test shows that the index ranks countries sensibly; it does not show that it can predict a single event."
    )
    ui.cite("ucdp", "ucdp_def", "wgi")
    st.page_link("app_pages/conflict.py", label="Conflict outlook: the forecast model, tested on unseen years",
                 icon=":material/insights:", query_params={"tab": "outlook"})

st.header("9 · Benchmark: the Fragile States Index")
st.markdown(
    "A second check compares the scores with an independent index that measures something similar. The "
    "[Fragile States Index](https://fragilestatesindex.org/) from The Fund for Peace rates states on 12 indicators "
    "using expert review. Where the two broadly agree, that is reassuring. The countries where they disagree show "
    "what each index picks up and the other misses."
)
with ui.guard("The benchmark"):
    fsi, _ = data.load_fsi()
    if fsi is None or fsi.empty:
        st.info("The Fragile States Index can't be downloaded from its publisher right now, so the benchmark is "
                "hidden. The app retries in a few minutes.")
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
        b1.metric("Countries compared", len(both), border=True, height="stretch")
        b2.metric("Rank correlation", f"{both['fsi'].rank().corr(both['score'].rank()):.2f}", border=True,
                  height="stretch",
                  help="Spearman correlation of the two rankings: 1 = identical order, 0 = unrelated.")
        b3.metric("Same countries in the riskiest 20", f"{len(top_fsi & top_ours)} of 20", border=True,
                  height="stretch")
        st.plotly_chart(charts.benchmark_scatter(both, fsi_year), config={"displayModeBar": False})
        cols = {"name": "Country", "fsi": st.column_config.NumberColumn("FSI", format="%.1f"),
                "score": st.column_config.NumberColumn("Seismographic", format="%.0f"),
                "gap": st.column_config.NumberColumn("Gap", format="%+.0f",
                                                     help="Difference in position between the two rankings, percentile points")}
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("**Riskier in Seismographic**")
            st.dataframe(both.nlargest(8, "gap")[list(cols)], hide_index=True, column_config=cols)
        with g2:
            st.markdown("**Riskier in the Fragile States Index**")
            st.dataframe(both.nsmallest(8, "gap")[list(cols)], hide_index=True, column_config=cols)
        st.caption(
            f"Both for {fsi_year}; the gap compares each country's position in the two rankings. The Fragile States Index "
            "also weighs group grievance, demographic pressure and outside intervention, which Seismographic does not "
            "measure; Seismographic gives more weight to economic and financial stress. The FSI data is downloaded from "
            "its publisher when the page opens and is not stored in this project."
        )
        ui.cite("fsi")

st.header("10 · Limitations")
st.markdown(
    """
* The data look backwards. Governance data describe last year, and conflict and displacement data lag by up to
  a year. A coup last month will not show in the score; the news pulse, the events watchlist and the analyst
  assessment are there for that.
* Governance data are perceptions. The WGI aggregate expert and survey perceptions, with real margins of error.
  Their authors publish the six dimensions separately and do not combine them. This index combines them into one
  pillar on purpose, and says so here.
* Scores are relative. Percentiles show a country's position and drop the distance between countries, so a global
  shock that worsens every country can leave the ranking unchanged.
* Data are thinnest where risk is highest. Small states and countries in conflict often have the least data, so
  check the coverage figure before drawing conclusions.
* The weights are a judgment. Indicators count equally within a pillar and the pillar weights are a choice. Other
  choices are defensible, and the sensitivity check on each profile shows how much they change the result.
* It is not a forecast. The index describes structural conditions. Turning it into the probability of a specific
  event takes the analyst work the assessments are for.
"""
)

st.header("11 · How professional models compare")
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

st.header("12 · Reproducibility")
st.markdown(
    "Every indicator, source, normalisation, weight and threshold is set out on this page, and all the data come "
    "from the public sources linked above, so anyone can recompute the scores."
)
ui.footer()
