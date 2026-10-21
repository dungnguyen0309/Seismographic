"""Glossary & legend: every term, abbreviation, colour and symbol used in Seismographic."""

import html
import re

import streamlit as st

from prm import config, glossary, ui

LEGEND = ("🎨", "#e8e6dc", "Legend", "Tiers, pillar colours, colour scales and symbols.")


def slug(name: str) -> str:
    return "g-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def gradient(scale: list[list], title: str, low: str, high: str) -> str:
    stops = ", ".join(f"{c} {round(t * 100)}%" for t, c in scale)
    return (f'<div style="margin:0 0 14px 0"><div style="font-size:0.85rem;margin-bottom:4px">{html.escape(title)}</div>'
            f'<div style="height:12px;border-radius:6px;background:linear-gradient(90deg, {stops})"></div>'
            f'<div style="display:flex;justify-content:space-between;color:#898781;font-size:0.75rem;margin-top:3px">'
            f'<span>{html.escape(low)}</span><span>{html.escape(high)}</span></div></div>')


def highlight(text: str, query: str) -> str:
    """Escaped text with the search query marked."""
    if not query:
        return html.escape(text)
    parts = re.split(f"({re.escape(query)})", text, flags=re.I)
    return "".join(f'<mark style="background:#c9850066;color:inherit;border-radius:3px;padding:0 2px">'
                   f'{html.escape(p)}</mark>' if i % 2 else html.escape(p) for i, p in enumerate(parts))


def band(name: str, icon: str, color: str, blurb: str, count: int | None = None,
         sources: tuple[str, ...] = (), compact: bool = False) -> None:
    """A category header: icon, name, term count, what the category covers and the sources behind it."""
    count_html = (f'<span style="font-size:0.75rem;color:{color};border:1px solid {color}88;border-radius:999px;'
                  f'padding:1px 9px;white-space:nowrap">{count} term{"s" if count != 1 else ""}</span>'
                  if count is not None else "")
    backed = (f'<div style="font-size:0.76rem;color:#898781;margin-top:6px">Backed by: '
              f'{" · ".join(ui.source_link(k) for k in sources)}</div>' if sources else "")
    st.markdown(
        f'<div id="{slug(name)}" style="scroll-margin-top:72px;display:flex;gap:14px;align-items:flex-start;'
        f'background:linear-gradient(90deg,{color}2e,{color}0a 65%,transparent);border:1px solid {color}55;'
        f'border-left:6px solid {color};border-radius:12px;padding:{"10px 14px" if compact else "14px 18px"};'
        f'margin:{"14px" if compact else "28px"} 0 10px">'
        f'<div style="font-size:{"1.4rem" if compact else "1.9rem"};line-height:1.1">{icon}</div>'
        '<div style="flex:1;min-width:0"><div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap">'
        f'<span style="font-size:{"1.05rem" if compact else "1.3rem"};font-weight:700;color:#ffffff">'
        f'{html.escape(name)}</span>{count_html}</div>'
        f'<div style="color:#c3c2b7;font-size:0.9rem;margin-top:3px">{html.escape(blurb)}</div>{backed}</div></div>',
        unsafe_allow_html=True,
    )


def term_card(t: glossary.Term, color: str, query: str = "") -> str:
    color = config.PILLAR_COLORS[t.pillar] if t.pillar else color
    tags = "".join(f'<span style="display:inline-block;font-size:0.7rem;color:#c3c2b7;background:#ffffff0f;'
                   f'border:1px solid #ffffff1a;border-radius:999px;padding:0 8px;margin:6px 4px 0 0">'
                   f'{highlight(tag, query)}</span>' for tag in t.tags)
    link = ""
    if t.source:
        url = t.url or config.SOURCES[t.source].url
        label = "See the data" if t.url else ui.source_label(t.source)
        link = (f'<div style="margin-top:8px;font-size:0.75rem"><a href="{html.escape(url)}" target="_blank" '
                f'rel="noopener">{html.escape(label)} ↗</a></div>')
    return (f'<div style="background:#0f1012;border:1px solid #2c2c2a;border-left:3px solid {color};'
            f'border-radius:8px;padding:11px 13px">'
            f'<div style="font-weight:700;color:{color};font-size:0.95rem;line-height:1.35">{highlight(t.term, query)}'
            f'</div><div style="color:#d6d5cc;font-size:0.86rem;line-height:1.5;margin-top:4px">'
            f'{highlight(t.definition, query)}</div>{tags}{link}</div>')


def cards(items: list[glossary.Term], color: str, query: str = "") -> None:
    st.markdown('<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:10px">'
                + "".join(term_card(t, color, query) for t in items) + "</div>", unsafe_allow_html=True)


def category_terms(category: str, items: list[glossary.Term], color: str, query: str = "") -> None:
    """A category's cards; the indicators are split by pillar, each in its pillar's colour."""
    if category != glossary.INDICATORS_CATEGORY:
        cards(items, color, query)
        return
    for p in config.PILLARS:
        pillar_items = [t for t in items if t.pillar == p.key]
        if pillar_items:
            st.markdown(f'<div style="margin:12px 0 8px">{ui.pillar_chip(p.key)}</div>', unsafe_allow_html=True)
            cards(pillar_items, color, query)


