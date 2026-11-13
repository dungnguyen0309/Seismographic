"""Shared Streamlit UI pieces: sidebar, loading, badges, tables, footer."""

from __future__ import annotations

import contextlib
import html
import logging
import os
import re
import threading

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from . import a11y, config, content, data, follow, globe, interpret
from .config import PILLARS, TIERS

WEIGHT_KEYS = {p.key: f"w_{p.key}" for p in PILLARS}
COUNTRY_PAGE = "app_pages/country.py"
COMPARE_PAGE = "app_pages/compare.py"
COMPARE_LIST = "compare_list"  # ISO3 codes picked for the Compare page, kept across pages
PAGE_KEY = "page:"  # Find's options are ISO3 codes and "page:<url path>"
log = logging.getLogger("seismographic")


# ---------------------------------------------------------------------------
# Error boundaries
# ---------------------------------------------------------------------------
def _strict() -> bool:
    """Tests set PRM_RAISE_ERRORS=1 so that a broken section fails the test instead of showing a polite note."""
    return os.environ.get("PRM_RAISE_ERRORS") == "1"


@contextlib.contextmanager
def guard(what: str):
    """Keeps one optional part of a page (news, video, a benchmark) from taking the whole page down: on an error it
    shows a one-line note instead and logs the details for the server logs. st.rerun/st.stop pass straight through
    (they are not Exceptions)."""
    try:
        yield
    except Exception:
        if _strict():
            raise
        log.exception("section failed: %s", what)
        st.caption(f"{what} can't be shown right now. The rest of the page is unaffected.")


def _reload() -> None:
    """Try again: every tab row back to its first tab, as the open one may be what failed (url_tabs rows included)."""
    rows = [str(k).removesuffix("__url") for k in st.session_state if str(k).endswith("__url")]
    for key in [k for k in st.session_state if str(k).startswith(("country_tab", "conflict_tab", "ov_tab", *rows))]:
        del st.session_state[key]
    st.query_params.pop("tab", None)
    st.query_params.pop("view", None)


class PageEnd(BaseException):
    """Raised by end_page(): the page has nothing more to draw. A BaseException, so section guards let it through."""


_boundary = threading.local()  # one script run per thread: is a page running inside page_error_boundary?


def money(text: str) -> str:
    """Markdown with each '$' kept as a dollar sign (Streamlit reads '$2bn ... $7bn' as a formula); an already
    escaped one stays as it is."""
    # code spans and fences are left alone: a backslash there would show
    return re.sub(r"(`+).+?\1|(?<!\\)\$", lambda m: m.group(0) if m.group(1) else r"\$", str(text), flags=re.S)


def end_page():
    """Stop drawing this page, like st.stop(), but let the bottom bar (drawn after the page) still appear.
    st.stop() can't be used for that: once requested, every later Streamlit call stops too."""
    if getattr(_boundary, "active", False):
        raise PageEnd
    st.stop()


def page_error_boundary(run) -> None:
    """Runs a page; if it fails, a friendly message with a way out instead of a stack trace."""
    _boundary.active = True
    try:
        run()
    except PageEnd:
        pass
    except Exception as exc:
        if _strict():
            raise
        log.exception("page failed")
        st.error("This page couldn't be drawn. Try again, or open another page: the rest of the app still works.",
                 icon=":material/error:")
        c1, c2 = st.columns([1, 1], width=420)
        c1.button("Try again", on_click=_reload, icon=":material/refresh:", key="sg_retry")
        try:  # the error screen itself must never fail
            c2.page_link("app_pages/overview.py", label="Global overview", icon=":material/public:")
        except Exception:
            pass
        with st.expander("Technical details"):
            st.code(f"{type(exc).__name__}: {str(exc)[:500]}", language=None)
    finally:
        _boundary.active = False


# ---------------------------------------------------------------------------
# Sidebar and weights
# ---------------------------------------------------------------------------
def _init_weights() -> None:
    for p in PILLARS:
        st.session_state.setdefault(WEIGHT_KEYS[p.key], p.default_weight)


def _reset_weights() -> None:
    for p in PILLARS:
        st.session_state[WEIGHT_KEYS[p.key]] = p.default_weight


def _reset_weights_from_note() -> None:
    _reset_weights()
    a11y.keep_focus(a11y.TITLE)  # the note and its button disappear: the keyboard goes to the page title


def _refresh_data() -> None:
    st.toast(data.refresh(), icon=":material/refresh:")


def decode_weights(text) -> dict[str, int] | None:
    """'50,20,20,10' (Stability, Governance, Economy, Social) from a shared link; None unless it is valid."""
    try:
        parts = [int(x) for x in str(text).split(",")]
    except ValueError:
        return None
    if len(parts) != len(PILLARS) or any(not 0 <= x <= 100 or x % 5 for x in parts) or not sum(parts):
        return None
    return {p.key: x for p, x in zip(PILLARS, parts)}


def custom_weights_label() -> str:
    """'Stability 50% · Governance 20% · …' when the weights differ from the defaults, otherwise ''."""
    w = dict(weights_tuple())
    if w == {p.key: float(p.default_weight) for p in PILLARS}:
        return ""
    return " · ".join(f"{p.short} {w[p.key] / 100:.0%}" for p in PILLARS)


def _sync_weights_link() -> None:
    """Custom weights travel in the address (?w=50,20,20,10), so a shared link shows the same scores; a link's
    weights are taken once, when it is opened."""
    if not st.session_state.get("_weights_from_link"):
        st.session_state["_weights_from_link"] = True
        if shared := decode_weights(st.query_params.get("w")):
            for key, value in shared.items():
                st.session_state[WEIGHT_KEYS[key]] = value
    if custom_weights_label():
        st.query_params["w"] = ",".join(str(int(weights()[p.key])) for p in PILLARS)
    else:
        st.query_params.pop("w", None)


def sidebar() -> None:
    _init_weights()
    _sync_weights_link()
    with st.sidebar:
        with st.expander("Index weights", expanded=False):
            st.caption(
                "How much each pillar counts in the composite score. "
                "Weights are rescaled to 100%, so only the proportions count."
            )
            for p in PILLARS:
                st.slider(p.label, min_value=0, max_value=100, step=5, key=WEIGHT_KEYS[p.key], help=p.question)
            w = dict(weights_tuple())  # what the scores use: all sliders at 0 means the defaults
            st.caption(" · ".join(f"{p.short} {w[p.key] / 100:.0%}" for p in PILLARS))
            st.button("Reset weights", on_click=_reset_weights)
        st.button(
            "Refresh data", on_click=_refresh_data, icon=":material/refresh:",
            help="Figures are cached for 12 hours. This downloads the latest from every source; the page updates "
                 "when they arrive.",
        )
        st.caption(
            f"**{config.APP_TITLE}** · built by {config.AUTHOR}  \n"
            "Educational project. Not investment or security advice."
        )


def weights() -> dict[str, float]:
    _init_weights()
    return {p.key: float(st.session_state[WEIGHT_KEYS[p.key]]) for p in PILLARS}


def weights_tuple() -> tuple[tuple[str, float], ...]:
    """The weights as shares of 100: only proportions count, so 70/50/50/30 is the default 35/25/25/15 (same
    scores, the ready-made history, no "your weights" note)."""
    w = weights()
    total = sum(w.values())
    if total <= 0:
        w, total = {p.key: float(p.default_weight) for p in PILLARS}, sum(p.default_weight for p in PILLARS)
    return tuple((p.key, w[p.key] * 100 / total) for p in PILLARS)


# ---------------------------------------------------------------------------
# Dock: a console bar along the bottom of every page (tracked-country readout + tabs + find)
# ---------------------------------------------------------------------------
DOCK_TABS = [  # (page, label, icon, url_path); the readout on the left is the way into the country page
    ("app_pages/overview.py", "Home", ":material/public:", ""),
    (COMPARE_PAGE, "Compare", ":material/compare_arrows:", "compare"),
    ("app_pages/video.py", "Live", ":material/live_tv:", "video"),
    ("app_pages/guide.py", "Guide", ":material/lightbulb:", "guide"),
]
ACCENT = "var(--sg-accent)"


def _wrap(key: str) -> str:
    """Streamlit puts each container in a layout wrapper, and that wrapper is the flex item."""
    return f'[data-testid="stLayoutWrapper"]:has(> .st-key-{key})'


_SEARCH_ICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 -960 960 960'%3E"
                "%3Cpath d='M784-120 532-372q-30 24-69 38t-83 14q-109 0-184.5-75.5T120-580q0-109 75.5-184.5T380-840q109 0 "
                "184.5 75.5T640-580q0 44-14 83t-38 69l252 252-56 56ZM380-400q75 0 127.5-52.5T560-580q0-75-52.5-127.5T380-760"
                "q-75 0-127.5 52.5T200-580q0 75 52.5 127.5T380-400Z'/%3E%3C/svg%3E")  # Material "search"; encoded, since a raw < in a style tag gets it stripped
