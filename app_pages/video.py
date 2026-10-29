"""Live TV & video: 24/7 international news channels, and the latest video reports and expert analysis."""

import streamlit as st

from prm import config, data, ui

core, year, values, scores = ui.load()
countries = core["countries"]
options, names = ui.country_options(countries)
official = dict(zip(countries["iso3"], countries.get("official_name", countries["name"])))

ui.hero("Live TV & video")

# --- Live now ---------------------------------------------------------------------------------------
st.header("Live now")
by_region = {r: [n for n, c in config.LIVE_CHANNELS.items() if c.region == r] for r in config.LIVE_REGIONS}
region = st.pills("Region", config.LIVE_REGIONS, default=config.LIVE_REGIONS[0], key="live_region",
                  format_func=lambda r: f"{r} · {len(by_region[r])}") or config.LIVE_REGIONS[0]
channel = st.pills("Channel", by_region[region], default=by_region[region][0],
                   key=f"live_channel_{region}") or by_region[region][0]
picked = config.LIVE_CHANNELS[channel]

ui.live_player(picked.id)
state_media = picked.funding.startswith("State")
st.markdown(
    f"**{channel}** · based in {picked.origin} · "
    + (f":orange-badge[{picked.funding}]" if state_media else f":gray-badge[{picked.funding}]")
    + f" · [open on YouTube](https://www.youtube.com/channel/{picked.id}/live)"
)
if state_media:
    st.caption("State-owned and state-funded channels can reflect their government's view, especially on their own "
               "country and its foreign policy. Compare with another channel.")
ui.cite("youtube")

# --- Reports and analysis ---------------------------------------------------------------------------
st.header("Video reports & analysis")
videos = data.load_videos()
if videos is None or videos.empty:
    st.info("The video feeds can't be reached right now. They are tried again every few minutes.")
    st.stop()

KINDS = {"News reports": "news", "Analysis & explainers": "analysis", "Institutions & NGOs": "institutions"}
f1, f2 = st.columns([1.4, 2])
about = f1.selectbox("About", ["ALL", *options], key="video_country",
                     format_func=lambda i: "All countries" if i == "ALL" else names.get(i, i))
kind = f2.segmented_control("Type", list(KINDS), default="News reports", key="video_kind") or "News reports"
pool = videos[videos["kind"] == KINDS[kind]]

if about == "ALL":
    shown = pool
else:
    shown = ui.videos_about(pool, about, names, official.get(about))
    if shown.empty:
        st.info(f"None of the latest {kind.lower()} mention {names[about]}. Showing the newest from all countries.")
        shown = pool
    else:
        st.caption(f"{len(shown)} recent {kind.lower()} mention {names[about]}.")
if shown.empty:
    st.info(f"No {kind.lower()} could be loaded right now. They are tried again every few minutes.")
else:
    ui.video_gallery(shown, key=f"gallery_{kind}_{about}", limit=12)
ui.cite("youtube")
st.page_link(ui.SOURCES_PAGE, label="Who runs each channel: ownership and location", icon=":material/verified:")
ui.footer()
