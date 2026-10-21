"""Data loading for the Streamlit app: instant start from the saved snapshot, live data in the background.

Downloading every API takes 40-60 seconds, and a free Streamlit app that has gone to sleep starts
cold. So pages render immediately from the snapshot CSVs in data/snapshot/ (refreshed monthly by
scripts/refresh_snapshot.py / the GitHub Action) while one background thread, shared by every
visitor, downloads the live figures. When they arrive, open pages re-run themselves (see
ui.load). Live data is kept for 12 hours; a series whose API is down keeps its snapshot copy.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import threading
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from . import config, export, forecast, scoring, sources, stress, validation

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = ROOT / "data" / "snapshot"
CACHE_TTL = 60 * 60 * 12
LIVE_START_DELAY = 4  # seconds
MIN_COVERAGE = 0.6  # a fresh download must cover at least this share of the countries in the saved copy


def _read_snapshot(name: str) -> pd.DataFrame | None:
    path = SNAPSHOT_DIR / f"{name}.csv"
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception:  # a corrupt snapshot should never crash the app
        return None


def plausible(new: pd.DataFrame | None, saved: pd.DataFrame | None) -> bool:
    """Guards against a truncated download replacing good data: the new copy must cover most of the countries the
    saved one does (APIs sometimes answer with a partial page instead of an error)."""
    if saved is None or saved.empty or "iso3" not in saved:
        return new is not None and not new.empty
    if new is None or new.empty or "iso3" not in new:
        return False
    return new["iso3"].nunique() >= MIN_COVERAGE * saved["iso3"].nunique()


def _snapshot_meta() -> dict:
    path = SNAPSHOT_DIR / "meta.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _with_country_columns(countries: pd.DataFrame) -> pd.DataFrame:
    """Older snapshots predate flags and capital coordinates."""
    countries = countries.copy()
    for col in ("iso2", "lat", "lng"):
        if col not in countries.columns:
            countries[col] = None
    return countries


def history_years() -> range:
    return range(config.HISTORY_START, analysis_year() + 1)


def build_default_history(series: dict[str, pd.DataFrame], countries: pd.DataFrame) -> pd.DataFrame:
    """The index for every year with the default weights: what almost every visitor sees, so it is built ahead."""
    return scoring.build_history(series, countries, scoring.default_weights(), history_years())


def _ready_history(frame: pd.DataFrame | None) -> pd.DataFrame | None:
    """A saved history, if it covers exactly the years the app shows today."""
    if frame is None or frame.empty or "year" not in frame:
        return None
    return frame if sorted(frame["year"].unique()) == list(history_years()) else None


# ---------------------------------------------------------------------------
# Live download (runs in a background thread: no Streamlit calls in here)
# ---------------------------------------------------------------------------
def _fetch_live_core() -> dict:
    snapshot_meta = _snapshot_meta()
    saved_countries = _read_snapshot("countries")
    try:
        countries, countries_from_snapshot = sources.fetch_wb_countries(), False
        if not plausible(countries, saved_countries):
            raise sources.SourceError("incomplete country list")
    except sources.SourceError:
        countries, countries_from_snapshot = saved_countries, True
        if countries is None:
            raise

    results = sources.fetch_many(config.RAW_SERIES)
    series: dict[str, pd.DataFrame] = {}
    meta: dict[str, dict] = {}
    for key, res in results.items():
        data, from_snapshot, error = res.data, False, res.error
        snap = _read_snapshot(key)
        if not error and not plausible(data, snap):
            error = f"incomplete download ({data['iso3'].nunique() if 'iso3' in data else 0} countries)"
        if error or data.empty:
            if snap is not None and not snap.empty:
                data, from_snapshot = snap, True
        series[key] = data
        snap_info = snapshot_meta.get("series", {}).get(key, {})
        meta[key] = {
            "provider": res.provider,
            "code": res.code,
            "last_updated": res.last_updated or (snap_info.get("last_updated") if from_snapshot else None),
            "edition": res.edition or (snap_info.get("edition") if from_snapshot else None),
            "error": error,
            "from_snapshot": from_snapshot,
            "snapshot_date": snapshot_meta.get("created") if from_snapshot else None,
            "rows": int(len(data)),
        }
    saved_flows = _read_snapshot("flows")
    try:
        flows = sources.fetch_unhcr_flows()
        if saved_flows is not None and len(flows) < MIN_COVERAGE * len(saved_flows):
            flows = saved_flows
    except sources.SourceError:
        flows = saved_flows
    countries = _with_country_columns(countries)
    try:  # built here, in the background, so pages switch to live data without a pause
        history = build_default_history(series, countries)
    except Exception:
        history = None
    return {
        "countries": countries,
        "countries_from_snapshot": countries_from_snapshot,
        "series": series,
        "meta": meta,
        "flows": flows,
        "history_default": history,
        "loaded_at": dt.datetime.now(dt.timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
        "source": "live",
        "version": f"live-{time.time():.0f}",
    }


MIN_SCORED = 150  # a healthy download scores about 200 economies
RETRY_DOWNLOAD = 900  # seconds to wait after a failed download before trying again
PARTIAL_RETRY = 3600  # a download where some sources failed is refreshed after an hour, not CACHE_TTL


def health_problem(core: dict) -> str | None:
    """None if a download produces a sensible index, otherwise what is wrong with it. Checked before visitors are
    switched to new data, so a source that changes its format cannot break every page at once."""
    try:
        values = scoring.build_values(core["series"], core["countries"], analysis_year())
        scores = scoring.compute_scores(values)
    except Exception as exc:
        return f"the new data could not be scored ({type(exc).__name__}: {str(exc)[:120]})"
    scored = int(scores["composite"].notna().sum())
    if scored < MIN_SCORED:
        return f"the new data scores only {scored} economies"
    if core.get("history_default") is None:
        return "the index history could not be rebuilt from the new data"
    return None


@st.cache_resource(show_spinner=False)
def _live_store() -> dict:
    """One per server process, shared by every visitor."""
    return {"core": None, "fetched_at": 0.0, "attempted_at": 0.0, "thread": None, "error": None,
            "lock": threading.Lock()}


def _download(store: dict) -> None:
    if store["core"] is None:
        # First download after the server starts: let the first visitor's page draw before competing for the CPU
        time.sleep(LIVE_START_DELAY)
    try:
        core = _fetch_live_core()
        problem = health_problem(core)
    except Exception as exc:  # keep serving what we have; ui.load reports it
        problem = f"{type(exc).__name__}: {exc}"
    if not problem and all(m["from_snapshot"] or m["error"] for m in core["meta"].values()):
        problem = "none of the data sources answered"  # nothing new: keep the snapshot and retry soon
    if problem:
        log.warning("live data not used: %s", problem)
        with store["lock"]:
            store["error"] = problem
        return
    # A download where some sources failed is used, but retried within the hour instead of being kept 12 hours
    partial = any(m["from_snapshot"] or m["error"] for m in core["meta"].values())
    fetched_at = time.time() - (CACHE_TTL - PARTIAL_RETRY if partial else 0)
    with store["lock"]:
        store["core"], store["fetched_at"], store["error"] = core, fetched_at, None


def _ensure_download(store: dict) -> None:
    with store["lock"]:
        now = time.time()
        stale = store["core"] is None or now - store["fetched_at"] > CACHE_TTL
        running = store["thread"] is not None and store["thread"].is_alive()
        recently_failed = store["error"] is not None and now - store["attempted_at"] < RETRY_DOWNLOAD
        if stale and not running and not recently_failed:
            store["attempted_at"] = now
            store["thread"] = threading.Thread(target=_download, args=(store,), daemon=True, name="prm-live-data")
            store["thread"].start()


@st.cache_data(show_spinner=False)
def _snapshot_core() -> dict | None:
    """Everything from data/snapshot/, shaped like the live data."""
    countries = _read_snapshot("countries")
    if countries is None:
        return None
    snapshot_meta = _snapshot_meta()
    created = snapshot_meta.get("created")
    series, meta = {}, {}
    for key, (provider, code, _options) in config.RAW_SERIES.items():
        snap = _read_snapshot(key)
        info = snapshot_meta.get("series", {}).get(key, {})
        series[key] = snap if snap is not None else pd.DataFrame(columns=["iso3", "year", "value"])
        meta[key] = {
            "provider": provider,
            "code": code,
            "last_updated": info.get("last_updated"),
            "edition": info.get("edition"),
            "error": None if snap is not None else "not in the saved snapshot",
            "from_snapshot": snap is not None,
            "snapshot_date": created,
            "rows": 0 if snap is None else int(len(snap)),
        }
    return {
        "countries": _with_country_columns(countries),
        "countries_from_snapshot": True,
        "series": series,
        "meta": meta,
        "flows": _read_snapshot("flows"),
        "history_default": _ready_history(_read_snapshot("history")),
        "loaded_at": f"saved snapshot of {created}",
        "source": "snapshot",
        "snapshot_date": created,
        "version": f"snapshot-{created}",
    }


def load_core() -> dict:
    """Live data if it has been downloaded, otherwise the snapshot (a live download starts in the background)."""
    store = _live_store()
    _ensure_download(store)
    if store["core"] is not None:
        return store["core"]
    snapshot = _snapshot_core()
    if snapshot is not None:
        return snapshot
    # No snapshot at all (e.g. a fresh checkout): wait for the download
    if store["thread"] is not None:
        store["thread"].join()
    if store["core"] is None:
        raise sources.SourceError(store["error"] or "the live download failed")
    return store["core"]


def live_status() -> dict:
    store = _live_store()
    thread = store["thread"]
    return {
        "version": store["core"]["version"] if store["core"] else None,
        "running": thread is not None and thread.is_alive(),
        "error": store["error"],
    }


REFRESH_COOLDOWN = 600  # seconds: the button cannot make every visitor's server re-download all APIs over and over


def refresh() -> str:
    """Start a fresh live download (the sidebar's Refresh button). Pages keep the current data meanwhile.
    Returns a short message for the visitor."""
    store = _live_store()
    with store["lock"]:
        running = store["thread"] is not None and store["thread"].is_alive()
        age = time.time() - store["fetched_at"] if store["core"] is not None else None
        if running:
            return "The latest figures are already downloading."
        if time.time() - store["attempted_at"] < 120:
            return "A download was tried a moment ago. Please wait a couple of minutes before trying again."
        if age is not None and age < REFRESH_COOLDOWN:
            return f"The data was downloaded {max(1, int(age // 60))} min ago, so it is already up to date."
        store["fetched_at"] = 0.0
        store["error"] = None
        store["attempted_at"] = 0.0
    _ensure_download(store)
    return "Downloading the latest figures; the page updates by itself in about a minute."


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_wgi_ci() -> dict[str, pd.DataFrame]:
    """WGI 90% confidence intervals: the snapshot copy if complete (they change once a year), else live."""
    snap = {key: _read_snapshot(key) for key in config.WGI_CI_SERIES}
    if all(df is not None and not df.empty for df in snap.values()):
        return snap
    results = sources.fetch_many(config.WGI_CI_SERIES)
    return {
        key: res.data if not res.data.empty or snap.get(key) is None else snap[key]
        for key, res in results.items()
    }


def analysis_year() -> int:
    """The year the index describes: the current calendar year (IMF estimates)."""
    return dt.date.today().year


# Derived tables are cached per data version; `_core` (underscore) is not hashed by Streamlit.
@st.cache_data(ttl=CACHE_TTL, show_spinner=False, max_entries=8)
def get_values(_core: dict, year: int, version: str) -> pd.DataFrame:
    return scoring.build_values(_core["series"], _core["countries"], year)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False, max_entries=32)
def get_scores(_core: dict, year: int, weights: tuple[tuple[str, float], ...], version: str) -> pd.DataFrame:
    return scoring.compute_scores(get_values(_core, year, version), dict(weights))


@st.cache_data(ttl=CACHE_TTL, show_spinner=False, max_entries=4)
def get_outlook(_core: dict, version: str):
    """The conflict outlook model (prm/forecast.py). Uses the pillar scores only, so it ignores the user's weights."""
    hist = get_history(_core, tuple((p.key, float(p.default_weight)) for p in config.PILLARS), version)
    return forecast.outlook(hist, _core["series"].get("battle_deaths"), analysis_year())


@st.cache_data(ttl=CACHE_TTL, show_spinner=False, max_entries=8)
def get_export(_core: dict, year: int, weights: tuple[tuple[str, float], ...], version: str) -> dict:
    """The open-data tables (prm/export.py) for the given weights."""
    values = get_values(_core, year, version)
    return export.build(_core, values, get_scores(_core, year, weights, version), get_history(_core, weights, version),
                        get_outlook(_core, version))


@st.cache_data(ttl=CACHE_TTL, show_spinner=False, max_entries=32)
def get_stress(_core: dict, year: int, weights: tuple[tuple[str, float], ...], shocks: tuple[tuple[str, float], ...],
               scope: tuple[str, ...] | None, version: str) -> pd.DataFrame:
    """The stress test (prm/stress.py) for one set of shocks and countries hit."""
    return stress.run(get_values(_core, year, version), dict(weights), dict(shocks), set(scope) if scope else None)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False, max_entries=16)