_ON = '[class*="st-key-sg_tab_on"] a'
_SIDEBAR_OPEN = 'body:has(section[data-testid="stSidebar"][aria-expanded="true"])'
DOCK_CSS = f"""
/* room under the page for the dock: two rows on tablets, its compact rows on phones, one row on desktop */
[data-testid="stMainBlockContainer"] {{ padding-bottom: 8.5rem !important; }}
@media (max-width: 640px), (min-width: 1024px) {{ [data-testid="stMainBlockContainer"] {{ padding-bottom: 6rem !important; }} }}
.st-key-sg_dock {{
  position: fixed !important; z-index: 1000; left: 0; right: 0; bottom: 0; width: auto !important;
  container-type: inline-size; container-name: sgdock;
  background: var(--sg-bar); border-top: 1px solid var(--sg-line);
  padding: 7px 1rem calc(7px + env(safe-area-inset-bottom)) !important;
  gap: 8px 14px !important; align-items: center !important; justify-content: space-between !important;
  transition: left .25s ease;
}}
/* the same side padding as the page (Streamlit's wide layout switches to 5rem at 864px), so the edges line up */
@media (min-width: 864px) {{ .st-key-sg_dock {{ padding-left: 5rem !important; padding-right: 5rem !important; }} }}
@media (min-width: 768px) {{
  body:has(section[data-testid="stSidebar"][aria-expanded="true"]) .st-key-sg_dock {{ left: 300px; }}
}}
/* desktop with the sidebar open: the sidebar already lists the pages, so the dock keeps only the readout and Find,
   in a small bar at the bottom right of the page column instead of a strip across it */
@media (min-width: 1024px) {{
  {_SIDEBAR_OPEN} .st-key-sg_tabs > [data-testid="stLayoutWrapper"]:not(:has(> .st-key-sg_tab_off_find)) {{
    display: none !important; }}
  /* container-type off: an inline-size container can't shrink to its content */
  {_SIDEBAR_OPEN} .st-key-sg_dock {{ container-type: normal; left: auto; right: 5rem; bottom: 12px;
    flex-wrap: nowrap !important; gap: 4px !important; padding: 5px !important;
    border: 1px solid var(--sg-line); border-radius: 12px; }}
  {_SIDEBAR_OPEN} {_wrap("sg_read")} {{ flex: 0 1 auto !important; max-width: 320px; }}
  {_SIDEBAR_OPEN} .st-key-sg_read {{ background: transparent; border-color: transparent; min-height: 52px; }}
  {_SIDEBAR_OPEN} .st-key-sg_read:hover {{ background: var(--sg-hover); }}
  {_SIDEBAR_OPEN} {_wrap("sg_tabs")} {{ margin-left: 0; }}
}}
/* phones: both rows tighter, the tabs still 44px tall */
@media (max-width: 640px) {{
  .st-key-sg_dock {{ padding: 4px 0.75rem calc(4px + env(safe-area-inset-bottom)) !important; gap: 4px 14px !important; }}
}}
/* never fade or flash while the page re-runs */
.st-key-sg_dock [data-stale], [data-stale]:has(> .st-key-sg_dock) {{ opacity: 1 !important; transition: none !important; }}
/* focus: the page's 2px ring; the readout's link is see-through and covers the readout, so the ring goes round it */
.st-key-sg_dock a:focus, .st-key-sg_dock button:focus {{ outline: none !important; box-shadow: none !important; }}
.st-key-sg_dock a:focus-visible, .st-key-sg_dock button:focus-visible,
.st-key-sg_read:has(a:focus-visible) {{ outline: 2px solid {ACCENT} !important; outline-offset: 2px; }}

/* readout: the tracked country (shown first, rendered last so the tabs never wait for it) */
{_wrap("sg_read")} {{ order: -1; flex: 1 1 260px !important; max-width: 440px; min-width: 0; }}
.st-key-sg_read {{ position: relative; background: var(--sg-panel); border: 1px solid var(--sg-line); border-radius: 8px;
  padding: 6px 10px 6px 8px !important; overflow: visible !important; min-height: 46px; }}
.st-key-sg_read:hover {{ background: var(--sg-hover); }}
.st-key-sg_read [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
.st-key-sg_read > [data-testid="stElementContainer"] {{ flex: 1 1 auto !important; min-width: 0; }}
.st-key-sg_read_link, .st-key-sg_read_link * {{ position: static !important; }}
.st-key-sg_read_link a {{ position: absolute !important; inset: 0; opacity: 0; z-index: 1; }}
{_wrap("sg_read_link")} {{ position: absolute !important; inset: 0; }}
.sg-read {{ display: flex; align-items: center; gap: 10px; min-width: 0; width: 100%; }}
.sg-tier {{ width: 3px; align-self: stretch; min-height: 30px; border-radius: 2px; background: var(--sg-c); flex: none; }}
.sg-read img {{ width: 26px; height: 19px; object-fit: cover; border-radius: 3px; flex: none;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.14); }}
.sg-read-text {{ min-width: 0; flex: 1; line-height: 1.25; }}
.sg-read-name {{ font-weight: 700; font-size: 0.875rem; color: var(--sg-strong); white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; }}
.sg-read-meta {{ font-size: 0.75rem; color: var(--sg-muted); white-space: nowrap; }}
.sg-read-meta b {{ color: var(--sg-strong); }}

/* tabs */
{_wrap("sg_tabs")} {{ flex: 0 0 auto !important; margin-left: auto; }}  /* right-aligned, with or without the readout */
.st-key-sg_tabs {{ gap: 2px !important; }}
.st-key-sg_tabs > [data-testid="stLayoutWrapper"] {{ flex: 0 0 64px !important; min-width: 0; }}
.st-key-sg_tabs [data-testid="stElementContainer"], .st-key-sg_tabs [data-testid="stPageLink"],
.st-key-sg_tabs [data-testid="stPageLink"] > div, .st-key-sg_tabs [data-testid="stPopover"] {{ width: 100% !important; }}
.st-key-sg_tabs a, .st-key-sg_tabs button {{
  position: relative; flex-direction: column !important; align-items: center !important; justify-content: center !important;
  gap: 2px !important; padding: 7px 2px 5px !important; height: 52px; min-height: 0 !important; width: 100% !important;
  border: none !important; box-sizing: border-box;
  border-radius: 6px !important; background: transparent !important;
}}
.st-key-sg_tabs [data-testid="stElementContainer"], .st-key-sg_tabs a {{ margin: 0 !important; }}
.st-key-sg_tabs a:hover, .st-key-sg_tabs button:hover {{ background: var(--sg-hover) !important; }}
.st-key-sg_tabs a p, .st-key-sg_tabs button p {{ font-size: 0.75rem !important;
  margin: 0 !important; white-space: nowrap; line-height: 1.2 !important; }}
.st-key-sg_tabs a span, .st-key-sg_tabs a p, .st-key-sg_tabs button p, .st-key-sg_tabs button span {{ color: var(--sg-faint) !important; }}
.st-key-sg_tabs [data-testid="stIconMaterial"] {{ font-size: 1.3rem !important; }}
.st-key-sg_tabs button [aria-hidden="true"], .st-key-sg_tabs button [data-testid="stIconMaterial"],
.st-key-sg_tabs button span:has(> [data-testid="stIconMaterial"]) {{ display: none !important; }}
/* margin: drawn at 1.3rem in the 1rem slot the font icons take, so icon and label line up with the links */
.st-key-sg_tabs button::before {{ content: ""; width: 1.3rem; height: 1.3rem; margin: -0.15rem 0; flex: none;
  background: var(--sg-faint);
  -webkit-mask: url("{_SEARCH_ICON}") center / contain no-repeat; mask: url("{_SEARCH_ICON}") center / contain no-repeat; }}
.st-key-sg_tabs button[aria-expanded="true"]::before {{ background: {ACCENT}; }}
.st-key-sg_tabs button span[data-has-shortcut] {{ display: flex !important; flex-direction: column; align-items: center;
  gap: 2px; }}
/* active tab: bright ink and a short needle line on top */
.st-key-sg_tabs {_ON} p, .st-key-sg_tabs {_ON} span, .st-key-sg_tabs a:focus:not(:focus-visible) p,
.st-key-sg_tabs a:focus:not(:focus-visible) span {{
  color: {ACCENT} !important; }}
.st-key-sg_tabs {_ON}::before, .st-key-sg_tabs a:focus:not(:focus-visible)::before {{
  content: ""; position: absolute; top: 0; left: 28%; right: 28%; height: 2px; border-radius: 0 0 2px 2px;
  background: {ACCENT};
}}
/* the moment a tab is tapped it takes over the highlight, before the next page has loaded (pointer taps only:
   keyboard focus just shows the focus ring and the current page keeps its highlight) */
.st-key-sg_dock:has(a:focus:not(:focus-visible)) {_ON}:not(:focus) p,
.st-key-sg_dock:has(a:focus:not(:focus-visible)) {_ON}:not(:focus) span {{
  color: var(--sg-faint) !important; }}
.st-key-sg_dock:has(a:focus:not(:focus-visible)) {_ON}:not(:focus)::before {{ display: none; }}

/* narrow screens: the readout on one line on top, the tabs spread across a row underneath */
@container sgdock (max-width: 640px) {{
  {_wrap("sg_read")} {{ flex: 1 1 100% !important; max-width: none; }}
  .st-key-sg_read {{ min-height: 0; padding: 3px 10px 3px 8px !important; }}
  .sg-tier {{ min-height: 16px; }}
  .sg-read img {{ width: 22px; height: 16px; }}
  .sg-read-text {{ display: flex; align-items: baseline; gap: 10px; }}
  .sg-read-name {{ min-width: 0; }}
  {_wrap("sg_tabs")} {{ flex: 1 1 100% !important; }}
  .st-key-sg_tabs > [data-testid="stLayoutWrapper"] {{ flex: 1 1 0 !important; }}
  .st-key-sg_tabs a, .st-key-sg_tabs button {{ height: 44px; padding: 4px 2px 3px !important; gap: 1px !important; }}
}}
"""


