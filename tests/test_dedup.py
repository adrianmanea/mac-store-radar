"""Dedup clustering tests (M9.5) — pure app-set Jaccard clustering."""

from __future__ import annotations

from radar.pipeline.dedup import cluster_duplicates, jaccard


def test_jaccard():
    assert jaccard({1, 2, 3}, {1, 2, 3}) == 1.0
    assert jaccard({1, 2}, {3, 4}) == 0.0
    assert jaccard(set(), set()) == 0.0
    assert abs(jaccard({1, 2, 3}, {2, 3, 4}) - 0.5) < 1e-9


def test_clusters_same_appset_different_wording():
    # the whatsapp case: different keywords, same apps -> one cluster
    cands = [
        {"keyword": "whatsapp mac", "best_opportunity": 15.0, "app_ids": [1, 2, 3, 4]},
        {"keyword": "whatsapp macos", "best_opportunity": 9.0, "app_ids": [1, 2, 3, 4]},
        {"keyword": "whatsapp macbook", "best_opportunity": 11.0, "app_ids": [1, 2, 3]},
    ]
    clusters = cluster_duplicates(cands, threshold=0.6)
    assert len(clusters) == 1
    keeper, dupes = clusters[0]
    assert keeper == "whatsapp mac"  # highest opportunity is the keeper
    assert set(dupes) == {"whatsapp macos", "whatsapp macbook"}


def test_distinct_niches_not_merged():
    cands = [
        {"keyword": "pdf editor mac", "best_opportunity": 14.0, "app_ids": [1, 2, 3, 4]},
        {"keyword": "video converter mac", "best_opportunity": 12.0, "app_ids": [9, 8, 7, 6]},
    ]
    assert cluster_duplicates(cands, threshold=0.6) == []


def test_empty_appsets_skipped():
    cands = [
        {"keyword": "a mac", "best_opportunity": 5.0, "app_ids": []},
        {"keyword": "b mac", "best_opportunity": 4.0, "app_ids": None},
    ]
    assert cluster_duplicates(cands) == []


def test_partial_overlap_below_threshold_kept_separate():
    cands = [
        {"keyword": "screen recorder mac", "best_opportunity": 11.0, "app_ids": [1, 2, 3, 4, 5]},
        {"keyword": "screen capture mac", "best_opportunity": 9.0, "app_ids": [4, 5, 6, 7, 8]},
    ]
    # overlap {4,5}/union 8 = 0.25 < 0.6 -> distinct
    assert cluster_duplicates(cands, threshold=0.6) == []
