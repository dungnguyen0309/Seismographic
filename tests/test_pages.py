"""Smoke tests: every page (and every country tab) runs without an error, using the saved data snapshot."""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest  # the `app` fixture comes from conftest.py

ROOT = Path(__file__).resolve().parents[1]
PAGES = re.findall(r'st\.Page\("(app_pages/[^"]+)"', (ROOT / "streamlit_app.py").read_text(encoding="utf-8"))
COUNTRY_TABS = [":material/summarize: Summary", ":material/explore: In real life", ":material/groups: Peers",
                ":material/map: Map & refugees", ":material/tune: What-if", ":material/list_alt: Indicators",
                ":material/account_balance: Governance", ":material/monitoring: Economy", ":material/newspaper: News",
                ":material/edit_note: Assessment"]
CONFLICT_TABS = [":material/swords: Armed conflict", ":material/luggage: Displacement & refugees",
                 ":material/insights: Outlook"]
OVERVIEW_TABS = [":material/warning: Hotspots", ":material/trending_up: Changes",
                 ":material/format_list_numbered: Ranking", ":material/scatter_plot: Risk matrix"]


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
    readout = next(m.value for m in app.markdown if 'class="sg-read' in m.value)
    assert "Kenya" in readout


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