# Colour tokens (config.INK) as CSS variables, so styles name a role (--sg-muted), not a hex value
TOKENS_CSS = ":root { " + " ".join(f"--sg-{name}: {value};" for name, value in config.INK.items()) + " }"
GLOBAL_CSS = """
/* page frame: less dead space above the content, but clear of the 3.75rem top bar */
[data-testid="stMainBlockContainer"] { padding-top: 4.6rem !important; }
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] { padding-top: 4.4rem !important; padding-left: 1rem !important;
                                         padding-right: 1rem !important; }
}
/* video cards: titles read like the news cards (no link underline, at most three lines) */
[class*="st-key-vidcard_"] [data-testid="stMarkdownContainer"] a { color: var(--sg-text) !important; text-decoration: none;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
[class*="st-key-vidcard_"] [data-testid="stMarkdownContainer"] a:hover { color: var(--sg-strong) !important; text-decoration: underline; }
/* Rows reflow by their own width, not the window's (the sidebar takes 300px of a laptop screen):
   - headline numbers (a metric in the first and last column): 3 per line, 2 for a row of four, then 2 on phones
   - filter rows (a selectbox, multiselect or slider first, no charts or tables): 2 per line when narrow
   - split views (containers keyed split_*): the two sides stack when narrow
   (the headline row itself, the sgkpi container, is set up with _KPI_ROW below) */
@container sgkpi (max-width: 880px) {
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    min-width: calc(33.333% - 11px) !important; flex: 1 1 calc(33.333% - 11px) !important; }
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(4)):not(:has(> [data-testid="stColumn"]:nth-child(5))) > [data-testid="stColumn"] {
    min-width: calc(50% - 8px) !important; flex: 1 1 calc(50% - 8px) !important; }
}
@container sgkpi (max-width: 470px) {
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    min-width: calc(50% - 8px) !important; flex: 1 1 calc(50% - 8px) !important; }
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:first-child :is([data-testid="stSelectbox"], [data-testid="stMultiSelect"], [data-testid="stSlider"])):not(:has([data-testid="stMetric"], [data-testid="stPlotlyChart"], [data-testid="stDataFrame"], iframe)) {
  container: sginputs / inline-size; flex-wrap: wrap !important; }
@container sginputs (max-width: 760px) {
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    min-width: calc(50% - 8px) !important; flex: 1 1 calc(50% - 8px) !important; }
}
@container sginputs (max-width: 470px) {  /* phones: one control per line, as wide as the screen */
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { min-width: 100% !important; flex: 1 1 100% !important; }
}
/* two charts, tables or globes side by side stack when the row is narrower than they can be read at */
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(2)):not(:has(> [data-testid="stColumn"]:nth-child(3))):has(> [data-testid="stColumn"] :is([data-testid="stPlotlyChart"], [data-testid="stDataFrame"], .rg-wrap)) {
  container: sgpair / inline-size; flex-wrap: wrap !important; }
@container sgpair (max-width: 760px) {  /* only the pair's own two columns, not rows nested inside them */
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(2)):not(:has(> [data-testid="stColumn"]:nth-child(3))):has(> [data-testid="stColumn"] :is([data-testid="stPlotlyChart"], [data-testid="stDataFrame"], .rg-wrap)) > [data-testid="stColumn"] {
    min-width: 100% !important; flex: 1 1 100% !important; }
}
[class*="st-key-split_"] { container: sgsplit / inline-size; }
@container sgsplit (max-width: 1000px) {  /* beside the globe the news column is narrow: headlines get the room */
  .st-key-ov_news .sg-news-thumb { display: none !important; }
}
@container sgsplit (max-width: 900px) {  /* What-if: its result needs more width than the news column does */
  .st-key-split_whatif [data-testid="stHorizontalBlock"]:not([data-testid="stColumn"] *) > [data-testid="stColumn"] {
    min-width: 100% !important; flex: 1 1 100% !important; }
  /* stacked, the result comes first, right under the scenario buttons that change it */
  .st-key-split_whatif [data-testid="stHorizontalBlock"]:not([data-testid="stColumn"] *) > [data-testid="stColumn"]:last-child {
    order: -1; }
  /* and a one-line copy of it stays under the top bar while the sliders scroll */
  .st-key-split_whatif [data-testid="stElementContainer"]:has(.sg-whatif-live) { display: flex !important;
    position: sticky; top: 3.75rem; z-index: 5; padding: 8px 0; background: var(--sg-bg); border-bottom: 1px solid var(--sg-line); }
}
.st-key-split_whatif [data-testid="stElementContainer"]:has(.sg-whatif-live) { display: none; }  /* side by side, the full result shows */
.sg-whatif-live { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; font-size: 0.875rem; color: var(--sg-soft); }
[data-testid="stMarkdownContainer"]:has(> .sg-whatif-live) { margin-bottom: 0 !important; }  /* its backdrop covers all of it */
/* keyboard focus scrolls clear of the top bar and the dock, and of the What-if line while it sticks */
[data-testid="stMain"] { scroll-padding: 3.75rem 0 6rem; }
[data-testid="stMain"]:has(.sg-whatif-live) { scroll-padding-top: 9.5rem; }  /* the slider label and value too */
@media (max-width: 640px) { [data-testid="stMain"] { scroll-padding-bottom: 6.5rem; } }  /* the dock takes two rows */
@container sgsplit (max-width: 780px) {
  [data-testid="stHorizontalBlock"]:not([data-testid="stColumn"] *) > [data-testid="stColumn"] {
    min-width: 100% !important; flex: 1 1 100% !important; }
  /* under the globe, the news needs less height (its wrapper fixes the height as a flex-basis) */
  [data-testid="stLayoutWrapper"]:has(> .st-key-ov_news) { flex: 0 0 440px !important; height: 440px !important; }
}
/* Markdown tables (e.g. the assessment preview) scroll inside themselves instead of widening the page */
[data-testid="stMarkdownContainer"] table { display: block; max-width: 100%; overflow-x: auto; }
/* the remove (x) on multiselect chips: a 24px target (it is drawn about 15x7) without making the chip taller */
[data-testid="stMultiSelectTagsContainer"] [data-tag] button { min-width: 24px; min-height: 24px; margin: -6px -6px -6px -2px;
  display: inline-flex; align-items: center; justify-content: center; }
/* headings carry no "link to heading" icon: it was an extra tab stop on every heading */
[data-testid="stHeaderActionElements"] { display: none !important; }
/* tabs: a little tighter, and they wrap onto a second line instead of hiding behind a sideways scroll */
[data-testid="stTabs"] [role="tablist"] { gap: 2px 12px; flex-wrap: wrap; overflow-x: visible !important; }
@media (min-width: 641px) {  /* wrapped tabs never overflow, so the scroll arrows have nothing to do */
  [data-testid="stTabsScrollLeft"], [data-testid="stTabsScrollRight"] { display: none !important; }
}
@media (max-width: 640px) {  /* phones: one row that scrolls sideways inside itself */
  [data-testid="stTabs"] [role="tablist"] { flex-wrap: nowrap; overflow-x: auto !important; }
  [data-testid="stTabs"] [role="tab"] { flex: none; }
}
/* touch screens show the grid toolbar all the time: room above the grid, so it covers no text */
@media (hover: none) { [data-testid="stElementContainer"]:has([data-testid="stDataFrame"]) { margin-top: 2.25rem; } }
/* the accent is bright ink, like body text: unselected tabs, segments and pills step down to muted ink */
[data-testid="stTabs"] [role="tab"][aria-selected="false"] :is(p, span),
[data-testid="stButtonGroup"] button:is([aria-checked="false"], [aria-pressed="false"]) { color: var(--sg-muted) !important; }
[data-testid="stTabs"] [role="tab"][aria-selected="false"]:hover :is(p, span),
[data-testid="stButtonGroup"] button:is([aria-checked="false"], [aria-pressed="false"]):hover { color: var(--sg-text) !important; }
/* a switched-on toggle is an ink track: its knob turns black so the position still reads */
[data-testid="stCheckbox"] label[data-selected="true"] > span + div > div { background: var(--sg-on-accent) !important; }
/* type scale: calmer headings */
[data-testid="stMain"] h1 { font-size: clamp(1.7rem, 4vw, 2.2rem); letter-spacing: -0.01em; }
[data-testid="stMain"] h2 { font-size: clamp(1.12rem, 2.2vw, 1.32rem); letter-spacing: -0.01em; padding-top: 0.9rem; }
[data-testid="stMain"] h2.sg-panel-title { font-size: 1rem; padding: 0; margin: 0 0 2px; }
[data-testid="stMain"] h3 { font-size: clamp(1.05rem, 2vw, 1.18rem); }
[data-testid="stMain"] h4, [data-testid="stMain"] h5 { font-size: 1rem; }
/* reading measure: prose and captions wrap at about 70 characters; table cells keep their width */
[data-testid="stMain"] [data-testid="stMarkdownContainer"] :is(p, li):not(table *, .sg-news > li),
[data-testid="stMain"] [data-testid="stCaptionContainer"] { max-width: 70ch; }
/* line breaks: no lone last word in prose and captions, headings balanced. The style longhand only, so a label
   Streamlit keeps on one line (white-space: nowrap) stays on one line */
[data-testid="stMain"] :is([data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"]) :is(p, li) {
  text-wrap-style: pretty; }
[data-testid="stMain"] :is(h1, h2, h3, h4) { text-wrap-style: balance; }
/* metrics: labels wrap between words instead of being cut off or split mid-word */
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * { white-space: normal !important; overflow: visible !important;
  text-overflow: clip !important; word-break: normal !important; overflow-wrap: normal !important; hyphens: none; }
[data-testid="stMetricLabel"] p { font-size: 0.75rem !important; color: var(--sg-muted); line-height: 1.3; }
/* figures stay below the page title (1.85rem); the box is sized too, or its 36px line box pads the figure */
[data-testid="stMetricValue"], [data-testid="stMetricValue"] p { font-size: 1.5rem; line-height: 1.25; }
/* sidebar: long page names wrap, the glossary link too; rows on a 30px pitch (the line-height of 2 made the icon's
   line 28px) and less room above the sidebar's own controls, so the list and Index weights fit a laptop screen */
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] p,
section[data-testid="stSidebar"] [data-testid="stPageLink"] p { white-space: normal !important; overflow: visible !important;
  text-overflow: clip !important; line-height: 1.3; }
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] { min-height: 1.75rem; height: auto !important; margin: 0 !important;
  line-height: 1.3; align-items: center !important; padding-top: 2px !important; padding-bottom: 2px !important; }
section[data-testid="stSidebar"] [data-testid="stSidebarNavSeparator"] { padding-top: 0.5rem; }
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding-top: 0.75rem; }
/* group names read as labels, not as pages */
section[data-testid="stSidebar"] [data-testid="stNavSectionHeader"],
section[data-testid="stSidebar"] [data-testid="stNavSectionHeader"] p { font-size: 0.75rem; font-weight: 500; color: var(--sg-faint); }
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] [data-testid="stMarkdownContainer"] p { margin: 0 !important; }
/* links and focus */
[data-testid="stMain"] a { text-underline-offset: 3px; text-decoration-thickness: 1px; }
:focus-visible { outline: 2px solid var(--sg-accent) !important; outline-offset: 2px; }
::selection { background: rgba(244,243,238,0.28); }
* { scrollbar-width: thin; scrollbar-color: var(--sg-line-strong) transparent; }
/* page title: the h1 and one line about the data, on the page itself */
.sg-head { margin: 0 0 18px; }
[data-testid="stMain"] h1.sg-head-title { font-size: clamp(1.5rem, 3vw, 1.85rem); font-weight: 700; line-height: 1.2;
  padding: 0; margin: 0; color: var(--sg-strong); }
.sg-head-sub { margin: 6px 0 0; font-size: 1rem; color: var(--sg-soft); max-width: 70ch; }
/* figures: digits line up and read as data */
[data-testid="stMetricValue"], .sg-cs-num, .sg-read-meta b, .sg-fol-meta b { font-variant-numeric: tabular-nums; }
/* follow: the sync slot renders nothing */
.st-key-sg_follow_sync, [data-testid="stElementContainer"]:has(.st-key-sg_follow_sync),
.st-key-sg_a11y, [data-testid="stElementContainer"]:has(.st-key-sg_a11y) { display: none !important; }
/* accessibility: text for screen readers only */
.sg-sr { position: absolute !important; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden;
  clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
/* accessibility: the skip link appears when a keyboard user reaches it */
.sg-skip { position: fixed; left: 12px; top: 12px; z-index: 1000001; padding: 8px 14px; font-size: 0.875rem;
  color: var(--sg-strong); background: var(--sg-panel); border: 1px solid var(--sg-accent); border-radius: 8px; text-decoration: none;
  transform: translateY(-160%); }
.sg-skip:focus { transform: none; }
/* the skip link's landing spot: the next Tab goes to the first control on the page, no ring round the whole page */
[data-testid="stMainBlockContainer"]:focus { outline: none !important; }
/* captions: full opacity in a muted grey (Streamlit's 0.6 opacity also dimmed the source links to 3.8:1) */
[data-testid="stCaptionContainer"] { opacity: 1 !important; color: var(--sg-muted) !important; }
/* dark text on the ink accent (primary buttons, chips); Compare paints its chips in the country colours */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primary"] *,
[data-baseweb="tag"], [data-baseweb="tag"] *,
[data-testid="stMultiSelectTagsContainer"] span { color: var(--sg-on-accent) !important; }
/* a country's colour on Compare: a short line, like the lines in its charts */
.sg-swatch { display: inline-block; width: 16px; height: 4px; border-radius: 2px; margin-right: 8px;
  vertical-align: middle; background: var(--c); }
.sg-cmp-score { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 12px; margin: 6px 0 4px; }
.sg-cmp-score .sg-cs-num { font-size: 2rem; }
.sg-cmp-meta { font-size: 0.75rem; color: var(--sg-muted); line-height: 1.45; text-wrap-style: pretty; }
/* red-flag severity: a small drawn dot before the text */
.sg-sev { display: inline-block; width: 0.62em; height: 0.62em; border-radius: 50%; background: var(--c);
  margin-right: 0.5em; vertical-align: 0.02em; }
/* bold in the mono face barely differs from regular at body size: full weight and the brightest ink */
[data-testid="stMarkdownContainer"] :is(strong, b) { font-weight: 700; color: var(--sg-strong); }
/* following strip */
.sg-follow-head { font-size: 0.875rem; font-weight: 600; color: var(--sg-strong); margin: 4px 0 -4px; }
[class*="st-key-fol_"]:not([class*="st-key-fol_open"]) { position: relative; background: var(--sg-raised); border: 1px solid var(--sg-line);
  border-radius: 10px; padding: 8px 10px !important; }
[class*="st-key-fol_"]:not([class*="st-key-fol_open"]):hover { border-color: var(--sg-line-strong); background: var(--sg-panel); }
[class*="st-key-fol_"] [data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }
.sg-fol { display: flex; align-items: center; gap: 10px; }
.sg-fol img { width: 30px; height: 22px; object-fit: cover; border-radius: 3px; box-shadow: 0 0 0 1px rgba(255,255,255,0.14); }
.sg-fol-name { font-weight: 700; font-size: 0.875rem; color: var(--sg-strong); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  max-width: 140px; }
.sg-fol-meta { font-size: 0.75rem; color: var(--sg-muted); }
.sg-fol-meta b { color: var(--sg-strong); font-size: 0.875rem; }
[class*="st-key-fol_open_"] { position: absolute !important; inset: 0; margin: 0 !important; }
[class*="st-key-fol_open_"] button { position: absolute !important; inset: 0; width: 100%; height: 100%; opacity: 0; }
[data-testid="stElementContainer"]:has([class*="st-key-fol_open_"]) { position: absolute; inset: 0; }
/* country header */
.sg-country-id { display: flex; align-items: center; gap: 16px; min-width: 0; }
.sg-country-id img { width: 64px; height: 48px; object-fit: cover; border-radius: 6px; flex: none;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.14); }
.sg-country-name { margin: 0 !important; padding: 0 !important; font-size: clamp(1.5rem, 3vw, 1.85rem) !important;
  line-height: 1.15 !important; }
.sg-country-meta { color: var(--sg-muted); font-size: 0.875rem; margin-top: 6px; line-height: 1.45; }
.sg-cs-num { font-size: 2.25rem; font-weight: 700; line-height: 1; color: var(--sg-strong); }
.sg-cs-num span { font-size: 0.875rem; color: var(--sg-faint); font-weight: 400; margin-left: 2px; }
.sg-cs-side { display: flex; flex-direction: column; align-items: flex-start; gap: 5px; font-size: 0.875rem; color: var(--sg-soft); }
.sg-cs-line { font-size: 0.875rem; color: var(--sg-soft); }
.sg-cs-line:empty { display: none; }
.sg-cs-link { text-decoration: underline; text-underline-offset: 3px; text-decoration-thickness: 1px; }
@media (max-width: 640px) {  /* phones: a shorter header (the flag beside the name, the facts under both) */
  .sg-country-id { display: grid; grid-template-columns: auto 1fr; gap: 0 10px; }
  .sg-country-id > div { display: contents; }
  .sg-country-id img { width: 32px; height: 24px; }
  .sg-country-name { font-size: 1.35rem !important; }
  .sg-country-meta { grid-column: 1 / -1; font-size: 0.75rem; margin-top: 4px; line-height: 1.4; }
  .sg-cs-num { font-size: 1.75rem; }
  .sg-cs-side { flex-direction: row; flex-wrap: wrap; align-items: center; gap: 4px 12px; font-size: 0.8125rem; }
  .sg-cs-line { font-size: 0.8125rem; }
}
/* news cards */
.sg-news { list-style: none; padding: 0; margin: 0 0 6px; }
.sg-news li { margin: 0 0 2px; }
.sg-news li > a, .sg-news li > span { display: flex; gap: 10px; align-items: flex-start; padding: 7px 6px;
  border-radius: 8px; color: inherit !important; text-decoration: none !important; }
.sg-news li > a:hover { background: var(--sg-panel); }
.sg-news-text { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.sg-news-title { color: var(--sg-text); font-size: 0.875rem; line-height: 1.38; display: -webkit-box; -webkit-line-clamp: 3;
  -webkit-box-orient: vertical; overflow: hidden; }
.sg-news li > a:hover .sg-news-title { color: var(--sg-strong); text-decoration: underline; text-underline-offset: 3px; }
.sg-news-meta { color: var(--sg-faint); font-size: 0.75rem; }
/* reduced motion: transitions become instant; loading spinners keep turning (they are status, not decoration) */
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { transition-duration: 0.01ms !important; } }
"""
# The face comes from Google Fonts: if that is blocked, text falls back to a system mono, not Streamlit's sans.
# Streamlit marks every Material icon (and nothing else) translate="no"; those keep their icon font.
GLOBAL_CSS += 'body, body :not([translate="no"]) { font-family: ' + config.MONO_FONT + "; }\n"
# Headline numbers (a metric in the first and last column of a row) form one bordered strip split by 1px rules: the
# line colour shows through 1px gaps, so the rules follow the row however it wraps.
_KPI_ROW = ('[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:first-child [data-testid="stMetric"])'
            ':has(> [data-testid="stColumn"]:last-child [data-testid="stMetric"])')
