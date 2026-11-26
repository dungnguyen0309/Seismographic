// Followed countries (prm/follow.py): a list of ISO3 codes in this browser's localStorage, no account needed.
import { h } from "./dom.js";

const KEY = "seismographic-following";
export const MAX_FOLLOWED = 12;
export const CHANGED = "sg:following"; // fired on window after every toggle, so the dock and strips redraw

function read() {
  try {
    return (JSON.parse(localStorage.getItem(KEY) || "[]") || []).filter((x) => /^[A-Z]{3}$/.test(x)).slice(-MAX_FOLLOWED);
  } catch {
    return []; // storage blocked or a bad value: nothing followed
  }
}

export const following = () => read();
export const isFollowing = (iso3) => read().includes(iso3);

// Follow or unfollow; returns true when the country is now followed. The oldest drops off past 12.
export function toggle(iso3) {
  const now = read();
  const next = now.includes(iso3) ? now.filter((x) => x !== iso3) : [...now, iso3].slice(-MAX_FOLLOWED);
  try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* storage blocked: nothing is remembered */ }
  window.dispatchEvent(new CustomEvent(CHANGED, { detail: next }));
  return next.includes(iso3);
}

// follow.follow_button: "☆ Follow" / "★ Following" for one country
export function followButton(iso3, name) {
  const btn = h("button", { type: "button", class: "sg-follow" });
  const paint = () => {
    const on = isFollowing(iso3);
    btn.classList.toggle("on", on);
    btn.textContent = on ? "★ Following" : "☆ Follow";
    btn.title = on ? `Stop following ${name}` : `Follow ${name} (remembered in this browser)`;
    btn.setAttribute("aria-pressed", String(on));
  };
  btn.addEventListener("click", () => { toggle(iso3); paint(); });
  paint();
  return btn;
}
