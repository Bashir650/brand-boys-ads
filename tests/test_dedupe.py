from types import SimpleNamespace

from src.analysis.dedupe import cluster_by_similarity


def _ad(id_, body):
    return SimpleNamespace(id=id_, ad_creative_body=body)


def test_identical_text_clusters_together():
    ads = [_ad("a", "Buy our shoes now, 50% off"), _ad("b", "Buy our shoes now, 50% off!!")]
    clusters = cluster_by_similarity(ads)
    assert len(clusters) == 1
    assert clusters[0].variant_count == 2


def test_distinct_ads_stay_separate():
    ads = [_ad("a", "Buy our shoes now"), _ad("b", "Free shipping on all backpacks today")]
    clusters = cluster_by_similarity(ads)
    assert len(clusters) == 2


def test_empty_body_is_ignored():
    ads = [_ad("a", ""), _ad("b", "Real ad copy here")]
    clusters = cluster_by_similarity(ads)
    assert len(clusters) == 1
    assert clusters[0].member_ids == ["b"]
