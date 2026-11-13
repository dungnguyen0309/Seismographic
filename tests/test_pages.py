"""Smoke tests: every page (and every country tab) runs without an error, using the saved data snapshot."""

import re
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest  # the `app` fixture comes from conftest.py

from prm import hotspots

ROOT = Path(__file__).resolve().parents[1]
PAGES = re.findall(r'st\.Page\("(app_pages/[^"]+)"', (ROOT / "streamlit_app.py").read_text(encoding="utf-8"))
COUNTRY_TABS = ["Summary", "Peers", "What-if", "Data", "News", "Assessment"]  # Assessment comes second when there is one
CONFLICT_TABS = [":material/swords: Armed conflict", ":material/luggage: Displacement & refugees",
                 ":material/insights: Outlook"]
OVERVIEW_TABS = [":material/warning: Hotspots", ":material/trending_up: Changes",
                 ":material/format_list_numbered: Ranking", ":material/scatter_plot: Risk matrix"]
CHANGES_TABS = ["Moves", "Map", "Tiers", "Drivers", "Red flags"]
HOTSPOT_TABS = ["Board", "Map", "Calendar"]


def errors(at: AppTest) -> list[str]:
    return [str(e.value)[:300] for e in at.exception]


def test_pages_are_found():
    assert len(PAGES) >= 18


@pytest.mark.parametrize("page", PAGES)
def test_page_runs(app, page):
    app.switch_page(page)
    app.run()
    assert not errors(app), errors(app)


@pytest.mark.parametrize("tab", COUNTRY_TABS)
def test_country_tab_runs(app, tab):
    app.switch_page("app_pages/country.py")
    app.session_state["country_tab"] = tab
    app.run()
    assert not errors(app), errors(app)


def test_country_picker_updates_the_dock(app):
    app.switch_page("app_pages/country.py")
    app.run()
    app.selectbox(key="country_pick").select("KEN").run()
    assert not any('class="sg-read' in m.value for m in app.markdown)  # the profile header shows it instead
    app.switch_page("app_pages/overview.py")
    app.run()
    readout = next(m.value for m in app.markdown if 'class="sg-read' in m.value)
    assert "Kenya" in readout


def test_calendar_shows_maintainer_tools_only_with_the_flag(app, monkeypatch):
    app.switch_page("app_pages/hotspots.py")
    app.session_state["hs_tab"] = "Calendar"
    monkeypatch.delenv("SEISMOGRAPHIC_MAINTAINER", raising=False)
    app.run()
    assert not errors(app), errors(app)
    assert not any("data/events.csv" in e.label for e in app.expander)
    monkeypatch.setenv("SEISMOGRAPHIC_MAINTAINER", "1")
    app.run()
    assert not errors(app), errors(app)
    assert any("data/events.csv" in e.label for e in app.expander)


@pytest.mark.parametrize("tab", HOTSPOT_TABS)
def test_hotspots_tab_runs(app, tab):
    app.switch_page("app_pages/hotspots.py")
    app.session_state["hs_tab"] = tab
    app.run()
    assert not errors(app), errors(app)


def hotspot_cards(at: AppTest) -> list[str]:
    return [m.value for m in at.markdown if 'class="sg-hs"' in m.value]


def with_news(monkeypatch, rows: list[tuple[str, int, int]]) -> None:
    """Real hotspot files plus made-up GDELT days: (iso3, daily count before, daily count in the last week)."""
    real, days = hotspots.load(), pd.date_range("2026-08-14", periods=hotspots.WINDOW_DAYS)
    gdelt = pd.DataFrame([(iso3, d.strftime("%Y-%m-%d"), before if i < len(days) - hotspots.RECENT_DAYS else after,
                           10_000) for iso3, before, after in rows for i, d in enumerate(days)],
                         columns=hotspots.GDELT_COLUMNS)
    monkeypatch.setattr(hotspots, "load", lambda: {**real, "gdelt": gdelt})


def test_hotspots_status_filter_waits_for_news_data(app, monkeypatch):
    with_news(monkeypatch, [])
    app.switch_page("app_pages/hotspots.py")
    app.session_state["hs_tab"] = "Board"
    app.run()
    assert not errors(app), errors(app)
    assert app.button_group(key="hs_status").disabled
    assert all("No conflict-news data yet" in c and ">Quiet</span>" not in c for c in hotspot_cards(app))


