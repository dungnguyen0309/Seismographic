"""Open data: the index, its inputs, red flags, history and the conflict outlook as tidy tables, with a data
dictionary. Used by the Data downloads page and the JSON API (prm/api.py)."""

from __future__ import annotations

import datetime as dt
import io
import json

import numpy as np
import pandas as pd

from . import config, scoring
from .config import INDICATORS, PILLARS

PILLAR_KEYS = [p.key for p in PILLARS]

TABLES: dict[str, str] = {
    "index": "The index today: one row per economy",
    "indicators": "Every indicator behind the index: value, year and 0–100 risk score (one row per economy and indicator)",
    "red_flags": "Absolute warning thresholds crossed (one row per flag)",
    "history": "The index for every year since " + str(config.HISTORY_START),
    "conflict_outlook": "Chance of a new armed conflict next year, for countries at peace",
    "dictionary": "What every column means",
}

_PILLAR_TEXT = {p.key: f"{p.label} pillar score, 0–100 (100 = riskiest)" for p in PILLARS}
DICTIONARY: list[tuple[str, str, str]] = [
    ("*", "iso3", "ISO 3166-1 alpha-3 country code"),
    ("*", "name", "Country or economy name (World Bank)"),
    ("index", "region", "World Bank region"),
    ("index", "income", "World Bank income group"),
    ("index, history", "composite", "Composite risk score, 0–100: the weighted average of the pillars (100 = riskiest "
                                    "in the sample; the index is relative, not a probability)"),
    *[("index, history", k, text) for k, text in _PILLAR_TEXT.items()],
    ("index, history", "tier", "Risk tier: " + ", ".join(f"{t.label} ({t.lower:g}+)" for t in config.TIERS)),
    ("index, history", "rank", "Rank by composite score (1 = highest risk)"),
    ("index", "coverage", "Share of the indicators with data, %"),
    ("index", "red_flags", "Number of absolute warning thresholds crossed"),
    ("index", "change_1y", "Change in the composite score since last year, points"),
    ("index", "population", "Population (World Bank)"),
    ("index", "gdp_per_person", "GDP per person, current US$ (IMF)"),
    ("indicators", "indicator", "Indicator key (see the indicator list on the Methodology page)"),
    ("indicators", "label", "Indicator name"),
    ("indicators", "pillar", "Pillar the indicator belongs to"),
    ("indicators", "value", "Latest value, in the unit given"),
    ("indicators", "unit", "Unit of the value"),
    ("indicators", "year", "Year of the value"),
    ("indicators", "risk_score", "The value turned into a 0–100 risk score (percentile or log scale)"),
    ("indicators", "source", "Publisher of the data"),
    ("red_flags", "flag", "Indicator that crosses the threshold"),
    ("red_flags", "severity", "Critical, Serious or Watch"),
    ("red_flags", "description", "The threshold crossed"),
    ("red_flags", "value", "The country's value"),
    ("history", "year", "Year the scores describe"),
    ("history", "battle_deaths", "Battle-related deaths that year (UCDP)"),
    ("conflict_outlook", "probability", "Estimated chance that an armed conflict (25+ battle deaths) starts next year"),
    ("conflict_outlook", "times_average", "The probability divided by the average for countries at peace"),
    ("conflict_outlook", "conflict_past_5y", "1 if the country had an armed conflict in the previous five years"),
    ("conflict_outlook", "status", "At peace, or already in armed conflict (no probability given)"),
]


def _names(core: dict) -> pd.DataFrame:
    return core["countries"].set_index("iso3")[["name", "region", "income"]]


def index_table(core: dict, values: pd.DataFrame, scores: pd.DataFrame, hist: pd.DataFrame | None) -> pd.DataFrame:
    out = _names(core).join(scores[["composite", *PILLAR_KEYS, "tier", "rank", "coverage"]], how="left")
    out["red_flags"] = scoring.flag_counts(values).reindex(out.index).fillna(0).astype(int)
    if hist is not None and not hist.empty:
        prev = hist[hist["year"] == int(hist["year"].max()) - 1].set_index("iso3")["composite"]
        out["change_1y"] = out["composite"] - prev.reindex(out.index)
    out["population"] = values["population"].reindex(out.index)
    out["gdp_per_person"] = values["gdppc"].reindex(out.index)
    out["rank"] = out["rank"].astype("Int64")
    return out.reset_index().sort_values("rank", na_position="last").reset_index(drop=True)


