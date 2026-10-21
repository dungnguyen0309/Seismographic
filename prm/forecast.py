"""Conflict outlook: the chance that armed conflict breaks out next year in a country at peace this year.

A small, transparent statistical model (logistic regression with a light penalty, fitted with numpy) on
- the four pillar scores of the index (they do not depend on the user's weights),
- low-level violence this year (battle deaths below the 25-death conflict line, log scale),
- whether the country had an armed conflict in any of the previous five years (the strongest known predictor).

It is tested the honest way: for each test year the model is fitted only on earlier years ("out of time"), then
its predictions for that year are compared with what happened. Conflict data come from UCDP via the World Bank.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config, validation

CONFLICT = validation.CONFLICT_DEATHS
FEATURES = ["stability", "governance", "economic", "social", "violence", "recent_conflict"]
FEATURE_LABELS = {
    "stability": "Stability pillar", "governance": "Governance pillar", "economic": "Economy pillar",
    "social": "Social pillar", "violence": "Low-level violence this year", "recent_conflict": "Conflict in the past 5 years",
}
# Ridge penalty on the standardised coefficients. With few events an unpenalised fit is overconfident; 25 gave the
# best-calibrated out-of-time predictions (Brier skill +0.12, top fifth 10.7% predicted vs 10.5% observed, Oct 2026)
PENALTY = 25.0
MIN_TRAIN_YEARS = 4


@dataclass
class Outlook:
    predictions: pd.DataFrame  # iso3, probability, relative (x the average), status
    base_rate: float
    coefficients: pd.Series  # per standardised feature (log-odds per standard deviation)
    backtest: pd.DataFrame  # out-of-time predictions: iso3, year, probability, onset
    auc: float | None
    brier_skill: float | None
    calibration: pd.DataFrame  # predicted vs observed by fifth
    data_year: int  # last year of conflict data
    index_year: int
    notes: list[str] = field(default_factory=list)


def _deaths(battle_deaths: pd.DataFrame) -> pd.DataFrame:
    return battle_deaths.pivot_table(index="iso3", columns="year", values="value", aggfunc="first").fillna(0.0)


def panel(hist: pd.DataFrame, battle_deaths: pd.DataFrame) -> pd.DataFrame:
    """Every country-year with features, whether it was at peace, and whether conflict started the next year."""
    deaths = _deaths(battle_deaths)
    last = int(battle_deaths["year"].max())
    pillars = [p.key for p in config.PILLARS]
    rows = []
    for year in sorted(hist["year"].unique()):
        frame = hist[hist["year"] == year][["iso3", *pillars]].dropna().set_index("iso3")
        if frame.empty:
            continue
        d_year = min(year, last)  # the index runs past the conflict data: use the latest conflict year available
        now = deaths.get(d_year, pd.Series(dtype=float)).reindex(frame.index).fillna(0.0)
        past = [deaths.get(y, pd.Series(dtype=float)).reindex(frame.index).fillna(0.0) for y in range(d_year - 5, d_year)]
        recent = (pd.concat(past, axis=1) >= CONFLICT).any(axis=1) if past else pd.Series(False, index=frame.index)
        out = frame.assign(year=int(year), violence=np.log1p(now.clip(upper=CONFLICT - 1)), recent_conflict=recent.astype(float),
                           at_peace=(now < CONFLICT).to_numpy())
        nxt = deaths.get(year + 1)
        out["onset"] = (nxt.reindex(frame.index).fillna(0.0) >= CONFLICT).to_numpy() if (nxt is not None and year + 1 <= last) \
            else np.nan
        rows.append(out.reset_index())
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _fit(x: np.ndarray, y: np.ndarray, penalty: float = PENALTY) -> np.ndarray:
    """Penalised logistic regression by Newton's method with a backtracking line search (each step must lower the
    penalised loss, which keeps the fit stable with rare events). x is standardised; returns [intercept, *coefs]."""
    xb = np.column_stack([np.ones(len(x)), x])
    w = np.zeros(xb.shape[1])
    w[0] = np.log(max(y.mean(), 1e-4) / max(1 - y.mean(), 1e-4))
    ridge = np.r_[0.0, np.full(xb.shape[1] - 1, penalty)]

    def loss(v: np.ndarray) -> float:
        z = xb @ v
        return float(np.sum(np.logaddexp(0, z) - y * z) + 0.5 * np.sum(ridge * v * v))

    current = loss(w)
    for _ in range(100):
        p = 1 / (1 + np.exp(-np.clip(xb @ w, -30, 30)))
        grad = xb.T @ (p - y) + ridge * w
        hess = (xb.T * (p * (1 - p))) @ xb + np.diag(ridge)
        step = np.linalg.solve(hess, grad)
        t = 1.0
        while t > 1e-6:
            trial = w - t * step
            new = loss(trial)
            if new <= current:
                break
            t /= 2
        if t <= 1e-6 or current - new < 1e-10:
            w = trial if new <= current else w
            break
        w, current = trial, new
    return w


def _predict(w: np.ndarray, x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(w[0] + x @ w[1:], -30, 30)))


def _standardise(train: pd.DataFrame, other: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, pd.Series, pd.Series]:
    mean, std = train[FEATURES].mean(), train[FEATURES].std(ddof=0).replace(0, 1)
    return ((train[FEATURES] - mean) / std).to_numpy(), ((other[FEATURES] - mean) / std).to_numpy(), mean, std


def outlook(hist: pd.DataFrame, battle_deaths: pd.DataFrame, index_year: int) -> Outlook | None:
    if battle_deaths is None or battle_deaths.empty or hist is None or hist.empty:
        return None
    data = panel(hist, battle_deaths)
    if data.empty:
        return None
    train_all = data[data["at_peace"] & data["onset"].notna()].copy()
    train_all["onset"] = train_all["onset"].astype(float)
    years = sorted(train_all["year"].unique())
    if len(years) < MIN_TRAIN_YEARS + 1 or train_all["onset"].sum() < 10:
        return None

    # Out-of-time test: fit on the years before, predict the year
    tests = []
    for year in years[MIN_TRAIN_YEARS:]:
        train, test = train_all[train_all["year"] < year], train_all[train_all["year"] == year]
        if train["onset"].sum() < 5 or test.empty:
            continue
        xt, xs, _, _ = _standardise(train, test)
        w = _fit(xt, train["onset"].to_numpy())
        tests.append(test[["iso3", "year", "onset"]].assign(probability=_predict(w, xs), base=train["onset"].mean()))
    backtest = pd.concat(tests, ignore_index=True) if tests else pd.DataFrame(columns=["iso3", "year", "onset", "probability", "base"])
    auc = validation.auc(backtest["probability"], backtest["onset"].astype(bool)) if len(backtest) else None
    if len(backtest):
        brier = float(((backtest["probability"] - backtest["onset"]) ** 2).mean())
        ref = float(((backtest["base"] - backtest["onset"]) ** 2).mean())
        skill = 1 - brier / ref if ref > 0 else None
        backtest["fifth"] = pd.qcut(backtest["probability"].rank(method="first"), 5, labels=False) + 1
        calibration = backtest.groupby("fifth").agg(predicted=("probability", "mean"), observed=("onset", "mean"),
                                                   cases=("onset", "size")).reset_index()
    else:
        skill, calibration = None, pd.DataFrame(columns=["fifth", "predicted", "observed", "cases"])

    # Final model on every year, applied to the latest index year
    latest = data[data["year"] == index_year]
    if latest.empty:
        latest = data[data["year"] == data["year"].max()]
    xt, xs, _, std = _standardise(train_all, latest)
    w = _fit(xt, train_all["onset"].to_numpy())
    prob = _predict(w, xs)
    base = float(train_all["onset"].mean())
    preds = latest[["iso3", "at_peace", "recent_conflict"]].assign(probability=prob, relative=prob / base)
    preds["status"] = np.where(preds["at_peace"], "At peace", "In armed conflict")
    preds.loc[~preds["at_peace"], ["probability", "relative"]] = np.nan
    return Outlook(
        predictions=preds.drop(columns=["at_peace"]).reset_index(drop=True), base_rate=base,
        coefficients=pd.Series(w[1:], index=FEATURES), backtest=backtest, auc=auc, brier_skill=skill,
        calibration=calibration, data_year=int(battle_deaths["year"].max()), index_year=int(latest["year"].iloc[0]),
    )
