"""Score changes: this year's index against last year's — risers, fallers, tier moves and new red flags."""

import pandas as pd
import streamlit as st

from prm import charts, config, data, interpret, scoring, ui
from prm.config import PILLARS, TIER_ORDER

core, year, values, scores = ui.load()
hist = ui.history(core)
table = ui.master_table(core, values, scores, hist)
prev_year = year - 1

ui.hero("Score changes", f"{year} compared with {prev_year}")
st.caption(f"{year} uses IMF estimates for the current year, so economic moves can still be revised.")

regions = sorted(table["region"].dropna().unique())
region = st.selectbox("Region", ["All regions", *regions], key="chg_region", width=520)  # fits the longest name
view = table if region == "All regions" else table[table["region"] == region]
moved = view.dropna(subset=["delta_1y"])

# --- Tier moves and pillar drivers -----------------------------------------------------
tier_rank = {t: i for i, t in enumerate(TIER_ORDER)}
moved = moved.assign(
    tier_move=moved["tier"].map(tier_rank) - moved["prev_tier"].map(tier_rank),
)
pillar_keys = [p.key for p in PILLARS]
prev_pillars = hist[hist["year"] == prev_year].set_index("iso3")[pillar_keys]
for p in PILLARS:
    moved[f"d_{p.key}"] = pd.to_numeric(moved[p.key] - moved["iso3"].map(prev_pillars[p.key]), errors="coerce")


def _driver(row) -> str:
    """The pillar that moved most in the same direction as the composite."""
    deltas = {p.short: row[f"d_{p.key}"] for p in PILLARS if pd.notna(row[f"d_{p.key}"])}
    if not deltas or pd.isna(row["delta_1y"]):
        return "—"
    sign = 1 if row["delta_1y"] >= 0 else -1
    pillar = max(deltas, key=lambda k: sign * deltas[k])
    return f"{pillar} {interpret.signed(deltas[pillar], 0)}"


moved["driver"] = moved.apply(_driver, axis=1)

# --- New and cleared red flags -------------------------------------------------------------
prev_values = data.get_values(core, prev_year, core["version"])
flag_rows = []
for iso3 in view["iso3"]:
    worse, eased = scoring.flag_changes(prev_values.loc[iso3], values.loc[iso3])
    for f in worse:
        flag_rows.append({"iso3": iso3, "change": "New", "severity": f["severity"], "flag_label": f["label"]})
    for f in eased:
        flag_rows.append({"iso3": iso3, "change": "Cleared", "severity": "", "flag_label": f["label"]})
flags = pd.DataFrame(flag_rows, columns=["iso3", "change", "severity", "flag_label"])
flags = flags.merge(view[["iso3", "name"]], on="iso3", how="left")

# --- Headline numbers ------------------------------------------------------------------------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Riskier", int((moved["delta_1y"] >= ui.TREND_THRESHOLD).sum()), help="Composite up by a point or more")
k2.metric("Safer", int((moved["delta_1y"] <= -ui.TREND_THRESHOLD).sum()), help="Composite down by a point or more")
k3.metric("To a riskier tier", int((moved["tier_move"] > 0).sum()))
k4.metric("To a safer tier", int((moved["tier_move"] < 0).sum()))
k5.metric("New red flags", int((flags["change"] == "New").sum()),
          help="Absolute warning thresholds crossed this year that were not crossed last year")

# --- Biggest moves -------------------------------------------------------------------------------
st.header("Biggest moves")
if moved.empty:
    st.info("No year-on-year comparison is available for this selection.")
else:
    event = st.plotly_chart(charts.change_bars(moved), config={"displayModeBar": False},
                            on_select="rerun", selection_mode="points", key="chg_bars")
    if iso3 := ui.clicked_iso3(event):
        ui.go_to_country(iso3)
    st.caption("Scores are relative, so a country can move because others changed.")

# --- Map of change ----------------------------------------------------------------------------------
st.header("Map of change")


def _change_note(r) -> str:
    tier = f"{r.prev_tier} → {r.tier} · " if pd.notna(r.tier_move) and r.tier_move != 0 else ""
    return f"{tier}main driver: {r.driver}"