GLOBAL_CSS += f"""
{_KPI_ROW} {{ container: sgkpi / inline-size; flex-wrap: wrap !important; gap: 1px !important;
  background: var(--sg-line); border: 1px solid var(--sg-line); border-radius: 0.5rem; overflow: hidden; }}
{_KPI_ROW} > [data-testid="stColumn"] {{ background: var(--sg-bg); }}
{_KPI_ROW} [data-testid="stMetric"] {{ padding: 0.75rem 1rem; }}
{_KPI_ROW} [data-testid="stMetric"] > div:first-child {{ padding: 0 !important; }}
@media (max-width: 640px) {{ {_KPI_ROW} [data-testid="stMetric"] {{ padding: 0.625rem 0.75rem; }} }}
"""


def _on_dock_search() -> None:
    st.session_state["_jump_to"] = st.session_state.get("dock_search")
    st.session_state["dock_search"] = None


def _readout() -> None:
    """The tracked country: flag, score, tier and change since last year. Tap to open it."""
    try:
        core = data.load_core()
        scores = data.get_scores(core, data.analysis_year(), weights_tuple(), core["version"])
        hist = history(core)
        countries = core["countries"]
        iso3 = current_country(countries, fallback=None)  # nothing tracked until the visitor picks a country
        if iso3 is None:
            return
        row = countries.set_index("iso3").loc[iso3]
    except Exception:  # the dock is a convenience; never let it break a page
        return
    score = scores["composite"].get(iso3) if iso3 in scores.index else None
    tier = scores["tier"].get(iso3) if iso3 in scores.index else None
    color = config.TIER_COLORS.get(tier, config.INK["faint"])
    years = (hist[hist["iso3"] == iso3].set_index("year")["composite"].sort_index().dropna() if not hist.empty
             else pd.Series(dtype=float))
    delta = round(years.iloc[-1] - years.iloc[-2], 1) if len(years) >= 2 else None
    tip = "Open the country profile"
    if score is None or pd.isna(score):
        meta = "not enough data to score"
    else:
        trend = ""
        if delta is not None and not pd.isna(delta):
            label = trend_label(delta)
            meaning = {"▲": "riskier than last year", "▼": "safer than last year",
                       "■": "steady, under 1 point from last year"}[label[0]]
            tip += f". {label[0]} {meaning}"
            trend = (f' · <span aria-hidden="true" title="{label[0]} {meaning}">{label}</span>'
                     f'<span class="sg-sr">{interpret.signed(delta)}, {meaning}</span>')
        meta = f"<b>{score:.0f}</b> · {html.escape(tier)}{trend}"
    flag = config.flag_url(row["iso2"])
    with st.container(key="sg_read", horizontal=True, vertical_alignment="center", wrap=False):
        st.markdown(
            f'<div class="sg-read" style="--sg-c:{color}" title="{tip}">'
            '<span class="sg-tier"></span>'
            + (f'<img src="{flag}" alt="">' if flag else "")
            + f'<div class="sg-read-text"><div class="sg-read-name">{html.escape(str(row["name"]))}</div>'
            f'<div class="sg-read-meta">{meta}</div></div></div>',
            unsafe_allow_html=True,
        )
        with st.container(key="sg_read_link"):
            st.page_link(COUNTRY_PAGE, label=f"Open {row['name']}")


