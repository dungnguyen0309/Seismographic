"""Hotspots: where fighting is happening now (UCDP candidate events), where conflict news is rising (GDELT), and the
calendar of dated events (elections, deadlines) kept in data/events.csv."""

import datetime as dt
import html
import os

import pandas as pd
import streamlit as st

from prm import charts, config, content, hotspots, ui

core, year, values, scores = ui.load()
hist = ui.history(core)
table = ui.master_table(core, values, scores, hist)
options, names = ui.country_options(core["countries"])
region_of = dict(zip(table["iso3"], table["region"]))
MAINTAINER = os.environ.get("SEISMOGRAPHIC_MAINTAINER") == "1"  # shows the tools for editing data/events.csv

h = hotspots.load()
meta = h["meta"]
today = pd.Timestamp(dt.date.today())
# a news file the daily run stopped updating would keep showing an old reading as "now"
news_stale = bool(meta.get("gdelt_through")) and pd.Timestamp(meta["gdelt_through"]) < today - pd.Timedelta(days=3)
signal = hotspots.escalation(None if news_stale else h["gdelt"])
news_note = "" if len(signal) else (" The news data is out of date." if news_stale
                                    else " The news data has not been collected yet.")
board = hotspots.board(table, h["monthly"], h["cells"], signal)


def day(value) -> str:
    """30 Sep 2026 (no leading zero, on every platform)."""
    d = pd.Timestamp(value)
    return f"{d.day} {d:%b %Y}"


through = meta.get("ucdp_through")
has_ucdp = bool(through) and not h["cells"].empty  # no files is no data, not "no fighting"
window = ""
if has_ucdp:
    start = pd.Timestamp(through) - pd.Timedelta(days=hotspots.WINDOW_DAYS - 1)
    if meta.get("ucdp_from"):  # the files may cover less than the window
        start = max(start, pd.Timestamp(meta["ucdp_from"]))
    window = f"{day(start)} to {day(through)}"
as_of = [f"UCDP events through {day(through)}" if through else "",
         f"conflict news through {day(meta['gdelt_through'])}" if meta.get("gdelt_through") else ""]
ui.hero("Hotspots", " · ".join(p for p in as_of if p))

# --- Headline numbers ------------------------------------------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric("Hotspots tracked", len(board),
          help=f"Countries with at least {hotspots.MIN_EVENTS_90D} UCDP events or {hotspots.MIN_DEATHS_90D} deaths in "
               f"the last {hotspots.WINDOW_DAYS} days, an Escalating conflict-news signal, or a composite score of "
               f"{hotspots.MIN_COMPOSITE} or more.")
k2.metric("Escalating now", int((board["status"] == "Escalating").sum()) if len(signal) else "—",
          help=f"Hotspots where the share of news about conflict in the last {hotspots.RECENT_DAYS} days is at least "
               f"{hotspots.ESCALATING_RATIO:g} times its usual level over the {hotspots.WINDOW_DAYS} days (GDELT)."
               + news_note)
k3.metric(f"UCDP events, {hotspots.WINDOW_DAYS} days", f"{int(h['cells']['events'].sum()):,}" if has_ucdp else "—",
          help="Organised violence with at least one death" + (f", {window}," if has_ucdp else "") + " from UCDP's "
               "candidate events: preliminary data, published about six weeks after the month ends and revised later."
               + ("" if has_ucdp else " The UCDP data is not available."))
k4.metric(f"Deaths, {hotspots.WINDOW_DAYS} days", f"{int(h['cells']['deaths'].sum()):,}" if has_ucdp else "—",
          help="UCDP's best estimate of the deaths in those events" + (f", {window}." if has_ucdp else "."))

# --- Tabs --------------------------------------------------------------------------------------------------------
TABS = {"board": "Board", "map": "Map", "calendar": "Calendar"}
tab_board, tab_map, tab_calendar = ui.url_tabs(TABS, key="hs_tab")

