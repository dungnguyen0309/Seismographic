# Vendored files

Everything the site loads at runtime, except YouTube embeds. Licence texts are in `licenses/`.

| Path | Source | Licence |
|---|---|---|
| plotly/plotly.min.js | plotly.js v4.1.1, from the Python plotly package (`package_data/plotly.min.js`) | MIT (header in file) |
| plotly/topojson/world_110m.json | https://cdn.plot.ly/un/world_110m.json, plotly.js's default geo base map (the flat maps; plot() sets topojsonURL to this folder) | MIT, shipped with plotly.js (dist/topojson); boundaries from UN geospatial data |
| globe/globe.gl.min.js | https://cdn.jsdelivr.net/npm/globe.gl@2.46.2/dist/globe.gl.min.js (bundles three.js) | MIT, licenses/globe.gl.txt |
| geo/ne_110m.geojson | https://cdn.jsdelivr.net/gh/vasturiano/globe.gl@v2.46.2/example/datasets/ne_110m_admin_0_countries.geojson; properties trimmed, coordinates 4 dp (scripts/trim_geojson.py) | Public domain (Natural Earth), licenses/natural-earth.txt |
| geo/ne_50m.geojson | https://cdn.jsdelivr.net/gh/nvkelso/natural-earth-vector@v5.1.2/geojson/ne_50m_admin_0_countries.geojson; properties trimmed, coordinates 4 dp (scripts/trim_geojson.py) | Public domain (Natural Earth) |
| earth/earth-night.jpg, earth/earth-topology.png | https://cdn.jsdelivr.net/npm/three-globe@2.45.2/example/img/ | MIT, licenses/three-globe.txt |
| flags/<iso2 lower case>.svg | https://cdn.jsdelivr.net/npm/flag-icons@7.5.0/flags/4x3/<iso2>.svg, one per code in data/snapshot/countries.csv except JG | MIT, licenses/flag-icons.txt |
| fonts/JetBrainsMono-{400,500,600,700}.woff2 | https://cdn.jsdelivr.net/npm/@fontsource/jetbrains-mono/files/jetbrains-mono-latin-<weight>-normal.woff2 | SIL OFL 1.1, licenses/jetbrains-mono.txt |
| icons/<name>.svg | https://cdn.jsdelivr.net/npm/@material-symbols/svg-400@0.31.0/outlined/<name>.svg (the names used in streamlit_app.py and prm/ui.py) | Apache 2.0, licenses/material-symbols.txt |
