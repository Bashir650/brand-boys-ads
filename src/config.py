from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    meta_app_id: str = os.getenv("META_APP_ID", "")
    meta_app_secret: str = os.getenv("META_APP_SECRET", "")
    meta_access_token: str = os.getenv("META_ACCESS_TOKEN", "")
    meta_ad_account_id: str = os.getenv("META_AD_ACCOUNT_ID", "")
    meta_oauth_redirect_uri: str = os.getenv(
        "META_OAUTH_REDIRECT_URI", "http://localhost:8501/Connect_Meta"
    )
    graph_api_version: str = os.getenv("META_GRAPH_API_VERSION", "v19.0")
    ad_library_countries: list[str] = field(
        default_factory=lambda: [
            c.strip() for c in os.getenv("AD_LIBRARY_COUNTRIES", "US").split(",") if c.strip()
        ]
    )
    enable_tiktok: bool = _bool("ENABLE_TIKTOK_COLLECTOR", True)
    enable_google_transparency: bool = _bool("ENABLE_GOOGLE_TRANSPARENCY_COLLECTOR", False)
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'ads.db'}")


settings = Settings()


def load_competitors() -> list[dict]:
    path = BASE_DIR / "config" / "competitors.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("competitors", [])
