import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import plotly.express as px
import streamlit as st

from dashboard.palette import competitor_color_map
from dashboard.utils import load_competitors_df, load_winning_scores_df

st.set_page_config(page_title="Winning Creatives & Dupes", layout="wide")
st.title("Winning Creatives & Dupes")
st.caption(
    "Meta's Ad Library API doesn't expose spend or impressions for ordinary commercial "
    "ads - only for political/issue ads. The best available proxy for 'this creative is "
    "winning' is how long it keeps running and how many near-duplicate variants a brand "
    "is running at once (a sign they're scaling it)."
)

competitors = load_competitors_df()
if not competitors.empty:
    competitors = competitors[~competitors["is_own_brand"]]
scores = load_winning_scores_df()

if scores.empty:
    st.info("No scores yet - run `python -m src.pipeline` after adding competitors.")
    st.stop()

name_by_id = dict(zip(competitors["id"], competitors["name"]))
scores["competitor"] = scores["competitor_id"].map(name_by_id)
color_map = competitor_color_map(sorted(scores["competitor"].dropna().unique()))

top = scores.sort_values("score", ascending=False).head(30)
fig = px.bar(
    top,
    x="score",
    y="ad_ref_id",
    color="competitor",
    orientation="h",
    color_discrete_map=color_map,
    hover_data=["days_running", "variant_count", "rationale"],
    title="Top 30 highest-scoring competitor creatives",
)
fig.update_layout(yaxis_title="", xaxis_title="Winning-creative score", legend_title="Competitor")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Reused creatives (likely dupes / templates being scaled)")
dupes = scores[scores["variant_count"] > 1].sort_values("variant_count", ascending=False)
if dupes.empty:
    st.info("No reused creatives detected yet.")
else:
    st.dataframe(
        dupes[["competitor", "ad_ref_id", "variant_count", "days_running", "rationale"]],
        use_container_width=True,
        hide_index=True,
    )
