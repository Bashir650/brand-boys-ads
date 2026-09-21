import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from dashboard.utils import load_competitors_df, load_meta_ads_df, load_tiktok_ads_df, meta_ad_library_browse_url

st.set_page_config(page_title="Competitor Ads Library", layout="wide")
st.title("Competitor Ads Library")
st.caption("Includes your own brand alongside competitors - the Ad Library is public data for any page.")

competitors = load_competitors_df()
meta_ads = load_meta_ads_df()
tiktok_ads = load_tiktok_ads_df()

if competitors.empty:
    st.info("Add competitors to config/competitors.yaml, then run the pipeline.")
    st.stop()

# Label own brand distinctly in the picker without changing the underlying name used to join.
display_name = {
    row.id: f"{row.name} (your brand)" if row.is_own_brand else row.name for row in competitors.itertuples()
}
options = [display_name[i] for i in competitors["id"]]
selected_display = st.multiselect("Brands", options=options, default=options)
selected_ids = [i for i in competitors["id"] if display_name[i] in selected_display]

tab_meta, tab_tiktok = st.tabs(["Meta (Facebook/Instagram) Ads", "TikTok Ads"])

with tab_meta:
    st.caption(
        "The automated pull only works for ads that reached the EU/UK, or political/"
        "social-issue ads anywhere - a Meta API restriction on ad_type=ALL, not "
        "something a token or verification unlocks. For everything else (most India-"
        "targeted brand ads), browse directly on the public Ad Library website below."
    )
    selected_rows = competitors[competitors["id"].isin(selected_ids)]
    with st.expander("Browse on the Ad Library website (works for any country)", expanded=True):
        for row in selected_rows.itertuples():
            url = meta_ad_library_browse_url(row.name, row.meta_page_id, row.meta_search_terms)
            st.markdown(f"- [{display_name[row.id]}]({url})")

    df = meta_ads[meta_ads["competitor_id"].isin(selected_ids)].copy()
    if df.empty:
        st.info("No Meta ads captured yet via the automated API pull for the selected brands - use the links above.")
    else:
        df["competitor"] = df["competitor_id"].map(display_name)
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
            width='stretch',
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
        df["competitor"] = df["competitor_id"].map(display_name)
        st.dataframe(
            df[["competitor", "brand_name", "caption", "likes", "comments", "shares", "video_url"]].sort_values(
                "likes", ascending=False
            ),
            width='stretch',
            hide_index=True,
        )
