"""Headlines: data/news/global.json, region-<slug>.json, <ISO3>.json ({fetched, source, items}) and status.json.

Same queries as the app: the global feed is None, a region is config.REGION_NEWS[region], a country is its news name.
A failed or empty fetch never replaces a good file."""

from __future__ import annotations

import datetime as dt
import json
from concurrent.futures import ThreadPoolExecutor

from prm import config, hotspots, sources, ui
from staticbuild.core import slug

WORKERS = 6


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def build(ctx) -> None:
    table = ui.master_table(ctx.core, ctx.values, ctx.scores, ctx.history)
    queries = {"global": None}
    for region in sorted(table["region"].dropna().unique()):
        queries[f"region-{slug(region)}"] = config.REGION_NEWS.get(region, region)
    for r in table.itertuples(index=False):
        queries[r.iso3] = hotspots.news_name(r.iso3, r.name)
    out = ctx.data / "news"
    fetched = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

    def fetch(key):
        try:
            df, source = sources.fetch_news(queries[key])
        except Exception as exc:  # a feed answering oddly must not stop the run
            return key, None, str(exc)[:200]
        return key, (df, source), None

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(fetch, queries))
    keys = {}
    for key, got, error in results:
        path = out / f"{key}.json"
        if got is not None and len(got[0]):
            ctx.write_json(path, {"fetched": fetched, "source": got[1], "items": got[0].to_dict("records")})
            keys[key] = "ok"
        elif path.is_file():
            keys[key] = "kept"
        elif got is not None:  # an answer with no headlines: the page says so
            ctx.write_json(path, {"fetched": fetched, "source": got[1], "items": []})
            keys[key] = "empty"
        else:
            keys[key] = "failed"
        if keys[key] in ("kept", "failed"):
            print(f"  news {key}: {keys[key]} ({error or 'empty answer'})", flush=True)
    counts = {s: sum(v == s for v in keys.values()) for s in ("ok", "empty", "kept", "failed")}
    # failed = fetches that did not produce new headlines (kept files included)
    ctx.write_json(out / "status.json", {"fetched": fetched, **counts, "failed": counts["kept"] + counts["failed"], "keys": keys})