def get_track_record(_core: dict, weights: tuple[tuple[str, float], ...], version: str, score: str) -> dict:
    """Did high scores come before armed conflict? (see prm/validation.py)"""
    panel = validation.onset_panel(get_history(_core, weights, version), _core["series"].get("battle_deaths"), score)
    return validation.summary(panel)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False, max_entries=64)
def get_sensitivity(_core: dict, year: int, iso3: str, weights: tuple[tuple[str, float], ...],
                    version: str) -> pd.DataFrame:
    """A country's score with equal weights and with each pillar left out (five full recomputes, so cached)."""
    return scoring.sensitivity(get_values(_core, year, version), iso3, dict(weights))


@st.cache_data(ttl=CACHE_TTL, show_spinner=False, max_entries=16)
def get_history(_core: dict, weights: tuple[tuple[str, float], ...], version: str) -> pd.DataFrame:
    if dict(weights) == scoring.default_weights() and _core.get("history_default") is not None:
        return _core["history_default"]  # built ahead of time (snapshot or live download)
    return scoring.build_history(_core["series"], _core["countries"], dict(weights), history_years())


# ---------------------------------------------------------------------------
# Optional live extras (news, video, media tone, protests, the FSI benchmark)
# ---------------------------------------------------------------------------
# Successes are cached; failures are not (st.cache_data never caches an exception), so a source that was down is
# tried again after RETRY_AFTER seconds instead of staying "unavailable" for the whole cache period. Any error,
# expected or not, becomes a short message for the page: an odd answer from a feed must never crash a page.
RETRY_AFTER = 300
_failures: dict[tuple, tuple[float, str]] = {}
log = logging.getLogger("seismographic.data")


