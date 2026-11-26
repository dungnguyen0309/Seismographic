"""The static export: core files, the static API (same payloads as prm/api.py) and the validator."""

import asyncio
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ["meta", "config", "countries", "values", "scores", "history", "master", "outlook", "wgi_trend"]


def run(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", *args], cwd=ROOT, capture_output=True, text=True)


def read(base: Path, rel: str):
    return json.loads((base / rel).read_text(encoding="utf-8"))


def col(table: dict, name: str) -> dict:
    i = table["columns"].index(name)
    return {r[0]: r[i] for r in table["rows"]}


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("web")
    done = run("staticbuild", "--only", "core", "--out", str(out))
    assert done.returncode == 0, done.stderr[-2000:]
    return out


def test_core_build(built, monkeypatch):
    from prm import config, data, scoring
    from staticbuild import common

    for name in CORE:
        assert (built / "data" / f"{name}.json").is_file(), name
    assert (built / "data/tokens.css").read_text().startswith(":root{--sg-bg:#000000;")
    scores = read(built, "data/scores.json")
    assert {"composite", "tier", "rank", "n_ranked", *(p.key for p in config.PILLARS)} <= set(scores["columns"])
    ctx = common.load(built)
    ctx.api_meta["generated"] = read(built, "data/meta.json")["built"]  # the one value that changes per run
    nga = col(scores, "composite")["NGA"]
    assert nga == pytest.approx(scoring.compute_scores(ctx.values)["composite"]["NGA"], abs=1e-9)
    assert "flag" not in read(built, "data/master.json")["columns"]
    manifest = read(built, "data/manifest.json")
    assert "data/scores.json" in manifest["files"] and manifest["built"]

    # the static country file is the payload prm/api.py answers with
    from prm import api

    monkeypatch.setattr(api, "_bundle", lambda: (ctx.tables, ctx.api_meta))
    request = SimpleNamespace(path_params={"iso3": "nga"})
    expected = json.loads(asyncio.run(api._country(request)).body)
    assert read(built, "api/v1/countries/NGA.json") == expected
    request = SimpleNamespace(query_params={"region": "south asia"})
    expected = json.loads(asyncio.run(api._countries(request)).body)
    assert read(built, "api/v1/countries.region-south-asia.json") == expected
    assert read(built, "api/v1/countries.json")["count"] == len(ctx.tables["index"])
    assert read(built, "api/v1/dictionary.json")["fields"]
    assert data.MIN_SCORED <= sum(v is not None for v in col(scores, "composite").values())


def matching(rules: list[dict], path: str, query: dict) -> str | None:
    """Vercel's rule: the first rewrite whose source, `has` and `missing` conditions all hold."""
    for rule in rules:
        if rule["source"] != path:
            continue
        if all(c["key"] in query and (("value" not in c) or re.search(c["value"], query[c["key"]]))
               for c in rule.get("has", [])) and not any(c["key"] in query for c in rule.get("missing", [])):
            return rule["destination"]
    return None


def test_vercel_filter_rules(built):
    rules = read(built, "vercel.json")["rewrites"]
    has = [r for r in rules if r.get("has")]
    assert len(rules) < 1024
    plain = rules.index({"source": "/api/v1/countries", "destination": "/api/v1/countries.json"})
    assert all(rules.index(r) < plain for r in has)
    assert all((built / r["destination"].lstrip("/")).is_file() for r in has)
    conds = [c for r in has for c in r["has"] + r.get("missing", [])]
    assert conds and not any("(?" in c.get("value", "") for c in conds)

    # every value matches its label in Python and in Node, whatever the case, with a space or a plus
    labels = {k: sorted({c[k] for c in read(built, "api/v1/countries.json")["countries"] if c[k]})
              for k in ("region", "income", "tier")}
    checks = []
    for c in conds:
        if "value" in c:
            hits = [lab for lab in labels[c["key"]] if re.search(c["value"], lab)]
            assert len(hits) == 1, (c, hits)
            lab = hits[0]
            for variant in (lab, lab.lower(), lab.upper(), lab.replace(" ", "+")):
                assert re.search(c["value"], variant), (c["value"], variant)
                checks.append([c["value"], variant])
    node = subprocess.run(["node", "-e", "const d=JSON.parse(require('fs').readFileSync(0,'utf8'));"
                           "console.log(JSON.stringify(d.filter(([p,s])=>!new RegExp(p).test(s))))"],
                          input=json.dumps(checks), capture_output=True, text=True)
    assert node.returncode == 0 and json.loads(node.stdout) == [], node.stderr + node.stdout


def test_filter_parity(built, monkeypatch):
    from prm import api
    from staticbuild import common

    ctx = common.load(built)
    ctx.api_meta["generated"] = read(built, "data/meta.json")["built"]
    monkeypatch.setattr(api, "_bundle", lambda: (ctx.tables, ctx.api_meta))
    rules = read(built, "vercel.json")["rewrites"]
    index = read(built, "api/v1/countries.json")["countries"]
    pick = next(c for c in index if c["region"] and c["income"] and c["tier"])
    r, i, t = pick["region"], pick["income"], pick["tier"]
    queries = [{}, {"region": r}, {"income": i.lower()}, {"tier": t.upper()}, {"region": r, "income": i},
               {"income": i, "tier": t}, {"region": r.replace(" ", "+"), "tier": t}, {"region": r, "income": i, "tier": t},
               {"region": "Atlantis"}, {"region": r, "income": "nowhere"}, {"tier": t, "region": r, "income": i + "x"},
               {"tier": "Low", "income": "High income", "region": "Sub-Saharan Africa"}]
    for query in queries:
        dest = matching(rules, "/api/v1/countries", query)
        assert dest, query
        wanted = {k: v.replace("+", " ") for k, v in query.items()}
        expected = json.loads(asyncio.run(api._countries(SimpleNamespace(query_params=wanted))).body)
        assert read(built, dest.lstrip("/")) == expected, query
    assert matching(rules, "/api/v1/countries", {"region": "Atlantis"}).endswith("countries.empty.json")
    assert matching(rules, "/api/v1/countries", {"other": "1"}).endswith("/countries.json")


def broken(built, tmp_path, name, edit):
    bad = tmp_path / name
    shutil.copytree(built, bad)
    edit(bad)
    done = run("staticbuild.validate", str(bad))
    assert done.returncode == 1, done.stdout
    assert "Traceback" not in done.stderr, done.stderr
    return done.stdout


def edit_json(rel, fn):
    def edit(base):
        doc = read(base, rel)
        fn(doc)
        (base / rel).write_text(json.dumps(doc))
    return edit


def test_validate_rejects(built, tmp_path):
    ok = run("staticbuild.validate", str(built))
    assert ok.returncode == 0, ok.stdout + ok.stderr

    def hot(scores):
        i = scores["columns"].index("composite")
        scores["rows"][0][i] = 140
    out = broken(built, tmp_path, "hot", edit_json("data/scores.json", hot))
    assert "scores composite: 1 values outside 0-100 (e.g. 140)" in out and "countries:" not in out

    out = broken(built, tmp_path, "few", edit_json("data/countries.json", lambda c: c.update(rows=c["rows"][:100])))
    assert "countries: 100 rows, need at least 180" in out and "outside 0-100" not in out

    def short(scores):
        scores["rows"] = scores["rows"][:100]
    out = broken(built, tmp_path, "short", edit_json("data/scores.json", short))
    assert "scored economies, need at least" in out

    out = broken(built, tmp_path, "empty", edit_json("data/history.json", lambda h: h.update(rows=[])))
    assert "history: no rows" in out

    out = broken(built, tmp_path, "nocol", edit_json("data/history.json", lambda h: h["columns"].remove("composite")))
    assert "history.json: could not be checked" in out

    out = broken(built, tmp_path, "nofile", lambda base: (base / "api/v1/countries.empty.json").unlink())
    assert "countries.empty.json" in out and "vercel.json: destination" in out

    out = broken(built, tmp_path, "count", edit_json("api/v1/countries.json", lambda a: a.update(count=5)))
    assert "lists 5 economies" in out


def test_validate_accepts_last_year_in_january():
    from datetime import date

    from staticbuild.validate import analysis_years

    assert analysis_years(date(2027, 1, 31)) == {2027, 2026}  # the daily refreshes pass until the weekly rebuild
    assert analysis_years(date(2027, 2, 1)) == {2027}
    assert analysis_years(date(2026, 12, 31)) == {2026}


def test_no_fsi_values(built, tmp_path):
    assert run("staticbuild.validate", str(built)).returncode == 0

    def column(countries):
        countries["columns"].append("fsi_score")
        for row in countries["rows"]:
            row.append(50)
    assert "data/countries.json: fsi_score" in broken(built, tmp_path, "col", edit_json("data/countries.json", column))

    def keyed(trend):
        trend["NGA"]["fsi"] = 3
    assert "data/wgi_trend.json" in broken(built, tmp_path, "keyed", edit_json("data/wgi_trend.json", keyed))

    def api_file(payload):
        payload["countries"][0]["fsi"] = 3
    assert "api/v1/countries.json" in broken(built, tmp_path, "api", edit_json("api/v1/countries.json", api_file))


def test_fixtures(tmp_path):
    out = tmp_path / "web"
    done = run("staticbuild", "--only", "core", "--fixtures", "--out", str(out))
    assert done.returncode == 0, done.stderr[-2000:]
    fx = out / "tests/fixtures"
    for name in ("scores_default", "scores_w50_20_20_10", "history_w50_20_20_10", "flag_counts", "format",
                 "interpret_NGA", "interpret_NGA_w50_20_20_10", "interpret_SYR", "interpret_NOR", "interpret_USA",
                 "interpret_VNM"):
        assert (fx / f"{name}.json").is_file(), name
    nga = read(fx, "interpret_NGA.json")
    assert nga["reading"]["iso3"] == "NGA" and nga["reading"]["tier"] and nga["inputs"]["today"]
    fmt = read(fx, "format.json")
    assert {"in": -0.04, "digits": 1, "out": "0.0"} in fmt["signed"]
    assert {"in": 2.25, "digits": 1, "out": "+2.2"} in fmt["signed"]
    unscored = [p.stem.removeprefix("interpret_") for p in fx.glob("interpret_???.json")
                if read(fx, p.name)["reading"]["tier"] is None]
    assert len(unscored) == 1
