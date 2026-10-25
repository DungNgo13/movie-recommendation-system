"""
Command-Line Interface for Offline Recommendation Evaluation Harness.

Usage:
    python -m app.recommendation_evaluation.cli \
        --data-dir data/ml-latest-small \
        --output-dir reports/experiments/baseline_tfidf_v1_0 \
        --experiment-id baseline_tfidf_v1_0
"""

import argparse
import json
import logging
from pathlib import Path
import sys

import yaml

from .config import TFIDFBaselineConfig
from .dataset import build_evaluation_dataset, download_and_extract_movielens
from .evaluator import OfflineEvaluator
from .report_exporter import export_experiment_reports

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("rec_eval")


def parse_args():
    parser = argparse.ArgumentParser(description="MovSug Offline Recommendation Evaluation Runner")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/ml-latest-small",
        help="Path to MovieLens ml-latest-small directory",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Automatically download MovieLens ml-latest-small if not present",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="reports/experiments/baseline_tfidf_v1_0",
        help="Directory to save experimental reports",
    )
    parser.add_argument(
        "--experiment-id",
        type=str,
        default="baseline_tfidf_v1_0",
        help="Experiment identifier for report metadata",
    )
    parser.add_argument(
        "--exclude-seen",
        type=str,
        choices=["none", "train"],
        default=None,
        help="Override seen-item exclusion policy ('none' for v1.0 baseline, 'train' for clean RecSys)",
    )
    parser.add_argument(
        "--k-values",
        type=str,
        default=None,
        help="Comma-separated K values, e.g. '5,10,20'",
    )
    parser.add_argument(
        "--relevance-threshold",
        type=float,
        default=None,
        help="Minimum star rating to consider a test interaction as relevant ground truth",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to YAML or JSON configuration file",
    )
    parser.add_argument(
        "--ablation",
        action="store_true",
        help="Run full 5-variant controlled ablation study and statistical analysis (Phase 5)",
    )
    return parser.parse_args()


def load_config_from_file(config_path: Path) -> dict:
    """Load config dictionary from YAML or JSON file."""
    with open(config_path, "r", encoding="utf-8") as f:
        if config_path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(f) or {}
        return json.load(f)


def main():
    args = parse_args()

    # Base configuration
    config_kwargs = {}
    if args.config:
        cfg_file = Path(args.config)
        if cfg_file.exists():
            file_cfg = load_config_from_file(cfg_file)
            config_kwargs.update(file_cfg)
            logger.info("Loaded configuration from %s", cfg_file)
        else:
            logger.error("Configuration file not found: %s", cfg_file)
            sys.exit(1)

    if args.exclude_seen:
        config_kwargs["exclude_seen_policy"] = args.exclude_seen
    if args.relevance_threshold is not None:
        config_kwargs["relevance_threshold"] = args.relevance_threshold
    if args.k_values:
        k_tuple = tuple(int(x.strip()) for x in args.k_values.split(",") if x.strip())
        config_kwargs["k_values"] = k_tuple

    config = TFIDFBaselineConfig(**config_kwargs)
    logger.info("Initialized configuration for '%s' (checksum: %s)", config.algorithm_name, config.compute_checksum()[:12])

    data_dir = Path(args.data_dir)
    # If data directory doesn't exist, check parent or attempt download
    if not (data_dir.exists() and (data_dir / "movies.csv").exists()):
        if args.download or not data_dir.exists():
            logger.info("Data directory missing movies.csv. Downloading MovieLens dataset...")
            dest_parent = data_dir.parent if data_dir.name == "ml-latest-small" else data_dir
            extracted_dir, sha256 = download_and_extract_movielens(dest_parent)
            data_dir = extracted_dir
            logger.info("Dataset ready at %s (SHA256: %s)", data_dir, sha256[:12])
        else:
            logger.error("Data directory %s does not contain MovieLens CSVs. Pass --download to fetch.", data_dir)
            sys.exit(1)

    logger.info("Building evaluation dataset from %s...", data_dir)
    dataset = build_evaluation_dataset(
        dataset_dir=data_dir,
        train_ratio=config.train_ratio,
        val_ratio=config.val_ratio,
        test_ratio=config.test_ratio,
        min_interactions=config.min_user_interactions,
        title_weight=config.title_weight,
        keywords_weight=config.keywords_weight,
        genres_weight=config.genres_weight,
        tag_leakage_prevention=True,
    )
    logger.info(
        "Dataset loaded: %d movies, %d total ratings across %d users. Split SHA256: %s",
        dataset.movies_count,
        dataset.total_ratings_count,
        dataset.users_count,
        dataset.split_checksum[:12],
    )

    if args.ablation:
        out_dir = Path("reports/experiments/tfidf_v1_1_controlled_ablation") if args.output_dir == "reports/experiments/baseline_tfidf_v1_0" else Path(args.output_dir)
        logger.info("Running Phase 5 controlled ablation study across 5 variants...")
        from .ablation import run_controlled_ablation
        run_controlled_ablation(dataset, out_dir)
        logger.info("Ablation study completed. Reports saved to %s", out_dir.resolve())
        return

    evaluator = OfflineEvaluator(config)
    logger.info("Running offline evaluation...")
    result = evaluator.evaluate(dataset)

    output_dir = Path(args.output_dir)
    logger.info("Exporting experimental reports to %s...", output_dir)
    report_paths = export_experiment_reports(result, output_dir, experiment_id=args.experiment_id)

    # Print summary table
    print("\n" + "=" * 70)
    print(f" EXPERIMENT RESULTS: {config.algorithm_name} (ID: {args.experiment_id})")
    print("=" * 70)
    print(f"Catalog size: {result.catalog_size} | Test users evaluated: {result.total_users_evaluated}")
    print(f"Users with relevant test items: {result.users_with_relevant_items}")
    print(f"Exclusion policy: {config.exclude_seen_policy} (Defect R1 active: {config.exclude_seen_policy == 'none'})")
    print(f"Latencies: p50={result.aggregate_metrics['latency']['p50_ms']:.2f}ms, p95={result.aggregate_metrics['latency']['p95_ms']:.2f}ms")
    print("-" * 70)
    print(f"{'Metric':<15} {'K=5':<12} {'K=10':<12} {'K=20':<12}")
    print("-" * 70)
    for metric_name in ["precision", "recall", "ndcg", "hit_rate", "map", "catalog_coverage", "intra_list_diversity", "novelty"]:
        row_str = f"{metric_name:<15}"
        for k in config.k_values:
            val = result.aggregate_metrics["by_k"][f"k_{k}"][metric_name]
            if metric_name == "catalog_coverage":
                row_str += f"{val*100:>10.2f}% "
            else:
                row_str += f"{val:>11.4f} "
        print(row_str)
    print("=" * 70)
    print(f"Reports saved to: {output_dir.resolve()}")
    for k, p in report_paths.items():
        print(f" - {k}: {p.name}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