# Cards: 3 to a row, 2 when the board is narrow, 1 on phones (sized by the board's own width, not the window's)
CARD_CSS = """
.st-key-hs_board { container: sghs / inline-size; }
.st-key-hs_grid { display: grid !important; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px !important;
  align-items: stretch !important; }  /* a row's cards share its height (each card fills its layout wrapper) */
@container sghs (max-width: 900px) { .st-key-hs_grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@container sghs (max-width: 560px) { .st-key-hs_grid { grid-template-columns: minmax(0, 1fr); } }
[class*="st-key-hs_card_"] { gap: 6px !important; padding: 12px 14px !important; background: var(--sg-raised);
  border: 1px solid var(--sg-line); border-radius: 10px; }
[class*="st-key-hs_card_"]:hover { border-color: var(--sg-line-strong); }
[class*="st-key-hs_card_"] > :last-child { margin-top: auto; }  /* the Open buttons line up along a row */
[class*="st-key-hs_card_"] [data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }
.sg-hs { display: flex; flex-direction: column; gap: 6px; font-size: 0.875rem; color: var(--sg-soft); line-height: 1.4; }
.sg-hs-id { display: flex; align-items: center; gap: 10px; min-width: 0; }
.sg-hs-id img { width: 30px; height: 22px; object-fit: cover; border-radius: 3px; flex: none;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.14); }
.sg-hs-name { font-weight: 700; font-size: 1rem; color: var(--sg-strong); overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; }
.sg-hs-meta { color: var(--sg-muted); font-size: 0.75rem; }
.sg-hs b { color: var(--sg-strong); font-variant-numeric: tabular-nums; }
"""
STATUS_TONE = {"Escalating": "var(--sg-worse)", "Easing": "var(--sg-better)"}  # Steady and Quiet stay muted ink


def card(r) -> str:
    flag = config.flag_url(r.iso2)
    score = "" if pd.isna(r.composite) else f"{r.composite:.0f} · "
    tone = STATUS_TONE.get(r.status, "var(--sg-muted)")
    word = f'<span style="color:{tone};font-weight:600">{r.status}</span> · '
    if r.iso3 not in signal.index:
        word, news = "", "No conflict-news data yet"  # nothing collected: a status word would read as a finding
    elif r.status == "Quiet":
        news = "Too little coverage to read"
    elif pd.isna(r.ratio):  # a usual level of zero: no ratio to show
        news = "Conflict news up from none on most days"
    else:
        news = (f'<span aria-hidden="true">×{r.ratio:.1f}</span><span class="sg-sr">{r.ratio:.1f} times the</span> '
                "conflict news vs its 90-day level")
    if not has_ucdp:
        fighting = "No UCDP data"
    elif r.events_90d:
        fighting = f"<b>{r.events_90d:,}</b> UCDP events · <b>{r.deaths_90d:,}</b> deaths in the last 90 days"
    else:
        fighting = "No UCDP events in the last 90 days"
    lines = [
        '<div class="sg-hs-id">' + (f'<img src="{flag}" alt="">' if flag else "")
        + f'<span class="sg-hs-name">{html.escape(str(r.name))}</span></div>',
        f"<div>{ui.tier_badge(r.tier, prefix=score)}</div>",
        f"<div>{word}{news}</div>",
        f"<div>{fighting}</div>",
    ]
    if pd.notna(r.last_event):
        lines.append(f'<div class="sg-hs-meta">Last event {day(r.last_event)}</div>')
    if r.analyst_rating:
        lines.append(f'<div class="sg-hs-meta">Analyst: {ui.tier_badge(r.analyst_rating)}</div>')
    return '<div class="sg-hs">' + "".join(lines) + "</div>"