def test_hotspots_board_shows_cards_and_filters_by_status(app, monkeypatch):
    with_news(monkeypatch, [("UKR", 40, 120), ("YEM", 30, 30), ("NGA", 60, 20), ("PAK", 1, 1)])
    app.switch_page("app_pages/hotspots.py")
    app.session_state["hs_tab"] = "Board"
    app.run()
    assert not errors(app), errors(app)
    cards = hotspot_cards(app)
    assert cards and any(b.key and b.key.startswith("hs_open_") for b in app.button)  # the real snapshot has some
    for status in ["Escalating", "Steady", "Easing", "Quiet"]:
        app.button_group(key="hs_status").set_value(status).run()
        assert not errors(app), errors(app)
        shown = hotspot_cards(app)
        # a country with no news data is filed as Quiet but shows no status word
        assert all(f">{status}</span>" in c or "No conflict-news data yet" in c for c in shown), status
        assert shown, status  # the made-up news gives every status a card
    app.button_group(key="hs_status").set_value("All").run()
    assert len(hotspot_cards(app)) == len(cards)


def test_hotspots_without_ucdp_files_say_no_data(app, monkeypatch):
    empty = {"monthly": pd.DataFrame(columns=hotspots.MONTHLY_COLUMNS), "cells": pd.DataFrame(columns=hotspots.CELL_COLUMNS),
             "gdelt": pd.DataFrame(columns=hotspots.GDELT_COLUMNS), "meta": {}}
    monkeypatch.setattr(hotspots, "load", lambda: empty)
    app.switch_page("app_pages/hotspots.py")
    app.session_state["hs_tab"] = "Board"
    app.run()
    assert not errors(app), errors(app)
    assert [m.value for m in app.metric][2:] == ["—", "—"]
    assert all("No UCDP data" in c for c in hotspot_cards(app))


def test_old_watchlist_links_open_the_calendar(app):
    sources = [*ROOT.glob("app_pages/*.py"), *ROOT.glob("prm/*.py"), ROOT / "streamlit_app.py"]
    assert not (ROOT / "app_pages" / "watchlist.py").exists()
    assert not [p.name for p in sources if "app_pages/watchlist.py" in p.read_text(encoding="utf-8")]
    app.switch_page("app_pages/regions.py")
    app.run()
    link = next(p.proto for p in app.get("page_link") if p.proto.label == "Full event calendar")
    assert "hotspots" in link.page and link.query_string == "tab=calendar"
    app.switch_page("app_pages/hotspots.py")
    app.session_state["hs_tab"] = "Board"
    app.run()
    app.query_params["tab"] = "calendar"  # what the link opens
    app.run()
    assert not errors(app), errors(app)
    assert app.session_state["hs_tab"] == "Calendar"
    app.session_state["hs_tab"] = "Board"
    app.run()


@pytest.mark.parametrize("tab", CONFLICT_TABS)
def test_conflict_tab_runs(app, tab):
    app.switch_page("app_pages/conflict.py")
    app.session_state["conflict_tab"] = tab
    app.run()
    assert not errors(app), errors(app)


@pytest.mark.parametrize("tab", OVERVIEW_TABS)
def test_overview_tab_runs(app, tab):
    app.switch_page("app_pages/overview.py")
    app.session_state["ov_tab"] = tab
    app.run()
    assert not errors(app), errors(app)


@pytest.mark.parametrize("tab", OVERVIEW_TABS)
def test_overview_tab_runs_with_a_region_filter(app, tab):  # the Risk matrix draws a region table only then
    app.switch_page("app_pages/overview.py")
    app.session_state["ov_region"] = "South Asia"
    app.session_state["ov_tab"] = tab
    try:
        app.run()
        assert not errors(app), errors(app)
    finally:
        app.session_state["ov_region"] = "All regions"


def page_title(at: AppTest) -> str:
    return next(m.value for m in at.markdown if 'class="sg-head-title"' in m.value)


def test_find_opens_pages_and_countries(app):
    app.switch_page("app_pages/overview.py")
    app.session_state["_jump_to"] = "page:stress"  # what picking "Stress test · page" in Find leaves for the next run
    app.run()
    assert not errors(app), errors(app)
    assert ">Stress test<" in page_title(app)
    app.session_state["_jump_to"] = "KEN"
    app.run()
    assert not errors(app), errors(app)
    assert app.session_state["country"] == "KEN"


