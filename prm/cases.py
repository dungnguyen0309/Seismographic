"""Case studies: what the index said the year before major political shocks.

The verdict is mechanical and uses only the index for the year before the event, so it can be checked:
- Flagged: High or Severe tier, or among the 25 riskiest economies.
- Partly flagged: Elevated tier, among the 50 riskiest, or 5+ points riskier over the three years before.
- Missed: none of these.
An analyst's commentary can be added as case_studies/<key>.md (Markdown); it is shown under the data.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import config, scoring

COMMENTARY_DIR = Path(__file__).resolve().parent.parent / "case_studies"


@dataclass(frozen=True)
class Case:
    key: str
    iso3: str
    date: str  # YYYY-MM-DD
    kind: str
    title: str
    what: str
    source: str  # background reading


CASES: list[Case] = [
    Case("ethiopia-2020", "ETH", "2020-11-04", "War", "War in Tigray",
         "Fighting broke out between the federal government and the Tigray People's Liberation Front, starting a "
         "two-year war.", "https://en.wikipedia.org/wiki/Tigray_war"),
    Case("myanmar-2021", "MMR", "2021-02-01", "Coup", "Military coup",
         "The military seized power and detained the elected leaders, including Aung San Suu Kyi, on the day the "
         "new parliament was due to sit.", "https://en.wikipedia.org/wiki/2021_Myanmar_coup_d%27%C3%A9tat"),
    Case("afghanistan-2021", "AFG", "2021-08-15", "Collapse of government", "Taliban takeover",
         "The Taliban entered Kabul and the elected government collapsed as foreign forces withdrew.",
         "https://en.wikipedia.org/wiki/Fall_of_Kabul_(2021)"),
    Case("ukraine-2022", "UKR", "2022-02-24", "Invasion", "Full-scale Russian invasion",
         "Russia launched a full-scale invasion of Ukraine.", "https://en.wikipedia.org/wiki/Russian_invasion_of_Ukraine"),
    Case("sri-lanka-2022", "LKA", "2022-04-12", "Economic collapse", "Default and mass protests",
         "Sri Lanka stopped paying its foreign debt amid fuel and food shortages; months of mass protests forced the "
         "president to resign in July.",
         "https://en.wikipedia.org/wiki/Sri_Lankan_economic_crisis_(2019%E2%80%932024)"),
    Case("sudan-2023", "SDN", "2023-04-15", "War", "Civil war",
         "Fighting broke out in Khartoum between the army and the Rapid Support Forces and spread into a nationwide "
         "war.", "https://en.wikipedia.org/wiki/Sudanese_civil_war_(2023%E2%80%93present)"),
    Case("niger-2023", "NER", "2023-07-26", "Coup", "Military coup",
         "Members of the presidential guard detained President Mohamed Bazoum and the military took power.",
         "https://en.wikipedia.org/wiki/2023_Nigerien_coup_d%27%C3%A9tat"),
    Case("bangladesh-2024", "BGD", "2024-08-05", "Uprising", "Student-led uprising",
         "Weeks of student-led protests, met with a deadly crackdown, forced Prime Minister Sheikh Hasina to resign "
         "and leave the country.", "https://en.wikipedia.org/wiki/July_Uprising"),
]
VERDICTS = {  # label -> (colour, meaning)
    "Flagged": ("#fd8078", "High or Severe tier, or among the 25 riskiest countries, the year before."),
    "Partly flagged": ("#e0a458", "Elevated tier, among the 50 riskiest, or 5+ points riskier over the three years before."),
    "Missed": ("#898781", "The index did not single the country out the year before."),
}


def reading(case: Case, hist: pd.DataFrame, values_before: pd.DataFrame) -> dict:
    """What the index showed the year before the event, and the verdict."""
    before = int(case.date[:4]) - 1
    rows = hist[hist["iso3"] == case.iso3].set_index("year").sort_index()
    if before not in rows.index or pd.isna(rows.loc[before, "composite"]):
        return {"before": before, "verdict": None}
    r = rows.loc[before]
    start = rows["composite"].get(before - 3)
    change = None if start is None or pd.isna(start) else float(r["composite"] - start)
    pillar_moves = {}
    if before - 3 in rows.index:
        for p in config.PILLARS:
            a, b = rows.loc[before - 3, p.key], r[p.key]
            if pd.notna(a) and pd.notna(b):
                pillar_moves[p.short] = float(b - a)
    flags = scoring.red_flags(values_before.loc[case.iso3]) if case.iso3 in values_before.index else []
    rank, n = int(r["rank"]), int(r["n_ranked"])
    if r["tier"] in ("High", "Severe") or rank <= 25:
        verdict = "Flagged"
    elif r["tier"] == "Elevated" or rank <= 50 or (change is not None and change >= 5):
        verdict = "Partly flagged"
    else:
        verdict = "Missed"
    return {"before": before, "score": float(r["composite"]), "tier": r["tier"], "rank": rank, "n": n,
            "change": change, "pillars": {p.short: (None if pd.isna(r[p.key]) else float(r[p.key])) for p in config.PILLARS},
            "pillar_moves": pillar_moves, "flags": flags, "verdict": verdict}


def commentary(case: Case) -> str | None:
    path = COMMENTARY_DIR / f"{case.key}.md"
    return path.read_text(encoding="utf-8") if path.exists() else None
