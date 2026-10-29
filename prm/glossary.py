"""Glossary: every term, abbreviation and symbol used in Seismographic, in plain language.

The 17 indicators are added from config.INDICATORS, so the glossary always matches the model.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import config

# Category -> [(term, definition)]
TERMS: dict[str, list[tuple[str, str]]] = {
    "Scores & ratings": [
        ("Composite score", "The headline risk score, from 0 to 100: a weighted average of the four pillar scores. "
                            "0 = the lowest risk in the sample, 100 = the highest."),
        ("Risk score (0–100)", "Any indicator or pillar put on a common 0–100 scale, where 100 = the riskiest economy "
                               "in the sample that year."),
        ("Relative scoring", "Scores compare countries with each other in the same year. They are not probabilities, "
                             "and a low score means 'safer than most', not 'safe'."),
        ("Percentile rank", "How most indicators become risk scores: a country's position among all countries, from "
                            "safest (0) to riskiest (100)."),
        ("Log scale", "Used for battle deaths and displacement, which are zero for most countries: 'none' scores 0 and "
                      "the score rises steeply from the first deaths or displacements, then flattens."),
        ("Global rank", "A country's position among all scored economies; 1 = the highest risk."),
        ("Tier", "Five bands of the composite score: Low (0–20), Moderate (20–40), Elevated (40–60), High (60–80) and "
                 "Severe (80–100)."),
        ("Pillar", "One of four groups of indicators: Political Stability & Violence, Governance & Institutions, "
                   "Macroeconomic & Financial, and Social & Humanitarian Pressure."),
        ("Indicator", "A single measured data series, such as inflation or rule of law. The index uses 17."),
        ("Weights", "How much each pillar counts in the composite. Defaults: Stability 35%, Governance 25%, Economy "
                    "25%, Social 15%; you can change them in the sidebar."),
        ("Data coverage", "The share of the 17 indicators available for a country. Below 75%, treat its score with "
                          "extra caution."),
        ("Regional median", "The middle score among countries in the same region — a benchmark for comparison."),
        ("Peer group", "The countries a profile is compared with: the same region, the same income group, or all."),
        ("1-yr change (▲ ▼ ■)", "The composite now minus last year's: ▲ riskier by a point or more, ▼ safer by a "
                                "point or more, ■ steady."),
        ("Risk over time", "The index recomputed for every year since 2015, each time with only the data available "
                           "for that year."),
        ("Main driver", "The pillar that moved most in the same direction as the composite since last year."),
        ("Sensitivity check", "Recomputes a country's score with equal weights, or with one pillar left out, to show "
                              "how much the result depends on modelling choices."),
        ("What-if simulator", "Change a country's indicators — or pick a scenario such as a currency crisis — and see "
                              "how its score, tier and rank would move."),
        ("Track record", "A test of the index: of the countries at peace in a year, did those where armed conflict "
                         "broke out the next year already score high? Shown on the Methodology page."),
        ("AUC (accuracy)", "The chance that a country where conflict broke out had scored higher than one where it "
                           "did not: 0.5 is a coin flip, 1 is perfect."),
        ("Benchmark", "A comparison with an independent index measuring something similar, here the Fragile States "
                      "Index, to see where the two agree and where they differ."),
        ("Case-study verdict", "Flagged, Partly flagged or Missed: what the index said the year before a major event, "
                               "decided by a fixed rule (tier, rank and change over three years)."),
        ("PDF brief", "A one-page summary of a country (score, pillars, trend, red flags and what it means in real "
                      "life) to download from its profile."),
        ("Hotspots to watch", "Countries scoring 50+ that got 2+ points riskier, "
                              "crossed a new red flag, or face a high-significance event within 120 days."),
        ("Conflict outlook", "The estimated chance that armed conflict (25+ battle deaths) starts next year in a "
                             "country at peace, from a small statistical model on the pillars, low-level violence and "
                             "recent conflict. On the Conflict page and each country's Summary."),
        ("Out-of-time test", "Checking a model the honest way: each year is predicted by a model fitted only on "
                             "earlier years, then compared with what happened."),
        ("Brier skill", "How much better the predicted chances are than always guessing the average rate: 0 = no "
                        "better, above 0 = better."),
        ("Calibration", "Whether predicted chances match what happened: of the cases given about 10%, about one in "
                        "ten should see conflict."),
        ("× average", "A country's predicted chance divided by the average chance for countries at peace."),
        ("Stress test", "Apply one economic shock (say, growth −4 points) to many countries at once and see who "
                        "crosses a tier or a red flag. Countries hit are scored against today's values, so a shock "
                        "that hits everyone still shows."),
        ("Similar risk profiles", "The countries whose four pillar scores are closest to a country's, wherever they "
                                  "are in the world."),
        ("Follow (★)", "Mark countries to keep them on the Global overview and in Find. The list stays in your "
                       "browser; no account needed."),
        ("Share link", "The address of the Compare and Stress test pages holds your selection, so you can send it."),
        ("Open data", "Every table behind the index, free to download as CSV, Excel or JSON on the Download data "
                      "page, with a data dictionary."),
    ],
    "Warnings": [
        ("Red flag", "An absolute warning threshold, such as inflation of 20% or more. Unlike the relative score, it "
                     "matters wherever the country ranks."),
        ("Critical / Serious / Watch", "Red-flag severities: 🔴 Critical (e.g. war, inflation ≥ 50%), 🟠 Serious "
                                       "(e.g. active conflict, inflation ≥ 20%), 🟡 Watch (e.g. debt ≥ 90% of GDP)."),
        ("Close to a red line", "An indicator within reach of a threshold — for example inflation between 15% and "
                                "20% — shown on the In real life tab."),
        ("Political stability deteriorating", "A Watch flag raised when the WGI political-stability score falls by "
                                              f"{config.WGI_TREND_THRESHOLD:g}+ points over "
                                              f"{config.WGI_TREND_YEARS} years."),
    ],
    "Analyst assessments": [
        ("Model tier vs analyst rating", "The model tier comes from the data; the analyst rating is a human "
                                         "judgment that can differ, with the reason written down."),
        ("Outlook", "The expected direction over the horizon: Improving, Stable or Deteriorating."),
        ("Confidence", "How solid the evidence behind an assessment is: Low, Moderate or High."),
        ("Horizon", "The period an assessment looks ahead: 6, 12 or 24 months."),
        ("BLUF", "Bottom line up front: the two or three sentences a busy reader needs first."),
        ("Key judgment", "A specific, checkable statement about the future, with a probability attached."),
        ("Estimative language (ICD 203)", "Standard words for probabilities from the US Intelligence Community, so "
                                          "words and numbers agree: 'unlikely' = 20–45%, 'likely' = 55–80%, "
                                          "'very likely' = 80–95%, and so on."),
        ("Scenario", "A coherent story of how events could unfold: a base case, an upside and a downside, with "
                     "probabilities adding to 100%."),
        ("Signpost", "An observable event that would show a scenario is coming true."),
        ("Driver", "A political, security, economic or social force that pushes risk up or down."),
    ],
    "Conflict & displacement": [
        ("Battle-related deaths", "Deaths in fighting between organised armed groups where at least one side is a "
                                  "government (UCDP 'state-based conflict'), counted where they happen."),
        ("Active armed conflict", "25 or more battle-related deaths in a year (the UCDP threshold)."),
        ("War", "1,000 or more battle-related deaths in a year (the UCDP threshold)."),
        ("Forcibly displaced", "People forced from their homes by conflict, violence or persecution: refugees, asylum "
                               "seekers, others in need of international protection and internally displaced people."),
        ("Refugee", "A person who has fled across an international border and is recognised as needing protection."),
        ("Asylum seeker", "A person who has applied for protection in another country and is waiting for a decision."),
        ("IDP (internally displaced person)", "Someone forced from home who is still inside their own country."),
        ("Others in need of international protection", "People outside their country who need protection but have "
                                                       "not applied for asylum (a UNHCR category since 2022)."),
        ("Refugee flow / corridor", "The number of people from one origin country living in one host country."),
        ("Host country", "A country where refugees and asylum seekers from elsewhere live."),
        ("Homicide rate", "Intentional killings per 100,000 people a year — a measure of criminal violence."),
        ("Protest coverage", "The share of world news coverage that mentions a country together with protests, riots, "
                             "strikes or unrest (GDELT): a fast signal of unrest getting attention."),
    ],
    "Economy": [
        ("Inflation", "How fast consumer prices rise over a year. High inflation erodes wages, savings and "
                      "fixed-price contracts."),
        ("Real GDP growth", "How much the economy grows in a year after removing inflation; negative = a shrinking "
                            "economy."),
        ("Public debt", "General government gross debt as a share of GDP. High debt leaves little room to respond to "
                        "shocks."),
        ("Fiscal balance", "Government revenue minus spending, as a share of GDP; negative = a budget deficit."),
        ("Current account", "Trade, income and transfers with the rest of the world; a large deficit means relying on "
                            "foreign money."),
        ("FX reserves (months of imports)", "The central bank's foreign currency, expressed as how many months of "
                                            "imports it could pay for. Under 3 months is a common warning line."),
        ("Unemployment / youth unemployment", "The share of the labour force (or of 15–24-year-olds) who want work "
                                              "but have none."),
        ("IMF projection", "The IMF's forecast for coming years in the World Economic Outlook; shown as dashed lines."),
        ("Stagflation", "Prices rising fast while the economy stagnates or shrinks."),
        ("Devaluation", "A sharp, often sudden fall in the value of a currency."),
        ("Capital controls", "Government limits on moving money in or out of a country."),
        ("IMF programme", "A loan from the IMF tied to policy conditions such as budget cuts or reforms."),
    ],
    "Governance (WGI)": [
        ("Voice & Accountability", "Citizens' ability to choose their government; freedom of expression, "
                                   "association and the media."),
        ("Political Stability & Absence of Violence", "Perceived likelihood of political instability and "
                                                      "politically motivated violence, including terrorism."),
        ("Government Effectiveness", "Quality of public services, the civil service and policy delivery."),
        ("Regulatory Quality", "Ability to make and apply sound policies that let the private sector develop."),
        ("Rule of Law", "Confidence in contracts, property rights, the police and the courts."),
        ("Control of Corruption", "How far public power is used for private gain, including state capture."),
        ("WGI score", "World Bank governance scores on a 0–100 scale (2025 methodology); higher = better governance."),
        ("90% confidence interval", "The range the true WGI score very probably lies in. If two years' ranges "
                                    "overlap, the change may be noise rather than real."),
        ("Statistically clear", "A change in a WGI score larger than its margin of error (the intervals don't "
                                "overlap)."),
    ],
    "Sources & abbreviations": [
        ("WGI", "Worldwide Governance Indicators (World Bank)."),
        ("WDI", "World Development Indicators (World Bank)."),
        ("IMF WEO", "International Monetary Fund World Economic Outlook — growth, inflation, debt and balance-of-"
                    "payments estimates and projections."),
        ("UNHCR", "The UN Refugee Agency — displacement and refugee statistics."),
        ("UCDP", "Uppsala Conflict Data Program — the academic standard for armed-conflict data."),
        ("GDELT", "Global Database of Events, Language and Tone — global news monitoring; used as a backup news "
                  "source and for media tone."),
        ("IFES ElectionGuide", "Calendar of national elections and referendums; the source of the watchlist dates."),
        ("OCHA", "UN Office for the Coordination of Humanitarian Affairs."),
        ("ISO3", "Three-letter country codes, e.g. NGA for Nigeria."),
        ("GDP", "Gross domestic product: the value of everything an economy produces in a year."),
        ("Natural Earth", "Public-domain map data; the source of the country outlines on the globe."),
        ("Snapshot", "A saved copy of all the data (refreshed monthly) so pages open instantly and keep working if "
                     "a source is down."),
        ("Live data", "Figures downloaded from the sources in the background; kept for 12 hours."),
    ],
    "Maps, globe & charts": [
        ("Risk colours", "Dim to bright = lower to higher risk. Countries in dim dark grey are outside your filters; "
                         "lighter grey means not enough data."),
        ("Pillar colours", "Stability = blue, Governance = orange, Economy = green, Social = amber — on maps, bars and "
                           "tables."),
        ("Map of change", "Blue = safer than last year, grey = little change, red = riskier; brighter and taller = "
                          "a bigger move."),
        ("3D (height)", "On the globe, countries are raised by their score: the taller, the riskier."),
        ("Conflict rings", "Pulsing rings mark active armed conflict; bigger and faster = more battle deaths."),
        ("Flows (arcs)", "Animated arcs run from refugees' country of origin (dim end) to the host country (bright "
                         "end); thicker = more people."),
        ("Year slider / ▶", "Replays the index on the globe year by year since 2015."),
        ("Spin / Reset / + −", "Turn auto-rotation on or off, return to the starting view, zoom in and out."),
        ("Bubble size", "In the risk matrix and growth-vs-inflation chart, bubbles are sized by population."),
        ("Dashed line", "An IMF projection rather than reported data."),
        ("Shaded band", "A 90% confidence interval (governance charts) or the middle half of countries (IMF outlook)."),
    ],
}


INDICATORS_CATEGORY = "The 17 indicators"


@dataclass(frozen=True)
class Category:
    icon: str
    color: str
    blurb: str
    sources: tuple[str, ...]  # config.SOURCES keys that back the whole category


CATEGORIES: dict[str, Category] = {
    "Scores & ratings": Category("", "#a68cf2", "How the index turns data into scores, ranks and tiers.",
                                 ("oecd_jrc", "wb_groups")),
    INDICATORS_CATEGORY: Category("", "#c3c2b7", "Every data series in the score, grouped by pillar, with a link to "
                                                   "the data itself.", tuple(config.INDEX_SOURCES)),
    "Warnings": Category("", "#f0575c", "Absolute red lines that matter wherever a country ranks.",
                         ("ucdp_def", "rr_inflation", "rr_debt", "freund", "imf_ara")),
    "Analyst assessments": Category("", "#2fb7a5", "The vocabulary of professional risk and intelligence writing.",
                                    ("icd203", "cia_tradecraft", "heuer")),
    "Conflict & displacement": Category("", config.PILLAR_COLORS["stability"], "Armed conflict, violence and people "
                                        "forced from their homes.", ("ucdp_def", "unhcr_def", "unodc")),
    "Economy": Category("", config.PILLAR_COLORS["economic"], "Growth, prices, debt and the external buffers.",
                        ("imf", "imf_weo", "imf_ara")),
    "Governance (WGI)": Category("", config.PILLAR_COLORS["governance"], "The six World Bank governance dimensions "
                                 "and how to read them.", ("wgi", "wgi_docs", "wgi_method")),
    "Sources & abbreviations": Category("", "#d55181", "Who publishes the data, and the short names used for them.",
                                        ()),
    "Maps, globe & charts": Category("", "#5ec8e0", "How to read the colours, heights, arcs and rings.",
                                     ("natural_earth", "globe_gl", "unhcr")),
}

# Term -> the config.SOURCES key that defines or publishes it
TERM_SOURCES: dict[str, str] = {
    "Conflict outlook": "ucdp_def", "Out-of-time test": "ucdp_def", "Stress test": "imf_weo",
    "Composite score": "oecd_jrc", "Percentile rank": "oecd_jrc", "Log scale": "oecd_jrc", "Weights": "oecd_jrc",
    "Sensitivity check": "oecd_jrc", "Regional median": "wb_groups", "Peer group": "wb_groups",
    "Political stability deteriorating": "wgi_method", "Track record": "ucdp_def", "Benchmark": "fsi",
    "Case-study verdict": "wikipedia", "Protest coverage": "gdelt",
    "Confidence": "icd203", "Key judgment": "icd203", "Estimative language (ICD 203)": "icd203",
    "Scenario": "cia_tradecraft", "Signpost": "cia_tradecraft", "Driver": "cia_tradecraft",
    "Battle-related deaths": "ucdp_def", "Active armed conflict": "ucdp_def", "War": "ucdp_def",
    "Forcibly displaced": "unhcr_def", "Refugee": "refugee_convention", "Asylum seeker": "unhcr_asylum",
    "IDP (internally displaced person)": "unhcr_idp", "Others in need of international protection": "unhcr_def",
    "Refugee flow / corridor": "unhcr", "Host country": "unhcr", "Homicide rate": "unodc",
    "Inflation": "imf_inflation", "Real GDP growth": "imf_gdp", "Public debt": "imf_fm", "Fiscal balance": "imf_fm",
    "Current account": "imf", "FX reserves (months of imports)": "imf_ara",
    "Unemployment / youth unemployment": "ilo_unemployment", "IMF projection": "imf_weo",
    "IMF programme": "imf_lending",
    **{label: "wgi_docs" for label in config.WGI_DIMENSIONS.values()},
    "WGI score": "wgi_method", "90% confidence interval": "wgi_method", "Statistically clear": "wgi_method",
    "WGI": "wgi", "WDI": "wdi", "IMF WEO": "imf", "UNHCR": "unhcr", "UCDP": "ucdp", "GDELT": "gdelt",
    "IFES ElectionGuide": "ifes", "OCHA": "ocha", "ISO3": "iso3166", "GDP": "imf_gdp", "Natural Earth": "natural_earth",
    "Conflict rings": "ucdp", "Flows (arcs)": "unhcr", "Dashed line": "imf_weo",
}


@dataclass(frozen=True)
class Term:
    term: str
    definition: str
    source: str | None = None  # config.SOURCES key
    url: str | None = None  # a more specific link than the source's home page
    tags: tuple[str, ...] = ()
    pillar: str | None = None

    @property
    def text(self) -> str:
        """Everything searchable about the term."""
        return " ".join((self.term, self.definition, *self.tags))


def indicator_terms() -> list[Term]:
    """The 17 indicators, straight from the model's configuration, in pillar order."""
    out = []
    for ind in config.INDICATORS:
        direction = "higher = riskier" if ind.higher_is_riskier else "lower = riskier"
        scale = "log scale" if ind.norm == "log" else "percentile rank"
        out.append(Term(ind.label, ind.description, config.indicator_source(ind), config.indicator_url(ind),
                        (ind.unit, direction, scale, ind.source), ind.pillar))
    return out


def all_terms() -> dict[str, list[Term]]:
    """Every category, with the indicators placed right after "Scores & ratings"."""
    first, *rest = TERMS.items()
    groups = [first, (INDICATORS_CATEGORY, None), *rest]
    return {cat: indicator_terms() if items is None else [Term(t, d, TERM_SOURCES.get(t)) for t, d in items]
            for cat, items in groups}
