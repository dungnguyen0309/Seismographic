"""Check that the events watchlist (data/events.csv) still looks ahead far enough and that every date can be read.

Run it yourself with:   python scripts/check_watchlist.py
The weekly GitHub Action runs it and opens a reminder issue when the list needs new events or date fixes.
Writes a Markdown report to stdout (and to the Action summary), and "needs_update=true|false" to $GITHUB_OUTPUT.
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from prm import content  # noqa: E402

MIN_UPCOMING = 8  # events wanted in the next six months
HORIZON_DAYS = 182
FIND_EVENTS = "https://www.electionguide.org/elections/type/upcoming/"


def main() -> int:
    events = content.load_events()
    today = pd.Timestamp(dt.date.today())
    upcoming = events[events["date"] >= today]
    soon = upcoming[upcoming["date"] <= today + pd.Timedelta(days=HORIZON_DAYS)]
    past = events[events["date"] < today]
    last = upcoming["date"].max() if not upcoming.empty else None
    undated = events.attrs.get("undated", 0)  # the page leaves these out and only tells a maintainer
    running_low = len(soon) < MIN_UPCOMING
    needs_update = running_low or undated > 0

    lines = [
        "## Events watchlist check",
        "",
        f"- Upcoming events in the next six months: **{len(soon)}** (target: at least {MIN_UPCOMING})",
        f"- All upcoming events: {len(upcoming)}; latest on {last:%d %b %Y}" if last is not None else "- No upcoming events",
        f"- Past events kept in the file (shown under *Past* on the page): {len(past)}",
        f"- Rows left out for a date not in the YYYY-MM-DD form: {undated}",
        "",
    ]
    if undated:
        lines += [
            f"**Fix the dates first.** {undated} row{'s' if undated > 1 else ''} in `data/events.csv` "
            f"{'have' if undated > 1 else 'has'} a date the watchlist cannot read (a file re-saved by Excel often "
            "turns them into D/M/YYYY). Write each date as YYYY-MM-DD.",
            "",
        ]
    if running_low:
        lines += [
            "**The watchlist is running low.** Add the next elections, referendums and other dated events:",
            "",
            f"1. Find upcoming national elections on [IFES ElectionGuide]({FIND_EVENTS}).",
            "2. Run the app with `SEISMOGRAPHIC_MAINTAINER=1`; on its *Events watchlist* page, use **Add an event** "
            "to create a line for each.",
            "3. Paste the lines at the end of `data/events.csv` on GitHub (pencil icon → *Commit changes*).",
            "",
            "This issue closes by itself once the check passes.",
        ]
    elif not undated:
        lines.append("The watchlist looks ahead far enough. Nothing to do.")
    report = "\n".join(lines)
    print(report)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(summary).write_text(report + "\n", encoding="utf-8")
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as fh:
            fh.write(f"needs_update={'true' if needs_update else 'false'}\n")
    if os.environ.get("CI"):  # the Action posts this file as the issue text
        (ROOT / "watchlist_report.md").write_text(report + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
