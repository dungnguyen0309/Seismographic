"""The country page's data: profiles, GDELT charts and PDF briefs (no network: fetchers are patched), and the page steps
restated in staticbuild/country.py for the JS fixtures, checked against the running page."""

import json

import pandas as pd
import pytest

from tests.test_pages import errors


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ctx(tmp_path_factory):
    from staticbuild import common

    return common.load(tmp_path_factory.mktemp("web"))


def test_profiles(ctx):
    from prm import scoring
    from staticbuild import country

    country.build(ctx, ["NGA", "ASM", "SYR"])
    nga = read(ctx.data / "country" / "NGA.json")
    assert set(nga) == {"iso3", "news_name", "next_growth", "stability_flags", "outlook", "whatif", "governance",
                        "elsewhere", "figures"}
    assert nga["next_growth"] == scoring._next_year_value(ctx.core["series"], "gdp_growth", "NGA", ctx.year + 1)
    assert nga["outlook"] == {"level": None, "text": f"In armed conflict in the latest data ({ctx.outlook.data_year})."}
    assert [c["key"] for c in nga["whatif"]["controls"]][:3] == ["wgi_pv", "battle_deaths_raw", "homicide"]
    assert nga["governance"]["columns"][0] == "Dimension" and len(nga["governance"]["rows"]) == 6
    assert nga["elsewhere"][-1][0] == "FAO food security"
    for fig in nga["figures"].values():
        assert fig["data"] and "template" not in fig["layout"]
    asm = read(ctx.data / "country" / "ASM.json")  # no composite score
    assert asm["outlook"] is None and asm["next_growth"] is None
    assert "Inflation" in asm["whatif"]["missing"] and asm["elsewhere"][-1][0] == "ReliefWeb"  # high income: no FAO
    flags = read(ctx.data / "country" / "SYR.json")["stability_flags"]
    assert flags == scoring.stability_flags(ctx.core["series"], "SYR")


