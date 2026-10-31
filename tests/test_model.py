"""Unit tests for the scoring model and the analysis helpers (fast, no network)."""

import numpy as np
import pandas as pd
import pytest

from prm import cases, config, data, forecast, glossary, report, scoring, validation


@pytest.fixture(scope="module")
def core():
    snapshot = data._snapshot_core()
    assert snapshot is not None, "data/snapshot is missing"
    return snapshot


@pytest.fixture(scope="module")
def values(core):
    return scoring.build_values(core["series"], core["countries"], data.analysis_year())


def test_scores_are_on_a_0_to_100_scale(values):
    scores = scoring.compute_scores(values)
    for col in ["composite", *[p.key for p in config.PILLARS]]:
        s = scores[col].dropna()
        assert len(s) > 150, f"too few countries scored on {col}"
        assert s.between(0, 100).all(), col
    assert set(scores["tier"].dropna()) <= set(config.TIER_ORDER)


def test_riskier_composite_means_a_better_rank(values):
    scores = scoring.compute_scores(values).dropna(subset=["composite"]).sort_values("composite", ascending=False)
    assert scores["rank"].is_monotonic_increasing


def test_weights_change_the_composite(values):
    stability_only = {p.key: (100.0 if p.key == "stability" else 0.0) for p in config.PILLARS}
    a = scoring.compute_scores(values)
    b = scoring.compute_scores(values, stability_only)
    both = a[["composite", "stability"]].join(b["composite"].rename("only"), how="inner").dropna()
    assert not np.allclose(both["composite"], both["only"])
    assert np.allclose(both["only"], both["stability"])


def test_red_flag_thresholds():
    row = pd.Series({"inflation": 25.0, "gov_debt": 120.0, "reserves_months": 1.5, "battle_deaths_raw": 2000})
    labels = {f["key"]: f["severity"] for f in scoring.red_flags(row)}
    assert labels["inflation"] == "serious"
    assert labels["gov_debt"] == "warning"
    assert labels["reserves_months"] == "serious"
    assert labels["battle_deaths_raw"] == "critical"
    assert scoring.red_flags(pd.Series({"inflation": 3.0})) == []


def test_saved_history_matches_a_fresh_build(core):
    if core.get("history_default") is None:
        pytest.skip("no saved history in the snapshot")
    fresh = data.build_default_history(core["series"], core["countries"])
    saved = core["history_default"]
    merged = fresh.merge(saved, on=["iso3", "year"], suffixes=("", "_saved"))
    assert len(merged) == len(fresh)
    assert np.allclose(merged["composite"].fillna(-1), merged["composite_saved"].fillna(-1), atol=1e-6)


def test_auc():
    scores = pd.Series([1, 2, 3, 4])
    assert validation.auc(scores, pd.Series([False, False, True, True])) == 1.0
    assert validation.auc(scores, pd.Series([True, True, False, False])) == 0.0
    assert validation.auc(scores, pd.Series([False] * 4)) is None


def test_onset_panel_counts_new_conflicts_only():
    hist = pd.DataFrame({"iso3": ["A", "B", "C"] * 2, "year": [2020] * 3 + [2021] * 3,
                         "stability": [80, 20, 50, 80, 20, 50]})
    deaths = pd.DataFrame({"iso3": ["A", "C", "C"], "year": [2021, 2020, 2021], "value": [100, 500, 500]})
    panel = validation.onset_panel(hist, deaths)
    # 2020 -> 2021 only (no data after 2021); C was already at war in 2020, so it is not a candidate
    assert set(panel["iso3"]) == {"A", "B"}
    assert panel.set_index("iso3").loc["A", "onset"] and not panel.set_index("iso3").loc["B", "onset"]


def test_track_record_beats_chance(core):
    panel = validation.onset_panel(core["history_default"], core["series"]["battle_deaths"])
    result = validation.summary(panel)
    assert result["onsets"] > 10
    assert result["auc"] > 0.6, "the stability pillar should rank countries before new conflicts better than chance"


def test_case_studies_have_readings(core):
    for case in cases.CASES:
        before = int(case.date[:4]) - 1
        reading = cases.reading(case, core["history_default"], scoring.build_values(core["series"], core["countries"], before))
        assert reading["verdict"] in cases.VERDICTS, case.key


def test_pdf_brief(core, values):
    from prm import content, interpret, ui
    year = data.analysis_year()
    scores = scoring.compute_scores(values)
    hist = core["history_default"]
    table = ui.master_table(core, values, scores, hist)
    reading = interpret.country_reading("NGA", table, values, scores, hist, content.load_events(), core.get("flows"), year)
    pdf = report.country_pdf(reading, table.set_index("iso3").loc["NGA"], hist[hist["iso3"] == "NGA"],
                             scoring.red_flags(values.loc["NGA"]), year)
    assert pdf.startswith(b"%PDF") and len(pdf) > 2000
    # every audience heading keeps its whole name (they once lost their first letters or word)
    markdown = interpret.reading_markdown(reading)
    for key, label in interpret.AUDIENCES.items():
        if reading.actions.get(key):
            assert f"## What to do: {label}\n" in markdown


def test_every_glossary_category_is_styled():
    terms = glossary.all_terms()
    assert set(terms) <= set(glossary.CATEGORIES)
    assert sum(len(v) for v in terms.values()) >= 100


