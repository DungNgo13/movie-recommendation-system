"""
Offline Recommendation Evaluation Framework.

Provides reproducible dataset pipelines, standard IR/RecSys ranking and diversity metrics,
and experimental harness for MovSug recommendation baselines.
"""

from .config import TFIDFBaselineConfig, TFIDFV11Config, TFIDFV11MMRConfig
from .dataset import (
    MovieMetadata,
    RatingEvent,
    EvaluationDataset,
    build_evaluation_dataset,
    download_and_extract_movielens,
)
from .baseline_engine import BaselineTFIDFRecommender, map_rating_to_weight
from .evaluator import OfflineEvaluator, EvaluationResult, UserEvaluationRow
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
from .mmr import mmr_rerank
from .report_exporter import export_experiment_reports
from .ablation import run_controlled_ablation

__all__ = [
    "TFIDFBaselineConfig",
    "TFIDFV11Config",
    "TFIDFV11MMRConfig",
    "mmr_rerank",
    "run_controlled_ablation",
    "MovieMetadata",
    "RatingEvent",
    "EvaluationDataset",
    "build_evaluation_dataset",
    "download_and_extract_movielens",
    "BaselineTFIDFRecommender",
    "map_rating_to_weight",
    "OfflineEvaluator",
    "EvaluationResult",
    "UserEvaluationRow",
    "precision_at_k",
    "recall_at_k",
    "ndcg_at_k",
    "hit_rate_at_k",
    "map_at_k",
    "catalog_coverage_at_k",
    "intra_list_diversity_at_k",
    "novelty_at_k",
    "compute_latency_percentiles",
    "export_experiment_reports",
]
