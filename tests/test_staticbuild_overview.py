"""The overview page data (staticbuild/overview.py): the files it writes, and the parity fixtures, whose expected
values must be what app_pages/overview.py shows. No network."""

import json

import pandas as pd
import pytest

# prm is imported inside the tests: the UI modules must first load inside the test app (tests/conftest.py)


def read(ctx, rel: str):
    return json.loads((ctx.web / rel).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ctx(tmp_path_factory):
    from staticbuild import common

    return common.load(tmp_path_factory.mktemp("web"))


def test_build_writes_wgi_changes_and_new_flags(ctx):
    from prm import data, scoring
    from staticbuild import overview

    overview.build(ctx)
    changes = read(ctx, "data/overview/wgi_changes.json")
    expected = scoring.wgi_changes(ctx.core["series"], ctx.core["countries"], "pv")
    assert changes["columns"] == ["iso3", "start", "end", "change", "start_year", "end_year"]
    assert len(changes["rows"]) == len(expected) > 100
    assert changes["rows"][0][3] == pytest.approx(float(expected["change"].iloc[0]), abs=0)  # full precision

    flags = read(ctx, "data/overview/new_flags.json")
    prev = data.get_values(ctx.core, ctx.year - 1, ctx.core["version"])
    worse = {i: [f["label"] for f in scoring.flag_changes(prev.loc[i], ctx.values.loc[i])[0]]
             for i in ctx.values.index if i in prev.index}
    assert flags == {i: labels for i, labels in worse.items() if labels}
    assert flags and all(labels for labels in flags.values())


def test_fixtures_cover_the_filters_and_weights(ctx):
    from staticbuild import overview

    overview.fixtures(ctx)
    head = read(ctx, "tests/fixtures/overview_headline.json")["cases"]
    assert {c["weights"] for c in head} == {"default", "w50_20_20_10"}
    assert any(c["expected"]["scored"] == 0 and c["expected"]["median"] == "—" for c in head)  # an empty view
    assert any(c["expected"]["assessed"] == 0 and c["expected"]["scored"] for c in head)  # "Critical red flag"
    hot = read(ctx, "tests/fixtures/overview_hotspots.json")
    assert hot["today"] == str(pd.Timestamp.today().normalize().date())
    assert any(c["expected"] for c in hot["cases"]) and any(not c["expected"] for c in hot["cases"])
    csv = read(ctx, "tests/fixtures/overview_ranking_csv.json")["cases"]
    assert all(c["expected"].startswith("﻿name,composite,trend,tier,rank,") for c in csv)
    movers = read(ctx, "tests/fixtures/overview_movers.json")["cases"]
    assert len(movers) >= 2 and all(c["figure"]["data"] for c in movers)


def test_fixture_numbers_are_what_the_page_shows(app, ctx):
    """The fixtures' Python side (overview.headline, overview.hotspot_rows) against the running page."""
    from prm import config, data, ui
    from staticbuild import overview

    app.switch_page("app_pages/overview.py")
    app.query_params.clear()
    for key in ("ov_tab", "ov_tab__url"):
        if key in app.session_state:
            del app.session_state[key]
    app.session_state["ov_region"], app.session_state["ov_income"] = "All regions", []
    for p in config.PILLARS:
        app.session_state[ui.WEIGHT_KEYS[p.key]] = int(p.default_weight)
    app.run()
    assert not app.exception, [str(e.value)[:300] for e in app.exception]

    table = ui.master_table(ctx.core, ctx.values, ctx.scores, ctx.history)
    view = overview.filter_view(table, "All regions", [])
    head = overview.headline(view, ctx.history, ctx.values, ctx.year)
    shown = {m.label: m for m in app.metric}
    assert shown["Countries scored"].value == str(head["scored"])
    assert shown["High or Severe risk"].value == str(head["high"])
    assert shown["High or Severe risk"].delta == str(head["high_delta"])
    assert shown["Median score"].value == head["median"]
    assert shown["Median score"].delta == str(head["median_delta"])
    assert shown["In armed conflict"].value == str(head["conflict"])
    assert shown["Assessments"].value == str(head["assessed"])

    rows = overview.hotspot_rows(view, ctx.values, data.get_values(ctx.core, ctx.year - 1, ctx.core["version"]),
                                 ctx.year, pd.Timestamp.today().normalize())
    hot = app.dataframe[0].value
    assert list(hot["name"]) == [r["name"] for r in rows]
    assert list(hot["why"]) == [r["why"] for r in rows]
