"""Central configuration: data series, indicators, pillars, tiers and display names.

Everything the app scores is defined here, so the methodology page, the scoring
engine and the charts all read from one source of truth. To add an indicator,
add its raw series to RAW_SERIES and an entry to INDICATORS.
"""

from __future__ import annotations

from dataclasses import dataclass, field

APP_TITLE = "Seismographic"
APP_TAGLINE = "Picking up political tremors before they become earthquakes."
APP_DESCRIPTION = (
    "A transparent country risk index built from open data — "
    "with an analyst's judgment on top."
)
AUTHOR = "Tuan Dung Nguyen"  # shown in the footer and on assessments

# ---------------------------------------------------------------------------
# Source links (used on the Methodology and Resources pages)
# ---------------------------------------------------------------------------
URL_WGI = "https://www.worldbank.org/en/publication/worldwide-governance-indicators"
URL_WGI_2025 = (
    "https://www.worldbank.org/content/dam/sites/govindicators/doc/"
    "The%20Worldwide%20Governance%20Indicators%202025%20Methodology%20Revision.pdf"
)
URL_WDI = "https://datatopics.worldbank.org/world-development-indicators/"
URL_WB_API = "https://datahelpdesk.worldbank.org/knowledgebase/articles/889392"
URL_IMF_WEO = "https://www.imf.org/external/datamapper"
URL_UNHCR = "https://www.unhcr.org/refugee-statistics/"
URL_UNHCR_API = "https://api.unhcr.org/docs/refugee-statistics.html"
URL_UCDP = "https://ucdp.uu.se/"
URL_GDELT = "https://www.gdeltproject.org/"
# Latest edition offered as a download on fragilestatesindex.org/excel (benchmark only, fetched when needed)
FSI_URL = "https://fragilestatesindex.org/wp-content/uploads/2023/06/FSI-2023-DOWNLOAD.xlsx"

# ---------------------------------------------------------------------------
# Raw series fetched from the APIs.  key -> (provider, code, options)
# provider: "WB" (World Bank API), "IMF" (IMF DataMapper API), "UNHCR"
# ---------------------------------------------------------------------------
WGI_DIMENSIONS = {
    "va": "Voice & Accountability",
    "pv": "Political Stability & Absence of Violence",
    "ge": "Government Effectiveness",
    "rq": "Regulatory Quality",
    "rl": "Rule of Law",
    "cc": "Control of Corruption",
}

RAW_SERIES: dict[str, tuple[str, str, dict]] = {
    # World Bank Worldwide Governance Indicators (source 3), 0-100 score, higher = better
    **{
        f"wgi_{d}": ("WB", f"GOV_WGI_{d.upper()}.SC", {"source": 3})
        for d in WGI_DIMENSIONS
    },
    # World Development Indicators (source 2)
    "pop": ("WB", "SP.POP.TOTL", {}),
    "battle_deaths": ("WB", "VC.BTL.DETH", {}),
    "homicide": ("WB", "VC.IHR.PSRC.P5", {}),
    "reserves_months": ("WB", "FI.RES.TOTL.MO", {}),
    "unemployment": ("WB", "SL.UEM.TOTL.ZS", {}),
    "youth_unemployment": ("WB", "SL.UEM.1524.ZS", {}),
    # IMF World Economic Outlook via DataMapper (includes projections)
    "inflation": ("IMF", "PCPIPCH", {}),
    "gdp_growth": ("IMF", "NGDP_RPCH", {}),
    "gov_debt": ("IMF", "GGXWDG_NGDP", {}),
    "fiscal_balance": ("IMF", "GGXCNL_NGDP", {}),
    "current_account": ("IMF", "BCA_NGDPD", {}),
    "unemployment_imf": ("IMF", "LUR", {}),
    "gdppc": ("IMF", "NGDPDPC", {}),
    "pop_imf": ("IMF", "LP", {}),  # millions; fallback for economies outside the WDI
    # UNHCR: refugees + asylum seekers + other people in need of protection + IDPs, by origin
    "displaced": ("UNHCR", "population", {}),
}

# Confidence-interval series for the WGI charts (loaded lazily on the country page)
WGI_CI_SERIES: dict[str, tuple[str, str, dict]] = {
    **{f"wgi_{d}_lb": ("WB", f"GOV_WGI_{d.upper()}.SC_LB", {"source": 3}) for d in WGI_DIMENSIONS},
    **{f"wgi_{d}_ub": ("WB", f"GOV_WGI_{d.upper()}.SC_UB", {"source": 3}) for d in WGI_DIMENSIONS},
}

SOURCE_LABELS = {
    "WB": "World Bank",
    "IMF": "IMF World Economic Outlook",
    "UNHCR": "UNHCR Refugee Data Finder",
}


# ---------------------------------------------------------------------------
# Source registry: every dataset and reference behind the tool, cited wherever its data appears
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Source:
    name: str
    publisher: str
    url: str
    used_for: str
    updates: str = ""
    terms: str = ""


