"""Stress test: apply one economic shock to many countries at once and see who crosses a risk tier or a red flag.

Shocked countries are scored against today's distribution (the yardstick stays fixed). Re-ranking everyone against
each other would hide a shock that hits all countries alike, since percentile ranks would barely move.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config, scoring


@dataclass(frozen=True)
class Shock:
    key: str  # indicator column in the values table
    label: str
    unit: str
    low: float
    high: float
    step: float
    relative: bool = False  # True: a % change of the value; False: added to it

    def apply(self, values: pd.Series, size: float) -> pd.Series:
        out = values * (1 + size / 100) if self.relative else values + size
        if self.key in {"unemployment", "youth_unemployment"}:
            return out.clip(0, 100)
        return out.clip(lower=0) if self.key in {"gov_debt", "reserves_months"} else out


SHOCKS: list[Shock] = [
    Shock("gdp_growth", "GDP growth", "points", -8.0, 4.0, 0.5),
    Shock("inflation", "Inflation", "points", -5.0, 30.0, 1.0),
    Shock("gov_debt", "Public debt", "points of GDP", -10.0, 40.0, 1.0),
    Shock("fiscal_balance", "Fiscal balance", "points of GDP", -8.0, 3.0, 0.5),
    Shock("current_account", "Current account", "points of GDP", -6.0, 3.0, 0.5),
    Shock("reserves_months", "FX reserves", "% change", -60.0, 30.0, 5.0, relative=True),
    Shock("unemployment", "Unemployment", "points", -2.0, 8.0, 0.5),
    Shock("youth_unemployment", "Youth unemployment", "points", -4.0, 16.0, 1.0),
]
SHOCK_BY_KEY = {s.key: s for s in SHOCKS}

# Round-number versions of past world-wide shocks, to start from (move the sliders to your own view)
SCENARIOS: dict[str, dict[str, float]] = {
    "Global recession (like 2009)": {"gdp_growth": -4.0, "gov_debt": 10.0, "fiscal_balance": -3.0,
                                     "reserves_months": -10.0, "unemployment": 1.5, "youth_unemployment": 3.0},
    "Pandemic shock (like 2020)": {"gdp_growth": -5.5, "gov_debt": 14.0, "fiscal_balance": -6.0,
                                   "unemployment": 1.5, "youth_unemployment": 3.0},
    "Price surge (like 2022)": {"inflation": 5.0, "gdp_growth": -1.0, "current_account": -1.0,
                                "reserves_months": -10.0},
    "Higher-for-longer rates": {"gdp_growth": -1.0, "gov_debt": 5.0, "fiscal_balance": -1.5,
                                "reserves_months": -20.0},
}


def _flags(row: pd.Series) -> dict[str, dict]:
    return {f["key"]: f for f in scoring.red_flags(row)}


def run(values: pd.DataFrame, weights: dict[str, float], shocks: dict[str, float],
        scope: set[str] | None = None) -> pd.DataFrame:
    """Shock the countries in `scope` (all if None) and re-score everyone against today's values.

    One row per country: scores and tiers today and under stress, the change, and new or worse red flags.
    """
    shocks = {k: v for k, v in shocks.items() if k in SHOCK_BY_KEY and v}
    hit = pd.Series(True, index=values.index) if scope is None else values.index.to_series().isin(scope)
    shocked = values.copy()
    for key, size in shocks.items():
        if key in shocked:
            shocked.loc[hit, key] = SHOCK_BY_KEY[key].apply(shocked.loc[hit, key], size)

    before = scoring.compute_scores(values, weights)
    after = scoring.compute_scores(shocked, weights, reference=values)
    out = pd.DataFrame(index=values.index)
    out["hit"] = hit
    for col in ["composite", "economic", "social", "tier"]:
        out[f"{col}_before"], out[f"{col}_after"] = before[col], after[col]
    out["delta"] = out["composite_after"] - out["composite_before"]
    order = {t: i for i, t in enumerate(config.TIER_ORDER)}
    out["tier_move"] = out["tier_after"].map(order) - out["tier_before"].map(order)

    rank = config.SEVERITY_ORDER
    new_flags, flags_before, flags_after = [], [], []
    for iso3 in values.index:
        was = _flags(values.loc[iso3]) if hit.loc[iso3] else None
        now = _flags(shocked.loc[iso3]) if hit.loc[iso3] else None
        if was is None:
            new_flags.append([])
            n = len(scoring.red_flags(values.loc[iso3]))
            flags_before.append(n)
            flags_after.append(n)
            continue
        worse = [f for k, f in now.items() if k not in was or rank[f["severity"]] < rank[was[k]["severity"]]]
        new_flags.append([f"{f['short']} ({config.SEVERITY_LABEL[f['severity']].lower()})" for f in
                          sorted(worse, key=lambda f: rank[f["severity"]])])
        flags_before.append(len(was))
        flags_after.append(len(now))
    out["flags_before"], out["flags_after"] = flags_before, flags_after
    out["new_flags"] = new_flags
    out["new_flag_count"] = out["new_flags"].map(len)
    return out


def summary(result: pd.DataFrame) -> dict:
    """Headline numbers for the countries hit by the shock."""
    hit = result[result["hit"] & result["composite_before"].notna()]
    severe = config.TIER_ORDER[-1]
    return {
        "countries": int(len(hit)),
        "tier_up": int((hit["tier_move"] > 0).sum()),
        "tier_down": int((hit["tier_move"] < 0).sum()),
        "new_flags": int(hit["new_flag_count"].sum()),
        "with_new_flags": int((hit["new_flag_count"] > 0).sum()),
        "mean_delta": float(hit["delta"].mean()) if len(hit) else float("nan"),
        "severe_before": int((hit["tier_before"] == severe).sum()),
        "severe_after": int((hit["tier_after"] == severe).sum()),
    }


def encode(shocks: dict[str, float]) -> str:
    """Shocks as a short text for a shareable link, e.g. 'gdp_growth:-4,gov_debt:10'."""
    return ",".join(f"{k}:{v:g}" for k, v in shocks.items() if k in SHOCK_BY_KEY and v)


def decode(text: str | None) -> dict[str, float]:
    out = {}
    for part in (text or "").split(","):
        key, _, raw = part.partition(":")
        shock = SHOCK_BY_KEY.get(key.strip())
        try:
            value = float(raw)
        except ValueError:
            continue
        if shock and np.isfinite(value):
            out[shock.key] = float(np.clip(round(value / shock.step) * shock.step, shock.low, shock.high))
    return out