def test_weights_travel_in_the_link(app):
    from prm import ui
    from prm.config import PILLARS

    assert ui.decode_weights("50,20,20,10") == {"stability": 50, "governance": 20, "economic": 20, "social": 10}
    assert all(ui.decode_weights(bad) is None for bad in ["", "50,20,20", "51,20,20,10", "0,0,0,0", "a,b,c,d", None])
    app.switch_page("app_pages/overview.py")
    if "_weights_from_link" in app.session_state:
        del app.session_state["_weights_from_link"]
    app.query_params["w"] = "50,20,20,10"
    app.run()
    assert not errors(app), errors(app)
    assert app.session_state["w_stability"] == 50 and app.session_state["w_social"] == 10
    assert any("Scores use your pillar weights" in c.value for c in app.caption)
    for p in PILLARS:  # the defaults doubled: the same proportions, so no note and no ?w= in the link
        app.session_state[ui.WEIGHT_KEYS[p.key]] = p.default_weight * 2
    app.run()
    assert not any("Scores use your pillar weights" in c.value for c in app.caption)
    assert "w" not in app.query_params
    for p in PILLARS:  # back to the defaults for the other tests
        app.session_state[ui.WEIGHT_KEYS[p.key]] = p.default_weight
    app.run()
    assert not any("Scores use your pillar weights" in c.value for c in app.caption)


def test_bottom_bar_on_a_page_that_stops_early(app):
    # Compare with nothing picked calls st.stop(); the bar is drawn after the page and must still appear
    app.switch_page("app_pages/stress.py")
    app.run()
    app.switch_page("app_pages/compare.py")
    app.session_state["compare_picked"] = []
    app.run()
    assert not errors(app), errors(app)
    assert any("Choose at least one country" in i.value for i in app.info)
    assert any('class="sg-read' in m.value for m in app.markdown)
    app.switch_page("app_pages/intro.py")  # leave a page without the compare widget, for the next tests
    app.run()


def test_builder_draft_survives_another_page(app):
    # Streamlit drops a page's widgets when you leave it; the builder once lost a half-written assessment that way
    app.switch_page("app_pages/builder.py")
    app.run()
    app.text_area(key="b_bluf").input("Risk rises as reserves fall.").run()
    app.text_area(key="drv_economic").input("My own analysis.").run()
    app.switch_page("app_pages/overview.py")
    app.run()
    app.switch_page("app_pages/builder.py")
    app.run()
    assert not errors(app), errors(app)
    assert app.text_area(key="b_bluf").value == "Risk rises as reserves fall."
    assert not any("default value" in w.value for w in app.warning)
    next(b for b in app.button if b.label == "Fill in the latest figures").click().run()
    assert app.text_area(key="drv_economic").value == "My own analysis."  # filling in never overwrites analysis
    assert app.text_area(key="drv_political").value  # an empty box gets the figures


def test_shared_comparison_link(app):
    app.switch_page("app_pages/compare.py")
    if "compare_picked" in app.session_state:
        del app.session_state["compare_picked"]
    app.query_params["c"] = "KEN,BRA"
    app.run()
    assert not errors(app), errors(app)
    assert list(app.multiselect(key="compare_picked").value) == ["KEN", "BRA"]


def test_stress_test_link_and_scenarios(app):
    app.switch_page("app_pages/stress.py")
    if "stress_scenario" in app.session_state:
        del app.session_state["stress_scenario"]
    app.query_params["shock"] = "gdp_growth:-4,inflation:5"
    app.run()
    assert not errors(app), errors(app)
    assert app.slider(key="stress_gdp_growth").value == -4 and app.slider(key="stress_inflation").value == 5
    assert app.selectbox(key="stress_scenario").value == "Custom"
    app.selectbox(key="stress_scenario").select("Pandemic shock (like 2020)").run()
    assert not errors(app), errors(app)
    assert app.slider(key="stress_gdp_growth").value == -5.5 and app.slider(key="stress_inflation").value == 0
    app.multiselect(key="stress_regions").select("Sub-Saharan Africa").run()
    assert not errors(app), errors(app)
    assert app.query_params["regions"] == "Sub-Saharan Africa"  # the link keeps who is hit
    # a region and an income group with no country in common hit nobody (it once hit every country)
    app.multiselect(key="stress_regions").set_value(["North America"]).run()
    app.multiselect(key="stress_incomes").set_value(["Low income"]).run()
    assert not errors(app), errors(app)
    assert app.metric[0].value == "0"


