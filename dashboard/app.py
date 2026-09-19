import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from dashboard.utils import load_competitors_df, load_meta_ads_df, load_own_insights_df, load_tiktok_ads_df

st.set_page_config(page_title="Brand Boys Ads Intelligence", page_icon="📊", layout="wide")

st.title("Brand Boys - Ads Intelligence Dashboard")
st.caption(
    "All data below is pulled by a scheduled Python pipeline via official/public APIs "
    "(Meta Ad Library, Meta Marketing API, TikTok Creative Center). Opening this "
    "dashboard only *reads* the database - it never calls any AI model and costs no tokens."
)

competitors = load_competitors_df()
meta_ads = load_meta_ads_df()
tiktok_ads = load_tiktok_ads_df()
own = load_own_insights_df()

col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "Competitors tracked",
    int((~competitors["is_own_brand"]).sum()) if not competitors.empty else 0,
)
col2.metric("Meta ads captured", len(meta_ads))
col3.metric("TikTok ads captured", len(tiktok_ads))
col4.metric("Days of own-account data", int(own["date"].nunique()) if not own.empty else 0)

st.divider()
st.markdown(
    """
    Use the pages in the sidebar:
    - **Connect Meta** - one-time OAuth link to your Facebook/Meta Ads account
      (not required to browse competitor data).
    - **Competitor Ads Library** - every Meta/TikTok ad captured per competitor.
    - **Winning Creatives & Dupes** - which competitor creatives are being scaled
      (long-running, reused across pages/countries) - the best signal available
      since Meta hides spend/impressions on ordinary commercial ads.
    - **Our Meta Performance** - your connected ad account's real spend/CTR/ROAS trends.
    - **Forecasts** - short-horizon projections for your own account's key metrics.
    """
)

if competitors.empty:
    st.warning(
        "No competitors configured yet. Edit `config/competitors.yaml` and run "
        "`python -m src.pipeline`."
    )
