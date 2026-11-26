"""Trim the globe's Natural Earth outlines to what web/js/lib/globe.js reads, to keep the first visit small.

Keeps the ISO_A3, ADM0_A3 and ADMIN properties, rounds coordinates to 4 decimal places (about 11 m) and writes compact
JSON in place. Running it again changes nothing.

python scripts/trim_geojson.py [file.geojson ...]   (default: web/vendor/geo/ne_110m.geojson and ne_50m.geojson)
"""

import json
import sys
from pathlib import Path

KEEP = ("ISO_A3", "ADM0_A3", "ADMIN")
GEO = Path(__file__).resolve().parent.parent / "web" / "vendor" / "geo"


def rounded(c):
    return [rounded(x) for x in c] if isinstance(c, list) else round(c, 4)


def trim(path: Path) -> None:
    geojson = json.loads(path.read_text(encoding="utf-8"))
    for f in geojson["features"]:
        f["properties"] = {k: f["properties"].get(k) for k in KEEP}
        if f.get("geometry"):
            f["geometry"]["coordinates"] = rounded(f["geometry"]["coordinates"])
    path.write_text(json.dumps(geojson, separators=(",", ":"), ensure_ascii=False), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    for p in [Path(a) for a in sys.argv[1:]] or [GEO / "ne_110m.geojson", GEO / "ne_50m.geojson"]:
        before = p.stat().st_size
        trim(p)
        print(f"{p.name}: {before:,} -> {p.stat().st_size:,} bytes")
