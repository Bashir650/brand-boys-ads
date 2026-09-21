import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np
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

# Metrics that are safe to sum directly (counts/currency). ctr/cpc/cpm/roas are
# ratios stored per ad/day by Meta - summing or averaging those across rows is
# meaningless (e.g. summing 2867 ads' CTR% gives a number >100%). They're
# recomputed below from the summed underlying totals instead.
ADDITIVE_METRICS = ["spend", "impressions", "clicks", "reach", "purchases", "purchase_value"]
RATIO_BASE_COLUMNS = ["spend", "impressions", "clicks", "purchase_value"]


def _aggregate(frame, group_col: str, metric: str):
    if metric in ADDITIVE_METRICS:
        return frame.groupby(group_col, as_index=False)[metric].sum()

    totals = frame.groupby(group_col, as_index=False)[RATIO_BASE_COLUMNS].sum()
    if metric == "ctr":
        totals[metric] = totals["clicks"] / totals["impressions"].replace(0, np.nan)
    elif metric == "cpc":
        totals[metric] = totals["spend"] / totals["clicks"].replace(0, np.nan)
    elif metric == "cpm":
        totals[metric] = totals["spend"] / totals["impressions"].replace(0, np.nan) * 1000
    elif metric == "roas":
        totals[metric] = totals["purchase_value"] / totals["spend"].replace(0, np.nan)
    return totals[[group_col, metric]]


min_date, max_date = df["date"].min().date(), df["date"].max().date()
st.caption(f"Data available: {min_date} to {max_date} ({df['date'].nunique()} days)")

date_range = st.date_input("Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
    df = df[(df["date"].dt.date >= start) & (df["date"].dt.date <= end)]

metric = st.selectbox("Metric", ADDITIVE_METRICS + ["ctr", "cpc", "cpm", "roas"])

col1, col2, col3, col4 = st.columns(4)
totals = df[RATIO_BASE_COLUMNS].sum()
col1.metric("Spend", f"{totals['spend']:,.0f}")
col2.metric(
    "CTR",
    f"{(totals['clicks'] / totals['impressions'] * 100):.2f}%" if totals["impressions"] else "-",
)
col3.metric(
    "CPM",
    f"{(totals['spend'] / totals['impressions'] * 1000):,.2f}" if totals["impressions"] else "-",
)
col4.metric(
    "ROAS",
    f"{(totals['purchase_value'] / totals['spend']):.2f}x" if totals["spend"] else "-",
)

daily = _aggregate(df, "date", metric)
fig = px.line(daily, x="date", y=metric, title=f"Daily {metric}", markers=True)
fig.update_traces(line_color=OWN_BRAND_COLOR)
fig.update_layout(yaxis_title=metric, xaxis_title="")
st.plotly_chart(fig, width='stretch')

st.subheader("By campaign")
by_campaign = _aggregate(df, "campaign_name", metric).sort_values(metric, ascending=False)
fig2 = px.bar(by_campaign, x=metric, y="campaign_name", orientation="h", color_discrete_sequence=[OWN_BRAND_COLOR])
fig2.update_layout(yaxis_title="", xaxis_title=metric)
st.plotly_chart(fig2, width='stretch')