with tab_board:
    if tab_board.open:
        st.html(f"<style>{CARD_CSS}</style>")
        regions = sorted(board["region"].dropna().unique())
        with st.container(horizontal=True, vertical_alignment="bottom", wrap=True):
            region = st.selectbox("Region", ["All regions", *regions], key="hs_region", width=290)
            in_region = board if region == "All regions" else board[board["region"] == region]
            counts = in_region["status"].value_counts()
            status = st.segmented_control(
                "Status", ["All", *hotspots.STATUS_ORDER], default="All", key="hs_status",
                format_func=lambda s: (f"{s} ({len(in_region) if s == 'All' else counts.get(s, 0)})"
                                       if len(signal) or s == "All" else s),
                disabled=signal.empty,  # every count would be Quiet until the news data is collected
                help=f"From the share of news about conflict: Escalating = at least {hotspots.ESCALATING_RATIO:g} "
                     f"times its usual level in the last {hotspots.RECENT_DAYS} days; Easing = "
                     f"{hotspots.EASING_RATIO:g} times or less; Quiet = fewer than {hotspots.MIN_ARTICLES_7D} "
                     "articles in the week, too few to read." + news_note) or "All"
        shown = in_region if status == "All" else in_region[in_region["status"] == status]
        if shown.empty:
            st.info("No hotspots with these filters.")
        else:
            with st.container(key="hs_board"), st.container(key="hs_grid"):
                for r in shown.itertuples(index=False):
                    with st.container(key=f"hs_card_{r.iso3}"):
                        st.markdown(card(r), unsafe_allow_html=True)
                        st.button(f"Open {r.name}", key=f"hs_open_{r.iso3}", on_click=ui._jump, args=(r.iso3,),
                                  type="tertiary", icon=":material/arrow_forward:")
        ui.cite("ucdp_ged", "gdelt", "index", "flags")

with tab_map:
    if tab_map.open:
        cells = h["cells"].assign(region=h["cells"]["iso3"].map(region_of))
        regions = sorted(cells["region"].dropna().unique())
        region = st.selectbox("Region", ["All regions", *regions], key="hs_map_region", width=290)
        where = "" if region == "All regions" else f", {config.region_short(region)}"
        if region != "All regions":
            cells = cells[cells["region"] == region]
        st.header(f"Events in the last {hotspots.WINDOW_DAYS} days{where}",
                  help=(f"{window}. " if window else "") + "Each circle is a 0.5° grid cell: its area shows the deaths, its colour the most "
                       "common type of violence there. Events placed only to a country sit at its centre. Click a "
                       "circle to open the country.")
        if cells.empty:
            st.info("No UCDP events in this window." if has_ucdp else "No UCDP data.")
        else:
            map_event = st.plotly_chart(
                charts.hotspot_map(cells, names, hotspots.VIOLENCE, zoom=region != "All regions"),
                config={"displayModeBar": False}, on_select="rerun", selection_mode="points", key="hs_map_click")
            if iso3 := ui.clicked_iso3(map_event):
                ui.go_to_country(iso3)
        monthly = h["monthly"]
        if region != "All regions":
            monthly = monthly[monthly["iso3"].map(region_of) == region]
        by_month = monthly.groupby("month")["events"].sum()
        if len(by_month):
            st.header(f"UCDP events by month{where}")
            bars = charts.yearly_bars(pd.to_datetime(by_month.index).strftime("%b %Y"), by_month.to_numpy(), "Events",
                                      charts.WORSE, "events")
            st.plotly_chart(bars.update_xaxes(type="category"), config={"displayModeBar": False})
        ui.cite("ucdp_ged", "natural_earth")

