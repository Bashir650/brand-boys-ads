import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from dashboard.utils import load_competitors_df, load_meta_ads_df, load_tiktok_ads_df

st.set_page_config(page_title="Competitor Ads Library", layout="wide")
st.title("Competitor Ads Library")

competitors = load_competitors_df()
if not competitors.empty:
    competitors = competitors[~competitors["is_own_brand"]]
meta_ads = load_meta_ads_df()
tiktok_ads = load_tiktok_ads_df()

if competitors.empty:
    st.info("Add competitors to config/competitors.yaml, then run the pipeline.")
    st.stop()

name_by_id = dict(zip(competitors["id"], competitors["name"]))
selected = st.multiselect(
    "Competitors", options=competitors["name"].tolist(), default=competitors["name"].tolist()
)
selected_ids = competitors[competitors["name"].isin(selected)]["id"].tolist()

tab_meta, tab_tiktok = st.tabs(["Meta (Facebook/Instagram) Ads", "TikTok Ads"])

with tab_meta:
    df = meta_ads[meta_ads["competitor_id"].isin(selected_ids)].copy()
    if df.empty:
        st.info("No Meta ads captured yet for the selected competitors.")
    else:
        df["competitor"] = df["competitor_id"].map(name_by_id)
        df["still_running"] = df["ad_delivery_stop_time"].isna()
        st.dataframe(
            df[
                [
                    "competitor",
                    "page_name",
                    "ad_creative_body",
                    "publisher_platforms",
                    "ad_delivery_start_time",
                    "still_running",
                    "ad_snapshot_url",
                ]
            ].sort_values("ad_delivery_start_time", ascending=False),
            use_container_width=True,
            hide_index=True,
        )

with tab_tiktok:
    df = tiktok_ads[tiktok_ads["competitor_id"].isin(selected_ids)].copy()
    if df.empty:
        st.info(
            "No TikTok ads captured yet. Either the pipeline hasn't run, "
            "ENABLE_TIKTOK_COLLECTOR is off, or the unofficial Creative Center endpoint "
            "needs updating - see src/collectors/tiktok_creative_center.py."
        )
    else:
        df["competitor"] = df["competitor_id"].map(name_by_id)
        st.dataframe(
            df[["competitor", "brand_name", "caption", "likes", "comments", "shares", "video_url"]].sort_values(
                "likes", ascending=False
            ),
            use_container_width=True,
            hide_index=True,
        )