def test_outlook_link_opens_the_outlook_tab(app):
    app.switch_page("app_pages/conflict.py")
    app.query_params["tab"] = "outlook"
    app.run()
    assert not errors(app), errors(app)
    assert app.session_state["conflict_tab"] == CONFLICT_TABS[-1]


def test_comparison_link_with_repeats_and_junk(app):
    app.switch_page("app_pages/intro.py")
    app.run()
    if "compare_picked" in app.session_state:
        del app.session_state["compare_picked"]
    app.query_params["c"] = ",,zzz, ken,KEN,BRA,USA,CHN,IND,RUS,FRA"
    app.switch_page("app_pages/compare.py")
    app.run()
    assert not errors(app), errors(app)
    assert list(app.multiselect(key="compare_picked").value) == ["KEN", "BRA", "USA", "CHN", "IND", "RUS"]


def test_whatif_preset_stays_selected_until_reset(app):
    def run_whatif():  # the test tree can send back an older tab choice, so the tab is set on every run
        app.session_state["country_tab"] = "What-if"
        app.run()

    def governance_open():
        return next(e for e in app.expander if e.label == "Governance & Institutions").proto.expanded

    app.switch_page("app_pages/country.py")
    run_whatif()
    start = {s.key: s.value for s in app.slider if s.key and s.key.endswith(("wgi_va", "wgi_rl", "wgi_cc", "wgi_ge"))}
    app.button(key="preset_Democratic backsliding").click()
    run_whatif()
    assert not errors(app), errors(app)
    assert app.button(key="preset_Democratic backsliding").proto.type == "primary"
    assert governance_open()  # the edited pillar
    assert any(c.value.startswith("Scenario: Democratic backsliding.") for c in app.caption)
    rank = next(m for m in app.metric if m.label.startswith("Global rank (of "))
    assert rank.delta is None or re.fullmatch(r"\d+ places? (riskier|safer)", rank.delta), rank.delta
    assert any('class="sg-whatif-live"' in m.value for m in app.markdown)
    for key, value in start.items():  # every Governance value back at its start: the pillar stays open
        app.slider(key=key).set_value(value)
    run_whatif()
    assert len(start) == 4 and governance_open()
    app.button(key="whatif_reset").click()
    run_whatif()
    assert app.button(key="preset_Democratic backsliding").proto.type == "secondary"


def test_ranking_table_shows_rounded_scores_and_short_regions(app):
    app.switch_page("app_pages/overview.py")
    app.session_state["ov_tab"] = OVERVIEW_TABS[2]
    app.run()
    shown = next(d.value for d in app.dataframe if "region" in d.value.columns)
    assert "MENA, Afghanistan & Pakistan" in set(shown["region"])  # config.REGION_SHORT
    assert (shown["composite"].dropna() % 1 == 0).all()  # screen readers get the number shown, not 15 digits


@pytest.mark.parametrize("tab,key,view", [("Data", "data_view", "Indicators"), ("Data", "data_view", "Governance"),
                                          ("Data", "data_view", "Economy"), ("Peers", "peers_view", "Map & refugees"),
                                          ("Summary", "real_life", True)])
def test_country_view_runs(app, tab, key, view):
    app.switch_page("app_pages/country.py")
    app.session_state["country_tab"] = tab
    app.session_state[key] = view
    app.run()
    assert not errors(app), errors(app)
    assert app.session_state[key] == view


@pytest.mark.parametrize("old,tab,slug,key,view", [
    ("real", "Summary", "summary", "real_life", True), ("map", "Peers", "peers", "peers_view", "Map & refugees"),
    ("indicators", "Data", "data", "data_view", "Indicators"), ("governance", "Data", "data", "data_view", "Governance"),
    ("economy", "Data", "data", "data_view", "Economy")])
