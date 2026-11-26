"""The one-page PDF briefs: files/briefs/<ISO3>.pdf for every country with the default weights, built as the profile's
"Download PDF brief" button builds them (prm.report.country_pdf).

The brief is dated with the snapshot date, not the build day: its masthead, the reading's "Coming up" countdowns and
the PDF's creation date (which also seeds the file ID). So an unchanged country gives the same bytes every week."""

from __future__ import annotations

import contextlib
import datetime as dt
import os
from types import SimpleNamespace
from unittest import mock

import pandas as pd

from prm import content, interpret, report, scoring, ui


@contextlib.contextmanager
def dated(day: dt.date):
    """report.country_pdf and interpret.country_reading as if run on `day`."""
    stamp = dt.datetime.combine(day, dt.time(), dt.timezone.utc)

    class Brief(report._Brief):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.set_creation_date(stamp)

    with mock.patch.object(report, "_Brief", Brief), \
            mock.patch.object(report, "dt", SimpleNamespace(date=SimpleNamespace(today=lambda: day))), \
            mock.patch.object(pd.Timestamp, "today", classmethod(lambda cls, tz=None: pd.Timestamp(day))):
        yield


def write_bytes(path, blob: bytes) -> None:
    """Atomic, as common.write_json: a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_bytes(blob)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def build(ctx, only: list[str] | None = None) -> None:
    day = dt.date.fromisoformat(str(ctx.core.get("snapshot_date") or ctx.built[:10]))
    table = ui.master_table(ctx.core, ctx.values, ctx.scores, ctx.history)
    rows = table.set_index("iso3")
    events = content.load_events()
    series = ctx.core["series"]
    total = 0
    with dated(day):
        for iso3 in only or table["iso3"]:
            reading = interpret.country_reading(iso3, table, ctx.values, ctx.scores, ctx.history, events,
                                                ctx.core.get("flows"), ctx.year, series)
            flags = scoring.red_flags(ctx.values.loc[iso3]) + scoring.stability_flags(series, iso3)
            country_hist = ctx.history[ctx.history["iso3"] == iso3].sort_values("year")
            blob = report.country_pdf(reading, rows.loc[iso3], country_hist, flags, ctx.year)
            write_bytes(ctx.web / "files" / "briefs" / f"{iso3}.pdf", blob)
            total += len(blob)
    print(f"  briefs: {total / 1e6:.1f} MB", flush=True)
