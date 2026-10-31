"""Save a copy of every data series to data/snapshot/ so the app still works if an API is down.

Run it yourself with:   python scripts/refresh_snapshot.py
or let the GitHub Action in .github/workflows/refresh-data.yml run it once a week.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from prm import config, data, sources  # noqa: E402

OUT = ROOT / "data" / "snapshot"


def _saved(name: str) -> pd.DataFrame | None:
    path = OUT / f"{name}.csv"
    try:
        return pd.read_csv(path) if path.exists() else None
    except Exception:
        return None


def _save(frame: pd.DataFrame, name: str) -> None:
    """Write to a temporary file first, so a crash mid-write never leaves a half-written snapshot."""
    tmp = OUT / f"{name}.csv.tmp"
    frame.to_csv(tmp, index=False)
    tmp.replace(OUT / f"{name}.csv")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    meta_path = OUT / "meta.json"
    old_meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    meta = {"created": dt.date.today().isoformat(), "series": dict(old_meta.get("series", {}))}

    try:
        countries = sources.fetch_wb_countries()
        if not data.plausible(countries, _saved("countries")):
            raise sources.SourceError(f"only {len(countries)} countries")
        _save(countries, "countries")
        print(f"countries: {len(countries)}")
    except sources.SourceError as exc:
        print(f"countries: FAILED — {exc} (keeping previous file)")

    try:
        flows = sources.fetch_unhcr_flows()
        saved = _saved("flows")
        if saved is not None and len(flows) < data.MIN_COVERAGE * len(saved):
            raise sources.SourceError(f"only {len(flows)} origin-host pairs (saved copy: {len(saved)})")
        _save(flows, "flows")
        print(f"flows: {len(flows)} origin-host pairs ({int(flows['year'].max())})")
    except sources.SourceError as exc:
        print(f"flows: FAILED — {exc} (keeping previous file)")

    results = sources.fetch_many({**config.RAW_SERIES, **config.WGI_CI_SERIES})
    failed = []
    for key, res in sorted(results.items()):
        if res.error or res.data.empty:
            failed.append(key)
            print(f"{key}: FAILED — {res.error} (keeping previous file)")
            continue
        if not data.plausible(res.data, _saved(key)):
            failed.append(key)
            print(f"{key}: INCOMPLETE — {res.data['iso3'].nunique()} countries (keeping previous file)")
            continue
        _save(res.data, key)
        meta["series"][key] = {
            "provider": res.provider,
            "code": res.code,
            "last_updated": res.last_updated,
            "edition": res.edition,
            "rows": int(len(res.data)),
            "saved": meta["created"],
        }
        print(f"{key}: {len(res.data)} rows")

    # The index for every year with the default weights, so the app's first page opens without computing it
    try:
        series = {key: pd.read_csv(OUT / f"{key}.csv") for key in config.RAW_SERIES if (OUT / f"{key}.csv").exists()}
        countries = pd.read_csv(OUT / "countries.csv")
        for col in ("iso2", "lat", "lng"):
            if col not in countries.columns:
                countries[col] = None
        history = data.build_default_history(series, countries)
        _save(history, "history")
        print(f"history: {len(history)} country-years")
    except Exception as exc:  # the app rebuilds it if this fails
        print(f"history: FAILED — {exc}")

    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"\nDone. {len(results) - len(failed)} of {len(results)} series saved.")
    return 1 if len(failed) == len(results) else 0


if __name__ == "__main__":
    sys.exit(main())