change_notes = {r.iso3: _change_note(r) for r in moved.itertuples(index=False)}
ui.globe_panel(
    table=table, hist=hist, flows=None, metric="composite", metric_label=f"Change vs {prev_year}", key="chg_globe",
    in_view=set(view["iso3"]), region=None if region == "All regions" else region,
    custom=moved.set_index("iso3")["delta_1y"], colorscale=config.CHANGE_COLORSCALE, value_range=(-10, 10),
    value_format="signed", ticks=["−10 · safer", "0", "riskier · +10"], notes=change_notes,
    empty_label="no comparison", extrude_abs=True, layers={"spin": True, "flows": False, "conflict": False},
)
st.caption("Taller = bigger move. Moves beyond ±10 points share the end colour.")

# --- Tier changes --------------------------------------------------------------------------------------
st.header("Tier changes")
tiers = moved[moved["tier_move"].fillna(0) != 0].sort_values(["tier_move", "delta_1y"], ascending=False)
if tiers.empty:
    st.caption("No country changed tier.")
else:
    tiers = tiers.assign(move=tiers.apply(lambda r: f"{r['prev_tier']} → {r['tier']}", axis=1)).reset_index(drop=True)
    # Fixed widths: auto-sized columns get squeezed to fit, which cut "Moderate → Elevated" and long names.
    # No region column: even shortened it does not fit at 1280 px, and the Region filter above sets it.
    # No flag in these tables: on a phone it pushed the change off screen. The pinned name stays at most 200 px,
    # since the grid unpins everything when pins take over 60% of its width.
    event = st.dataframe(
        tiers[["iso3", "name", "trend", "move", "driver"]], hide_index=True,
        on_select="rerun", selection_mode="single-row", key="chg_tiers",
        column_config={"iso3": None,
                       "name": ui.NAME_COLUMN,
                       "trend": st.column_config.TextColumn("Change", width=90, alignment="right",
                                                            help="Composite score vs last year"),
                       "move": st.column_config.TextColumn("Tier", width=180),
                       "driver": st.column_config.TextColumn("Main driver", width=140, help="Pillar that moved most")},
    )
    ui.open_selected(event, tiers, "changes_tiers")

# --- What drove the change ------------------------------------------------------------------------------
st.header("What drove each change")
st.caption("Change in each pillar score since last year, for every country whose composite moved by a point or more.")
drivers = moved[moved["delta_1y"].abs() >= ui.TREND_THRESHOLD].sort_values("delta_1y", ascending=False)
drivers = drivers.reset_index(drop=True)
d_cols = [f"d_{k}" for k in pillar_keys]
event = st.dataframe(  # rounded numbers shown signed, so the columns sort as numbers
    # No "Main driver" column: the pillar columns show it, and without it the table fits at 1280 px
    drivers[["iso3", "name", "trend", *d_cols]].round().style.format(lambda v: interpret.signed(v, 0),
                                                                     subset=d_cols, na_rep="—"),
    hide_index=True, height=420, on_select="rerun", selection_mode="single-row", key="chg_drivers",
    placeholder="—",  # the grid draws missing cells itself and ignores the Styler's na_rep
    column_config={
        "iso3": None, "name": ui.NAME_COLUMN,
        "trend": st.column_config.TextColumn("Composite", alignment="right"),
        **{f"d_{p.key}": st.column_config.NumberColumn(p.short, help=p.label) for p in PILLARS},
    },
)
ui.open_selected(event, drivers, "changes_drivers")

# --- Red flags --------------------------------------------------------------------------------------------
st.header("Red flags crossed or cleared")
if flags.empty:
    st.caption("No red flags changed.")
else:
    flags = flags.assign(severity=flags["severity"].map(lambda s: config.SEVERITY_LABEL[s]
                                                        if s else "Cleared"))
    flags = flags.sort_values(["change", "name"], ascending=[False, True]).reset_index(drop=True)
    event = st.dataframe(
        flags[["iso3", "name", "change", "severity", "flag_label"]], hide_index=True, height=380,
        on_select="rerun", selection_mode="single-row", key="chg_flags",
        column_config={"iso3": None, "name": ui.NAME_COLUMN,
                       "change": "Change",
                       "severity": "Severity", "flag_label": st.column_config.TextColumn("Red flag", width="large")},
    )
    ui.open_selected(event, flags, "changes_flags")
ui.cite("index", "ucdp_def", "imf_ara")

ui.footer()
