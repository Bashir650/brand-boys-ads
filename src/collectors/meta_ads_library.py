"""Client for Meta's official, public Ad Library API (`/ads_archive`).

Docs: https://www.facebook.com/ads/library/api

IMPORTANT data limitation: for ordinary commercial ads (ad_type=ALL), Meta does
NOT expose spend or impressions - those fields are only populated for
POLITICAL_AND_ISSUE_ADS, and only in a handful of countries. There is no way
around this; it's a deliberate restriction on Meta's side. For commercial
competitor ads, treat "days running" and "how many near-duplicate variants are
live at once" as the performance proxy instead (see
src/analysis/winning_creative_score.py) rather than expecting real spend data.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import logging
import time

import requests

from src.config import settings
from src.db.models import MetaAd

logger = logging.getLogger(__name__)

GRAPH_URL_TMPL = "https://graph.facebook.com/{version}/ads_archive"

BASE_FIELDS = [
    "id",
    "ad_creation_time",
    "ad_creative_bodies",
    "ad_creative_link_captions",
    "ad_creative_link_titles",
    "ad_delivery_start_time",
    "ad_delivery_stop_time",
    "ad_snapshot_url",
    "page_id",
    "page_name",
    "publisher_platforms",
    "languages",
]

# Meta only allows requesting these when ad_type=POLITICAL_AND_ISSUE_ADS.
POLITICAL_ONLY_FIELDS = ["impressions", "spend", "demographic_distribution", "delivery_by_region"]


class MetaAdLibraryError(RuntimeError):
    pass


class MetaAdLibraryClient:
    def __init__(self, access_token: str | None = None, api_version: str | None = None):
        self.access_token = access_token or settings.meta_access_token
        self.api_version = api_version or settings.graph_api_version
        if not self.access_token:
            raise MetaAdLibraryError(
                "No Meta access token configured. Set META_ACCESS_TOKEN in .env, or run "
                "the 'Connect Meta' page in the dashboard / scripts/exchange_token.py first."
            )

    def search_ads(
        self,
        countries: list[str],
        search_terms: str | None = None,
        page_ids: list[str] | None = None,
        ad_type: str = "ALL",
        ad_active_status: str = "ALL",
        page_limit: int = 200,
        max_pages: int = 25,
    ) -> list[dict]:
        if not search_terms and not page_ids:
            raise MetaAdLibraryError("Provide search_terms and/or page_ids")

        fields = list(BASE_FIELDS)
        if ad_type == "POLITICAL_AND_ISSUE_ADS":
            fields += POLITICAL_ONLY_FIELDS

        params = {
            "access_token": self.access_token,
            "ad_reached_countries": json.dumps(countries),
            "ad_type": ad_type,
            "ad_active_status": ad_active_status,
            "fields": ",".join(fields),
            "limit": page_limit,
        }
        if search_terms:
            params["search_terms"] = search_terms
        if page_ids:
            params["search_page_ids"] = json.dumps(page_ids)

        url = GRAPH_URL_TMPL.format(version=self.api_version)
        results: list[dict] = []
        pages_fetched = 0

        while url and pages_fetched < max_pages:
            resp = requests.get(url, params=params if pages_fetched == 0 else None, timeout=30)
            if resp.status_code != 200:
                raise MetaAdLibraryError(f"Ad Library API error {resp.status_code}: {resp.text[:500]}")
            payload = resp.json()
            results.extend(payload.get("data", []))
            url = payload.get("paging", {}).get("next")
            pages_fetched += 1
            if url:
                time.sleep(0.3)  # be polite, avoid rate limiting

        logger.info(
            "Fetched %d ads (%d pages) for terms=%r page_ids=%r",
            len(results),
            pages_fetched,
            search_terms,
            page_ids,
        )
        return results


def _content_hash(body: str, title: str) -> str:
    normalized = "".join(ch.lower() for ch in f"{body}{title}" if ch.isalnum())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _parse_dt(value: str | None):
    if not value:
        return None
    return datetime.datetime.fromisoformat(value)


def sync_competitor_ads(session, competitor, client: MetaAdLibraryClient, countries: list[str]) -> int:
    raw_ads = client.search_ads(
        countries=countries,
        search_terms=competitor.meta_search_terms or None,
        page_ids=[competitor.meta_page_id] if competitor.meta_page_id else None,
    )
    now = datetime.datetime.utcnow()
    upserted = 0
    for raw in raw_ads:
        body = " ".join(raw.get("ad_creative_bodies") or [])
        title = " ".join(raw.get("ad_creative_link_titles") or [])
        caption = " ".join(raw.get("ad_creative_link_captions") or [])

        ad = session.get(MetaAd, raw["id"])
        if ad is None:
            ad = MetaAd(id=raw["id"], competitor_id=competitor.id, first_seen_at=now)
            session.add(ad)

        ad.competitor_id = competitor.id
        ad.page_id = raw.get("page_id")
        ad.page_name = raw.get("page_name")
        ad.ad_creative_body = body
        ad.ad_creative_link_title = title
        ad.ad_creative_link_caption = caption
        ad.ad_snapshot_url = raw.get("ad_snapshot_url")
        ad.publisher_platforms = ",".join(raw.get("publisher_platforms") or [])
        ad.ad_delivery_start_time = _parse_dt(raw.get("ad_delivery_start_time"))
        ad.ad_delivery_stop_time = _parse_dt(raw.get("ad_delivery_stop_time"))
        ad.languages = ",".join(raw.get("languages") or [])
        ad.content_hash = _content_hash(body, title)
        ad.last_seen_at = now
        upserted += 1

    session.commit()
    return upserted