def _follow_jump(pages: dict) -> None:
    """A pick from Find or a followed-country card, made on the previous run: open that country or page now."""
    jump = st.session_state.pop("_jump_to", None)
    if not jump:
        return
    a11y.keep_focus(a11y.TITLE)  # the keyboard lands on the new page's title, not on whatever control is there
    if jump.startswith(PAGE_KEY):
        by_path = {p.url_path: p for section in pages.values() for p in section}
        if jump[len(PAGE_KEY):] in by_path:
            st.switch_page(by_path[jump[len(PAGE_KEY):]])
    else:
        go_to_country(jump)


def _find(pages: dict) -> None:
    """One search for every country and every page; opened with no text, it lists the pages first."""
    titles = {PAGE_KEY + p.url_path: p.title for section in pages.values() for p in section}
    try:
        options, names = country_options(data.load_countries())
    except Exception:  # the country list is a convenience; the pages still work without it
        options, names = [], {}
    st.selectbox("Find a country or page", [*titles, *options], index=None, key="dock_search",
                 on_change=_on_dock_search, placeholder="Type a country or page…",
                 format_func=lambda i: f"{titles[i]} · page" if i in titles else names.get(i, i))
    for iso3 in follow.following():
        if iso3 in names:
            st.button(f"★ {names[iso3]}", key=f"dock_fol_{iso3}", on_click=_jump, args=(iso3,), type="tertiary")


def page_setup(current_url_path: str, pages: dict) -> None:
    """Before the page draws: a pending jump from Find, the styles, the followed list and the accessibility helper."""
    _follow_jump(pages)
    if current_url_path == "introduction":  # read it: the overview stops pointing first-timers there
        st.session_state["_explored"] = True
    st.html(f"<style>{TOKENS_CSS}{GLOBAL_CSS}{DOCK_CSS}</style>")
    follow.sync()
    a11y.page_helper()


def dock(current_url_path: str, pages: dict) -> None:
    """A console bar along the bottom of every page: the tracked country, the main pages and Find. Drawn after the
    page, so keyboard users reach it after the content, as they see it."""
    with st.container(key="sg_dock", horizontal=True, wrap=True):
        with st.container(key="sg_tabs", horizontal=True, wrap=False, gap=None, width="content"):
            for page, label, icon, url_path in DOCK_TABS:
                state = "on" if url_path == current_url_path else "off"
                with st.container(key=f"sg_tab_{state}_{label.lower()}"):
                    st.page_link(page, label=label, icon=icon, width="stretch")
            with st.container(key="sg_tab_off_find"):
                with st.popover("Find", icon=":material/search:", type="tertiary", width="stretch",
                                help="Search countries and pages (press / or Ctrl+K)"):
                    _find(pages)
        if current_url_path != "country":  # the profile's own header already shows the country
            _readout()  # last, so the tabs never wait for it (CSS shows it first)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
@st.fragment(run_every=4)
def _wait_for_live_data(version: str) -> None:
    """While a live download runs, re-run the page as soon as the new data is ready."""
    status = data.live_status()
    if status["version"] and status["version"] != version:
        st.rerun(scope="app")


def _providers(keys: list[str]) -> str:
    """'World Bank, IMF World Economic Outlook' for a list of series keys."""
    names = {config.SOURCE_LABELS.get(config.RAW_SERIES.get(k, ("",))[0], "another source") for k in keys}
    return ", ".join(sorted(names))


def load():
    """Load data and scores for the current weights. Stops the page with a message if impossible."""
    try:
        with st.spinner("Loading the data…"):
            core = data.load_core()
            year = data.analysis_year()
            values = data.get_values(core, year, core["version"])
            scores = data.get_scores(core, year, weights_tuple(), core["version"])
    except Exception as exc:  # show a friendly message instead of a stack trace
        st.error(
            "The data couldn't be loaded: the sources didn't answer and there is no saved copy yet. "
            "Try again in a few minutes."
        )
        with st.expander("Technical details"):
            st.code(f"{type(exc).__name__}: {exc}")
        end_page()
    status = data.live_status()
    if core["source"] == "snapshot":
        if status["running"]:
            st.info(
                f"Showing saved data from {core.get('snapshot_date') or 'the last snapshot'} while the latest "
                "figures download. The page updates by itself in about a minute.",
            )
        elif status["error"]:
            st.warning(
                f"The latest figures couldn't be downloaded, so this is saved data from "
                f"{core.get('snapshot_date') or 'the last snapshot'}. The app retries every 15 minutes."
            )
    else:
        failed = [k for k, m in core["meta"].items() if m["error"] and not m["from_snapshot"]]
        snap = [k for k, m in core["meta"].items() if m["from_snapshot"]]
        if failed:
            st.warning(
                f"{_providers(failed)} didn't respond, so scores use the remaining indicators. Details are under "
                "*Data status and provenance* at the bottom of the page."
            )
        elif snap:
            saved_on = core["meta"][snap[0]].get("snapshot_date") or "the last snapshot"
            st.info(f"{_providers(snap)} didn't respond, so some figures come from the saved copy of {saved_on}. "
                    "The app retries within the hour.", icon=":material/history:")
    if status["running"] or (status["version"] and status["version"] != core["version"]):
        _wait_for_live_data(core["version"])
    if label := custom_weights_label():  # every score on the page depends on them, so say so
        with st.container(horizontal=True, vertical_alignment="center", key="sg_weights_note", gap="small"):
            st.caption(f"Scores use your pillar weights: {label}.")
            st.button("Reset weights", on_click=_reset_weights_from_note, type="tertiary", key="sg_weights_reset")
    return core, year, values, scores


def history(core: dict) -> pd.DataFrame:
    """The index for every year since config.HISTORY_START, with the current weights."""
    return data.get_history(core, weights_tuple(), core["version"])


@st.cache_data(ttl=600, show_spinner=False)
def assessments() -> dict[str, dict]:
    return content.load_assessments()


def master_table(core: dict, values: pd.DataFrame, scores: pd.DataFrame, hist: pd.DataFrame) -> pd.DataFrame:
    """One row per country with names, groups, flags, scores and analyst info (+ change vs last year)."""
    from . import scoring  # local import keeps module import order simple

    countries = core["countries"].set_index("iso3")
    table = countries[["name", "region", "income", "iso2", "lat", "lng"]].join(scores, how="left").join(
        values[["population", "gdppc", "battle_deaths_raw"]], how="left"
    )
    table["flag"] = table["iso2"].map(config.flag_url)
    if not hist.empty:
        last_year = int(hist["year"].max()) - 1
        prev = hist[hist["year"] == last_year].set_index("iso3")
        table["prev_composite"] = prev["composite"].reindex(table.index)
        table["prev_tier"] = prev["tier"].reindex(table.index)
        table["delta_1y"] = (table["composite"] - table["prev_composite"]).round(1)  # the shown 1-dp change picks the arrow
        table["trend"] = table["delta_1y"].map(trend_label)
    table["flags"] = scoring.flag_counts(values, core["series"]).reindex(table.index).fillna(0).astype(int)
    a = assessments()
    table["assessment"] = table.index.map(lambda i: "✓" if i in a else "")
    table["analyst_rating"] = table.index.map(lambda i: a.get(i, {}).get("meta", {}).get("analyst_rating", ""))
    table["rank_label"] = table.apply(
        lambda r: f"{int(r['rank'])} of {int(r['n_ranked'])}" if pd.notna(r.get("rank")) else "not ranked", axis=1
    )
    return table.reset_index()


# ---------------------------------------------------------------------------
# Small components
# ---------------------------------------------------------------------------
TREND_THRESHOLD = 1.0  # score points; smaller year-on-year moves count as steady


def median_delta(median_now, last) -> dict:
    """st.metric delta args for a median score vs last year's row: no "-0.0", and a move under a point stays grey."""
    d = None if last is None or median_now is None else (round(float(median_now - last["median"]), 1) or 0.0)
    return {"delta": d, "delta_color": "inverse" if d is not None and abs(d) >= TREND_THRESHOLD else "off"}


def trend_label(delta) -> str:
    """Arrow + change vs last year. Up = riskier."""
    if delta is None or pd.isna(delta):
        return "—"
    arrow = "▲" if delta >= TREND_THRESHOLD else "▼" if delta <= -TREND_THRESHOLD else "■"
    return f"{arrow} {interpret.signed(delta)}"


def trend_said(delta: float, year: int) -> str:
    """trend_label in words, for a title and screen readers: 'Riskier than in 2025: up 6.2 points'."""
    if delta >= TREND_THRESHOLD:
        return f"Riskier than in {year - 1}: up {delta:.1f} points"
    if delta <= -TREND_THRESHOLD:
        return f"Safer than in {year - 1}: down {-delta:.1f} points"
    return f"Steady since {year - 1}: moved less than {TREND_THRESHOLD:.0f} point"


def flag_img(iso2, height: str = "1em") -> str:
    url = config.flag_url(iso2)
    if not url:
        return ""
    return (f'<img src="{url}" alt="" style="height:{height};aspect-ratio:4/3;border-radius:3px;'
            f'vertical-align:-0.12em;margin-right:0.35em;box-shadow:0 0 0 1px var(--sg-line)">')


# The header box is a Streamlit container, so the analyst's rating inside it can be a real button (an invisible one
# over the line, as on the following cards): plain links would reload the app and lose the visit
_COUNTRY_HEAD_CSS = """
.st-key-country_head { gap: 14px 24px !important; justify-content: space-between; border: 1px solid var(--sg-line);
  border-radius: 14px; padding: 18px 20px; margin: 6px 0 12px; background: var(--sg-raised); }
.st-key-country_head > [data-testid="stElementContainer"]:first-child { flex: 1 1 320px !important; min-width: 0; }
.st-key-country_score { gap: 12px 16px !important; flex: 0 1 auto; }
.st-key-country_side { gap: 5px !important; }
.st-key-country_head [data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }  /* it holds no paragraph */
.st-key-country_analyst { position: relative; }
.st-key-country_analyst_open { position: absolute !important; inset: 0; width: auto !important; margin: 0 !important; }
.st-key-country_analyst_open button { position: absolute !important; inset: 0; width: 100%; height: 100%; min-height: 0;
  opacity: 0; overflow: hidden; }
.st-key-country_analyst:has(button:focus-visible) { outline: 2px solid var(--sg-accent); outline-offset: 3px; border-radius: 4px; }
.st-key-country_analyst:hover .sg-cs-link { color: var(--sg-strong); }
@media (pointer: coarse) { .st-key-country_analyst_open button { inset: -10px -6px; width: auto; height: auto; } }  /* 44px */
@media (max-width: 640px) {
  .st-key-country_head { gap: 8px 16px !important; padding: 10px 12px; margin: 0; }
  /* the score beside its lines, which wrap (Streamlit's layout wrappers are the flex items) */
  [data-testid="stLayoutWrapper"]:has(> .st-key-country_score) { flex: 1 1 100% !important; min-width: 0; }
  .st-key-country_score { flex-wrap: nowrap !important; }
  [data-testid="stLayoutWrapper"]:has(> .st-key-country_side) { flex: 1 1 0 !important; min-width: 0; }
  .st-key-country_side { flex-direction: row !important; flex-wrap: wrap; align-items: center; gap: 4px 12px !important; }
}
"""


