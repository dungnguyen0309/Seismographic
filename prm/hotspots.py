"""Hotspots: recent armed-conflict events (UCDP candidate data) and conflict-news volume (GDELT).

scripts/refresh_hotspots.py downloads both every day and saves four files to data/snapshot/; the app only reads them.
The parsing helpers live here so the tests cover them.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import streamlit as st

from . import config
from .data import SNAPSHOT_DIR
from .sources import _name_key

WINDOW_DAYS = 90  # the UCDP and GDELT windows
RECENT_DAYS = 7  # the signal compares the last week with the rest of the window
CELL_DEG = 0.5

# Escalation signal thresholds
MIN_ARTICLES_7D = 20  # fewer articles in the last week: too little coverage to read a change
ESCALATING_RATIO = 1.5
ESCALATING_Z = 2.0
EASING_RATIO = 0.67
MAD_SCALE = 1.4826  # makes the median absolute deviation comparable to a standard deviation
MIN_SPREAD = 0.05  # spread floor as a share of the baseline, so a flat baseline (MAD 0) does not divide by zero
STATUS_ORDER = ["Escalating", "Steady", "Easing", "Quiet"]

# Hotspot rules
MIN_EVENTS_90D = 5
MIN_DEATHS_90D = 25
MIN_COMPOSITE = 60

VIOLENCE = {1: "State-based", 2: "Non-state", 3: "One-sided"}

# UCDP country names that differ from the app's
UCDP_NAMES = {
    "DR Congo (Zaire)": "COD", "Russia (Soviet Union)": "RUS", "Yemen (North Yemen)": "YEM",
    "Myanmar (Burma)": "MMR", "Cambodia (Kampuchea)": "KHM", "Zimbabwe (Rhodesia)": "ZWE",
    "Madagascar (Malagasy)": "MDG", "Bosnia-Herzegovina": "BIH", "Ivory Coast": "CIV",
    "Kingdom of eSwatini (Swaziland)": "SWZ", "Serbia (Yugoslavia)": "SRB", "Turkey": "TUR",
    "United States of America": "USA", "Congo": "COG", "Vietnam (North Vietnam)": "VNM",
    "Macedonia, FYR": "MKD", "North Macedonia": "MKD", "Gambia": "GMB", "Kosovo": "XKX",
    "Iran": "IRN", "Syria": "SYR", "Laos": "LAO", "North Korea": "PRK", "South Korea": "KOR",
    "Palestine": "PSE", "Czech Republic": "CZE", "Cape Verde": "CPV", "Bahamas": "BHS",
}

# GDELT matches a phrase anywhere, so these names also catch a neighbour's (or a namesake's) news
GDELT_EXCLUDE = {
    "COG": '-"Democratic Republic"', "SDN": '-"South Sudan"', "NER": '-"Niger State" -"Niger Delta"',
    "GIN": '-Bissau -"Equatorial Guinea" -"New Guinea"', "GEO": "-Atlanta",
}

MONTHLY_COLUMNS =["iso3", "month", "events", "deaths"]
CELL_COLUMNS = ["iso3", "lat", "lon", "events", "deaths", "last_date", "violence"]
GDELT_COLUMNS = ["iso3", "date", "count", "norm"]
SIGNAL_COLUMNS = ["recent", "baseline", "ratio", "z", "articles_7d", "status"]


# ---------------------------------------------------------------------------
# UCDP parsing (used by scripts/refresh_hotspots.py)
# ---------------------------------------------------------------------------
def ucdp_iso3(names: pd.Series, countries: pd.DataFrame) -> pd.Series:
    """ISO3 for each UCDP country name: UCDP_NAMES first, then the app's names and official names."""
    lookup = {}
    for col in ("official_name", "name"):
        if col in countries:
            lookup.update({_name_key(n): iso for n, iso in zip(countries[col], countries["iso3"]) if isinstance(n, str)})
    lookup.update({_name_key(n): iso for n, iso in UCDP_NAMES.items()})
    return names.map(lambda n: lookup.get(_name_key(n)))


