"""Case studies: what the index showed the year before major political shocks."""

import html

import pandas as pd
import streamlit as st

from prm import cases, charts, data, interpret, ui

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
              f'<div style="font-size:1.5rem;font-weight:700;line-height:1.1">{counts[v]} of {len(cases.CASES)}</div>'
              f'<div style="font-size:0.75rem;color:{color};margin-top:2px">{v}</div></div>'
              for v, (color, _) in cases.VERDICTS.items())
    + "</div>",
    unsafe_allow_html=True,
)
table = pd.DataFrame([{
    "country": names.get(c.iso3, c.iso3), "event": c.title, "date": pd.Timestamp(c.date),
    "verdict": readings[c.key].get("verdict") or "No data", "tier": readings[c.key].get("tier"),
    "rank": readings[c.key].get("rank"),
} for c in cases.CASES])
# Fixed widths: auto-sized columns get squeezed to fit and cut the event names. Tier and rank, the verdict rule's
# inputs, fit at 1280 px only without the flag and score columns; each case below shows both.
st.dataframe(
    table, hide_index=True,
    column_config={
        "country": st.column_config.TextColumn("Country", width=110),
        "event": st.column_config.TextColumn("Event", width=245),
        "date": st.column_config.DateColumn("Date", format="D MMM YYYY", width=110),
        "verdict": st.column_config.TextColumn("Verdict", width=140),
        "tier": st.column_config.TextColumn("Tier", width=100, help="In the year before the event"),
        "rank": st.column_config.NumberColumn("Rank", format="%d", help="In the year before the event. 1 = riskiest"),
    },
)

# --- One case ----------------------------------------------------------------------------------------------
keys = [c.key for c in cases.CASES]
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
        f'<span style="color:var(--sg-muted);font-size:0.875rem">{html.escape(meaning)}</span>',
        unsafe_allow_html=True,
    )
    m1, m2, m3 = st.columns(3)
    m1.metric(f"Score in {r['before']} (of 100)", f"{r['score']:.0f}", help=r["tier"])
    m2.metric(f"Global rank (of {r['n']})", f"{r['rank']}", help="1 = the riskiest economy that year")
    m3.metric(f"Change since {r['before'] - 3}", "—" if r["change"] is None else interpret.signed(r["change"]),
              help="Composite score, three years before the year before the event")

    rows = hist[hist["iso3"] == case.iso3].sort_values("year")
    st.plotly_chart(charts.case_history(rows, case.date, case.title), config={"displayModeBar": False})

    left, right = st.columns(2)
    with left:
        st.markdown(f"**What moved in the three years before ({r['before'] - 3}–{r['before']})**")
        if r["pillar_moves"]:
            for pillar, move in sorted(r["pillar_moves"].items(), key=lambda kv: -abs(kv[1])):
                arrow = "▲" if move >= 1 else ("▼" if move <= -1 else "■")
                st.markdown(f"- {arrow} {pillar}: {interpret.signed(move)} points")
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
        st.markdown(ui.money(note))

st.caption(
    "Read with care: the scores are rebuilt with data as published today, which includes later revisions, and "
    "governance scores for a year are only published the following year. These cases show how the index "
    "behaves; for a test of prediction, see the track record on the Methodology page."
)
ui.cite("index", "wikipedia", "ucdp_def")
ui.footer()
