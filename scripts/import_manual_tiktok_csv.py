"""Fallback loader: import TikTok competitor ad data from a manually exported
CSV when the automated Creative Center collector is unavailable or blocked
(e.g. TikTok changed the endpoint - see src/collectors/tiktok_creative_center.py).

You can populate this CSV by hand from the public Creative Center UI, or by
exporting from a third-party ad-intelligence tool you already subscribe to
(e.g. PiPiADS, Minea).

Expected columns: competitor_name, ad_id, brand_name, video_url,
thumbnail_url, caption, likes, comments, shares

Usage: python scripts/import_manual_tiktok_csv.py path/to/file.csv
"""
import csv
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.models import Competitor, TikTokAd
from src.db.session import get_session


def main(csv_path: str):
    session = get_session()
    now = datetime.datetime.utcnow()
    imported = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            competitor = session.query(Competitor).filter_by(name=row["competitor_name"]).one_or_none()
            if competitor is None:
                print(f"Skipping unknown competitor: {row['competitor_name']}")
                continue

            ad = session.get(TikTokAd, row["ad_id"])
            if ad is None:
                ad = TikTokAd(id=row["ad_id"], competitor_id=competitor.id, first_seen_at=now)
                session.add(ad)

            ad.competitor_id = competitor.id
            ad.brand_name = row.get("brand_name")
            ad.video_url = row.get("video_url")
            ad.thumbnail_url = row.get("thumbnail_url")
            ad.caption = row.get("caption")
            ad.likes = int(row["likes"]) if row.get("likes") else None
            ad.comments = int(row["comments"]) if row.get("comments") else None
            ad.shares = int(row["shares"]) if row.get("shares") else None
            ad.last_seen_at = now
            imported += 1

    session.commit()
    print(f"Imported/updated {imported} TikTok ads.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/import_manual_tiktok_csv.py <path_to_csv>")
        sys.exit(1)
    main(sys.argv[1])
