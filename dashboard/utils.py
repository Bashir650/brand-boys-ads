import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from src.db.base import Base, engine
from src.db.models import Competitor, MetaAd, OwnAdInsight, Prediction, TikTokAd, WinningCreativeScore
from src.db.session import get_session


@st.cache_resource
def db_session():
    # On a fresh deploy (e.g. Streamlit Cloud before the pipeline has ever run),
    # data/ads.db exists with no schema yet - create any missing tables so the
    # dashboard shows empty-state messages instead of crashing. No-op once the
    # pipeline (or scripts/init_db.py) has already created them.
    Base.metadata.create_all(engine)
    return get_session()


@st.cache_data(ttl=300)
def load_competitors_df() -> pd.DataFrame:
    session = db_session()
    rows = session.query(Competitor).all()
    return pd.DataFrame(
        [{"id": c.id, "name": c.name, "country": c.country, "is_own_brand": c.is_own_brand, "notes": c.notes} for c in rows]
    )


@st.cache_data(ttl=300)
def load_meta_ads_df() -> pd.DataFrame:
    session = db_session()
    rows = session.query(MetaAd).all()
    return pd.DataFrame(
        [
            {
                "id": a.id,
                "competitor_id": a.competitor_id,
                "page_name": a.page_name,
                "ad_creative_body": a.ad_creative_body,
                "ad_snapshot_url": a.ad_snapshot_url,
                "publisher_platforms": a.publisher_platforms,
                "ad_delivery_start_time": a.ad_delivery_start_time,
                "ad_delivery_stop_time": a.ad_delivery_stop_time,
                "last_seen_at": a.last_seen_at,
            }
            for a in rows
        ]
    )


@st.cache_data(ttl=300)
def load_tiktok_ads_df() -> pd.DataFrame:
    session = db_session()
    rows = session.query(TikTokAd).all()
    return pd.DataFrame(
        [
            {
                "id": a.id,
                "competitor_id": a.competitor_id,
                "brand_name": a.brand_name,
                "caption": a.caption,
                "video_url": a.video_url,
                "thumbnail_url": a.thumbnail_url,
                "likes": a.likes,
                "comments": a.comments,
                "shares": a.shares,
                "last_seen_at": a.last_seen_at,
            }
            for a in rows
        ]
    )


@st.cache_data(ttl=300)
def load_own_insights_df() -> pd.DataFrame:
    session = db_session()
    rows = session.query(OwnAdInsight).all()
    return pd.DataFrame(
        [
            {
                "date": r.date,
                "campaign_name": r.campaign_name,
                "adset_name": r.adset_name,
                "ad_name": r.ad_name,
                "spend": r.spend,
                "impressions": r.impressions,
                "clicks": r.clicks,
                "ctr": r.ctr,
                "cpc": r.cpc,
                "cpm": r.cpm,
                "roas": r.roas,
            }
            for r in rows
        ]
    )


@st.cache_data(ttl=300)
def load_predictions_df() -> pd.DataFrame:
    session = db_session()
    rows = session.query(Prediction).all()
    return pd.DataFrame(
        [
            {
                "metric_name": p.metric_name,
                "forecast_date": p.forecast_date,
                "predicted_value": p.predicted_value,
                "lower_bound": p.lower_bound,
                "upper_bound": p.upper_bound,
            }
            for p in rows
        ]
    )


@st.cache_data(ttl=300)
def load_winning_scores_df() -> pd.DataFrame:
    session = db_session()
    rows = session.query(WinningCreativeScore).all()
    return pd.DataFrame(
        [
            {
                "source": s.source,
                "competitor_id": s.competitor_id,
                "ad_ref_id": s.ad_ref_id,
                "days_running": s.days_running,
                "variant_count": s.variant_count,
                "score": s.score,
                "rationale": s.rationale,
            }
            for s in rows
        ]
    )
