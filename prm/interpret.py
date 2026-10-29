"""From numbers to the real world: plain-language readings of the index, and what to do with them.

Everything here is rule-based and general. It translates a country's tier, pillar scores, red flags,
trend and upcoming events into what they usually look like on the ground, and into common practical
responses for four audiences. It is educational guidance — not investment, legal or security advice —
and it is no substitute for current, local information.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import config, scoring

AUDIENCES = {
    "business": "Business & investors",
    "ngo": "NGOs & humanitarian work",
    "travel": "Travel, study & staff safety",
    "research": "Policy, journalism & research",
}

# Tier -> (one-line summary, what it usually looks like on the ground)
TIER_MEANING = {
    "Low": (
        "Among the most stable places in the sample.",
        "Politics rarely disrupts daily life or business. Institutions generally work, disputes go through "
        "courts and elections, and the economy has buffers. Risk comes mainly from unexpected shocks.",
    ),
    "Moderate": (
        "Broadly functional, with specific weak spots.",
        "Most things work most of the time, but there are soft spots — a stretched budget, patchy governance "
        "or pockets of unrest. Disruptions happen, and are usually contained and short.",
    ),
    "Elevated": (
        "Material risk on more than one front.",
        "Expect periodic protests, policy surprises or economic stress. Contracts and plans can be upset by "
        "events outside your control, so they need contingencies and regular review.",
    ),
    "High": (
        "Serious, persistent risk.",
        "Instability, weak institutions and/or economic crisis are part of normal operating conditions. "
        "Working there takes active risk management: security planning, financial safeguards and local advice.",
    ),
    "Severe": (
        "Among the most dangerous and fragile places in the world.",
        "War, the near-collapse of the state or a deep economic crisis. Daily life and business are heavily "
        "disrupted; outside presence is often limited to essential humanitarian, diplomatic or security work.",
    ),
}

# Pillar -> what a high score looks like on the ground, and who feels it first
PILLAR_MEANING = {
    "stability": {
        "ground": "Political violence, unrest and armed conflict: protests that shut roads and shops, attacks, "
                  "curfews and, at the extreme, war.",
        "felt_by": "Everyone physically there — residents, staff, travellers — and anything with a fixed location.",
    },
    "governance": {
        "ground": "Institutions you can't rely on: slow or biased courts, demands for bribes, rules that change "
                  "without warning, weak protection of property and contracts.",
        "felt_by": "Businesses, investors and NGOs dealing with officials, permits, contracts or courts.",
    },
    "economic": {
        "ground": "Exposure to an economic crisis: prices rising fast, a falling currency, shortages of dollars, "
                  "tax rises or spending cuts, and payments that arrive late or not at all.",
        "felt_by": "Anyone earning, saving, borrowing or trading in the local currency — and importers above all.",
    },
    "social": {
        "ground": "Pressures that can turn into instability: jobless young people, cost-of-living anger and mass "
                  "displacement.",
        "felt_by": "Communities, employers and governments — and often an early sign of unrest to come.",
    },
}

# What a high risk score on each indicator means, in a few words
INDICATOR_PHRASE = {
    "wgi_pv": "a high perceived risk of political violence",
    "battle_deaths_100k": "deaths in armed conflict",
    "homicide": "violent crime",
    "wgi_va": "limited political freedoms and accountability",
    "wgi_ge": "weak public services and policy delivery",
    "wgi_rq": "a difficult regulatory environment",
    "wgi_rl": "weak rule of law (courts, contracts, property)",
    "wgi_cc": "corruption",
    "inflation": "high inflation",
    "gdp_growth": "weak growth",
    "gov_debt": "heavy public debt",
    "fiscal_balance": "a large budget deficit",
    "current_account": "a large external deficit",
    "reserves_months": "thin foreign-exchange reserves",
    "unemployment": "unemployment",
    "youth_unemployment": "youth unemployment",
    "displaced_share": "mass displacement",
}

# Red-flag indicator -> (what it means in real life, what people typically do about it)
FLAG_MEANING = {
    "battle_deaths_raw": (
        "Armed conflict is killing people on a scale that counts as war or active conflict. Fighting can move "
        "fast, cut roads and supply lines, and spill into neighbouring areas.",
        "Most governments advise against travel to affected areas; organisations limit presence to essential "
        "staff with security plans, and insurers treat the area as a war zone.",
    ),
    "inflation": (
        "Prices are rising fast, so wages, savings and fixed-price contracts lose value month by month — a "
        "classic trigger of cost-of-living protests and strikes.",
        "Contracts are indexed to inflation or priced in hard currency; salaries and cash transfers are "
        "reviewed often; stock is bought earlier before prices rise.",
    ),
    "gdp_growth": (
        "The economy is shrinking: weaker demand, layoffs and falling tax revenue, which can sour the political "
        "mood and squeeze the government's budget.",
        "Sales forecasts are cut and credit risk on local customers is reviewed; layoffs and wage disputes are "
        "anticipated.",
    ),
    "gov_debt": (
        "Public debt is high, leaving little room to respond to a shock. Tax rises, spending cuts or an IMF "
        "programme become more likely — and in the worst case a debt restructuring.",
        "Exposure to government bonds and public-sector clients is checked; budget announcements and IMF talks "
        "are watched as risk events.",
    ),
    "fiscal_balance": (
        "The government spends far more than it collects. That usually ends in tax rises, spending cuts, money "
        "printing or late payments to suppliers.",
        "Payment terms with government clients are tightened; tax changes are planned for.",
    ),
    "current_account": (
        "The country relies on foreign money to pay for its imports, which leaves the currency vulnerable if "
        "investors pull back.",
        "Currency exposure is hedged or reduced; supply chains that depend on imports are reviewed.",
    ),
    "reserves_months": (
        "The central bank has little foreign currency left — under three months of imports. This often comes "
        "before import restrictions, dollar shortages, capital controls or a devaluation.",
        "Firms keep extra stock of imported inputs, convert local earnings to hard currency promptly, and check "
        "the rules on moving money out of the country.",
    ),
    "youth_unemployment": (
        "A quarter or more of young people who want work can't find it — a well-documented driver of protest "
        "movements and emigration.",
        "Employers invest in local hiring and training; analysts watch campuses, social media and fuel or food "
        "price decisions as protest triggers.",
    ),
    "displaced_share": (
        "At least one person in twenty has been forced from their home. Needs for shelter, food and health care "
        "are large, and neighbouring countries carry heavy pressure.",
        "Humanitarian agencies scale up through UN-led coordination; donors and host governments plan for "
        "long-term displacement, not just emergency relief.",
    ),
    "homicide": (
        "Violent crime is very high — twenty or more murders per 100,000 people a year — affecting residents, "
        "staff and visitors.",
        "Organisations adopt crime-specific security measures: vetted transport, secure accommodation, "
        "restrictions on night travel.",
    ),
}

# "Close to a red line": indicator -> (comparison, warning level) — checked only if the flag itself isn't raised
NEAR = {
    "inflation": (">=", 15), "gdp_growth": ("<", 1.0), "gov_debt": (">=", 80), "fiscal_balance": ("<=", -4),
    "current_account": ("<=", -4), "reserves_months": ("<", 3.6), "youth_unemployment": (">=", 20),
    "displaced_share": (">=", 3), "homicide": (">=", 15), "battle_deaths_raw": (">=", 10),
}
NEAR_TEXT = {
    "inflation": "Inflation is {v:.1f}%, approaching the 20% warning line.",
    "gdp_growth": "Growth is only {v:.1f}%, close to stalling.",
    "gov_debt": "Public debt is {v:.0f}% of GDP, approaching the 90% warning line.",
    "fiscal_balance": "The budget deficit is {neg:.1f}% of GDP, close to the 5% warning line.",
    "current_account": "The external deficit is {neg:.1f}% of GDP, close to the 5% warning line.",
    "reserves_months": "Reserves cover {v:.1f} months of imports, close to the 3-month warning line.",
    "youth_unemployment": "Youth unemployment is {v:.0f}%, approaching the 25% warning line.",
    "displaced_share": "{v:.1f}% of the population is displaced, approaching the 5% warning line.",
    "homicide": "The homicide rate is {v:.0f} per 100,000, approaching the warning line of 20.",
    "battle_deaths_raw": "{v:,.0f} battle deaths were recorded — below the 25 that defines an active conflict, "
                         "but not zero.",
}

CAVEATS = [
    "Scores are relative: they say where a country sits compared with others, not the probability of any event.",
    "The data look backwards — governance scores describe last year and conflict data lag by up to a year — so "
    "always check current news and official travel advice.",
    "This is general, educational guidance, not investment, legal or security advice.",
]


@dataclass
class Reading:
    iso3: str
    name: str
    tier: str | None
    headline: str
    ground: str
    drivers: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    near: list[str] = field(default_factory=list)
    direction: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    actions: dict[str, list[str]] = field(default_factory=dict)
    caveats: list[str] = field(default_factory=list)


def _compare(op: str, value: float, threshold: float) -> bool:
    return {">=": value >= threshold, "<": value < threshold, "<=": value <= threshold}[op]


def _shown(ind: config.Indicator, raw) -> str:
    """' (32.5%)', ' (69.3% of GDP)', ' (4.4 months of imports)' — or '' when there is no value."""
    if raw is None or pd.isna(raw):
        return ""
    if ind.unit == "% change":
        return f" ({ind.fmt(raw)}%)"
    return f" ({ind.fmt(raw)}{'' if ind.unit.startswith('%') else ' '}{ind.unit})"


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def country_reading(iso3: str, table: pd.DataFrame, values: pd.DataFrame, scores: pd.DataFrame, hist: pd.DataFrame,
                    events: pd.DataFrame, flows: pd.DataFrame | None, year: int) -> Reading:
    """Translate one country's numbers into a plain-language reading with practical actions."""
    row = table.set_index("iso3").loc[iso3]
    name = row["name"]
    v = values.loc[iso3] if iso3 in values.index else pd.Series(dtype=float)
    s = scores.loc[iso3] if iso3 in scores.index else pd.Series(dtype=float)
    tier = s.get("tier") if isinstance(s.get("tier"), str) else None

    if tier is None:
        return Reading(iso3, name, None,
                       f"There is not enough data to score {name}, so no reading can be made from the index.",
                       "Use current news, official travel advice and specialist sources instead.",
                       caveats=CAVEATS)

    # --- Headline ---------------------------------------------------------------------------------------
    summary, ground = TIER_MEANING[tier]
    peers = table[(table["region"] == row["region"]) & table["composite"].notna()].sort_values("composite",
                                                                                               ascending=False)
    region_pos = list(peers["iso3"]).index(iso3) + 1 if iso3 in set(peers["iso3"]) else None
    headline = (f"{name} is in the {tier} tier ({s['composite']:.0f}/100, {_ordinal(int(s['rank']))} riskiest of "
                f"{int(s['n_ranked'])}" + (f"; {_ordinal(region_pos)} of {len(peers)} in {row['region']}" if region_pos
                                           else "") + f"). {summary}")

    # --- Drivers: the high-risk pillars (50+) and the indicators behind them ------------------------------------
    pillars = sorted((p for p in config.PILLARS if pd.notna(s.get(p.key))), key=lambda p: s[p.key], reverse=True)
    drivers = []
    for p in [p for p in pillars if s[p.key] >= 50][:3]:
        inds = sorted((i for i in config.indicators_for(p.key) if pd.notna(s.get(f"n_{i.key}"))),
                      key=lambda i: s[f"n_{i.key}"], reverse=True)
        evidence = [f"{INDICATOR_PHRASE.get(i.key, i.short.lower())}{_shown(i, v.get(i.key))}"
                    for i in inds[:2] if s[f"n_{i.key}"] >= 60]
        drivers.append({"pillar": p.key, "label": p.label, "score": float(s[p.key]),
                        "ground": PILLAR_MEANING[p.key]["ground"], "felt_by": PILLAR_MEANING[p.key]["felt_by"],
                        "evidence": evidence})
    if not drivers and pillars:
        weakest = pillars[0]
        ground += (f" No pillar scores as high risk; the relatively weakest area is {weakest.label} "
                   f"({s[weakest.key]:.0f}/100).")

    # --- Warning signs (red flags) and near misses ---------------------------------------------------------------
    flags = scoring.red_flags(v) if len(v) else []
    warnings = [{"severity": f["severity"], "label": f["label"], "meaning": FLAG_MEANING[f["key"]][0],
                 "response": FLAG_MEANING[f["key"]][1]} for f in flags if f["key"] in FLAG_MEANING]
    flagged = {f["key"] for f in flags}
    near = []
    for key, (op, level) in NEAR.items():
        value = v.get(key)
        if key in flagged or value is None or pd.isna(value):
            continue
        if key == "battle_deaths_raw" and value <= 0:
            continue
        if _compare(op, float(value), level):
            near.append(NEAR_TEXT[key].format(v=float(value), neg=-float(value)))

    # --- Direction -----------------------------------------------------------------------------------------------------
    direction = []
    delta = row.get("delta_1y")
    if pd.notna(delta):
        moved = (f" and moved from the {row['prev_tier']} to the {tier} tier"
                 if isinstance(row.get("prev_tier"), str) and row["prev_tier"] != tier else "")
        if delta >= 3:
            direction.append(f"Getting noticeably riskier: up {delta:+.1f} points since {year - 1}{moved}.")
        elif delta >= 1:
            direction.append(f"Edging riskier: {delta:+.1f} points since {year - 1}{moved}.")
        elif delta <= -3:
            direction.append(f"Getting noticeably safer: {delta:+.1f} points since {year - 1}{moved}.")
        elif delta <= -1:
            direction.append(f"Edging safer: {delta:+.1f} points since {year - 1}{moved}.")
        else:
            direction.append(f"Broadly steady since {year - 1} ({delta:+.1f} points).")
    ch = hist[(hist["iso3"] == iso3)].dropna(subset=["composite"]).sort_values("year")
    if len(ch) >= 3:
        first = ch.iloc[0]
        change = s["composite"] - first["composite"]
        if abs(change) >= 5:
            direction.append(f"Over the longer run it has {'risen' if change > 0 else 'fallen'} from "
                             f"{first['composite']:.0f} in {int(first['year'])} to {s['composite']:.0f} now.")
        else:
            direction.append(f"Over the longer run it has been fairly stable ({first['composite']:.0f} in "
                             f"{int(first['year'])}, {s['composite']:.0f} now).")

    # --- Coming up ---------------------------------------------------------------------------------------------------------
    today = pd.Timestamp.today().normalize()
    upcoming = events[(events["iso3"] == iso3) & (events["date"] >= today)
                      & (events["date"] <= today + pd.Timedelta(days=365))].sort_values("date")
    event_lines = [f"{e.event} — {e.date:%d %b %Y} (in {(e.date - today).days} days, {e.significance} significance)"
                   for e in upcoming.itertuples(index=False)]
    next_event = upcoming.iloc[0] if len(upcoming) else None

    # --- What to do with it --------------------------------------------------------------------------------------------------
    hi = {p.key: pd.notna(s.get(p.key)) and s[p.key] >= 60 for p in config.PILLARS}
    conflict = "battle_deaths_raw" in flagged
    crime = "homicide" in flagged
    money = flagged & {"inflation", "reserves_months", "current_account"}
    budget = flagged & {"gov_debt", "fiscal_balance"}
    displaced = v.get("displaced_share")
    calm = s["composite"] < 30 and not flags
    when = (f"“{next_event['event']}” ({next_event['date']:%d %b %Y})" if next_event is not None else None)

    business = ["Use the score as a screen, not a verdict: compare with peers (Peers tab) and read the drivers "
                "before deciding anything."]
    if hi["economic"] or money:
        business.append("Protect against currency and payment risk: price in hard currency or index to inflation, "
                        "shorten payment terms, consider hedging, and check the rules on moving money out.")
    if "reserves_months" in flagged:
        business.append("Thin reserves often come before import limits or devaluation — hold extra stock of imported "
                        "inputs and convert local earnings promptly.")
    if budget:
        business.append("Expect tax rises, spending cuts or late government payments — check exposure to "
                        "public-sector clients and contracts.")
    if hi["governance"]:
        business.append("Raise due-diligence standards: vet partners and owners, enforce anti-bribery compliance, "
                        "use international arbitration clauses, and consider political-risk insurance.")
    if hi["stability"] or conflict:
        business.append("Plan for disruption: business-continuity and evacuation plans, security for staff and "
                        "sites, and insurance that covers political violence.")
    if hi["social"]:
        business.append("Labour and community relations matter: watch cost-of-living protests and strikes; local "
                        "hiring and engagement reduce friction.")
    if when:
        business.append(f"Treat {when} as a decision window: avoid locking in large, hard-to-reverse commitments "
                        "just before it.")
    if calm:
        business.append("A relatively stable profile: standard due diligence is usually enough — keep an eye on "
                        "*What changed* for early shifts.")

    ngo = []
    if pd.notna(displaced) and displaced >= 1:
        hosts = []
        if flows is not None and not flows.empty:
            names = dict(zip(table["iso3"], table["name"]))
            top = flows[(flows["origin"] == iso3) & flows["host"].isin(names)].nlargest(3, "value")
            hosts = [names[h] for h in top["host"]]
        ngo.append(f"About {displaced:.1f}% of the population is displaced: plan for shelter, protection, food and "
                   "health needs through UN-led coordination (OCHA, UNHCR)."
                   + (f" The largest numbers abroad are in {', '.join(hosts[:-1])} and {hosts[-1]}." if len(hosts) > 1
                      else f" The largest number abroad is in {hosts[0]}." if hosts else ""))
    if conflict or hi["stability"]:
        ngo.append("Access and safety come first: negotiate access, apply humanitarian principles, and keep a "
                   "security risk-management plan and duty of care for staff.")
    if "inflation" in flagged:
        ngo.append("Fast-rising prices erode the value of cash and voucher assistance — index transfers to local "
                   "prices and monitor markets.")
    if hi["governance"]:
        ngo.append("Expect bureaucratic hurdles and diversion risk — strengthen financial controls, partner "
                   "vetting and accountability to affected people.")
    if when:
        ngo.append(f"Movement and access may tighten around {when} — adjust field schedules and communications.")
    if not ngo or calm:
        ngo.append("A development rather than an emergency context: focus on long-term programming, resilience "
                   "and local partnerships.")

    travel = [f"Check your government's official travel advice for {name} before going — it is updated far faster "
              "than annual data."]
    if conflict:
        travel.append("There is active armed conflict: many governments advise against all or non-essential travel "
                      "to the affected regions.")
    if crime or hi["stability"]:
        travel.append("Higher violence and crime: avoid travelling at night, use trusted transport, keep a low "
                      "profile and share your itinerary.")
    if hi["social"] or when:
        travel.append("Stay away from demonstrations" + (f", especially around {when}" if when else "")
                      + " — protests can turn violent quickly.")
    if money:
        travel.append("Bring more than one way to pay: cash shortages, card problems and fast-changing prices are "
                      "possible.")
    if calm:
        travel.append("Generally stable: normal precautions apply.")

    research = []
    top = [d["label"] for d in drivers[:2]]
    if top:
        research.append(f"Start with the drivers: {' and '.join(top)} {'carry' if len(top) > 1 else 'carries'} the "
                        "most risk — explain why.")
    elif pillars:
        research.append(f"No pillar is high risk; ask what keeps {name} stable and what could change that — the "
                        f"relatively weakest area is {pillars[0].label}.")
    if region_pos:
        research.append(f"Put it in context: {name} ranks {_ordinal(region_pos)} of {len(peers)} in {row['region']} "
                        "— the Peers tab shows who is close.")
    research.append("Check whether changes are real: governance moves inside the WGI confidence intervals may be "
                    "noise (Governance trends tab).")
    research.append("Test what matters: the What-if simulator shows which indicators would move the score most.")
    research.append("Write it up: the Assessment builder turns this into a structured brief with probabilities.")

    caveats = list(CAVEATS)
    if pd.notna(s.get("coverage")) and s["coverage"] < 75:
        caveats.insert(0, f"Only {s['coverage']:.0f}% of the indicators are available for {name}: treat this "
                          "reading with extra caution.")

    return Reading(iso3, name, tier, headline, ground, drivers, warnings, near, direction, event_lines,
                   {"business": business, "ngo": ngo, "travel": travel, "research": research}, caveats)