SOURCES: dict[str, Source] = {
    "wgi": Source("Worldwide Governance Indicators", "World Bank", URL_WGI,
                  "The six governance scores: the Governance pillar and political stability", "Yearly",
                  "CC BY 4.0"),
    "wdi": Source("World Development Indicators", "World Bank", URL_WDI,
                  "Population, homicide rate, FX reserves, unemployment, youth unemployment", "Per indicator, "
                  "several times a year", "CC BY 4.0"),
    "ucdp": Source("UCDP battle-related deaths (via World Bank WDI)", "Uppsala Conflict Data Program",
                   "https://ucdp.uu.se/downloads/", "Battle deaths, armed-conflict flags and the globe's conflict "
                   "rings", "Yearly"),
    "ucdp_def": Source("UCDP definitions", "Uppsala Conflict Data Program",
                       "https://www.uu.se/en/department/peace-and-conflict-research/research/ucdp/ucdp-definitions",
                       "The 25 (armed conflict) and 1,000 (war) battle-death thresholds"),
    "imf": Source("World Economic Outlook", "International Monetary Fund", URL_IMF_WEO,
                  "Inflation, growth, public debt, fiscal and current-account balances, GDP per capita, projections",
                  "Twice a year (April and October)"),
    "imf_ara": Source("Assessing Reserve Adequacy", "International Monetary Fund",
                      "https://www.imf.org/external/np/spr/ara/", "The 3-months-of-imports reserves warning line"),
    "unhcr": Source("Refugee Data Finder", "UNHCR", URL_UNHCR,
                    "Forcibly displaced people, displacement share, refugee flows and host countries",
                    "Yearly, with a mid-year update"),
    "news": Source("Bing News and Google News (RSS search)", "Microsoft and Google", "https://www.bing.com/news",
                   "Live headlines and photos; every headline links to its original publisher", "Every 10 minutes"),
    "gdelt": Source("GDELT DOC 2.0", "The GDELT Project", URL_GDELT, "Backup headlines, media tone and protest coverage",
                    "Every 15 minutes"),
    "youtube": Source("Official YouTube channels of broadcasters, think tanks and institutions", "Each channel",
                      "https://www.youtube.com", "Live TV and video reports, through official embeds and feeds",
                      "Live; feeds every 15 minutes", "Each video belongs to its channel"),
    "ifes": Source("ElectionGuide", "IFES", "https://www.electionguide.org/", "Dates of the events in the watchlist",
                   "Checked when events are added"),
    "wb_countries": Source("World Bank country API", "World Bank", URL_WB_API,
                           "Country list, regions, income groups, capitals", "Continuously", "CC BY 4.0"),
    "natural_earth": Source("Admin-0 countries, 1:110m and 1:50m (v5.1.2)", "Natural Earth",
                            "https://www.naturalearthdata.com/", "Country outlines on the 3D globe", "Static",
                            "Public domain"),
    "flags": Source("flag-icons (v7.5.0)", "lipis/flag-icons", "https://github.com/lipis/flag-icons",
                    "Country flags", "Static", "MIT"),
    "icd203": Source("ICD 203: Analytic Standards", "US Office of the Director of National Intelligence",
                     "https://www.dni.gov/files/documents/ICD/ICD-203.pdf",
                     "Estimative language (probability words) in the assessment builder"),
    "oecd_jrc": Source("Handbook on Constructing Composite Indicators", "OECD and European Commission JRC",
                       "https://www.oecd.org/en/publications/handbook-on-constructing-composite-indicators-"
                       "methodology-and-user-guide_9789264043466-en.html",
                       "The method behind the index: normalisation, weighting, aggregation"),
    # --- Definitions, methods and thresholds ---
    "wgi_docs": Source("WGI documentation", "World Bank", f"{URL_WGI}/documentation",
                       "Definitions of the six governance dimensions"),
    "wgi_method": Source("The Worldwide Governance Indicators: 2025 Methodology Revision", "World Bank", URL_WGI_2025,
                         "The 0–100 scale and the 90% confidence intervals of the governance scores"),
    "wb_groups": Source("World Bank country and lending groups", "World Bank",
                        "https://datahelpdesk.worldbank.org/knowledgebase/articles/906519-world-bank-country-and-"
                        "lending-groups", "Regions and income groups used for peers and regional briefings",
                        "Every 1 July"),
    "iso3166": Source("ISO 3166 country codes", "International Organization for Standardization",
                      "https://www.iso.org/iso-3166-country-codes.html", "The two- and three-letter country codes"),
    "unhcr_def": Source("Refugee Data Finder: definitions", "UNHCR",
                        "https://www.unhcr.org/refugee-statistics/methodology/definition",
                        "Who is counted as forcibly displaced, and in which category"),
    "refugee_convention": Source("The 1951 Refugee Convention", "UNHCR",
                                 "https://www.unhcr.org/about-unhcr/overview/1951-refugee-convention",
                                 "The legal definition of a refugee"),
    "unhcr_asylum": Source("Asylum-seekers", "UNHCR", "https://www.unhcr.org/about-unhcr/who-we-protect/asylum-seekers",
                           "Who counts as an asylum seeker"),
    "unhcr_idp": Source("Internally displaced people", "UNHCR",
                        "https://www.unhcr.org/about-unhcr/who-we-protect/internally-displaced-people",
                        "Who counts as internally displaced"),
    "unodc": Source("Global Study on Homicide", "UN Office on Drugs and Crime",
                    "https://www.unodc.org/unodc/en/data-and-analysis/global-study-on-homicide.html",
                    "The homicide statistics behind the World Bank series, and global comparisons"),
    "ilo_unemployment": Source("Unemployment, total (modelled ILO estimate)", "International Labour Organization via "
                               "World Bank", "https://data.worldbank.org/indicator/SL.UEM.TOTL.ZS",
                               "The international definition of unemployment used by the index"),
    "imf_weo": Source("World Economic Outlook reports", "International Monetary Fund",
                      "https://www.imf.org/en/Publications/WEO", "The analysis that comes with the IMF projections",
                      "April and October"),
    "imf_fm": Source("Fiscal Monitor", "International Monetary Fund", "https://www.imf.org/en/Publications/FM",
                     "Public debt and budget balances in context", "April and October"),
    "imf_inflation": Source("Inflation: Prices on the Rise (Back to Basics)", "IMF Finance & Development",
                            "https://www.imf.org/en/Publications/fandd/issues/Series/Back-to-Basics/Inflation",
                            "A plain-language explanation of inflation"),
    "imf_gdp": Source("Gross Domestic Product: An Economy's All (Back to Basics)", "IMF Finance & Development",
                      "https://www.imf.org/en/Publications/fandd/issues/Series/Back-to-Basics/gross-domestic-"
                      "product-GDP", "A plain-language explanation of GDP and growth"),
    "imf_lending": Source("IMF Lending (factsheet)", "International Monetary Fund",
                          "https://www.imf.org/en/About/Factsheets/IMF-Lending",
                          "What an IMF programme is and how its conditions work"),
    "rr_inflation": Source("This Time is Different: A Panoramic View of Eight Centuries of Financial Crises (NBER "
                           "w13882)", "Carmen Reinhart and Kenneth Rogoff, NBER", "https://www.nber.org/papers/w13882",
                           "The 20%-a-year line for an inflation crisis"),
    "rr_debt": Source("Growth in a Time of Debt (NBER w15639)", "Carmen Reinhart and Kenneth Rogoff, NBER",
                      "https://www.nber.org/papers/w15639",
                      "The 90%-of-GDP public-debt benchmark (its growth effect is disputed)"),
    "freund": Source("Current Account Adjustment in Industrialized Countries (IFDP 692)",
                     "Caroline Freund, US Federal Reserve Board",
                     "https://www.federalreserve.gov/pubs/ifdp/2000/692/default.htm",
                     "Current-account deficits around 5% of GDP as the point where adjustment tends to start"),
    "eu_sgp": Source("Stability and Growth Pact", "European Commission",
                     "https://economy-finance.ec.europa.eu/economic-governance-framework/stability-and-growth-pact_en",
                     "The EU's 3%-of-GDP deficit reference value, for comparison with the 5% flag"),
    "cia_tradecraft": Source("A Tradecraft Primer: Structured Analytic Techniques", "US Central Intelligence Agency",
                             "https://www.cia.gov/resources/csi/static/Tradecraft-Primer-apr09.pdf",
                             "Scenarios, drivers and signposts, as used in the assessment builder"),
    "heuer": Source("Psychology of Intelligence Analysis", "Richards J. Heuer Jr., CIA Center for the Study of "
                    "Intelligence", "https://www.cia.gov/resources/csi/static/Pyschology-of-Intelligence-Analysis.pdf",
                    "Cognitive biases, and why judgments should carry stated probabilities"),
    "ocha": Source("UN Office for the Coordination of Humanitarian Affairs", "United Nations",
                   "https://www.unocha.org/", "Humanitarian situation reports and appeals"),
    "globe_gl": Source("globe.gl (v2.46.2) and three-globe", "Vasco Asturiano", "https://globe.gl/",
                       "The 3D globe engine and its night-Earth texture", "Static", "MIT"),
    # --- Independent indices to cross-check the scores against ---
    "acled": Source("Armed Conflict Location & Event Data (ACLED)", "ACLED", "https://acleddata.com/",
                    "Political violence and protest events, near real time", "Weekly", "Registration required"),
    "gpi": Source("Global Peace Index", "Institute for Economics & Peace", "https://www.visionofhumanity.org/maps/",
                  "Peacefulness of 163 countries: conflict, safety and militarisation", "Yearly"),
    "sipri": Source("SIPRI databases", "Stockholm International Peace Research Institute",
                    "https://www.sipri.org/databases", "Military spending, arms transfers and peace operations",
                    "Yearly"),
    "vdem": Source("Varieties of Democracy (V-Dem)", "V-Dem Institute, University of Gothenburg",
                   "https://www.v-dem.net/", "Hundreds of expert-coded measures of democracy", "Yearly"),
    "freedom_house": Source("Freedom in the World", "Freedom House", "https://freedomhouse.org/report/freedom-world",
                            "Political rights and civil liberties scores", "Yearly"),
    "eiu_democracy": Source("Democracy Index", "Economist Intelligence Unit",
                            "https://www.eiu.com/n/campaigns/democracy-index-2024/",
                            "Regime type and quality of democracy", "Yearly"),
    "rsf": Source("World Press Freedom Index", "Reporters Without Borders", "https://rsf.org/en/index",
                  "Media freedom by country", "Yearly"),
    "oecd_crc": Source("Country Risk Classification", "OECD",
                       "https://www.oecd.org/en/topics/country-risk-classification.html",
                       "Official export-credit country risk categories (0–7)", "Several times a year"),
    "undp_hdi": Source("Human Development Index", "UN Development Programme",
                       "https://hdr.undp.org/data-center/human-development-index",
                       "Health, education and income", "Yearly"),
    "fao_giews": Source("Global Information and Early Warning System (GIEWS)", "UN Food and Agriculture Organization",
                        "https://www.fao.org/giews/en/", "Food-security early warnings and food-price alerts",
                        "Monthly"),
    "idmc": Source("Internal Displacement Monitoring Centre", "IDMC (Norwegian Refugee Council)",
                   "https://www.internal-displacement.org/", "Internal displacement by conflict and disasters",
                   "Yearly, with updates"),
    "reliefweb": Source("ReliefWeb", "UN OCHA", "https://reliefweb.int/",
                        "Humanitarian reports, maps and situation updates", "Daily"),
    "hdx": Source("Humanitarian Data Exchange", "UN OCHA", "https://data.humdata.org/",
                  "Open crisis datasets from humanitarian agencies", "Daily"),
    "fsi": Source("Fragile States Index", "The Fund for Peace", "https://fragilestatesindex.org/",
                  "An overall fragility score from 12 indicators; the benchmark on the Methodology page", "Yearly"),
    "wikipedia": Source("Wikipedia articles on the case-study events", "Wikimedia Foundation", "https://en.wikipedia.org/",
                        "Background reading on the events in the case studies (dates and what happened)",
                        "Continuously", "CC BY-SA 4.0"),
}
# The index is built from these
INDEX_SOURCES = ["wgi", "wdi", "ucdp", "imf", "unhcr"]
# Short names for inline citations
CITE_LABELS = {
    "wgi": "World Bank WGI", "wdi": "World Bank WDI", "ucdp": "UCDP", "ucdp_def": "UCDP definitions",
    "imf": "IMF WEO", "imf_ara": "IMF reserve adequacy", "unhcr": "UNHCR", "news": "Bing News & Google News",
    "gdelt": "GDELT", "youtube": "official YouTube channels", "ifes": "IFES ElectionGuide",
    "wb_countries": "World Bank country API", "natural_earth": "Natural Earth", "flags": "flag-icons",
    "icd203": "ICD 203 (ODNI)", "oecd_jrc": "OECD/JRC Handbook", "wgi_method": "WGI methodology",
    "wgi_docs": "WGI documentation", "wb_groups": "World Bank country groups", "unhcr_def": "UNHCR definitions",
    "rr_inflation": "Reinhart & Rogoff (2008)", "rr_debt": "Reinhart & Rogoff (2010)", "freund": "Freund (2000)",
    "eu_sgp": "EU Stability and Growth Pact", "unodc": "UNODC", "imf_weo": "IMF WEO reports", "imf_fm": "IMF Fiscal Monitor",
    "cia_tradecraft": "CIA Tradecraft Primer", "heuer": "Heuer", "globe_gl": "globe.gl",
}
# How the Sources page groups the registry
SOURCE_GROUPS: dict[str, list[str]] = {
    "Country lists, codes and groups": ["wb_countries", "wb_groups", "iso3166"],
    "Definitions behind the warnings": ["ucdp_def", "unhcr_def", "refugee_convention", "unhcr_asylum", "unhcr_idp",
                                        "imf_ara", "rr_inflation", "rr_debt", "freund", "eu_sgp", "unodc",
                                        "ilo_unemployment"],
    "Method and analytic tradecraft": ["oecd_jrc", "wgi_docs", "wgi_method", "icd203", "cia_tradecraft", "heuer"],
    "Economic explainers and reports": ["imf_weo", "imf_fm", "imf_inflation", "imf_gdp", "imf_lending"],
    "Live news, video and events": ["news", "gdelt", "youtube", "ifes", "ocha", "wikipedia"],
    "Maps and graphics": ["natural_earth", "globe_gl", "flags"],
}
# Independent sources to check each pillar against (not used in the score)
CROSS_CHECKS: dict[str, list[str]] = {
    "stability": ["acled", "gpi", "sipri"],
    "governance": ["vdem", "freedom_house", "eiu_democracy", "rsf"],
    "economic": ["oecd_crc", "imf_weo", "imf_fm"],
    "social": ["undp_hdi", "fao_giews", "idmc", "reliefweb", "hdx"],
    "composite": ["fsi"],
}


