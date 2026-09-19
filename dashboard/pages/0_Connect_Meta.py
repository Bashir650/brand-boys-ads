import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from src.auth.meta_oauth import build_authorize_url, exchange_code_for_token, load_token
from src.config import settings

st.set_page_config(page_title="Connect Meta", layout="centered")
st.title("Connect your Meta Ads account")

st.markdown(
    """
    This is a **one-time** step. Once connected, the scheduled pipeline refreshes your
    own ad account's performance data on its own via the Marketing API - no chat/LLM
    tokens involved, and you don't need to reconnect every time the dashboard updates.

    **Before clicking connect**, make sure:
    1. You created a Meta app at [developers.facebook.com](https://developers.facebook.com)
       (My Apps -> Create App -> "Business") and set `META_APP_ID` / `META_APP_SECRET`
       in your `.env` file.
    2. Your redirect URL (e.g. `http://localhost:8501/Connect_Meta`, or your deployed
       dashboard's URL) is added under *Facebook Login -> Settings -> Valid OAuth
       Redirect URIs* on that app.
    3. Your Meta user is added as an Admin/Developer/Tester on the app - required while
       it's in Development Mode, which is fine for a single-account internal tool like
       this one (no App Review needed for your own ad account's data).
    """
)

if not settings.meta_app_id or not settings.meta_app_secret:
    st.error("Set META_APP_ID and META_APP_SECRET in your .env file first.")
    st.stop()

existing = load_token()
if existing:
    st.success("A Meta access token is already saved locally (secrets/meta_token.json).")

query_params = st.query_params
code = query_params.get("code")

if code:
    with st.spinner("Exchanging code for a long-lived token..."):
        try:
            token_data = exchange_code_for_token(code)
            days_valid = token_data.get("expires_in", 0) // 86400
            st.success(f"Connected! Token valid for about {days_valid} days.")
            st.query_params.clear()
        except Exception as exc:
            st.error(f"Token exchange failed: {exc}")
else:
    st.link_button("Connect with Facebook", build_authorize_url())

st.caption(
    "The token is stored locally in secrets/meta_token.json (gitignored) - never commit "
    "it. For the scheduled GitHub Action, put the long-lived token in the "
    "META_ACCESS_TOKEN repository secret instead (see README)."
)
