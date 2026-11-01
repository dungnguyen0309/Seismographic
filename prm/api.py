"""A small read-only JSON API, served next to the app when it runs as an ASGI app (asgi.py: uvicorn, Docker, Vercel).

`streamlit run` (and so Streamlit Community Cloud) has no custom routes, so there the API is simply absent.

    GET /api/v1                     what is available
    GET /api/v1/countries           the index today (default weights); filter with ?region=, ?income=, ?tier=
    GET /api/v1/countries/{iso3}    one economy: scores, indicators, red flags, history and conflict outlook
    GET /api/v1/dictionary          what every field means
"""

from __future__ import annotations

import logging
import threading

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from . import config, data, export, scoring

ENABLED = False  # set by routes(), so the Data downloads page only documents the API where it exists
PREFIX = "/api/v1"
HEADERS = {"Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=900"}
_cache: dict = {}
log = logging.getLogger("seismographic.api")
_lock = threading.Lock()


def _bundle() -> tuple[dict, dict]:
    """All tables with the default weights, built once per data version."""
    core = data.load_core()
    with _lock:
        if _cache.get("version") != core["version"]:
            year = data.analysis_year()
            weights = tuple((k, float(v)) for k, v in scoring.default_weights().items())
            values = data.get_values(core, year, core["version"])
            scores = data.get_scores(core, year, weights, core["version"])
            hist = data.get_history(core, weights, core["version"])
            tables = export.build(core, values, scores, hist, data.get_outlook(core, core["version"]))
            _cache.update(version=core["version"], tables=tables, meta=export.meta(core, year, dict(weights)))
        return _cache["tables"], _cache["meta"]


def _json(payload: dict, status: int = 200) -> JSONResponse:
    headers = HEADERS if status == 200 else {**HEADERS, "Cache-Control": "no-store"}
    return JSONResponse(payload, status_code=status, headers=headers)


def _safe(handler):
    """A failure answers with JSON (503: try again later) instead of a bare error page; details go to the log."""
    async def wrapped(request: Request) -> JSONResponse:
        try:
            return await handler(request)
        except Exception:
            log.exception("API request failed: %s", request.url.path)
            return _json({"error": "the data is temporarily unavailable", "retry_after_seconds": 60}, status=503)
    return wrapped


async def _root(request: Request) -> JSONResponse:
    _, meta = await run_in_threadpool(_bundle)
    base = str(request.base_url).rstrip("/") + PREFIX
    return _json({"meta": meta, "endpoints": {
        "countries": f"{base}/countries", "country": f"{base}/countries/{{iso3}}", "dictionary": f"{base}/dictionary",
    }, "filters": {"region": "World Bank region", "income": "World Bank income group",
                   "tier": ", ".join(config.TIER_ORDER)}})


async def _countries(request: Request) -> JSONResponse:
    tables, meta = await run_in_threadpool(_bundle)
    rows = tables["index"]
    for field in ("region", "income", "tier"):
        if wanted := request.query_params.get(field):
            rows = rows[rows[field].fillna("").str.lower() == wanted.strip().lower()]
    return _json({"meta": meta, "count": len(rows), "countries": export.records(rows)})


async def _country(request: Request) -> JSONResponse:
    tables, meta = await run_in_threadpool(_bundle)
    iso3 = request.path_params["iso3"].upper()
    row = tables["index"][tables["index"]["iso3"] == iso3]
    if row.empty:
        return _json({"error": "unknown country code", "iso3": iso3[:12],  # never echo a long path back in full
                      "hint": f"use a code from {PREFIX}/countries"}, status=404)
    pick = {name: frame[frame["iso3"] == iso3].drop(columns=["iso3", "name"], errors="ignore")
            for name, frame in tables.items() if name in ("indicators", "red_flags", "history", "conflict_outlook")}
    outlook = export.records(pick["conflict_outlook"])
    return _json({"meta": meta, "country": export.records(row)[0], "indicators": export.records(pick["indicators"]),
                  "red_flags": export.records(pick["red_flags"]), "history": export.records(pick["history"]),
                  "conflict_outlook": outlook[0] if outlook else None})


async def _dictionary(request: Request) -> JSONResponse:
    return _json({"fields": export.records(export.dictionary_table())})


def routes() -> list[Route]:
    global ENABLED
    ENABLED = True
    return [
        Route(PREFIX, _safe(_root), methods=["GET"]),
        Route(f"{PREFIX}/countries", _safe(_countries), methods=["GET"]),
        Route(f"{PREFIX}/countries/{{iso3:str}}", _safe(_country), methods=["GET"]),
        Route(f"{PREFIX}/dictionary", _safe(_dictionary), methods=["GET"]),
    ]