def series_source(key: str) -> str:
    """The SOURCES key behind a raw series."""
    if key.startswith("wgi_"):
        return "wgi"
    if key == "battle_deaths":
        return "ucdp"
    return {"IMF": "imf", "UNHCR": "unhcr"}.get(RAW_SERIES[key][0], "wdi")


def series_url(key: str) -> str | None:
    """The public data page of a raw series (World Bank indicator page, IMF DataMapper chart, UNHCR finder)."""
    spec = RAW_SERIES.get(key)
    if spec is None:
        return None
    provider, code, options = spec
    if provider == "WB":
        return URL_WGI if options.get("source") == 3 else f"https://data.worldbank.org/indicator/{code}"
    if provider == "IMF":
        return f"https://www.imf.org/external/datamapper/{code}@WEO"
    return URL_UNHCR


# ---------------------------------------------------------------------------
# Pillars and indicators
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Pillar:
    key: str
    label: str
    short: str
    default_weight: int
    question: str


PILLARS: list[Pillar] = [
    Pillar(
        "stability",
        "Political Stability & Violence",
        "Stability",
        35,
        "How likely is political violence, unrest or armed conflict to disrupt people and operations?",
    ),
    Pillar(
        "governance",
        "Governance & Institutions",
        "Governance",
        25,
        "Can institutions be relied on — courts, regulators, contracts, clean administration?",
    ),
    Pillar(
        "economic",
        "Macroeconomic & Financial",
        "Economy",
        25,
        "Is the economy exposed to a crisis — inflation, debt distress, balance-of-payments stress?",
    ),
    Pillar(
        "social",
        "Social & Humanitarian Pressure",
        "Social",
        15,
        "Are there social pressures that can turn into instability — joblessness, displacement?",
    ),
]
PILLAR_BY_KEY = {p.key: p for p in PILLARS}


