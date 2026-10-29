"""
Maximum Marginal Relevance (MMR) Re-ranking Module.

Implements diversity-aware re-ranking on top of TF-IDF v1.1 recommendation
scores using the standard MMR objective:

    MMR(i) = λ × Relevance(i) − (1 − λ) × max_j∈S Similarity(i, j)

where:
    - Relevance(i) is the cosine similarity between user profile and item i
    - Similarity(i, j) is the cosine similarity between items i and j
    - S is the set of already-selected items
    - λ ∈ [0, 1] controls the relevance–diversity trade-off

When λ = 1.0, MMR degenerates to pure relevance ranking (equivalence control).
When λ = 0.0, MMR selects items maximally dissimilar from those already chosen.

References:
    Carbonell & Goldstein (1998). "The use of MMR, diversity-based reranking
    for reordering documents and producing summaries."
"""

import numpy as np
from typing import Sequence


def mmr_rerank(
    candidate_ids: Sequence[str],
    candidate_scores: Sequence[float],
    item_vectors: dict[str, np.ndarray],
    select_n: int,
    lambda_param: float = 0.5,
) -> list[tuple[str, float]]:
    """
    Re-rank candidates using Maximum Marginal Relevance.

    Args:
        candidate_ids: Ordered list of candidate movie IDs (pre-filtered, no excluded items).
        candidate_scores: Corresponding relevance scores (cosine similarity to user profile).
        item_vectors: Dict mapping movie_id -> dense TF-IDF vector (1D numpy array).
        select_n: Number of items to select via MMR.
        lambda_param: Trade-off parameter. 1.0 = pure relevance, 0.0 = pure diversity.

    Returns:
        List of (movie_id, mmr_score) tuples, ordered by MMR selection order.
        The mmr_score is the MMR objective value at the time of selection.

    Determinism:
        - Ties in MMR score are broken by higher relevance score, then by
          ascending movie_id (numeric if possible).
        - This ensures identical outputs across runs given identical inputs.

    Edge cases:
        - Empty candidates → empty result.
        - select_n > len(candidates) → returns all candidates in MMR order.
        - Items missing from item_vectors → treated as zero vectors (max diversity).
        - λ = 1.0 → reproduces pure relevance ordering (with deterministic ties).
    """
    n_candidates = len(candidate_ids)
    if n_candidates == 0 or select_n <= 0:
        return []

    actual_n = min(select_n, n_candidates)

    # Build parallel arrays for efficient computation
    ids = list(candidate_ids)
    rel_scores = np.array(candidate_scores, dtype=np.float64)

    # Pre-extract vectors, handling missing items gracefully
    # Determine vector dimensionality from first available vector
    vec_dim = 0
    for mid in ids:
        if mid in item_vectors:
            vec_dim = len(item_vectors[mid])
            break

    if vec_dim == 0:
        # No vectors available at all — fall back to pure relevance ranking
        sorted_indices = _argsort_deterministic(ids, rel_scores, rel_scores)
        result = [(ids[i], float(rel_scores[i])) for i in sorted_indices[:actual_n]]
        return result

    # Build the candidate vector matrix (n_candidates × vec_dim)
    cand_vectors = np.zeros((n_candidates, vec_dim), dtype=np.float64)
    for i, mid in enumerate(ids):
        if mid in item_vectors:
            cand_vectors[i] = item_vectors[mid]

    # Pre-compute L2 norms for cosine similarity
    cand_norms = np.linalg.norm(cand_vectors, axis=1)
    # Avoid division by zero
    cand_norms_safe = np.where(cand_norms > 0, cand_norms, 1.0)

    # Normalize relevance scores to [0, 1] range for consistent MMR computation
    rel_max = np.max(rel_scores) if len(rel_scores) > 0 else 1.0
    rel_min = np.min(rel_scores) if len(rel_scores) > 0 else 0.0
    if rel_max > rel_min:
        rel_normalized = (rel_scores - rel_min) / (rel_max - rel_min)
    else:
        rel_normalized = np.ones_like(rel_scores)

    # Greedy MMR selection
    selected_indices: list[int] = []
    selected_mmr_scores: list[float] = []
    remaining = set(range(n_candidates))

    for step in range(actual_n):
        best_idx = -1
        best_mmr = -np.inf
        best_rel = -np.inf  # tie-breaker 1: higher raw relevance
        best_id_key = ""    # tie-breaker 2: lower movie_id

        for i in remaining:
            # Relevance component
            relevance = rel_normalized[i]

            # Diversity component: max similarity to any already-selected item
            if selected_indices:
                # Compute cosine similarity between candidate i and all selected items
                max_sim = _max_cosine_sim_to_selected(
                    cand_vectors[i], cand_norms[i],
                    cand_vectors, cand_norms_safe,
                    selected_indices,
                )
            else:
                max_sim = 0.0

            mmr_score = lambda_param * relevance - (1.0 - lambda_param) * max_sim

            # Deterministic tie-breaking
            id_key = (int(ids[i]) if ids[i].isdigit() else ids[i])

            if (mmr_score > best_mmr + 1e-12 or
                (abs(mmr_score - best_mmr) <= 1e-12 and rel_scores[i] > best_rel + 1e-12) or
                (abs(mmr_score - best_mmr) <= 1e-12 and abs(rel_scores[i] - best_rel) <= 1e-12 and
                 _id_less_than(id_key, best_id_key))):
                best_idx = i
                best_mmr = mmr_score
                best_rel = rel_scores[i]
                best_id_key = id_key

        if best_idx < 0:
            break

        selected_indices.append(best_idx)
        selected_mmr_scores.append(float(best_mmr))
        remaining.discard(best_idx)

    return [(ids[i], s) for i, s in zip(selected_indices, selected_mmr_scores)]


def _max_cosine_sim_to_selected(
    vec_i: np.ndarray,
    norm_i: float,
    all_vectors: np.ndarray,
    all_norms_safe: np.ndarray,
    selected_indices: list[int],
) -> float:
    """Compute max cosine similarity between vec_i and each selected item."""
    if norm_i <= 0:
        return 0.0

    max_sim = -1.0
    for j in selected_indices:
        dot = float(np.dot(vec_i, all_vectors[j]))
        sim = dot / (norm_i * all_norms_safe[j])
        # Clamp to [-1, 1] for numerical stability
        sim = max(-1.0, min(1.0, sim))
        if sim > max_sim:
            max_sim = sim

    return max(0.0, max_sim)  # Clamp negative similarities to 0


def _id_less_than(a, b) -> bool:
    """Compare IDs for deterministic tie-breaking (ascending)."""
    if b == "":
        return True
    if isinstance(a, int) and isinstance(b, int):
        return a < b
    return str(a) < str(b)


def _argsort_deterministic(
    ids: list[str],
    primary_scores: np.ndarray,
    secondary_scores: np.ndarray,
) -> list[int]:
    """Sort indices by descending primary score, then descending secondary, then ascending ID."""
    indices = list(range(len(ids)))
    indices.sort(key=lambda i: (
        -primary_scores[i],
        -secondary_scores[i],
        int(ids[i]) if ids[i].isdigit() else ids[i],
    ))
    return indices