def test_every_cited_source_exists():
    keys = [k for group in config.SOURCE_GROUPS.values() for k in group]
    keys += [k for group in config.CROSS_CHECKS.values() for k in group]
    keys += [s for s, _ in config.FLAG_BASIS.values() if s]
    keys += [k for c in glossary.CATEGORIES.values() for k in c.sources] + list(glossary.TERM_SOURCES.values())
    assert set(keys) <= set(config.SOURCES)


def test_outlook_model_is_tested_out_of_time_and_beats_chance(core):
    outlook = forecast.outlook(core["history_default"], core["series"]["battle_deaths"], data.analysis_year())
    assert outlook is not None
    assert outlook.auc > 0.75, "out-of-time accuracy should clearly beat a coin flip"
    assert outlook.brier_skill > 0, "predictions should beat the average rate"
    probs = outlook.predictions["probability"].dropna()
    assert probs.between(0, 1).all() and len(probs) > 100
    in_conflict = outlook.predictions[outlook.predictions["status"] == "In armed conflict"]
    assert in_conflict["probability"].isna().all()
    # each backtest year is predicted by a model that never saw it
    assert outlook.backtest["year"].min() >= config.HISTORY_START + forecast.MIN_TRAIN_YEARS


def test_logistic_fit_recovers_a_clear_signal():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(4000, 2))
    y = (rng.random(4000) < 1 / (1 + np.exp(-(-3 + 1.5 * x[:, 0])))).astype(float)
    w = forecast._fit(x, y, penalty=0.1)
    assert abs(w[1] - 1.5) < 0.3 and abs(w[2]) < 0.3


def test_similar_countries(values):
    scores = scoring.compute_scores(values)
    like = scoring.similar(scores, "NGA", n=5)
    assert len(like) == 5 and "NGA" not in like.index and like["distance"].is_monotonic_increasing


def test_fixed_yardstick_scoring_matches_the_index(values):
    a = scoring.compute_scores(values)
    b = scoring.compute_scores(values, reference=values)
    cols = ["composite", *[p.key for p in config.PILLARS]]
    assert np.allclose(a[cols].fillna(-1), b[cols].fillna(-1))


def test_stress_test(values):
    from prm import stress
    result = stress.run(values, scoring.default_weights(), {"gdp_growth": -4.0, "gov_debt": 10.0})
    s = stress.summary(result)
    assert s["countries"] > 150 and s["tier_up"] > 0 and s["tier_down"] == 0 and s["mean_delta"] > 0
    shrinking = result[result["new_flags"].map(lambda f: any("Shrinking" in x for x in f))]
    assert len(shrinking) and (values.loc[shrinking.index, "gdp_growth"] >= 0).all()
    # only the countries hit move
    scoped = stress.run(values, scoring.default_weights(), {"gdp_growth": -4.0}, scope={"KEN"})
    moved = scoped["delta"].abs() > 1e-9
    assert set(scoped.index[moved]) == {"KEN"}
    assert stress.decode(stress.encode({"gdp_growth": -4.0, "inflation": 5.0})) == {"gdp_growth": -4.0, "inflation": 5.0}


def test_open_data_tables(core, values):
    from prm import export
    hist = core["history_default"]
    tables = export.build(core, values, scoring.compute_scores(values), hist)
    assert set(tables) == set(export.TABLES)
    assert len(tables["index"]) > 150 and tables["index"]["rank"].dropna().is_monotonic_increasing
    assert {"iso3", "indicator", "value", "year", "risk_score"} <= set(tables["indicators"].columns)
    described = set(tables["dictionary"]["column"])
    for name in ("index", "indicators", "red_flags", "history"):
        assert set(tables[name].columns) <= described, name
    info = export.meta(core, data.analysis_year(), scoring.default_weights())
    assert export.to_excel(tables, info)[:2] == b"PK"
    assert b'"index"' in export.to_json(tables, info)


def test_json_api():
    from starlette.applications import Starlette
    from starlette.testclient import TestClient
    from prm import api
    client = TestClient(Starlette(routes=api.routes()))
    listing = client.get("/api/v1/countries?tier=severe").json()
    assert listing["count"] > 0 and all(c["tier"] == "Severe" for c in listing["countries"])
    one = client.get("/api/v1/countries/ken")
    assert one.status_code == 200 and one.json()["country"]["iso3"] == "KEN" and one.json()["history"]
    assert one.headers["access-control-allow-origin"] == "*"
    assert client.get("/api/v1/countries/XYZ").status_code == 404
    assert client.get("/api/v1").json()["endpoints"]


def test_news_filter_drops_off_topic_headlines():
    from prm import sources
    risk = [f"Troops clash with rebels in region {i}" for i in range(sources.MIN_ON_TOPIC)]
    df = pd.DataFrame({"title": [*risk, "Cat reunites with family after 571 days missing"]})
    assert "Cat reunites with family after 571 days missing" not in set(sources.on_topic(df)["title"])
    few = pd.DataFrame({"title": ["Election called", "Bank wins water award"]})
    assert len(sources.on_topic(few)) == 2  # too few on-topic headlines: keep the column full


def test_news_filter_drops_sport():
    from prm import sources
    risk = [f"Troops clash with rebels in region {i}" for i in range(sources.MIN_ON_TOPIC)]
    sport = "Former Purdue basketball player finds home in transfer portal after court battle"
    assert sport not in set(sources.on_topic(pd.DataFrame({"title": [*risk, sport]}))["title"])
