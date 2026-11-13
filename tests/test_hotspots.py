"""Unit tests for the Hotspots data (fast, no network)."""

import importlib.util
import io
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from prm import hotspots

ROOT = Path(__file__).resolve().parents[1]


def _series(shares: list[float], norm: int = 10000, iso3: str = "AAA") -> pd.DataFrame:
    dates = pd.date_range("2026-08-01", periods=len(shares), freq="D")
    return pd.DataFrame({"iso3": iso3, "date": dates.strftime("%Y-%m-%d"),
                         "count": [round(s * norm) for s in shares], "norm": norm})


def _noisy(n: int, level: float = 0.01, seed: int = 0) -> list[float]:
    rng = np.random.default_rng(seed)
    return list(level * (1 + 0.1 * rng.standard_normal(n)))


def test_flat_series_is_steady_and_mad_zero_does_not_divide_by_zero():
    sig = hotspots.escalation(_series([0.01] * 90))
    row = sig.loc["AAA"]
    assert row["status"] == "Steady"
    assert row["ratio"] == pytest.approx(1.0) and row["z"] == pytest.approx(0.0)
    assert np.isfinite(hotspots.escalation(_series([0.01] * 83 + [0.03] * 7)).loc["AAA", "z"])


def test_jump_is_escalating_and_drop_is_easing():
    up = hotspots.escalation(_series(_noisy(83) + [0.03] * 7)).loc["AAA"]
    assert up["status"] == "Escalating" and up["ratio"] > 2 and up["z"] > 2
    down = hotspots.escalation(_series(_noisy(83) + [0.004] * 7)).loc["AAA"]
    assert down["status"] == "Easing"


def test_thin_series_is_quiet():
    few_articles = hotspots.escalation(_series([0.01] * 90, norm=100)).loc["AAA"]  # 1 article a day
    assert few_articles["articles_7d"] < hotspots.MIN_ARTICLES_7D and few_articles["status"] == "Quiet"
    assert hotspots.escalation(pd.DataFrame(columns=hotspots.GDELT_COLUMNS)).empty


def test_flare_up_from_a_zero_baseline_is_escalating():
    row = hotspots.escalation(_series([0] * 83 + [0.05] * 7, norm=1000)).loc["AAA"]
    assert row["articles_7d"] == 350 and row["baseline"] == 0
    assert row["status"] == "Escalating" and np.isnan(row["ratio"])


def test_missing_days_count_as_zero():
    full = _series(_noisy(83) + [0.03] * 7)
    gappy = full.drop(index=range(0, 83, 2))  # GDELT left out every other baseline day
    row = hotspots.escalation(gappy).loc["AAA"]
    assert row["baseline"] == 0 and row["status"] == "Escalating"
    assert hotspots.escalation(_series([0.01] * 20)).loc["AAA", "baseline"] == 0  # 70 days missing before it


UCDP_CSV = """country,latitude,longitude,date_start,date_end,best,type_of_violence,where_prec
DR Congo (Zaire),-1.2,29.2,2026-09-28 00:00:00.000,2026-09-28 00:00:00.000,10,1,1
DR Congo (Zaire),-1.9,29.4,2026-09-20 00:00:00.000,2026-09-20 00:00:00.000,3,3,1
DR Congo (Zaire),-1.7,29.3,2026-09-10 00:00:00.000,2026-09-10 00:00:00.000,1,3,1
Russia (Soviet Union),50.1,36.2,2026-05-01 00:00:00.000,2026-05-01 00:00:00.000,7,1,1
Russia (Soviet Union),50.1,36.2,2026-09-30 00:00:00.000,2026-09-30 00:00:00.000,2,1,1
Atlantis,0,0,2026-09-01 00:00:00.000,2026-09-01 00:00:00.000,1,2,1
"""
COUNTRIES = pd.DataFrame({"iso3": ["COD", "RUS"], "name": ["DR Congo", "Russia"],
                          "official_name": ["Congo, Dem. Rep.", "Russian Federation"]})


