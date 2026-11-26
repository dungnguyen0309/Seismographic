# Deploying Seismographic

The live site is the static build in `web/`. It is served from Vercel. Streamlit stays for local use
(`streamlit run streamlit_app.py`).

## Vercel

- Project: `seismographic`, team `internship-16d4`.
- Root directory: `web`. Framework preset: Other. No build command, no output directory override.
- Git-connected to `main`: every push to `main` deploys.
- Domain: `seismographic.vercel.app`.
- `web/vercel.json` holds the rewrites, redirects and headers. There are no functions.

## First deploy

The GDELT data is built only in GitHub Actions, so run the refreshes once before the first deploy.

1. On GitHub open **Actions** and run **Refresh news** by hand (**Run workflow**, `workflow_dispatch`).
2. When it is done, run **Refresh data snapshot** (the weekly data refresh) by hand.
3. Deploy the Vercel project, then open `https://seismographic.vercel.app`.
4. Turn the uptime check on: `gh workflow enable uptime.yml` (it stays off until the site is live). If a
   "Site down" issue is open from before, close it.

## Refresh workflows

| Workflow | When | What |
|---|---|---|
| Refresh data snapshot | Mondays 06:17 UTC | New data snapshot, full rebuild of `web/` |
| Refresh hotspots | Daily 04:41 UTC | Rebuilds `web/data/hotspots/` |
| Refresh news | Daily 03:11 UTC | Rebuilds news and videos |
| Uptime check | Every 30 minutes | Checks the live site |
| Watchlist check | Mondays 07:23 UTC | Opens an issue if the event calendar runs short |

Each refresh builds into a copy of `web/` (`scripts/refresh_web.sh`), checks it (validation, JS tests, smoke test of
every route) and only then commits. If any check fails, nothing is committed.

- All refresh workflows share one concurrency group, `data-snapshot`. Only one run is pending at a time, and a later
  trigger replaces the pending one.
- If a refresh hits a rebase conflict when it pushes, that run's data is lost. Do not push `web/` data by hand while
  a refresh is running. Rerun the workflow instead.
- A failed or cancelled refresh opens a GitHub issue titled "Data refresh failed: <workflow>". Only one is open per
  workflow.
- Each refresh re-enables the scheduled workflows, so GitHub does not disable them after 60 days without commits.
- `uptime.yml` checks the live site every 30 minutes and opens a "Site down" issue when it fails, and closes it when
  the site is back.

## Local use

```bash
streamlit run streamlit_app.py
```

See the README for building and serving the static site locally.

## Make it yours

- Assessments: write them in the app's *Assessment builder* page, download the file and put it in `assessments/`.
  See `assessments/README.md`.
- Event calendar: edit `data/events.csv`. Run the app with `SEISMOGRAPHIC_MAINTAINER=1` for the helper on the
  *Hotspots* calendar tab.
- Model: weights, thresholds and indicators are in `prm/config.py`.
- After a change to any of these, commit and push the change, then run **Refresh data snapshot** by hand (or wait for
  Monday's run). It rebuilds and checks `web/`. Do not build `web/` locally: GDELT is built only in GitHub Actions.

## Other hosts

The Streamlit app also runs on Streamlit Community Cloud (main file `streamlit_app.py`), Hugging Face Spaces (the
*Publish to Hugging Face* workflow, needs the `HF_TOKEN` secret and `HF_SPACE` variable) and any Docker host
(`Dockerfile`). These serve the Streamlit app, not the static site.