def parse_ucdp(raw: pd.DataFrame, countries: pd.DataFrame, window_days: int = WINDOW_DAYS):
    """(monthly, cells, info) from a UCDP GED candidate file. info has from, through and the unmapped names."""
    df = raw[["country", "latitude", "longitude", "date_start", "date_end", "best", "type_of_violence"]].copy()
    df["iso3"] = ucdp_iso3(df["country"], countries)
    unmapped = sorted(df.loc[df["iso3"].isna(), "country"].dropna().unique())
    df["date"] = pd.to_datetime(df["date_start"], errors="coerce").dt.normalize()
    df["end"] = pd.to_datetime(df["date_end"], errors="coerce").dt.normalize().fillna(df["date"])
    df = df.dropna(subset=["iso3", "date"])
    df["best"] = pd.to_numeric(df["best"], errors="coerce").fillna(0).astype(int)
    through = df["end"].max()
    info = {"from": None if df.empty else df["date"].min().date().isoformat(),
            "through": None if df.empty else through.date().isoformat(), "unmapped": unmapped}
    if df.empty:
        return pd.DataFrame(columns=MONTHLY_COLUMNS), pd.DataFrame(columns=CELL_COLUMNS), info

    df["month"] = df["date"].dt.strftime("%Y-%m")
    monthly = (df.groupby(["iso3", "month"]).agg(events=("best", "size"), deaths=("best", "sum")).reset_index())

    # an event lasting weeks counts if it ends in the window
    # shortcut: its deaths count in full, not just the days inside the window; share them out if that skews the board
    recent = df[df["end"] > through - pd.Timedelta(days=window_days)].copy()
    recent["lat"] = np.floor(recent["latitude"] / CELL_DEG) * CELL_DEG + CELL_DEG / 2
    recent["lon"] = np.floor(recent["longitude"] / CELL_DEG) * CELL_DEG + CELL_DEG / 2
    keys = ["iso3", "lat", "lon"]
    cells = recent.groupby(keys).agg(events=("best", "size"), deaths=("best", "sum"),
                                     last_date=("end", "max")).reset_index()
    main = (recent.groupby([*keys, "type_of_violence"]).size().rename("n").reset_index()
            .sort_values([*keys, "n", "type_of_violence"], ascending=[True, True, True, False, True])
            .drop_duplicates(keys).rename(columns={"type_of_violence": "violence"}))
    cells = cells.merge(main[[*keys, "violence"]], on=keys, how="left")
    cells["last_date"] = cells["last_date"].dt.strftime("%Y-%m-%d")
    cells["violence"] = cells["violence"].astype(int)
    return monthly[MONTHLY_COLUMNS], cells[CELL_COLUMNS], info


def gdelt_points(payload: dict, iso3: str) -> pd.DataFrame:
    """Rows of hotspots_gdelt.csv from one TimelineVolRaw answer."""
    timeline = payload.get("timeline") or []
    points = timeline[0].get("data", []) if timeline else []
    if not points:
        return pd.DataFrame(columns=GDELT_COLUMNS)
    df = pd.DataFrame(points).rename(columns={"value": "count"})
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%dT%H%M%SZ", errors="coerce").dt.strftime("%Y-%m-%d")
    df["iso3"] = iso3
    return df.dropna(subset=["date"])[GDELT_COLUMNS]


# ---------------------------------------------------------------------------
# Signal and board (pure)
# ---------------------------------------------------------------------------
def escalation(gdelt: pd.DataFrame) -> pd.DataFrame:
    """Conflict-news share of the last RECENT_DAYS against the rest of the window, per country."""
    if gdelt is None or gdelt.empty:
        return pd.DataFrame(columns=SIGNAL_COLUMNS, index=pd.Index([], name="iso3"))
    df = gdelt.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["norm"] > 0]
    df["share"] = df["count"] / df["norm"]
    rows = {}
    for iso3, g in df.groupby("iso3"):
        # GDELT leaves out some days: each country gets its full window, and a missing day counts as no articles
        end = g["date"].max()
        days = pd.date_range(end - pd.Timedelta(days=WINDOW_DAYS - 1), end, freq="D")
        g = g.drop_duplicates("date").set_index("date").reindex(days)
        g[["count", "share"]] = g[["count", "share"]].fillna(0)
        last, base = g.iloc[-RECENT_DAYS:], g.iloc[:-RECENT_DAYS]
        recent, baseline = last["share"].mean(), base["share"].median()
        articles = int(last["count"].sum())
        ratio = recent / baseline if baseline > 0 else np.nan
        if articles < MIN_ARTICLES_7D:
            rows[iso3] = (recent, baseline, ratio, np.nan, articles, "Quiet")
            continue
        mad = (base["share"] - baseline).abs().median()
        # floors: a flat baseline (MAD 0) and a zero baseline (a country that rarely makes conflict news)
        spread = max(MAD_SCALE * mad, MIN_SPREAD * baseline, 1 / g["norm"].median())
        z = (recent - baseline) / spread
        if z >= ESCALATING_Z and (baseline == 0 or ratio >= ESCALATING_RATIO):
            status = "Escalating"
        elif ratio <= EASING_RATIO:
            status = "Easing"
        else:
            status = "Steady"
        rows[iso3] = (recent, baseline, ratio, z, articles, status)
    out = pd.DataFrame.from_dict(rows, orient="index", columns=SIGNAL_COLUMNS)
    out.index.name = "iso3"
    return out