def country_header(name: str, row: pd.Series, delta, year: int, meta: str, analyst_rating: str | None = None,
                   on_analyst=None) -> None:
    """The top of a country profile: identity on the left, the score with tier, rank and change on the right.
    on_analyst: a callback for a click on the analyst's rating (the profile opens the assessment)."""
    tier = row.get("tier")
    score = row.get("composite")
    flag = config.flag_url(row.get("iso2"))
    rank = ""
    if pd.notna(row.get("rank")):
        said = f"Rank {int(row['rank'])} of {int(row['n_ranked'])}; 1 is the highest risk"
        rank = (f'<span title="{said}"><span aria-hidden="true">#{int(row["rank"])} of {int(row["n_ranked"])}</span>'
                f'<span class="sg-sr">{said}</span></span>')
    change = ""
    if delta is not None and pd.notna(delta):
        tone = ("var(--sg-worse)" if delta >= TREND_THRESHOLD else "var(--sg-better)" if delta <= -TREND_THRESHOLD
                else "var(--sg-faint)")
        said = trend_said(delta, year)
        change = (f'<span title="{said}"><span aria-hidden="true"><span style="color:{tone}">{trend_label(delta)}</span>'
                  f' vs {year - 1}</span><span class="sg-sr">{said}</span></span>')
    st.html(f"<style>{_COUNTRY_HEAD_CSS}</style>")
    with st.container(key="country_head", horizontal=True, wrap=True, vertical_alignment="center", gap=None):
        st.markdown(
            '<div class="sg-country-id">' + (f'<img src="{flag}" alt="">' if flag else "")
            + f'<div><h1 class="sg-country-name">{html.escape(str(name))}</h1>'
            f'<div class="sg-country-meta">{meta}</div></div></div>',
            unsafe_allow_html=True, width="stretch",
        )
        with st.container(key="country_score", horizontal=True, width="content", vertical_alignment="center", gap=None):
            st.markdown(f'<div class="sg-cs-num">{"—" if pd.isna(score) else f"{score:.0f}"}<span>/100</span></div>',
                        unsafe_allow_html=True, width="content")
            with st.container(key="country_side", width="content", gap=None):
                st.markdown(f'<div class="sg-cs-side">{tier_badge(tier)}<div class="sg-cs-line">{rank}</div>'
                            f'<div class="sg-cs-line">{change}</div></div>', unsafe_allow_html=True, width="content")
                if analyst_rating:
                    with st.container(key="country_analyst", width="content"):
                        st.markdown(f'<div class="sg-cs-line" aria-hidden="true"><span class="sg-cs-link">Analyst</span>: '
                                    f'{tier_badge(analyst_rating)}</div>', unsafe_allow_html=True, width="content")
                        if on_analyst:
                            st.button(f"Analyst: {analyst_rating}. Open the assessment", key="country_analyst_open",
                                      type="tertiary", on_click=on_analyst)


def _jump(iso3: str) -> None:
    st.session_state["_jump_to"] = iso3  # the dock makes the jump at the start of the next run


def following_strip(table: pd.DataFrame) -> None:
    """Cards for the countries this browser follows (★ on a profile). Nothing when there are none."""
    followed = [i for i in follow.following() if i in set(table["iso3"])]
    if not followed:
        return
    rows = table.set_index("iso3")
    st.markdown('<div class="sg-follow-head">★ Following</div>', unsafe_allow_html=True)
    with st.container(horizontal=True, wrap=True, gap="small", key="following_strip"):
        for iso3 in followed:
            r = rows.loc[iso3]
            delta = r.get("delta_1y")
            change = "" if pd.isna(delta) else trend_label(delta)
            flag = config.flag_url(r["iso2"])
            score = "—" if pd.isna(r["composite"]) else f"{r['composite']:.0f}"
            tier = html.escape(r["tier"]) if isinstance(r["tier"], str) else "—"
            with st.container(key=f"fol_{iso3}", width=210):
                st.markdown(
                    '<div class="sg-fol">' + (f'<img src="{flag}" alt="">' if flag else "")
                    + f'<div><div class="sg-fol-name">{html.escape(str(r["name"]))}</div>'
                    f'<div class="sg-fol-meta"><b>{score}</b> · {tier} {change}</div></div></div>',
                    unsafe_allow_html=True,
                )
                st.button(f"Open {r['name']}", key=f"fol_open_{iso3}", on_click=_jump, args=(iso3,))


def sev_mark(severity: str, spoken: bool = True) -> str:
    """The coloured severity dot as HTML, silent for screen readers; with spoken=True they hear the word instead
    ("Serious:"). Use spoken=False where the severity word is already in the sentence."""
    word = f'<span class="sg-sr">{config.SEVERITY_LABEL[severity]}: </span>' if spoken else ""
    return f'<span class="sg-sev" style="--c:{config.SEVERITY_COLOR[severity]}" aria-hidden="true"></span>{word}'


def country_heading(name: str, iso2, level: int = 1, css: str = "") -> None:
    """A heading with the country's flag in front (css: an extra class, e.g. sg-panel-title for a small panel title)."""
    cls = f' class="{css}"' if css else ""
    st.markdown(f"<h{level}{cls}>{flag_img(iso2, '0.85em')}{html.escape(str(name))}</h{level}>", unsafe_allow_html=True)