def _guarded(key: tuple, fetch):
    """(result, None) or (None, error message), waiting RETRY_AFTER seconds before retrying a failed source."""
    failed = _failures.get(key)
    if failed and time.time() - failed[0] < RETRY_AFTER:
        return None, failed[1]
    try:
        result = fetch()
    except Exception as exc:
        message = str(exc) if isinstance(exc, sources.SourceError) else f"unexpected answer ({type(exc).__name__})"
        log.warning("%s failed: %s", key[0], str(exc)[:300])  # the details go to the server log, not the page
        _failures[key] = (time.time(), message[:300])
        return None, message[:300]
    _failures.pop(key, None)
    return result, None


@st.cache_data(ttl=60 * 10, show_spinner=False)
def _news(name: str | None) -> tuple[pd.DataFrame, str]:
    return sources.fetch_news(name)


def load_news(name: str | None) -> dict:
    """Headlines for a country (None = global), cached for 10 minutes per country."""
    fetched = dt.datetime.now(dt.timezone.utc).strftime("%H:%M UTC")
    result, error = _guarded(("news", name), lambda: _news(name))
    articles, source = result if result is not None else (None, "")
    return {"articles": articles, "error": error, "source": source, "fetched": fetched}


@st.cache_data(ttl=60 * 15, show_spinner=False)
def _videos() -> pd.DataFrame:
    frames = []
    for kind, channels in (("news", config.NEWS_VIDEO_CHANNELS), ("analysis", config.ANALYSIS_VIDEO_CHANNELS),
                           ("institutions", config.INSTITUTION_VIDEO_CHANNELS)):
        try:
            frames.append(sources.fetch_videos(channels, kind))
        except sources.SourceError:
            continue
    if not frames:
        raise sources.SourceError("no video feed could be reached")
    return pd.concat(frames, ignore_index=True)