def test_old_tab_link_opens_the_merged_tab(app, old, tab, slug, key, view):
    app.switch_page("app_pages/country.py")
    app.session_state["country_tab"] = "News"
    app.run()
    app.query_params["tab"] = old  # a link made when this was its own tab
    app.run()
    assert not errors(app), errors(app)
    assert app.session_state["country_tab"] == tab
    assert app.session_state[key] == view  # ?tab=real also opens the real-life reading
    assert app.query_params["tab"] == slug
    assert app.query_params.get("view") == (None if old == "real" else old)


def test_country_tab_and_view_survive_a_new_country_and_another_tab(app):
    app.switch_page("app_pages/country.py")
    app.session_state["country"] = "KEN"  # no assessment
    app.session_state["country_tab"] = "News"
    app.run()
    app.selectbox(key="country_pick").select("SDN").run()  # an assessment moves its tab second: a new tab row
    assert not errors(app), errors(app)
    assert app.session_state["country_tab"] == "News" and app.query_params["tab"] == "news"
    app.session_state["country_tab"] = "Data"
    app.run()
    app.session_state["data_view"] = "Governance"
    app.run()
    assert app.query_params["view"] == "governance"
    app.session_state["country_tab"] = "News"
    app.run()
    assert "view" not in app.query_params  # ?view belongs to Data and Peers
    app.session_state["country_tab"] = "Data"
    app.run()
    assert app.session_state["data_view"] == "Governance" and app.query_params["view"] == "governance"
    app.query_params["view"] = "economy"  # a link, or Back
    app.run()
    assert not errors(app), errors(app)
    assert app.session_state["data_view"] == "Economy"
    app.session_state["country"] = "NGA"
    app.session_state["country_tab"] = "Summary"
    app.run()


def test_tabs_keep_the_open_tab_in_the_link(app):
    app.switch_page("app_pages/conflict.py")
    app.session_state["conflict_tab"] = CONFLICT_TABS[0]
    app.run()
    app.query_params["tab"] = "outlook"  # a link opens its tab
    app.run()
    assert app.session_state["conflict_tab"] == CONFLICT_TABS[2]
    app.session_state["conflict_tab"] = CONFLICT_TABS[1]  # opening a tab writes it into the link
    app.run()
    assert not errors(app), errors(app)
    assert app.query_params["tab"] == "displacement"
    del app.query_params["tab"]  # Back to the plain address: the first tab, and the link stays clean
    app.run()
    assert app.session_state["conflict_tab"] == CONFLICT_TABS[0] and "tab" not in app.query_params
    app.query_params["tab"] = "nonsense"  # junk is ignored, then replaced
    app.run()
    assert not errors(app), errors(app)
    assert app.session_state["conflict_tab"] == CONFLICT_TABS[0] and app.query_params["tab"] == "conflict"


@pytest.mark.parametrize("tab", CHANGES_TABS)
def test_changes_tab_runs(app, tab):
    app.switch_page("app_pages/changes.py")
    app.session_state["chg_tab"] = tab
    app.run()
    assert not errors(app), errors(app)
    assert ("chg_globe" in str(app._tree)) == (tab == "Map")  # the page's second globe is built only on its tab


def test_changes_link_opens_the_map(app):
    app.switch_page("app_pages/changes.py")
    app.session_state["chg_tab"] = CHANGES_TABS[0]
    app.run()
    app.query_params["tab"] = "map"
    app.run()
    assert not errors(app), errors(app)
    assert app.session_state["chg_tab"] == "Map" and "chg_globe" in str(app._tree)


def test_first_visit_tracks_no_country_and_keeps_the_introduction_link(app):
    saved = {k: app.session_state[k] for k in ("country", "_following") if k in app.session_state}
    for key in ("country", "_following", "_explored"):
        if key in app.session_state:
            del app.session_state[key]
    app.query_params.pop("country", None)

    def overview() -> tuple[bool, bool]:
        app.switch_page("app_pages/overview.py")
        app.run()
        assert not errors(app), errors(app)
        links = [p.proto.label for p in app.get("page_link")]
        return (any('class="sg-read' in m.value for m in app.markdown),
                any(label.startswith("Introduction") for label in links))

    assert overview() == (False, True)  # nothing tracked until the visitor picks a country
    app.switch_page("app_pages/changes.py")
    app.run()
    assert overview() == (False, True)  # another page is not the introduction: the link stays
    app.switch_page("app_pages/intro.py")
    app.run()
    assert overview() == (False, False)
    app.switch_page("app_pages/country.py")
    app.run()
    assert overview() == (False, False)  # the profile showed its fallback country; the visitor picked nothing
    app.switch_page("app_pages/country.py")
    app.run()
    app.selectbox(key="country_pick").select("KEN").run()
    readout, _ = overview()
    assert readout  # a picked country is tracked in the bottom bar
    for key, value in saved.items():
        app.session_state[key] = value


