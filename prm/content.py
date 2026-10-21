"""Analyst content: written country assessments and the events watchlist.

Assessments are Markdown files in assessments/, named by ISO3 code (NGA.md).
The block between the two '---' lines at the top holds structured fields.
Events live in data/events.csv, one row per event.
"""

from __future__ import annotations

import datetime as dt
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
            value = value.split(" #", 1)[0].strip().strip('"').strip("'")
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
            meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
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
        df = pd.read_csv(EVENTS_PATH, dtype=str, keep_default_na=False)
    except Exception:
        return pd.DataFrame(columns=EVENT_COLUMNS)
    for col in EVENT_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[EVENT_COLUMNS].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["iso3"] = df["iso3"].str.upper().str.strip()
    # A hand-edited file can have typos: unknown values fall back to safe defaults instead of breaking a chart
    df["significance"] = df["significance"].str.strip().str.title().where(lambda s: s.isin(SIGNIFICANCE), "Medium")
    df["category"] = df["category"].str.strip().where(lambda s: s.isin(EVENT_CATEGORIES), "Other")
    return df.sort_values("date").reset_index(drop=True)


def csv_row(values: dict) -> str:
    """One CSV line in the events.csv column order (quotes fields with commas)."""
    cells = []
    for col in EVENT_COLUMNS:
        cell = str(values.get(col, "")).replace('"', "'")
        cells.append(f'"{cell}"' if ("," in cell or "\n" in cell) else cell)
    return ",".join(cells)


def build_assessment_markdown(f: dict) -> str:
    """Render the assessment builder form into the standard Markdown file."""
    judgments = "\n".join(
        f"{i}. {j['text'].strip()} — **{j['term']}** (~{j['probability']}%)"
        for i, j in enumerate(f.get("judgments", []), start=1)
        if j.get("text", "").strip()
    ) or "1. "
    scenario_rows = "\n".join(
        f"| {s['name']} | {s['probability']}% | {s['description'].strip()} | {s['signposts'].strip()} |"
        for s in f.get("scenarios", [])
    )
    watch = "\n".join(f"- {w.strip()}" for w in f.get("indicators_to_watch", "").split("\n") if w.strip()) or "- "
    srcs = "\n".join(f"- {w.strip()}" for w in f.get("sources", "").split("\n") if w.strip()) or "- "
    today = f.get("date") or dt.date.today().isoformat()
    return f"""---
country: {f.get('country', '')}
iso3: {f.get('iso3', '')}
author: {f.get('author', '')}
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
