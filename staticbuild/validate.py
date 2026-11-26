"""python -m staticbuild.validate [DIR]: exits 1 (and says why) unless the built site in DIR (default web/) is sane."""

import datetime as dt
import json
import re
import sys
from pathlib import Path

from prm import config, data

CORE = ["meta", "config", "countries", "values", "scores", "history", "master", "outlook", "wgi_trend"]
MAX_BYTES = 5 * 1024 * 1024
MIN_COUNTRIES = 180
REQUIRED = re.compile(r"export\s+const\s+required\s*=\s*\[([^\]]*)\]")
ISO3 = re.compile(r"^[A-Z]{3}$")


def analysis_years(today: dt.date | None = None) -> set[int]:
    """Years the built site may describe: the analysis year, and in January also the year before, so the daily
    refreshes keep passing until the weekly rebuild moves the site to the new year."""
    today = today or dt.date.today()  # data.analysis_year() is today's calendar year
    return {today.year, today.year - 1} if today.month == 1 else {today.year}


def column(table: dict, name: str) -> list:
    if name not in table["columns"]:
        raise ValueError(f"no column {name}")
    return [r[table["columns"].index(name)] for r in table["rows"]]


def fsi_fields(node, where: str) -> list[str]:
    """Names containing 'fsi' on per-country records: table columns, rows of dicts with an iso3, dicts keyed by ISO3.
    Aggregate statistics may carry the name; a per-country Fragile States Index value may not."""
    found = []
    if isinstance(node, dict):
        names = []
        if isinstance(node.get("columns"), list):
            names += [c for c in node["columns"] if isinstance(c, str)]
        if "iso3" in node or sum(bool(ISO3.match(k)) for k in node) >= 3:
            names += list(node)
            for v in node.values():
                if isinstance(v, dict):
                    names += list(v)
        found += [f"{where}: {n}" for n in names if "fsi" in n.lower()]
        for k, v in node.items():
            found += fsi_fields(v, f"{where}.{k}")
    elif isinstance(node, list):
        for v in node[:3000]:
            found += fsi_fields(v, where)
    return found


def check(root: Path) -> list[str]:
    problems = []

    def load(rel: str):
        try:
            return json.loads((root / rel).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            problems.append(f"{rel}: missing or not valid JSON ({type(exc).__name__})")

    def guard(label: str, fn, *args) -> None:  # one broken file must not hide the other failures
        try:
            fn(*args)
        except Exception as exc:
            problems.append(f"{label}: could not be checked ({type(exc).__name__}: {exc})")

    docs = {name: load(f"data/{name}.json") for name in CORE}
    if not (root / "data/tokens.css").is_file():
        problems.append("data/tokens.css: missing")
    countries, scores, history, meta = docs["countries"], docs["scores"], docs["history"], docs["meta"]
    pillars = ["composite", *(p.key for p in config.PILLARS)]

    def countries_check():
        if len(countries["rows"]) < MIN_COUNTRIES:
            problems.append(f"countries: {len(countries['rows'])} rows, need at least {MIN_COUNTRIES}")

    def scores_check():
        composite = [v for v in column(scores, "composite") if v is not None]
        if len(composite) < data.MIN_SCORED:
            problems.append(f"composite: {len(composite)} scored economies, need at least {data.MIN_SCORED}")
        for name in pillars:
            bad = [v for v in column(scores, name) if v is not None and not 0 <= v <= 100]
            if bad:
                problems.append(f"scores {name}: {len(bad)} values outside 0-100 (e.g. {bad[0]})")

    def history_check():
        for name in pillars:
            bad = [v for v in column(history, name) if v is not None and not 0 <= v <= 100]
            if bad:
                problems.append(f"history {name}: {len(bad)} values outside 0-100 (e.g. {bad[0]})")
        years = sorted(set(column(history, "year")))
        if not years:
            problems.append("history: no rows")
            return
        if years != list(range(config.HISTORY_START, years[-1] + 1)):
            problems.append(f"history years {years} are not contiguous from {config.HISTORY_START}")
        if years[-1] not in analysis_years():
            problems.append(f"history ends in {years[-1]}, the analysis year is {data.analysis_year()}")

    def api_check():
        listed = load("api/v1/countries.json")
        for rel in ("index", "dictionary", "countries.empty"):
            load(f"api/v1/{rel}.json")
        if listed and countries and listed.get("count") != len(countries["rows"]):
            problems.append(f"api/v1/countries.json: lists {listed.get('count')} economies, "
                            f"data/countries.json has {len(countries['rows'])}")
        for iso3 in column(countries, "iso3"):
            if not (root / f"api/v1/countries/{iso3}.json").is_file():
                problems.append(f"api/v1/countries/{iso3}.json: missing")
                break

    def vercel_check():
        path = root / "vercel.json"
        if not path.is_file():
            return problems.append("vercel.json: missing")
        rules = json.loads(path.read_text(encoding="utf-8"))
        for rule in [*rules.get("rewrites", []), *rules.get("redirects", [])]:
            dest = rule["destination"].split("?")[0]
            if "." in dest.rsplit("/", 1)[-1] and not re.search(r"[:$]", dest) and not (root / dest.lstrip("/")).is_file():
                problems.append(f"vercel.json: destination {dest} does not exist")

    guard("data/countries.json", countries_check) if countries else None
    guard("data/scores.json", scores_check) if scores else None
    guard("data/history.json", history_check) if history else None
    guard("api/v1", api_check)
    guard("vercel.json", vercel_check)
    if meta and meta.get("year") not in analysis_years():
        problems.append(f"meta year {meta.get('year')} is not the analysis year {data.analysis_year()}")
    for page in sorted((root / "js/pages").glob("*.js")):
        if m := REQUIRED.search(page.read_text(encoding="utf-8")):
            for rel in re.findall(r"""['"]([^'"]+)['"]""", m.group(1)):
                if not (root / rel.lstrip("/")).is_file():
                    problems.append(f"{page.name}: required file {rel} does not exist")
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.stat().st_size > MAX_BYTES:
            problems.append(f"{path.relative_to(root).as_posix()}: {path.stat().st_size / 1e6:.1f} MB, over 5 MB")
    scanned = [*(root / "data").rglob("*.json"), *(root / "api").rglob("*.json"),
               *(root / "tests/fixtures").rglob("*.json")]
    for path in sorted(scanned):
        rel = path.relative_to(root).as_posix()
        try:
            problems += fsi_fields(json.loads(path.read_text(encoding="utf-8")), rel)
        except ValueError:
            problems.append(f"{rel}: not valid JSON")
    return list(dict.fromkeys(problems))


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "web"
    problems = check(root)
    for p in problems:
        print(f"FAIL {p}")
    print(f"{len(problems)} problem(s)" if problems else f"ok: {root}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
