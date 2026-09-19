"""One-time OAuth connect flow for your own Meta Ads account.

You do this once (via the dashboard's "Connect Meta" page, or
scripts/exchange_token.py for a fully manual path) to get a long-lived
(~60 day) access token saved locally. The scheduled pipeline then refreshes
your own account's performance data on its own via the Marketing API - no
re-auth, and no chat/LLM tokens involved in that recurring update.
"""
from __future__ import annotations

import json
import time

import requests

from src.config import BASE_DIR, settings

TOKEN_STORE_PATH = BASE_DIR / "secrets" / "meta_token.json"

DEFAULT_SCOPES = ["ads_read", "ads_management", "business_management"]


def build_authorize_url(scopes: list[str] | None = None) -> str:
    scopes = scopes or DEFAULT_SCOPES
    return (
        f"https://www.facebook.com/{settings.graph_api_version}/dialog/oauth"
        f"?client_id={settings.meta_app_id}"
        f"&redirect_uri={settings.meta_oauth_redirect_uri}"
        f"&scope={','.join(scopes)}"
        f"&response_type=code"
    )


def exchange_code_for_token(code: str) -> dict:
    resp = requests.get(
        f"https://graph.facebook.com/{settings.graph_api_version}/oauth/access_token",
        params={
            "client_id": settings.meta_app_id,
            "client_secret": settings.meta_app_secret,
            "redirect_uri": settings.meta_oauth_redirect_uri,
            "code": code,
        },
        timeout=30,
    )
    resp.raise_for_status()
    short_lived = resp.json()
    return exchange_for_long_lived_token(short_lived["access_token"])


def exchange_for_long_lived_token(short_lived_token: str) -> dict:
    resp = requests.get(
        f"https://graph.facebook.com/{settings.graph_api_version}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": settings.meta_app_id,
            "client_secret": settings.meta_app_secret,
            "fb_exchange_token": short_lived_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    data["obtained_at"] = int(time.time())
    save_token(data)
    return data


def save_token(data: dict) -> None:
    TOKEN_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_STORE_PATH.write_text(json.dumps(data, indent=2))


def load_token() -> dict | None:
    if not TOKEN_STORE_PATH.exists():
        return None
    return json.loads(TOKEN_STORE_PATH.read_text())


def current_access_token() -> str | None:
    token = load_token()
    if token:
        return token.get("access_token")
    return settings.meta_access_token or None
