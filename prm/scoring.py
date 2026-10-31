"""The risk index: picking the latest values, normalising, aggregating, flagging.

Method in one paragraph
-----------------------
For every country we take the most recent value of each indicator (within a
look-back window). Each indicator is turned into a 0-100 risk score, where 100
is the riskiest country in the sample: most indicators use a percentile rank;
zero-heavy indicators (battle deaths, displacement) use a log scale so that
"no conflict" scores 0. Indicator scores are averaged into four pillars, and the
pillars are combined with user-adjustable weights into the composite index.
The index is *relative*: it says where a country sits compared with others,
not an absolute probability of crisis.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import config
from .config import INDICATORS, PILLARS, SCORED_INDICATORS, TIERS


# ---------------------------------------------------------------------------
# Selecting values
# ---------------------------------------------------------------------------
def pick_latest(df: pd.DataFrame | None, max_year: int, lookback: int) -> tuple[pd.Series, pd.Series]:
    """Most recent non-missing value per country within [max_year - lookback, max_year]."""
    if df is None or df.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    window = df[(df["year"] <= max_year) & (df["year"] >= max_year - lookback)].dropna(subset=["value"])
    if window.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    latest = window.sort_values("year").groupby("iso3").tail(1).set_index("iso3")
    return latest["value"].astype(float), latest["year"].astype(float)


def _population(series: dict[str, pd.DataFrame], index: pd.Index, year: int) -> pd.Series:
    """Population for a given year: World Bank first, IMF (millions) as fallback."""
    wb, _ = pick_latest(series.get("pop"), year, 3)
    imf, _ = pick_latest(series.get("pop_imf"), year, 3)
    pop = wb.reindex(index)
    return pop.fillna((imf * 1_000_000).reindex(index))


def build_values(series: dict[str, pd.DataFrame], countries: pd.DataFrame, year: int) -> pd.DataFrame:
    """Wide table: one row per country, one column per indicator (+ '__year' columns and context)."""
    index = pd.Index(countries["iso3"], name="iso3")
    out = pd.DataFrame(index=index)

    for ind in INDICATORS:
        if ind.series:
            values, years = pick_latest(series.get(ind.series), year, ind.lookback)
            values, years = values.reindex(index), years.reindex(index)
            if ind.fallback_series:
                fb_values, fb_years = pick_latest(series.get(ind.fallback_series), year, ind.lookback)
                missing = values.isna()
                values = values.where(~missing, fb_values.reindex(index))
                years = years.where(~missing, fb_years.reindex(index))
            out[ind.key] = values
            out[f"{ind.key}__year"] = years

    # Battle deaths: UCDP records every conflict, so "no record" means zero deaths.
    bd = series.get("battle_deaths")
    if bd is not None and not bd.empty:
        bd = bd[bd["year"] <= year].dropna(subset=["value"])
    if bd is not None and not bd.empty:
        bd_year = int(bd["year"].max())
        raw = bd[bd["year"] == bd_year].set_index("iso3")["value"].reindex(index).fillna(0.0)
        pop = _population(series, index, bd_year)
        out["battle_deaths_raw"] = raw
        out["battle_deaths_100k"] = (raw / pop * 100_000).where(pop > 0)
        out["battle_deaths_100k__year"] = float(bd_year)
    else:
        out["battle_deaths_raw"] = np.nan
        out["battle_deaths_100k"] = np.nan
        out["battle_deaths_100k__year"] = np.nan

    # Displacement as a share of population (UNHCR, latest published year up to `year`)
    dp = series.get("displaced")
    if dp is not None and not dp.empty:
        dp = dp[dp["year"] <= year]
    if dp is not None and not dp.empty:
        dp_year = int(dp["year"].max())
        total = dp[dp["year"] == dp_year].set_index("iso3")["value"].reindex(index).fillna(0.0)
        pop = _population(series, index, dp_year)
        out["displaced_total"] = total
        out["displaced_share"] = (total / pop * 100).where(pop > 0)
        out["displaced_share__year"] = float(dp_year)
    else:
        out["displaced_total"] = np.nan
        out["displaced_share"] = np.nan
        out["displaced_share__year"] = np.nan

    # Context (not scored)
    out["population"] = _population(series, index, year)
    gdppc, gdppc_year = pick_latest(series.get("gdppc"), year, 2)
    out["gdppc"] = gdppc.reindex(index)
    out["gdppc__year"] = gdppc_year.reindex(index)
    return out


# ---------------------------------------------------------------------------
# Normalising and aggregating
# ---------------------------------------------------------------------------
def normalise(values: pd.Series, higher_is_riskier: bool, method: str = "percentile") -> pd.Series:
    """Convert raw values to a 0-100 risk score (100 = riskiest)."""
    s = pd.to_numeric(values, errors="coerce").astype(float)
    valid = s.dropna()
    if len(valid) < 2:
        return pd.Series(np.nan, index=s.index)
    if method == "log":
        x = np.log1p(valid.clip(lower=0))
        positive = x[x > 0]
        cap = float(positive.quantile(config.LOG_CAP_QUANTILE)) if len(positive) else 0.0
        scored = (x / cap * 100).clip(upper=100) if cap > 0 else x * 0
        if not higher_is_riskier:
            scored = 100 - scored
    else:
        ranks = valid.rank(ascending=higher_is_riskier, method="min")
        scored = (ranks - 1) / (len(valid) - 1) * 100
    return scored.reindex(s.index)


def normalise_against(values: pd.Series, reference: pd.Series, higher_is_riskier: bool,
                      method: str = "percentile") -> pd.Series:
    """Like normalise, but every value is scored against a fixed reference distribution (today's values), so a
    shock that hits all countries alike still shows. With reference = values it gives exactly normalise's result."""
    s = pd.to_numeric(values, errors="coerce").astype(float)
    ref = pd.to_numeric(reference, errors="coerce").astype(float).dropna()
    if len(ref) < 2:
        return pd.Series(np.nan, index=s.index)
    if method == "log":
        x_ref = np.log1p(ref.clip(lower=0))
        positive = x_ref[x_ref > 0]
        cap = float(positive.quantile(config.LOG_CAP_QUANTILE)) if len(positive) else 0.0
        x = np.log1p(s.clip(lower=0))
        scored = (x / cap * 100).clip(upper=100) if cap > 0 else x * 0
        return scored if higher_is_riskier else 100 - scored
    ordered = np.sort(ref.to_numpy())
    v = s.to_numpy()
    # "min" ranks: the share of the reference that is strictly less risky
    less_risky = np.searchsorted(ordered, v, side="left") if higher_is_riskier \
        else len(ordered) - np.searchsorted(ordered, v, side="right")
    scored = np.clip(less_risky / (len(ordered) - 1) * 100, 0, 100)
    return pd.Series(np.where(np.isnan(v), np.nan, scored), index=s.index)


def tier_for(score: float) -> str | None:
    if score is None or (isinstance(score, float) and math.isnan(score)):
        return None
    label = TIERS[0].label
    for tier in TIERS:
        if score >= tier.lower:
            label = tier.label
    return label


def default_weights() -> dict[str, float]:
    return {p.key: float(p.default_weight) for p in PILLARS}


def compute_scores(values: pd.DataFrame, weights: dict[str, float] | None = None,
                   reference: pd.DataFrame | None = None) -> pd.DataFrame:
    """Indicator scores (n_*), pillar scores, composite, tier, rank and coverage.

    `reference`: score the values against this table's distribution instead of their own (the stress test).
    """
    weights = dict(weights or default_weights())
    if sum(max(w, 0) for w in weights.values()) <= 0:
        weights = default_weights()

    def column(frame: pd.DataFrame, key: str) -> pd.Series:
        return frame[key] if key in frame else pd.Series(np.nan, index=frame.index)

    scores = pd.DataFrame(index=values.index)
    for ind in SCORED_INDICATORS:
        if reference is None:
            scores[f"n_{ind.key}"] = normalise(column(values, ind.key), ind.higher_is_riskier, ind.norm)
        else:
            scores[f"n_{ind.key}"] = normalise_against(column(values, ind.key), column(reference, ind.key),
                                                       ind.higher_is_riskier, ind.norm)

    for pillar in PILLARS:
        cols = [f"n_{i.key}" for i in config.indicators_for(pillar.key)]
        block = scores[cols]
        needed = max(1, math.ceil(len(cols) * config.PILLAR_MIN_SHARE))
        pillar_score = block.mean(axis=1, skipna=True)
        scores[pillar.key] = pillar_score.where(block.notna().sum(axis=1) >= needed)

    pillar_keys = [p.key for p in PILLARS]
    pillar_block = scores[pillar_keys]
    w = pd.Series({k: max(float(weights.get(k, 0)), 0.0) for k in pillar_keys})
    available = pillar_block.notna()
    weight_matrix = available.astype(float).mul(w, axis=1)
    weight_sum = weight_matrix.sum(axis=1)
    composite = (pillar_block.fillna(0) * weight_matrix).sum(axis=1) / weight_sum.where(weight_sum > 0)
    enough = available.sum(axis=1) >= config.COMPOSITE_MIN_PILLARS
    scores["composite"] = composite.where(enough)

    n_cols = [f"n_{i.key}" for i in SCORED_INDICATORS]
    scores["coverage"] = scores[n_cols].notna().sum(axis=1) / len(n_cols) * 100
    scores["tier"] = scores["composite"].map(tier_for)
    scores["rank"] = scores["composite"].rank(ascending=False, method="min")
    scores["n_ranked"] = int(scores["composite"].notna().sum())
    return scores


def build_history(series: dict[str, pd.DataFrame], countries: pd.DataFrame, weights: dict[str, float],
                  years: range) -> pd.DataFrame:
    """The index recomputed for every year: one row per country-year (composite, pillars, tier, rank).

    Each year is scored only against data available up to that year, and relative to the other
    countries that year — so a rising score means a country moved up the risk ranking.
    """
    pillar_keys = [p.key for p in PILLARS]
    frames = []
    for year in years:
        values = build_values(series, countries, year)
        scores = compute_scores(values, weights)
        frame = scores[["composite", *pillar_keys, "tier", "rank", "n_ranked"]].assign(
            year=year, battle_deaths_raw=values["battle_deaths_raw"]
        )
        frames.append(frame.reset_index())
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Flags, trends and the automatic brief
# ---------------------------------------------------------------------------
_OPS = {
    ">=": lambda a, b: a >= b,
    ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b,
    "<": lambda a, b: a < b,
}


def red_flags(row: pd.Series) -> list[dict]:
    """Absolute-threshold warnings for one country (most severe per indicator only)."""
    flags, seen = [], set()
    for key, op, threshold, severity, label in config.RED_FLAGS:
        if key in seen:
            continue
        value = row.get(key)
        if value is None or pd.isna(value):
            continue
        if _OPS[op](float(value), threshold):
            seen.add(key)
            flags.append({"key": key, "severity": severity, "label": label, "value": float(value),
                          "short": config.FLAG_SHORT.get((key, threshold), label)})
    flags.sort(key=lambda f: config.SEVERITY_ORDER[f["severity"]])
    return flags


def flag_counts(values: pd.DataFrame) -> pd.Series:
    """Number of red flags per country (for tables)."""
    return values.apply(lambda row: len(red_flags(row)), axis=1)


def wgi_trend(series: dict[str, pd.DataFrame], iso3: str, dim: str = "pv", years: int | None = None) -> dict | None:
    """Change in a WGI score over the trend window for one country."""
    years = years or config.WGI_TREND_YEARS
    df = series.get(f"wgi_{dim}")
    if df is None or df.empty:
        return None
    s = df[df["iso3"] == iso3].set_index("year")["value"].sort_index()
    if s.empty:
        return None
    end_year = int(s.index.max())
    start_year = end_year - years
    if start_year not in s.index:
        return None
    return {
        "dim": dim,
        "start_year": start_year,
        "end_year": end_year,
        "start": float(s.loc[start_year]),
        "end": float(s.loc[end_year]),
        "change": float(s.loc[end_year] - s.loc[start_year]),
    }


def wgi_changes(series: dict[str, pd.DataFrame], countries: pd.DataFrame, dim: str = "pv", years: int | None = None) -> pd.DataFrame:
    """Change in a WGI dimension over the trend window for all countries (for the movers table)."""
    years = years or config.WGI_TREND_YEARS
    df = series.get(f"wgi_{dim}")
    if df is None or df.empty:
        return pd.DataFrame(columns=["iso3", "start", "end", "change", "start_year", "end_year"])
    end_year = int(df["year"].max())
    start_year = end_year - years
    wide = df[df["year"].isin([start_year, end_year])].pivot_table(index="iso3", columns="year", values="value")
    if start_year not in wide.columns or end_year not in wide.columns:
        return pd.DataFrame(columns=["iso3", "start", "end", "change", "start_year", "end_year"])
    out = pd.DataFrame(
        {"start": wide[start_year], "end": wide[end_year], "change": wide[end_year] - wide[start_year]}
    ).dropna()
    out["start_year"], out["end_year"] = start_year, end_year
    out = out.reset_index()
    return out[out["iso3"].isin(countries["iso3"])]


def ci_overlap(series: dict[str, pd.DataFrame], ci: dict[str, pd.DataFrame], iso3: str, dim: str, y0: int, y1: int) -> bool | None:
    """True if the 90% confidence intervals of two years overlap (change not statistically clear)."""
    lb, ub = ci.get(f"wgi_{dim}_lb"), ci.get(f"wgi_{dim}_ub")
    if lb is None or ub is None or lb.empty or ub.empty:
        return None

    def _get(df, year):
        hit = df[(df["iso3"] == iso3) & (df["year"] == year)]["value"]
        return float(hit.iloc[0]) if len(hit) else None

    lb0, ub0, lb1, ub1 = _get(lb, y0), _get(ub, y0), _get(lb, y1), _get(ub, y1)
    if None in (lb0, ub0, lb1, ub1):
        return None
    return not (ub1 < lb0 or ub0 < lb1)


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def country_brief(
    iso3: str,
    name: str,
    values: pd.DataFrame,
    scores: pd.DataFrame,
    series: dict[str, pd.DataFrame],
    countries: pd.DataFrame,
    year: int,
) -> list[str]:
    """Plain-English, data-only observations for one country. No judgments are invented."""
    lines: list[str] = []
    if iso3 not in scores.index:
        return lines
    s, v = scores.loc[iso3], values.loc[iso3]

    if pd.notna(s["composite"]):
        lines.append(
            f"{name} ranks {_ordinal(int(s['rank']))} of {int(s['n_ranked'])} countries on the composite "
            f"index (score {s['composite']:.0f}/100, {s['tier']} tier; 1st = highest risk)."
        )
        region = countries.set_index("iso3").loc[iso3, "region"]
        peers = countries[countries["region"] == region]["iso3"]
        peer_scores = scores.loc[scores.index.intersection(peers), "composite"].dropna()
        if len(peer_scores) > 1:
            peer_rank = int((peer_scores > s["composite"]).sum()) + 1
            lines.append(
                f"Within {region} it is {_ordinal(peer_rank)} of {len(peer_scores)} "
                f"(regional median {peer_scores.median():.0f})."
            )
    else:
        lines.append(f"There is not enough data to compute a composite score for {name}.")

    pillar_scores = {p.short: s[p.key] for p in PILLARS if pd.notna(s[p.key])}
    if len(pillar_scores) >= 2:
        worst = max(pillar_scores, key=pillar_scores.get)
        best = min(pillar_scores, key=pillar_scores.get)
        lines.append(
            f"Highest-risk pillar: {worst} ({pillar_scores[worst]:.0f}); "
            f"lowest-risk pillar: {best} ({pillar_scores[best]:.0f})."
        )

    trend = wgi_trend(series, iso3, "pv")
    if trend:
        direction = "improved" if trend["change"] > 0 else "deteriorated" if trend["change"] < 0 else "was unchanged"
        lines.append(
            f"Political stability (World Bank governance indicators) {direction} from {trend['start']:.1f} "
            f"({trend['start_year']}) to "
            f"{trend['end']:.1f} ({trend['end_year']}), a change of {trend['change']:+.1f} points."
        )

    growth, infl = v.get("gdp_growth"), v.get("inflation")
    nxt = _next_year_value(series, "gdp_growth", iso3, year + 1)
    if pd.notna(growth) and pd.notna(infl):
        gy, iy = int(v["gdp_growth__year"]), int(v["inflation__year"])
        if gy == iy == year:
            text = f"The IMF projects real GDP growth of {growth:.1f}% and inflation of {infl:.1f}% for {year}"
        else:  # the IMF has stopped publishing current figures for a few countries (e.g. Afghanistan, Lebanon)
            text = (f"The latest IMF figures, for {gy}, show real GDP growth of {growth:.1f}% and inflation of {infl:.1f}%"
                    if gy == iy else f"The latest IMF figures show real GDP growth of {growth:.1f}% ({gy}) "
                    f"and inflation of {infl:.1f}% ({iy})")
        if nxt is not None:
            text += f", with growth of {nxt:.1f}% in {year + 1}"
        lines.append(text + ".")

    raw_bd = v.get("battle_deaths_raw")
    bd_year = v.get("battle_deaths_100k__year")
    if pd.notna(raw_bd) and pd.notna(bd_year):
        if raw_bd > 0:
            lines.append(f"UCDP recorded {raw_bd:,.0f} battle-related deaths in {int(bd_year)}.")
        else:
            lines.append(f"No battle-related deaths from state-based conflict were recorded in {int(bd_year)}.")

    share = v.get("displaced_share")
    if pd.notna(share) and share >= 0.5:
        lines.append(
            f"About {v['displaced_total']:,.0f} people ({share:.1f}% of the population) from {name} were "
            f"forcibly displaced in {int(v['displaced_share__year'])} (UNHCR)."
        )

    cov = s.get("coverage")
    if pd.notna(cov) and cov < 75:
        lines.append(f"Only {cov:.0f}% of indicators are available, so treat the score with caution.")
    return lines


def _next_year_value(series: dict[str, pd.DataFrame], key: str, iso3: str, year: int) -> float | None:
    df = series.get(key)
    if df is None or df.empty:
        return None
    hit = df[(df["iso3"] == iso3) & (df["year"] == year)]["value"]
    return float(hit.iloc[0]) if len(hit) else None


def simulate(values: pd.DataFrame, iso3: str, changes: dict[str, float], weights: dict[str, float]) -> tuple[pd.DataFrame, pd.Series]:
    """What-if: change some of one country's raw values and re-score everyone.

    All countries are re-normalised, so the result is exactly what the index would show
    if those values were real. Returns (scores for all countries, the country's new values).
    """
    scenario = values.copy()
    for key, value in changes.items():
        scenario.loc[iso3, key] = value
    return compute_scores(scenario, weights), scenario.loc[iso3]


def sensitivity(values: pd.DataFrame, iso3: str, weights: dict[str, float]) -> pd.DataFrame:
    """How the country's rank changes if each pillar's weight is set to zero (robustness check)."""
    base = compute_scores(values, weights)
    rows = [{"Scenario": "Your weights", "Score": base.loc[iso3, "composite"], "Rank": base.loc[iso3, "rank"]}]
    equal = {p.key: 25.0 for p in PILLARS}
    eq = compute_scores(values, equal)
    rows.append({"Scenario": "Equal weights", "Score": eq.loc[iso3, "composite"], "Rank": eq.loc[iso3, "rank"]})
    for p in PILLARS:
        alt = dict(weights)
        alt[p.key] = 0.0
        if sum(alt.values()) <= 0:
            continue
        sc = compute_scores(values, alt)
        rows.append(
            {"Scenario": f"Without {p.short}", "Score": sc.loc[iso3, "composite"], "Rank": sc.loc[iso3, "rank"]}
        )
    return pd.DataFrame(rows)


def similar(scores: pd.DataFrame, iso3: str, n: int = 6) -> pd.DataFrame:
    """The countries whose four pillar scores are closest to this one's (Euclidean distance, 0 = identical profile)."""
    keys = [p.key for p in PILLARS]
    block = scores[keys].dropna()
    if iso3 not in block.index:
        return pd.DataFrame(columns=["distance"])
    gap = ((block - block.loc[iso3]) ** 2).sum(axis=1) ** 0.5
    return gap.drop(iso3).nsmallest(n).rename("distance").to_frame()
