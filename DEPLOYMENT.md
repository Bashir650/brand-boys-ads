# Deploying the dashboard

## Why Netlify shows "Page not found"

Netlify (and Vercel's static tier, GitHub Pages, Cloudflare Pages, etc.) are
built for **static sites** and short-lived **serverless functions** - a
request comes in, a function runs for a few seconds, a response goes out.

This dashboard is a **Streamlit app**. Streamlit is a long-running Python
process that keeps a persistent WebSocket connection open to your browser for
as long as the page is open, and it reads a database file/connection on every
interaction. There is no `index.html` for Netlify to serve and no way to
"build" a Python server into a static bundle - so Netlify falls back to its
generic 404. This isn't a misconfiguration you can fix with a build setting;
it's the wrong category of host for this kind of app.

**Use one of the options below instead.** All of them connect to the same
GitHub repo the same way Netlify does (push to deploy); the difference is
they can actually run a persistent Python server.

## Which one should I use?

| | Streamlit Community Cloud | Render (Web Service) | Your own VM |
|---|---|---|---|
| Cost | Free | Free tier, sleeps when idle | Whatever the VM costs |
| Setup effort | Lowest - a few clicks | Low - one YAML file | Highest - you manage the OS |
| Custom domain | Paid tier only | Yes, free | Yes |
| Good for | Getting this running today | A stable internal tool with its own URL | Full control, no third-party dependency |

**Recommendation: start with Streamlit Community Cloud.** It's free, made by
the same people who make Streamlit, and needs no config files. Move to
Render or a VM later only if you need a custom domain or more control.

---

## Option A: Streamlit Community Cloud (recommended)

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with
   the same GitHub account connected to `Bashir650/brand-boys-ads`.
2. Click **New app**, pick this repository and the
   `claude/competitor-ads-dashboard-dcfd31` branch, and set **Main file
   path** to `dashboard/app.py`.
3. Before clicking Deploy, open **Advanced settings** and paste your `.env`
   values into the **Secrets** box in TOML format:
   ```toml
   META_APP_ID = "your-app-id"
   META_APP_SECRET = "your-app-secret"
   META_ACCESS_TOKEN = "your-long-lived-token"
   META_AD_ACCOUNT_ID = "act_1234567890"
   META_OAUTH_REDIRECT_URI = "https://<your-app-name>.streamlit.app/Connect_Meta"
   AD_LIBRARY_COUNTRIES = "IN,US"
   ```
   Streamlit Cloud injects these as environment variables, which
   `src/config.py` already reads - no code changes needed. **Never commit
   these values to the repo**; the secrets box is the only place they should
   live for this host.
4. Update the Meta App's **Valid OAuth Redirect URIs** (Facebook Login ->
   Settings) to include the `https://<your-app-name>.streamlit.app/Connect_Meta`
   URL from step 3, so the "Connect Meta" OAuth flow can redirect back.
5. Deploy. The app installs `requirements.txt` and starts
   `streamlit run dashboard/app.py` for you.
6. **Data freshness for free**: because `.github/workflows/update_data.yml`
   commits the refreshed `data/ads.db` to this same branch every night,
   Streamlit Community Cloud - which watches the repo and reboots on new
   commits - picks up the fresh data automatically. No extra sync step.

A `.python-version` file is included in this repo so Streamlit Cloud (and
Render) builds with the same Python version (3.11) this project was tested
against.

**First boot, before the pipeline has ever run**: the dashboard creates its
own (empty) database tables on startup if they don't exist yet, so a brand
new deploy shows "no data yet" messages instead of crashing - it doesn't
need `scripts/init_db.py` to have been run first. Once the GitHub Action
runs (nightly, or trigger it manually via **Actions -> Update ads data ->
Run workflow** to not wait for 3am UTC) and commits real data, the next
reboot picks it up.

## Option B: Render (Web Service)

Use this if you want a stable custom domain or don't want to depend on
Streamlit's own hosting.

1. This repo includes `render.yaml`. In the [Render
   dashboard](https://dashboard.render.com), choose **New -> Blueprint** and
   point it at this repo/branch. Render reads `render.yaml` and creates the
   service for you.
2. Render will prompt you to fill in the secret environment variables marked
   `sync: false` in `render.yaml` (`META_APP_ID`, `META_APP_SECRET`,
   `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID`) directly in its dashboard -
   again, never commit these.
3. Update the Meta App's Valid OAuth Redirect URIs to
   `https://<your-service>.onrender.com/Connect_Meta`.
4. Render auto-deploys on every push to the connected branch (including the
   nightly data-refresh commit from the GitHub Action), the same way
   Streamlit Cloud does.
5. Free-tier Render web services spin down after 15 minutes of inactivity
   and take ~30-60s to wake back up on the next visit - fine for an internal
   tool, mention it to your team so a slow first load isn't mistaken for a
   bug.

## Option C: Self-hosted VM

Use this only if you need full control (e.g. a shared Postgres database
instead of the git-committed SQLite file, or you're already running other
internal tools on a VM).

```bash
git clone https://github.com/Bashir650/brand-boys-ads.git
cd brand-boys-ads
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in real values, keep this file off git
python scripts/init_db.py
```

Run it as a systemd service so it survives reboots and restarts on crash:

```ini
# /etc/systemd/system/brand-boys-ads.service
[Unit]
Description=Brand Boys Ads Dashboard
After=network.target

[Service]
WorkingDirectory=/opt/brand-boys-ads
ExecStart=/opt/brand-boys-ads/.venv/bin/streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0
Restart=on-failure
EnvironmentFile=/opt/brand-boys-ads/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now brand-boys-ads
```

Put a reverse proxy (nginx/Caddy) with TLS in front of port 8501 rather than
exposing it directly - the dashboard shows real competitor and campaign data,
so don't leave it on plain HTTP or a bare port.

On a VM, `data/ads.db` won't update itself just because GitHub Actions
committed a new version upstream - either add a `git pull && systemctl
restart brand-boys-ads` cron job on the VM, or (better, for anything beyond
a single-user MVP) point `DATABASE_URL` at a hosted Postgres instance that
both the GitHub Action and the VM write to/read from directly, so there's no
git-commit-a-binary-file step at all.

---

## Secrets hygiene, whichever host you pick

- `.env`, `secrets/meta_token.json`, and `data/ads.db` (locally) are all
  gitignored - keep it that way. If you ever see a real access token in a
  diff you're about to commit, stop and remove it before pushing, then
  rotate the token in the Meta App dashboard.
- Set secrets through the host's own secrets UI (Streamlit Cloud's Secrets
  box, Render's environment variables, a VM's `EnvironmentFile`) - never in
  a file that gets committed.
- The GitHub Action already reads `META_ACCESS_TOKEN` etc. from **repository
  secrets**, not from `.env` - that's intentional and requires no change.
