"""Client for Meta's Marketing API `/insights` endpoint, used to pull YOUR OWN
connected ad account's real performance (spend, CTR, ROAS, etc.) - unlike the
Ad Library, this data is fully available because it's your own account.
"""
from __future__ import annotations

import datetime
import logging

import requests

from src.config import settings
from src.db.models import OwnAdInsight

logger = logging.getLogger(__name__)

GRAPH_URL_TMPL = "https://graph.facebook.com/{version}/{ad_account_id}/insights"

FIELDS = [
    "campaign_id",
    "campaign_name",
    "adset_id",
    "adset_name",
    "ad_id",
    "ad_name",
    "spend",
    "impressions",
    "clicks",
    "ctr",
    "cpc",
    "cpm",
    "reach",
    "frequency",
    "actions",
    "action_values",
]

PURCHASE_ACTION_TYPES = {"omni_purchase", "purchase", "offsite_conversion.fb_pixel_purchase"}


class MetaMarketingError(RuntimeError):
    pass


class MetaMarketingClient:
    def __init__(self, access_token: str | None = None, ad_account_id: str | None = None, api_version: str | None = None):
        self.access_token = access_token or settings.meta_access_token
        self.ad_account_id = ad_account_id or settings.meta_ad_account_id
        self.api_version = api_version or settings.graph_api_version
        if not self.access_token or not self.ad_account_id:
            raise MetaMarketingError("META_ACCESS_TOKEN and META_AD_ACCOUNT_ID must both be configured")

    def fetch_daily_insights(self, days_back: int = 30) -> list[dict]:
        until = datetime.date.today()
        since = until - datetime.timedelta(days=days_back)
        url = GRAPH_URL_TMPL.format(version=self.api_version, ad_account_id=self.ad_account_id)
        params = {
            "access_token": self.access_token,
            "level": "ad",
            "fields": ",".join(FIELDS),
            "time_range": f'{{"since":"{since.isoformat()}","until":"{until.isoformat()}"}}',
            "time_increment": 1,
            "limit": 500,
        }
        results: list[dict] = []
        while url:
            # Ad-level daily insights over a full month can take Meta noticeably
            # longer to compute server-side than most Graph API calls - 30s was
            # too tight and caused ReadTimeout on real accounts. 120s gives it
            # room; this still fails loudly (caught by run_own_account_pull)
            # rather than hanging indefinitely.
            resp = requests.get(url, params=params if not results else None, timeout=120)
            if resp.status_code != 200:
                raise MetaMarketingError(f"Marketing API error {resp.status_code}: {resp.text[:500]}")
            payload = resp.json()
            results.extend(payload.get("data", []))
            url = payload.get("paging", {}).get("next")
        logger.info("Fetched %d daily insight rows", len(results))
        return results


def _extract_action_value(actions: list[dict] | None, action_types: set[str]) -> float:
    if not actions:
        return 0.0
    return sum(float(a.get("value", 0)) for a in actions if a.get("action_type") in action_types)


def sync_own_insights(session, client: MetaMarketingClient, days_back: int = 30) -> int:
    rows = client.fetch_daily_insights(days_back=days_back)
    upserted = 0
    for row in rows:
        row_date = datetime.datetime.strptime(row["date_start"], "%Y-%m-%d")
        purchases = _extract_action_value(row.get("actions"), PURCHASE_ACTION_TYPES)
        purchase_value = _extract_action_value(row.get("action_values"), PURCHASE_ACTION_TYPES)
        spend = float(row.get("spend") or 0)

        insight = (
            session.query(OwnAdInsight).filter_by(ad_id=row.get("ad_id"), date=row_date).one_or_none()
        )
        is_new = insight is None
        if is_new:
            insight = OwnAdInsight(ad_id=row.get("ad_id"), date=row_date)

        insight.ad_account_id = client.ad_account_id
        insight.campaign_id = row.get("campaign_id")
        insight.campaign_name = row.get("campaign_name")
        insight.adset_id = row.get("adset_id")
        insight.adset_name = row.get("adset_name")
        insight.ad_name = row.get("ad_name")
        insight.spend = spend
        insight.impressions = float(row.get("impressions") or 0)
        insight.clicks = float(row.get("clicks") or 0)
        insight.ctr = float(row.get("ctr") or 0)
        insight.cpc = float(row.get("cpc") or 0)
        insight.cpm = float(row.get("cpm") or 0)
        insight.reach = float(row.get("reach") or 0)
        insight.frequency = float(row.get("frequency") or 0)
        insight.purchases = purchases
        insight.purchase_value = purchase_value
        insight.roas = (purchase_value / spend) if spend > 0 else None

        if is_new:
            session.add(insight)
        upserted += 1

    session.commit()
    return upserted
