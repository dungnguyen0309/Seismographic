"""Shared Streamlit UI pieces: sidebar, loading, badges, tables, footer."""

from __future__ import annotations

import contextlib
import html
import logging
import os
import re

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
    for key in [k for k in st.session_state if str(k).startswith(("country_tab", "conflict_tab", "ov_tab"))]:
        del st.session_state[key]


def page_error_boundary(run) -> None:
    """Runs a page; if it fails, a friendly message with a way out instead of a stack trace."""
    try:
        run()
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


# ---------------------------------------------------------------------------
# Sidebar and weights
# ---------------------------------------------------------------------------
def _init_weights() -> None:
    for p in PILLARS:
        st.session_state.setdefault(WEIGHT_KEYS[p.key], p.default_weight)


def _reset_weights() -> None:
    for p in PILLARS:
        st.session_state[WEIGHT_KEYS[p.key]] = p.default_weight


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
    w = weights()
    if all(w[p.key] == p.default_weight for p in PILLARS) or sum(w.values()) <= 0:
        return ""
    total = sum(w.values())
    return " · ".join(f"{p.short} {w[p.key] / total:.0%}" for p in PILLARS)


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
                "Weights are rescaled to 100%, so only their proportions matter."
            )
            for p in PILLARS:
                st.slider(p.label, min_value=0, max_value=100, step=5, key=WEIGHT_KEYS[p.key], help=p.question)
            w = weights()
            total = sum(w.values()) or 1
            st.caption(" · ".join(f"{p.short} {w[p.key] / total:.0%}" for p in PILLARS))
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
    w = weights()
    if sum(w.values()) <= 0:
        w = {p.key: float(p.default_weight) for p in PILLARS}
    return tuple((p.key, w[p.key]) for p in PILLARS)


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
DOCK_CSS = f"""
[data-testid="stMainBlockContainer"] {{ padding-bottom: 8.5rem !important; }}
.st-key-sg_dock {{
  position: fixed !important; z-index: 1000; left: 0; right: 0; bottom: 0; width: auto !important;
  container-type: inline-size; container-name: sgdock;
  background: var(--sg-bar); border-top: 1px solid var(--sg-line);
  padding: 7px max(12px, calc((100% - 980px) / 2)) calc(7px + env(safe-area-inset-bottom)) !important;
  gap: 8px 14px !important; align-items: center !important; justify-content: space-between !important;
  transition: left .25s ease;
}}
@media (min-width: 768px) {{
  body:has(section[data-testid="stSidebar"][aria-expanded="true"]) .st-key-sg_dock {{ left: 300px; }}
}}
/* never fade or flash while the page re-runs */
.st-key-sg_dock [data-stale], [data-stale]:has(> .st-key-sg_dock) {{ opacity: 1 !important; transition: none !important; }}
.st-key-sg_dock a:focus, .st-key-sg_dock button:focus {{ outline: none !important; box-shadow: none !important; }}
.st-key-sg_dock a:focus-visible, .st-key-sg_dock button:focus-visible {{ outline: 1px solid {ACCENT} !important;
  outline-offset: -2px; }}

/* readout: the tracked country (shown first, rendered last so the tabs never wait for it) */
{_wrap("sg_read")} {{ order: -1; flex: 1 1 260px !important; max-width: 440px; min-width: 0; }}
.st-key-sg_read {{ position: relative; background: var(--sg-panel); border: 1px solid var(--sg-line); border-radius: 8px;
  padding: 6px 10px 6px 8px !important; overflow: visible !important; min-height: 46px; }}
.st-key-sg_read:hover {{ background: var(--sg-hover); }}
.st-key-sg_read:has(.sg-read.on) {{ border-color: color-mix(in srgb, {ACCENT} 55%, transparent); }}
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
.sg-read-name {{ font-weight: 700; font-size: 0.86rem; color: var(--sg-strong); white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; }}
.sg-read-meta {{ font-size: 0.75rem; color: var(--sg-muted); white-space: nowrap; }}
.sg-read-meta b {{ color: var(--sg-c); font-size: 0.8rem; }}
.sg-spark {{ flex: none; width: 92px; height: 26px; }}

/* tabs */
{_wrap("sg_tabs")} {{ flex: 0 0 auto !important; }}
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
.st-key-sg_tabs a p, .st-key-sg_tabs button p {{ font-size: 0.72rem !important;
  margin: 0 !important; white-space: nowrap; line-height: 1.2 !important; }}
.st-key-sg_tabs a span, .st-key-sg_tabs a p, .st-key-sg_tabs button p, .st-key-sg_tabs button span {{ color: var(--sg-faint) !important; }}
.st-key-sg_tabs [data-testid="stIconMaterial"] {{ font-size: 1.3rem !important; }}
.st-key-sg_tabs button [aria-hidden="true"], .st-key-sg_tabs button [data-testid="stIconMaterial"],
.st-key-sg_tabs button span:has(> [data-testid="stIconMaterial"]) {{ display: none !important; }}
.st-key-sg_tabs button::before {{ content: ""; width: 1.3rem; height: 1.3rem; flex: none; background: var(--sg-faint);
  -webkit-mask: url("{_SEARCH_ICON}") center / contain no-repeat; mask: url("{_SEARCH_ICON}") center / contain no-repeat; }}
.st-key-sg_tabs button[aria-expanded="true"]::before {{ background: {ACCENT}; }}
.st-key-sg_tabs button {{ padding-top: 4px !important; }}  /* drawn icon is a touch shorter than the font icons */
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

/* narrow screens: the readout on top, the tabs spread across a row underneath */
@container sgdock (max-width: 640px) {{
  {_wrap("sg_read")} {{ flex: 1 1 100% !important; max-width: none; }}
  {_wrap("sg_tabs")} {{ flex: 1 1 100% !important; }}
  .st-key-sg_tabs > [data-testid="stLayoutWrapper"] {{ flex: 1 1 0 !important; }}
  .st-key-sg_tabs a, .st-key-sg_tabs button {{ height: 50px; }}
}}
@container sgdock (max-width: 300px) {{ .sg-spark {{ display: none; }} }}
"""


