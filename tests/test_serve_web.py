import json
import threading
import urllib.error
import urllib.request

import pytest

from scripts.serve_web import make_server

VERCEL = {
    "cleanUrls": True,
    "redirects": [{"source": "/watchlist", "destination": "/hotspots?tab=calendar", "permanent": False}],
    "rewrites": [
        {"source": "/", "destination": "/index.html"},
        {"source": "/(country|hotspots)", "destination": "/index.html"},
        {"source": "/api/v1/countries", "has": [{"type": "query", "key": "region", "value": "(?i)^europe & central asia$"}],
         "destination": "/api/v1/countries.region-eca.json"},
        {"source": "/api/v1/countries", "has": [{"type": "query", "key": "income"}],
         "missing": [{"type": "query", "key": "region"}], "destination": "/api/v1/countries.income.json"},
        {"source": "/api/v1/countries", "destination": "/api/v1/countries.json"},
        {"source": "/api/v1/countries/:iso3", "destination": "/api/v1/countries/:iso3.json"},
    ],
    "headers": [{"source": "/api/(.*)", "headers": [{"key": "Access-Control-Allow-Origin", "value": "*"}]}],
}


@pytest.fixture
def base(tmp_path):
    (tmp_path / "vercel.json").write_text(json.dumps(VERCEL))
    (tmp_path / "index.html").write_text("<main>app</main>")
    (tmp_path / "404.html").write_text("Page not found")
    api = tmp_path / "api/v1"
    (api / "countries").mkdir(parents=True)
    (api / "countries.json").write_text('{"all":1}')
    (api / "countries.income.json").write_text('{"income":1}')
    (api / "countries.region-eca.json").write_text('{"eca":1}')
    (api / "countries/NGA.json").write_text('{"iso3":"NGA"}')
    srv = make_server(tmp_path, 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def get(url):
    try:
        r = urllib.request.build_opener(_NoRedirect).open(url)
    except urllib.error.HTTPError as e:
        r = e
    return r.status, dict(r.headers), r.read().decode()


def test_rewrites(base):
    s, _, body = get(base + "/country?country=NGA")
    assert (s, body) == (200, "<main>app</main>")
    assert get(base + "/")[0] == 200
    s, h, _ = get(base + "/watchlist")
    assert (s, h["Location"]) == (307, "/hotspots?tab=calendar")
    s, _, body = get(base + "/nope")
    assert (s, body) == (404, "Page not found")
    s, h, body = get(base + "/api/v1/countries")
    assert (s, json.loads(body), h["Access-Control-Allow-Origin"]) == (200, {"all": 1}, "*")
    assert json.loads(get(base + "/api/v1/countries?region=Europe%20%26%20Central%20Asia")[2]) == {"eca": 1}
    assert json.loads(get(base + "/api/v1/countries?region=Asia")[2]) == {"all": 1}
    assert json.loads(get(base + "/api/v1/countries/NGA")[2]) == {"iso3": "NGA"}
    assert get(base + "/api/v1/countries/ZZZ")[0] == 404
    assert get(base + "/../vercel.json")[0] in (404, 400)


def test_has_missing_and_presence_only(base):
    body = lambda q: json.loads(get(base + "/api/v1/countries" + q)[2])
    assert body("?income=High%20income") == {"income": 1}  # presence-only has
    assert body("?income=x&region=Asia") == {"all": 1}  # missing region fails
    assert body("?income=x&region=Europe%20%26%20Central%20Asia") == {"eca": 1}  # first match wins
    assert body("?tier=a") == {"all": 1}


def test_blank_query_value_counts_as_present(base):
    assert json.loads(get(base + "/api/v1/countries?income=")[2]) == {"income": 1}


def test_clean_url_redirects(base):
    for src, dest in [("/index.html", "/"), ("/country.html", "/country"), ("/country/", "/country"),
                      ("/country/?country=NGA", "/country?country=NGA")]:
        s, h, _ = get(base + src)
        assert (s, h["Location"]) == (308, dest), src


def test_bad_paths_give_404(base, tmp_path):
    (tmp_path.parent / "secret.txt").write_text("s")
    assert get(base + "/%00")[0] == 404
    assert get(base + "/..%2fsecret.txt")[0] == 404
    assert get(base + "/api/v1/countries.region-eca")[0] == 404  # dotted name is not mangled into .html


def test_file_names_are_case_sensitive(base, tmp_path):
    (tmp_path / "Foo.txt").write_text("x")
    assert get(base + "/Foo.txt")[0] == 200
    assert get(base + "/foo.txt")[0] == 404


def test_real_vercel_json_serves_every_route_and_api_url():
    """The real web/vercel.json: every page route, the /watchlist redirect and every API URL the README lists."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    cfg = json.loads((root / "web/vercel.json").read_text(encoding="utf-8"))
    pages = re.fullmatch(r"/\((.*)\)", cfg["rewrites"][1]["source"]).group(1).split("|")
    api = re.findall(r"^GET (/api/v1\S*)", (root / "README.md").read_text(encoding="utf-8"), re.M)
    assert len(pages) == 18 and len(api) == 4
    srv = make_server(root / "web", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        for path in ["/", *(f"/{p}" for p in pages)]:
            assert get(base + path)[0] == 200, path
        s, h, _ = get(base + "/watchlist")
        assert (s, h["Location"]) == (307, "/hotspots?tab=calendar")
        for path in api:
            s, h, body = get(base + path)
            assert (s, h["Content-Type"].split(";")[0]) == (200, "application/json"), path
            json.loads(body)
    finally:
        srv.shutdown()