def _time_ago(ts) -> str:
    if ts is None or pd.isna(ts):
        return ""
    minutes = int((pd.Timestamp.now(tz="UTC") - ts).total_seconds() // 60)
    if minutes < 60:
        return f"{max(minutes, 1)} min ago"
    if minutes < 60 * 24:
        return f"{minutes // 60} h ago"
    return f"{minutes // (60 * 24)} d ago"


THUMB = "width:78px;height:52px;flex:none;border-radius:6px;object-fit:cover;background:var(--sg-hover)"


def news_list(query_name: str | None, limit: int = 10) -> None:
    """Latest risk-related headlines with photos where the feed has one.

    Bing News + Google News, GDELT as backup; cached for 10 minutes.
    """
    with guard("The news"):
        _news_list(query_name, limit)


def _news_list(query_name: str | None, limit: int) -> None:
    news = data.load_news(query_name)
    articles = news["articles"]
    if news["error"]:
        st.info("Headlines are unavailable: every news source refused the request. The app retries automatically.")
        return
    if articles is None or articles.empty:
        st.info("No matching headlines in the last 7 days.")
        return
    items = []
    for row in articles.head(limit).itertuples(index=False):
        url = str(row.url or "")
        title = html.escape(str(row.title or ""))
        domain = html.escape(str(row.domain or ""))
        # <bdi>: a right-to-left source name can't pull "1 d ago" into its own direction
        meta = " · ".join(x for x in (domain and f"<bdi>{domain}</bdi>", _time_ago(row.seen).replace(" ", "\u00a0")) if x)
        image = row.image if isinstance(row.image, str) and row.image.startswith("https://") else None
        # no picture: no placeholder either (a flag repeated down the list), the headline takes the room
        thumb = (f'<img class="sg-news-thumb" src="{html.escape(image)}" alt="" loading="lazy" style="{THUMB}">'
                 if image else "")
        body = (f'{thumb}<span class="sg-news-text"><span class="sg-news-title">{title}</span>'
                f'<span class="sg-news-meta">{meta}</span></span>')
        items.append(f'<li><a href="{html.escape(url)}" target="_blank" rel="noopener">{body}</a></li>'
                     if url.startswith("http") else f"<li><span>{body}</span></li>")
    st.markdown(f'<ul class="sg-news">{"".join(items)}</ul>', unsafe_allow_html=True)
    st.caption(f"{news['source']} · fetched {news['fetched']} · refreshes every 10 minutes. "
               "Collected automatically and unchecked: verify before citing.")


_PILL = "padding:2px 11px;border-radius:999px;font-weight:600;font-size:0.875rem;white-space:nowrap;"


def tier_badge(tier: str | None, prefix: str = "") -> str:
    """The tier as a pill whose weight rises with the risk: Low and Moderate outlined, Elevated and up filled, and
    Severe filled with an ink ring (its pale fill alone reads weaker than Elevated's)."""
    if not isinstance(tier, str) or tier not in config.TIER_ORDER:
        return '<span style="color:var(--sg-faint)">Not rated</span>'
    t = next(t for t in TIERS if t.label == tier)
    rank = config.TIER_ORDER.index(tier)
    look = f"background:{t.color};color:{t.text_on};" if rank >= 2 else "background:transparent;color:var(--sg-text);"
    if rank == len(TIERS) - 1:
        look += "font-weight:700;box-shadow:0 0 0 2px var(--sg-bg),0 0 0 3.5px var(--sg-text);"
    return f'<span style="{_PILL}border:1px solid {t.color};{look}">{prefix}{tier}</span>'


def tier_legend() -> str:
    """The five tiers with their lower bounds, then the grey the maps give a country without enough data."""
    parts = [tier_badge(t.label) + f'<span style="color:var(--sg-faint);font-size:0.75rem;margin:0 14px 0 8px">'
             f'{int(t.lower)}+</span>' for t in TIERS]
    parts.append(f'<span style="{_PILL}font-weight:400;border:1px solid {config.NO_DATA_COLOR};'
                 f'background:{config.NO_DATA_COLOR};color:var(--sg-soft)">No data</span>')
    return '<div style="line-height:2.4">' + "".join(parts) + "</div>"


def country_options(countries: pd.DataFrame) -> tuple[list[str], dict[str, str]]:
    names = dict(zip(countries["iso3"], countries["name"]))
    order = sorted(names, key=lambda i: names[i])
    return order, names


def current_country(countries: pd.DataFrame, fallback: str | None = "NGA") -> str | None:
    """The country opened last in this visit; on a fresh visit, the first one this browser follows. With
    fallback=None, None until the visitor has picked, opened or followed one."""
    valid = set(countries["iso3"])
    followed = follow.following()
    for candidate in (st.session_state.get("country"), st.query_params.get("country"),
                      followed[0] if followed else None, fallback):
        if candidate and str(candidate).upper() in valid:
            return str(candidate).upper()
    return countries["iso3"].iloc[0] if fallback else None


def go_to_country(iso3: str) -> None:
    st.session_state["country"] = iso3
    st.switch_page(COUNTRY_PAGE)


def clicked_iso3(event) -> str | None:
    """ISO3 code of a clicked chart point. Clickable charts put it last in customdata."""
    points = getattr(getattr(event, "selection", None), "points", None) or []
    for point in points:
        custom = point.get("customdata")
        if isinstance(custom, (list, tuple)) and custom:
            return str(custom[-1])
    return None


def add_to_compare(iso3: str) -> None:
    picked = st.session_state.setdefault(COMPARE_LIST, [])
    if iso3 not in picked and len(picked) < config.MAX_COMPARE:
        picked.append(iso3)
    # Drop the Compare page's widget value so it re-reads the list next time it opens
    st.session_state.pop("compare_picked", None)


def url_tabs(tabs: dict[str, str], key: str) -> list:
    """Lazy tabs ({slug: label}; build a tab's content only `if tab.open:`) that keep the open one in the address as
    ?tab=<slug>, so Back, reload and a bookmark reopen it. Returns the tabs in dict order.

    A ?tab the row has not applied or written yet opens its tab (a link, or Back and Forward); after the tabs are
    drawn the open tab's slug goes back into the address. The first tab needs no ?tab, so a plain link stays clean."""
    slugs = list(tabs)
    mark = f"{key}__url"  # the slug this row last applied or wrote; starts with the key, so _reload clears it too
    asked = st.query_params.get("tab")
    if asked is None and st.session_state.get(mark):
        asked = slugs[0]  # Back to the address without ?tab: the first tab again
    if asked in tabs and (asked != st.session_state.get(mark) or key not in st.session_state):
        st.session_state[key] = tabs[asked]
    elif st.session_state.get(key) in tabs.values():
        # the widget id comes from the labels, so a row in a new order (the profile's Assessment) is a new widget
        # that would open on its first tab: set the open label again so it carries over
        st.session_state[key] = st.session_state[key]
    drawn = list(st.tabs(list(tabs.values()), key=key, on_change="rerun"))
    shown = next((slug for slug, tab in zip(slugs, drawn) if tab.open), slugs[0])
    st.session_state[mark] = shown
    if st.query_params.get("tab", slugs[0]) != shown:
        st.query_params["tab"] = shown
    return drawn


def url_view(label: str, views: dict[str, str], key: str) -> str:
    """A segmented control of views ({slug: label}) inside a url_tabs tab, kept in the address as ?view=<slug> the
    way url_tabs keeps ?tab. The page drops ?view while its tab is closed; the choice comes back with the tab.
    Returns the open view's label."""
    mark = f"{key}__url"  # the slug last applied or shown; it outlives the control, which goes when its tab closes
    asked = st.query_params.get("view")
    if asked in views and (asked != st.session_state.get(mark) or key not in st.session_state):
        st.session_state[key] = views[asked]
    elif st.session_state.get(key) not in views.values():
        st.session_state[key] = views.get(st.session_state.get(mark), next(iter(views.values())))
    shown = st.segmented_control(label, list(views.values()), key=key, required=True, label_visibility="collapsed")
    st.session_state[mark] = slug = next(slug for slug, text in views.items() if text == shown)
    if st.query_params.get("view") != slug:
        st.query_params["view"] = slug
    return shown


def hero(title: str, subtitle: str = "") -> None:
    """The page title (the screen's one h1) and an optional line about the data under it."""
    st.markdown(
        f'<div class="sg-head"><h1 class="sg-head-title">{html.escape(title)}</h1>'
        + (f'<p class="sg-head-sub">{html.escape(subtitle)}</p>' if subtitle else "") + "</div>",
        unsafe_allow_html=True,
    )


def pillar_chip(pillar_key: str, text: str | None = None) -> str:
    """A small label in the pillar's colour, used to tie headings to the pillar charts and maps."""
    color = config.PILLAR_COLORS[pillar_key]
    label = text or config.PILLAR_BY_KEY[pillar_key].label
    return (
        f'<span style="display:inline-block;border-left:6px solid {color};background:{color}1f;'
        f'padding:2px 10px;border-radius:4px;font-weight:600">{label}</span>'
    )


def fmt_population(p) -> str:
    if p is None or pd.isna(p):
        return "—"
    if p >= 1e9:
        return f"{p / 1e9:.2f} bn"
    if p >= 1e6:
        return f"{p / 1e6:.1f} m"
    return f"{p / 1e3:.0f} k"


FLAG_COLUMN = st.column_config.ImageColumn(" ", width=50)  # narrow and not pinned: on a phone the figures get the room
# at most 200px: the grid unpins every column once pinned ones take over 60% of its width (phones)
NAME_COLUMN = st.column_config.TextColumn("Country", pinned=True, width="medium")
SOURCES_PAGE = "app_pages/sources.py"


def source_label(key: str) -> str:
    """The short name of a source, for inline citations."""
    return config.CITE_LABELS.get(key, config.SOURCES[key].name)


def source_link(key: str, label: str | None = None) -> str:
    """An HTML link to a source that opens in a new tab."""
    s = config.SOURCES[key]
    return (f'<a href="{html.escape(s.url)}" target="_blank" rel="noopener">'
            f'{html.escape(label or source_label(key))} ↗</a>')


def cite(*keys: str, note: str | None = None) -> None:
    """A linked "Sources:" line under a number, chart or table. Keys are config.SOURCES keys;
    "index" stands for the five datasets the risk index is built from."""
    expanded = [k for key in keys for k in (config.INDEX_SOURCES if key == "index" else [key])]
    links = [f"[{source_label(k)}]({config.SOURCES[k].url})" for k in dict.fromkeys(expanded)]
    glue = chr(0xA0) + "·" + chr(0xA0)  # the last two share a line (no-break spaces), so none sits alone on the last
    st.caption("Sources: " + " · ".join(links[:-2] + [glue.join(links[-2:])]) + (f". {note}" if note else ""))


@st.fragment
def globe_panel(**kwargs) -> None:
    """A 3D globe in its own fragment, so clicking countries re-runs only the globe, not the whole page.

    Takes the arguments of globe.risk_globe; "Open full profile" goes to the country.
    """
    open_iso3 = None
    with guard("The 3D globe"):
        open_iso3, _ = globe.risk_globe(**kwargs)
    if open_iso3:
        go_to_country(open_iso3)


def open_selected(event, frame: pd.DataFrame, key: str) -> None:
    """A ticked row offers its country instead of leaving the page at once: the tick selects, the button opens."""
    if not (event and event.selection.rows) or event.selection.rows[0] >= len(frame):
        return  # a keyed table keeps its tick when a filter shrinks it
    row = frame.iloc[event.selection.rows[0]]
    name = str(row.get("name") or row["iso3"]).removeprefix("▶ ")
    if st.button(f"Open {name}", key=f"{key}_open", icon=":material/arrow_forward:"):
        go_to_country(row["iso3"])


# A progress column takes one colour for every row, so score bars are neutral ink and the Tier cell carries the tier
BAR_COLOR = config.INK["soft"]
_TIER_FILL = {t.label: f"background-color: {t.color}; color: {t.text_on}"
              + ("; font-weight: 700" if t is TIERS[-1] else "")
              for t in TIERS[config.TIER_ORDER.index("Elevated"):]}


def tier_cells(frame: pd.DataFrame):
    """As on the tier badges: Elevated and up filled in the tier colour (Severe in bold), Low and Moderate plain."""
    return frame.style.map(lambda v: _TIER_FILL.get(v, ""), subset=["tier"])


def thin_data(df: pd.DataFrame) -> pd.Series:
    """Rows whose score rests on thin data: under 75% of the indicators (the profile header's threshold) or a whole
    pillar missing (small islands such as Tuvalu have 76% but no social pillar)."""
    return (df["coverage"] < 75) | df[[p.key for p in PILLARS]].isna().any(axis=1)


def movers_lists(df: pd.DataFrame, n: int = 5, key: str = "movers") -> None:
    """Two lists: the biggest rises and falls in the composite since last year (tick a row to open it). Names on thin
    data say so in the table; the button under it keeps the plain name."""
    valid = df.dropna(subset=["delta_1y"])
    risers = valid[valid["delta_1y"] >= TREND_THRESHOLD].nlargest(n, "delta_1y").reset_index(drop=True)
    fallers = valid[valid["delta_1y"] <= -TREND_THRESHOLD].nsmallest(n, "delta_1y").reset_index(drop=True)
    # stacked: side by side, half-width tables cut names and tiers
    for title, frame, part in (("▲ Biggest risers (riskier)", risers, "up"), ("▼ Biggest fallers (safer)", fallers, "down")):
        st.markdown(f"**{title}**")
        if frame.empty:
            st.caption("No country moved by a point or more.")
            continue
        frame = frame.assign(tier_text=[f"{a} → {b}" if isinstance(a, str) and a != b else b
                                        for a, b in zip(frame["prev_tier"], frame["tier"])])
        shown = frame.assign(name=frame["name"].mask(thin_data(frame), frame["name"] + " (limited data)"))
        event = st.dataframe(
            shown[["iso3", "name", "composite", "trend", "flag", "tier_text"]].round(), hide_index=True,
            on_select="rerun", selection_mode="single-row", key=f"{key}_{part}",
            column_config={
                "iso3": None, "flag": FLAG_COLUMN, "name": NAME_COLUMN,
                "composite": st.column_config.NumberColumn("Score", format="%.0f"),
                "trend": st.column_config.TextColumn("Change", alignment="right"), "tier_text": "Tier",
            },
        )
        open_selected(event, frame, f"{key}_{part}")


def country_table(df: pd.DataFrame, key: str, height: int | str | None = None, extra: dict | None = None,
                  sort: str = "rank", ascending: bool = True) -> None:
    """A ranking table (flag, score, change, tier, pillars); a ticked row offers its profile."""
    # The name is pinned and the figures follow it (extra ones such as a group rank first), then the flag, so a
    # phone's first view shows the name and the figures
    cols = ["iso3", "name", *(extra or {}), "composite", "trend", "flag", "tier", "rank", *[p.key for p in PILLARS]]
    frame = df.sort_values(sort, ascending=ascending, na_position="last")[[c for c in cols if c in df.columns]]
    frame = frame.reset_index(drop=True)
    event = st.dataframe(  # every number here shows whole, so screen readers get them rounded too
        tier_cells(frame.round()), hide_index=True, on_select="rerun", selection_mode="single-row", key=key, height=height,
        placeholder="—", column_config={
            "iso3": None, "flag": FLAG_COLUMN, "name": NAME_COLUMN,
            # fixed widths: auto-sizing fits the figures, which cuts these headers and the filled tier cells
            "rank": st.column_config.NumberColumn("Global rank", format="%d", width=110,
                                                  help="1 = the highest risk of all the countries scored"),
            "composite": st.column_config.ProgressColumn("Composite", min_value=0, max_value=100, format="%.0f",
                                                         width=100, color=BAR_COLOR),  # "small" cuts the header
            "trend": st.column_config.TextColumn("1-yr change", alignment="right", width=110,
                                                 help="Composite score vs last year. ▲ = riskier, ▼ = safer, "
                                                      "■ = under 1 point"),
            "tier": st.column_config.TextColumn("Tier", width=100),
            **{p.key: st.column_config.ProgressColumn(p.short, min_value=0, max_value=100, format="%.0f",
                                                      color=config.PILLAR_COLORS[p.key]) for p in PILLARS},
            **(extra or {}),
        },
    )
    open_selected(event, frame, key)


def upcoming_events(events: pd.DataFrame, limit: int = 8) -> None:
    """Upcoming events from the event calendar, with a countdown."""
    today = pd.Timestamp.today().normalize()
    upcoming = events[events["date"] >= today].sort_values("date").head(limit)
    if upcoming.empty:
        st.caption("No upcoming events on the calendar.")
        return
    rows = []
    for e in upcoming.itertuples(index=False):
        when = interpret.countdown((e.date - today).days)
        # significance in ink, not a tier colour: high stands out in the brightest ink
        colour = "var(--sg-strong)" if str(e.significance).title() == "High" else "var(--sg-faint)"
        source = (f' · <a href="{html.escape(e.source_url)}" target="_blank" rel="noopener">source</a>'
                  if str(e.source_url).startswith("http") else "")
        rows.append(
            f'<li style="margin:0 0 0.6em 0;line-height:1.35"><b>{html.escape(str(e.event))}</b><br>'
            f'<span style="color:var(--sg-faint);font-size:0.75rem">{html.escape(str(e.country))} · {e.date:%d %b %Y} · '
            f'<span style="color:{colour}">{when} · {html.escape(str(e.significance))} significance</span>{source}</span></li>'
        )
    st.markdown(f'<ul style="list-style:none;padding:0;margin:0;font-size:0.875rem">{"".join(rows)}</ul>',
                unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Video: live channels and the report / analysis gallery
# ---------------------------------------------------------------------------
def live_player(channel_id: str, height: int = 460) -> None:
    """A channel's current 24/7 live stream, through YouTube's official embed (privacy-enhanced domain)."""
    components.html(
        f'<iframe src="https://www.youtube-nocookie.com/embed/live_stream?channel={channel_id}&rel=0" '
        'style="width:100%;height:100%;border:0;border-radius:12px;background:var(--sg-bg)" '
        'allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen '
        'referrerpolicy="strict-origin-when-cross-origin" title="Live news"></iframe>'
        '<style>html,body{margin:0;height:100%;background:transparent}</style>',
        height=height,
    )


def videos_about(videos: pd.DataFrame, iso3: str, names: dict[str, str], official: str | None = None) -> pd.DataFrame:
    """Videos whose title or description mentions a country (its name, news name, official name or aliases)."""
    name = names.get(iso3, iso3)
    terms = {name, config.NEWS_NAMES.get(iso3, name)} | ({official} if official else set())
    loose = [t for t in terms | set(config.VIDEO_ALIASES.get(iso3, [])) if not t.isupper()]
    exact = [t for t in config.VIDEO_ALIASES.get(iso3, []) if t.isupper()]
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, sorted(loose, key=len, reverse=True))) + r")\b", re.I)
    pattern_exact = re.compile(r"\b(" + "|".join(map(re.escape, exact)) + r")\b") if exact else None
    # Longer country names that contain this one ("South Sudan" for Sudan) are removed before matching
    longer = [n for n in names.values() if n != name and name.lower() in n.lower()]
    strip = re.compile("|".join(map(re.escape, sorted(longer, key=len, reverse=True))), re.I) if longer else None

    def mentions(text: str) -> bool:
        text = strip.sub(" ", text) if strip else text
        return bool(pattern.search(text) or (pattern_exact and pattern_exact.search(text)))

    hits = (videos["title"].fillna("") + " \n " + videos["description"].fillna("")).map(mentions)
    return videos[hits]