# Colour tokens (config.INK) as CSS variables, so styles name a role (--sg-muted), not a hex value
TOKENS_CSS = ":root { " + " ".join(f"--sg-{name}: {value};" for name, value in config.INK.items()) + " }"
GLOBAL_CSS = """
/* page frame: less dead space above the content, but clear of the 3.75rem top bar */
[data-testid="stMainBlockContainer"] { padding-top: 4.6rem !important; }
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] { padding-top: 4.4rem !important; padding-left: 0.9rem !important;
                                         padding-right: 0.9rem !important; }
}
/* video cards: titles read like the news cards (no link underline, at most three lines) */
[class*="st-key-vidcard_"] [data-testid="stMarkdownContainer"] a { color: var(--sg-text) !important; text-decoration: none;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
[class*="st-key-vidcard_"] [data-testid="stMarkdownContainer"] a:hover { color: var(--sg-strong) !important; text-decoration: underline; }
/* Rows reflow by their own width, not the window's (the sidebar takes 300px of a laptop screen):
   - headline numbers (a metric in the first and last column): 3 per line, 2 for a row of four, then 2 on phones
   - filter rows (a selectbox, multiselect or slider first, no charts or tables): 2 per line when narrow
   - split views (containers keyed split_*): the two sides stack when narrow */
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:first-child [data-testid="stMetric"]):has(> [data-testid="stColumn"]:last-child [data-testid="stMetric"]) {
  container: sgkpi / inline-size; flex-wrap: wrap !important; }
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
  .st-key-ov_news .sg-news a > :first-child { display: none; }
}
@container sgsplit (max-width: 900px) {  /* What-if: its result needs more width than the news column does */
  .st-key-split_whatif [data-testid="stHorizontalBlock"]:not([data-testid="stColumn"] *) > [data-testid="stColumn"] {
    min-width: 100% !important; flex: 1 1 100% !important; }
  /* stacked, the result comes first, right under the scenario buttons that change it */
  .st-key-split_whatif [data-testid="stHorizontalBlock"]:not([data-testid="stColumn"] *) > [data-testid="stColumn"]:last-child {
    order: -1; }
}
@container sgsplit (max-width: 780px) {
  [data-testid="stHorizontalBlock"]:not([data-testid="stColumn"] *) > [data-testid="stColumn"] {
    min-width: 100% !important; flex: 1 1 100% !important; }
  /* under the globe, the news needs less height (its wrapper fixes the height as a flex-basis) */
  [data-testid="stLayoutWrapper"]:has(> .st-key-ov_news) { flex: 0 0 440px !important; height: 440px !important; }
}
@media (max-width: 640px) {
  [data-testid="stMetric"] { padding: 10px 12px !important; }
  [data-testid="stMetricValue"] { font-size: 1.55rem !important; }
}
/* tabs: a little tighter, and they wrap onto a second line instead of hiding behind a sideways scroll */
[data-testid="stTabs"] [role="tablist"] { gap: 2px 12px; flex-wrap: wrap; overflow-x: visible !important; }
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
/* metrics: labels wrap between words instead of being cut off or split mid-word */
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * { white-space: normal !important; overflow: visible !important;
  text-overflow: clip !important; word-break: normal !important; overflow-wrap: normal !important; hyphens: none; }
[data-testid="stMetricLabel"] p { font-size: 0.8rem !important; color: var(--sg-muted); line-height: 1.3; }
[data-testid="stMetricValue"] p { font-size: clamp(1.4rem, 2.4vw, 2.1rem); }
/* sidebar: long page names wrap, the glossary link too */
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] p,
section[data-testid="stSidebar"] [data-testid="stPageLink"] p { white-space: normal !important; overflow: visible !important;
  text-overflow: clip !important; line-height: 1.3; }
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] { min-height: 2rem; height: auto !important;
  align-items: center !important; padding-top: 3px !important; padding-bottom: 3px !important; }
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
.sg-head-sub { margin: 6px 0 0; font-size: 0.98rem; color: var(--sg-soft); max-width: 70ch; }
/* figures keep the mono face: digits line up and read as data */
[data-testid="stMetricValue"], .sg-cs-num, .sg-read-meta b, .sg-fol-meta b {
  font-family: 'JetBrains Mono', ui-monospace, monospace; font-variant-numeric: tabular-nums; }
/* follow: the sync slot renders nothing */
.st-key-sg_follow_sync, [data-testid="stElementContainer"]:has(.st-key-sg_follow_sync),
.st-key-sg_a11y, [data-testid="stElementContainer"]:has(.st-key-sg_a11y) { display: none !important; }
/* accessibility: text for screen readers only */
.sg-sr { position: absolute !important; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden;
  clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
/* accessibility: the skip link appears when a keyboard user reaches it */
.sg-skip { position: fixed; left: 12px; top: 12px; z-index: 1000001; padding: 8px 14px; font-size: 0.9rem;
  color: var(--sg-strong); background: var(--sg-panel); border: 1px solid var(--sg-accent); border-radius: 8px; text-decoration: none;
  transform: translateY(-160%); }
.sg-skip:focus { transform: none; }
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
.sg-cmp-score .sg-cs-num { font-size: 2.3rem; }
.sg-cmp-meta { font-size: 0.8rem; color: var(--sg-muted); line-height: 1.45; }
/* red-flag severity: a small drawn dot before the text */
.sg-sev { display: inline-block; width: 0.62em; height: 0.62em; border-radius: 50%; background: var(--c);
  margin-right: 0.5em; vertical-align: 0.02em; }
/* bold in the mono face barely differs from regular at body size: full weight and the brightest ink */
[data-testid="stMarkdownContainer"] :is(strong, b) { font-weight: 700; color: var(--sg-strong); }
/* following strip */
.sg-follow-head { font-size: 0.95rem; font-weight: 600; color: var(--sg-strong); margin: 4px 0 -4px; }
[class*="st-key-fol_"]:not([class*="st-key-fol_open"]) { position: relative; background: var(--sg-raised); border: 1px solid var(--sg-line);
  border-radius: 10px; padding: 8px 10px !important; }
[class*="st-key-fol_"]:not([class*="st-key-fol_open"]):hover { border-color: var(--sg-line-strong); background: var(--sg-panel); }
[class*="st-key-fol_"] [data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }
.sg-fol { display: flex; align-items: center; gap: 10px; }
.sg-fol img { width: 30px; height: 22px; object-fit: cover; border-radius: 3px; box-shadow: 0 0 0 1px rgba(255,255,255,0.14); }
.sg-fol-name { font-weight: 700; font-size: 0.86rem; color: var(--sg-strong); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  max-width: 140px; }
.sg-fol-meta { font-size: 0.72rem; color: var(--sg-muted); }
.sg-fol-meta b { color: var(--c); font-size: 0.84rem; }
[class*="st-key-fol_open_"] { position: absolute !important; inset: 0; margin: 0 !important; }
[class*="st-key-fol_open_"] button { position: absolute !important; inset: 0; width: 100%; height: 100%; opacity: 0; }
[data-testid="stElementContainer"]:has([class*="st-key-fol_open_"]) { position: absolute; inset: 0; }
/* country header */
.sg-country { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 14px 24px;
  border: 1px solid var(--sg-line); border-radius: 14px; padding: 18px 20px; margin: 6px 0 12px; background: var(--sg-raised); }
.sg-country-id { display: flex; align-items: center; gap: 16px; min-width: 0; flex: 1 1 320px; }
.sg-country-id img { width: 64px; height: 48px; object-fit: cover; border-radius: 6px; flex: none;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.14); }
.sg-country-name { margin: 0 !important; padding: 0 !important; font-size: clamp(1.7rem, 4.4vw, 2.4rem) !important;
  line-height: 1.1 !important; }
.sg-country-meta { color: var(--sg-muted); font-size: 0.84rem; margin-top: 6px; line-height: 1.45; }
.sg-country-score { display: flex; align-items: center; gap: 16px; flex: 0 1 auto; }
.sg-cs-num { font-size: 3rem; font-weight: 700; line-height: 1; color: var(--c); }
.sg-cs-num span { font-size: 0.95rem; color: var(--sg-faint); font-weight: 400; margin-left: 2px; }
.sg-cs-side { display: flex; flex-direction: column; gap: 5px; font-size: 0.8rem; color: var(--sg-soft); }
.sg-cs-line:empty { display: none; }
.sg-cs-spark { width: 150px; height: 46px; flex: none; }
@media (max-width: 640px) {
  .sg-country { padding: 14px; }
  .sg-country-id img { width: 48px; height: 36px; }
  .sg-cs-num { font-size: 2.4rem; }
  .sg-cs-spark { width: 110px; }
}
/* news cards */
.sg-news { list-style: none; padding: 0; margin: 0 0 6px; }
.sg-news li { margin: 0 0 2px; }
.sg-news li > a, .sg-news li > span { display: flex; gap: 10px; align-items: flex-start; padding: 7px 6px;
  border-radius: 8px; color: inherit !important; text-decoration: none !important; }
.sg-news li > a:hover { background: var(--sg-panel); }
.sg-news-text { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.sg-news-title { color: var(--sg-text); font-size: 0.85rem; line-height: 1.38; display: -webkit-box; -webkit-line-clamp: 3;
  -webkit-box-orient: vertical; overflow: hidden; }
.sg-news li > a:hover .sg-news-title { color: var(--sg-strong); text-decoration: underline; text-underline-offset: 3px; }
.sg-news-meta { color: var(--sg-faint); font-size: 0.72rem; }
/* reduced motion: transitions become instant; loading spinners keep turning (they are status, not decoration) */
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { transition-duration: 0.01ms !important; } }
"""


