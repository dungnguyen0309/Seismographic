"""Page-level accessibility that Streamlit leaves out, added once per page by the dock:

- a "Skip to content" link as the first tab stop (the sidebar and dock put about 40 links before the page title)
- Material icons, which Streamlit draws as ligature text ("public", "compare_arrows"), hidden from screen readers
  so links read "Global overview" rather than "public Global overview"
"""

from __future__ import annotations

import streamlit as st

_HTML = '<span class="sg-a11y" hidden></span>'
_JS = """
export default function () {
  // Icons drawn as ligature text are decoration: hide them from assistive tech, also as Streamlit redraws the page
  // (two forms: icon elements, and icons inside Markdown labels, e.g. tab names, which carry an "x icon" label)
  const hide = () => document.querySelectorAll(
    '[data-testid="stIconMaterial"]:not([aria-hidden]), span[role="img"][translate="no"][aria-label$=" icon"]:not([aria-hidden])'
  ).forEach((e) => e.setAttribute("aria-hidden", "true"));
  hide();
  if (!window.sgIconWatch) {
    let queued = false;
    window.sgIconWatch = new MutationObserver(() => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => { queued = false; hide(); });
    });
    window.sgIconWatch.observe(document.body, { childList: true, subtree: true });
  }
  // Skip link: the first thing a keyboard user reaches; it moves focus to the page title
  if (!document.querySelector(".sg-skip")) {
    const a = document.createElement("a");
    a.className = "sg-skip";
    a.href = "#";
    a.textContent = "Skip to content";
    a.addEventListener("click", (e) => {
      e.preventDefault();
      const target = document.querySelector('[data-testid="stMain"] h1') || document.querySelector('[data-testid="stMain"]');
      if (!target) return;
      target.setAttribute("tabindex", "-1");
      target.focus();
    });
    document.body.prepend(a);
  }
}
"""
_component = st.components.v2.component("sg_a11y", html=_HTML, js=_JS, isolate_styles=False)


def page_helper() -> None:
    """Mount once per page (renders nothing visible)."""
    _component(key="sg_a11y", width="content")
