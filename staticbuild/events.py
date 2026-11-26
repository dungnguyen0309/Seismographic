"""data/events.json: data/events.csv as the app reads it (prm.content.load_events), dates as YYYY-MM-DD."""

from prm import content


def build(ctx) -> None:
    df = content.load_events()
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    ctx.write_json("data/events.json", ctx.table(df))