def _on_dock_search() -> None:
    st.session_state["_jump_to"] = st.session_state.get("dock_search")
    st.session_state["dock_search"] = None


def _sparkline(values: pd.Series, color: str, w: int = 92, h: int = 26, css: str = "sg-spark") -> str:
    """The country's risk since 2015 as a small seismogram (SVG)."""
    v = values.dropna()
    if len(v) < 2:
        return ""
    lo, hi = float(v.min()), float(v.max())
    if hi - lo < 10:  # small moves stay small
        mid = (hi + lo) / 2
        lo, hi = mid - 5, mid + 5
    pad = 3
    xs = [pad + i * (w - 2 * pad) / (len(v) - 1) for i in range(len(v))]
    ys = [h - pad - (val - lo) / (hi - lo) * (h - 2 * pad) for val in v]
    points = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    return (f'<svg class="{css}" viewBox="0 0 {w} {h}" aria-hidden="true">'
            f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="1.6" stroke-linejoin="round" '
            f'stroke-linecap="round" opacity="0.9"/><circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="2.6" '
            f'fill="{color}"/></svg>')


def _readout(current_url_path: str) -> None:
    """The tracked country: flag, score, tier, change and its risk since 2015. Tap to open it."""
    try:
        core = data.load_core()
        scores = data.get_scores(core, data.analysis_year(), weights_tuple(), core["version"])
        hist = history(core)
        countries = core["countries"]
        iso3 = current_country(countries)
        row = countries.set_index("iso3").loc[iso3]
    except Exception:  # the dock is a convenience; never let it break a page
        return
    score = scores["composite"].get(iso3) if iso3 in scores.index else None
    tier = scores["tier"].get(iso3) if iso3 in scores.index else None
    color = config.TIER_COLORS.get(tier, config.INK["faint"])
    years = (hist[hist["iso3"] == iso3].set_index("year")["composite"].sort_index().dropna() if not hist.empty
             else pd.Series(dtype=float))
    delta = years.iloc[-1] - years.iloc[-2] if len(years) >= 2 else None
    if score is None or pd.isna(score):
        meta = "not enough data to score"
    else:
        trend = "" if delta is None or pd.isna(delta) else f" · {trend_label(delta)}"
        meta = f"<b>{score:.0f}</b> · {html.escape(tier)}{trend}"
    flag = config.flag_url(row["iso2"])
    state = " on" if current_url_path == "country" else ""
    with st.container(key="sg_read", horizontal=True, vertical_alignment="center", wrap=False):
        st.markdown(
            f'<div class="sg-read{state}" style="--sg-c:{color}" title="Open the country profile">'
            '<span class="sg-tier"></span>'
            + (f'<img src="{flag}" alt="">' if flag else "")
            + f'<div class="sg-read-text"><div class="sg-read-name">{html.escape(str(row["name"]))}</div>'
            f'<div class="sg-read-meta">{meta}</div></div>{_sparkline(years, color)}</div>',
            unsafe_allow_html=True,
        )
        with st.container(key="sg_read_link"):
            st.page_link(COUNTRY_PAGE, label=f"Open {row['name']}")


