"""The Compare / Score changes / Regions / Indicator explorer data (staticbuild/group8.py). Reads the snapshot only."""

import json

import pandas as pd
import pytest

from prm import charts, data, scoring


@pytest.fixture(scope="module")
def ctx(tmp_path_factory):
    from staticbuild import common, group8

    ctx = common.load(tmp_path_factory.mktemp("web"))
    group8.build(ctx)
    return ctx


def read(ctx, rel):
    return json.loads((ctx.web / rel).read_text(encoding="utf-8"))


def test_series_files_draw_what_compare_lines_draws(ctx):
    files = list((ctx.data / "group8" / "series").glob("*.json"))
    assert len(files) == len(ctx.core["countries"])  # one per economy, so a pick never meets a missing file
    nga = read(ctx, "data/group8/series/NGA.json")
    for key in ["wgi_pv", "wgi_cc", "gdp_growth"]:
        rows = pd.DataFrame(nga[key], columns=["year", "value"]).assign(iso3="NGA")
        kw = dict(start_year=ctx.year - 12, end_year=ctx.year + 5, projected_from=ctx.year) if key == "gdp_growth" else {}
        got = charts.compare_lines({key: rows}, key, ["NGA"], {"NGA": "Nigeria"}, "t", **kw)
        want = charts.compare_lines(ctx.core["series"], key, ["NGA"], {"NGA": "Nigeria"}, "t", **kw)
        assert got.to_json() == want.to_json(), key
    assert all(ctx.year - 12 <= y <= ctx.year + 5 for y, _ in nga["inflation"])
    assert nga["wgi_pv"][0][0] < ctx.year - 12  # WGI keeps every year


def test_flag_changes_are_last_year_against_this_year(ctx):
    t = read(ctx, "data/group8/flag_changes.json")
    assert t["columns"] == ["iso3", "change", "severity", "flag_label"]
    rows = pd.DataFrame(t["rows"], columns=t["columns"])
    prev = data.get_values(ctx.core, ctx.year - 1, ctx.core["version"])
    for iso3 in ["BHR", "AGO", "NGA", "NOR"]:
        worse, eased = scoring.flag_changes(prev.loc[iso3], ctx.values.loc[iso3])
        mine = rows[rows["iso3"] == iso3]
        assert list(mine.loc[mine["change"] == "New", "flag_label"]) == [f["label"] for f in worse]
        assert list(mine.loc[mine["change"] == "New", "severity"]) == [f["severity"] for f in worse]
        assert list(mine.loc[mine["change"] == "Cleared", "flag_label"]) == [f["label"] for f in eased]
    assert set(rows["change"]) == {"New", "Cleared"} and (rows.loc[rows["change"] == "Cleared", "severity"] == "").all()


def test_fixtures_cover_every_page(ctx):
    from staticbuild import group8

    group8.fixtures(ctx)
    for page in ["compare", "changes", "regions", "explorer"]:
        assert read(ctx, f"tests/fixtures/group8_{page}.json")["cases"]
    cases = read(ctx, "tests/fixtures/group8_regions.json")["cases"]
    assert {c["region"] for c in cases if c["asked"] in (None, "Nowhere")} == {"East Asia & Pacific"}
    unscored = [c for c in read(ctx, "tests/fixtures/group8_compare.json")["cases"] if c["cards"][0]["rank"] is None]
    assert unscored and unscored[0]["cards"][0]["score"] == "—" and unscored[0]["similar"] == []