def test_tier_badges_rise_in_weight(app):
    from prm import ui

    low, elevated, severe = ui.tier_badge("Low"), ui.tier_badge("Elevated"), ui.tier_badge("Severe")
    assert "background:transparent" in low and "border:1px solid" in low and "box-shadow" not in low  # outlined
    assert "background:transparent" not in elevated and "box-shadow" not in elevated  # filled
    assert "background:transparent" not in severe and "box-shadow:0 0 0 2px" in severe  # filled, with a ring
    assert "No data" in ui.tier_legend()


@pytest.mark.parametrize("tab", OVERVIEW_TABS)
def test_overview_has_one_sources_line(app, tab):
    app.switch_page("app_pages/overview.py")
    app.session_state["ov_tab"] = tab
    app.run()
    assert not errors(app), errors(app)
    assert "High or Severe" not in next(m.value for m in app.markdown if "sg-head-sub" in m.value)  # the KPIs say it
    assert sum(c.value.startswith("Sources:") for c in app.caption) == 1


def test_thin_data_is_marked(app):
    app.switch_page("app_pages/overview.py")
    app.session_state["ov_tab"] = OVERVIEW_TABS[1]  # Changes
    app.run()
    names = [n for d in app.dataframe if "name" in d.value.columns for n in d.value["name"]]
    assert any(str(n).endswith(" (limited data)") for n in names), names  # e.g. Tuvalu: no social pillar

    import pandas as pd

    from prm import charts
    frame = pd.DataFrame({"iso3": ["TUV", "KEN"], "name": ["Tuvalu", "Kenya"], "delta_1y": [5.0, -2.0],
                          "prev_composite": [40.0, 50.0], "composite": [45.0, 48.0], "thin": [True, False]})
    bar = charts.change_bars(frame).data[0]
    assert list(bar.y) == ["Kenya", "Tuvalu"]  # plain names: the label room stays small on a phone
    assert list(bar.marker.pattern.shape) == ["", "/"] and bar.customdata[1][-1] == "TUV"  # iso3 last, for clicks


def test_overview_flat_map_runs(app):
    app.switch_page("app_pages/overview.py")
    app.run()
    style = next(b for b in app.button_group if b.label == "Map style")
    style.set_value("Flat map").run()
    assert not errors(app), errors(app)
    next(s for s in app.selectbox if s.label == "Map shows").set_value("stability").run()
    assert not errors(app), errors(app)
    next(s for s in app.selectbox if s.label == "Map shows").set_value("composite").run()
    next(b for b in app.button_group if b.label == "Map style").set_value("3D globe").run()
    assert not errors(app), errors(app)


def test_assessment_comes_second_and_the_header_opens_it(app):
    app.switch_page("app_pages/country.py")
    before = app.session_state["country"] if "country" in app.session_state else "NGA"
    app.session_state["country"] = "SDN"  # Sudan has an assessment
    app.session_state["country_tab"] = "Summary"
    app.run()
    app.query_params["tab"] = "assessment"
    app.run()
    assert not errors(app), errors(app)
    assert app.session_state["country_tab"] == "Assessment"
    assert [t.label for t in app.tabs][:2] == ["Summary", "Assessment"]
    assert any(c.value.startswith("By ") for c in app.caption)
    assert not any("assessments/" in c.value for c in app.caption)  # the byline names no file
    app.session_state["country_tab"] = "Summary"
    app.run()
    app.button(key="country_analyst_open").click().run()  # "Analyst: <tier>" in the header
    assert not errors(app), errors(app)
    assert app.session_state["country_tab"] == "Assessment"
    app.session_state["country"] = before
    app.session_state["country_tab"] = "Summary"
    app.run()
