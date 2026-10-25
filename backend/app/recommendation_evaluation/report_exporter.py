"""
Report Exporter for Offline Recommendation Evaluation.

Generates reproducible research artifacts:
- metrics.json
- per_user_metrics.csv
- experiment_config.json
- environment.json
- summary.md
"""

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any

import numpy as np
import scipy
import sklearn

from .evaluator import EvaluationResult


def get_git_commit_hash() -> str:
    """Retrieve current Git commit SHA."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "unknown_or_detached"


def collect_environment_metadata() -> dict[str, Any]:
    """Capture runtime environment details for scientific reproducibility."""
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "git_commit": get_git_commit_hash(),
        "dependencies": {
            "scikit-learn": sklearn.__version__,
            "scipy": scipy.__version__,
            "numpy": np.__version__,
        },
    }


def export_experiment_reports(
    result: EvaluationResult,
    output_dir: Path,
    experiment_id: str = "baseline_tfidf_v1_0",
) -> dict[str, Path]:
    """
    Save all evaluation artifacts into output_dir.

    Returns dict of artifact paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    env_info = collect_environment_metadata()
    config_dict = result.config.to_dict()
    config_checksum = result.config.compute_checksum()

    # 1. environment.json
    env_path = output_dir / "environment.json"
    with open(env_path, "w", encoding="utf-8") as f:
        json.dump(env_info, f, indent=2)

    # 2. experiment_config.json
    cfg_path = output_dir / "experiment_config.json"
    full_config_payload = {
        "experiment_id": experiment_id,
        "config_checksum_sha256": config_checksum,
        "raw_dataset_checksum_sha256": result.raw_dataset_checksum,
        "split_checksum_sha256": result.split_checksum,
        "configuration": config_dict,
    }
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(full_config_payload, f, indent=2)

    # 3. metrics.json
    metrics_path = output_dir / "metrics.json"
    full_metrics_payload = {
        "experiment_id": experiment_id,
        "algorithm_name": result.config.algorithm_name,
        "algorithm_version": result.config.algorithm_version,
        "git_commit": env_info["git_commit"],
        "timestamp_utc": env_info["timestamp_utc"],
        "checksums": {
            "config_sha256": config_checksum,
            "raw_dataset_sha256": result.raw_dataset_checksum,
            "split_sha256": result.split_checksum,
        },
        "metrics": result.aggregate_metrics,
    }
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(full_metrics_payload, f, indent=2)

    # 4. per_user_metrics.csv
    csv_path = output_dir / "per_user_metrics.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = [
            "user_id",
            "num_train",
            "num_test_total",
            "num_test_relevant",
            "has_relevant_items",
            "latency_ms",
        ]
        for k in result.config.k_values:
            header.extend([
                f"precision@{k}",
                f"recall@{k}",
                f"ndcg@{k}",
                f"map@{k}",
                f"hit_rate@{k}",
            ])
        writer.writerow(header)

        for row in result.per_user_rows:
            csv_row: list[Any] = [
                row.user_id,
                row.num_train,
                row.num_test_total,
                row.num_test_relevant,
                int(row.has_relevant_items),
                round(row.latency_ms, 3),
            ]
            for k in result.config.k_values:
                m = row.metrics_by_k[k]
                csv_row.extend([
                    round(m["precision"], 6),
                    round(m["recall"], 6),
                    round(m["ndcg"], 6),
                    round(m["map"], 6),
                    round(m["hit_rate"], 6),
                ])
            writer.writerow(csv_row)

    # 5. summary.md
    summary_path = output_dir / "summary.md"
    summary_content = _generate_summary_markdown(
        experiment_id=experiment_id,
        result=result,
        env_info=env_info,
        config_checksum=config_checksum,
    )
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_content)

    return {
        "metrics_json": metrics_path,
        "per_user_csv": csv_path,
        "config_json": cfg_path,
        "environment_json": env_path,
        "summary_md": summary_path,
    }