def load_videos() -> pd.DataFrame | None:
    """Latest news reports, think-tank analysis and institutions' videos (YouTube feeds), cached for 15 minutes."""
    return _guarded(("videos",), _videos)[0]


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def _tone(name: str) -> pd.DataFrame:
    return sources.fetch_gdelt_tone(name)


def load_tone(name: str) -> tuple[pd.DataFrame | None, str | None]:
    return _guarded(("tone", name), lambda: _tone(name))


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def _protests(name: str) -> pd.DataFrame:
    return sources.fetch_gdelt_protests(name)


def load_protests(name: str) -> tuple[pd.DataFrame | None, str | None]:
    return _guarded(("protests", name), lambda: _protests(name))


@st.cache_data(ttl=60 * 60 * 24 * 7, show_spinner=False)
def _fsi() -> pd.DataFrame:
    return sources.fetch_fsi(config.FSI_URL, load_countries())


def load_fsi() -> tuple[pd.DataFrame | None, str | None]:
    """The Fragile States Index edition in config.FSI_URL, matched to our country codes (cached for a week)."""
    return _guarded(("fsi",), _fsi)


def load_countries() -> pd.DataFrame:
    """Just the country list — powers the sidebar search on every page."""
    return load_core()["countries"]


def country_series(series: dict[str, pd.DataFrame], key: str, iso3: str) -> pd.DataFrame:
    df = series.get(key)
    if df is None or df.empty:
        return pd.DataFrame(columns=["year", "value"])
    return df[df["iso3"] == iso3][["year", "value"]].sort_values("year")
