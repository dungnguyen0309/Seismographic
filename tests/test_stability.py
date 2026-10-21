"""Stability: the app degrades gracefully when sources fail, data files are odd or a section breaks."""

import time

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from prm import api, content, data, sources


def test_guard_keeps_the_rest_of_the_page(monkeypatch):
    monkeypatch.setenv("PRM_RAISE_ERRORS", "0")

    def script():
        import streamlit as st
        from prm import ui
        with ui.guard("The news"):
            raise ValueError("boom")
        st.write("still here")

    at = AppTest.from_function(script).run()
    assert not at.exception
    assert any("can't be shown" in c.value for c in at.caption)
    assert any("still here" in m.value for m in at.markdown)


def test_page_error_boundary_shows_a_way_out(monkeypatch):
    monkeypatch.setenv("PRM_RAISE_ERRORS", "0")

    def script():
        from prm import ui

        def broken_page():
            raise KeyError("missing column")

        ui.page_error_boundary(broken_page)

    at = AppTest.from_function(script).run()
    assert not at.exception
    assert at.error and "Something went wrong" in at.error[0].value
    assert at.button(key="sg_retry")


def test_strict_mode_raises(monkeypatch):
    monkeypatch.setenv("PRM_RAISE_ERRORS", "1")

    def script():
        from prm import ui
        with ui.guard("x"):
            raise ValueError("boom")

    assert AppTest.from_function(script).run().exception


def test_truncated_downloads_are_rejected():
    saved = pd.DataFrame({"iso3": [f"C{i:02d}" for i in range(100)], "value": 1.0})
    assert data.plausible(saved.head(90), saved)
    assert not data.plausible(saved.head(20), saved)
    assert not data.plausible(pd.DataFrame(), saved)
    assert data.plausible(saved, None)


def test_failed_sources_are_retried_later_not_cached(monkeypatch):
    calls = []

    def failing(name):
        calls.append(name)
        raise sources.SourceError("GDELT: 429")

    monkeypatch.setattr(sources, "fetch_gdelt_tone", failing)
    data._failures.clear()
    df, error = data.load_tone("Testland")
    assert df is None and "429" in error
    data.load_tone("Testland")
    assert len(calls) == 1, "a failed source waits RETRY_AFTER seconds before the next try"
    data._failures[("tone", "Testland")] = (time.time() - data.RETRY_AFTER - 1, "old")
    monkeypatch.setattr(sources, "fetch_gdelt_tone", lambda name: pd.DataFrame({"date": [], "tone": []}))
    df, error = data.load_tone("Testland")
    assert error is None and df is not None and ("tone", "Testland") not in data._failures


def test_unexpected_errors_become_messages(monkeypatch):
    def broken(name):
        raise KeyError("items")

    monkeypatch.setattr(sources, "fetch_gdelt_protests", broken)
    data._failures.clear()
    df, error = data.load_protests("Testland")
    assert df is None and "unexpected" in error


def test_events_with_typos_are_normalised(tmp_path, monkeypatch):
    path = tmp_path / "events.csv"
    path.write_text("date,iso3,country,event,category,significance,source_url,notes\n"
                    "2030-01-01,ken,Kenya,Vote,election?,HIGH,,\n"
                    "not a date,KEN,Kenya,Bad,Election,Low,,\n", encoding="utf-8")
    monkeypatch.setattr(content, "EVENTS_PATH", path)
    events = content.load_events()
    assert len(events) == 1
    row = events.iloc[0]
    assert row["iso3"] == "KEN" and row["significance"] == "High" and row["category"] == "Other"


def test_refresh_has_a_cooldown():
    store = data._live_store()
    saved = dict(store)
    try:
        store.update(core={"version": "test"}, fetched_at=time.time() - 30, attempted_at=0.0, thread=None)
        assert "already up to date" in data.refresh()
    finally:
        store.clear()
        store.update(saved)


def test_api_answers_json_when_the_data_fails(monkeypatch):
    from starlette.applications import Starlette
    from starlette.testclient import TestClient

    def broken():
        raise RuntimeError("no data")

    monkeypatch.setattr(api, "_bundle", broken)
    response = TestClient(Starlette(routes=api.routes())).get("/api/v1/countries")
    assert response.status_code == 503 and "error" in response.json()
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("text", ["gdp_growth:abc", "inflation:1e400", ":::", "foo:3", "gov_debt:-999", ""])
def test_bad_stress_links_are_ignored_or_clamped(text):
    from prm import stress
    shocks = stress.decode(text)
    for key, value in shocks.items():
        shock = stress.SHOCK_BY_KEY[key]
        assert shock.low <= value <= shock.high


def test_a_broken_download_is_never_shown():
    core = data._snapshot_core()
    assert data.health_problem(core) is None
    truncated = {**core, "series": {k: v.head(30) for k, v in core["series"].items()}}
    assert "scores only" in data.health_problem(truncated)
    renamed = {**core, "series": {**core["series"],
                                  "inflation": core["series"]["inflation"].rename(columns={"value": "val"})}}
    assert "could not be scored" in data.health_problem(renamed)


def test_a_failed_download_keeps_the_current_data(monkeypatch):
    store = {"core": None, "fetched_at": 0.0, "attempted_at": 0.0, "thread": None, "error": None,
             "lock": __import__("threading").Lock()}
    core = data._snapshot_core()
    monkeypatch.setattr(data, "LIVE_START_DELAY", 0)
    monkeypatch.setattr(data, "_fetch_live_core",
                        lambda: {**core, "series": {k: v.head(5) for k, v in core["series"].items()}})
    data._download(store)
    assert store["core"] is None and "scores only" in store["error"]


def _store():
    return {"core": None, "fetched_at": 0.0, "attempted_at": 0.0, "thread": None, "error": None,
            "lock": __import__("threading").Lock()}


def _core_with_failures(failed: set[str]):
    core = data._snapshot_core()
    meta = {k: {**m, "from_snapshot": k in failed, "error": "down" if k in failed else None}
            for k, m in core["meta"].items()}
    return {**core, "meta": meta, "source": "live"}


def test_when_no_source_answers_the_snapshot_stays(monkeypatch):
    store, core = _store(), _core_with_failures(set(data._snapshot_core()["meta"]))
    monkeypatch.setattr(data, "LIVE_START_DELAY", 0)
    monkeypatch.setattr(data, "_fetch_live_core", lambda: core)
    data._download(store)
    assert store["core"] is None and "none of the data sources" in store["error"]


def test_a_partial_download_is_used_but_retried_within_the_hour(monkeypatch):
    store, core = _store(), _core_with_failures({"inflation"})
    monkeypatch.setattr(data, "LIVE_START_DELAY", 0)
    monkeypatch.setattr(data, "_fetch_live_core", lambda: core)
    data._download(store)
    assert store["core"] is core and store["error"] is None
    age = time.time() - store["fetched_at"]
    assert data.CACHE_TTL - age <= data.PARTIAL_RETRY + 5
