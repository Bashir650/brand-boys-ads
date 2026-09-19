"""Computes a 'is this creative winning' proxy score for competitor ads.

Meta's Ad Library API hides real spend/impressions for ordinary commercial
ads, so we combine two signals that ARE visible:
  - days_running: how long the ad has stayed live (advertisers pull losing
    ads quickly; long-running ads are usually working).
  - variant_count: how many near-duplicate copies of the same creative are
    running at once (a sign the advertiser is actively scaling it).
"""
from __future__ import annotations

import datetime
import logging

from src.analysis.dedupe import cluster_by_similarity
from src.db.models import MetaAd, WinningCreativeScore

logger = logging.getLogger(__name__)


def _days_running(ad: MetaAd) -> float:
    start = ad.ad_delivery_start_time
    if not start:
        return 0.0
    end = ad.ad_delivery_stop_time or datetime.datetime.utcnow()
    return max((end - start).total_seconds() / 86400, 0.0)


def compute_meta_competitor_scores(session, competitor) -> int:
    ads = session.query(MetaAd).filter_by(competitor_id=competitor.id).all()
    if not ads:
        return 0

    clusters = cluster_by_similarity(ads)
    variant_count_by_ad_id = {
        ad_id: cluster.variant_count for cluster in clusters for ad_id in cluster.member_ids
    }

    session.query(WinningCreativeScore).filter_by(
        competitor_id=competitor.id, source="meta_competitor"
    ).delete()

    written = 0
    for ad in ads:
        days = _days_running(ad)
        variants = variant_count_by_ad_id.get(ad.id, 1)
        # Tune these weights once you have real outcomes (e.g. sales lift on
        # your own copied variants) to calibrate against - this is a starting
        # heuristic, not a validated model.
        score = min(days, 90) * 0.6 + min(variants, 10) * 4
        rationale = f"Running {days:.0f} days; {variants} near-duplicate variant(s) seen"
        session.add(
            WinningCreativeScore(
                source="meta_competitor",
                competitor_id=competitor.id,
                ad_ref_id=ad.id,
                days_running=days,
                variant_count=variants,
                score=round(score, 1),
                rationale=rationale,
            )
        )
        written += 1

    session.commit()
    return written
