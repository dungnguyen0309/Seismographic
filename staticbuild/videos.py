"""data/videos.json: {fetched, items, live, regions, aliases}. Items are the latest YouTube uploads of the app's channels
(news, analysis, institutions); live holds the 24/7 channels; the last good items stay when no feed answers."""

import datetime as dt

from prm import config, sources
from staticbuild.news import read_json

KINDS = (("news", config.NEWS_VIDEO_CHANNELS), ("analysis", config.ANALYSIS_VIDEO_CHANNELS),
         ("institutions", config.INSTITUTION_VIDEO_CHANNELS))
COLUMNS = ["video_id", "title", "channel", "kind", "published", "description", "views", "thumbnail"]


def build(ctx) -> None:
    old = read_json(ctx.data / "videos.json") or {}
    items, fetched = [], old.get("fetched")
    for kind, channels in KINDS:
        try:
            df = sources.fetch_videos(channels, kind)
        except Exception:  # this kind's old items stay
            df = None
        if df is not None and len(df):
            items += df[COLUMNS].assign(published=df["published"].map(lambda t: t.isoformat() if t == t else None)).to_dict("records")
            fetched = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
        else:
            items += [i for i in old.get("items", []) if i["kind"] == kind]
    live = {n: {"id": c.id, "region": c.region, "origin": c.origin, "funding": c.funding} for n, c in config.LIVE_CHANNELS.items()}
    ctx.write_json("data/videos.json", {"fetched": fetched, "items": items, "live": live,
                                        "regions": config.LIVE_REGIONS, "aliases": config.VIDEO_ALIASES})