@dataclass(frozen=True)
class Indicator:
    key: str
    label: str
    short: str
    pillar: str
    higher_is_riskier: bool
    unit: str
    decimals: int
    source: str
    source_url: str
    description: str
    series: str | None = None  # key in RAW_SERIES (None for derived indicators)
    fallback_series: str | None = None  # used where the main series has no value
    lookback: int = 5  # years to look back for the most recent value
    norm: str = "percentile"  # "percentile" or "log" (for zero-heavy indicators)
    scored: bool = True

    def fmt(self, value) -> str:
        if value is None or value != value:  # NaN check
            return "—"
        return f"{value:,.{self.decimals}f}"


INDICATORS: list[Indicator] = [
    # --- Political stability & violence ---------------------------------
    Indicator(
        "wgi_pv", "Political stability & absence of violence", "Political stability",
        "stability", False, "WGI score, 0–100", 1, "World Bank WGI", URL_WGI,
        "Perceptions of the likelihood of political instability and politically motivated "
        "violence, including terrorism. Higher score = more stable.",
        series="wgi_pv", lookback=3,
    ),
    Indicator(
        "battle_deaths_100k", "Battle-related deaths per 100,000 people", "Battle deaths /100k",
        "stability", True, "deaths per 100k", 2, "UCDP via World Bank WDI", URL_UCDP,
        "Deaths in state-based armed conflicts (UCDP definition), scaled by population. "
        "Countries with no recorded conflict are scored 0.",
        norm="log",
    ),
    Indicator(
        "homicide", "Intentional homicides per 100,000 people", "Homicide rate",
        "stability", True, "per 100k", 1, "UNODC via World Bank WDI", URL_WDI,
        "A proxy for criminal violence and the state's control over security.",
        series="homicide", lookback=8,
    ),
    # --- Governance & institutions --------------------------------------
    Indicator(
        "wgi_va", "Voice & accountability", "Voice & accountability", "governance", False,
        "WGI score, 0–100", 1, "World Bank WGI", URL_WGI,
        "Citizens' ability to choose their government; freedom of expression, association and media.",
        series="wgi_va", lookback=3,
    ),
    Indicator(
        "wgi_ge", "Government effectiveness", "Gov. effectiveness", "governance", False,
        "WGI score, 0–100", 1, "World Bank WGI", URL_WGI,
        "Quality of public services and the civil service, and the credibility of policy commitments.",
        series="wgi_ge", lookback=3,
    ),
    Indicator(
        "wgi_rq", "Regulatory quality", "Regulatory quality", "governance", False,
        "WGI score, 0–100", 1, "World Bank WGI", URL_WGI,
        "Ability to formulate and implement sound policies that permit private-sector development.",
        series="wgi_rq", lookback=3,
    ),
    Indicator(
        "wgi_rl", "Rule of law", "Rule of law", "governance", False,
        "WGI score, 0–100", 1, "World Bank WGI", URL_WGI,
        "Confidence in contract enforcement, property rights, the police and the courts.",
        series="wgi_rl", lookback=3,
    ),
    Indicator(
        "wgi_cc", "Control of corruption", "Control of corruption", "governance", False,
        "WGI score, 0–100", 1, "World Bank WGI", URL_WGI,
        "The extent to which public power is exercised for private gain, including state capture.",
        series="wgi_cc", lookback=3,
    ),
    # --- Macroeconomic & financial ----------------------------------------
    Indicator(
        "inflation", "Inflation, average consumer prices", "Inflation",
        "economic", True, "% change", 1, "IMF WEO", URL_IMF_WEO,
        "Current-year IMF estimate. High inflation erodes incomes and is a classic trigger of unrest.",
        series="inflation", lookback=2,
    ),
    Indicator(
        "gdp_growth", "Real GDP growth", "GDP growth", "economic", False,
        "% change", 1, "IMF WEO", URL_IMF_WEO,
        "Current-year IMF estimate. Recessions strain budgets, jobs and political support.",
        series="gdp_growth", lookback=2,
    ),
    Indicator(
        "gov_debt", "General government gross debt", "Public debt", "economic", True,
        "% of GDP", 1, "IMF WEO", URL_IMF_WEO,
        "Current-year IMF estimate. High debt limits room to respond to shocks.",
        series="gov_debt", lookback=2,
    ),
    Indicator(
        "fiscal_balance", "Government net lending/borrowing", "Fiscal balance", "economic", False,
        "% of GDP", 1, "IMF WEO", URL_IMF_WEO,
        "Current-year IMF estimate. Large deficits signal pressure for austerity or money printing.",
        series="fiscal_balance", lookback=2,
    ),
    Indicator(
        "current_account", "Current account balance", "Current account", "economic", False,
        "% of GDP", 1, "IMF WEO", URL_IMF_WEO,
        "Current-year IMF estimate. Persistent deficits create dependence on foreign financing.",
        series="current_account", lookback=2,
    ),
    Indicator(
        "reserves_months", "Total reserves in months of imports", "FX reserves", "economic", False,
        "months of imports", 1, "World Bank WDI", URL_WDI,
        "The buffer against a currency or balance-of-payments crisis. Under 3 months is a common warning line.",
        series="reserves_months", lookback=4,
    ),
    # --- Social & humanitarian pressure ------------------------------------
    Indicator(
        "unemployment", "Unemployment rate", "Unemployment", "social", True,
        "% of labour force", 1, "ILO modelled estimate via World Bank WDI", URL_WDI,
        "Share of the labour force without work (IMF estimate used where the ILO series is missing).",
        series="unemployment", fallback_series="unemployment_imf", lookback=3,
    ),
    Indicator(
        "youth_unemployment", "Youth unemployment (ages 15–24)", "Youth unemployment", "social", True,
        "% of youth labour force", 1, "ILO modelled estimate via World Bank WDI", URL_WDI,
        "A well-documented driver of protest movements.",
        series="youth_unemployment", lookback=3,
    ),
    Indicator(
        "displaced_share", "Forcibly displaced people from the country", "Displaced (% pop.)",
        "social", True, "% of population", 2, "UNHCR", URL_UNHCR,
        "Refugees, asylum seekers, others in need of international protection and internally "
        "displaced people originating from the country, as a share of its population.",
        norm="log",
    ),
]
INDICATOR_BY_KEY = {i.key: i for i in INDICATORS}


