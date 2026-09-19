"""Scheduled entry point - pulls fresh data via the official/best-effort APIs
and recomputes analysis. Meant to run on a cron (see
.github/workflows/update_data.yml) or manually with `python -m src.pipeline`.
This never calls any AI/LLM model - it's plain API calls + Python.
"""
from __future__ import annotations

import logging

from src.analysis.forecasting import generate_forecasts
from src.analysis.winning_creative_score import compute_meta_competitor_scores
from src.collectors.meta_ads_library import MetaAdLibraryClient, sync_competitor_ads
from src.collectors.meta_own_account import MetaMarketingClient, sync_own_insights
from src.collectors.tiktok_creative_center import sync_competitor_tiktok_ads
from src.config import load_competitors, settings
from src.db.base import Base, engine
from src.db.models import Competitor
from src.db.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def ensure_competitors_synced(session) -> list[Competitor]:
    configured = load_competitors()
    result = []
    for entry in configured:
        competitor = session.query(Competitor).filter_by(name=entry["name"]).one_or_none()
        if competitor is None:
            competitor = Competitor(name=entry["name"])
            session.add(competitor)
        competitor.meta_page_id = entry.get("meta_page_id") or None
        competitor.meta_search_terms = entry.get("meta_search_terms") or None
        competitor.tiktok_handle = entry.get("tiktok_handle") or None
        competitor.country = entry.get("country", "US")
        competitor.is_own_brand = bool(entry.get("is_own_brand", False))
        competitor.notes = entry.get("notes")
        result.append(competitor)
    session.commit()
    return result


def run_meta_competitor_pull(session, competitors: list[Competitor]) -> None:
    try:
        client = MetaAdLibraryClient()
    except Exception as exc:
        logger.warning("Skipping Meta Ad Library pull: %s", exc)
        return

    for competitor in competitors:
        if competitor.is_own_brand or not (competitor.meta_page_id or competitor.meta_search_terms):
            continue
        try:
            count = sync_competitor_ads(session, competitor, client, settings.ad_library_countries)
            logger.info("Synced %d Meta Ad Library ads for %s", count, competitor.name)
        except Exception:
            logger.exception("Meta Ad Library sync failed for %s", competitor.name)


def run_tiktok_pull(session, competitors: list[Competitor]) -> None:
    if not settings.enable_tiktok:
        logger.info("TikTok collector disabled (ENABLE_TIKTOK_COLLECTOR=false)")
        return
    for competitor in competitors:
        if competitor.is_own_brand:
            continue
        try:
            count = sync_competitor_tiktok_ads(session, competitor)
            if count:
                logger.info("Synced %d TikTok ads for %s", count, competitor.name)
        except Exception:
            logger.exception("TikTok sync failed for %s", competitor.name)


def run_own_account_pull(session) -> None:
    try:
        client = MetaMarketingClient()
    except Exception as exc:
        logger.warning("Skipping own Meta Ads account pull: %s", exc)
        return
    try:
        count = sync_own_insights(session, client)
        logger.info("Synced %d rows of own ad account insights", count)
    except Exception:
        logger.exception("Own ad account sync failed")


def run_analysis(session, competitors: list[Competitor]) -> None:
    for competitor in competitors:
        if competitor.is_own_brand:
            continue
        try:
            compute_meta_competitor_scores(session, competitor)
        except Exception:
            logger.exception("Winning-creative scoring failed for %s", competitor.name)
    try:
        generate_forecasts(session)
    except Exception:
        logger.exception("Forecast generation failed")


def main() -> None:
    Base.metadata.create_all(engine)
    session = get_session()
    try:
        competitors = ensure_competitors_synced(session)
        run_meta_competitor_pull(session, competitors)
        run_tiktok_pull(session, competitors)
        run_own_account_pull(session)
        run_analysis(session, competitors)
    finally:
        session.close()


if __name__ == "__main__":
    main()