def indicators_table(core: dict, values: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    names = _names(core)["name"]
    frames = []
    for ind in INDICATORS:
        if ind.key not in values:
            continue
        year = values.get(f"{ind.key}__year", pd.Series(np.nan, index=values.index))
        frames.append(pd.DataFrame({
            "iso3": values.index, "name": names.reindex(values.index).to_numpy(), "indicator": ind.key,
            "label": ind.label, "pillar": config.PILLAR_BY_KEY[ind.pillar].short, "value": values[ind.key].to_numpy(),
            "unit": ind.unit, "year": year.to_numpy(),
            "risk_score": scores.get(f"n_{ind.key}", pd.Series(np.nan, index=values.index)).reindex(values.index).to_numpy(),
            "source": ind.source,
        }))
    out = pd.concat(frames, ignore_index=True).dropna(subset=["value"])
    out["year"] = out["year"].astype("Int64")
    return out.sort_values(["iso3", "indicator"]).reset_index(drop=True)


def red_flags_table(core: dict, values: pd.DataFrame) -> pd.DataFrame:
    names = _names(core)["name"]
    rows = [{"iso3": iso3, "name": names.get(iso3, iso3), "flag": f["key"],
             "severity": config.SEVERITY_LABEL[f["severity"]], "description": f["label"], "value": f["value"]}
            for iso3 in values.index for f in scoring.red_flags(values.loc[iso3])]
    return pd.DataFrame(rows, columns=["iso3", "name", "flag", "severity", "description", "value"])


def history_table(core: dict, hist: pd.DataFrame) -> pd.DataFrame:
    out = hist[["iso3", "year", "composite", *PILLAR_KEYS, "tier", "rank", "battle_deaths_raw"]]
    out = out.rename(columns={"battle_deaths_raw": "battle_deaths"})
    out.insert(1, "name", out["iso3"].map(_names(core)["name"]))
    out["rank"] = out["rank"].astype("Int64")
    return out.sort_values(["iso3", "year"]).reset_index(drop=True)


def outlook_table(core: dict, outlook) -> pd.DataFrame:
    cols = ["iso3", "name", "probability", "times_average", "conflict_past_5y", "status"]
    if outlook is None:
        return pd.DataFrame(columns=cols)
    out = outlook.predictions.rename(columns={"relative": "times_average", "recent_conflict": "conflict_past_5y"})
    out["name"] = out["iso3"].map(_names(core)["name"])
    out["conflict_past_5y"] = out["conflict_past_5y"].astype(int)
    return out[cols].sort_values("probability", ascending=False, na_position="last").reset_index(drop=True)


def dictionary_table() -> pd.DataFrame:
    rows = [{"table": "(all)" if t == "*" else t, "column": c, "meaning": m} for t, c, m in DICTIONARY]
    rows += [{"table": "(tables)", "column": name, "meaning": text} for name, text in TABLES.items()]
    return pd.DataFrame(rows)


def build(core: dict, values: pd.DataFrame, scores: pd.DataFrame, hist: pd.DataFrame | None, outlook=None) -> dict:
    return {
        "index": index_table(core, values, scores, hist),
        "indicators": indicators_table(core, values, scores),
        "red_flags": red_flags_table(core, values),
        "history": history_table(core, hist) if hist is not None else pd.DataFrame(),
        "conflict_outlook": outlook_table(core, outlook),
        "dictionary": dictionary_table(),
    }


def meta(core: dict, year: int, weights: dict[str, float]) -> dict:
    return {
        "title": config.APP_TITLE,
        "index_year": year,
        "data_version": core.get("version"),
        "generated": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "weights": {k: float(v) for k, v in weights.items()},
        "scale": "0–100, 100 = highest risk in the sample (relative, not a probability)",
        "terms": "Data come from the publishers listed on the Sources page; their terms apply. "
                 "Cite the original sources.",
    }


def records(df: pd.DataFrame) -> list[dict]:
    """JSON-ready rows: NaN becomes null, numbers are rounded."""
    return json.loads(df.to_json(orient="records", double_precision=4, force_ascii=False))


def to_json(tables: dict, info: dict) -> bytes:
    return json.dumps({"meta": info, **{k: records(v) for k, v in tables.items()}}, ensure_ascii=False).encode("utf-8")


def to_excel(tables: dict, info: dict) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame(list(info.items()), columns=["field", "value"]).astype(str).to_excel(
            writer, sheet_name="about", index=False)
        for name, frame in tables.items():
            frame.to_excel(writer, sheet_name=name[:31], index=False)
        for sheet in writer.book.worksheets:
            sheet.freeze_panes = "A2"
            for column in sheet.columns:
                width = max(len(str(c.value or "")) for c in list(column)[:200])
                sheet.column_dimensions[column[0].column_letter].width = min(max(10, width + 2), 60)
    return buffer.getvalue()