def indicator_source(ind: Indicator) -> str:
    """The SOURCES key behind an indicator, for citations."""
    if ind.key.startswith("wgi_"):
        return "wgi"
    if ind.key == "battle_deaths_100k":
        return "ucdp"
    if ind.key == "displaced_share":
        return "unhcr"
    return "imf" if RAW_SERIES[ind.series][0] == "IMF" else "wdi"


def indicator_url(ind: Indicator) -> str:
    """Where to see the data behind an indicator, as published by its source."""
    if ind.series:
        return series_url(ind.series) or ind.source_url
    return {"battle_deaths_100k": "https://data.worldbank.org/indicator/VC.BTL.DETH",
            "displaced_share": URL_UNHCR}.get(ind.key, ind.source_url)
SCORED_INDICATORS = [i for i in INDICATORS if i.scored]


def indicators_for(pillar_key: str) -> list[Indicator]:
    return [i for i in SCORED_INDICATORS if i.pillar == pillar_key]


# A pillar is scored only if at least this share of its indicators is available
PILLAR_MIN_SHARE = 0.5
# The composite is scored only if at least this many pillars are available
COMPOSITE_MIN_PILLARS = 3
# For log-normalised indicators: values at or above this percentile of non-zero
# values get the maximum score, so one extreme case does not flatten everyone else
LOG_CAP_QUANTILE = 0.90

# ---------------------------------------------------------------------------
# Risk tiers (ordinal ramp validated for contrast and step visibility)
# ---------------------------------------------------------------------------
# The app uses a black theme, so every ramp runs dark -> bright: low risk recedes into the
# background and high risk glows. Ramps hold one hue in OKLCH with even lightness steps.
@dataclass(frozen=True)
class Tier:
    label: str
    lower: float
    color: str
    text_on: str  # readable text colour on top of the tier colour


TIERS: list[Tier] = [
    Tier("Low", 0, "#9b0e1b", "#ffffff"),
    Tier("Moderate", 20, "#c42d31", "#ffffff"),
    Tier("Elevated", 40, "#e94f4d", "#000000"),
    Tier("High", 60, "#fd8078", "#000000"),
    Tier("Severe", 80, "#feb5ae", "#000000"),
]
TIER_ORDER = [t.label for t in TIERS]
TIER_COLORS = {t.label: t.color for t in TIERS}

# Continuous scale for maps: near-zero recedes toward the black surface, then the tier ramp
MAP_COLORSCALE = [
    [0.0, "#4f0007"],
    [0.2, "#9b0e1b"],
    [0.4, "#c42d31"],
    [0.6, "#e94f4d"],
    [0.8, "#fd8078"],
    [1.0, "#feb5ae"],
]
NO_DATA_COLOR = "#2e2e2c"
OCEAN_COLOR = "#07111f"

# Pillar identity colours (categorical slots 1-4 in fixed order, dark-mode steps) and a one-hue
# map ramp per pillar (OKLCH lightness 0.27 -> 0.87), so brighter always means riskier.
PILLAR_COLORS = {"stability": "#3987e5", "governance": "#d95926", "economic": "#199e70", "social": "#c98500"}
PILLAR_RAMPS = {
    "stability": ["#002550", "#014387", "#1665bc", "#3c89e8", "#74b1fe", "#b9d7fe"],
    "governance": ["#461300", "#772601", "#ad3b01", "#dc5c29", "#fc8a61", "#fec5b1"],
    "economic": ["#012f1e", "#035238", "#047954", "#1fa173", "#5ac698", "#93eac1"],
    "social": ["#372101", "#5f3d03", "#8a5b04", "#b87b0c", "#e19f3f", "#feca85"],
}


