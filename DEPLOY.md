# Publishing Seismographic (no coding needed)

Two free ways to put the app online. Both update by themselves every time the GitHub repository changes.

## Option A: Streamlit Community Cloud (5 minutes)

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. Click **Create app** → **Deploy a public app from GitHub**.
3. Repository `ClockworkAngels666/Seismographic`, branch `main`, main file path `streamlit_app.py`.
4. Under **Advanced settings**, choose Python 3.12 or newer. Optionally set a custom **App URL** such as
   `seismographic`.
5. Click **Deploy**. The first build takes a few minutes. Pages open instantly from the saved snapshot and switch to
   live data by themselves about a minute later.

Streamlit Community Cloud shows a small "Hosted with Streamlit" badge in the bottom-right corner of the app.

## Option B: Hugging Face Spaces (10 minutes, no badge)

1. Sign up at [huggingface.co/join](https://huggingface.co/join) and confirm your e-mail.
2. Open [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) → **Create new token** → type
   **Write**, name it `seismographic-publish`, copy it. Keep it private.
3. Give GitHub the token (it asks you to paste it, then stores it encrypted) and the Space's name:

   ```bash
   gh secret set HF_TOKEN -R ClockworkAngels666/Seismographic
   ```

   ```bash
   gh variable set HF_SPACE -R ClockworkAngels666/Seismographic --body "YOUR-HF-USERNAME/Seismographic"
   ```

   Or on github.com: **Settings → Secrets and variables → Actions**.
4. On GitHub open **Actions** → **Publish to Hugging Face** → **Run workflow**. It creates the Space and uploads the
   app; from then on every push to `main` publishes by itself.
5. After 3–5 minutes of building, share `https://YOUR-HF-USERNAME-seismographic.hf.space` (username in lower case):
   the app full screen with nothing around it.

## Option C: Vercel (experimental, no badge)

The repository is ready for Vercel: `asgi.py` runs the app as a standard Python web app (Streamlit's `st.App`), and
`vercel.json` gives it the longest time Vercel's free plan allows.

1. Sign in at [vercel.com](https://vercel.com) with GitHub (**Continue with GitHub**).
2. **Add New… → Project**, then **Import** `ClockworkAngels666/Seismographic`. If it isn't listed, click
   **Adjust GitHub App Permissions** and allow Vercel to see the repository.
3. Leave the settings as they are (Framework Preset: *Other*) and click **Deploy**. Every push to `main` then
   deploys again by itself.

This deployment also serves the read-only JSON API at `/api/v1` (see the README), which `streamlit run` cannot.

Know the limits before relying on it. Vercel runs the app in short-lived functions and supports the live
connection Streamlit needs only in beta. On the free plan, each visitor's connection is cut after 5 minutes. The
page reconnects by itself, but it can come back as a fresh session, so choices such as the selected country or
the weights may reset. A first visit after a quiet spell also waits for a cold start. Options A and B do not have
these limits.

The `Dockerfile` in the repository also runs the app on Render, Fly.io or any other Docker host.

## Monthly data backup

The **Refresh data snapshot** action saves a copy of all data on the 3rd of every month, so pages open instantly
and keep working if a source is down. The Space republishes after each refresh. If a run fails at "Commit the
snapshot", go to **Settings → Actions → General → Workflow permissions**, pick **Read and write permissions**,
save, and run it again.

## Make it yours

* **Write assessments**: use the app's *Assessment builder* page, download the file and upload it to the
  `assessments` folder. See `assessments/README.md` for a writing guide.
* **Fill the watchlist**: use the helper on the *Events watchlist* page, then edit `data/events.csv` on GitHub
  (pencil icon → paste the line at the bottom → *Commit changes*).
* **Change the model**: weights, thresholds and indicators are all in `prm/config.py`.

Every change you commit on GitHub appears in the live app a few minutes later.

## Troubleshooting

| Problem | Fix |
|---|---|
| "This app has gone to sleep" (Streamlit) | Free apps sleep after a period without visitors. Click the button to wake it; open it yourself before sending the link to anyone. |
| The app shows an error on start-up (Streamlit) | Open **Manage app** (bottom right, only you see it) to read the logs. |
| The Space says it is sleeping | Free Spaces sleep after about two days without visitors. Opening it wakes it in under a minute; open it yourself before sending the link to anyone. |
| The Action fails with "401" or "403" | The token is missing or is not a **Write** token. Create a new one and set `HF_TOKEN` again. |
| The Action is skipped | The `HF_SPACE` variable is not set (step 2). |
| The Space shows "Build error" or "Runtime error" | Open the Space's **Logs** tab to see why. |
| A yellow banner says a source is unavailable | One of the APIs is down; scores use the other indicators. Click **↻ Refresh data** in the sidebar later. |
| News says it is unavailable | Every news source (Bing, Google, GDELT) refused at once — rare. It retries by itself within 10 minutes. |
| An assessment doesn't appear | Check the file name is the three-letter code (`NGA.md`), it is inside `assessments/`, and the top block starts and ends with `---`. |

## Putting it on your CV

> **Seismographic** — Designed and launched an open-source political-risk dashboard scoring around 200 economies
> on 17 indicators across four pillars, using live World Bank, IMF, UNHCR and UCDP data; authored quarterly
> risk assessments with probabilistic forecasts. *(link)*

Pin the repository on your GitHub profile and add the app link to the *Projects* or *Featured* section on LinkedIn.
