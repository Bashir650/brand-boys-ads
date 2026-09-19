"""One-off manual helper: paste a short-lived User Access Token generated from
the Graph API Explorer (https://developers.facebook.com/tools/explorer,
select your app + ads_read/ads_management scopes) and this exchanges it for a
long-lived (~60 day) token, saved to secrets/meta_token.json.

Prefer the dashboard's "Connect Meta" page for a one-click OAuth flow - use
this script only if you'd rather not go through the browser redirect.

Usage: python scripts/exchange_token.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.auth.meta_oauth import exchange_for_long_lived_token


def main():
    token = input("Paste short-lived access token: ").strip()
    result = exchange_for_long_lived_token(token)
    print("Saved long-lived token to secrets/meta_token.json")
    print("Expires in (seconds):", result.get("expires_in"))


if __name__ == "__main__":
    main()