# Diverging scale for change maps (dark mode): two hues with a neutral grey midpoint, equal steps per arm,
# matched lightness on both sides (bright = big move, dark grey = no change)
CHANGE_COLORSCALE = [[0.0, "#74b1fe"], [0.25, "#1665bc"], [0.5, "#383835"], [0.75, "#c42d31"], [1.0, "#fd8078"]]


def reversed_scale(scale: list[list]) -> list[list]:
    """The same colours, bright end first (e.g. 'sooner = brighter' for days until an event)."""
    return [[round(1 - t, 4), c] for t, c in reversed(scale)]


def map_colorscale(metric: str) -> list[list]:
    """Composite uses the tier ramp; each pillar map uses its own hue."""
    ramp = PILLAR_RAMPS.get(metric)
    if ramp is None:
        return MAP_COLORSCALE
    return [[i / (len(ramp) - 1), c] for i, c in enumerate(ramp)]


# ---------------------------------------------------------------------------
# Video: broadcasters' and think tanks' official YouTube channels (embeds and public RSS feeds, no API key)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Channel:
    id: str
    region: str
    origin: str
    funding: str  # "Public broadcaster", "State-funded", "State-owned" or "Commercial"


LIVE_CHANNELS: dict[str, Channel] = {  # 24/7 live English-language news streams, verified via their feeds
    "ABC News (US)": Channel("UCBi2mrWuNuyYy4gbM6fU18Q", "Americas", "United States", "Commercial"),
    "CBS News": Channel("UC8p1vwvWtl6T73JiExfWs1g", "Americas", "United States", "Commercial"),
    "NBC News": Channel("UCeY0bbntWzzVIaj2z3QigXg", "Americas", "United States", "Commercial"),
    "Bloomberg Television": Channel("UCIALMKvObZNtJ6AmdCLP7Lg", "Americas", "United States", "Commercial"),
    "Global News": Channel("UChLtXXpo4Ge1ReTEboVvTDg", "Americas", "Canada", "Commercial"),
    "DW News": Channel("UCknLrEdhRCp1aegoMqRaCZg", "Europe", "Germany", "Public broadcaster"),
    "France 24 English": Channel("UCQfwfsi5VrQ8yKZ-UWmAEFg", "Europe", "France", "Public broadcaster"),
    "Sky News": Channel("UCoMdktPbSTixAyNGwb-UYkQ", "Europe", "United Kingdom", "Commercial"),
    "Euronews": Channel("UCSrZ3UV4jOidv8ppoVuvW9Q", "Europe", "Pan-European", "Commercial"),
    "Al Jazeera English": Channel("UCNye-wNBqNL5ZzHSJj3l8Bg", "Middle East", "Qatar", "State-funded"),
    "TRT World": Channel("UC7fWeaHhqgM4Ry-RMpM2YYw", "Middle East", "Türkiye", "State-owned"),
    "i24NEWS English": Channel("UCvHDpsWKADrDia0c99X37vg", "Middle East", "Israel", "Commercial"),
    "Africanews": Channel("UC1_E8NeF5QHY2dtdLRBCCLA", "Africa", "Pan-African", "Commercial"),
    "SABC News": Channel("UC8yH-uI81UUtEMDsowQyx1g", "Africa", "South Africa", "Public broadcaster"),
    "Channels Television": Channel("UCEXGDNclvmg6RW0vipJYsTQ", "Africa", "Nigeria", "Commercial"),
    "Arise News": Channel("UCyEJX-kSj0kOOCS7Qlq2G7g", "Africa", "Nigeria", "Commercial"),
    "KTN News Kenya": Channel("UCKVsdeoHExltrWMuK0hOWmg", "Africa", "Kenya", "Commercial"),
    "Citizen TV Kenya": Channel("UChBQgieUidXV1CmDxSdRm3g", "Africa", "Kenya", "Commercial"),
    "CNA": Channel("UC83jt4dlz1Gjl58fzQrrKZg", "Asia-Pacific", "Singapore", "State-owned"),
    "NHK WORLD-JAPAN": Channel("UCSPEjw8F2nQDtmUKPFNF7_A", "Asia-Pacific", "Japan", "Public broadcaster"),
    "ABC News Australia": Channel("UCVgO39Bk5sMo66-6o6Spn6Q", "Asia-Pacific", "Australia", "Public broadcaster"),
    "WION": Channel("UC_gUM8rL-Lrg6O3adPW9K1g", "Asia-Pacific", "India", "Commercial"),
    "NDTV": Channel("UCZFMm1mMw0F81Z37aaEzTUA", "Asia-Pacific", "India", "Commercial"),
    "India Today": Channel("UCYPvAwZP8pZhSMW8qs7cVCw", "Asia-Pacific", "India", "Commercial"),
    "CGTN": Channel("UCgrNz-aDmcr2uuto8_DL2jg", "Asia-Pacific", "China", "State-owned"),
}
LIVE_REGIONS = ["Europe", "Americas", "Middle East", "Africa", "Asia-Pacific"]
OTHER_NEWS_CHANNELS: dict[str, Channel] = {  # news uploads, but no 24/7 stream that can be embedded
    "BBC News": Channel("UC16niRr50-MSBwiO3YDb3RA", "Europe", "United Kingdom", "Public broadcaster"),
    "Reuters": Channel("UChqUTb7kYRX8-EiaN3XFrSQ", "Europe", "United Kingdom", "Commercial"),
    "Associated Press": Channel("UC52X5wxOL_s5yw0dQk7NtgA", "Americas", "United States", "Non-profit cooperative"),
}
NEWS_VIDEO_CHANNELS = {name: c.id for name, c in {**LIVE_CHANNELS, **OTHER_NEWS_CHANNELS}.items()}
ANALYSIS_VIDEO_CHANNELS = {  # think tanks: interviews, explainers and expert panels
    "Council on Foreign Relations": "UCL_A4jkwvKuMyToAPy3FQKQ",
    "International Crisis Group": "UCj015l-Gu66iB80-X_sr9tw",
    "Carnegie Endowment": "UCDeDd29TrRzAkSKXBCtGhxA",
    "Brookings Institution": "UCi7jxgIOxcRaF4Q54U7lF3g",
    "Atlantic Council": "UCw0y9zO1RXI6uEzoKbbnxTQ",
    "CSIS": "UCr5jq6MC_VCe1c5ciIZtk_w",
}
INSTITUTION_VIDEO_CHANNELS = {  # international organisations and NGOs
    "United Nations": "UC5O114-PQNYkurlTg6hekZw",
    "IMF": "UCIYhr3JsLYfKkCM7-W5B6DA",
    "World Bank": "UCE9mrcoX-oE-2f1BL-iPPoQ",
    "ICRC (Red Cross)": "UCZyACOXbNnPs2RXA_Iv9pxA",
    "Human Rights Watch": "UCoS-mm5bC5eY07AaKntKzgw",
}
# Extra words that identify a country in video titles (besides its name). All-caps entries match case-sensitively.
VIDEO_ALIASES = {
    "USA": ["US", "U.S.", "American", "Washington"], "GBR": ["UK", "Britain", "British"],
    "RUS": ["Russian", "Kremlin", "Moscow"], "CHN": ["Chinese", "Beijing"], "UKR": ["Ukrainian", "Kyiv"],
    "ISR": ["Israeli"], "PSE": ["Gaza", "Palestinian", "West Bank"], "IRN": ["Iranian", "Tehran"],
    "SDN": ["Sudanese", "Khartoum"], "SSD": ["South Sudanese"], "SYR": ["Syrian", "Damascus"],
    "AFG": ["Afghan", "Taliban"], "TWN": ["Taiwanese", "Taipei"], "PRK": ["North Korean", "Pyongyang"],
    "KOR": ["South Korean", "Seoul"], "IND": ["Indian", "New Delhi"], "PAK": ["Pakistani", "Islamabad"],
    "LBN": ["Lebanese", "Hezbollah", "Beirut"], "YEM": ["Yemeni", "Houthi", "Houthis"], "VEN": ["Venezuelan"],
    "HTI": ["Haitian"], "MMR": ["Burma"], "NGA": ["Nigerian"], "ETH": ["Ethiopian"], "COD": ["Congolese", "DRC"],
    "SOM": ["Somali"], "FRA": ["French"], "DEU": ["German"], "TUR": ["Turkey", "Turkish"], "BRA": ["Brazilian"],
    "MEX": ["Mexican"], "ARG": ["Argentine", "Argentinian"], "JPN": ["Japanese", "Tokyo"], "IRQ": ["Iraqi", "Baghdad"],
    "SAU": ["Saudi"], "EGY": ["Egyptian", "Cairo"], "MLI": ["Malian"], "BFA": ["Burkinabe"], "NER": ["Nigerien"],
}

