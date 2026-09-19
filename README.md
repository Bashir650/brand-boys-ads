# Brand Boys - Ads Intelligence Dashboard

A code-based, API-driven competitive intelligence dashboard:

- A **Python pipeline** (`src/pipeline.py`) pulls data on a schedule via real
  APIs - Meta's official Ad Library API, Meta's Marketing API for your own ad
  account, and a best-effort TikTok Creative Center collector - and writes it
  to a local database.
- A **Streamlit dashboard** (`dashboard/`) only *reads* that database. Viewing
  it never calls an AI model and costs no LLM/chat tokens - tokens (Meta
  access tokens, that is) are only needed once, to connect your account.
- Everything is plain code (Python + SQL), version-controlled, no no-code
  tools.

## What it does

| Page | What it shows | Data source |
|---|---|---|
| Connect Meta | One-time OAuth to link your own ad account | Meta Login |
| Competitor Ads Library | Every ad captured per tracked competitor | Meta Ad Library API, TikTok Creative Center |
| Winning Creatives & Dupes | Which competitor creatives are being scaled (long-running / reused variants) | Computed from the above |
| Our Meta Performance | Your account's real spend/CTR/ROAS/CPM trends | Meta Marketing API |
| Forecasts | Short-horizon projection of your own metrics | Computed from own-account history |

## Read this before you start: what the APIs actually give you

**Meta Ad Library API (competitor ads)** is public and free, but for ordinary
commercial ads (`ad_type=ALL`) Meta does **not** expose spend or impressions -
only the ad creative, dates, and page info. Spend/impressions are only
populated for `POLITICAL_AND_ISSUE_ADS`, and only in a handful of countries.
This is a deliberate restriction on Meta's side, not something this project
can work around. Because of that, "winning creative" for competitors is
inferred from **how long an ad keeps running** and **how many near-duplicate
variants are live at once** (see `src/analysis/winning_creative_score.py`) -
a widely used proxy, not real performance data.

**Meta Marketing API (your own account)** gives you everything - spend,
impressions, CTR, ROAS, etc. - because it's your own data.

**TikTok** has no official public API for browsing competitors' ads. The
TikTok Creative Center's public "Top Ads" page is the closest thing, and
`src/collectors/tiktok_creative_center.py` talks to its (undocumented)
backend on a best-effort basis. It can break if TikTok changes that endpoint,
and automated requests to it may fall outside TikTok's Terms of Service -
review those terms for your use case. It's gated behind
`ENABLE_TIKTOK_COLLECTOR` and fails soft (logs a warning, pipeline keeps
going) if it stops working; `scripts/import_manual_tiktok_csv.py` is a manual
fallback.

**Other ad libraries** (Google Ads Transparency Center, etc.) - see
`src/collectors/google_ads_transparency.py` for why that one is left as a
documented extension point rather than a fake implementation, and what it'd
take to wire up.

**Using the same setup for prospecting**, not just competitors: any brand
that's been running lots of ads for months in the Ad Library is spending real
budget - add Indian/international brands you'd like as clients to
`config/competitors.yaml` alongside your actual competitors (use the `notes`
field to tell them apart) and the same pipeline becomes a lead list.

## Setup

### 1. Create a Meta Developer App

