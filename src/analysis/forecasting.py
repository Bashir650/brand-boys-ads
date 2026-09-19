"""Lightweight forecasting for your own Meta Ads account performance.

Not a marketing-mix model - it's a trend projection (Holt-Winters, with a
plain linear-trend fallback for short/flat series) answering "if nothing
changes, where is spend/CTR/ROAS headed over the next week", using only what
the Marketing API insights already gave us. No external data, no LLM calls.
"""
from __future__ import annotations

import datetime
import logging

import numpy as np
import pandas as pd

from src.db.models import OwnAdInsight, Prediction

logger = logging.getLogger(__name__)

MIN_HISTORY_DAYS = 10
FORECAST_HORIZON_DAYS = 7
DEFAULT_METRICS = ["spend", "ctr", "roas", "cpm"]


def _load_daily_metric(session, metric: str) -> pd.Series:
    rows = session.query(OwnAdInsight.date, getattr(OwnAdInsight, metric)).all()
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rows, columns=["date", metric])
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df.groupby("date")[metric].sum().sort_index()


def _forecast_series(daily: pd.Series, horizon: int = FORECAST_HORIZON_DAYS) -> pd.DataFrame:
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        model = ExponentialSmoothing(
            daily.values, trend="add", seasonal=None, initialization_method="estimated"
        )
        fit = model.fit(optimized=True)
        forecast = fit.forecast(horizon)
        resid_std = float(np.std(fit.resid)) if len(fit.resid) else 0.0
    except Exception as exc:  # statsmodels can be finicky on short/flat series
        logger.info("Falling back to linear trend forecast (%s)", exc)
        x = np.arange(len(daily))
        coeffs = np.polyfit(x, daily.values, deg=1)
        future_x = np.arange(len(daily), len(daily) + horizon)
        forecast = np.polyval(coeffs, future_x)
        resid_std = float(np.std(daily.values - np.polyval(coeffs, x)))

    last_date = daily.index[-1]
    future_dates = [last_date + datetime.timedelta(days=i + 1) for i in range(horizon)]
    return pd.DataFrame(
        {
            "date": future_dates,
            "predicted": np.clip(forecast, a_min=0, a_max=None),
            "lower": np.clip(np.asarray(forecast) - 1.96 * resid_std, a_min=0, a_max=None),
            "upper": np.asarray(forecast) + 1.96 * resid_std,
        }
    )


def generate_forecasts(session, metrics: list[str] | None = None) -> int:
    metrics = metrics or DEFAULT_METRICS
    written = 0
    for metric in metrics:
        daily = _load_daily_metric(session, metric).dropna()
        if len(daily) < MIN_HISTORY_DAYS:
            logger.info(
                "Not enough history for %s yet (%d days, need %d)", metric, len(daily), MIN_HISTORY_DAYS
            )
            continue

        forecast_df = _forecast_series(daily)
        session.query(Prediction).filter_by(metric_name=metric, entity_type="account").delete()
        for _, row in forecast_df.iterrows():
            session.add(
                Prediction(
                    metric_name=metric,
                    entity_type="account",
                    entity_id="account",
                    forecast_date=row["date"],
                    predicted_value=float(row["predicted"]),
                    lower_bound=float(row["lower"]),
                    upper_bound=float(row["upper"]),
                    model_name="holt_winters_or_linear",
                )
            )
            written += 1
        session.commit()
    return written