# News search terms for each World Bank region (the full names make poor search queries)
REGION_NEWS = {
    "East Asia & Pacific": '("East Asia" OR "Southeast Asia" OR Pacific)',
    "Europe & Central Asia": '(Europe OR "Central Asia" OR Balkans OR Caucasus)',
    "Latin America & Caribbean": '("Latin America" OR Caribbean OR "South America")',
    "Middle East, North Africa, Afghanistan & Pakistan": '("Middle East" OR "North Africa" OR Gulf OR Afghanistan OR Pakistan)',
    "North America": '("United States" OR Canada)',
    "South Asia": '("South Asia" OR India OR Bangladesh OR "Sri Lanka" OR Nepal)',
    "Sub-Saharan Africa": '(Africa OR Sahel OR "Horn of Africa")',
}

# Shorter region names for chart labels (filters and tables keep the World Bank names)
REGION_SHORT = {"Middle East, North Africa, Afghanistan & Pakistan": "MENA, Afghanistan & Pakistan",
                "Latin America & Caribbean": "Latin America & Carib."}


def region_short(name: str) -> str:
    return REGION_SHORT.get(name, name)


# Rough region centres (lon, lat) for pointing the globe view
REGION_CENTERS = {
    "East Asia & Pacific": (120, 10),
    "Europe & Central Asia": (40, 50),
    "Latin America & Caribbean": (-70, -12),
    "Middle East, North Africa, Afghanistan & Pakistan": (40, 28),
    "North America": (-100, 45),
    "South Asia": (78, 22),
    "Sub-Saharan Africa": (20, -3),
}

# Categorical colours for comparing countries (fixed order, never cycled; dark-mode steps)
SERIES_COLORS = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300"]
MAX_COMPARE = len(SERIES_COLORS)
PRIMARY = "#3987e5"
FORECAST_GREY = "#898781"
MONO_FONT = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

