"""
Offline Evaluation Adapter and Phase 8B Experiment Runner for Semantic Embeddings
and Metadata Quality Ablation.

Evaluates:
  1. Condition A (Original MovieLens Metadata — 9,742 movies, 587 active test users):
     - ``tfidf_v1_1``: TF-IDF v1.1 baseline
     - ``tfidf_v1_1_mmr_05``: TF-IDF v1.1 + MMR (λ=0.5, pool=100)
     - ``tfidf_v1_1_mmr_07``: TF-IDF v1.1 + MMR (λ=0.7, pool=100)
     - ``semantic_en``: English Semantic Embeddings (`all-MiniLM-L6-v2`)
     - ``semantic_multi``: Multilingual Semantic Embeddings (`paraphrase-multilingual-MiniLM-L12-v2`)
     - ``semantic_en_mmr_05``: English Semantic Embeddings + MMR (λ=0.5, pool=100)
     - ``semantic_en_mmr_07``: English Semantic Embeddings + MMR (λ=0.7, pool=100)
  2. Condition B (Approved Phase 8A Enriched Metadata — 2×2 Ablation Matrix):
     - Protocol B1: Full 9,742-movie catalog with approved Phase 8A enrichment
       applied to the 11 matched MovieLens movies via `links.csv` (`tmdbId`).
     - Protocol B2: Matched 11-movie enriched subset, reporting exact user/item
       sample sizes and explicit ``NOT ENOUGH EVIDENCE`` status when statistical
       power is insufficient for confirmatory claims.
  3. Paired Statistical Significance & Effect Size Analysis:
     - Paired t-test, Wilcoxon signed-rank test, 1000-resample 95% bootstrap CI,
       Cohen's d effect size, and per-user Win / Tie / Loss counts.
  4. Operational Cost & Latency Benchmarks:
     - Batch embedding generation time, cache load time, storage footprint,
       peak memory usage, per-user p50/p95 recommendation latency, cold-start
       latency, and missing-vector / fallback rates.
"""

from __future__ import annotations

from collections import Counter
import copy
import csv
from dataclasses import dataclass
import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Any, Literal, Sequence

import numpy as np
from scipy import stats

from ..services.metadata_enrichment_benchmark import _build_mock_tmdb_catalog
from ..services.recommendation.embedding_cache import (
    DEFAULT_EMBEDDING_CACHE_DIR,
    EmbeddingArtifact,
    find_latest_artifact,
    save_embedding_artifact,
)
from ..services.recommendation.embeddings import (
    SentenceEncoderProtocol,
    generate_catalog_embeddings,
    get_model_spec,
)
from ..services.recommendation.text_builder import (
    deduplicate_phrases,
    prepare_movie_document,
)
from .ablation import compute_bootstrap_ci
from .baseline_engine import BaselineTFIDFRecommender, map_rating_to_weight
from .config import TFIDFV11Config, TFIDFV11MMRConfig
from .dataset import EvaluationDataset, MovieMetadata, RatingEvent
from .evaluator import EvaluationResult, OfflineEvaluator, UserEvaluationRow
from .metrics import (
    catalog_coverage_at_k,
    compute_latency_percentiles,
    hit_rate_at_k,
    intra_list_diversity_at_k,
    map_at_k,
    ndcg_at_k,
    novelty_at_k,
    precision_at_k,
    recall_at_k,
)
from .mmr import mmr_rerank
from .report_exporter import collect_environment_metadata

logger = logging.getLogger("semantic_eval")

# Admin-approved TMDB IDs from Phase 8A benchmark (excluding rejected 3085 and 24420)
APPROVED_PHASE8A_TMDB_IDS: frozenset[int] = frozenset(
    {278, 680, 157336, 129, 961729, 1397832, 328425, 653, 10331, 240, 961, 964, 4808}
)


