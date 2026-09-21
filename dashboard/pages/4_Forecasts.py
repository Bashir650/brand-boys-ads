import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.palette import OWN_BRAND_COLOR
from dashboard.utils import load_own_insights_df, load_predictions_df

st.set_page_config(page_title="Forecasts", layout="wide")
st.title("Forecasts")
st.caption(
    "A lightweight trend projection (Holt-Winters, linear-trend fallback) over your own "
    "account's daily metrics. Needs at least 10 days of history per metric - not a "
    "substitute for a real marketing-mix model, but useful for 'where is this headed "
    "if nothing changes'."
)

actuals = load_own_insights_df()
predictions = load_predictions_df()

if predictions.empty:
    st.info("No forecasts yet - the pipeline generates these once you have 10+ days of own-account data.")
    st.stop()

metric = st.selectbox("Metric", sorted(predictions["metric_name"].unique()))

actual_daily = (
    actuals.groupby("date", as_index=False)[metric].sum() if metric in actuals.columns else pd.DataFrame()
)
pred = predictions[predictions["metric_name"] == metric].sort_values("forecast_date")

fig = go.Figure()
if not actual_daily.empty:
    fig.add_trace(
        go.Scatter(
            x=actual_daily["date"],
            y=actual_daily[metric],
            mode="lines+markers",
            name="Actual",
            line=dict(color=OWN_BRAND_COLOR),
        )
    )
fig.add_trace(
    go.Scatter(
        x=pred["forecast_date"],
        y=pred["predicted_value"],
        mode="lines+markers",
        name="Forecast",
        line=dict(color="#D55E00", dash="dash"),
    )
)
fig.add_trace(
    go.Scatter(
        x=pd.concat([pred["forecast_date"], pred["forecast_date"][::-1]]),
        y=pd.concat([pred["upper_bound"], pred["lower_bound"][::-1]]),
        fill="toself",
        fillcolor="rgba(213,94,0,0.15)",
        line=dict(color="rgba(0,0,0,0)"),
        name="Confidence band",
    )
)
fig.update_layout(title=f"{metric}: actual vs forecast", yaxis_title=metric, xaxis_title="")
st.plotly_chart(fig, width='stretch')
