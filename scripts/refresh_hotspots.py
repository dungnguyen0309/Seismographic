"""Save the Hotspots data to data/snapshot/hotspots_*: UCDP candidate events and GDELT conflict-news volume.

Run it yourself with:   python scripts/refresh_hotspots.py
or let the GitHub Action in .github/workflows/refresh-hotspots.yml run it every day. It takes several minutes,
because GDELT allows about one request every five seconds.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import requests  # noqa: E402

from prm import config, data, hotspots, scoring, sources  # noqa: E402

OUT = ROOT / "data" / "snapshot"
UCDP_PAGE = "https://ucdp.uu.se/downloads/"
UCDP_BASE = "https://ucdp.uu.se/downloads/candidateged/"
UCDP_YTD = re.compile(r"candidateged/(GEDEvent_v(\d{2})_01_\2_(\d{2})\.csv)")
UCDP_MONTHLY = re.compile(r"candidateged/(GEDEvent_v(\d{2})_0_(\d{1,2})\.csv)")
CONFLICT_TERMS = ('(attack OR clashes OR airstrike OR shelling OR killed OR militants OR insurgents OR coup OR '
                  '"armed groups")')
GDELT_PAUSE = 8  # seconds between requests (GDELT asks for at least 5)
GDELT_RETRY_PAUSE = 45
GDELT_GIVE_UP = 8  # failures in a row: GDELT is down or blocking us, so stop instead of trying for hours
GDELT_TIMEOUT = (20, 60)
MAX_COUNTRIES = 80
MIN_COMPOSITE = 50


def _save(frame: pd.DataFrame, name: str) -> None:
    tmp = OUT / f"{name}.tmp"
    frame.to_csv(tmp, index=False)
    tmp.replace(OUT / name)


def ucdp_files(page: str) -> list[str]:
    """The newest year-to-date candidate file on the downloads page plus every newer monthly file, oldest first.
    The year-to-date files come out less often than the monthly ones."""
    ytd = sorted({(int(y), int(m), f) for f, y, m in UCDP_YTD.findall(page)})
    monthly = sorted({(int(y), int(m), f) for f, y, m in UCDP_MONTHLY.findall(page)})
    if not ytd and not monthly:
        raise sources.SourceError("no candidate file linked on the UCDP downloads page")
    if not ytd:
        return [monthly[-1][2]]
    return [ytd[-1][2], *(f for y, m, f in monthly if (y, m) > ytd[-1][:2])]


def fetch_ucdp(countries: pd.DataFrame):
    page = requests.get(UCDP_PAGE, timeout=sources.TIMEOUT, headers=sources.HEADERS)
    page.raise_for_status()
    files = ucdp_files(page.text)
    raws = []
    for name in files:
        response = requests.get(UCDP_BASE + name, timeout=(20, 180), headers=sources.HEADERS)
        response.raise_for_status()
        raws.append(pd.read_csv(io.BytesIO(response.content), low_memory=False))
    raw = pd.concat(raws, ignore_index=True)
    if "id" in raw:  # a newer file revises the events it repeats
        raw = raw.drop_duplicates("id", keep="last")
    return (", ".join(files), *hotspots.parse_ucdp(raw, countries))


def current_scores(countries: pd.DataFrame) -> pd.Series:
    """Composite scores for this year with the default weights, built with the app's own code."""
    series = {key: df for key in config.RAW_SERIES if (df := data._read_snapshot(key)) is not None}
    values = scoring.build_values(series, countries, data.analysis_year())
    return scoring.compute_scores(values)["composite"]


def gdelt_targets(cells: pd.DataFrame, composite: pd.Series) -> list[str]:
    """Countries with UCDP events in the window or composite >= MIN_COMPOSITE, likeliest hotspots first."""
    recent = cells.groupby("iso3").agg(events=("events", "sum"), deaths=("deaths", "sum"))
    picked = set(recent.index) | set(composite[composite >= MIN_COMPOSITE].index)
    frame = pd.DataFrame(index=sorted(picked))
    frame["hot"] = (recent["events"].reindex(frame.index).fillna(0) >= hotspots.MIN_EVENTS_90D) | (
        recent["deaths"].reindex(frame.index).fillna(0) >= hotspots.MIN_DEATHS_90D)
    frame["composite"] = composite.reindex(frame.index)
    frame = frame.sort_values(["hot", "composite"], ascending=[False, False], na_position="last")
    return list(frame.index[:MAX_COUNTRIES])