def test_gdelt_files_keep_the_last_good(ctx, monkeypatch):
    from prm import sources
    from staticbuild import gdelt

    clock = {"now": 0.0}
    waits = []
    monkeypatch.setattr(gdelt.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(gdelt.time, "sleep", lambda s: (waits.append(s), clock.__setitem__("now", clock["now"] + s)))
    monkeypatch.setenv("GDELT_COUNTRIES", "nga, SYR")
    points = pd.DataFrame({"date": pd.to_datetime(["2026-09-01", "2026-09-02"], utc=True), "tone": [-1.5, -2.0]})
    shares = pd.DataFrame({"date": pd.to_datetime(["2026-09-01", "2026-09-02"], utc=True), "share": [0.1, 0.2]})
    asked = []

    def tone(name):
        asked.append(("tone", name))
        return points

    def protests(name):
        asked.append(("protests", name))
        return shares if name == "Nigeria" else shares.iloc[0:0]  # GDELT found nothing for Syria

    monkeypatch.setattr(sources, "fetch_gdelt_tone", tone)
    monkeypatch.setattr(sources, "fetch_gdelt_protests", protests)
    gdelt.build(ctx)
    out = ctx.data / "gdelt"
    assert sorted(p.name for p in out.glob("*.json")) == ["NGA.json", "SYR.json"]
    assert asked == [("tone", "Nigeria"), ("protests", "Nigeria"), ("tone", "Syria"), ("protests", "Syria")]
    assert waits == [gdelt.PAUSE] * 3  # one request every 5 seconds
    nga, syr = read(out / "NGA.json"), read(out / "SYR.json")
    assert set(nga) == {"tone", "protests"} and nga["tone"]["data"] and nga["protests"]["data"]
    assert syr["tone"]["data"] and syr["protests"] is None
    before = (out / "NGA.json").read_bytes(), (out / "SYR.json").read_bytes()

    def tone_429(name):
        raise sources.SourceError("Please limit requests to one every 5 seconds")

    asked.clear()
    monkeypatch.setattr(sources, "fetch_gdelt_tone", lambda name: tone_429(name) if name == "Nigeria" else points)
    monkeypatch.setattr(sources, "fetch_gdelt_protests", lambda name: tone_429(name))  # Syria: tone ok, protests fail
    gdelt.build(ctx)
    assert ((out / "NGA.json").read_bytes(), (out / "SYR.json").read_bytes()) == before  # never a partial file
    assert not list(out.glob("*.tmp"))

    asked.clear()  # GDELT down: the run stops after GIVE_UP failures in a row
    monkeypatch.setattr(gdelt, "GIVE_UP", 1)
    monkeypatch.setattr(sources, "fetch_gdelt_tone", lambda name: (asked.append(name), tone_429(name)))
    gdelt.build(ctx)
    assert asked == ["Nigeria"]

    asked.clear()  # a slow week: the run stops once GDELT_BUDGET_MIN has passed, the rest keep their last file
    monkeypatch.setattr(gdelt, "GIVE_UP", 10)
    monkeypatch.setenv("GDELT_BUDGET_MIN", "0.25")  # 15 s: room for the first country's two requests only
    monkeypatch.setattr(sources, "fetch_gdelt_tone", lambda name: (asked.append(name), clock.__setitem__("now", clock["now"] + 10), points)[-1])
    monkeypatch.setattr(sources, "fetch_gdelt_protests", lambda name: shares)
    gdelt.build(ctx)
    assert asked == ["Nigeria"]


def test_gdelt_waits_longer_than_the_app(ctx, monkeypatch):
    from prm import sources
    from staticbuild import gdelt

    seen = []

    def slow(url, params, timeout, headers):
        seen.append(timeout)
        raise sources.requests.Timeout("slow")

    monkeypatch.setenv("GDELT_COUNTRIES", "NGA")
    monkeypatch.setattr(sources.requests, "get", slow)
    gdelt.build(ctx)
    assert seen == [gdelt.TIMEOUT] and sources._gdelt_json.__defaults__ == (sources.GDELT_TIMEOUT,)


def test_briefs_are_dated_with_the_snapshot(ctx):
    from staticbuild import briefs

    from prm import report

    today, brief = pd.Timestamp.today, report._Brief
    briefs.build(ctx, ["NGA", "ASM"])
    path = ctx.web / "files" / "briefs" / "NGA.pdf"
    first = path.read_bytes()
    briefs.build(ctx, ["NGA"])
    assert path.read_bytes() == first  # an unchanged country: the same bytes
    assert first.startswith(b"%PDF") and (ctx.web / "files" / "briefs" / "ASM.pdf").is_file()
    stamp = ctx.core["snapshot_date"].replace("-", "")
    assert f"/CreationDate (D:{stamp}000000".encode() in first
    assert (pd.Timestamp.today, report._Brief) == (today, brief)  # the clock is back to normal afterwards


def test_page_steps_match_the_app(app, ctx):
    """The restated page steps behind the JS fixtures give what the running page shows (Nigeria, default weights)."""
    from prm import ui
    from staticbuild import country

    version = ctx.core["version"]
    controls = country.whatif_controls(ctx.values, "NGA")["controls"]
    table = ui.master_table(ctx.core, ctx.values, ctx.scores, ctx.history)

    def run(tab):
        app.session_state["country"] = "NGA"
        app.session_state["country_tab"] = tab
        app.run()
        assert not errors(app), errors(app)

    app.switch_page("app_pages/country.py")
    run("What-if")
    assert any(country.page_meta(ctx.values, ctx.scores, table, "NGA") in m.value for m in app.markdown)
    for c in controls:
        key = f"wi_NGA_{version}_{c['key']}"
        if c["kind"] == "select":
            widget = app.select_slider(key=key)
            assert [int(o.replace(",", "")) for o in widget.options] == c["options"] and widget.value == c["current"]
        else:
            widget = app.slider(key=key)
            assert (widget.min, widget.max, widget.value) == (c["min"], c["max"], c["current"]), c["key"]
    for preset in ("Currency crisis", "Armed conflict"):
        app.button(key=f"preset_{preset}").click()
        run("What-if")
        values = country.apply_preset(preset, controls)
        for key, value in values.items():
            widget_key = f"wi_NGA_{version}_{key}"
            shown = (app.select_slider(key=widget_key) if key == "battle_deaths_raw" else app.slider(key=widget_key)).value
            assert shown == value, key
        result = country.whatif_result(ctx.values, ctx.scores, dict(ctx.weights), "NGA", "Nigeria", controls, values, preset)
        score = next(m for m in app.metric if m.label == "Composite score (of 100)")
        rank = next(m for m in app.metric if m.label.startswith("Global rank (of "))
        assert (score.value, score.delta) == (result["score_value"], result["score_change"])
        assert (rank.value, rank.delta) == (str(result["rank"]), result["places"])
        assert rank.label == f"Global rank (of {result['n_ranked']})"
        assert result["caption"] in [c.value for c in app.caption]
    app.button(key="whatif_reset").click()
    app.query_params["view"] = "ranking"  # the app is shared by every test: open the ranking of the region
    app.session_state["peer_group"] = "Region · Sub-Saharan Africa"
    run("Peers")
    peers = country.page_peers(table, ctx.scores, "NGA")
    region = peers["Region · Sub-Saharan Africa"]
    assert any(region["place"] in m.value and region["sr"].strip() in m.value for m in app.markdown)
    assert region["caption"] in [c.value for c in app.caption]