ui.hero("📖 Glossary & legend", kicker="About")
terms = glossary.all_terms()
query = st.text_input("Search the glossary", placeholder="e.g. tier, inflation, WGI, IDP, red flag…",
                      key="glossary_search").strip()

# --- Search results ----------------------------------------------------------------------------------------
if query:
    q = query.lower()
    hits = {cat: [t for t in items if q in t.text.lower()] for cat, items in terms.items()}
    hits = {cat: items for cat, items in hits.items() if items}
    found = sum(len(v) for v in hits.values())
    st.caption(f"{found} matching term{'s' if found != 1 else ''} in {len(hits)} "
               f"categor{'ies' if len(hits) != 1 else 'y'}. Clear the search to browse everything.")
    if not hits:
        st.info("Nothing matches. Try a shorter word, or clear the search to browse the categories.")
    for cat, items in hits.items():
        meta = glossary.CATEGORIES[cat]
        band(cat, meta.icon, meta.color, meta.blurb, len(items), compact=True)
        category_terms(cat, items, meta.color, query)
    ui.footer()
    st.stop()

# --- Contents -------------------------------------------------------------------------------------------------
tiles = [(LEGEND[2], LEGEND[0], LEGEND[1], LEGEND[3], None)] + [
    (cat, glossary.CATEGORIES[cat].icon, glossary.CATEGORIES[cat].color, glossary.CATEGORIES[cat].blurb, len(items))
    for cat, items in terms.items()
]
st.markdown(
    '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(185px,1fr));gap:10px;margin:6px 0 4px">'
    + "".join(
        f'<a href="#{slug(name)}" style="text-decoration:none;color:inherit">'
        f'<div style="height:100%;box-sizing:border-box;background:#0f1012;border:1px solid #2c2c2a;'
        f'border-top:4px solid {color};border-radius:10px;padding:10px 12px">'
        f'<div style="display:flex;justify-content:space-between;align-items:center"><span style="font-size:1.35rem">'
        f'{icon}</span><span style="font-size:0.72rem;color:{color}">{"" if n is None else f"{n} terms"}</span></div>'
        f'<div style="font-weight:700;color:{color};margin-top:4px;line-height:1.3">{html.escape(name)}</div>'
        f'<div style="font-size:0.76rem;color:#a3a29a;margin-top:3px;line-height:1.4">{html.escape(blurb)}</div>'
        "</div></a>"
        for name, icon, color, blurb, n in tiles
    )
    + "</div>",
    unsafe_allow_html=True,
)

# --- Visual legend ------------------------------------------------------------------------------------
band(LEGEND[2], LEGEND[0], LEGEND[1], LEGEND[3])
left, right = st.columns(2, gap="large")
with left:
    st.markdown("**Risk tiers** (composite score)")
    st.markdown(ui.tier_legend(), unsafe_allow_html=True)
    st.markdown("**Pillars** (each has its own colour everywhere in the tool)")
    st.markdown(" ".join(ui.pillar_chip(p.key, p.short) for p in config.PILLARS), unsafe_allow_html=True)
    st.markdown("**Symbols**")
    st.markdown(
        "- 🔴 Critical · 🟠 Serious · 🟡 Watch — red-flag severity\n"
        "- ⚑ a red flag crossed · ✅ none crossed\n"
        "- ▲ riskier · ▼ safer · ■ steady — change since last year (1 point or more)\n"
        "- ✓ a written analyst assessment exists\n"
        "- ☆ follow · ★ following (kept in your browser)\n"
        "- ▶ play (replay the years on the globe, or play a video)"
    )
with right:
    st.markdown("**Colour scales**")
    scales = gradient(config.MAP_COLORSCALE, "Composite risk", "0 · lower risk", "higher risk · 100")
    scales += "".join(gradient(config.map_colorscale(p.key), f"{p.short} pillar risk", "lower", "higher")
                      for p in config.PILLARS)
    scales += gradient(config.CHANGE_COLORSCALE, "Change since last year (map of change)", "▼ safer", "riskier ▲")
    scales += gradient(config.reversed_scale(config.map_colorscale("social")), "Next event (watchlist globe)",
                       "now", "in a year")
    st.markdown(scales, unsafe_allow_html=True)
    st.caption("On a black background, dim = low and bright = high. Dark grey = not enough data; near-black = "
               "outside your filters.")

# --- Terms, by category -----------------------------------------------------------------------------------------
for category, items in terms.items():
    meta = glossary.CATEGORIES[category]
    band(category, meta.icon, meta.color, meta.blurb, len(items), meta.sources)
    category_terms(category, items, meta.color)
    if not meta.sources:
        st.page_link(ui.SOURCES_PAGE, label="Every source in full, with links and update dates",
                     icon=":material/verified:")
ui.footer()
