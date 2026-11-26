"""data/assessments/index.json ({ISO3: meta + file}) and <ISO3>.json ({iso3, file, meta, body}), exactly as written."""

from prm import content


def build(ctx) -> None:
    found = content.load_assessments()
    ctx.write_json("data/assessments/index.json", {k: {**v["meta"], "file": v["file"]} for k, v in found.items()})
    for iso3, a in found.items():
        ctx.write_json(f"data/assessments/{iso3}.json", {"iso3": iso3, "file": a["file"], "meta": a["meta"], "body": a["body"]})
