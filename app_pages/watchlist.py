"""Events watchlist: elections, deadlines and other dated risk events you track."""

import datetime as dt
import os

import pandas as pd
import streamlit as st

from prm import charts, config, content, ui

core, year, values, scores = ui.load()
hist = ui.history(core)
table = ui.master_table(core, values, scores, hist)
options, names = ui.country_options(core["countries"])
MAINTAINER = os.environ.get("SEISMOGRAPHIC_MAINTAINER") == "1"  # shows the tools for editing data/events.csv

ui.hero("Events watchlist", "Elections and other dated events that could move a country's risk.")

events = content.load_events()
if MAINTAINER and (undated := events.attrs.get("undated")):
    st.warning(f"{undated} row{'s' if undated > 1 else ''} in data/events.csv {'have' if undated > 1 else 'has'} no "
               f"date in the YYYY-MM-DD form, so the watchlist leaves {'them' if undated > 1 else 'it'} out.")
if not events.empty:
    events["country"] = events.apply(lambda r: names.get(r["iso3"], r["country"] or r["iso3"]), axis=1)
    today = pd.Timestamp(dt.date.today())
    upcoming = events[events["date"] >= today]
    past = events[events["date"] < today]

    windows = {"Next 90 days": upcoming[upcoming["date"] <= today + pd.Timedelta(days=90)],
               "Next 12 months": upcoming[upcoming["date"] <= today + pd.Timedelta(days=365)],
               "All upcoming": upcoming, "Past": past.sort_values("date", ascending=False)}
    window = st.segmented_control("Show", list(windows), default="Next 12 months",
                                  format_func=lambda w: f"{w} ({len(windows[w])})")
    shown = windows[window or "Next 12 months"]

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
                "date": st.column_config.TextColumn("Date", width=120),  # fixed: auto widths cut the date and the header below
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
            table=table, hist=hist, flows=None, metric="composite", metric_label="Next event", key="evt_globe",
            custom=days.where(days <= 365), colorscale=config.reversed_scale(config.map_colorscale("social")),
            value_range=(0, 365), value_format="days", ticks=["now", "in 6 months", "in a year"],
            notes={iso3: f"{e.event} · {e.date:%d %b %Y} · {e.significance} significance"
                   for iso3, e in next_event.iterrows()},
            empty_label="no event in the next year", layers={"spin": True, "extrude": False, "flows": False,
                                                             "conflict": False}, height=360,
        )
        ui.cite("ifes", "natural_earth")
elif MAINTAINER:
    st.info(
        "Your watchlist is empty. Add events to the project's `data/events.csv`; "
        "the helper below writes each line for you."
    )
else:
    st.info("No events on the watchlist yet.")

# --- Maintainer tools: a helper to write a new CSV line -----------------------------------
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
            notes = st.text_input("Why it could move risk (one line)")
            source = st.text_input("Source URL", placeholder="https://…")
            submitted = st.form_submit_button("Create CSV line")
        if submitted:
            if not event.strip():
                st.warning("Give the event a name.")
            else:
                line = content.csv_row({
                    "date": when.isoformat(), "iso3": iso3, "country": names.get(iso3, iso3), "event": event.strip(),
                    "category": category, "significance": significance, "source_url": source.strip(),
                    "notes": notes.strip(),
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
