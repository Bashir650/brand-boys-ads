"""Groups near-identical ad creatives (same copy reused across many ad IDs,
countries, or date ranges) which, for ordinary commercial ads where Meta hides
spend and impressions, is the best available proxy for "this creative is
being scaled because it's winning".
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from rapidfuzz import fuzz

SIMILARITY_THRESHOLD = 85


@dataclass
class CreativeCluster:
    representative_text: str
    member_ids: list[str] = field(default_factory=list)

    @property
    def variant_count(self) -> int:
        return len(self.member_ids)


def cluster_by_exact_hash(ads: list) -> dict[str, list]:
    groups: dict[str, list] = defaultdict(list)
    for ad in ads:
        groups[ad.content_hash].append(ad)
    return groups


def cluster_by_similarity(ads: list, threshold: int = SIMILARITY_THRESHOLD) -> list[CreativeCluster]:
    """Cheap O(n^2) near-duplicate clustering on ad copy text. Fine for the ad
    volumes a handful of tracked competitors generate (low hundreds/thousands);
    swap for a vector-index approach if you track far more.
    """
    clusters: list[CreativeCluster] = []
    for ad in ads:
        text = (ad.ad_creative_body or "").strip()
        if not text:
            continue
        placed = False
        for cluster in clusters:
            if fuzz.token_sort_ratio(text, cluster.representative_text) >= threshold:
                cluster.member_ids.append(ad.id)
                placed = True
                break
        if not placed:
            clusters.append(CreativeCluster(representative_text=text, member_ids=[ad.id]))
    return clusters