def _generate_summary_markdown(
    experiment_id: str,
    result: EvaluationResult,
    env_info: dict[str, Any],
    config_checksum: str,
) -> str:
    """Generate comprehensive human-readable experiment summary report."""
    cfg = result.config
    agg = result.aggregate_metrics
    cohort = agg["evaluation_cohort"]
    lat = agg["latency"]
    by_k = agg["by_k"]

    lines = [
        f"# MovSug Offline Evaluation Report: {cfg.algorithm_name}",
        "",
        f"**Experiment ID:** `{experiment_id}`  ",
        f"**Algorithm Version:** `{cfg.algorithm_version}`  ",
        f"**Execution Timestamp:** `{env_info['timestamp_utc']}`  ",
        f"**Git Commit:** `{env_info['git_commit']}`  ",
        f"**Configuration Checksum (SHA256):** `{config_checksum}`  ",
        f"**Dataset Checksum (SHA256):** `{result.raw_dataset_checksum}`  ",
        f"**Split Checksum (SHA256):** `{result.split_checksum}`  ",
        "",
        "---",
        "",
        "## 1. Experimental Setup & Protocol",
        "",
        f"- **Dataset:** `{cfg.dataset_name}` ({cohort['catalog_size']} movies, {cohort['total_test_users']} test users)",
        f"- **Evaluation Protocol:** Per-user chronological split ({cfg.train_ratio*100:.0f}% Train / {cfg.val_ratio*100:.0f}% Val / {cfg.test_ratio*100:.0f}% Test)",
        f"- **Positive Relevance Ground Truth:** Rating $\\ge {cfg.relevance_threshold}$ in held-out test split",
        f"- **Evaluated Cohort:** {cohort['users_with_relevant_items']} users with $\\ge 1$ relevant test item ({cohort['users_without_relevant_items']} users with 0 relevant test items)",
        f"- **Seen-Item Exclusion Policy:** `{cfg.exclude_seen_policy}` (Defect R1 active: `{cfg.exclude_seen_policy == 'none'}`)",
        f"- **Model Fitting Duration:** {cohort['fit_duration_seconds']:.2f} s",
        f"- **Full Evaluation Duration:** {cohort['eval_duration_seconds']:.2f} s",
        "",
        "---",
        "",
        "## 2. Key Performance Metrics",
        "",
        "### 2.1 Ranking & Accuracy Metrics (Macro-averaged over users with $\\ge 1$ relevant test item)",
        "",
        "| Metric | K = 5 | K = 10 | K = 20 |",
        "|---|---|---|---|",
        f"| **Precision@K** | {by_k['k_5']['precision']:.4f} | {by_k['k_10']['precision']:.4f} | {by_k['k_20']['precision']:.4f} |",
        f"| **Recall@K** | {by_k['k_5']['recall']:.4f} | {by_k['k_10']['recall']:.4f} | {by_k['k_20']['recall']:.4f} |",
        f"| **NDCG@K** | {by_k['k_5']['ndcg']:.4f} | {by_k['k_10']['ndcg']:.4f} | {by_k['k_20']['ndcg']:.4f} |",
        f"| **HitRate@K** | {by_k['k_5']['hit_rate']:.4f} | {by_k['k_10']['hit_rate']:.4f} | {by_k['k_20']['hit_rate']:.4f} |",
        f"| **MAP@K** | {by_k['k_5']['map']:.4f} | {by_k['k_10']['map']:.4f} | {by_k['k_20']['map']:.4f} |",
        "",
        "### 2.2 Ranking Metrics Across ALL Test Users (including users with 0 test positives)",
        "",
        "| Metric | K = 5 | K = 10 | K = 20 |",
        "|---|---|---|---|",
        f"| **Precision@K** | {by_k['k_5']['all_users_precision']:.4f} | {by_k['k_10']['all_users_precision']:.4f} | {by_k['k_20']['all_users_precision']:.4f} |",
        f"| **Recall@K** | {by_k['k_5']['all_users_recall']:.4f} | {by_k['k_10']['all_users_recall']:.4f} | {by_k['k_20']['all_users_recall']:.4f} |",
        f"| **NDCG@K** | {by_k['k_5']['all_users_ndcg']:.4f} | {by_k['k_10']['all_users_ndcg']:.4f} | {by_k['k_20']['all_users_ndcg']:.4f} |",
        f"| **HitRate@K** | {by_k['k_5']['all_users_hit_rate']:.4f} | {by_k['k_10']['all_users_hit_rate']:.4f} | {by_k['k_20']['all_users_hit_rate']:.4f} |",
        f"| **MAP@K** | {by_k['k_5']['all_users_map']:.4f} | {by_k['k_10']['all_users_map']:.4f} | {by_k['k_20']['all_users_map']:.4f} |",
        "",
        "### 2.3 Diversity, Coverage & Novelty Metrics",
        "",
        "| Metric | K = 5 | K = 10 | K = 20 |",
        "|---|---|---|---|",
        f"| **Catalog Coverage@K** | {by_k['k_5']['catalog_coverage']*100:.2f}% | {by_k['k_10']['catalog_coverage']*100:.2f}% | {by_k['k_20']['catalog_coverage']*100:.2f}% |",
        f"| **Intra-List Diversity@K** | {by_k['k_5']['intra_list_diversity']:.4f} | {by_k['k_10']['intra_list_diversity']:.4f} | {by_k['k_20']['intra_list_diversity']:.4f} |",
        f"| **Novelty@K (bits)** | {by_k['k_5']['novelty']:.4f} | {by_k['k_10']['novelty']:.4f} | {by_k['k_20']['novelty']:.4f} |",
        "",
        "### 2.4 Recommendation Latency",
        "",
        "| Percentile | Latency (ms) |",
        "|---|---|",
        f"| **Median (p50)** | {lat['p50_ms']:.2f} ms |",
        f"| **90th Percentile (p90)** | {lat['p90_ms']:.2f} ms |",
        f"| **95th Percentile (p95)** | {lat['p95_ms']:.2f} ms |",
        f"| **Mean** | {lat['mean_ms']:.2f} ms |",
        "",
        "---",
        "",
        "## 3. Analysis & Known Limitations",
        "",
        "### 3.1 Defect R1 Preservation",
        "In production MovSug `TFIDF-v1.0`, only favorites are excluded from recommendation lists (`exclude_ids = set(get_user_favorite_ids())`). Rated and watched movies are NOT excluded.",
        "In offline evaluation where ground truth ratings are split chronologically, training-set movies that the user rated highly (4-5 stars) have the highest cosine similarity with the user vector.",
        "When `exclude_seen_policy = 'none'`, the recommender recommends already-rated training movies back to the user at the top ranks. Since those training movies cannot appear in the held-out future test set, ranking metrics against future test items are severely degraded.",
        "",
        "### 3.2 Metadata Representation Adaptation",
        "The production engine builds movie profiles from `title * 2`, `overview * 1`, `genres * 1`, `cast * 1`, `keywords * 2`, `director * 1`.",
        "MovieLens `ml-latest-small` contains only `title`, `genres`, and user `tags` (acting as keywords). Plot overviews, cast, and directors are not present in MovieLens and were NOT fabricated.",
        "Item representations in this baseline use `title * 2`, `genres * 1`, and `tags * 2`. Tag leakage prevention ensures tags applied during future test interactions are excluded from movie profiles.",
        "",
        "### 3.3 Readiness for Phase 5",
        "This experiment establishes the exact numerical baseline for `TFIDF-v1.0-as-is`. In Phase 5, controlled experiments will measure:",
        "1. `TFIDF-v1.1`: Fixing Defect R1 (seen-item filtering) and Defect R2 (negative feedback suppression).",
        "2. Algorithmic enhancements: Maximal Marginal Relevance (MMR) for diversity, Cold-start fallback re-ranking, and Hybrid recommendations.",
    ]
    return "\n".join(lines) + "\n"
