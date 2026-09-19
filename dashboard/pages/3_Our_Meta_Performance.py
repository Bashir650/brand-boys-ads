import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import plotly.express as px
import streamlit as st

from dashboard.palette import OWN_BRAND_COLOR
from dashboard.utils import load_own_insights_df

st.set_page_config(page_title="Our Meta Performance", layout="wide")
st.title("Our Meta Ads Performance")

df = load_own_insights_df()
if df.empty:
    st.info(
        "Not connected yet, or the pipeline hasn't pulled insights. Go to the "
        "'Connect Meta' page to link your ad account."
    )
    st.stop()

metric = st.selectbox("Metric", ["spend", "impressions", "clicks", "ctr", "cpc", "cpm", "roas"])
daily = df.groupby("date", as_index=False)[metric].sum()

fig = px.line(daily, x="date", y=metric, title=f"Daily {metric}", markers=True)
fig.update_traces(line_color=OWN_BRAND_COLOR)
fig.update_layout(yaxis_title=metric, xaxis_title="")
st.plotly_chart(fig, use_container_width=True)

st.subheader("By campaign")
by_campaign = df.groupby("campaign_name", as_index=False)[metric].sum().sort_values(metric, ascending=False)
fig2 = px.bar(by_campaign, x=metric, y="campaign_name", orientation="h", color_discrete_sequence=[OWN_BRAND_COLOR])
fig2.update_layout(yaxis_title="", xaxis_title=metric)
st.plotly_chart(fig2, use_container_width=True)
