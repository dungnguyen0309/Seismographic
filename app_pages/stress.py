"""Stress test: apply one economic shock to many countries at once and see who crosses a risk tier or a red flag."""

import pandas as pd
import streamlit as st

from prm import charts, config, data, stress, ui

core, year, values, scores = ui.load()
hist = ui.history(core)
table = ui.master_table(core, values, scores, hist)

ui.hero("Stress test", "Apply one economic shock to many countries at once and see who crosses a risk tier or a "
                       "red-flag line.")

CUSTOM = "Custom"
FIRST = next(iter(stress.SCENARIOS))
KEYS = {s.key: f"stress_{s.key}" for s in stress.SHOCKS}
INCOMES = ["Low income", "Lower middle income", "Upper middle income", "High income"]


def _set(shocks: dict[str, float]) -> None:
    for s in stress.SHOCKS:
        st.session_state[KEYS[s.key]] = float(shocks.get(s.key, 0.0))


def _preset() -> None:
    if (name := st.session_state["stress_scenario"]) in stress.SCENARIOS:
        _set(stress.SCENARIOS[name])


def _custom() -> None:
    st.session_state["stress_scenario"] = CUSTOM


def _clear() -> None:
    _set({})
    _custom()


# Widget state is dropped when you leave the page, so seed it each visit: a shared link (?shock=...) first, then the
# last shocks used in this session, then the first scenario
if "stress_scenario" not in st.session_state:
    seed = stress.decode(st.query_params.get("shock")) or st.session_state.get("_stress_last") or stress.SCENARIOS[FIRST]
    st.session_state["stress_scenario"] = next((n for n, v in stress.SCENARIOS.items() if v == seed), CUSTOM)
    _set(seed)

with st.container(border=True):
    c1, c2, c3 = st.columns([1.3, 1, 1])
    c1.selectbox("Scenario", [*stress.SCENARIOS, CUSTOM], key="stress_scenario", on_change=_preset,
                 help="Round-number versions of past world-wide shocks, to start from. Countries hit are scored "
                      "against today's values, so the yardstick stays fixed.")
    regions = c2.multiselect("Regions hit", sorted(table["region"].dropna().unique()), key="stress_regions",
                             placeholder="All regions")
    incomes = c3.multiselect("Income groups hit", [i for i in INCOMES if i in set(table["income"])],
                             key="stress_incomes", placeholder="All income groups")
    # The sliders fold away, so the results sit right under the scenario on a phone too; the label says what is set
    set_now = [f"{s.label} {st.session_state[KEYS[s.key]]:+g} {s.unit}" for s in stress.SHOCKS
               if st.session_state[KEYS[s.key]]]
    with st.expander("Shocks: " + (" · ".join(set_now) if set_now else "none"), icon=":material/tune:",
                     key="stress_shocks"):  # the key keeps it open while the label changes
        for row in range(0, len(stress.SHOCKS), 4):  # row by row, so phones list them in order
            for col, s in zip(st.columns(4), stress.SHOCKS[row:row + 4]):
                col.slider(f"{s.label}, {s.unit}", s.low, s.high, step=s.step, key=KEYS[s.key], on_change=_custom,
                           format="%+.1f" if s.step < 1 else "%+.0f")
        st.button("Clear shocks", on_click=_clear, type="tertiary", icon=":material/restart_alt:")

shocks = {s.key: float(st.session_state[KEYS[s.key]]) for s in stress.SHOCKS if st.session_state[KEYS[s.key]]}
st.session_state["_stress_last"] = shocks
if not shocks:
    st.query_params.pop("shock", None)
    st.info("Pick a scenario or move a slider.")
    st.stop()
st.query_params["shock"] = stress.encode(shocks)  # the address bar now holds a link to this exact test

in_scope = table
if regions:
    in_scope = in_scope[in_scope["region"].isin(regions)]
if incomes:
    in_scope = in_scope[in_scope["income"].isin(incomes)]
scope = tuple(sorted(in_scope["iso3"])) if (regions or incomes) else None
result = data.get_stress(core, year, ui.weights_tuple(), tuple(sorted(shocks.items())), scope, core["version"])
summary = stress.summary(result)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Countries hit", summary["countries"], border=True)
k2.metric("Move up a tier", summary["tier_up"], border=True,
          help=f"Severe tier: {summary['severe_before']} today → {summary['severe_after']} under stress")
