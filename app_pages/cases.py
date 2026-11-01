"""Case studies: what the index showed the year before major political shocks."""

import html

import pandas as pd
import streamlit as st

from prm import cases, charts, config, data, ui

core, year, values, scores = ui.load()
hist = ui.history(core)
names = dict(zip(core["countries"]["iso3"], core["countries"]["name"]))
iso2 = dict(zip(core["countries"]["iso3"], core["countries"]["iso2"]))

ui.hero("Case studies")
st.markdown(
    "Eight shocks since 2020 (coups, wars, an invasion, a default and an uprising) and what the index said about each "
    "country the year before. The verdict follows a fixed rule, shown under each case, so you can check it."
)

readings = {}
for case in cases.CASES:
    before = int(case.date[:4]) - 1
    readings[case.key] = cases.reading(case, hist, data.get_values(core, before, core["version"]))

# --- Scorecard -----------------------------------------------------------------------------------------
counts = {v: sum(1 for r in readings.values() if r.get("verdict") == v) for v in cases.VERDICTS}
st.markdown(
    '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px;margin:6px 0 10px">'
    + "".join(f'<div style="border:1px solid var(--sg-line);border-radius:10px;padding:10px 12px">'
              f'<div style="font-size:1.7rem;font-weight:700;line-height:1.1">{counts[v]} of {len(cases.CASES)}</div>'
              f'<div style="font-size:0.8rem;color:{color};margin-top:2px">{v}</div></div>'
              for v, (color, _) in cases.VERDICTS.items())
    + "</div>",
    unsafe_allow_html=True,
)
table = pd.DataFrame([{
    "key": c.key, "flag": config.flag_url(iso2.get(c.iso3)), "country": names.get(c.iso3, c.iso3), "event": c.title,
    "date": pd.Timestamp(c.date), "verdict": readings[c.key].get("verdict") or "No data",
    "score": readings[c.key].get("score"), "tier": readings[c.key].get("tier"), "rank": readings[c.key].get("rank"),
} for c in cases.CASES])
event = st.dataframe(
    table, hide_index=True, on_select="rerun", selection_mode="single-row", key="cases_table",
    column_config={
        "key": None, "flag": ui.FLAG_COLUMN, "country": "Country", "event": "Event",
        "date": st.column_config.DateColumn("Date", format="D MMM YYYY"), "verdict": "Verdict",
        "score": st.column_config.ProgressColumn("Score the year before", min_value=0, max_value=100, format="%.0f",
                                                 color="#fd8078"),
        "tier": "Tier", "rank": st.column_config.NumberColumn("Rank", format="%d", help="1 = riskiest"),
    },
)
st.caption("Tick a row for the full case.")

# --- One case ----------------------------------------------------------------------------------------------
keys = [c.key for c in cases.CASES]
clicked = event.selection.rows[0] if event and event.selection.rows else None
if clicked is not None and clicked != st.session_state.get("_case_row"):  # a new click in the table wins
    st.session_state["case_pick"] = keys[clicked]
st.session_state["_case_row"] = clicked
pick = st.selectbox("Case", keys, key="case_pick",
                    format_func=lambda k: next(f"{names.get(c.iso3, c.iso3)} · {c.title} ({c.date[:4]})"
                                               for c in cases.CASES if c.key == k))
case = next(c for c in cases.CASES if c.key == pick)
r = readings[pick]
name = names.get(case.iso3, case.iso3)

ui.country_heading(f"{name}: {case.title}", iso2.get(case.iso3), level=2)
when = pd.Timestamp(case.date)
st.markdown(f"{when:%d %B %Y} · {html.escape(case.kind)} · {html.escape(case.what)} "
            f"[Background ↗]({case.source})")

if not r.get("verdict"):
    st.info(f"The index has too little data on {name} for {r['before']} to judge this case.")
else:
    color, meaning = cases.VERDICTS[r["verdict"]]
    st.markdown(
        f'<span style="display:inline-block;border:1px solid {color};color:{color};border-radius:999px;'
        f'padding:2px 12px;font-weight:700">{r["verdict"]}</span> '
        f'<span style="color:var(--sg-muted);font-size:0.85rem">{html.escape(meaning)}</span>',
        unsafe_allow_html=True,
    )
    m1, m2, m3 = st.columns(3)
    m1.metric(f"Score in {r['before']}", f"{r['score']:.0f} / 100", border=True, height="stretch", help=r["tier"])
    m2.metric("Global rank", f"{r['rank']} of {r['n']}", border=True,
              height="stretch", help="1 = the riskiest economy that year")
    m3.metric(f"Change since {r['before'] - 3}", "—" if r["change"] is None else f"{r['change']:+.1f}",
              border=True, height="stretch", help="Composite score, three years before the year before the event")

    rows = hist[hist["iso3"] == case.iso3].sort_values("year")
    st.plotly_chart(charts.case_history(rows, case.date, case.title), config={"displayModeBar": False})

    left, right = st.columns(2)
    with left:
        st.markdown(f"**What moved in the three years before ({r['before'] - 3}–{r['before']})**")
        if r["pillar_moves"]:
            for pillar, move in sorted(r["pillar_moves"].items(), key=lambda kv: -abs(kv[1])):
                arrow = "▲" if move >= 1 else ("▼" if move <= -1 else "■")
                st.markdown(f"- {arrow} {pillar}: {move:+.1f} points")
        else:
            st.caption("Not enough history.")
    with right:
        st.markdown(f"**Red flags in {r['before']}**")
        if r["flags"]:
            for f in r["flags"]:
                st.markdown(f"- {ui.sev_mark(f['severity'])}{html.escape(f['label'])}", unsafe_allow_html=True)
        else:
            st.markdown("- None")

    note = cases.commentary(case)
    if note:
        st.markdown("### Analyst commentary")
        st.markdown(note)

st.caption(
    "Read with care: the scores are rebuilt with data as published today, which includes later revisions, and "
    "governance scores for a year are only published the following year. These cases show how the index "
    "behaves; for a test of prediction, see the track record on the Methodology page."
)
ui.cite("index", "wikipedia", "ucdp_def")
ui.footer()
