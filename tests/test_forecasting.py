import datetime

import pandas as pd

from src.analysis.forecasting import _forecast_series


def test_forecast_series_returns_expected_horizon():
    dates = pd.date_range(end=datetime.date.today(), periods=20)
    series = pd.Series(range(20), index=dates.date)
    forecast = _forecast_series(series, horizon=7)
    assert len(forecast) == 7
    assert (forecast["predicted"] >= 0).all()


def test_forecast_series_handles_flat_line():
    dates = pd.date_range(end=datetime.date.today(), periods=15)
    series = pd.Series([5.0] * 15, index=dates.date)
    forecast = _forecast_series(series, horizon=5)
    assert len(forecast) == 5