@dataclass(frozen=True)
class SemanticModelConfig:
    """
    Frozen configuration for offline semantic embedding recommendation evaluation.
    """
    algorithm_name: str = "Semantic-MiniLM-EN"
    algorithm_version: str = "1.0.0"
    model_key: str = "english_minilm"
    dataset_condition: str = "condition_a_original"
    exclude_seen_policy: Literal["none", "train"] = "train"
    negative_feedback_policy: Literal["ignore", "suppress"] = "suppress"
    cold_start_policy: Literal["release_date_desc", "deterministic_v1_1"] = "deterministic_v1_1"
    mmr_enabled: bool = False
    mmr_lambda: float = 0.5
    mmr_candidate_pool_size: int = 100
    dataset_name: str = "MovieLens ml-latest-small"
    relevance_threshold: float = 4.0
    k_values: tuple[int, ...] = (5, 10, 20)
    train_ratio: float = 0.70
    val_ratio: float = 0.15
    test_ratio: float = 0.15
    min_user_interactions: int = 5
    random_seed: int = 42

    def to_dict(self) -> dict[str, Any]:
        spec = get_model_spec(self.model_key)
        return {
            "algorithm_name": self.algorithm_name,
            "algorithm_version": self.algorithm_version,
            "model_spec": spec.to_dict(),
            "dataset_condition": self.dataset_condition,
            "policies": {
                "exclude_seen_policy": self.exclude_seen_policy,
                "negative_feedback_policy": self.negative_feedback_policy,
                "cold_start_policy": self.cold_start_policy,
            },
            "mmr": {
                "enabled": self.mmr_enabled,
                "lambda": self.mmr_lambda,
                "candidate_pool_size": self.mmr_candidate_pool_size,
            },
            "evaluation_protocol": {
                "dataset_name": self.dataset_name,
                "relevance_threshold": self.relevance_threshold,
                "k_values": list(self.k_values),
                "split_ratios": {
                    "train": self.train_ratio,
                    "val": self.val_ratio,
                    "test": self.test_ratio,
                },
                "min_user_interactions": self.min_user_interactions,
                "random_seed": self.random_seed,
            },
        }

    def compute_checksum(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class OfflineSemanticRecommender:
    """
    Standalone offline semantic embedding recommender adhering to the exact
    interaction weighting, seen-item exclusion, and cold-start policies of
    ``BaselineTFIDFRecommender`` (TF-IDF v1.1).
    """

    def __init__(
        self,
        config: SemanticModelConfig,
        cache_dir: Path | None = None,
        allow_download: bool = False,
        encoder: SentenceEncoderProtocol | None = None,
        batch_size: int = 64,
    ):
        self.config = config
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_EMBEDDING_CACHE_DIR
        self.allow_download = allow_download
        self.encoder = encoder
        self.batch_size = batch_size

        self.artifact: EmbeddingArtifact | None = None
        self.movie_ids: list[str] = []
        self.id_to_idx: dict[str, int] = {}
        self.n_features: int = 0
        self.item_vectors: dict[str, np.ndarray] = {}
        self.cache_load_ms: float = 0.0
        self.was_cached_on_disk: bool = False

    def fit(self, movies: dict[str, MovieMetadata]) -> "OfflineSemanticRecommender":
        """
        Load a matching precomputed ``EmbeddingArtifact`` from ``cache_dir`` if
        its ``metadata_snapshot_checksum`` matches ``movies``; otherwise generate
        and save a new versioned artifact.
        """
        from ..services.recommendation.text_builder import prepare_catalog_documents

        spec = (
            self.encoder.spec
            if self.encoder is not None
            else get_model_spec(self.config.model_key)
        )
        _, snapshot_summary = prepare_catalog_documents(
            movies=movies,
            language_policy=spec.language_policy,
        )
        snapshot_checksum = snapshot_summary["metadata_snapshot_checksum"]
        dataset_id = f"{self.config.dataset_condition}_{len(movies)}"
        artifact_id = f"{dataset_id}__{spec.model_key}__{snapshot_checksum[:12]}"

        manifest_file = self.cache_dir / f"{artifact_id}_manifest.json"
        if manifest_file.is_file() and self.encoder is None:
            from ..services.recommendation.embedding_cache import load_embedding_artifact

            t_load0 = time.perf_counter()
            self.artifact = load_embedding_artifact(
                self.cache_dir, artifact_id=artifact_id, verify_checksums=True
            )
            self.cache_load_ms = (time.perf_counter() - t_load0) * 1000.0
            self.was_cached_on_disk = True
        else:
            prior_art = (
                find_latest_artifact(self.cache_dir, model_key=spec.model_key)
                if self.encoder is None
                else None
            )
            if prior_art is not None:
                docs, snapshot_summary = prepare_catalog_documents(
                    movies=movies,
                    language_policy=spec.language_policy,
                )
                from ..services.recommendation.embeddings import create_encoder
                active_enc = create_encoder(spec.model_key, allow_download=self.allow_download)
                vectors = np.zeros((len(docs), spec.embedding_dim), dtype=np.float32)
                changed_indices: list[int] = []
                changed_texts: list[str] = []
                for idx, doc in enumerate(docs):
                    prev_idx = prior_art.id_to_idx.get(doc.movie_id)
                    prev_sha = prior_art.movie_text_checksums.get(doc.movie_id)
                    if prev_idx is not None and prev_sha == doc.text_sha256:
                        vectors[idx] = prior_art.vectors[prev_idx]
                    else:
                        changed_indices.append(idx)
                        changed_texts.append(doc.text)
                t0 = time.perf_counter()
                if changed_texts:
                    new_vecs = active_enc.encode(changed_texts, batch_size=self.batch_size, normalize=True)
                    for row_i, target_idx in enumerate(changed_indices):
                        vectors[target_idx] = new_vecs[row_i]
                dt = time.perf_counter() - t0
                gen = {
                    "spec": spec,
                    "vectors": vectors,
                    "documents": docs,
                    "generation_duration_seconds": round(dt, 4),
                    "peak_memory_mb": prior_art.peak_memory_mb,
                }
            else:
                gen = generate_catalog_embeddings(
                    movies=movies,
                    model_key=self.config.model_key,
                    batch_size=self.batch_size,
                    allow_download=self.allow_download,
                    encoder=self.encoder,
                )
            self.artifact = save_embedding_artifact(
                cache_dir=self.cache_dir,
                dataset_id=dataset_id,
                spec=gen["spec"],
                vectors=gen["vectors"],
                documents=gen["documents"],
                metadata_snapshot_checksum=snapshot_checksum,
                generation_duration_seconds=gen["generation_duration_seconds"],
                peak_memory_mb=gen["peak_memory_mb"],
                artifact_id=artifact_id,
            )
            t_load0 = time.perf_counter()
            from ..services.recommendation.embedding_cache import load_embedding_artifact

            _ = load_embedding_artifact(
                self.cache_dir, artifact_id=artifact_id, verify_checksums=True
            )
            self.cache_load_ms = (time.perf_counter() - t_load0) * 1000.0
            self.was_cached_on_disk = False

        self.movie_ids = list(self.artifact.movie_ids)
        self.id_to_idx = dict(self.artifact.id_to_idx)
        self.n_features = self.artifact.dimensions
        self.item_vectors = {
            mid: self.artifact.vectors[idx].astype(np.float64)
            for mid, idx in self.id_to_idx.items()
        }
        return self

    def build_user_vector(self, user_ratings: Sequence[RatingEvent]) -> np.ndarray | None:
        """
        Build an L2-normalized semantic user preference vector from training
        interactions using the exact rating weight mapping of TF-IDF v1.1.
        """
        if self.artifact is None or not self.movie_ids:
            return None

        zero_set = set(self.artifact.zero_vector_movie_ids)
        movie_weights: dict[str, float] = {}

        for r in user_ratings:
            mid = str(r.movie_id)
            if mid not in self.id_to_idx or mid in zero_set:
                continue
            weight = map_rating_to_weight(r.rating)
            if weight > 0:
                movie_weights[mid] = max(movie_weights.get(mid, 0.0), weight)

        if not movie_weights:
            return None

        user_vector = np.zeros(self.n_features, dtype=np.float64)
        total_weight = 0.0
        for mid, weight in movie_weights.items():
            idx = self.id_to_idx[mid]
            vec = self.artifact.vectors[idx]
            if float(np.linalg.norm(vec)) <= 1e-8:
                continue
            user_vector += weight * vec.astype(np.float64)
            total_weight += weight

        if total_weight <= 0.0:
            return None

        user_vector /= total_weight
        norm = float(np.linalg.norm(user_vector))
        if norm > 0:
            user_vector /= norm

        return user_vector.astype(np.float32)

    def recommend(
        self,
        user_ratings: Sequence[RatingEvent],
        top_n: int = 20,
        exclude_seen: Literal["none", "train"] | None = None,
    ) -> list[tuple[str, float]]:
        """
        Generate top-N semantic recommendations for a user with deterministic
        tie-breaking and optional MMR diversity re-ranking.
        """
        policy = exclude_seen or self.config.exclude_seen_policy
        if self.artifact is None or not self.movie_ids:
            return []

        user_vector = self.build_user_vector(user_ratings)
        if user_vector is None:
            return [(mid, 0.0) for mid in self.movie_ids[:top_n]]

        scores = np.dot(self.artifact.vectors, user_vector)
        zero_set = set(self.artifact.zero_vector_movie_ids)

        exclude_ids: set[str] = set()
        if policy == "train":
            exclude_ids = {str(r.movie_id) for r in user_ratings}

        scored_candidates: list[tuple[str, float]] = []
        for i, mid in enumerate(self.movie_ids):
            if mid in exclude_ids or mid in zero_set:
                continue
            scored_candidates.append((mid, float(scores[i])))

        scored_candidates.sort(
            key=lambda x: (-round(x[1], 12), int(x[0]) if x[0].isdigit() else x[0])
        )

        if self.config.mmr_enabled and len(scored_candidates) > 0:
            pool_size = min(self.config.mmr_candidate_pool_size, len(scored_candidates))
            pool = scored_candidates[:pool_size]
            pool_ids = [mid for mid, _ in pool]
            pool_scores = [s for _, s in pool]
            return mmr_rerank(
                candidate_ids=pool_ids,
                candidate_scores=pool_scores,
                item_vectors=self.item_vectors,
                select_n=top_n,
                lambda_param=self.config.mmr_lambda,
            )

        return scored_candidates[:top_n]


def evaluate_recommender(
    recommender: BaselineTFIDFRecommender | OfflineSemanticRecommender,
    config: Any,
    dataset: EvaluationDataset,
    reference_tfidf_vectors: dict[str, np.ndarray] | None = None,
) -> EvaluationResult:
    """
    Execute the standard offline evaluation loop for either a TF-IDF or
    Semantic recommender on ``dataset``.

    Also computes ``tfidf_reference_ild`` when ``reference_tfidf_vectors`` are
    provided so Intra-List Diversity can be compared in a shared feature space
    as well as in each model's native vector space.
    """
    t_fit_start = time.perf_counter()
    recommender.fit(dataset.movies)
    fit_duration = time.perf_counter() - t_fit_start

    catalog_ids = set(dataset.movies.keys())
    k_values = config.k_values
    max_k = max(k_values)

    train_counts: Counter[str] = Counter()
    for u_train in dataset.train_by_user.values():
        for r in u_train:
            train_counts[str(r.movie_id)] += 1
    total_train_interactions = sum(train_counts.values())

    t_eval_start = time.perf_counter()
    per_user_rows: list[UserEvaluationRow] = []
    recommendations_by_user: dict[str, list[str]] = {}
    all_latencies_ms: list[float] = []

    test_user_ids = sorted(
        [uid for uid, t_list in dataset.test_by_user.items() if len(t_list) > 0],
        key=lambda x: int(x) if x.isdigit() else x,
    )

    for uid in test_user_ids:
        u_train = dataset.train_by_user.get(uid, [])
        u_test = dataset.test_by_user.get(uid, [])

        relevant_set = {
            str(r.movie_id)
            for r in u_test
            if r.rating >= config.relevance_threshold
        }

        t0 = time.perf_counter()
        top_recs_scored = recommender.recommend(
            user_ratings=u_train,
            top_n=max_k,
            exclude_seen=config.exclude_seen_policy,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        all_latencies_ms.append(elapsed_ms)

        rec_ids = [mid for mid, _ in top_recs_scored]
        recommendations_by_user[uid] = rec_ids

        user_metrics: dict[int, dict[str, float]] = {}
        for k in k_values:
            user_metrics[k] = {
                "precision": precision_at_k(rec_ids, relevant_set, k),
                "recall": recall_at_k(rec_ids, relevant_set, k),
                "ndcg": ndcg_at_k(rec_ids, relevant_set, k),
                "hit_rate": hit_rate_at_k(rec_ids, relevant_set, k),
                "map": map_at_k(rec_ids, relevant_set, k),
            }

        per_user_rows.append(
            UserEvaluationRow(
                user_id=uid,
                num_train=len(u_train),
                num_test_total=len(u_test),
                num_test_relevant=len(relevant_set),
                has_relevant_items=len(relevant_set) > 0,
                latency_ms=elapsed_ms,
                metrics_by_k=user_metrics,
                recommendations_top20=rec_ids[:20],
            )
        )

    eval_duration = time.perf_counter() - t_eval_start

    # Measure cold-start latency explicitly
    t_cs0 = time.perf_counter()
    _ = recommender.recommend(user_ratings=[], top_n=max_k, exclude_seen=config.exclude_seen_policy)
    cold_start_ms = (time.perf_counter() - t_cs0) * 1000.0

    active_user_rows = [r for r in per_user_rows if r.has_relevant_items]
    n_active = len(active_user_rows)
    n_total = len(per_user_rows)

    latency_dict = compute_latency_percentiles(all_latencies_ms)
    latency_dict["cold_start_ms"] = round(cold_start_ms, 4)

    aggregate_metrics: dict[str, Any] = {
        "evaluation_cohort": {
            "total_test_users": n_total,
            "users_with_relevant_items": n_active,
            "users_without_relevant_items": n_total - n_active,
            "catalog_size": len(catalog_ids),
            "relevance_threshold": config.relevance_threshold,
            "exclude_seen_policy": config.exclude_seen_policy,
            "fit_duration_seconds": round(fit_duration, 4),
            "eval_duration_seconds": round(eval_duration, 4),
        },
        "latency": latency_dict,
        "by_k": {},
    }

    if isinstance(recommender, OfflineSemanticRecommender) and recommender.artifact is not None:
        art = recommender.artifact
        zero_rate = (
            len(art.zero_vector_movie_ids) / float(art.movie_count)
            if art.movie_count > 0
            else 0.0
        )
        aggregate_metrics["embedding_artifact"] = {
            "artifact_id": art.artifact_id,
            "model_key": art.model_key,
            "model_name": art.model_name,
            "model_revision": art.model_revision,
            "is_pretrained_neural": art.is_pretrained_neural,
            "language_policy": art.language_policy,
            "dimensions": art.dimensions,
            "metadata_snapshot_checksum": art.metadata_snapshot_checksum,
            "embedding_config_checksum": art.embedding_config_checksum,
            "movie_id_mapping_checksum": art.movie_id_mapping_checksum,
            "vectors_sha256": art.vectors_sha256,
            "generation_duration_seconds": round(art.generation_duration_seconds, 4),
            "cache_load_ms": round(recommender.cache_load_ms, 4),
            "was_cached_on_disk": recommender.was_cached_on_disk,
            "storage_bytes": art.storage_bytes,
            "storage_mb": round(art.storage_bytes / (1024.0 * 1024.0), 4),
            "peak_memory_mb": round(art.peak_memory_mb, 4),
            "missing_vector_rate": round(zero_rate, 6),
            "fallback_rate": 0.0,
        }

    for k in k_values:
        if n_active > 0:
            p_macro = sum(r.metrics_by_k[k]["precision"] for r in active_user_rows) / n_active
            r_macro = sum(r.metrics_by_k[k]["recall"] for r in active_user_rows) / n_active
            ndcg_macro = sum(r.metrics_by_k[k]["ndcg"] for r in active_user_rows) / n_active
            hr_macro = sum(r.metrics_by_k[k]["hit_rate"] for r in active_user_rows) / n_active
            map_macro = sum(r.metrics_by_k[k]["map"] for r in active_user_rows) / n_active
        else:
            p_macro = r_macro = ndcg_macro = hr_macro = map_macro = 0.0

        if n_total > 0:
            p_all = sum(r.metrics_by_k[k]["precision"] for r in per_user_rows) / n_total
            r_all = sum(r.metrics_by_k[k]["recall"] for r in per_user_rows) / n_total
            ndcg_all = sum(r.metrics_by_k[k]["ndcg"] for r in per_user_rows) / n_total
            hr_all = sum(r.metrics_by_k[k]["hit_rate"] for r in per_user_rows) / n_total
            map_all = sum(r.metrics_by_k[k]["map"] for r in per_user_rows) / n_total
        else:
            p_all = r_all = ndcg_all = hr_all = map_all = 0.0

        cov = catalog_coverage_at_k(recommendations_by_user, catalog_ids, k)
        ild = intra_list_diversity_at_k(recommendations_by_user, recommender.item_vectors, k)
        nov = novelty_at_k(recommendations_by_user, train_counts, total_train_interactions, k)

        k_entry: dict[str, Any] = {
            "precision": round(p_macro, 6),
            "recall": round(r_macro, 6),
            "ndcg": round(ndcg_macro, 6),
            "hit_rate": round(hr_macro, 6),
            "map": round(map_macro, 6),
            "all_users_precision": round(p_all, 6),
            "all_users_recall": round(r_all, 6),
            "all_users_ndcg": round(ndcg_all, 6),
            "all_users_hit_rate": round(hr_all, 6),
            "all_users_map": round(map_all, 6),
            "catalog_coverage": round(cov, 6),
            "intra_list_diversity": round(ild, 6),
            "novelty": round(nov, 6),
        }
        if reference_tfidf_vectors is not None:
            ref_ild = intra_list_diversity_at_k(
                recommendations_by_user, reference_tfidf_vectors, k
            )
            k_entry["tfidf_space_ild"] = round(ref_ild, 6)

        aggregate_metrics["by_k"][f"k_{k}"] = k_entry

    return EvaluationResult(
        config=config,
        aggregate_metrics=aggregate_metrics,
        per_user_rows=per_user_rows,
        total_users_evaluated=n_total,
        users_with_relevant_items=n_active,
        catalog_size=len(catalog_ids),
        raw_dataset_checksum=dataset.raw_files_checksum,
        split_checksum=dataset.split_checksum,
        fit_duration_seconds=fit_duration,
        eval_duration_seconds=eval_duration,
    )


def compute_extended_paired_comparison(
    baseline_scores: list[float],
    variant_scores: list[float],
    n_resamples: int = 1000,
    random_seed: int = 42,
) -> dict[str, Any]:
    """
    Compute paired statistical comparison between baseline and variant user scores:
      - Mean & SD of paired difference (variant - baseline)
      - Cohen's d effect size (mean_diff / std_diff)
      - Paired t-test and Wilcoxon signed-rank test
      - 1000-resample 95% bootstrap confidence interval
      - Win / Tie / Loss user counts
    """
    base_arr = np.array(baseline_scores, dtype=np.float64)
    var_arr = np.array(variant_scores, dtype=np.float64)
    n = len(base_arr)

    if n == 0 or len(var_arr) != n:
        return {
            "sample_size": 0,
            "mean_baseline": 0.0,
            "mean_variant": 0.0,
            "mean_difference": 0.0,
            "std_difference": 0.0,
            "cohens_d": 0.0,
            "t_statistic": 0.0,
            "p_value_ttest": 1.0,
            "wilcoxon_stat": 0.0,
            "p_value_wilcoxon": 1.0,
            "bootstrap_ci_95": [0.0, 0.0],
            "win_tie_loss": {"wins": 0, "ties": 0, "losses": 0},
            "statistically_significant_05": False,
            "statistically_significant_001": False,
            "evidence_status": "NOT ENOUGH EVIDENCE",
        }

    diff = var_arr - base_arr
    mean_base = float(np.mean(base_arr))
    mean_var = float(np.mean(var_arr))
    mean_diff = float(np.mean(diff))
    std_diff = float(np.std(diff, ddof=1)) if n > 1 else 0.0
    cohens_d = (mean_diff / std_diff) if std_diff > 1e-12 else 0.0

    wins = int(np.sum(diff > 1e-12))
    losses = int(np.sum(diff < -1e-12))
    ties = int(np.sum(np.abs(diff) <= 1e-12))

    if np.allclose(diff, 0.0) or n < 2:
        return {
            "sample_size": n,
            "mean_baseline": round(mean_base, 6),
            "mean_variant": round(mean_var, 6),
            "mean_difference": 0.0,
            "std_difference": 0.0,
            "cohens_d": 0.0,
            "t_statistic": 0.0,
            "p_value_ttest": 1.0,
            "wilcoxon_stat": 0.0,
            "p_value_wilcoxon": 1.0,
            "bootstrap_ci_95": [0.0, 0.0],
            "win_tie_loss": {"wins": wins, "ties": ties, "losses": losses},
            "statistically_significant_05": False,
            "statistically_significant_001": False,
            "evidence_status": "IDENTICAL_PREDICTIONS" if n >= 30 else "NOT ENOUGH EVIDENCE",
        }

    t_res = stats.ttest_rel(var_arr, base_arr)
    t_stat = float(t_res.statistic)
    p_ttest = float(t_res.pvalue)

    nonzero = diff[np.abs(diff) > 1e-12]
    if len(nonzero) >= 1:
        try:
            w_res = stats.wilcoxon(var_arr, base_arr)
            w_stat = float(w_res.statistic)
            p_wilcoxon = float(w_res.pvalue)
        except ValueError:
            w_stat = 0.0
            p_wilcoxon = 1.0
    else:
        w_stat = 0.0
        p_wilcoxon = 1.0

    _, ci_low, ci_high = compute_bootstrap_ci(
        diff.tolist(), n_resamples=n_resamples, random_seed=random_seed
    )

    sig_05 = bool(p_ttest < 0.05 and (ci_low > 0.0 or ci_high < 0.0))
    sig_001 = bool(p_ttest < 0.001 and (ci_low > 0.0 or ci_high < 0.0))

    return {
        "sample_size": n,
        "mean_baseline": round(mean_base, 6),
        "mean_variant": round(mean_var, 6),
        "mean_difference": round(mean_diff, 6),
        "std_difference": round(std_diff, 6),
        "cohens_d": round(cohens_d, 4),
        "t_statistic": round(t_stat, 4),
        "p_value_ttest": p_ttest,
        "wilcoxon_stat": round(w_stat, 4),
        "p_value_wilcoxon": p_wilcoxon,
        "bootstrap_ci_95": [round(ci_low, 6), round(ci_high, 6)],
        "win_tie_loss": {"wins": wins, "ties": ties, "losses": losses},
        "statistically_significant_05": sig_05,
        "statistically_significant_001": sig_001,
        "evidence_status": "SUFFICIENT_SAMPLE" if n >= 30 else "NOT ENOUGH EVIDENCE",
    }


def build_condition_b_datasets(
    base_dataset: EvaluationDataset,
    dataset_dir: Path,
) -> tuple[EvaluationDataset, EvaluationDataset, dict[str, Any]]:
    """
    Construct the two Condition B (Enriched Metadata) datasets from ``base_dataset``
    and the approved Phase 8A TMDB records linked via ``links.csv``:
      1. ``full_partial_enriched_dataset`` (Protocol B1): All 9,742 MovieLens movies,
         with the 11 matched movies enriched with approved Phase 8A metadata.
      2. ``matched_subset_dataset`` (Protocol B2): Only the 11 matched MovieLens
         movies and the user interactions on those 11 movies.

    Never fabricates metadata for unmatched MovieLens movies.
    """
    links_path = dataset_dir / "links.csv"
    tmdb_to_ml_id: dict[int, str] = {}
    if links_path.is_file():
        with open(links_path, mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                raw_tmdb = (row.get("tmdbId") or "").strip()
                raw_mid = (row.get("movieId") or "").strip()
                if raw_tmdb and raw_tmdb.isdigit() and raw_mid:
                    tmdb_to_ml_id[int(raw_tmdb)] = raw_mid

    tmdb_catalog = _build_mock_tmdb_catalog()
    enriched_movies_full: dict[str, MovieMetadata] = {}
    for mid, m in base_dataset.movies.items():
        enriched_movies_full[mid] = copy.deepcopy(m)

    matched_ml_ids: list[str] = []
    matched_details: list[dict[str, Any]] = []

    for tmdb_id in sorted(APPROVED_PHASE8A_TMDB_IDS):
        ml_id = tmdb_to_ml_id.get(tmdb_id)
        if not ml_id or ml_id not in enriched_movies_full:
            continue

        payload = tmdb_catalog.get(tmdb_id)
        if not payload:
            continue

        movie_obj = enriched_movies_full[ml_id]
        tmdb_genres = [
            g["name"] for g in payload.get("genres", []) if isinstance(g, dict) and g.get("name")
        ]
        merged_genres = deduplicate_phrases(list(movie_obj.genres) + tmdb_genres)

        tmdb_keywords = [
            k["name"]
            for k in payload.get("keywords", {}).get("keywords", [])
            if isinstance(k, dict) and k.get("name")
        ]
        merged_keywords = deduplicate_phrases(list(movie_obj.tags) + tmdb_keywords)

        cast_list = [
            c["name"]
            for c in payload.get("credits", {}).get("cast", [])
            if isinstance(c, dict) and c.get("name")
        ]
        crew_list = payload.get("credits", {}).get("crew", [])
        directors = [
            c["name"]
            for c in crew_list
            if isinstance(c, dict) and c.get("job") == "Director" and c.get("name")
        ]
        director_str = directors[0] if directors else ""
        vi_block = payload.get("vi", {}) or {}

        movie_obj.original_title = str(payload.get("original_title") or "")
        movie_obj.title_vi = str(vi_block.get("title") or "")
        movie_obj.overview = str(payload.get("overview") or "")
        movie_obj.overview_vi = str(vi_block.get("overview") or "")
        movie_obj.genres = merged_genres
        movie_obj.keywords = merged_keywords
        movie_obj.cast = cast_list
        movie_obj.director = director_str
        movie_obj.tmdb_id = tmdb_id
        movie_obj.metadata_source = "tmdb"
        movie_obj.metadata_version = 2
        movie_obj.metadata_enrichment_status = "applied"

        # Rebuild TF-IDF text_profile using enriched fields (matching movie_profile.py)
        prepared_tfidf = prepare_movie_document(movie_obj, language_policy="tfidf_enriched")
        movie_obj.text_profile = prepared_tfidf.text

        matched_ml_ids.append(ml_id)
        matched_details.append(
            {
                "movielens_movie_id": ml_id,
                "tmdb_id": tmdb_id,
                "title": movie_obj.title,
                "title_vi": movie_obj.title_vi,
                "director": movie_obj.director,
                "enriched_token_count": prepared_tfidf.token_count,
            }
        )

    full_partial_dataset = EvaluationDataset(
        movies=enriched_movies_full,
        train_by_user=base_dataset.train_by_user,
        val_by_user=base_dataset.val_by_user,
        test_by_user=base_dataset.test_by_user,
        raw_files_checksum=base_dataset.raw_files_checksum,
        split_checksum=base_dataset.split_checksum,
        total_ratings_count=base_dataset.total_ratings_count,
        users_count=base_dataset.users_count,
        movies_count=len(enriched_movies_full),
    )

    # Build Protocol B2 matched-subset dataset (restricted to matched_ml_ids)
    matched_set = set(matched_ml_ids)
    subset_movies_orig = {mid: copy.deepcopy(base_dataset.movies[mid]) for mid in matched_ml_ids}
    subset_movies_enriched = {mid: copy.deepcopy(enriched_movies_full[mid]) for mid in matched_ml_ids}

    subset_train: dict[str, list[RatingEvent]] = {}
    subset_val: dict[str, list[RatingEvent]] = {}
    subset_test: dict[str, list[RatingEvent]] = {}
    subset_ratings_count = 0
    users_with_train_and_test = 0
    users_with_relevant_test = 0

    for uid in base_dataset.train_by_user:
        u_tr = [r for r in base_dataset.train_by_user.get(uid, []) if r.movie_id in matched_set]
        u_va = [r for r in base_dataset.val_by_user.get(uid, []) if r.movie_id in matched_set]
        u_te = [r for r in base_dataset.test_by_user.get(uid, []) if r.movie_id in matched_set]
        if u_tr and u_te:
            subset_train[uid] = u_tr
            subset_val[uid] = u_va
            subset_test[uid] = u_te
            subset_ratings_count += len(u_tr) + len(u_va) + len(u_te)
            users_with_train_and_test += 1
            if any(r.rating >= 4.0 for r in u_te):
                users_with_relevant_test += 1

    matched_subset_enriched_dataset = EvaluationDataset(
        movies=subset_movies_enriched,
        train_by_user=subset_train,
        val_by_user=subset_val,
        test_by_user=subset_test,
        raw_files_checksum=base_dataset.raw_files_checksum,
        split_checksum=f"matched_subset_{len(matched_ml_ids)}_{users_with_train_and_test}",
        total_ratings_count=subset_ratings_count,
        users_count=users_with_train_and_test,
        movies_count=len(subset_movies_enriched),
    )

    matched_subset_original_dataset = EvaluationDataset(
        movies=subset_movies_orig,
        train_by_user=subset_train,
        val_by_user=subset_val,
        test_by_user=subset_test,
        raw_files_checksum=base_dataset.raw_files_checksum,
        split_checksum=f"matched_subset_{len(matched_ml_ids)}_{users_with_train_and_test}",
        total_ratings_count=subset_ratings_count,
        users_count=users_with_train_and_test,
        movies_count=len(subset_movies_orig),
    )

    enrichment_coverage_info = {
        "total_movielens_catalog": len(base_dataset.movies),
        "phase8a_approved_movies_total": len(APPROVED_PHASE8A_TMDB_IDS),
        "matched_movielens_movies_count": len(matched_ml_ids),
        "catalog_enrichment_coverage_ratio": round(
            len(matched_ml_ids) / float(len(base_dataset.movies)), 6
        ),
        "matched_movies": matched_details,
        "matched_subset_cohort": {
            "candidate_movies": len(matched_ml_ids),
            "users_with_train_and_test": users_with_train_and_test,
            "users_with_relevant_test": users_with_relevant_test,
            "total_subset_ratings": subset_ratings_count,
            "evidence_status": (
                "SUFFICIENT_SAMPLE"
                if len(matched_ml_ids) >= 50 and users_with_relevant_test >= 30
                else "NOT ENOUGH EVIDENCE"
            ),
            "evidence_note": (
                f"Only {len(matched_ml_ids)} of {len(base_dataset.movies)} MovieLens movies "
                f"({len(matched_ml_ids)/len(base_dataset.movies)*100:.2f}%) have approved Phase 8A "
                f"enriched metadata (no fabricated metadata permitted). With {len(matched_ml_ids)} "
                f"candidate items and {users_with_relevant_test} users having both training and "
                f"relevant test interactions inside the subset, statistical power is insufficient "
                f"for confirmatory claims (`NOT ENOUGH EVIDENCE`)."
            ),
        },
        "matched_subset_original_dataset": matched_subset_original_dataset,
    }

    return full_partial_dataset, matched_subset_enriched_dataset, enrichment_coverage_info


def run_phase8b_experiments(
    dataset: EvaluationDataset,
    dataset_dir: Path,
    output_dir: Path,
    cache_dir: Path | None = None,
    allow_download: bool = False,
    encoder_override: SentenceEncoderProtocol | None = None,
    batch_size: int = 64,
) -> dict[str, Any]:
    """
    Execute the complete Phase 8B experimental suite:
      1. Condition A (Original Metadata on full 9,742-movie MovieLens benchmark):
         - TF-IDF v1.1 (no MMR)
         - TF-IDF v1.1 + MMR (λ=0.5, pool=100)
         - TF-IDF v1.1 + MMR (λ=0.7, pool=100)
         - Semantic-EN (`all-MiniLM-L6-v2`)
         - Semantic-Multi (`paraphrase-multilingual-MiniLM-L12-v2`)
         - Semantic-EN + MMR (λ=0.5, pool=100)
         - Semantic-EN + MMR (λ=0.7, pool=100)
      2. Condition B (Approved Enriched Metadata — 2×2 Ablation Matrix):
         - Protocol B1 (Full 9,742-movie catalog with partial approved enrichment)
         - Protocol B2 (Matched 11-movie enriched subset, with explicit power check)
      3. Paired statistical significance tests & effect sizes across all RQs.
      4. Operational cost, memory, storage, and latency benchmarks.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_cache_dir = Path(cache_dir) if cache_dir else (output_dir / "cache")
    resolved_cache_dir.mkdir(parents=True, exist_ok=True)

    env_info = collect_environment_metadata()

    # ── 1. Condition A Variants (Original MovieLens Metadata) ──────────────
    logger.info("Running Condition A: TF-IDF v1.1 baseline...")
    cfg_tfidf_a = TFIDFV11Config(algorithm_name="TFIDF-v1.1 (Original Metadata)")
    rec_tfidf_a = BaselineTFIDFRecommender(cfg_tfidf_a)
    res_tfidf_a = evaluate_recommender(rec_tfidf_a, cfg_tfidf_a, dataset)
    ref_tfidf_vectors = rec_tfidf_a.item_vectors

    logger.info("Running Condition A: TF-IDF v1.1 + MMR (lambda=0.5, pool=100)...")
    cfg_tfidf_mmr05 = TFIDFV11MMRConfig(
        algorithm_name="TFIDF-v1.1+MMR(λ=0.5,pool=100)",
        mmr_enabled=True,
        mmr_lambda=0.5,
        mmr_candidate_pool_size=100,
    )
    rec_tfidf_mmr05 = BaselineTFIDFRecommender(cfg_tfidf_mmr05)
    res_tfidf_mmr05 = evaluate_recommender(
        rec_tfidf_mmr05, cfg_tfidf_mmr05, dataset, reference_tfidf_vectors=ref_tfidf_vectors
    )

    logger.info("Running Condition A: TF-IDF v1.1 + MMR (lambda=0.7, pool=100)...")
    cfg_tfidf_mmr07 = TFIDFV11MMRConfig(
        algorithm_name="TFIDF-v1.1+MMR(λ=0.7,pool=100)",
        mmr_enabled=True,
        mmr_lambda=0.7,
        mmr_candidate_pool_size=100,
    )
    rec_tfidf_mmr07 = BaselineTFIDFRecommender(cfg_tfidf_mmr07)
    res_tfidf_mmr07 = evaluate_recommender(
        rec_tfidf_mmr07, cfg_tfidf_mmr07, dataset, reference_tfidf_vectors=ref_tfidf_vectors
    )

    logger.info("Running Condition A: English Semantic Embeddings (all-MiniLM-L6-v2)...")
    cfg_sem_en_a = SemanticModelConfig(
        algorithm_name="Semantic-MiniLM-EN (Original Metadata)",
        model_key="english_minilm" if encoder_override is None else encoder_override.spec.model_key,
        dataset_condition="condition_a_original",
    )
    rec_sem_en_a = OfflineSemanticRecommender(
        cfg_sem_en_a,
        cache_dir=resolved_cache_dir,
        allow_download=allow_download,
        encoder=encoder_override,
        batch_size=batch_size,
    )
    res_sem_en_a = evaluate_recommender(
        rec_sem_en_a, cfg_sem_en_a, dataset, reference_tfidf_vectors=ref_tfidf_vectors
    )

    logger.info("Running Condition A: Multilingual Semantic Embeddings (paraphrase-multilingual-MiniLM-L12-v2)...")
    cfg_sem_multi_a = SemanticModelConfig(
        algorithm_name="Semantic-Multilingual-MiniLM (Original Metadata)",
        model_key="multilingual_minilm" if encoder_override is None else encoder_override.spec.model_key,
        dataset_condition="condition_a_original",
    )
    rec_sem_multi_a = OfflineSemanticRecommender(
        cfg_sem_multi_a,
        cache_dir=resolved_cache_dir,
        allow_download=allow_download,
        encoder=encoder_override,
        batch_size=batch_size,
    )
    res_sem_multi_a = evaluate_recommender(
        rec_sem_multi_a, cfg_sem_multi_a, dataset, reference_tfidf_vectors=ref_tfidf_vectors
    )

    logger.info("Running Condition A: English Semantic Embeddings + MMR (lambda=0.5, pool=100)...")
    cfg_sem_en_mmr05 = SemanticModelConfig(
        algorithm_name="Semantic-MiniLM-EN+MMR(λ=0.5,pool=100)",
        model_key="english_minilm" if encoder_override is None else encoder_override.spec.model_key,
        dataset_condition="condition_a_original",
        mmr_enabled=True,
        mmr_lambda=0.5,
        mmr_candidate_pool_size=100,
    )
    rec_sem_en_mmr05 = OfflineSemanticRecommender(
        cfg_sem_en_mmr05,
        cache_dir=resolved_cache_dir,
        allow_download=allow_download,
        encoder=encoder_override,
        batch_size=batch_size,
    )
    res_sem_en_mmr05 = evaluate_recommender(
        rec_sem_en_mmr05, cfg_sem_en_mmr05, dataset, reference_tfidf_vectors=ref_tfidf_vectors
    )

    logger.info("Running Condition A: English Semantic Embeddings + MMR (lambda=0.7, pool=100)...")
    cfg_sem_en_mmr07 = SemanticModelConfig(
        algorithm_name="Semantic-MiniLM-EN+MMR(λ=0.7,pool=100)",
        model_key="english_minilm" if encoder_override is None else encoder_override.spec.model_key,
        dataset_condition="condition_a_original",
        mmr_enabled=True,
        mmr_lambda=0.7,
        mmr_candidate_pool_size=100,
    )
    rec_sem_en_mmr07 = OfflineSemanticRecommender(
        cfg_sem_en_mmr07,
        cache_dir=resolved_cache_dir,
        allow_download=allow_download,
        encoder=encoder_override,
        batch_size=batch_size,
    )
    res_sem_en_mmr07 = evaluate_recommender(
        rec_sem_en_mmr07, cfg_sem_en_mmr07, dataset, reference_tfidf_vectors=ref_tfidf_vectors
    )

    # ── 2. Condition B Variants (Enriched Metadata — 2×2 Ablation) ─────────
    logger.info("Building Condition B datasets (Full Partial Enriched & Matched Subset)...")
    full_b_dataset, subset_b_dataset, enrichment_info = build_condition_b_datasets(
        dataset, dataset_dir
    )
    subset_a_dataset = enrichment_info.pop("matched_subset_original_dataset")

    logger.info("Running Condition B1 (Full Catalog Partial Enrichment): TF-IDF v1.1...")
    cfg_tfidf_b1 = TFIDFV11Config(algorithm_name="TFIDF-v1.1 (Enriched Metadata - Full Catalog)")
    rec_tfidf_b1 = BaselineTFIDFRecommender(cfg_tfidf_b1)
    res_tfidf_b1 = evaluate_recommender(
        rec_tfidf_b1, cfg_tfidf_b1, full_b_dataset, reference_tfidf_vectors=ref_tfidf_vectors
    )

    logger.info("Running Condition B1 (Full Catalog Partial Enrichment): Semantic-EN...")
    cfg_sem_en_b1 = SemanticModelConfig(
        algorithm_name="Semantic-MiniLM-EN (Enriched Metadata - Full Catalog)",
        model_key="english_minilm" if encoder_override is None else encoder_override.spec.model_key,
        dataset_condition="condition_b1_full_partial_enriched",
    )
    rec_sem_en_b1 = OfflineSemanticRecommender(
        cfg_sem_en_b1,
        cache_dir=resolved_cache_dir,
        allow_download=allow_download,
        encoder=encoder_override,
        batch_size=batch_size,
    )
    res_sem_en_b1 = evaluate_recommender(
        rec_sem_en_b1, cfg_sem_en_b1, full_b_dataset, reference_tfidf_vectors=ref_tfidf_vectors
    )

    logger.info("Running Condition B1 (Full Catalog Partial Enrichment): Semantic-Multi...")
    cfg_sem_multi_b1 = SemanticModelConfig(
        algorithm_name="Semantic-Multilingual-MiniLM (Enriched Metadata - Full Catalog)",
        model_key="multilingual_minilm" if encoder_override is None else encoder_override.spec.model_key,
        dataset_condition="condition_b1_full_partial_enriched",
    )
    rec_sem_multi_b1 = OfflineSemanticRecommender(
        cfg_sem_multi_b1,
        cache_dir=resolved_cache_dir,
        allow_download=allow_download,
        encoder=encoder_override,
        batch_size=batch_size,
    )
    res_sem_multi_b1 = evaluate_recommender(
        rec_sem_multi_b1, cfg_sem_multi_b1, full_b_dataset, reference_tfidf_vectors=ref_tfidf_vectors
    )

    # Protocol B2: Matched 11-movie subset (exploratory / underpowered check)
    logger.info("Running Condition B2 (Matched 11-Movie Subset 2x2 check)...")
    res_sub_tfidf_a = evaluate_recommender(
        BaselineTFIDFRecommender(TFIDFV11Config(algorithm_name="Subset-TFIDF-Original")),
        TFIDFV11Config(algorithm_name="Subset-TFIDF-Original"),
        subset_a_dataset,
    )
    res_sub_tfidf_b = evaluate_recommender(
        BaselineTFIDFRecommender(TFIDFV11Config(algorithm_name="Subset-TFIDF-Enriched")),
        TFIDFV11Config(algorithm_name="Subset-TFIDF-Enriched"),
        subset_b_dataset,
    )
    res_sub_sem_en_a = evaluate_recommender(
        OfflineSemanticRecommender(
            SemanticModelConfig(
                algorithm_name="Subset-Semantic-EN-Original",
                model_key="english_minilm" if encoder_override is None else encoder_override.spec.model_key,
                dataset_condition="condition_b2_subset_original",
            ),
            cache_dir=resolved_cache_dir,
            allow_download=allow_download,
            encoder=encoder_override,
            batch_size=batch_size,
        ),
        SemanticModelConfig(
            algorithm_name="Subset-Semantic-EN-Original",
            model_key="english_minilm" if encoder_override is None else encoder_override.spec.model_key,
            dataset_condition="condition_b2_subset_original",
        ),
        subset_a_dataset,
    )
    res_sub_sem_en_b = evaluate_recommender(
        OfflineSemanticRecommender(
            SemanticModelConfig(
                algorithm_name="Subset-Semantic-EN-Enriched",
                model_key="english_minilm" if encoder_override is None else encoder_override.spec.model_key,
                dataset_condition="condition_b2_subset_enriched",
            ),
            cache_dir=resolved_cache_dir,
            allow_download=allow_download,
            encoder=encoder_override,
            batch_size=batch_size,
        ),
        SemanticModelConfig(
            algorithm_name="Subset-Semantic-EN-Enriched",
            model_key="english_minilm" if encoder_override is None else encoder_override.spec.model_key,
            dataset_condition="condition_b2_subset_enriched",
        ),
        subset_b_dataset,
    )
    res_sub_sem_multi_a = evaluate_recommender(
        OfflineSemanticRecommender(
            SemanticModelConfig(
                algorithm_name="Subset-Semantic-Multi-Original",
                model_key="multilingual_minilm" if encoder_override is None else encoder_override.spec.model_key,
                dataset_condition="condition_b2_subset_original",
            ),
            cache_dir=resolved_cache_dir,
            allow_download=allow_download,
            encoder=encoder_override,
            batch_size=batch_size,
        ),
        SemanticModelConfig(
            algorithm_name="Subset-Semantic-Multi-Original",
            model_key="multilingual_minilm" if encoder_override is None else encoder_override.spec.model_key,
            dataset_condition="condition_b2_subset_original",
        ),
        subset_a_dataset,
    )
    res_sub_sem_multi_b = evaluate_recommender(
        OfflineSemanticRecommender(
            SemanticModelConfig(
                algorithm_name="Subset-Semantic-Multi-Enriched",
                model_key="multilingual_minilm" if encoder_override is None else encoder_override.spec.model_key,
                dataset_condition="condition_b2_subset_enriched",
            ),
            cache_dir=resolved_cache_dir,
            allow_download=allow_download,
            encoder=encoder_override,
            batch_size=batch_size,
        ),
        SemanticModelConfig(
            algorithm_name="Subset-Semantic-Multi-Enriched",
            model_key="multilingual_minilm" if encoder_override is None else encoder_override.spec.model_key,
            dataset_condition="condition_b2_subset_enriched",
        ),
        subset_b_dataset,
    )

    # ── 3. Paired Statistical Comparisons ──────────────────────────────────
    def _extract_active_scores(res: EvaluationResult, metric: str = "ndcg", k: int = 10) -> list[float]:
        return [r.metrics_by_k[k][metric] for r in res.per_user_rows if r.has_relevant_items]

    base_ndcg10_a = _extract_active_scores(res_tfidf_a, "ndcg", 10)
    sem_en_ndcg10_a = _extract_active_scores(res_sem_en_a, "ndcg", 10)
    sem_multi_ndcg10_a = _extract_active_scores(res_sem_multi_a, "ndcg", 10)
    tfidf_mmr05_ndcg10_a = _extract_active_scores(res_tfidf_mmr05, "ndcg", 10)
    tfidf_mmr07_ndcg10_a = _extract_active_scores(res_tfidf_mmr07, "ndcg", 10)
    sem_en_mmr05_ndcg10_a = _extract_active_scores(res_sem_en_mmr05, "ndcg", 10)
    sem_en_mmr07_ndcg10_a = _extract_active_scores(res_sem_en_mmr07, "ndcg", 10)

    tfidf_ndcg10_b1 = _extract_active_scores(res_tfidf_b1, "ndcg", 10)
    sem_en_ndcg10_b1 = _extract_active_scores(res_sem_en_b1, "ndcg", 10)
    sem_multi_ndcg10_b1 = _extract_active_scores(res_sem_multi_b1, "ndcg", 10)

    statistical_comparisons = {
        "rq1_tfidf_enriched_vs_original_full_catalog": {
            "research_question": "RQ1: Does enriching movie metadata improve TF-IDF recommendation quality (Full Catalog with 11/9742 enriched)?",
            "ndcg_at_10": compute_extended_paired_comparison(base_ndcg10_a, tfidf_ndcg10_b1),
            "precision_at_10": compute_extended_paired_comparison(
                _extract_active_scores(res_tfidf_a, "precision", 10),
                _extract_active_scores(res_tfidf_b1, "precision", 10),
            ),
            "recall_at_10": compute_extended_paired_comparison(
                _extract_active_scores(res_tfidf_a, "recall", 10),
                _extract_active_scores(res_tfidf_b1, "recall", 10),
            ),
        },
        "rq1_semantic_en_enriched_vs_original_full_catalog": {
            "research_question": "RQ1b: Does enriching movie metadata improve English Semantic Embeddings (Full Catalog with 11/9742 enriched)?",
            "ndcg_at_10": compute_extended_paired_comparison(sem_en_ndcg10_a, sem_en_ndcg10_b1),
        },
        "rq1_semantic_multi_enriched_vs_original_full_catalog": {
            "research_question": "RQ1c: Does enriching movie metadata (with Vietnamese title_vi/overview_vi) improve Multilingual Semantic Embeddings?",
            "ndcg_at_10": compute_extended_paired_comparison(sem_multi_ndcg10_a, sem_multi_ndcg10_b1),
        },
        "rq2_semantic_en_vs_tfidf_original": {
            "research_question": "RQ2a: Do English semantic embeddings (all-MiniLM-L6-v2) outperform TF-IDF v1.1 on Original Metadata?",
            "ndcg_at_5": compute_extended_paired_comparison(
                _extract_active_scores(res_tfidf_a, "ndcg", 5),
                _extract_active_scores(res_sem_en_a, "ndcg", 5),
            ),
            "ndcg_at_10": compute_extended_paired_comparison(base_ndcg10_a, sem_en_ndcg10_a),
            "ndcg_at_20": compute_extended_paired_comparison(
                _extract_active_scores(res_tfidf_a, "ndcg", 20),
                _extract_active_scores(res_sem_en_a, "ndcg", 20),
            ),
            "precision_at_10": compute_extended_paired_comparison(
                _extract_active_scores(res_tfidf_a, "precision", 10),
                _extract_active_scores(res_sem_en_a, "precision", 10),
            ),
            "recall_at_10": compute_extended_paired_comparison(
                _extract_active_scores(res_tfidf_a, "recall", 10),
                _extract_active_scores(res_sem_en_a, "recall", 10),
            ),
        },
        "rq2_semantic_multi_vs_tfidf_original": {
            "research_question": "RQ2b: Do Multilingual semantic embeddings (paraphrase-multilingual-MiniLM-L12-v2) outperform TF-IDF v1.1 on Original Metadata?",
            "ndcg_at_5": compute_extended_paired_comparison(
                _extract_active_scores(res_tfidf_a, "ndcg", 5),
                _extract_active_scores(res_sem_multi_a, "ndcg", 5),
            ),
            "ndcg_at_10": compute_extended_paired_comparison(base_ndcg10_a, sem_multi_ndcg10_a),
            "ndcg_at_20": compute_extended_paired_comparison(
                _extract_active_scores(res_tfidf_a, "ndcg", 20),
                _extract_active_scores(res_sem_multi_a, "ndcg", 20),
            ),
            "precision_at_10": compute_extended_paired_comparison(
                _extract_active_scores(res_tfidf_a, "precision", 10),
                _extract_active_scores(res_sem_multi_a, "precision", 10),
            ),
            "recall_at_10": compute_extended_paired_comparison(
                _extract_active_scores(res_tfidf_a, "recall", 10),
                _extract_active_scores(res_sem_multi_a, "recall", 10),
            ),
        },
        "rq2_semantic_en_vs_semantic_multi_original": {
            "research_question": "RQ2c: How does English MiniLM compare against Multilingual MiniLM on Original Metadata?",
            "ndcg_at_10": compute_extended_paired_comparison(sem_multi_ndcg10_a, sem_en_ndcg10_a),
        },
        "rq2_semantic_en_vs_tfidf_enriched": {
            "research_question": "RQ2d: Do English semantic embeddings outperform TF-IDF v1.1 when both use Enriched Metadata (Condition B1)?",
            "ndcg_at_10": compute_extended_paired_comparison(tfidf_ndcg10_b1, sem_en_ndcg10_b1),
        },
        "rq3_semantic_en_vs_tfidf_mmr_05": {
            "research_question": "RQ3a: How do English semantic embeddings compare against TF-IDF v1.1 + MMR (λ=0.5, pool=100)?",
            "ndcg_at_10": compute_extended_paired_comparison(tfidf_mmr05_ndcg10_a, sem_en_ndcg10_a),
        },
        "rq3_semantic_en_mmr_05_vs_tfidf_mmr_05": {
            "research_question": "RQ3b: How does Semantic-EN + MMR (λ=0.5) compare against TF-IDF v1.1 + MMR (λ=0.5)?",
            "ndcg_at_10": compute_extended_paired_comparison(tfidf_mmr05_ndcg10_a, sem_en_mmr05_ndcg10_a),
        },
        "rq3_semantic_en_mmr_05_vs_semantic_en": {
            "research_question": "RQ3c: Does adding MMR (λ=0.5, pool=100) to Semantic-EN improve diversity or ranking?",
            "ndcg_at_10": compute_extended_paired_comparison(sem_en_ndcg10_a, sem_en_mmr05_ndcg10_a),
        },
        "rq3_semantic_en_mmr_07_vs_semantic_en": {
            "research_question": "RQ3d: Does adding MMR (λ=0.7, pool=100) to Semantic-EN improve diversity or ranking?",
            "ndcg_at_10": compute_extended_paired_comparison(sem_en_ndcg10_a, sem_en_mmr07_ndcg10_a),
        },
    }

    # ── 4. Performance & Resource Cost Benchmark Summary ───────────────────
    tfidf_matrix_bytes = (
        int(
            rec_tfidf_a.matrix.data.nbytes
            + rec_tfidf_a.matrix.indices.nbytes
            + rec_tfidf_a.matrix.indptr.nbytes
        )
        if rec_tfidf_a.matrix is not None
        else 0
    )
    sem_en_art = res_sem_en_a.aggregate_metrics.get("embedding_artifact", {})
    sem_multi_art = res_sem_multi_a.aggregate_metrics.get("embedding_artifact", {})

    performance_benchmark = {
        "catalog_size": dataset.movies_count,
        "evaluated_users": res_tfidf_a.users_with_relevant_items,
        "models": {
            "tfidf_v1_1": {
                "algorithm_name": "TFIDF-v1.1",
                "dimensions": rec_tfidf_a.n_features,
                "generation_duration_seconds": round(res_tfidf_a.fit_duration_seconds, 4),
                "cache_load_ms": round(res_tfidf_a.fit_duration_seconds * 1000.0, 2),
                "storage_bytes": tfidf_matrix_bytes,
                "storage_mb": round(tfidf_matrix_bytes / (1024.0 * 1024.0), 4),
                "peak_memory_mb": round(tfidf_matrix_bytes / (1024.0 * 1024.0), 4),
                "recommendation_latency_p50_ms": round(res_tfidf_a.aggregate_metrics["latency"]["p50_ms"], 4),
                "recommendation_latency_p95_ms": round(res_tfidf_a.aggregate_metrics["latency"]["p95_ms"], 4),
                "recommendation_latency_mean_ms": round(res_tfidf_a.aggregate_metrics["latency"]["mean_ms"], 4),
                "cold_start_latency_ms": round(res_tfidf_a.aggregate_metrics["latency"]["cold_start_ms"], 4),
                "missing_vector_rate": 0.0,
                "fallback_rate": 0.0,
            },
            "tfidf_v1_1_mmr_05": {
                "algorithm_name": "TFIDF-v1.1+MMR(λ=0.5,pool=100)",
                "dimensions": rec_tfidf_mmr05.n_features,
                "generation_duration_seconds": round(res_tfidf_mmr05.fit_duration_seconds, 4),
                "cache_load_ms": round(res_tfidf_mmr05.fit_duration_seconds * 1000.0, 2),
                "storage_bytes": tfidf_matrix_bytes,
                "storage_mb": round(tfidf_matrix_bytes / (1024.0 * 1024.0), 4),
                "peak_memory_mb": round(tfidf_matrix_bytes / (1024.0 * 1024.0), 4),
                "recommendation_latency_p50_ms": round(res_tfidf_mmr05.aggregate_metrics["latency"]["p50_ms"], 4),
                "recommendation_latency_p95_ms": round(res_tfidf_mmr05.aggregate_metrics["latency"]["p95_ms"], 4),
                "recommendation_latency_mean_ms": round(res_tfidf_mmr05.aggregate_metrics["latency"]["mean_ms"], 4),
                "cold_start_latency_ms": round(res_tfidf_mmr05.aggregate_metrics["latency"]["cold_start_ms"], 4),
                "missing_vector_rate": 0.0,
                "fallback_rate": 0.0,
            },
            "semantic_en": {
                "algorithm_name": cfg_sem_en_a.algorithm_name,
                "model_name": sem_en_art.get("model_name", ""),
                "model_revision": sem_en_art.get("model_revision", ""),
                "is_pretrained_neural": sem_en_art.get("is_pretrained_neural", False),
                "dimensions": sem_en_art.get("dimensions", 384),
                "generation_duration_seconds": sem_en_art.get("generation_duration_seconds", 0.0),
                "cache_load_ms": sem_en_art.get("cache_load_ms", 0.0),
                "storage_bytes": sem_en_art.get("storage_bytes", 0),
                "storage_mb": sem_en_art.get("storage_mb", 0.0),
                "peak_memory_mb": sem_en_art.get("peak_memory_mb", 0.0),
                "recommendation_latency_p50_ms": round(res_sem_en_a.aggregate_metrics["latency"]["p50_ms"], 4),
                "recommendation_latency_p95_ms": round(res_sem_en_a.aggregate_metrics["latency"]["p95_ms"], 4),
                "recommendation_latency_mean_ms": round(res_sem_en_a.aggregate_metrics["latency"]["mean_ms"], 4),
                "cold_start_latency_ms": round(res_sem_en_a.aggregate_metrics["latency"]["cold_start_ms"], 4),
                "missing_vector_rate": sem_en_art.get("missing_vector_rate", 0.0),
                "fallback_rate": sem_en_art.get("fallback_rate", 0.0),
            },
            "semantic_multi": {
                "algorithm_name": cfg_sem_multi_a.algorithm_name,
                "model_name": sem_multi_art.get("model_name", ""),
                "model_revision": sem_multi_art.get("model_revision", ""),
                "is_pretrained_neural": sem_multi_art.get("is_pretrained_neural", False),
                "dimensions": sem_multi_art.get("dimensions", 384),
                "generation_duration_seconds": sem_multi_art.get("generation_duration_seconds", 0.0),
                "cache_load_ms": sem_multi_art.get("cache_load_ms", 0.0),
                "storage_bytes": sem_multi_art.get("storage_bytes", 0),
                "storage_mb": sem_multi_art.get("storage_mb", 0.0),
                "peak_memory_mb": sem_multi_art.get("peak_memory_mb", 0.0),
                "recommendation_latency_p50_ms": round(res_sem_multi_a.aggregate_metrics["latency"]["p50_ms"], 4),
                "recommendation_latency_p95_ms": round(res_sem_multi_a.aggregate_metrics["latency"]["p95_ms"], 4),
                "recommendation_latency_mean_ms": round(res_sem_multi_a.aggregate_metrics["latency"]["mean_ms"], 4),
                "cold_start_latency_ms": round(res_sem_multi_a.aggregate_metrics["latency"]["cold_start_ms"], 4),
                "missing_vector_rate": sem_multi_art.get("missing_vector_rate", 0.0),
                "fallback_rate": sem_multi_art.get("fallback_rate", 0.0),
            },
            "semantic_en_mmr_05": {
                "algorithm_name": cfg_sem_en_mmr05.algorithm_name,
                "model_name": sem_en_art.get("model_name", ""),
                "model_revision": sem_en_art.get("model_revision", ""),
                "is_pretrained_neural": sem_en_art.get("is_pretrained_neural", False),
                "dimensions": sem_en_art.get("dimensions", 384),
                "generation_duration_seconds": sem_en_art.get("generation_duration_seconds", 0.0),
                "cache_load_ms": sem_en_art.get("cache_load_ms", 0.0),
                "storage_bytes": sem_en_art.get("storage_bytes", 0),
                "storage_mb": sem_en_art.get("storage_mb", 0.0),
                "peak_memory_mb": sem_en_art.get("peak_memory_mb", 0.0),
                "recommendation_latency_p50_ms": round(res_sem_en_mmr05.aggregate_metrics["latency"]["p50_ms"], 4),
                "recommendation_latency_p95_ms": round(res_sem_en_mmr05.aggregate_metrics["latency"]["p95_ms"], 4),
                "recommendation_latency_mean_ms": round(res_sem_en_mmr05.aggregate_metrics["latency"]["mean_ms"], 4),
                "cold_start_latency_ms": round(res_sem_en_mmr05.aggregate_metrics["latency"]["cold_start_ms"], 4),
                "missing_vector_rate": sem_en_art.get("missing_vector_rate", 0.0),
                "fallback_rate": sem_en_art.get("fallback_rate", 0.0),
            },
        },
    }

    condition_a_variants = {
        "tfidf_v1_1": {
            "name": "TF-IDF v1.1 (no MMR)",
            "condition": "A_Original",
            "config_checksum": cfg_tfidf_a.compute_checksum()[:16],
            "metrics": res_tfidf_a.aggregate_metrics,
        },
        "tfidf_v1_1_mmr_05": {
            "name": "TF-IDF v1.1 + MMR (λ=0.5, pool=100)",
            "condition": "A_Original",
            "config_checksum": cfg_tfidf_mmr05.compute_checksum()[:16],
            "metrics": res_tfidf_mmr05.aggregate_metrics,
        },
        "tfidf_v1_1_mmr_07": {
            "name": "TF-IDF v1.1 + MMR (λ=0.7, pool=100)",
            "condition": "A_Original",
            "config_checksum": cfg_tfidf_mmr07.compute_checksum()[:16],
            "metrics": res_tfidf_mmr07.aggregate_metrics,
        },
        "semantic_en": {
            "name": "English Semantic Embeddings (all-MiniLM-L6-v2)",
            "condition": "A_Original",
            "config_checksum": cfg_sem_en_a.compute_checksum()[:16],
            "metrics": res_sem_en_a.aggregate_metrics,
        },
        "semantic_multi": {
            "name": "Multilingual Semantic Embeddings (paraphrase-multilingual-MiniLM-L12-v2)",
            "condition": "A_Original",
            "config_checksum": cfg_sem_multi_a.compute_checksum()[:16],
            "metrics": res_sem_multi_a.aggregate_metrics,
        },
        "semantic_en_mmr_05": {
            "name": "English Semantic Embeddings + MMR (λ=0.5, pool=100)",
            "condition": "A_Original",
            "config_checksum": cfg_sem_en_mmr05.compute_checksum()[:16],
            "metrics": res_sem_en_mmr05.aggregate_metrics,
        },
        "semantic_en_mmr_07": {
            "name": "English Semantic Embeddings + MMR (λ=0.7, pool=100)",
            "condition": "A_Original",
            "config_checksum": cfg_sem_en_mmr07.compute_checksum()[:16],
            "metrics": res_sem_en_mmr07.aggregate_metrics,
        },
    }

    ablation_2x2 = {
        "protocol_b1_full_catalog_partial_enrichment": {
            "description": (
                "Full 9,742-movie MovieLens catalog where 11 matched movies receive "
                "admin-approved Phase 8A TMDB enriched metadata (overview, overview_vi, "
                "title_vi, cast, director, keywords)."
            ),
            "catalog_size": full_b_dataset.movies_count,
            "enriched_movies_count": enrichment_info["matched_movielens_movies_count"],
            "evaluated_test_users": res_tfidf_b1.users_with_relevant_items,
            "cells": {
                "tfidf_original": res_tfidf_a.aggregate_metrics,
                "tfidf_enriched": res_tfidf_b1.aggregate_metrics,
                "semantic_en_original": res_sem_en_a.aggregate_metrics,
                "semantic_en_enriched": res_sem_en_b1.aggregate_metrics,
                "semantic_multi_original": res_sem_multi_a.aggregate_metrics,
                "semantic_multi_enriched": res_sem_multi_b1.aggregate_metrics,
            },
        },
        "protocol_b2_matched_enriched_subset": {
            "description": (
                "Restricted 11-movie candidate catalog containing ONLY the MovieLens "
                "movies with approved Phase 8A enriched metadata."
            ),
            "evidence_status": enrichment_info["matched_subset_cohort"]["evidence_status"],
            "evidence_note": enrichment_info["matched_subset_cohort"]["evidence_note"],
            "catalog_size": subset_b_dataset.movies_count,
            "evaluated_test_users": res_sub_tfidf_b.users_with_relevant_items,
            "cells": {
                "tfidf_original": res_sub_tfidf_a.aggregate_metrics,
                "tfidf_enriched": res_sub_tfidf_b.aggregate_metrics,
                "semantic_en_original": res_sub_sem_en_a.aggregate_metrics,
                "semantic_en_enriched": res_sub_sem_en_b.aggregate_metrics,
                "semantic_multi_original": res_sub_sem_multi_a.aggregate_metrics,
                "semantic_multi_enriched": res_sub_sem_multi_b.aggregate_metrics,
            },
        },
        "enrichment_coverage": enrichment_info,
    }

    summary_payload = {
        "phase": "Phase 8B — Semantic Embeddings, Metadata Quality Experiments, and TEC Evaluation",
        "timestamp_utc": env_info["timestamp_utc"],
        "git_commit": env_info["git_commit"],
        "environment": env_info,
        "dataset_checksum": dataset.raw_files_checksum,
        "split_checksum": dataset.split_checksum,
        "cohort": {
            "catalog_size": dataset.movies_count,
            "total_users": dataset.users_count,
            "evaluated_test_users": res_tfidf_a.users_with_relevant_items,
            "relevance_threshold": cfg_tfidf_a.relevance_threshold,
            "exclude_seen_policy": cfg_tfidf_a.exclude_seen_policy,
            "k_values": list(cfg_tfidf_a.k_values),
        },
        "condition_a_variants": condition_a_variants,
        "ablation_2x2": ablation_2x2,
        "statistical_comparisons": statistical_comparisons,
        "performance_benchmark": performance_benchmark,
    }

    # Save JSON and CSV artifacts
    summary_path = output_dir / "phase8b_evaluation_summary.json"
    summary_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    sig_path = output_dir / "phase8b_statistical_significance.json"
    sig_path.write_text(json.dumps(statistical_comparisons, indent=2), encoding="utf-8")

    perf_path = output_dir / "phase8b_performance_benchmark.json"
    perf_path.write_text(json.dumps(performance_benchmark, indent=2), encoding="utf-8")

    _export_condition_a_csv(output_dir / "phase8b_condition_a_comparison.csv", condition_a_variants)
    _export_ablation_2x2_csv(output_dir / "phase8b_ablation_2x2.csv", ablation_2x2)
    _export_per_user_csv(
        output_dir / "phase8b_per_user_metrics.csv",
        [
            ("tfidf_v1_1", res_tfidf_a),
            ("tfidf_v1_1_mmr_05", res_tfidf_mmr05),
            ("semantic_en", res_sem_en_a),
            ("semantic_multi", res_sem_multi_a),
            ("semantic_en_mmr_05", res_sem_en_mmr05),
            ("tfidf_v1_1_enriched_b1", res_tfidf_b1),
            ("semantic_en_enriched_b1", res_sem_en_b1),
            ("semantic_multi_enriched_b1", res_sem_multi_b1),
        ],
    )

    logger.info("Phase 8B evaluation completed. Artifacts saved to %s", output_dir.resolve())
    return summary_payload


def _export_condition_a_csv(csv_path: Path, variants: dict[str, Any]) -> None:
    """Export Condition A comparison table to CSV."""
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = [
            "variant_key", "variant_name",
            "P@5", "R@5", "NDCG@5", "HR@5", "MAP@5", "Coverage@5", "ILD@5", "Novelty@5",
            "P@10", "R@10", "NDCG@10", "HR@10", "MAP@10", "Coverage@10", "ILD@10", "TFIDF_ILD@10", "Novelty@10",
            "P@20", "R@20", "NDCG@20", "HR@20", "MAP@20", "Coverage@20", "ILD@20", "Novelty@20",
            "Latency_p50_ms", "Latency_p95_ms",
        ]
        writer.writerow(header)
        for vkey, vdata in variants.items():
            m = vdata["metrics"]["by_k"]
            lat = vdata["metrics"]["latency"]
            k5, k10, k20 = m["k_5"], m["k_10"], m["k_20"]
            row = [
                vkey, vdata["name"],
                k5["precision"], k5["recall"], k5["ndcg"], k5["hit_rate"], k5["map"],
                k5["catalog_coverage"], k5["intra_list_diversity"], k5["novelty"],
                k10["precision"], k10["recall"], k10["ndcg"], k10["hit_rate"], k10["map"],
                k10["catalog_coverage"], k10["intra_list_diversity"],
                k10.get("tfidf_space_ild", k10["intra_list_diversity"]), k10["novelty"],
                k20["precision"], k20["recall"], k20["ndcg"], k20["hit_rate"], k20["map"],
                k20["catalog_coverage"], k20["intra_list_diversity"], k20["novelty"],
                round(lat["p50_ms"], 4), round(lat["p95_ms"], 4),
            ]
            writer.writerow(row)


def _export_ablation_2x2_csv(csv_path: Path, ablation_2x2: dict[str, Any]) -> None:
    """Export 2x2 Metadata Quality vs Model Architecture ablation CSV."""
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = [
            "protocol", "cell_key", "catalog_size", "evaluated_users",
            "P@10", "R@10", "NDCG@10", "HR@10", "MAP@10",
            "Coverage@10", "ILD@10", "Novelty@10",
        ]
        writer.writerow(header)
        for proto_key in ("protocol_b1_full_catalog_partial_enrichment", "protocol_b2_matched_enriched_subset"):
            proto = ablation_2x2[proto_key]
            for cell_key, metrics in proto["cells"].items():
                k10 = metrics["by_k"]["k_10"]
                writer.writerow([
                    proto_key, cell_key, proto["catalog_size"], proto["evaluated_test_users"],
                    k10["precision"], k10["recall"], k10["ndcg"], k10["hit_rate"], k10["map"],
                    k10["catalog_coverage"], k10["intra_list_diversity"], k10["novelty"],
                ])


def _export_per_user_csv(
    csv_path: Path,
    results: list[tuple[str, EvaluationResult]],
) -> None:
    """Export per-user metrics for paired verification."""
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = [
            "user_id", "variant_key", "num_train", "num_test_relevant",
            "has_relevant_items", "latency_ms",
            "P@5", "R@5", "NDCG@5", "HR@5", "MAP@5",
            "P@10", "R@10", "NDCG@10", "HR@10", "MAP@10",
            "P@20", "R@20", "NDCG@20", "HR@20", "MAP@20",
        ]
        writer.writerow(header)
        for vkey, res in results:
            for row in res.per_user_rows:
                csv_row: list[Any] = [
                    row.user_id, vkey, row.num_train, row.num_test_relevant,
                    int(row.has_relevant_items), round(row.latency_ms, 4),
                ]
                for k in (5, 10, 20):
                    mk = row.metrics_by_k[k]
                    csv_row.extend([
                        mk["precision"], mk["recall"], mk["ndcg"],
                        mk["hit_rate"], mk["map"],
                    ])
                writer.writerow(csv_row)
