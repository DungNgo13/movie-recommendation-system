"""
Evaluation Harness and Metric Accumulator.

Executes offline evaluation across test users, computes per-user and aggregate
metrics (ranking, coverage, diversity, novelty, latency), and returns structured results.
"""

from collections import Counter
from dataclasses import dataclass, field
import time
from typing import Any

from .baseline_engine import BaselineTFIDFRecommender
from .config import TFIDFBaselineConfig
from .dataset import EvaluationDataset, RatingEvent
from .metrics import (
    precision_at_k,
    recall_at_k,
    ndcg_at_k,
    hit_rate_at_k,
    map_at_k,
    catalog_coverage_at_k,
    intra_list_diversity_at_k,
    novelty_at_k,
    compute_latency_percentiles,
)


@dataclass
class UserEvaluationRow:
    """Evaluation metrics for a single user."""
    user_id: str
    num_train: int
    num_test_total: int
    num_test_relevant: int
    has_relevant_items: bool
    latency_ms: float
    metrics_by_k: dict[int, dict[str, float]] = field(default_factory=dict)
    recommendations_top20: list[str] = field(default_factory=list)


@dataclass
class EvaluationResult:
    """Complete aggregated evaluation results for an experiment."""
    config: TFIDFBaselineConfig
    aggregate_metrics: dict[str, Any]
    per_user_rows: list[UserEvaluationRow]
    total_users_evaluated: int
    users_with_relevant_items: int
    catalog_size: int
    raw_dataset_checksum: str
    split_checksum: str
    fit_duration_seconds: float
    eval_duration_seconds: float


class OfflineEvaluator:
    """
    Coordinates model fitting, recommendation generation, timing, and metric calculation.
    """

    def __init__(self, config: TFIDFBaselineConfig | None = None):
        self.config = config or TFIDFBaselineConfig()
        self.recommender = BaselineTFIDFRecommender(self.config)

    def evaluate(self, dataset: EvaluationDataset) -> EvaluationResult:
        """
        Run the complete evaluation workflow.
        """
        # 1. Fit recommender
        t_fit_start = time.perf_counter()
        self.recommender.fit(dataset.movies)
        fit_duration = time.perf_counter() - t_fit_start

        catalog_ids = set(dataset.movies.keys())
        k_values = self.config.k_values
        max_k = max(k_values)

        # Count item interactions in training set for Novelty
        train_counts: Counter[str] = Counter()
        for u_train in dataset.train_by_user.values():
            for r in u_train:
                train_counts[str(r.movie_id)] += 1
        total_train_interactions = sum(train_counts.values())

        # Collect user results
        t_eval_start = time.perf_counter()
        per_user_rows: list[UserEvaluationRow] = []
        recommendations_by_user: dict[str, list[str]] = {}
        all_latencies_ms: list[float] = []

        # Sort users for deterministic execution
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
                if r.rating >= self.config.relevance_threshold
            }

            # Measure recommendation latency
            t0 = time.perf_counter()
            top_recs_scored = self.recommender.recommend(
                user_ratings=u_train,
                top_n=max_k,
                exclude_seen=self.config.exclude_seen_policy,
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

            row = UserEvaluationRow(
                user_id=uid,
                num_train=len(u_train),
                num_test_total=len(u_test),
                num_test_relevant=len(relevant_set),
                has_relevant_items=len(relevant_set) > 0,
                latency_ms=elapsed_ms,
                metrics_by_k=user_metrics,
                recommendations_top20=rec_ids[:20],
            )
            per_user_rows.append(row)

        eval_duration = time.perf_counter() - t_eval_start

        # ── Compute Aggregate Metrics ──────────────────────────────────
        active_user_rows = [r for r in per_user_rows if r.has_relevant_items]
        n_active = len(active_user_rows)
        n_total = len(per_user_rows)

        aggregate_metrics: dict[str, Any] = {
            "evaluation_cohort": {
                "total_test_users": n_total,
                "users_with_relevant_items": n_active,
                "users_without_relevant_items": n_total - n_active,
                "catalog_size": len(catalog_ids),
                "relevance_threshold": self.config.relevance_threshold,
                "exclude_seen_policy": self.config.exclude_seen_policy,
                "fit_duration_seconds": round(fit_duration, 4),
                "eval_duration_seconds": round(eval_duration, 4),
            },
            "latency": compute_latency_percentiles(all_latencies_ms),
            "by_k": {},
        }

        for k in k_values:
            # Macro average over users with at least 1 relevant test item
            if n_active > 0:
                p_macro = sum(r.metrics_by_k[k]["precision"] for r in active_user_rows) / n_active
                r_macro = sum(r.metrics_by_k[k]["recall"] for r in active_user_rows) / n_active
                ndcg_macro = sum(r.metrics_by_k[k]["ndcg"] for r in active_user_rows) / n_active
                hr_macro = sum(r.metrics_by_k[k]["hit_rate"] for r in active_user_rows) / n_active
                map_macro = sum(r.metrics_by_k[k]["map"] for r in active_user_rows) / n_active
            else:
                p_macro = r_macro = ndcg_macro = hr_macro = map_macro = 0.0

            # Macro average across ALL test users (treating zero-relevant as 0)
            if n_total > 0:
                p_all = sum(r.metrics_by_k[k]["precision"] for r in per_user_rows) / n_total
                r_all = sum(r.metrics_by_k[k]["recall"] for r in per_user_rows) / n_total
                ndcg_all = sum(r.metrics_by_k[k]["ndcg"] for r in per_user_rows) / n_total
                hr_all = sum(r.metrics_by_k[k]["hit_rate"] for r in per_user_rows) / n_total
                map_all = sum(r.metrics_by_k[k]["map"] for r in per_user_rows) / n_total
            else:
                p_all = r_all = ndcg_all = hr_all = map_all = 0.0

            cov = catalog_coverage_at_k(recommendations_by_user, catalog_ids, k)
            ild = intra_list_diversity_at_k(recommendations_by_user, self.recommender.item_vectors, k)
            nov = novelty_at_k(recommendations_by_user, train_counts, total_train_interactions, k)

            aggregate_metrics["by_k"][f"k_{k}"] = {
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

        return EvaluationResult(
            config=self.config,
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
