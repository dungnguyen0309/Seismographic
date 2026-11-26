"""The reference pages' data: glossary, sources, video channels, methodology inputs and the Fragile States Index
benchmark (no network: the FSI download is patched)."""

import json

import pandas as pd
import pytest


def read(base, rel: str):
    return json.loads((base / rel).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ctx(tmp_path_factory):
    from staticbuild import common

    return common.load(tmp_path_factory.mktemp("web"))


def fake_fsi(ctx, year=2023):
    """An FSI edition that ranks countries exactly as our composite for `year` does (plus one we do not score)."""
    ours = ctx.history[ctx.history["year"] == year].dropna(subset=["composite"])
    return pd.DataFrame({"fsi_name": ours["iso3"], "iso3": ours["iso3"], "year": year,
                         "total": ours["composite"] * 1.2}).reset_index(drop=True)


def test_reference_files(ctx, monkeypatch):
    from prm import config, glossary, hotspots, sources
    from staticbuild import reference

    monkeypatch.setattr(sources, "fetch_fsi", lambda url, countries: fake_fsi(ctx))
    reference.build(ctx)
    out = ctx.data / "reference"

    g = read(out, "glossary.json")
    assert [c["name"] for c in g["categories"]] == list(glossary.all_terms())
    first = g["categories"][0]
    assert first["color"] == glossary.CATEGORIES[first["name"]].color and len(first["terms"]) == 34
    assert first["terms"][0] == {"term": "Composite score", "definition": glossary.TERMS["Scores & ratings"][0][1],
                                 "tags": [], "pillar": None,
                                 "link": {"url": config.SOURCES["oecd_jrc"].url, "label": "OECD/JRC Handbook"}}
    inds = g["categories"][1]
    assert inds["name"] == glossary.INDICATORS_CATEGORY and len(inds["terms"]) == len(config.INDICATORS)
    assert inds["terms"][0]["link"]["label"] == "See the data" and inds["terms"][0]["pillar"] == "stability"
    assert set(g["scales"]) == {"composite", "pillars", "change", "next_event"}
    assert len(g["scales"]["composite"]) == 5 and g["scales"]["composite"][0].startswith("rgb(")
    assert g["scales"]["change"] == [c for _, c in config.CHANGE_COLORSCALE]

    s = read(out, "sources.json")
    assert [c["key"] for c in s["index_cards"]] == config.INDEX_SOURCES
    wgi = s["index_cards"][0]
    assert wgi["status"].startswith("Loaded now: source updated ") and wgi["indicators"][0]["label"] == "Political stability"
    rows = s["indicators"]
    assert rows["columns"] == ["Pillar", "Indicator", "Original source", "Series code", "Most common data year",
                               "Source updated", "Status", "Data"]
    assert len(rows["rows"]) == len(config.INDICATORS)
    bd = rows["rows"][[i.key for i in config.INDICATORS].index("battle_deaths_100k")]
    assert bd[3] == "derived from battle_deaths and population" and isinstance(bd[4], int)
    assert len(s["channels"]) == (len(config.NEWS_VIDEO_CHANNELS) + len(config.ANALYSIS_VIDEO_CHANNELS)
                                  + len(config.INSTITUTION_VIDEO_CHANNELS))
    assert s["channels"][0]["Content"] == "24/7 live stream and news reports"
    assert s["channels"][-1] == {"Channel": "Human Rights Watch", "Content": "Institutional briefings", "Region": "—",
                                 "Based in": "United States", "Ownership": "Non-profit NGO",
                                 "YouTube": f"https://www.youtube.com/channel/{config.INSTITUTION_VIDEO_CHANNELS['Human Rights Watch']}"}
    assert s["cite"]["author"] == "Nguyen, T. D." and "," in s["cite"]["edition"] and ")" not in s["cite"]["edition"]

    v = read(out, "video.json")
    assert v["regions"] == config.LIVE_REGIONS and set(v["live"]) == set(config.LIVE_CHANNELS)
    assert v["live"]["CGTN"] == {"id": config.LIVE_CHANNELS["CGTN"].id, "region": "Asia-Pacific", "origin": "China",
                                 "funding": "State-owned"}
    assert v["news_names"] == config.NEWS_NAMES

    m = read(out, "methodology.json")
    assert m["escalation"] == {"window_days": hotspots.WINDOW_DAYS, "recent_days": hotspots.RECENT_DAYS,
                               "escalating_ratio": hotspots.ESCALATING_RATIO, "escalating_z": hotspots.ESCALATING_Z,
                               "mad_scale": hotspots.MAD_SCALE, "easing_ratio": hotspots.EASING_RATIO,
                               "min_articles_7d": hotspots.MIN_ARTICLES_7D}
    assert m["conflict"]["last"] == int(ctx.core["series"]["battle_deaths"]["year"].max())

    f = read(out, "fsi.json")
    assert f == {"compared": len(fake_fsi(ctx)), "spearman": pytest.approx(1.0), "top20_overlap": 20, "year": 2023}


def test_conflict_years_rebuild_the_onset_panel(ctx, monkeypatch):
    """The exported conflict years are all the track record needs: the panel rebuilt from them is the app's."""
    from prm import sources, validation
    from staticbuild import reference

    monkeypatch.setattr(sources, "fetch_fsi", lambda url, countries: fake_fsi(ctx))
    reference.build(ctx)
    conflict = read(ctx.data, "reference/methodology.json")["conflict"]
    hist = ctx.history
    for score in ("stability", "composite"):
        want = validation.onset_panel(hist, ctx.core["series"]["battle_deaths"], score)
        rows = []
        for year in sorted(hist["year"].unique()):
            if year + 1 > conflict["last"]:
                continue
            now, nxt = (set(conflict["years"].get(str(y), [])) for y in (year, year + 1))
            frame = hist[hist["year"] == year][["iso3", score]].dropna()
            rows += [(i, year, s, i in nxt) for i, s in zip(frame["iso3"], frame[score]) if i not in now]
        got = pd.DataFrame(rows, columns=["iso3", "year", "score", "onset"])
        assert got["iso3"].tolist() == want["iso3"].tolist() and got["onset"].tolist() == want["onset"].tolist()
        assert got["score"].tolist() == want["score"].tolist() and got["year"].tolist() == want["year"].tolist()


def test_fsi_keeps_the_last_good_file(ctx, monkeypatch):
    from prm import sources
    from staticbuild import reference

    monkeypatch.setattr(sources, "fetch_fsi", lambda url, countries: fake_fsi(ctx))
    reference.build(ctx)
    path = ctx.data / "reference" / "fsi.json"
    before = path.read_text(encoding="utf-8")

    def down(url, countries):
        raise sources.SourceError("Fragile States Index: down")

    monkeypatch.setattr(sources, "fetch_fsi", down)
    reference.build(ctx)
    assert path.read_text(encoding="utf-8") == before
    monkeypatch.setattr(sources, "fetch_fsi", lambda url, countries: fake_fsi(ctx).iloc[0:0])
    reference.build(ctx)
    assert path.read_text(encoding="utf-8") == before


def test_fsi_failure_without_a_file_writes_none(monkeypatch, tmp_path):
    from prm import sources
    from staticbuild import common, reference

    def down(url, countries):
        raise sources.SourceError("Fragile States Index: down")

    monkeypatch.setattr(sources, "fetch_fsi", down)
    reference.build(common.load(tmp_path))
    out = tmp_path / "data" / "reference"
    assert not (out / "fsi.json").exists() and (out / "methodology.json").is_file()


def test_no_per_country_fsi_value(ctx, monkeypatch):
    from prm import sources
    from staticbuild import reference, validate

    monkeypatch.setattr(sources, "fetch_fsi", lambda url, countries: fake_fsi(ctx))
    reference.build(ctx)
    reference.fixtures(ctx)
    files = [*(ctx.data / "reference").glob("*.json"), *(ctx.web / "tests" / "fixtures").glob("reference_*.json")]
    assert len(files) >= 9
    for path in files:
        doc = read(path.parent, path.name)
        assert validate.fsi_fields(doc, path.name) == []
    assert set(read(ctx.data, "reference/fsi.json")) == {"compared", "spearman", "top20_overlap", "year"}