1. Go to [developers.facebook.com](https://developers.facebook.com) -> **My
   Apps** -> **Create App** -> choose **Business**.
2. Add the **Marketing API** product to the app.
3. Under **App Settings -> Basic**, copy the **App ID** and **App Secret**
   into your `.env` (see step 3).
4. Under **Facebook Login -> Settings**, add your dashboard's URL as a valid
   OAuth redirect URI, e.g. `http://localhost:8501/Connect_Meta` for local
   use.
5. While the app is in **Development Mode** (the default, no App Review
   needed), add your own Facebook user as an Admin/Developer/Tester under
   **App Roles** - that's enough to pull your own ad account's data and to
   use the Ad Library API.

### 2. Install dependencies

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# fill in META_APP_ID, META_APP_SECRET
```

Edit `config/competitors.yaml`: add each competitor's Facebook Page ID (or a
search-terms fallback) and TikTok handle, plus one entry for your own brand
with `is_own_brand: true`.

### 4. Initialize the database and connect your own ad account

```bash
python scripts/init_db.py
streamlit run dashboard/app.py
```

Open the **Connect Meta** page and click through the OAuth flow once. This
saves a long-lived (~60 day) token to `secrets/meta_token.json` (gitignored -
never commit it). Alternatively run `python scripts/exchange_token.py` and
paste a token from the
[Graph API Explorer](https://developers.facebook.com/tools/explorer).

### 5. Run the pipeline

```bash
python -m src.pipeline
```

This pulls competitor ads, your own account's insights, computes
winning-creative scores and forecasts, and writes everything to
`data/ads.db`. Re-run it any time; it's idempotent (upserts by ad/date).

### 6. Automate it (no manual re-runs, no tokens spent per update)

`.github/workflows/update_data.yml` runs the pipeline daily via GitHub
Actions and commits the refreshed `data/ads.db` back to the repo. Set these
in **Settings -> Secrets and variables -> Actions**:

- Secrets: `META_APP_ID`, `META_APP_SECRET`, `META_ACCESS_TOKEN` (the
  long-lived token from step 4), `META_AD_ACCOUNT_ID` (format `act_123...`).
- Variables (optional): `AD_LIBRARY_COUNTRIES`, `ENABLE_TIKTOK_COLLECTOR`.

Committing a SQLite file via CI is the zero-infrastructure option for an
internal MVP. For multi-user or production use, swap `DATABASE_URL` for a
hosted Postgres instance (e.g. Supabase's free tier) instead - no code
changes needed elsewhere, SQLAlchemy handles both.

### 7. Deploy the dashboard

Any host that can run Streamlit works (Streamlit Community Cloud, a small
VM, etc.) - point it at the same `DATABASE_URL` the Action writes to. The
dashboard itself makes no outbound API calls at view-time, so it's cheap to
host and safe to share internally.

## Project layout

```
config/competitors.yaml      # who to track (competitors, prospects, own brand)
src/config.py                 # env + config loading
src/db/                       # SQLAlchemy models + session
src/collectors/                # one module per data source
  meta_ads_library.py          # official Meta Ad Library API
  meta_own_account.py          # official Meta Marketing API (your account)
  tiktok_creative_center.py    # best-effort, unofficial
  google_ads_transparency.py   # documented extension point (not implemented)
src/analysis/
  dedupe.py                    # near-duplicate creative clustering
  winning_creative_score.py    # days-running + variant-count heuristic
  forecasting.py                # Holt-Winters / linear trend projection
src/auth/meta_oauth.py         # one-time OAuth connect + long-lived token
src/pipeline.py                 # scheduled entry point, ties it all together
dashboard/                      # Streamlit app (read-only against the DB)
scripts/                        # init_db, manual token exchange, CSV import
.github/workflows/update_data.yml  # daily scheduled pipeline run
```

## Running tests

```bash
pytest
```

Covers the dedupe clustering and forecasting logic with synthetic data (no
API credentials required).

## Extending

- **More ad libraries**: follow the shape of `meta_ads_library.py` - a
  `sync_competitor_*` function, a table in `src/db/models.py`, one more call
  in `src/pipeline.py`.
- **Real image/video dedup**: `dedupe.py` currently clusters on ad copy text;
  swap in perceptual image hashing (`imagehash` + `Pillow`) once you're
  downloading creative assets from `ad_snapshot_url`.
- **Better forecasts**: `forecasting.py` is intentionally simple (Holt-Winters
  / linear trend) to keep dependencies light; swap in `prophet` or a proper
  MMM library once you have enough history to justify it.
