"""The shared page data: news, events, videos, assessments, flows, hotspots (no network: fetchers are patched)."""

import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def read(base: Path, rel: str):
    return json.loads((base / rel).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ctx(tmp_path_factory):
    from staticbuild import common

    return common.load(tmp_path_factory.mktemp("web"))


def articles(n=3, tag="a"):
    return pd.DataFrame({
        "seen": pd.to_datetime([f"2026-11-2{i}T10:00:00Z" for i in range(n)]),
        "title": [f"{tag} headline {i}" for i in range(n)], "domain": ["example.org"] * n,
        "url": [f"https://example.org/{tag}{i}" for i in range(n)], "image": [None] + ["https://i.example/x.jpg"] * (n - 1),
    })


def test_news_files_and_status(ctx, monkeypatch):
    from prm import sources
    from staticbuild import news

    asked = []

    def fake(name):
        asked.append(name)
        return articles(), "Bing News + Google News"

    monkeypatch.setattr(sources, "fetch_news", fake)
    news.build(ctx)
    out = ctx.data / "news"
    g = read(out, "global.json")
    assert set(g) == {"fetched", "source", "items"} and g["source"] == "Bing News + Google News"
    assert set(g["items"][0]) == {"seen", "title", "domain", "url", "image"} and g["items"][0]["image"] is None
    assert g["items"][0]["seen"].startswith("2026-11-20")
    assert None in asked and "Ivory Coast" in asked and "DR Congo" in asked  # the news names the pages use
    assert (out / "NGA.json").is_file() and (out / "region-south-asia.json").is_file()
    assert '("South Asia" OR India OR Bangladesh OR "Sri Lanka" OR Nepal)' in asked
    status = read(out, "status.json")
    assert status["failed"] == 0 and status["ok"] == len(list(out.glob("*.json"))) - 1
    assert status["keys"]["NGA"] == "ok"


def test_news_keeps_last_good(ctx, monkeypatch):
    from prm import sources
    from staticbuild import news

    monkeypatch.setattr(sources, "fetch_news", lambda name: (articles(tag="good"), "Google News"))
    news.build(ctx)
    before = (ctx.data / "news" / "NGA.json").read_text(encoding="utf-8")

    def flaky(name):
        if name == "Nigeria":
            raise sources.SourceError("down")
        if name is None:
            return articles(0), "Google News"  # nothing returned
        return articles(tag="new"), "Google News"

    monkeypatch.setattr(sources, "fetch_news", flaky)
    news.build(ctx)
    out = ctx.data / "news"
    assert (out / "NGA.json").read_text(encoding="utf-8") == before
    assert read(out, "global.json")["items"][0]["title"] == "good headline 0"
    assert read(out, "SYR.json")["items"][0]["title"] == "new headline 0"
    status = read(out, "status.json")
    assert status["keys"]["NGA"] == "kept" and status["keys"]["global"] == "kept" and status["failed"] == 2


def test_news_failure_without_a_file_writes_nothing(ctx, monkeypatch, tmp_path):
    from prm import sources
    from staticbuild import common, news

    c = common.load(tmp_path)

    def fail(name):
        raise sources.SourceError("down")

    monkeypatch.setattr(sources, "fetch_news", fail)
    news.build(c)
    assert [p.name for p in (tmp_path / "data" / "news").glob("*.json")] == ["status.json"]
    assert read(tmp_path, "data/news/status.json")["ok"] == 0


def test_events_assessments_flows(ctx):
    from prm import content
    from staticbuild import assessments, events, flows

    events.build(ctx)
    ev = read(ctx.data, "events.json")
    assert ev["columns"] == content.EVENT_COLUMNS and len(ev["rows"]) == len(content.load_events())
    assert all(len(r[0]) == 10 and r[0][4] == "-" for r in ev["rows"])

    assessments.build(ctx)
    index = read(ctx.data, "assessments/index.json")
    files = {p.stem for p in (ROOT / "assessments").glob("*.md") if p.stem != "README" and not p.name.startswith("_")}
    assert set(index) == files
    syr = read(ctx.data, "assessments/SYR.json")
    original = content.load_assessments()["SYR"]
    assert syr["meta"] == original["meta"] and syr["body"] == original["body"] and syr["file"] == "SYR.md"
    assert index["SYR"]["outlook"] == original["meta"]["outlook"]

    flows.build(ctx)
    fl = read(ctx.data, "flows.json")
    assert fl["columns"] == ["origin", "host", "year", "value"] and len(fl["rows"]) == len(ctx.core["flows"])


def test_videos(ctx, monkeypatch):
    from prm import config, sources
    from staticbuild import videos

    def one(channels, kind):
        return pd.DataFrame({"video_id": ["v1"], "title": [f"{kind} t"], "published": [pd.Timestamp("2026-11-24", tz="UTC")],
                             "description": ["d"], "views": [5.0], "thumbnail": ["https://i.ytimg.com/vi/v1/mqdefault.jpg"],
                             "channel": ["C"], "kind": [kind]})

    monkeypatch.setattr(sources, "fetch_videos", one)
    videos.build(ctx)
    v = read(ctx.data, "videos.json")
    assert {i["kind"] for i in v["items"]} == {"news", "analysis", "institutions"}
    assert set(v["items"][0]) == {"video_id", "title", "channel", "kind", "published", "description", "views", "thumbnail"}
    assert v["live"]["ABC News (US)"]["id"] == config.LIVE_CHANNELS["ABC News (US)"].id
    assert v["regions"] == config.LIVE_REGIONS and "USA" in v["aliases"]

    def down(channels, kind):
        raise sources.SourceError("down")

    monkeypatch.setattr(sources, "fetch_videos", down)
    videos.build(ctx)
    assert read(ctx.data, "videos.json")["items"] == v["items"]  # last good kept

    def half(channels, kind):  # "news" fails, the others answer with new titles
        if kind == "news":
            raise RuntimeError("odd")
        return one(channels, kind).assign(title=f"new {kind}")

    monkeypatch.setattr(sources, "fetch_videos", half)
    videos.build(ctx)
    got = {i["kind"]: i["title"] for i in read(ctx.data, "videos.json")["items"]}
    assert got == {"news": "news t", "analysis": "new analysis", "institutions": "new institutions"}


def test_write_json_is_atomic(tmp_path, monkeypatch):
    import json as js

    from staticbuild import common

    common.write_json("a.json", {"x": 1}, tmp_path)

    def boom(*a, **k):
        raise OSError("disk")

    monkeypatch.setattr(common.os, "replace", boom)
    with pytest.raises(OSError):
        common.write_json("a.json", {"x": 2}, tmp_path)
    assert js.loads((tmp_path / "a.json").read_text()) == {"x": 1} and [p.name for p in tmp_path.iterdir()] == ["a.json"]


def test_hotspots(ctx):
    from prm import hotspots, ui
    from staticbuild import hotspots as export

    export.build(ctx)
    out = ctx.data / "hotspots"
    h = hotspots.load()
    assert read(out, "meta.json") == h["meta"]
    table = ui.master_table(ctx.core, ctx.values, ctx.scores, ctx.history)
    expected = hotspots.board(table, h["monthly"], h["cells"], hotspots.escalation(h["gdelt"]))
    board = read(out, "board.json")
    assert board["columns"] == list(expected.columns) and len(board["rows"]) == len(expected)
    assert [r[board["columns"].index("iso3")] for r in board["rows"]] == list(expected["iso3"])
    assert [r[board["columns"].index("deaths_90d")] for r in board["rows"]] == list(expected["deaths_90d"])
    for name, df in (("monthly", h["monthly"]), ("cells", h["cells"]), ("gdelt", h["gdelt"])):
        t = read(out, f"{name}.json")
        assert t["columns"] == list(df.columns) and len(t["rows"]) == len(df)
    sig = read(out, "signal.json")
    assert sig["columns"][0] == "iso3" and set(hotspots.SIGNAL_COLUMNS) <= set(sig["columns"])


def test_partial_builds_keep_the_site_year(tmp_path, monkeypatch):
    from prm import data
    from staticbuild import common

    monkeypatch.setattr(data, "analysis_year", lambda: 2027)  # 1 January: the weekly rebuild has not run yet
    assert common.keep_site_year(tmp_path) is None and data.analysis_year() == 2027  # no site yet: today's year
    (tmp_path / "data").mkdir()
    (tmp_path / "data/meta.json").write_text('{"year": 2026}')
    assert common.keep_site_year(tmp_path) == 2026 and data.analysis_year() == 2026
    assert data.history_years()[-1] == 2026
