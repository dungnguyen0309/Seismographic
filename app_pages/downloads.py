"""Data downloads: the index, its inputs, red flags, history and the conflict outlook, with a data dictionary."""

from urllib.parse import urlsplit

import streamlit as st

from prm import api, data, export, ui

core, year, values, scores = ui.load()
weights = ui.weights_tuple()
tables = data.get_export(core, year, weights, core["version"])
info = export.meta(core, year, dict(weights))

ui.hero("Data downloads", "Everything behind the index as open tables. When you reuse them, credit the original "
                           "publishers.")
st.page_link(ui.SOURCES_PAGE, label="Sources", icon=":material/verified:")

with st.container(horizontal=True, key="dl_all"):
    st.download_button("Download all tables (Excel)", data=lambda: export.to_excel(tables, info),
                       file_name=f"seismographic-{year}.xlsx", type="primary", icon=":material/table_view:",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.download_button("Download all tables (JSON)", data=lambda: export.to_json(tables, info),
                       file_name=f"seismographic-{year}.json", mime="application/json", icon=":material/data_object:")

st.header("Tables")
with st.container(border=True, gap="small"):
    for name, text in export.TABLES.items():
        frame = tables[name]
        left, right = st.columns([5, 1], vertical_alignment="center")
        rows = f"{len(frame):,} rows"
        if name == "index" and "composite" in frame:  # every economy is listed; some lack the data for a score
            rows += (f" ({int(frame['composite'].notna().sum())} with a score; the others have too little data and "
                     "their scores are blank)")
        left.markdown(f"**{name.replace('_', ' ').capitalize()}** · {rows}  \n"
                      f"<span style='color:var(--sg-muted);font-size:0.86rem'>{text}</span>", unsafe_allow_html=True)
        right.download_button("Download CSV", data=lambda f=frame: f.to_csv(index=False).encode("utf-8"),
                              file_name=f"seismographic-{name}-{year}.csv", mime="text/csv", key=f"dl_{name}",
                              type="tertiary", icon=":material/download:")

st.header("Preview")
pick = st.segmented_control("Table", list(export.TABLES), default="index", key="dl_preview",
                            format_func=lambda n: n.replace("_", " ").capitalize(),
                            label_visibility="collapsed") or "index"
st.dataframe(tables[pick].head(300).round(3 if pick == "conflict_outlook" else 1), hide_index=True, height=360)

if api.ENABLED:  # only where the app runs as an ASGI app (asgi.py)
    st.header("JSON API")
    url = urlsplit(st.context.url or "")
    base = f"{url.scheme}://{url.netloc}{api.PREFIX}" if url.netloc else api.PREFIX
    st.code(f"{base}/countries\n{base}/countries?region=South Asia\n{base}/countries/KEN\n{base}/dictionary",
            language="text")
    st.caption("Read-only, no key needed, default weights. Filter the list with ?region=, ?income= or ?tier=.")
