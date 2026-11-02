"""Analyst content: written country assessments and the events watchlist.

Assessments are Markdown files in assessments/, named by ISO3 code (NGA.md).
The block between the two '---' lines at the top holds structured fields.
Events live in data/events.csv, one row per event.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
from pathlib import Path

import pandas as pd

from .config import TIER_ORDER

ROOT = Path(__file__).resolve().parent.parent
ASSESSMENT_DIR = ROOT / "assessments"
EVENTS_PATH = ROOT / "data" / "events.csv"

OUTLOOKS = ["Improving", "Stable", "Deteriorating"]
CONFIDENCE = ["Low", "Moderate", "High"]
EVENT_CATEGORIES = ["Election", "Referendum", "Leadership transition", "Budget / economic", "Security", "Diplomatic", "Legal / regulatory", "Protest / social", "Other"]
SIGNIFICANCE = ["Low", "Medium", "High"]
EVENT_COLUMNS = ["date", "iso3", "country", "event", "category", "significance", "source_url", "notes"]


def parse_front_matter(text: str) -> tuple[dict, str]:
    """Split '---' front matter (key: value lines) from the Markdown body."""
    meta: dict[str, str] = {}
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return meta, text
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            body = "\n".join(lines[i + 1 :]).strip()
            return meta, body
        if ":" in line and not line.lstrip().startswith("#"):
            key, value = line.split(":", 1)
            quoted = re.match(r"""^\s*(["'])(.*?)\1\s*(?:#.*)?$""", value)  # "a #b" stays whole; "a" # note
            value = quoted.group(2) if quoted else value.split(" #", 1)[0].strip().strip('"').strip("'")
            meta[key.strip().lower()] = value
    return {}, text  # no closing '---': treat everything as body


def load_assessments() -> dict[str, dict]:
    """{ISO3: {"meta": {...}, "body": str, "file": name}} for every assessment file."""
    out: dict[str, dict] = {}
    if not ASSESSMENT_DIR.exists():
        return out
    for path in sorted(ASSESSMENT_DIR.glob("*.md")):
        if path.name.startswith("_") or path.name.upper() == "README.MD":
            continue
        try:
            # utf-8-sig: Windows editors often add a byte-order mark, which hid the front matter
            meta, body = parse_front_matter(path.read_text(encoding="utf-8-sig", errors="replace"))
        except OSError:
            continue
        iso3 = (meta.get("iso3") or path.stem).upper()[:3]
        rating = meta.get("analyst_rating", "").title()
        meta["analyst_rating"] = rating if rating in TIER_ORDER else ""
        out[iso3] = {"meta": meta, "body": body, "file": path.name}
    return out


def load_events() -> pd.DataFrame:
    if not EVENTS_PATH.exists():
        return pd.DataFrame(columns=EVENT_COLUMNS)
    try:
        text = EVENTS_PATH.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return pd.DataFrame(columns=EVENT_COLUMNS)
    try:  # a bad line (stray comma, odd byte) costs that row, not the whole watchlist
        df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False, on_bad_lines="skip")
    except Exception:
        df = pd.DataFrame(columns=EVENT_COLUMNS)
    # An unclosed quote makes pandas swallow the lines after it. Read on their own, lines lose only that row (but
    # would split a note written over several lines), so that reading is used only when a quote is left open.
    rows = [next(csv.reader([line]), []) for line in text.splitlines()]
    if len(rows) > 1 and (text.count('"') % 2 or df.empty):
        by_line = pd.DataFrame([r for r in rows[1:] if len(r) == len(rows[0])], columns=rows[0])
        if len(by_line) > len(df):
            df = by_line
    for col in EVENT_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[EVENT_COLUMNS].copy()
    # Only the date part of an ISO date (as documented): the format no longer depends on the first row, and a time
    # or UTC offset after it never moves the event to another day
    day = df["date"].str.strip().str.extract(r"^(\d{4}-\d{1,2}-\d{1,2})")[0]
    df["date"] = pd.to_datetime(day, errors="coerce", format="ISO8601")
    undated = int((df["date"].isna() & df["event"].str.strip().ne("")).sum())  # e.g. a file re-saved by Excel
    df = df.dropna(subset=["date"])
    df["iso3"] = df["iso3"].str.upper().str.strip()
    # A hand-edited file can have typos: unknown values fall back to safe defaults instead of breaking a chart
    df["significance"] = df["significance"].str.strip().str.title().where(lambda s: s.isin(SIGNIFICANCE), "Medium")
    df["category"] = df["category"].str.strip().where(lambda s: s.isin(EVENT_CATEGORIES), "Other")
    out = df.sort_values("date").reset_index(drop=True)
    out.attrs["undated"] = undated  # the watchlist says how many rows were left out
    return out


def csv_row(values: dict) -> str:
    """One CSV line in the events.csv column order (standard CSV quoting, so commas and quotes survive)."""
    out = io.StringIO()
    csv.writer(out, lineterminator="").writerow([values.get(col, "") for col in EVENT_COLUMNS])
    return out.getvalue()


def _cell(text: str) -> str:
    """Text for one Markdown table cell: one line, with '|' escaped so it stays in its column."""
    return " ".join(str(text).split()).replace("|", r"\|")


def build_assessment_markdown(f: dict) -> str:
    """Render the assessment builder form into the standard Markdown file."""
    judgments = "\n".join(
        f"{i}. {j['text'].strip()} ({j['term']}, ~{j['probability']}%)"
        for i, j in enumerate(f.get("judgments", []), start=1)
        if j.get("text", "").strip()
    ) or "1. "
    scenario_rows = "\n".join(
        f"| {s['name']} | {s['probability']}% | {_cell(s['description'])} | {_cell(s['signposts'])} |"
        for s in f.get("scenarios", [])
    )
    watch = "\n".join(f"- {w.strip()}" for w in f.get("indicators_to_watch", "").split("\n") if w.strip()) or "- "
    srcs = "\n".join(f"- {w.strip()}" for w in f.get("sources", "").split("\n") if w.strip()) or "- "
    today = f.get("date") or dt.date.today().isoformat()
    return f"""---
country: {f.get('country', '')}
iso3: {f.get('iso3', '')}
author: "{f.get('author', '')}"
date: {today}
analyst_rating: {f.get('analyst_rating', '')}
outlook: {f.get('outlook', '')}
confidence: {f.get('confidence', '')}
horizon: {f.get('horizon', '12 months')}
model_score_at_writing: {f.get('model_score', '')}
---

## Bottom line up front
{f.get('bluf', '').strip()}

## Key judgments
{judgments}

## Drivers
### Political
{f.get('drv_political', '').strip()}

### Security
{f.get('drv_security', '').strip()}

### Economic
{f.get('drv_economic', '').strip()}

### Social
{f.get('drv_social', '').strip()}

## Scenarios ({f.get('horizon', '12 months')})
| Scenario | Probability | What it looks like | Signposts |
|---|---|---|---|
{scenario_rows}

## Indicators to watch
{watch}

## Why my rating differs from the model
{f.get('divergence', '').strip() or 'My rating matches the model tier.'}

## Implications
{f.get('implications', '').strip()}

## Sources
{srcs}
"""