# ---------------------------------------------------------------------------
# Red flags: absolute thresholds shown alongside the relative index
# ---------------------------------------------------------------------------
# (indicator key, comparison, threshold, severity, label)
RED_FLAGS: list[tuple[str, str, float, str, str]] = [
    ("battle_deaths_raw", ">=", 1000, "critical", "War-level violence (≥1,000 battle deaths in a year, UCDP threshold)"),
    ("battle_deaths_raw", ">=", 25, "serious", "Active armed conflict (≥25 battle deaths in a year, UCDP threshold)"),
    ("inflation", ">=", 50, "critical", "Very high inflation (≥50%)"),
    ("inflation", ">=", 20, "serious", "High inflation (≥20%)"),
    ("gdp_growth", "<", 0, "serious", "Economy contracting (negative real GDP growth)"),
    ("gov_debt", ">=", 90, "warning", "High public debt (≥90% of GDP)"),
    ("fiscal_balance", "<=", -5, "warning", "Large fiscal deficit (≥5% of GDP)"),
    ("current_account", "<=", -5, "warning", "Large current-account deficit (≥5% of GDP)"),
    ("reserves_months", "<", 3, "serious", "Thin FX reserves (<3 months of imports)"),
    ("youth_unemployment", ">=", 25, "warning", "Very high youth unemployment (≥25%)"),
    ("displaced_share", ">=", 5, "serious", "Mass displacement (≥5% of population displaced)"),
    ("homicide", ">=", 20, "serious", "Very high homicide rate (≥20 per 100k)"),
]
# Where each threshold comes from: (indicator key, threshold) -> (SOURCES key or None, basis)
FLAG_BASIS: dict[tuple[str, float], tuple[str | None, str]] = {
    ("battle_deaths_raw", 1000): ("ucdp_def", "UCDP's definition of a war"),
    ("battle_deaths_raw", 25): ("ucdp_def", "UCDP's definition of an active armed conflict"),
    ("inflation", 50): ("rr_inflation", "Seismographic line for a deep crisis, well above the 20% inflation-crisis "
                                        "line"),
    ("inflation", 20): ("rr_inflation", "Reinhart & Rogoff's definition of an inflation crisis"),
    ("gdp_growth", 0): ("imf_gdp", "By definition: real output is shrinking"),
    ("gov_debt", 90): ("rr_debt", "Reinhart & Rogoff's high-debt benchmark; later research disputes the growth "
                                  "effect, so it is only a Watch flag"),
    ("fiscal_balance", -5): ("eu_sgp", "Seismographic line; the EU's reference value is a 3% deficit"),
    ("current_account", -5): ("freund", "Deficits near 5% of GDP are where adjustment has tended to start"),
    ("reserves_months", 3): ("imf_ara", "The traditional rule of thumb discussed in the IMF's reserve-adequacy work"),
    ("youth_unemployment", 25): ("ilo_unemployment", "Seismographic line: one in four young people in the labour "
                                                     "force out of work"),
    ("displaced_share", 5): ("unhcr_def", "Seismographic line: one person in twenty forcibly displaced"),
    ("homicide", 20): ("unodc", "Seismographic line, several times the global rate in UNODC data"),
}
# Short names for tables and tooltips, where the full label would be cut off
FLAG_SHORT: dict[tuple[str, float], str] = {
    ("battle_deaths_raw", 1000): "War", ("battle_deaths_raw", 25): "Armed conflict",
    ("inflation", 50): "Inflation ≥ 50%", ("inflation", 20): "Inflation ≥ 20%",
    ("gdp_growth", 0): "Shrinking economy", ("gov_debt", 90): "Debt ≥ 90% of GDP",
    ("fiscal_balance", -5): "Deficit ≥ 5% of GDP", ("current_account", -5): "Current-account gap ≥ 5%",
    ("reserves_months", 3): "Reserves < 3 months", ("youth_unemployment", 25): "Youth jobless ≥ 25%",
    ("displaced_share", 5): "Displaced ≥ 5%", ("homicide", 20): "Homicides ≥ 20/100k",
}
SEVERITY_ORDER = {"critical": 0, "serious": 1, "warning": 2}
SEVERITY_ICON = {"critical": "🔴", "serious": "🟠", "warning": "🟡"}
SEVERITY_LABEL = {"critical": "Critical", "serious": "Serious", "warning": "Watch"}

# A WGI change is flagged as deteriorating when the score falls by at least this much over 3 years
WGI_TREND_YEARS = 3
WGI_TREND_THRESHOLD = 5.0

# ICD 203 estimative language (Intelligence Community Directive 203, Analytic Standards)
ESTIMATIVE_LANGUAGE: list[tuple[str, str, int, int]] = [
    ("almost no chance", "remote", 1, 5),
    ("very unlikely", "highly improbable", 5, 20),
    ("unlikely", "improbable", 20, 45),
    ("roughly even chance", "roughly even odds", 45, 55),
    ("likely", "probable", 55, 80),
    ("very likely", "highly probable", 80, 95),
    ("almost certain", "nearly certain", 95, 99),
]


def estimative_term(probability: float) -> str:
    """Map a probability (0-100) to the ICD 203 estimative term."""
    for term, _alt, low, high in ESTIMATIVE_LANGUAGE:
        if probability <= high:
            return term
    return ESTIMATIVE_LANGUAGE[-1][0]


# ---------------------------------------------------------------------------
# Country names and extra economies
# ---------------------------------------------------------------------------
# Economies the World Bank country list omits but WGI/IMF cover
EXTRA_ECONOMIES = {
    "TWN": {"name": "Taiwan", "region": "East Asia & Pacific", "income": "High income", "iso2": "TW",
            "capital": "Taipei", "lat": 25.0330, "lng": 121.5654},
}

# Flags: SVGs from the flag-icons package on jsDelivr, pinned to an exact version
FLAG_URL = "https://cdn.jsdelivr.net/npm/flag-icons@7.5.0/flags/4x3/{code}.svg"
NO_FLAG = {"JG"}  # World Bank codes with no flag in the set (Channel Islands)


def flag_url(iso2) -> str | None:
    code = str(iso2 or "").strip().upper()
    if len(code) != 2 or not code.isalpha() or code in NO_FLAG:
        return None
    return FLAG_URL.format(code=code.lower())


# First year of the risk-over-time history (the index is recomputed for every year since)
HISTORY_START = 2015
# WGI rows for non-member economies come without an ISO3 code; map them by name
WB_NAME_TO_ISO3 = {"Taiwan, China": "TWN"}
# IMF codes that differ from World Bank codes
IMF_TO_WB_ISO3 = {"UVK": "XKX", "WBG": "PSE"}

# Plain-English display names (the World Bank uses formal names such as "Egypt, Arab Rep.")
DISPLAY_NAMES = {
    "BHS": "The Bahamas", "BRN": "Brunei", "CIV": "Côte d'Ivoire", "COD": "DR Congo",
    "COG": "Republic of the Congo", "CPV": "Cabo Verde", "CZE": "Czechia", "EGY": "Egypt",
    "FSM": "Micronesia", "GMB": "The Gambia", "HKG": "Hong Kong", "IRN": "Iran",
    "KGZ": "Kyrgyzstan", "KNA": "St Kitts and Nevis", "KOR": "South Korea", "LAO": "Laos",
    "LCA": "St Lucia", "MAC": "Macao", "MKD": "North Macedonia", "PRK": "North Korea",
    "PSE": "West Bank and Gaza", "RUS": "Russia", "SVK": "Slovakia", "SOM": "Somalia", "STP": "São Tomé and Príncipe",
    "SYR": "Syria", "TUR": "Türkiye", "VCT": "St Vincent and the Grenadines", "VEN": "Venezuela",
    "VNM": "Vietnam", "YEM": "Yemen", "TWN": "Taiwan", "VIR": "US Virgin Islands",
    "MAF": "St Martin (French part)", "SXM": "Sint Maarten", "TCA": "Turks and Caicos Islands",
}
# Names that work better as news search terms
NEWS_NAMES = {
    "CIV": "Ivory Coast", "COD": "DR Congo", "COG": "Republic of Congo",
    "PSE": "Palestinian", "TUR": "Turkey", "STP": "Sao Tome", "MKD": "North Macedonia",
}
