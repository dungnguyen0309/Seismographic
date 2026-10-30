"""Seismographic — entry point.

Run locally with:  streamlit run streamlit_app.py
"""

import streamlit as st

from prm import brand, config, ui

st.set_page_config(
    page_title=config.APP_TITLE,
    page_icon=brand.svg("icon"),
    layout="wide",
    initial_sidebar_state="auto",  # open on wide screens, folded away on phones (the dock is the phone menu)
)
st.logo(brand.svg("logo"), icon_image=brand.svg("icon"), size="large")

# Four sections of up to five pages each; every page is also reachable from Find in the bottom bar
pages = {
    "Monitor": [
        st.Page("app_pages/overview.py", title="Global overview", icon=":material/public:", default=True),
        st.Page("app_pages/country.py", title="Country profile", icon=":material/flag:", url_path="country"),
        st.Page("app_pages/compare.py", title="Compare countries", icon=":material/compare_arrows:", url_path="compare"),
        st.Page("app_pages/changes.py", title="Score changes", icon=":material/trending_up:", url_path="changes"),
        st.Page("app_pages/video.py", title="Live video", icon=":material/live_tv:", url_path="video"),
    ],
    "Briefings": [
        st.Page("app_pages/regions.py", title="Regions", icon=":material/travel_explore:", url_path="regions"),
        st.Page("app_pages/conflict.py", title="Conflict & displacement", icon=":material/crisis_alert:",
                url_path="conflict"),
        st.Page("app_pages/economy.py", title="Economic stress", icon=":material/monitoring:", url_path="economy"),
        st.Page("app_pages/watchlist.py", title="Events watchlist", icon=":material/event:", url_path="watchlist"),
        st.Page("app_pages/cases.py", title="Case studies", icon=":material/history:", url_path="cases"),
    ],
    "Tools": [
        st.Page("app_pages/explorer.py", title="Indicator explorer", icon=":material/explore:", url_path="explorer"),
        st.Page("app_pages/stress.py", title="Stress test", icon=":material/bolt:", url_path="stress"),
        st.Page("app_pages/builder.py", title="Assessment builder", icon=":material/edit_note:", url_path="builder"),
        st.Page("app_pages/downloads.py", title="Data downloads", icon=":material/download:", url_path="data"),
    ],
    "Reference": [
        st.Page("app_pages/intro.py", title="Introduction", icon=":material/waving_hand:", url_path="introduction"),
        st.Page("app_pages/guide.py", title="Guide", icon=":material/lightbulb:", url_path="guide"),
        st.Page("app_pages/methodology.py", title="Methodology", icon=":material/functions:", url_path="methodology"),
        st.Page("app_pages/glossary.py", title="Glossary & legend", icon=":material/help:", url_path="glossary"),
        st.Page("app_pages/sources.py", title="Sources", icon=":material/verified:", url_path="sources"),
    ],
}

page = st.navigation(pages, expanded=True)
st.set_page_config(page_title=f"{page.title} · {config.APP_TITLE}")  # each page names itself
with ui.guard("The sidebar"):
    ui.sidebar()
with ui.guard("Page setup"):
    ui.page_setup(page.url_path, pages)
ui.page_error_boundary(page.run)  # a page that ends early (ui.end_page) still returns here
with ui.guard("The bottom bar"):
    ui.dock(page.url_path, pages)  # after the page: fixed to the bottom of the screen and last in the tab order