k3.metric("New red flags", summary["new_flags"], border=True,
          help=f"New or more severe, in {summary['with_new_flags']} countries")
k4.metric("Average change", "—" if pd.isna(summary["mean_delta"]) else f"{summary['mean_delta']:+.1f}", border=True,
          help="Composite score points, countries hit")

# --- Globe -------------------------------------------------------------------------------------------------------
frame = table.join(result, on="iso3")
hit = frame[frame["hit"] & frame["composite_before"].notna()]


def _note(r) -> str:
    parts = [f"{r.tier_before} → {r.tier_after}"] if r.tier_move and r.tier_move > 0 else []
    return " · ".join(parts + list(r.new_flags))


notes = {r.iso3: _note(r) for r in hit.itertuples(index=False)}
ui.globe_panel(
    table=table, hist=hist, flows=None, metric="composite", metric_label="Change under stress", key="stress_globe",
    in_view=set(hit["iso3"]), custom=hit.set_index("iso3")["delta"], colorscale=config.CHANGE_COLORSCALE,
    value_range=(-10, 10), value_format="signed", ticks=["▼ −10 safer", "no change", "riskier +10 ▲"],
    notes={k: v for k, v in notes.items() if v}, empty_label="not hit", extrude_abs=True,
    layers={"spin": True, "flows": False, "conflict": False},
)

# --- Who crosses a line ----------------------------------------------------------------------------------------
st.header("Who crosses a line")
show = st.segmented_control("Show", ["Crossing a line", "All countries hit"], default="Crossing a line",
                            key="stress_show", label_visibility="collapsed") or "Crossing a line"
rows = hit if show == "All countries hit" else hit[(hit["tier_move"] > 0) | (hit["new_flag_count"] > 0)]
rows = rows.assign(
    tier_change=[f"{a} → {b}" if m else str(b) for a, b, m in zip(rows["tier_before"], rows["tier_after"],
                                                                     rows["tier_move"].fillna(0) != 0)],
    flags_text=rows["new_flags"].map(" · ".join),
).sort_values(["tier_move", "new_flag_count", "delta"], ascending=False).reset_index(drop=True)
if rows.empty:
    st.caption("No country crosses a tier or a red-flag line under these shocks.")
else:
    event = st.dataframe(
        # What crossed a line comes first; the scores behind it follow
        rows[["iso3", "flag", "name", "tier_change", "delta", "flags_text", "composite_before", "composite_after"]],
        hide_index=True, on_select="rerun", selection_mode="single-row", key="stress_table",
        height=min(520, 36 * (len(rows) + 1) + 4),
        column_config={
            "iso3": None, "flag": ui.FLAG_COLUMN, "name": "Country",
            "composite_before": st.column_config.NumberColumn("Today", format="%.0f"),
            "composite_after": st.column_config.ProgressColumn("Under stress", min_value=0, max_value=100,
                                                               format="%.0f", color=config.TIER_COLORS["Elevated"]),
            "delta": st.column_config.NumberColumn("Change", format="%+.1f"),
            "tier_change": st.column_config.TextColumn("Tier", width="medium"),
            "flags_text": st.column_config.TextColumn("New or worse red flags", width="large"),
        },
    )
    ui.open_selected(event, rows, "stress_rows")

left, right = st.columns(2)
with left:
    st.markdown("**Tiers today and under stress**")
    st.plotly_chart(charts.tier_shift(hit["tier_before"].dropna(), hit["tier_after"].dropna()),
                    config={"displayModeBar": False})
with right:
    st.markdown("**Red-flag lines crossed**")
    crossed = hit["new_flags"].explode().dropna()
    if crossed.empty:
        st.caption("None.")
    else:
        counts = crossed.value_counts().rename_axis("flag").reset_index()
        st.plotly_chart(charts.ranked_bars(counts, "count", "flag", charts.WORSE, "countries"),
                        config={"displayModeBar": False})


def _csv() -> bytes:
    cols = ["iso3", "name", "region", "income", "composite_before", "composite_after", "delta", "tier_before",
            "tier_after", "flags_before", "flags_after"]
    out = hit[cols].assign(new_flags=hit["new_flags"].map(" | ".join))
    return out.round(2).to_csv(index=False).encode("utf-8")


st.download_button("Download results (CSV)", data=_csv, file_name="seismographic-stress-test.csv", mime="text/csv",
                   type="tertiary")
ui.cite("imf", "wdi", "index")
