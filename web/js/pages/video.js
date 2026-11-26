// Live video: 24/7 international news channels, and the latest video reports and expert analysis (app_pages/video.py).
import * as ui from "../lib/ui.js";
import { h, clear } from "../lib/dom.js";
import { asRows } from "../lib/scoring.js";
import { pills, videosAbout } from "../charts/reference.js";

export const title = "Live video";
export const required = ["data/reference/video.json"];

// the visitor's picks, kept for the visit as the app keeps its widgets (a redraw for new weights does not reset them)
const kept = { region: null, channels: new Map(), about: "ALL", kind: "News reports" };
const KINDS = { "News reports": "news", "Analysis & explainers": "analysis", "Institutions & NGOs": "institutions" };

// Live now: a region, then one of its channels, in YouTube's player
function liveNow(box, channels) {
  const byRegion = Object.fromEntries(channels.regions.map((r) => [r, Object.keys(channels.live).filter((n) => channels.live[n].region === r)]));
  const channelBox = h("div", { class: "sg-stack" });
  const showRegion = (region) => {
    const names = byRegion[region];
    const playing = h("div", { class: "sg-stack" });
    const play = (name) => {
      kept.channels.set(region, name);
      const ch = channels.live[name];
      const state = ch.funding.startsWith("State");
      clear(playing).append(...[
        ui.livePlayer(ch.id),
        h("p", null, h("b", null, name), ` · based in ${ch.origin} · `, h("span", { class: `sg-ref-badge${state ? " warn" : ""}` }, ch.funding), " · ",
          h("a", { href: `https://www.youtube.com/channel/${encodeURIComponent(ch.id)}/live`, target: "_blank", rel: "noopener" }, "open on YouTube")),
        state ? ui.caption("State-owned and state-funded channels can reflect their government's view, especially on their own country and its foreign policy.") : null,
      ].filter(Boolean));
    };
    kept.region = region;
    const first = names.includes(kept.channels.get(region)) ? kept.channels.get(region) : names[0];
    clear(channelBox).append(pills({ label: "Channel", options: names, value: first, onChange: play }), playing);
    play(first);
  };
  const region = channels.regions.includes(kept.region) ? kept.region : channels.regions[0];
  box.append(pills({ label: "Region", options: channels.regions, value: region, format: (r) => `${r} · ${byRegion[r].length}`, onChange: showRegion }),
    channelBox, ui.cite(["youtube"]));
  showRegion(region);
}

export async function render(main, ctx) {
  await ui.loadCss("/css/reference.css");
  const countries = asRows(ctx.core.countries);
  const names = Object.fromEntries(countries.map((r) => [r.iso3, r.name]));
  const official = Object.fromEntries(countries.map((r) => [r.iso3, r.official_name ?? r.name]));
  const options = countries.map((r) => r.iso3).sort((a, b) => (names[a] < names[b] ? -1 : names[a] > names[b] ? 1 : 0));
  const [channels, videos] = await Promise.all(["/data/reference/video.json", "/data/videos.json"].map((u) => ctx.fetchJSON(u).catch((err) => {
    console.warn(`section data missing: ${u}`, err);
    return null;
  })));

  const live = h("div", { class: "sg-stack" });
  if (channels) liveNow(live, channels);
  else live.append(ui.emptyState("The live channels can't be shown right now. The rest of the page is unaffected."));
  main.append(...[ui.weightsNote(ctx), ui.hero(title), h("h2", null, "Live now"), live, h("h2", null, "Video reports & analysis")].filter(Boolean));

  const items = videos?.items ?? [];
  if (!items.length) { // as the app: the page ends here
    main.append(ui.emptyState("The video feeds couldn't be loaded. They refresh every day."));
    return;
  }
  const lookup = { newsNames: channels?.news_names ?? {}, aliases: videos.aliases ?? {} };
  const results = h("div", { class: "sg-stack" });
  const show = () => {
    const { about, kind } = kept;
    const pool = items.filter((v) => v.kind === KINDS[kind]);
    const notes = [];
    let shown = pool;
    if (about !== "ALL") {
      shown = videosAbout(pool, about, names, official[about], lookup);
      if (!shown.length) {
        notes.push(ui.emptyState(`None of the latest ${kind.toLowerCase()} mention ${names[about]}. Showing the newest from all countries.`));
        shown = pool;
      } else notes.push(ui.caption(`${shown.length} recent ${kind.toLowerCase()} mention ${names[about]}.`));
    }
    clear(results).append(...notes, shown.length ? ui.videoGallery(shown, { limit: 12 })
      : ui.emptyState(`No ${kind.toLowerCase()} could be loaded right now. They refresh every day.`));
  };
  main.append(
    h("div", { class: "sg-ref-cols sg-ref-cols-video" },
      ui.select({ label: "About", options: ["ALL", ...options], value: kept.about, format: (i) => (i === "ALL" ? "All countries" : names[i] ?? i),
        onChange: (v) => { kept.about = v; show(); } }),
      ui.segmented({ label: "Type", options: Object.keys(KINDS), value: kept.kind, onChange: (v) => { kept.kind = v; show(); } })),
    results, ui.cite(["youtube"]), ui.pageLink("/sources", "Channel ownership", "verified"), ui.footer());
  show();
}
