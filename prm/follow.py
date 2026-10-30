"""Follow countries: a ★ button whose list is remembered in the visitor's own browser (localStorage), no account needed.

`follow_button(iso3, name)` shows the button; `sync()` (called once per page by the dock) reads the list back so every
page knows which countries the visitor follows. The current list is in st.session_state["_following"].
"""

from __future__ import annotations

import streamlit as st

STATE = "_following"
MAX_FOLLOWED = 12

_HTML = '<button class="sg-follow" type="button" hidden></button>'
_CSS = """
.sg-follow { font: inherit; font-size: 0.86rem; height: 2.5rem; padding: 0 14px; border-radius: 8px; cursor: pointer;
  background: transparent; color: var(--sg-text); border: 1px solid rgba(250,250,250,0.2); white-space: nowrap; }
.sg-follow:hover { border-color: var(--sg-accent); color: var(--sg-strong); }
.sg-follow.on { border-color: color-mix(in srgb, var(--sg-accent) 60%, transparent); color: var(--sg-strong);
  background: rgba(244,243,238,0.08); }
.sg-follow[hidden] { display: none; }
"""
_JS = """
const KEY = "seismographic-following";
const read = () => {
  try { return (JSON.parse(localStorage.getItem(KEY) || "[]") || []).filter((x) => /^[A-Z]{3}$/.test(x)); }
  catch (e) { return []; }
};
const write = (list) => { try { localStorage.setItem(KEY, JSON.stringify(list)); } catch (e) {} };
const same = (a, b) => JSON.stringify(a || []) === JSON.stringify(b || []);

export default function (component) {
  const { data, parentElement, setStateValue } = component;
  const button = parentElement.querySelector(".sg-follow");
  const paint = (list) => {
    if (!data.iso3) { button.hidden = true; return; }
    const on = list.includes(data.iso3);
    button.hidden = false;
    button.classList.toggle("on", on);
    button.textContent = on ? "★ Following" : "☆ Follow";
    button.title = on ? "Stop following " + data.name : "Follow " + data.name + " (remembered in this browser)";
    button.setAttribute("aria-pressed", on ? "true" : "false");
  };
  const stored = read();
  if (!same(stored, data.following)) setStateValue("following", stored);  // tell Python what this browser follows
  paint(stored);
  button.onclick = () => {
    if (!data.iso3) return;
    const now = read();
    const next = now.includes(data.iso3) ? now.filter((x) => x !== data.iso3) : [...now, data.iso3].slice(-data.max);
    write(next);
    paint(next);
    setStateValue("following", next);
  };
}
"""
_component = st.components.v2.component("sg_follow", html=_HTML, css=_CSS, js=_JS, isolate_styles=False)


def following() -> list[str]:
    return list(st.session_state.get(STATE, []))


def _store(key: str) -> None:
    """Runs before the page re-runs, so the whole page already sees the new list."""
    value = st.session_state.get(key)
    new = value.get("following") if hasattr(value, "get") else getattr(value, "following", None)
    if isinstance(new, list):
        st.session_state[STATE] = [str(x) for x in new if isinstance(x, str)][-MAX_FOLLOWED:]


def _mount(iso3: str | None, name: str, key: str) -> None:
    _component(key=key, data={"iso3": iso3, "name": name, "following": following(), "max": MAX_FOLLOWED},
               default={"following": following()}, on_following_change=lambda: _store(key), width="content")


def sync() -> None:
    """Reads the followed countries back from the browser (renders nothing)."""
    _mount(None, "", "sg_follow_sync")


def follow_button(iso3: str, name: str) -> None:
    _mount(iso3, name, f"sg_follow_{iso3}")
