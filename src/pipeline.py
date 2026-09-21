"""Scheduled entry point - pulls fresh data via the official/best-effort APIs
and recomputes analysis. Meant to run on a cron (see
.github/workflows/update_data.yml) or manually with `python -m src.pipeline`.
This never calls any AI/LLM model - it's plain API calls + Python.
"""
from __future__ import annotations

import logging
import os

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


def run_meta_competitor_pull(session, competitors: list[Competitor]) -> int | None:
    """Returns the number of ads synced, or None if the pull was skipped
    entirely (e.g. no access token configured) - distinct from 0, which
    means it ran but the Ad Library genuinely had nothing to return."""
    try:
        client = MetaAdLibraryClient()
    except Exception as exc:
        logger.warning("Skipping Meta Ad Library pull: %s", exc)
        return None

    total = 0
    for competitor in competitors:
        if competitor.is_own_brand or not (competitor.meta_page_id or competitor.meta_search_terms):
            continue
        try:
            count = sync_competitor_ads(session, competitor, client, settings.ad_library_countries)
            logger.info("Synced %d Meta Ad Library ads for %s", count, competitor.name)
            total += count
        except Exception:
            logger.exception("Meta Ad Library sync failed for %s", competitor.name)
    return total


def run_tiktok_pull(session, competitors: list[Competitor]) -> int | None:
    """Returns ads synced, or None if the collector is disabled entirely."""
    if not settings.enable_tiktok:
        logger.info("TikTok collector disabled (ENABLE_TIKTOK_COLLECTOR=false)")
        return None
    total = 0
    for competitor in competitors:
        if competitor.is_own_brand:
            continue
        try:
            count = sync_competitor_tiktok_ads(session, competitor)
            total += count
            if count:
                logger.info("Synced %d TikTok ads for %s", count, competitor.name)
        except Exception:
            logger.exception("TikTok sync failed for %s", competitor.name)
    return total


def run_own_account_pull(session) -> int | None:
    """Returns insight rows synced, or None if skipped (no token/account id,
    or the sync itself failed)."""
    try:
        client = MetaMarketingClient()
    except Exception as exc:
        logger.warning("Skipping own Meta Ads account pull: %s", exc)
        return None
    try:
        count = sync_own_insights(session, client)
        logger.info("Synced %d rows of own ad account insights", count)
        return count
    except Exception:
        logger.exception("Own ad account sync failed")
        return None


def run_analysis(session, competitors: list[Competitor]) -> int:
    """Returns the number of forecast rows generated."""
    for competitor in competitors:
        if competitor.is_own_brand:
            continue
        try:
            compute_meta_competitor_scores(session, competitor)
        except Exception:
            logger.exception("Winning-creative scoring failed for %s", competitor.name)
    try:
        return generate_forecasts(session)
    except Exception:
        logger.exception("Forecast generation failed")
        return 0


def _in_github_actions() -> bool:
    return os.getenv("GITHUB_ACTIONS") == "true"


def _gh_warning(message: str) -> None:
    # ::warning:: is a GitHub Actions workflow command - it puts a visible
    # yellow annotation directly on the run page, not just in the raw log,
    # so a missing secret is impossible to miss without opening logs.
    if _in_github_actions():
        print(f"::warning::{message}")
    logger.warning(message)


def _summary_line(label: str, value: int | None, skip_reason: str) -> str:
    if value is None:
        return f"- {label}: **skipped** ({skip_reason})"
    return f"- {label}: {value}"


def _report_summary(
    *, competitor_count: int, meta_ads: int | None, tiktok_ads: int | None, own_insights: int | None, forecasts: int
) -> None:
    lines = [
        "## Ads pipeline summary",
        f"- Competitors tracked: {competitor_count}",
        _summary_line("Meta Ad Library ads pulled", meta_ads, "META_ACCESS_TOKEN not configured"),
        _summary_line("TikTok ads pulled", tiktok_ads, "ENABLE_TIKTOK_COLLECTOR is false"),
        _summary_line(
            "Own ad account insight rows pulled",
            own_insights,
            "META_ACCESS_TOKEN and/or META_AD_ACCOUNT_ID not configured",
        ),
        f"- Forecasts generated: {forecasts}",
    ]
    logger.info("\n".join(lines))

    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    if meta_ads is None:
        _gh_warning(
            "Meta Ad Library pull was skipped - no META_ACCESS_TOKEN. The dashboard's "
            "'Competitor Ads Library' page will stay empty until the META_ACCESS_TOKEN "
            "repository secret is set (Settings -> Secrets and variables -> Actions). "
            "See DEPLOYMENT.md."
        )
    if own_insights is None:
        _gh_warning(
            "Own ad account pull was skipped - META_ACCESS_TOKEN and/or "
            "META_AD_ACCOUNT_ID are missing. 'Our Meta Performance' and 'Forecasts' "
            "will stay empty until both repository secrets are set."
        )


def main() -> None:
    Base.metadata.create_all(engine)
    session = get_session()
    try:
        competitors = ensure_competitors_synced(session)
        meta_ads = run_meta_competitor_pull(session, competitors)
        tiktok_ads = run_tiktok_pull(session, competitors)
        own_insights = run_own_account_pull(session)
        forecasts = run_analysis(session, competitors)
        _report_summary(
            competitor_count=len(competitors),
            meta_ads=meta_ads,
            tiktok_ads=tiktok_ads,
            own_insights=own_insights,
            forecasts=forecasts,
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
