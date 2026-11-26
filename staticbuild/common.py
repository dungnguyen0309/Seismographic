"""Shared by every exporter: the core data, loaded once from data/snapshot exactly as the app does, and JSON writing."""

from __future__ import annotations

import dataclasses
import json
import logging
import math
import os
import datetime as dt
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DATA = WEB / "data"


def _clean(obj):
    """JSON-ready: NaN/inf -> None, numpy and pandas scalars -> Python, dataclasses and tuples -> dicts and lists."""
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_clean(v) for v in obj]
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return _clean(dataclasses.asdict(obj))
    if isinstance(obj, np.generic):
        obj = obj.item()
    if obj is pd.NA or obj is pd.NaT:
        return None
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(obj).isoformat()
    return obj


def write_json(path: str | Path, obj, root: Path = WEB) -> Path:
    """Write compact UTF-8 JSON; `path` is relative to `root` (default web/) or absolute. Returns the absolute path."""
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(_clean(obj), separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    tmp = path.with_name(path.name + ".tmp")  # same folder, so os.replace is atomic: a crash never leaves half a file
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return path


def _num(v, decimals: int | None, sig: int | None):
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return None
    if sig is not None:
        v = float(f"{v:.{sig}g}")
    elif decimals is not None:
        v = round(v, decimals)
    return int(v) if v.is_integer() and abs(v) < 2**53 else v


def table(df: pd.DataFrame, decimals: int | None = None, sig: int | None = None) -> dict:
    """Column-oriented {"columns", "rows"} with null for missing; a named index becomes the first column.
    Floats are rounded to `decimals` places or `sig` significant digits; whole floats are written as integers."""
    if df.index.name is not None:
        df = df.reset_index()
    cols = []
    for name in df.columns:
        s = df[name]
        if pd.api.types.is_float_dtype(s):
            cols.append([_num(v, decimals, sig) for v in s.astype(float).tolist()])
        else:
            cols.append([_clean(v) for v in s.astype(object).where(s.notna(), None).tolist()])
    return {"columns": [str(c) for c in df.columns], "rows": [list(r) for r in zip(*cols)]}


def keep_site_year(out: str | Path | None = None) -> int | None:
    """A build without core uses the year the site was built for (data/meta.json), so in January the daily refreshes
    and their fixtures match the rest of the site until the weekly rebuild moves it to the new year."""
    from prm import data

    meta = (Path(out) if out else WEB) / "data/meta.json"
    year = json.loads(meta.read_text(encoding="utf-8")).get("year") if meta.is_file() else None
    if year:
        data.analysis_year = lambda: year
    return year


def load(out: str | Path | None = None) -> SimpleNamespace:
    """The context every exporter's build(ctx) gets: the app's snapshot core (prm.data._snapshot_core), the analysis
    year, values, default scores and history, the open-data tables, plus paths and writers. No network access.
    `out` replaces web/ as the output root (tests build into a temporary folder)."""
    from prm import config, data, export, forecast, scoring

    for name in ("streamlit", "streamlit.runtime.caching.cache_data_api"):  # "no runtime" warnings outside the app
        logging.getLogger(name).setLevel(logging.ERROR)

    year = data.analysis_year()
    core = data._snapshot_core(year)  # load_core() would start a live download when the snapshot is old
    if core is None:
        raise SystemExit("data/snapshot/countries.csv is missing")
    weights = scoring.default_weights()
    values = scoring.build_values(core["series"], core["countries"], year)
    scores = scoring.compute_scores(values, weights)
    history = core["history_default"]
    if history is None:  # history.csv is from another year: rebuild it as data.get_history does
        history = data.build_default_history(core["series"], core["countries"])
    outlook = forecast.outlook(history, core["series"].get("battle_deaths"), year)
    tables = export.build(core, values, scores, history, outlook)
    web = Path(out).resolve() if out else WEB
    built = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()  # the only thing that changes per run
    return SimpleNamespace(
        core=core, year=year, weights=weights, values=values, scores=scores, history=history, outlook=outlook,
        tables=tables, api_meta={**export.meta(core, year, weights), "generated": built}, config=config, built=built,
        root=ROOT, web=web, data=web / "data", write_json=lambda path, obj: write_json(path, obj, web), table=table,
    )