@st.fragment
def video_gallery(videos: pd.DataFrame, key: str, limit: int = 9, columns: int = 3) -> None:
    """Thumbnails of videos; "▶ Play" shows the video in a player above the grid (only this section re-runs)."""
    with guard("The videos"):
        _video_gallery(videos, key, limit, columns)


def _video_gallery(videos: pd.DataFrame, key: str, limit: int, columns: int) -> None:
    shown = videos.head(limit).reset_index(drop=True)
    playing = st.session_state.get(f"{key}_playing")
    if playing in set(shown["video_id"]):
        current = shown[shown["video_id"] == playing].iloc[0]
        st.video(f"https://www.youtube.com/watch?v={playing}")
        st.caption(money(f"**{current['title']}** · {current['channel']} · {_time_ago(current['published'])}"))
    cols = st.columns(columns)
    for i, v in shown.iterrows():
        with cols[i % columns], st.container(border=True, key=f"vidcard_{key}_{i}"):
            st.image(v["thumbnail"], width="stretch")
            url = f"https://www.youtube.com/watch?v={v['video_id']}"
            st.markdown(money(f"**[{v['title'].replace('[', '(').replace(']', ')')}]({url})**"))
            views = f" · {v['views'] / 1000:,.0f}k views" if pd.notna(v.get("views")) and v["views"] >= 1000 else ""
            st.caption(f"{v['channel']} · {_time_ago(v['published'])}{views}")
            if st.button("Play here", key=f"{key}_{v['video_id']}", width="stretch", icon=":material/play_arrow:"):
                st.session_state[f"{key}_playing"] = v["video_id"]
                st.rerun(scope="fragment")


def render_reading(r: interpret.Reading, key: str) -> None:
    """A country's numbers translated into real life: on the ground, warning signs, direction, what to do."""
    st.markdown(f"{tier_badge(r.tier)} &nbsp; {html.escape(r.headline)}", unsafe_allow_html=True)
    if r.tier is None:
        st.info(r.ground)
        return
    left, right = st.columns([1.15, 1], gap="large")
    with left:
        st.markdown("#### What it looks like on the ground")
        st.markdown(r.ground)
        for d in r.drivers:
            with st.container(border=True):
                st.markdown(pillar_chip(d["pillar"], f"{d['label']} · {d['score']:.0f}/100"), unsafe_allow_html=True)
                st.markdown(d["ground"])
                if d["evidence"]:
                    st.caption("Driven by " + "; ".join(d["evidence"]) + ".")
                st.caption(f"Felt first by: {d['felt_by']}")
    with right:
        st.markdown("#### Warning signs right now")
        if r.warnings:
            for w in r.warnings:
                st.markdown(f"{sev_mark(w['severity'])}**{html.escape(w['label'])}**  \n{html.escape(w['meaning'])}",
                            unsafe_allow_html=True)
                st.caption(f"Typical response: {w['response']}")
        else:
            st.markdown("No absolute warning thresholds crossed.")
        if r.near:
            st.markdown("#### Close to a red line")
            st.markdown("\n".join(f"- {n}" for n in r.near))
        if r.direction:
            st.markdown("#### Direction")
            st.markdown("\n".join(f"- {d}" for d in r.direction))
        st.markdown("#### Coming up")
        if r.events:
            st.markdown(money("\n".join(f"- {e}" for e in r.events)))  # event names are hand-written
        else:
            st.caption("No events on the calendar for the next 12 months.")

    st.markdown("#### What to do with it")
    tabs = st.tabs(list(interpret.AUDIENCES.values()))
    for tab, audience in zip(tabs, interpret.AUDIENCES):
        with tab:
            st.markdown(money("\n".join(f"- {a}" for a in r.actions.get(audience, []))))
    st.download_button("Download reading (Markdown)", interpret.reading_markdown(r).encode("utf-8"),
                       file_name=f"{r.iso3}_real_life_reading.md", mime="text/markdown", key=f"{key}_download")
    st.caption(" ".join(r.caveats))


def data_status(core: dict) -> None:
    with st.expander("Data status and provenance"):
        rows = []
        for key, m in core["meta"].items():
            if m["error"] and not m["from_snapshot"]:
                status = "Unavailable"
            elif m["from_snapshot"]:
                status = f"Snapshot ({m.get('snapshot_date') or 'saved copy'})"
            else:
                status = "Live"
            rows.append({
                "Series": key,
                "Provider": config.SOURCE_LABELS.get(m["provider"], m["provider"]),
                "Code": m["code"],
                "Source updated": m.get("edition") or m.get("last_updated") or "—",
                "Rows": m.get("rows", 0),
                "Status": status,
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        st.caption(f"Data loaded {core['loaded_at']}; cached for 12 hours.")
        errors = {k: m["error"] for k, m in core["meta"].items() if m["error"]}
        if errors:
            st.caption("Errors: " + " · ".join(f"**{k}**: {v[:160]}" for k, v in errors.items()))


def footer(full: bool = False) -> None:
    """The full footer on the Introduction and Sources pages; one line everywhere else."""
    st.divider()
    if not full:
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            st.caption("Educational project. Scores are relative and model-based and do not forecast specific events. "
                       "Not investment or security advice.", width="content")
            st.page_link(SOURCES_PAGE, label="Sources", icon=":material/verified:")
        return
    st.caption(
        f"{config.APP_TITLE}: {config.APP_DESCRIPTION} Data: World Bank Worldwide Governance Indicators & World "
        "Development Indicators · IMF World Economic Outlook · UNHCR · UCDP (via World Bank) · Bing News, Google News "
        "and GDELT. Scores are relative and model-based, and they do not forecast specific events. "
        f"Built by {config.AUTHOR}."
    )
    st.page_link(SOURCES_PAGE, label="All sources, with links and update dates", icon=":material/verified:")
