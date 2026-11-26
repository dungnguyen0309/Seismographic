"""data/hotspots/{meta,board,monthly,cells,gdelt,signal}.json, from the snapshot as app_pages/hotspots.py reads it."""

from prm import hotspots, ui


def build(ctx) -> None:
    h = hotspots.load()
    signal = hotspots.escalation(h["gdelt"])  # the page decides if the news file is too old to use
    table = ui.master_table(ctx.core, ctx.values, ctx.scores, ctx.history)
    board = hotspots.board(table, h["monthly"], h["cells"], signal)
    board["last_event"] = board["last_event"].map(lambda d: d.isoformat() if d == d and d is not None else None)
    ctx.write_json("data/hotspots/meta.json", h["meta"])
    for name, df in (("board", board), ("monthly", h["monthly"]), ("cells", h["cells"]), ("gdelt", h["gdelt"]),
                     ("signal", signal)):
        ctx.write_json(f"data/hotspots/{name}.json", ctx.table(df))
