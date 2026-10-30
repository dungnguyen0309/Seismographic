"""Page-level accessibility that Streamlit leaves out, added once per page by the dock:

- a "Skip to content" link as the first tab stop (the sidebar and dock put about 40 links before the page title)
- "/" or Ctrl/Cmd + K to open Find
- focus put back on a control that Streamlit redraws after it is used (see keep_focus)
- Material icons, which Streamlit draws as ligature text ("public", "compare_arrows"), hidden from screen readers
  so links read "Global overview" rather than "public Global overview"
"""

from __future__ import annotations

import streamlit as st

_HTML = '<span class="sg-a11y" hidden></span>'
_JS = """
export default function (component) {
  const { data } = component;
  // A control that was just used and then redrawn (e.g. "Add to compare" becoming "Open comparison") gets the focus
  // back, so a keyboard user is not sent to the top of the page. The page draws after this runs, so wait for it.
  // The old element can still be on screen while the page redraws, so for a few seconds the focus is put back
  // whenever it falls to the page itself.
  if (data && data.focus) {
    const started = Date.now();
    const refocus = () => {
      const lost = !document.activeElement || document.activeElement === document.body;
      const el = document.querySelector(".st-key-" + data.focus + " button, .st-key-" + data.focus + " a");
      if (lost && el && !el.disabled && !el.closest('[data-stale="true"]')) el.focus();
      if (Date.now() - started < 4000) setTimeout(refocus, 100);
    };
    refocus();
  }
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
  // Find from the keyboard: "/" (when not typing) or Ctrl/Cmd + K opens the Find sheet with the cursor in its box
  if (!window.sgFindKey) {
    window.sgFindKey = true;
    document.addEventListener("keydown", (e) => {
      const el = document.activeElement;
      const typing = el && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable);
      if (!((e.key === "k" && (e.ctrlKey || e.metaKey)) || (e.key === "/" && !typing && !e.ctrlKey && !e.metaKey))) return;
      const find = [...document.querySelectorAll(".st-key-sg_tabs button")].find((b) => /Find/.test(b.innerText));
      if (!find) return;
      e.preventDefault();
      if (find.getAttribute("aria-expanded") !== "true") find.click();
      const focusBox = (tries) => {
        const box = document.querySelector('[data-testid="stPopoverBody"] input');
        if (box) box.focus();
        else if (tries > 0) setTimeout(() => focusBox(tries - 1), 60);
      };
      focusBox(10);
    });
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


FOCUS = "_sg_focus"  # session key: the widget key to give the focus back to on the next run


def keep_focus(widget_key: str) -> None:
    """Call from a widget's callback when the widget is redrawn as a new element: the focus returns to it."""
    st.session_state[FOCUS] = widget_key


def page_helper() -> None:
    """Mount once per page (renders nothing visible)."""
    _component(key="sg_a11y", data={"focus": st.session_state.pop(FOCUS, None)}, width="content")
