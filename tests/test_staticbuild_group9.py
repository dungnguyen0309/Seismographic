"""The conflict and economy page data (staticbuild/group9.py) and its parity fixtures. No network: the exporter only
reads the snapshot."""

import json
from types import SimpleNamespace

import pytest


@pytest.fixture(scope="module")
def ctx(tmp_path_factory):
    from staticbuild import common

    return common.load(tmp_path_factory.mktemp("web"))


def read(ctx, rel: str):
    return json.loads((ctx.web / rel).read_text(encoding="utf-8"))


def test_pct_delta():
    from staticbuild.group9 import pct_delta

    assert pct_delta(100, 0) is None
    assert pct_delta(100, 100) == 0 and pct_delta(100.2, 100) == 0  # rounds to nothing: a plain 0, shown grey
    assert pct_delta(98, 100) == "-2%" and pct_delta(103, 100) == "+3%"


def test_conflict_and_economy_files(ctx):
    from staticbuild import group9

    group9.build(ctx)
    c = read(ctx, "data/group9/conflict.json")
    assert c["bd_year"] and c["dp_year"] and c["flows_year"]
    labels = [k["label"] for k in c["kpis"]]
    assert labels == ["Armed conflicts", "At war", f"Battle deaths, {c['bd_year']}", f"Displaced, {c['dp_year']}",
                      "Refugees abroad"]
    assert c["kpis"][0]["value"] == c["in_conflict"] > 0 and c["kpis"][0]["note"] == f"vs {c['bd_year'] - 1}"
    assert c["kpis"][0]["deltaColor"] == "inverse" and "help" in c["kpis"][1]
    assert set(c["figures"]) == {"deaths", "deadliest", "displaced", "origins", "hosts", "sankey", "drivers", "calibration"}
    assert c["figures"]["sankey"]["data"][0]["type"] == "sankey" and "template" not in c["figures"]["deaths"]["layout"]
    deaths = [d["deaths"] for d in c["deadliest"]]
    assert 0 < len(deaths) <= 10 and deaths == sorted(deaths, reverse=True) and min(deaths) >= 25
    rows = c["rows"]
    assert rows["columns"] == ["iso3", "name", "iso2", "deaths", "change_text", "battle_deaths_100k", "displaced_share",
                               "stability", "level"]
    assert len(rows["rows"]) == c["in_conflict"]  # every country in armed conflict, deadliest first
    assert rows["rows"][0][rows["columns"].index("level")] == "War"
    ukr = c["notes"].get("UKR", "")
    assert "battle deaths in" in ukr and "people displaced" in ukr

    e = read(ctx, "data/group9/economy.json")
    assert set(e["series"]) == {"inflation", "gdp_growth", "gov_debt"}
    s = e["series"]["inflation"]
    years = [r[s["columns"].index("year")] for r in s["rows"]]
    assert s["columns"] == ["iso3", "year", "value"] and min(years) == ctx.year - 12 and max(years) >= ctx.year + 4


def test_conflict_without_flows_or_outlook(ctx):
    from staticbuild import group9

    bare = SimpleNamespace(**{**vars(ctx), "core": {**ctx.core, "flows": None}, "outlook": None})
    c = group9.conflict(bare)
    assert c["flows_year"] is None and c["kpis"][4]["value"] == "—"
    assert set(c["figures"]) == {"deaths", "deadliest", "displaced", "origins"}  # the page shows its empty states


def test_fixtures(ctx):
    from staticbuild import group9

    group9.fixtures(ctx)
    hs = read(ctx, "tests/fixtures/group9_hotspots.json")
    assert [b["weights"] for b in hs["boards"]] == ["default", "w50_20_20_10", "default"]
    stale = hs["boards"][2]["board"]
    assert stale and {r["status"] for r in stale} == {"Quiet"} and all(r["ratio"] is None for r in stale)
    assert hs["constants"]["WINDOW_DAYS"] == 90 and hs["constants"]["VIOLENCE"]["1"] == "State-based"
    eco = read(ctx, "tests/fixtures/group9_economy.json")["cases"]
    assert [c["region"] for c in eco] == ["All regions", "Sub-Saharan Africa", "North America"]
    assert eco[0]["heatmap"]["data"][0]["type"] == "heatmap" and len(eco[0]["heatmap"]["data"][0]["y"]) == 40
    cal = read(ctx, "tests/fixtures/group9_calendar.json")
    assert set(cal["windows"]) == {"Next 90 days", "Next 12 months", "All upcoming", "Past"}
    out = read(ctx, "tests/fixtures/group9_outlook.json")
    assert len(out["rows"]) == 20 and out["chance_max"] >= 30