def test_ucdp_parsing_maps_names_sums_months_and_builds_cells():
    monthly, cells, info = hotspots.parse_ucdp(pd.read_csv(io.StringIO(UCDP_CSV)), COUNTRIES)
    assert info["unmapped"] == ["Atlantis"]
    assert info["from"] == "2026-05-01" and info["through"] == "2026-09-30"
    m = monthly.set_index(["iso3", "month"])
    assert m.loc[("COD", "2026-09"), "events"] == 3 and m.loc[("COD", "2026-09"), "deaths"] == 14
    assert m.loc[("RUS", "2026-05"), "deaths"] == 7
    # the May event is outside the 90-day window
    assert cells.loc[cells["iso3"] == "RUS", "events"].sum() == 1
    cod = cells[cells["iso3"] == "COD"].set_index(["lat", "lon"])
    assert set(cod.index) == {(-1.75, 29.25), (-1.25, 29.25)}  # 0.5-degree cell centres
    cell = cod.loc[(-1.75, 29.25)]
    assert cell["events"] == 2 and cell["deaths"] == 4 and cell["last_date"] == "2026-09-20"
    assert cell["violence"] == 3


def test_event_ending_inside_the_window_counts():
    raw = pd.read_csv(io.StringIO(UCDP_CSV + "Russia (Soviet Union),50.1,36.2,2026-06-01 00:00:00.000,2026-08-20 00:00:00.000,40,1,1\n"))
    _, cells, info = hotspots.parse_ucdp(raw, COUNTRIES)
    rus = cells[cells["iso3"] == "RUS"]
    assert rus["events"].sum() == 2 and rus["deaths"].sum() == 42  # started before the window, ended in it
    assert info["through"] == "2026-09-30" and rus["last_date"].max() == "2026-09-30"


def test_ucdp_files_add_monthly_files_newer_than_the_cumulative_one():
    spec = importlib.util.spec_from_file_location("refresh_hotspots", ROOT / "scripts" / "refresh_hotspots.py")
    refresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(refresh)
    page = " ".join(f'href="candidateged/{f}"' for f in [
        "GEDEvent_v26_01_26_06.csv", "GEDEvent_v26_01_26_09.csv", "GEDEvent_v26_0_9.csv", "GEDEvent_v26_0_10.csv",
        "GEDEvent_v26_0_11.csv", "GEDEvent_v25_0_12.csv"])
    assert refresh.ucdp_files(page) == ["GEDEvent_v26_01_26_09.csv", "GEDEvent_v26_0_10.csv", "GEDEvent_v26_0_11.csv"]
    assert refresh.ucdp_files('href="candidateged/GEDEvent_v26_0_10.csv"') == ["GEDEvent_v26_0_10.csv"]


def test_board_membership_and_order():
    table = pd.DataFrame({
        "iso3": ["EVT", "DTH", "ESC", "HIGH", "CALM"],
        "name": list("abcde"), "iso2": list("ABCDE"), "region": "r", "tier": "High",
        "composite": [40.0, 30.0, 20.0, 65.0, 59.0], "analyst_rating": "",
    })
    cells = pd.DataFrame({"iso3": ["EVT", "DTH", "CALM"], "lat": 0.25, "lon": 0.25, "events": [5, 1, 4],
                          "deaths": [0, 25, 24], "last_date": "2026-09-30", "violence": 1})
    signal = pd.DataFrame({"status": ["Escalating", "Steady"], "ratio": [2.0, 1.0]}, index=["ESC", "CALM"])
    monthly = pd.DataFrame(columns=hotspots.MONTHLY_COLUMNS)
    b = hotspots.board(table, monthly, cells, signal)
    assert list(b["iso3"]) == ["ESC", "DTH", "HIGH", "EVT"]
    assert list(b["order"]) == [1, 2, 3, 4]
    assert b.set_index("iso3").loc["HIGH", "status"] == "Quiet"


def test_loaders_return_empty_frames_when_files_are_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(hotspots, "SNAPSHOT_DIR", tmp_path)
    hotspots.load.clear()
    try:
        got = hotspots.load()
    finally:
        hotspots.load.clear()
    assert got["meta"] == {}
    for key, cols in [("monthly", hotspots.MONTHLY_COLUMNS), ("cells", hotspots.CELL_COLUMNS),
                      ("gdelt", hotspots.GDELT_COLUMNS)]:
        assert got[key].empty and list(got[key].columns) == cols
