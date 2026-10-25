"""
Offline Recommendation Metrics Implementation.

Implements standard Top-K ranking, coverage, diversity, and novelty metrics:
- Precision@K
- Recall@K
- NDCG@K
- HitRate@K
- MAP@K
- Catalog Coverage@K
- Intra-List Diversity@K
- Novelty@K
- Latency percentiles (p50, p95)
"""

import math
from typing import Sequence
import numpy as np


def precision_at_k(recommended: Sequence[str], relevant: set[str], k: int) -> float:
    """
    Precision@K = (# of relevant items in top-K) / K
    """
    if k <= 0:
        return 0.0
    top_k = recommended[:k]
    hits = sum(1 for item in top_k if item in relevant)
    return hits / float(k)


def recall_at_k(recommended: Sequence[str], relevant: set[str], k: int) -> float:
    """
    Recall@K = (# of relevant items in top-K) / (total # of relevant items)
    Returns 0.0 if there are no relevant items.
    """
    if not relevant or k <= 0:
        return 0.0
    top_k = recommended[:k]
    hits = sum(1 for item in top_k if item in relevant)
    return hits / float(len(relevant))


def ndcg_at_k(recommended: Sequence[str], relevant: set[str], k: int) -> float:
    """
    Normalized Discounted Cumulative Gain at K with binary relevance.
    DCG@K = sum_{i=1}^{min(k, |rec|)} [ rel_i / log2(i + 1) ]
    IDCG@K = sum_{i=1}^{min(k, |rel|)} [ 1 / log2(i + 1) ]
    NDCG@K = DCG@K / IDCG@K
    """
    if not relevant or k <= 0:
        return 0.0

    top_k = recommended[:k]
    dcg = 0.0
    for i, item in enumerate(top_k, start=1):
        if item in relevant:
            dcg += 1.0 / math.log2(i + 1)

    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(k, len(relevant)) + 1))
    if idcg <= 0.0:
        return 0.0

    return dcg / idcg


def hit_rate_at_k(recommended: Sequence[str], relevant: set[str], k: int) -> float:
    """
    HitRate@K = 1.0 if at least one relevant item is in top-K, else 0.0.
    """
    if not relevant or k <= 0:
        return 0.0
    top_k = recommended[:k]
    for item in top_k:
        if item in relevant:
            return 1.0
    return 0.0


def map_at_k(recommended: Sequence[str], relevant: set[str], k: int) -> float:
    """
    Mean Average Precision at K (Average Precision for a single user).
    AP@K = (1 / min(K, |relevant|)) * sum_{i=1}^K [ Precision@i * rel_i ]
    """
    if not relevant or k <= 0:
        return 0.0

    top_k = recommended[:k]
    cum_hits = 0
    sum_prec = 0.0
    for i, item in enumerate(top_k, start=1):
        if item in relevant:
            cum_hits += 1
            sum_prec += cum_hits / float(i)

    denom = min(k, len(relevant))
    if denom == 0:
        return 0.0
    return sum_prec / float(denom)


def catalog_coverage_at_k(
    recommendations_by_user: dict[str, Sequence[str]],
    catalog_item_ids: set[str],
    k: int,
) -> float:
    """
    Catalog Coverage@K = (|Union_{u} Top-K(u)|) / |Catalog|
    """
    if not catalog_item_ids or not recommendations_by_user or k <= 0:
        return 0.0

    recommended_union: set[str] = set()
    for recs in recommendations_by_user.values():
        recommended_union.update(recs[:k])

    covered = len(recommended_union.intersection(catalog_item_ids))
    return covered / float(len(catalog_item_ids))


def intra_list_diversity_at_k(
    recommendations_by_user: dict[str, Sequence[str]],
    item_vectors: dict[str, np.ndarray],
    k: int,
) -> float:
    """
    Intra-List Diversity@K:
    Macro-average across users of the average pairwise cosine distance (1 - cos_sim)
    between all distinct item pairs in the user's top-K recommendation list.

    ILD(R) = (2 / (k * (k - 1))) * sum_{i < j} (1 - cos(v_i, v_j))
    """
    if not recommendations_by_user or k < 2:
        return 0.0

    user_ild_scores: list[float] = []

    for recs in recommendations_by_user.values():
        top_k = [item for item in recs[:k] if item in item_vectors]
        n_items = len(top_k)
        if n_items < 2:
            user_ild_scores.append(0.0)
            continue

        pair_distances: list[float] = []
        for i in range(n_items):
            v_i = item_vectors[top_k[i]]
            norm_i = np.linalg.norm(v_i)
            for j in range(i + 1, n_items):
                v_j = item_vectors[top_k[j]]
                norm_j = np.linalg.norm(v_j)
                if norm_i > 0 and norm_j > 0:
                    cos_sim = float(np.dot(v_i, v_j) / (norm_i * norm_j))
                    # Clamp numerical precision
                    cos_sim = max(-1.0, min(1.0, cos_sim))
                    dist = 1.0 - cos_sim
                else:
                    dist = 1.0
                pair_distances.append(dist)

        if pair_distances:
            user_ild_scores.append(float(np.mean(pair_distances)))
        else:
            user_ild_scores.append(0.0)

    return float(np.mean(user_ild_scores)) if user_ild_scores else 0.0


def novelty_at_k(
    recommendations_by_user: dict[str, Sequence[str]],
    item_interaction_counts: dict[str, int],
    total_interactions: int,
    k: int,
) -> float:
    """
    Novelty@K (Self-Information):
    Macro-average across users of the average self-information of recommended items.
    Self-Information(item) = -log2( P(item) )
    where P(item) = count(item) / total_interactions.
    """
    if not recommendations_by_user or total_interactions <= 0 or k <= 0:
        return 0.0

    user_novelty_scores: list[float] = []

    for recs in recommendations_by_user.values():
        top_k = recs[:k]
        if not top_k:
            continue

        item_novelties: list[float] = []
        for item in top_k:
            count = item_interaction_counts.get(item, 1)  # Laplace fallback for unseen items
            prob = max(1, count) / float(total_interactions)
            item_novelties.append(-math.log2(prob))

        if item_novelties:
            user_novelty_scores.append(float(np.mean(item_novelties)))

    return float(np.mean(user_novelty_scores)) if user_novelty_scores else 0.0


def compute_latency_percentiles(latencies_ms: Sequence[float]) -> dict[str, float]:
    """
    Compute p50 (median), p90, p95, and mean latency in milliseconds.
    """
    if not latencies_ms:
        return {"p50_ms": 0.0, "p90_ms": 0.0, "p95_ms": 0.0, "mean_ms": 0.0}

    arr = np.array(latencies_ms, dtype=np.float64)
    return {
        "p50_ms": float(np.percentile(arr, 50)),
        "p90_ms": float(np.percentile(arr, 90)),
        "p95_ms": float(np.percentile(arr, 95)),
        "mean_ms": float(np.mean(arr)),
    }