def fetch_gdelt(iso3: str, name: str) -> pd.DataFrame:
    params = {
        "query": f"{sources._gdelt_term(hotspots.news_name(iso3, name))} {hotspots.GDELT_EXCLUDE.get(iso3, '')} "
                 f"{CONFLICT_TERMS} sourcelang:english",
        "mode": "TimelineVolRaw",
        "format": "json",
        "timespan": f"{hotspots.WINDOW_DAYS}d",
    }
    try:
        payload = sources._gdelt_json(params, timeout=GDELT_TIMEOUT)
    except sources.SourceError:  # rate limit (429 or a plain-text answer) or a timeout: one more try
        time.sleep(GDELT_RETRY_PAUSE)
        payload = sources._gdelt_json(params, timeout=GDELT_TIMEOUT)
    return hotspots.gdelt_points(payload, iso3)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    meta_path = OUT / "hotspots_meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        meta = {}
    countries = data._read_snapshot("countries")
    if countries is None:
        print("countries: missing from data/snapshot (run scripts/refresh_snapshot.py first)")
        return 1
    names = countries.set_index("iso3")["name"]
    ok = 0

    try:
        name, monthly, cells, info = fetch_ucdp(countries)
        if cells.empty:
            raise sources.SourceError(f"{name} has no events")
        _save(monthly, "hotspots_ucdp_monthly.csv")
        _save(cells, "hotspots_ucdp_cells.csv")
        meta.update(ucdp_file=name, ucdp_from=info["from"], ucdp_through=info["through"])
        ok += 1
        print(f"UCDP: {name}, {info['from']} to {info['through']}, {int(monthly['events'].sum())} events, "
              f"{cells['iso3'].nunique()} countries in the last {hotspots.WINDOW_DAYS} days")
        if info["unmapped"]:
            print(f"UCDP: no country code for {', '.join(info['unmapped'])}")
    except (requests.RequestException, sources.SourceError, ValueError, KeyError) as exc:
        print(f"UCDP: FAILED ({exc}); keeping the previous files")
        cells = hotspots._csv("hotspots_ucdp_cells", hotspots.CELL_COLUMNS)

    targets = gdelt_targets(cells, current_scores(countries))
    frames, failed = [], []
    for i, iso3 in enumerate(targets):
        if i:
            time.sleep(GDELT_PAUSE)
        try:
            frame = fetch_gdelt(iso3, names.get(iso3, iso3))
            if frame.empty:
                raise sources.SourceError("no data")
            frames.append(frame)
            print(f"GDELT {iso3}: {len(frame)} days", flush=True)
        except sources.SourceError as exc:
            failed.append(iso3)
            print(f"GDELT {iso3}: FAILED ({exc})", flush=True)
            if failed[-GDELT_GIVE_UP:] == targets[i + 1 - GDELT_GIVE_UP:i + 1]:
                failed += targets[i + 1:]
                print(f"GDELT: {GDELT_GIVE_UP} failures in a row; skipping the other {len(targets) - i - 1}")
                break
    if frames:
        gdelt = pd.concat(frames, ignore_index=True)
        # a country that failed today keeps yesterday's series
        previous = pd.read_csv(OUT / "hotspots_gdelt.csv") if (OUT / "hotspots_gdelt.csv").exists() else None
        if previous is not None:
            gdelt = pd.concat([gdelt, previous[previous["iso3"].isin(failed)]], ignore_index=True)
        _save(gdelt[hotspots.GDELT_COLUMNS], "hotspots_gdelt.csv")
        meta.update(gdelt_through=gdelt["date"].max(), gdelt_countries=len(frames), gdelt_failed=failed)
        ok += 1
        print(f"GDELT: {len(frames)} of {len(targets)} countries, through {gdelt['date'].max()}")
    else:  # a warning on the workflow run: the page marks the news data stale after a few days
        print("::warning::GDELT failed for every country; keeping the previous file")

    meta["fetched"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    tmp = meta_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    tmp.replace(meta_path)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
