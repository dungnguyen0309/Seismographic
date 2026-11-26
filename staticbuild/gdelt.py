"""Media tone and protest coverage (GDELT) as the profile's News tab draws them: data/gdelt/<ISO3>.json
{tone, protests}, each a plotly figure (charts.tone_chart / protest_chart) or null when GDELT returned no points.

GDELT allows one request every 5 seconds and often takes 15-20 s to answer, so a full run (two requests for each of
the 218 economies) takes one to two hours: the weekly workflow. A country is written only when both of its requests
succeed; otherwise its last file stays (never a partial file). After GIVE_UP failures in a row (GDELT down or
limiting this address) the run stops and every remaining country keeps its last file. GDELT_BUDGET_MIN=150 stops
the run the same way once it has taken that many minutes, so one slow week cannot time out the whole refresh.
GDELT_COUNTRIES=NGA,SYR,UKR limits a run to those countries (local runs)."""

from __future__ import annotations

import functools
import os
import time
from unittest import mock

from prm import charts, config, sources
from staticbuild.charts import figure

PAUSE = 5.0  # seconds between two GDELT requests
TIMEOUT = (30, 30)  # seconds to connect and to read: the app waits (5, 20) for a visitor, a weekly build can wait more
GIVE_UP = 10  # failures in a row that end the run


def countries(ctx) -> list[tuple[str, str]]:
    """(ISO3, news name) of the countries to fetch: all of them, or those named in GDELT_COUNTRIES."""
    rows = list(zip(ctx.core["countries"]["iso3"], ctx.core["countries"]["name"]))
    only = {c.strip().upper() for c in os.environ.get("GDELT_COUNTRIES", "").split(",") if c.strip()}
    return [(iso3, config.NEWS_NAMES.get(iso3, name)) for iso3, name in rows if not only or iso3 in only]


def build(ctx) -> None:
    last = None  # when the previous answer came: a slow answer does not shorten the pause (GDELT 429s sooner requests)

    def ask(fetch, name):
        nonlocal last
        if last is not None:
            time.sleep(max(0.0, PAUSE - (time.monotonic() - last)))
        try:
            return fetch(name), None
        except Exception as exc:  # 429s, timeouts and odd answers alike: keep the last good file
            return None, str(exc)[:200]
        finally:
            last = time.monotonic()

    kept = failed = 0
    todo = countries(ctx)
    budget = float(os.environ.get("GDELT_BUDGET_MIN") or 0) * 60  # 0: no limit
    start = time.monotonic()
    with mock.patch.object(sources, "_gdelt_json", functools.partial(sources._gdelt_json, timeout=TIMEOUT)):
        for i, (iso3, name) in enumerate(todo):
            if failed >= GIVE_UP:
                kept += len(todo) - i
                print(f"  gdelt: {failed} failures in a row, stopped; {len(todo) - i} countries not asked", flush=True)
                break
            if budget and time.monotonic() - start >= budget:
                kept += len(todo) - i
                print(f"  gdelt: out of time, stopped; {len(todo) - i} countries not asked", flush=True)
                break
            tone, error = ask(sources.fetch_gdelt_tone, name)
            protests = None
            if error is None:
                protests, error = ask(sources.fetch_gdelt_protests, name)
            if error is not None:
                kept += 1
                failed += 1
                print(f"  gdelt {iso3}: kept the last file ({error})", flush=True)
                continue
            failed = 0
            ctx.write_json(f"data/gdelt/{iso3}.json", {
                "tone": None if tone is None or tone.empty else figure(charts.tone_chart(tone)),
                "protests": None if protests is None or protests.empty else figure(charts.protest_chart(protests)),
            })
    if kept:
        print(f"  gdelt: {kept} countries kept their last file", flush=True)