def board(table: pd.DataFrame, monthly: pd.DataFrame, cells: pd.DataFrame, signal: pd.DataFrame) -> pd.DataFrame:
    """One row per hotspot, sorted: Escalating first, then deaths in the last 90 days, then composite.

    table: ui.master_table (iso3 as a column or the index). monthly is used for deaths_prev_3m, the deaths in the
    three months before the file's last three.
    """
    t = table.set_index("iso3") if "iso3" in table.columns else table
    if not cells.empty:
        recent = cells.groupby("iso3").agg(events_90d=("events", "sum"), deaths_90d=("deaths", "sum"),
                                           last_event=("last_date", "max"))
    else:
        recent = pd.DataFrame(columns=["events_90d", "deaths_90d", "last_event"])
    out = t.reindex(columns=["name", "iso2", "region", "composite", "tier", "analyst_rating"]).join(recent, how="left")
    out = out.join(signal.reindex(columns=["status", "ratio"]), how="left")
    if not monthly.empty:
        months = sorted(monthly["month"].unique())
        prev = monthly[monthly["month"].isin(months[-6:-3])].groupby("iso3")["deaths"].sum()
        out["deaths_prev_3m"] = prev.reindex(out.index).fillna(0).astype(int)
    else:
        out["deaths_prev_3m"] = 0
    out[["events_90d", "deaths_90d"]] = out[["events_90d", "deaths_90d"]].fillna(0).astype(int)
    out["last_event"] = pd.to_datetime(out["last_event"]).dt.date
    out["status"] = out["status"].fillna("Quiet")
    out["ratio"] = pd.to_numeric(out["ratio"], errors="coerce")
    out["analyst_rating"] = out["analyst_rating"].fillna("")
    hot = ((out["events_90d"] >= MIN_EVENTS_90D) | (out["deaths_90d"] >= MIN_DEATHS_90D)
           | (out["status"] == "Escalating") | (out["composite"] >= MIN_COMPOSITE))
    out = out[hot].assign(_esc=lambda d: d["status"] != "Escalating")
    out = out.sort_values(["_esc", "deaths_90d", "composite"], ascending=[True, False, False], na_position="last")
    out = out.drop(columns="_esc")
    out["order"] = range(1, len(out) + 1)
    out.index.name = "iso3"
    return out.reset_index()


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def _csv(name: str, columns: list[str]) -> pd.DataFrame:
    path = SNAPSHOT_DIR / f"{name}.csv"
    try:
        return pd.read_csv(path)[columns]
    except Exception:  # missing or corrupt: the page shows an empty state
        return pd.DataFrame(columns=columns)


@st.cache_data(ttl=60 * 60, show_spinner=False)
def load() -> dict:
    """{"monthly", "cells", "gdelt", "meta"} from data/snapshot/hotspots_*."""
    try:
        meta = json.loads((SNAPSHOT_DIR / "hotspots_meta.json").read_text(encoding="utf-8"))
    except Exception:
        meta = {}
    return {
        "monthly": _csv("hotspots_ucdp_monthly", MONTHLY_COLUMNS),
        "cells": _csv("hotspots_ucdp_cells", CELL_COLUMNS),
        "gdelt": _csv("hotspots_gdelt", GDELT_COLUMNS),
        "meta": meta,
    }


def news_name(iso3: str, name: str) -> str:
    return config.NEWS_NAMES.get(iso3, name)
