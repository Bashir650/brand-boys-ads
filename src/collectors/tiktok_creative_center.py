"""Best-effort client for TikTok's public Creative Center "Top Ads" data.

IMPORTANT: unlike Meta, TikTok has not published an official, documented API
for searching arbitrary competitors' ads. This module talks to the same
internal endpoint the public Creative Center website
(https://ads.tiktok.com/business/creativecenter) uses to render its "Top Ads"
dashboard, which is viewable with no login. Because it's unofficial:

  - The URL, payload shape and response fields below are a best guess based on
    the site's public behavior and MAY need adjusting (open the Creative
    Center in a browser, inspect the Network tab for the current
    `top_ads` / `creative_radar_api` request, and update TOP_ADS_URL / the
    payload / the field names below to match).
  - It can break without notice if TikTok changes the endpoint.
  - Automated requests to it may fall outside TikTok's Terms of Service -
    review those terms for your use case (and consider TikTok's official
    Business/Marketing API at https://business-api.tiktok.com if you can get
    partner access) before running this at scale.

This is why it's gated behind ENABLE_TIKTOK_COLLECTOR (default on, but fails
soft: a broken endpoint logs a warning and the rest of the pipeline keeps
going) and why scripts/import_manual_tiktok_csv.py exists as a manual fallback.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import logging

import requests

from src.db.models import TikTokAd

logger = logging.getLogger(__name__)

TOP_ADS_URL = "https://ads.tiktok.com/creative_radar_api/v1/top_ads/list"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; brand-boys-ads-research-bot/1.0)",
    "Content-Type": "application/json",
}


class TikTokCollectorError(RuntimeError):
    pass


def fetch_top_ads(
    keyword: str,
    country_code: str = "IN",
    period_days: int = 30,
    page: int = 1,
    page_size: int = 20,
) -> list[dict]:
    payload = {
        "page": page,
        "limit": page_size,
        "period": period_days,
        "country_code": country_code,
        "keyword": keyword,
    }
    try:
        resp = requests.post(TOP_ADS_URL, json=payload, headers=DEFAULT_HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise TikTokCollectorError(
            "TikTok Creative Center request failed - the unofficial endpoint may have "
            f"changed shape. See this module's docstring. Original error: {exc}"
        ) from exc

    return (data.get("data") or {}).get("materials", [])


def sync_competitor_tiktok_ads(session, competitor, country_code: str = "IN") -> int:
    if not competitor.tiktok_handle:
        return 0

    try:
        materials = fetch_top_ads(keyword=competitor.tiktok_handle, country_code=country_code)
    except TikTokCollectorError as exc:
        logger.warning("Skipping TikTok sync for %s: %s", competitor.name, exc)
        return 0

    now = datetime.datetime.utcnow()
    upserted = 0
    for item in materials:
        ad_id = str(
            item.get("id")
            or item.get("ad_id")
            or hashlib.sha1(json.dumps(item, sort_keys=True).encode()).hexdigest()
        )
        video_info = item.get("video_info") if isinstance(item.get("video_info"), dict) else {}

        ad = session.get(TikTokAd, ad_id)
        if ad is None:
            ad = TikTokAd(id=ad_id, competitor_id=competitor.id, first_seen_at=now)
            session.add(ad)

        ad.competitor_id = competitor.id
        ad.brand_name = item.get("brand_name") or competitor.name
        ad.video_url = video_info.get("video_url")
        ad.thumbnail_url = video_info.get("cover")
        ad.caption = item.get("ad_title") or item.get("title")
        ad.likes = item.get("like") or item.get("likes")
        ad.comments = item.get("comment") or item.get("comments")
        ad.shares = item.get("share") or item.get("shares")
        ad.metrics_json = json.dumps(item)
        ad.last_seen_at = now
        upserted += 1

    session.commit()
    return upserted