def reading_markdown(r: Reading) -> str:
    """The reading as a Markdown brief (for download)."""
    out = [f"# {r.name} — what the data means in real life", "", r.headline, "", "## On the ground", "", r.ground, ""]
    for d in r.drivers:
        out.append(f"- **{d['label']} ({d['score']:.0f}/100):** {d['ground']} *Felt by:* {d['felt_by']}"
                   + (f" Evidence: {'; '.join(d['evidence'])}." if d["evidence"] else ""))
    if r.warnings:
        out += ["", "## Warning signs right now", ""]
        for w in r.warnings:
            out.append(f"- **{w['label']}.** {w['meaning']} *Typical response:* {w['response']}")
    if r.near:
        out += ["", "## Close to a red line", ""] + [f"- {n}" for n in r.near]
    if r.direction:
        out += ["", "## Direction", ""] + [f"- {d}" for d in r.direction]
    if r.events:
        out += ["", "## Coming up", ""] + [f"- {e}" for e in r.events]
    for key, label in AUDIENCES.items():
        if r.actions.get(key):
            out += ["", f"## What to do — {label[2:]}", ""] + [f"- {a}" for a in r.actions[key]]
    out += ["", "---", ""] + [f"*{c}*" for c in r.caveats]
    return "\n".join(out) + "\n"
