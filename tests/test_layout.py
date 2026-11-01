"""Small screens, foldables and hostile input: what the browser sweeps found, kept from coming back.

The browser checks themselves (every page at fold-cover, unfolded, dual-screen and tabletop sizes) need Chromium, so
they live outside the test suite; these tests pin the pieces of the fixes that can be checked without a browser.
"""

import re
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from starlette.applications import Starlette
from starlette.testclient import TestClient

from prm import api, charts, config  # not prm.ui at import time: see conftest.py (the globe must register in the app)

ROOT = Path(__file__).resolve().parents[1]


def test_long_axis_titles_break_before_their_unit():
    assert charts._fit_title("Risk score (0 = lowest, 100 = highest)") == "Risk score<br>(0 = lowest, 100 = highest)"
    assert charts._fit_title("Countries") == "Countries"
    assert charts._fit_title("Already<br>two lines (x)") == "Already<br>two lines (x)"
    assert charts._fit_title(None) is None
    fig = charts._base(go.Figure(go.Bar(x=[1], y=["a"])).update_xaxes(title="A long title for a chart (units)"))
    assert fig.layout.xaxis.title.text == "A long title for a chart<br>(units)"


def test_no_one_line_axis_title_is_wider_than_a_phone_chart():
    # ~30 characters fit across the narrowest chart on a 344px cover screen, ~38 up the side of a 300px-tall one
    source = (ROOT / "prm" / "charts.py").read_text(encoding="utf-8")
    titles = re.findall(r'update_(x|y)axes\([^)]*?title="([^"]+)"', source)
    assert len(titles) > 12
    for axis, title in titles:
        fitted = charts._fit_title(title) if axis == "x" else charts._fit_title(title, 36)
        assert all(len(line) <= (30 if axis == "x" else 38) for line in fitted.split("<br>")), title


def test_short_names_for_chart_axes():
    assert config.short_name("St Vincent and the Grenadines") == "St Vincent & Gren."
    assert config.short_name("Kenya") == "Kenya"
    assert all(len(v) <= 18 for v in config.SHORT_NAMES.values())
    countries = pd.read_csv(ROOT / "data" / "snapshot" / "countries.csv")
    long = {n for n in countries["name"].astype(str) if len(n) > 18}
    assert long <= set(config.SHORT_NAMES), long - set(config.SHORT_NAMES)


def test_heatmap_rows_use_short_names_and_hover_keeps_the_full_one():
    df = pd.DataFrame({"name": ["St Vincent and the Grenadines", "Kenya"]})
    for key, _ in charts.ECON_COLUMNS:
        df[key] = [1.0, float("nan")]
        df[f"n_{key}"] = [40.0, float("nan")]
    fig = charts.econ_heatmap(df)
    assert list(fig.data[0].y) == ["St Vincent & Gren.", "Kenya"]
    assert "St Vincent and the Grenadines" in fig.data[0].hovertext[0][0]
    assert "Risk score: —" in fig.data[0].hovertext[1][0]


def test_card_grids_can_shrink_below_their_minimum():
    # repeat(auto-fill, minmax(270px, 1fr)) overflows a 280px cover screen; minmax(min(270px, 100%), 1fr) does not
    for path in (ROOT / "app_pages").glob("*.py"):
        assert not re.search(r"minmax\((\{\w+\}|\d+)px", path.read_text(encoding="utf-8")), path.name


def test_foldable_styles_are_injected():
    from prm import ui

    css = ui.FOLD_CSS
    assert "(horizontal-viewport-segments: 2)" in css and "(vertical-viewport-segments: 2)" in css
    assert "env(viewport-segment-left 1 0)" in css  # side by side: the page starts on the right screen
    assert "env(viewport-segment-top 0 1)" in css  # tabletop: the bar moves to the lower screen
    assert "@container sgdock (max-width: 360px)" in css  # cover screens
    assert "{FOLD_CSS}" in (ROOT / "prm" / "ui.py").read_text(encoding="utf-8")


def test_api_rejects_junk_without_echoing_it():
    client = TestClient(Starlette(routes=api.routes()))
    r = client.get("/api/v1/countries/" + "A" * 5000)
    assert r.status_code == 404 and len(r.json()["iso3"]) <= 12
    r = client.get("/api/v1/countries/%3Cscript%3E")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")
    assert client.get("/api/v1/countries?region=%00").json()["count"] == 0
    assert client.post("/api/v1/countries").status_code == 405


def test_unknown_tab_in_a_link_is_dropped(app):
    for page in ("app_pages/conflict.py", "app_pages/overview.py"):
        app.switch_page(page)
        app.query_params["tab"] = "<img src=x>"
        app.run()
        assert not app.exception, [str(e.value)[:200] for e in app.exception]
        assert "tab" not in app.query_params
