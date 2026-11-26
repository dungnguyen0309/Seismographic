"""data/flows.json: the UNHCR refugee flows (origin, host, year, value) the globe and the conflict page read."""

import pandas as pd


def build(ctx) -> None:
    flows = ctx.core.get("flows")
    if flows is None:
        flows = pd.DataFrame(columns=["origin", "host", "year", "value"])
    ctx.write_json("data/flows.json", ctx.table(flows))
