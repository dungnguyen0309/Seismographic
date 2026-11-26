"""Case studies, stress test, builder and data downloads: the files staticbuild/group10.py writes (no network)."""

import io
import json
import time
import zipfile

import openpyxl
import pytest


@pytest.fixture(scope="module")
def ctx(tmp_path_factory):
    from staticbuild import common

    return common.load(tmp_path_factory.mktemp("web"))


@pytest.fixture(scope="module")
def built(ctx):
    from staticbuild import group10

    group10.build(ctx)
    return ctx


def read(ctx, rel: str):
    return json.loads((ctx.web / rel).read_text(encoding="utf-8"))


def test_cases_file(built):
    from prm import cases

    out = read(built, "data/group10/cases.json")
    assert [c["key"] for c in out["cases"]] == [c.key for c in cases.CASES]
    assert out["verdicts"]["Flagged"] == list(cases.VERDICTS["Flagged"])
    eth = out["cases"][0]
    assert {"iso3", "date", "kind", "title", "what", "source", "flags", "commentary"} <= set(eth)
    assert eth["iso3"] == "ETH" and eth["commentary"] is None  # case_studies/ holds only a README
    assert {f["key"] for f in eth["flags"]} >= {"reserves_months"}  # red flags of 2019, the year before the war


def test_stress_file(built):
    from prm import stress

    out = read(built, "data/group10/stress.json")
    assert [s["key"] for s in out["shocks"]] == [s.key for s in stress.SHOCKS]
    assert out["shocks"][5] == {"key": "reserves_months", "label": "FX reserves", "unit": "% change", "low": -60,
                                "high": 30, "step": 5, "relative": True}
    assert list(out["scenarios"]) == list(stress.SCENARIOS)


def test_builder_file(built):
    out = read(built, "data/group10/builder.json")
    assert set(out) == {"next_growth"} and isinstance(out["next_growth"]["NGA"], float)


def test_tables_file(built):
    out = read(built, "data/group10/tables.json")
    assert list(out["descriptions"]) == ["index", "indicators", "red_flags", "history", "conflict_outlook", "dictionary"]
    assert out["dtypes"]["index"]["rank"] == "int" and out["dtypes"]["index"]["composite"] == "float"
    assert out["dtypes"]["history"]["battle_deaths"] == "float" and out["dtypes"]["index"]["tier"] == "str"
    for name in ("indicators", "red_flags", "conflict_outlook", "dictionary"):
        assert len(out[name]["rows"]) == len(built.tables[name]), name
        assert out[name]["columns"] == list(built.tables[name].columns), name
    assert "index" not in out and "history" not in out  # these follow the visitor's weights: built in the browser
    assert out["bd_last_year"] == int(built.core["series"]["battle_deaths"]["year"].max())
    assert out["meta"]["data_version"] == built.core["version"] and "generated" not in out["meta"]


def test_workbook_is_the_default_export(built):
    blob = (built.web / "files/seismographic.xlsx").read_bytes()
    book = openpyxl.load_workbook(io.BytesIO(blob))
    assert book.sheetnames == ["about", "index", "indicators", "red_flags", "history", "conflict_outlook", "dictionary"]
    about = dict(book["about"].iter_rows(min_row=2, values_only=True))
    assert about["generated"] == f"{built.core['snapshot_date']}T00:00:00+00:00"
    assert json.loads(about["weights"].replace("'", '"')) == {"stability": 35.0, "governance": 25.0, "economic": 25.0,
                                                               "social": 15.0}
    assert book["index"].max_row == len(built.tables["index"]) + 1


def test_workbook_is_byte_identical_for_the_same_snapshot(built, monkeypatch):
    from staticbuild import group10

    first = (built.web / "files/seismographic.xlsx").read_bytes()
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 86400 * 3)  # zip entries take their date from the clock
    group10.build(built)
    assert (built.web / "files/seismographic.xlsx").read_bytes() == first
    day = tuple(int(x) for x in built.core["snapshot_date"].split("-"))
    with zipfile.ZipFile(io.BytesIO(first)) as z:
        assert {i.date_time for i in z.infolist()} == {(*day, 0, 0, 0)}
        core = z.read("docProps/core.xml").decode()
    assert core.count(f"{built.core['snapshot_date']}T00:00:00Z") == 2  # created and modified


def test_fixtures(built):
    from staticbuild import group10

    group10.fixtures(built)
    out = built.web / "tests/fixtures"
    names = {p.name for p in out.glob("group10_*.json")}
    assert names == {"group10_normalise_against.json", "group10_stress.json", "group10_cases.json",
                     "group10_builder.json", "group10_export.json"}
    norm = read(built, "tests/fixtures/group10_normalise_against.json")
    assert {c["method"] for c in norm["cases"]} == {"percentile", "log"}
    assert any(None in c["out"] for c in norm["cases"])  # missing values stay missing
    stress = read(built, "tests/fixtures/group10_stress.json")
    assert stress["decode"][0] == {"in": "garbage", "out": {}}
    builder = read(built, "tests/fixtures/group10_builder.json")
    assert builder["driver_facts"]["drv_economic"][0] == "inflation"