def _follow_jump(pages: dict) -> None:
    """A pick from Find or a followed-country card, made on the previous run: open that country or page now."""
    jump = st.session_state.pop("_jump_to", None)
    if not jump:
        return
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


def dock(current_url_path: str, pages: dict) -> None:
    """A console bar along the bottom of every page: the tracked country, the main pages and Find."""
    _follow_jump(pages)
    if current_url_path:  # any page but the overview: the overview stops pointing first-timers to the introduction
        st.session_state["_explored"] = True
    st.html(f"<style>{TOKENS_CSS}{GLOBAL_CSS}{DOCK_CSS}</style>")
    follow.sync()
    a11y.page_helper()
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
        _readout(current_url_path)  # last, so the tabs never wait for it (CSS shows it first)


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
        st.stop()
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
            st.button("Reset weights", on_click=_reset_weights, type="tertiary", key="sg_weights_reset")
    return core, year, values, scores


def history(core: dict) -> pd.DataFrame:
    """The index for every year since config.HISTORY_START, with the current weights."""
    return data.get_history(core, weights_tuple(), core["version"])


@st.cache_data(ttl=600, show_spinner=False)
def assessments() -> dict[str, dict]:
    return content.load_assessments()


def master_table(core: dict, values: pd.DataFrame, scores: pd.DataFrame, hist: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per country with names, groups, flags, scores and analyst info (+ change vs last year)."""
    from . import scoring  # local import keeps module import order simple

    countries = core["countries"].set_index("iso3")
    table = countries[["name", "region", "income", "iso2", "lat", "lng"]].join(scores, how="left").join(
        values[["population", "gdppc", "battle_deaths_raw"]], how="left"
    )
    table["flag"] = table["iso2"].map(config.flag_url)
    if hist is not None and not hist.empty:
        last_year = int(hist["year"].max()) - 1
        prev = hist[hist["year"] == last_year].set_index("iso3")
        table["prev_composite"] = prev["composite"].reindex(table.index)
        table["prev_tier"] = prev["tier"].reindex(table.index)
        table["delta_1y"] = table["composite"] - table["prev_composite"]
        table["trend"] = table["delta_1y"].map(trend_label)
    table["flags"] = scoring.flag_counts(values).reindex(table.index).fillna(0).astype(int)
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


def trend_label(delta) -> str:
    """Arrow + change vs last year. Up = riskier."""
    if delta is None or pd.isna(delta):
        return "—"
    if delta >= TREND_THRESHOLD:
        return f"▲ {delta:+.1f}"
    if delta <= -TREND_THRESHOLD:
        return f"▼ {delta:+.1f}"
    return f"■ {delta:+.1f}"


def flag_img(iso2, height: str = "1em") -> str:
    url = config.flag_url(iso2)
    if not url:
        return ""
    return (f'<img src="{url}" alt="" style="height:{height};aspect-ratio:4/3;border-radius:3px;'
            f'vertical-align:-0.12em;margin-right:0.35em;box-shadow:0 0 0 1px var(--sg-line)">')


def country_header(name: str, row: pd.Series, years: pd.Series, delta, year: int, meta: str,
                   analyst_rating: str | None = None) -> None:
    """The top of a country profile: identity on the left, the score with tier, rank, change and trend on the right."""
    tier = row.get("tier")
    color = config.TIER_COLORS.get(tier, config.INK["faint"])
    score = row.get("composite")
    flag = config.flag_url(row.get("iso2"))
    rank = "" if pd.isna(row.get("rank")) else f"#{int(row['rank'])} of {int(row['n_ranked'])}"
    if delta is None or pd.isna(delta):
        change = ""
    else:
        arrow, tone = ("▲", "var(--sg-worse)") if delta >= TREND_THRESHOLD else (
            ("▼", "var(--sg-better)") if delta <= -TREND_THRESHOLD else ("■", "var(--sg-faint)"))
        change = f'<span style="color:{tone}">{arrow} {delta:+.1f}</span> vs {year - 1}'
    analyst = (f'<div class="sg-cs-line">Analyst: {tier_badge(analyst_rating)}</div>' if analyst_rating else "")
    st.markdown(
        '<div class="sg-country">'
        '<div class="sg-country-id">'
        + (f'<img src="{flag}" alt="">' if flag else "")
        + f'<div><h1 class="sg-country-name">{html.escape(str(name))}</h1>'
        f'<div class="sg-country-meta">{meta}</div></div></div>'
        f'<div class="sg-country-score" style="--c:{color}">'
        f'<div class="sg-cs-num">{"—" if pd.isna(score) else f"{score:.0f}"}<span>/100</span></div>'
        f'<div class="sg-cs-side">{tier_badge(tier)}<div class="sg-cs-line">{rank}</div>'
        f'<div class="sg-cs-line">{change}</div>{analyst}</div>'
        f'{_sparkline(years, color, w=150, h=46, css="sg-cs-spark")}</div></div>',
        unsafe_allow_html=True,
    )


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
            color = config.TIER_COLORS.get(r["tier"], config.INK["faint"])
            delta = r.get("delta_1y")
            change = "" if pd.isna(delta) else trend_label(delta)
            flag = config.flag_url(r["iso2"])
            score = "—" if pd.isna(r["composite"]) else f"{r['composite']:.0f}"
            tier = html.escape(r["tier"]) if isinstance(r["tier"], str) else "—"
            with st.container(key=f"fol_{iso3}", width=210):
                st.markdown(
                    f'<div class="sg-fol" style="--c:{color}">' + (f'<img src="{flag}" alt="">' if flag else "")
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


def news_list(query_name: str | None, limit: int = 10, iso2=None) -> None:
    """Latest risk-related headlines with photos where the feed has one (the country flag otherwise).

    Bing News + Google News, GDELT as backup; cached for 10 minutes.
    """
    with guard("The news"):
        _news_list(query_name, limit, iso2)


def _news_list(query_name: str | None, limit: int, iso2) -> None:
    news = data.load_news(query_name)
    articles = news["articles"]
    if news["error"]:
        st.info("Headlines are unavailable: every news source refused the request. The app retries automatically.")
        return
    if articles is None or articles.empty:
        st.info("No matching headlines in the last 7 days.")
        return
    fallback = config.flag_url(iso2)
    items = []
    for row in articles.head(limit).itertuples(index=False):
        url = str(row.url or "")
        title = html.escape(str(row.title or ""))
        meta = " · ".join(x for x in (html.escape(str(row.domain or "")), _time_ago(row.seen)) if x)
        image = row.image if isinstance(row.image, str) and row.image.startswith("https://") else None
        if image:
            thumb = f'<img src="{html.escape(image)}" alt="" loading="lazy" style="{THUMB}">'
        elif fallback:
            thumb = (f'<span style="{THUMB};display:flex;align-items:center;justify-content:center">'
                     f'<img src="{fallback}" alt="" style="width:40px;border-radius:3px;opacity:0.85"></span>')
        else:  # no picture: no empty placeholder either, the headline takes the room
            thumb = ""
        body = (f'{thumb}<span class="sg-news-text"><span class="sg-news-title">{title}</span>'
                f'<span class="sg-news-meta">{meta}</span></span>')
        items.append(f'<li><a href="{html.escape(url)}" target="_blank" rel="noopener">{body}</a></li>'
                     if url.startswith("http") else f"<li><span>{body}</span></li>")
    st.markdown(f'<ul class="sg-news">{"".join(items)}</ul>', unsafe_allow_html=True)
    st.caption(f"{news['source']} · fetched {news['fetched']} · refreshes every 10 minutes. "
               "Collected automatically and unchecked: verify before citing.")


def tier_badge(tier: str | None, prefix: str = "") -> str:
    if not isinstance(tier, str) or tier not in config.TIER_ORDER:
        return '<span style="color:var(--sg-faint)">Not rated</span>'
    t = next(t for t in TIERS if t.label == tier)
    return (
        f'<span style="background:{t.color};color:{t.text_on};padding:3px 12px;border-radius:999px;'
        f'font-weight:600;font-size:0.9rem;white-space:nowrap">{prefix}{tier}</span>'
    )


def tier_legend() -> str:
    parts = [tier_badge(t.label) + f'<span style="color:var(--sg-faint);font-size:0.8rem;margin:0 10px 0 4px">'
             f'{int(t.lower)}+</span>' for t in TIERS]
    return '<div style="line-height:2.2">' + "".join(parts) + "</div>"


def country_options(countries: pd.DataFrame) -> tuple[list[str], dict[str, str]]:
    names = dict(zip(countries["iso3"], countries["name"]))
    order = sorted(names, key=lambda i: names[i])
    return order, names


def current_country(countries: pd.DataFrame, fallback: str = "NGA") -> str:
    """The country opened last in this visit; on a fresh visit, the first one this browser follows."""
    valid = set(countries["iso3"])
    followed = follow.following()
    for candidate in (st.session_state.get("country"), st.query_params.get("country"),
                      followed[0] if followed else None, fallback):
        if candidate and str(candidate).upper() in valid:
            return str(candidate).upper()
    return countries["iso3"].iloc[0]


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


def hero(title: str, subtitle: str = "") -> None:
    """The page title (the screen's one h1) and an optional line about the data under it."""
    st.markdown(
        f'<div class="sg-head"><h1 class="sg-head-title">{title}</h1>'
        + (f'<p class="sg-head-sub">{subtitle}</p>' if subtitle else "") + "</div>",
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


FLAG_COLUMN = st.column_config.ImageColumn(" ", width="small")
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
    st.caption("Sources: " + " · ".join(links) + (f" — {note}" if note else ""))


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
    if not (event and event.selection.rows):
        return
    row = frame.iloc[event.selection.rows[0]]
    name = str(row.get("name") or row["iso3"]).removeprefix("▶ ")
    if st.button(f"Open {name}", key=f"{key}_open", icon=":material/arrow_forward:"):
        go_to_country(row["iso3"])


def movers_lists(df: pd.DataFrame, n: int = 5, key: str = "movers") -> None:
    """Two lists: the biggest rises and falls in the composite since last year (tick a row to open it)."""
    valid = df.dropna(subset=["delta_1y"])
    risers = valid[valid["delta_1y"] >= TREND_THRESHOLD].nlargest(n, "delta_1y").reset_index(drop=True)
    fallers = valid[valid["delta_1y"] <= -TREND_THRESHOLD].nsmallest(n, "delta_1y").reset_index(drop=True)
    left, right = st.columns(2)
    for col, title, frame, part in ((left, "▲ Biggest risers (riskier)", risers, "up"),
                                    (right, "▼ Biggest fallers (safer)", fallers, "down")):
        with col:
            st.markdown(f"**{title}**")
            if frame.empty:
                st.caption("No country moved by a point or more.")
                continue
            frame = frame.assign(tier_text=[f"{a} → {b}" if isinstance(a, str) and a != b else b
                                            for a, b in zip(frame["prev_tier"], frame["tier"])])
            event = st.dataframe(
                frame[["iso3", "flag", "name", "composite", "trend", "tier_text"]], hide_index=True,
                on_select="rerun", selection_mode="single-row", key=f"{key}_{part}",
                column_config={
                    "iso3": None, "flag": FLAG_COLUMN, "name": "Country",
                    "composite": st.column_config.NumberColumn("Score", format="%.0f"),
                    "trend": "Change", "tier_text": "Tier",
                },
            )
            open_selected(event, frame, f"{key}_{part}")


def country_table(df: pd.DataFrame, key: str, height: int | None = None, extra: dict | None = None,
                  sort: str = "rank", ascending: bool = True) -> None:
    """A ranking table (flag, score, change, tier, pillars); a ticked row offers its profile."""
    # Score and change right after the name, so they stay on screen when the table is narrower than its columns
    cols = ["iso3", "flag", "name", "composite", "trend", "tier", "rank", *[p.key for p in PILLARS], *(extra or {})]
    frame = df.sort_values(sort, ascending=ascending, na_position="last")[[c for c in cols if c in df.columns]]
    frame = frame.reset_index(drop=True)
    event = st.dataframe(
        frame, hide_index=True, on_select="rerun", selection_mode="single-row", key=key, height=height,
        column_config={
            "iso3": None, "flag": st.column_config.ImageColumn(" ", width="small", pinned=True),
            "name": st.column_config.TextColumn("Country", pinned=True, width="medium"),
            "rank": st.column_config.NumberColumn("Global rank", format="%d"),
            "composite": st.column_config.ProgressColumn("Composite", min_value=0, max_value=100, format="%.0f",
                                                         color=config.TIER_COLORS["Elevated"]),
            "trend": "1-yr change", "tier": "Tier",
            **{p.key: st.column_config.ProgressColumn(p.short, min_value=0, max_value=100, format="%.0f",
                                                      color=config.PILLAR_COLORS[p.key]) for p in PILLARS},
            **(extra or {}),
        },
    )
    open_selected(event, frame, key)


def upcoming_events(events: pd.DataFrame, limit: int = 8) -> None:
    """Upcoming watchlist events with a countdown."""
    today = pd.Timestamp.today().normalize()
    upcoming = events[events["date"] >= today].sort_values("date").head(limit)
    if upcoming.empty:
        st.caption("No upcoming events in the watchlist.")
        return
    rows = []
    for e in upcoming.itertuples(index=False):
        days = (e.date - today).days
        when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"
        colour = {"High": "#fd8078", "Medium": "#e19f3f"}.get(str(e.significance).title(), "var(--sg-faint)")
        source = (f' · <a href="{html.escape(e.source_url)}" target="_blank" rel="noopener">source</a>'
                  if str(e.source_url).startswith("http") else "")
        rows.append(
            f'<li style="margin:0 0 0.6em 0;line-height:1.35"><b>{html.escape(str(e.event))}</b><br>'
            f'<span style="color:var(--sg-faint);font-size:0.82em">{html.escape(str(e.country))} · {e.date:%d %b %Y} · '
            f'<span style="color:{colour}">{when}</span> · {html.escape(str(e.significance))} significance{source}</span></li>'
        )
    st.markdown(f'<ul style="list-style:none;padding:0;margin:0;font-size:0.9rem">{"".join(rows)}</ul>',
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
        st.caption(f"**{current['title']}** · {current['channel']} · {_time_ago(current['published'])}")
    cols = st.columns(columns)
    for i, v in shown.iterrows():
        with cols[i % columns], st.container(border=True, key=f"vidcard_{key}_{i}"):
            st.image(v["thumbnail"], width="stretch")
            url = f"https://www.youtube.com/watch?v={v['video_id']}"
            st.markdown(f"**[{v['title'].replace('[', '(').replace(']', ')')}]({url})**")
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
            st.markdown("\n".join(f"- {e}" for e in r.events))
        else:
            st.caption("No events in the watchlist for the next 12 months.")

    st.markdown("#### What to do with it")
    tabs = st.tabs(list(interpret.AUDIENCES.values()))
    for tab, audience in zip(tabs, interpret.AUDIENCES):
        with tab:
            st.markdown("\n".join(f"- {a}" for a in r.actions.get(audience, [])))
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


def footer() -> None:
    st.divider()
    st.caption(
        f"**{config.APP_TITLE}** — {config.APP_DESCRIPTION} Data: World Bank Worldwide Governance Indicators & World "
        "Development Indicators · IMF World Economic Outlook · UNHCR · UCDP (via World Bank) · Bing News, Google News "
        "and GDELT. Scores are relative and model-based, and they do not forecast specific events. "
        f"Built by {config.AUTHOR}."
    )
    st.page_link(SOURCES_PAGE, label="All sources, with links and update dates", icon=":material/verified:")