with tab_calendar:
    if tab_calendar.open:
        events = content.load_events()
        if MAINTAINER and (undated := events.attrs.get("undated")):
            st.warning(f"{undated} row{'s' if undated > 1 else ''} in data/events.csv "
                       f"{'have' if undated > 1 else 'has'} no date in the YYYY-MM-DD form, so the calendar leaves "
                       f"{'them' if undated > 1 else 'it'} out.")
        if not events.empty:
            events["country"] = events.apply(lambda r: names.get(r["iso3"], r["country"] or r["iso3"]), axis=1)
            today = pd.Timestamp(dt.date.today())
            upcoming = events[events["date"] >= today]
            past = events[events["date"] < today]

            windows = {"Next 90 days": upcoming[upcoming["date"] <= today + pd.Timedelta(days=90)],
                       "Next 12 months": upcoming[upcoming["date"] <= today + pd.Timedelta(days=365)],
                       "All upcoming": upcoming, "Past": past.sort_values("date", ascending=False)}
            span = st.segmented_control("Show", list(windows), default="Next 12 months",
                                        format_func=lambda w: f"{w} ({len(windows[w])})")
            shown = windows[span or "Next 12 months"]

            if shown.empty:
                st.info("No events in this window.")
            else:
                st.plotly_chart(charts.events_timeline(shown), config={"displayModeBar": False})
                st.dataframe(
                    shown.assign(date=shown["date"].dt.strftime("%d %b %Y"))[
                        ["country", "date", "event", "category", "significance", "notes", "source_url"]
                    ],
                    hide_index=True,
                    column_config={
                        "country": ui.NAME_COLUMN,
                        # fixed: auto widths cut the date and the header below
                        "date": st.column_config.TextColumn("Date", width=120),
                        "event": st.column_config.TextColumn("Event", width="large"),
                        # one category in every row says nothing
                        "category": "Category" if shown["category"].nunique() > 1 else None,
                        "significance": st.column_config.TextColumn("Significance", width=130),
                        "notes": "Notes",
                        "source_url": st.column_config.LinkColumn("Source", display_text="Link"),
                    },
                )
                ui.cite("ifes")

            if not upcoming.empty:
                st.header("Upcoming events on the globe")
                next_event = upcoming.sort_values("date").groupby("iso3").first()
                days = (next_event["date"] - today).dt.days.clip(lower=0)
                ui.globe_panel(
                    table=table, hist=hist, flows=None, metric="composite", metric_label="Next event",
                    key="evt_globe", custom=days.where(days <= 365),
                    colorscale=config.reversed_scale(config.map_colorscale("social")), value_range=(0, 365),
                    value_format="days", ticks=["now", "in 6 months", "in a year"],
                    notes={iso3: f"{e.event} · {e.date:%d %b %Y} · {e.significance} significance"
                           for iso3, e in next_event.iterrows()},
                    empty_label="no event in the next year",
                    layers={"spin": True, "extrude": False, "flows": False, "conflict": False}, height=360,
                )
                ui.cite("ifes", "natural_earth")
        elif MAINTAINER:
            st.info(
                "The event calendar is empty. Add events to the project's `data/events.csv`; "
                "the helper below writes each line for you."
            )
        else:
            st.info("No events on the calendar yet.")

        # --- Maintainer tools: a helper to write a new CSV line ---------------------------------------------
        if MAINTAINER:
            with st.expander("Add an event (creates a line to paste into data/events.csv)", expanded=events.empty):
                with st.form("event_form"):
                    c1, c2 = st.columns(2)
                    when = c1.date_input("Date", value=dt.date.today() + dt.timedelta(days=30))
                    iso3 = c2.selectbox("Country", options, format_func=lambda i: names.get(i, i))
                    event = st.text_input("Event", placeholder="e.g. Presidential election, first round")
                    c3, c4 = st.columns(2)
                    category = c3.selectbox("Category", content.EVENT_CATEGORIES)
                    significance = c4.selectbox("Significance", content.SIGNIFICANCE, index=1)
                    notes = st.text_input("Why it could move risk")
                    source = st.text_input("Source URL", placeholder="https://…")
                    submitted = st.form_submit_button("Create CSV line")
                if submitted:
                    if not event.strip():
                        st.warning("Give the event a name.")
                    else:
                        line = content.csv_row({
                            "date": when.isoformat(), "iso3": iso3, "country": names.get(iso3, iso3),
                            "event": event.strip(), "category": category, "significance": significance,
                            "source_url": source.strip(), "notes": notes.strip(),
                        })
                        st.markdown("Copy this line and add it at the bottom of the project's `data/events.csv`:")
                        st.code(line, language="text")

            st.markdown(
                "Where to find events: [IFES ElectionGuide](https://www.electionguide.org/elections/type/upcoming/) "
                "(election calendar) · [Crisis Group CrisisWatch](https://www.crisisgroup.org/crisiswatch) (monthly "
                "conflict tracker with an outlook) · IMF programme review dates and Article IV schedules · government "
                "budget calendars."
            )
ui.footer()
