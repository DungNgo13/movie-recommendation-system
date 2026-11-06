"""
Phase 8C Evaluation: 6-Cell Metadata Coverage × Model Architecture Comparison.

Implements the controlled A–F evaluation matrix:
  A: TF-IDF v1.1 — original metadata
  B: TF-IDF v1.1 — enriched metadata
  C: Semantic-EN — original metadata
  D: Semantic-EN — enriched metadata
  E: Semantic-Multi — original metadata
  F: Semantic-Multi — enriched metadata

All cells use identical catalog, splits, cohort, relevance definition,
seen-item policy, and metric implementations. Reports at K=5, 10, 20
with full statistical analysis.

Preserves Phase 8B artifacts as historical references.
"""

from __future__ import annotations

import copy
import csv
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np
from scipy import stats

from ..services.recommendation.text_builder import prepare_movie_document
from .baseline_engine import BaselineTFIDFRecommender
from .config import TFIDFV11Config
from .dataset import EvaluationDataset, MovieMetadata, RatingEvent
from .evaluator import EvaluationResult
from .identity_mapping import IdentityMappingResult, load_identity_mapping
from .report_exporter import collect_environment_metadata
from .research_snapshot import (
    ResearchMetadataSnapshot,
    compute_field_coverage,
    create_snapshot,
    save_snapshot,
)
from .semantic_eval import (
    OfflineSemanticRecommender,
    SemanticModelConfig,
    compute_extended_paired_comparison,
    evaluate_recommender,
)
from .tmdb_research_retrieval import (
    RetrievalSummary,
    build_enriched_catalog,
    generate_coverage_report,
    retrieve_mock_tmdb_metadata,
    select_stratified_pilot_subset,
)

logger = logging.getLogger("phase8c_eval")

# Phase 8C default configuration
PHASE8C_SEED = 8042
PHASE8C_PILOT_SIZE = 200


@dataclass(frozen=True)
class Phase8CEvalConfig:
    """Configuration for Phase 8C evaluation experiments."""

    pilot_sample_size: int = PHASE8C_PILOT_SIZE
    seed: int = PHASE8C_SEED
    k_values: tuple[int, ...] = (5, 10, 20)
    relevance_threshold: float = 4.0
    exclude_seen_policy: str = "train"
    enrichment_source: str = "mock_tmdb_catalog"


def _build_enriched_dataset(
    base_dataset: EvaluationDataset,
    enriched_catalog: dict[str, MovieMetadata],
) -> EvaluationDataset:
    """Build an EvaluationDataset with an enriched movie catalog."""
    return EvaluationDataset(
        movies=enriched_catalog,
        train_by_user=base_dataset.train_by_user,
        val_by_user=base_dataset.val_by_user,
        test_by_user=base_dataset.test_by_user,
        raw_files_checksum=base_dataset.raw_files_checksum,
        split_checksum=base_dataset.split_checksum,
        total_ratings_count=base_dataset.total_ratings_count,
        users_count=base_dataset.users_count,
        movies_count=len(enriched_catalog),
    )


def _extract_active_ndcg(
    result: EvaluationResult, metric: str = "ndcg", k: int = 10
) -> list[float]:
    """Extract per-user metric scores for users with relevant test items."""
    return [
        r.metrics_by_k[k][metric]
        for r in result.per_user_rows
        if r.has_relevant_items
    ]


def run_phase8c_evaluation(
    dataset: EvaluationDataset,
    dataset_dir: Path,
    output_dir: Path,
    config: Phase8CEvalConfig | None = None,
    cache_dir: Path | None = None,
    allow_download: bool = False,
    encoder_override: Any = None,
    batch_size: int = 64,
) -> dict[str, Any]:
    """
    Execute the complete Phase 8C evaluation suite.

    Steps:
      1. Load identity mapping from links.csv
      2. Select stratified pilot subset
      3. Retrieve mock TMDB metadata (dry-run)
      4. Create research metadata snapshot
      5. Evaluate 6-cell matrix (A–F)
      6. Statistical comparisons
      7. Generate coverage and temporal validity reports
      8. Save all artifacts

    Returns:
        Full evaluation summary dictionary.
    """
    cfg = config or Phase8CEvalConfig()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir = output_dir / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    resolved_cache_dir = Path(cache_dir) if cache_dir else (output_dir / "cache")
    resolved_cache_dir.mkdir(parents=True, exist_ok=True)

    env_info = collect_environment_metadata()
    start_time = time.monotonic()

    # ── 1. Identity Mapping ───────────────────────────────────────────────
    logger.info("Step 1: Loading MovieLens-to-TMDB identity mapping...")
    mapping = load_identity_mapping(dataset_dir)

    from .identity_mapping import generate_identity_coverage_report

    generate_identity_coverage_report(mapping, output_dir)

    # ── 2. Stratified Pilot Selection ─────────────────────────────────────
    logger.info(
        "Step 2: Selecting stratified pilot subset (size=%d, seed=%d)...",
        cfg.pilot_sample_size,
        cfg.seed,
    )
    pilot_ids = select_stratified_pilot_subset(
        dataset=dataset,
        mapping=mapping,
        sample_size=cfg.pilot_sample_size,
        seed=cfg.seed,
    )
    logger.info("Pilot subset: %d movies selected", len(pilot_ids))

    # ── 3. Mock TMDB Retrieval ────────────────────────────────────────────
    logger.info("Step 3: Retrieving mock TMDB metadata (dry-run)...")
    enriched_movies, retrieval_summary = retrieve_mock_tmdb_metadata(
        movie_ids=pilot_ids,
        dataset=dataset,
        mapping=mapping,
    )

    # Build full catalog with enriched movies
    full_enriched_catalog = build_enriched_catalog(dataset, enriched_movies)

    # ── 4. Research Metadata Snapshot ─────────────────────────────────────
    logger.info("Step 4: Creating research metadata snapshot...")
    snapshot_id = f"phase8c_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    snapshot = create_snapshot(
        snapshot_id=snapshot_id,
        movies=full_enriched_catalog,
        movielens_checksum=dataset.raw_files_checksum,
        split_checksum=dataset.split_checksum,
        links_checksum=mapping.links_checksum,
        enriched_count=retrieval_summary.successful,
        failed_count=retrieval_summary.api_errors + retrieval_summary.not_found,
        enrichment_source=cfg.enrichment_source,
        enrichment_config={
            "pilot_sample_size": cfg.pilot_sample_size,
            "seed": cfg.seed,
            "enrichment_source": cfg.enrichment_source,
        },
    )
    save_snapshot(snapshot, snapshot_dir)

    # Field coverage report
    generate_coverage_report(
        enriched_movies=enriched_movies,
        total_catalog_size=len(dataset.movies),
        retrieval_summary=retrieval_summary,
        mapping=mapping,
        output_dir=output_dir,
        snapshot_id=snapshot_id,
    )

    # ── 5. 6-Cell Evaluation Matrix (A–F) ────────────────────────────────
    logger.info("Step 5: Running 6-cell evaluation matrix (A–F)...")
    enriched_dataset = _build_enriched_dataset(dataset, full_enriched_catalog)

    # Cell A: TF-IDF v1.1 — Original
    logger.info("  Cell A: TF-IDF v1.1 (Original Metadata)...")
    cfg_tfidf = TFIDFV11Config(algorithm_name="TFIDF-v1.1 (Original)")
    rec_tfidf_a = BaselineTFIDFRecommender(cfg_tfidf)
    res_a = evaluate_recommender(rec_tfidf_a, cfg_tfidf, dataset)
    ref_tfidf_vectors = rec_tfidf_a.item_vectors

    # Cell B: TF-IDF v1.1 — Enriched
    logger.info("  Cell B: TF-IDF v1.1 (Enriched Metadata)...")
    cfg_tfidf_b = TFIDFV11Config(algorithm_name="TFIDF-v1.1 (Enriched)")
    rec_tfidf_b = BaselineTFIDFRecommender(cfg_tfidf_b)
    res_b = evaluate_recommender(
        rec_tfidf_b, cfg_tfidf_b, enriched_dataset, reference_tfidf_vectors=ref_tfidf_vectors
    )

    # Cell C: Semantic-EN — Original
    logger.info("  Cell C: Semantic-EN (Original Metadata)...")
    cfg_sem_c = SemanticModelConfig(
        algorithm_name="Semantic-EN (Original)",
        model_key="english_minilm" if encoder_override is None else encoder_override.spec.model_key,
        dataset_condition="phase8c_original",
    )
    rec_sem_c = OfflineSemanticRecommender(
        cfg_sem_c,
        cache_dir=resolved_cache_dir,
        allow_download=allow_download,
        encoder=encoder_override,
        batch_size=batch_size,
    )
    res_c = evaluate_recommender(
        rec_sem_c, cfg_sem_c, dataset, reference_tfidf_vectors=ref_tfidf_vectors
    )

    # Cell D: Semantic-EN — Enriched
    logger.info("  Cell D: Semantic-EN (Enriched Metadata)...")
    cfg_sem_d = SemanticModelConfig(
        algorithm_name="Semantic-EN (Enriched)",
        model_key="english_minilm" if encoder_override is None else encoder_override.spec.model_key,
        dataset_condition="phase8c_enriched",
    )
    rec_sem_d = OfflineSemanticRecommender(
        cfg_sem_d,
        cache_dir=resolved_cache_dir,
        allow_download=allow_download,
        encoder=encoder_override,
        batch_size=batch_size,
    )
    res_d = evaluate_recommender(
        rec_sem_d, cfg_sem_d, enriched_dataset, reference_tfidf_vectors=ref_tfidf_vectors
    )

    # Cell E: Semantic-Multi — Original
    logger.info("  Cell E: Semantic-Multi (Original Metadata)...")
    cfg_sem_e = SemanticModelConfig(
        algorithm_name="Semantic-Multi (Original)",
        model_key="multilingual_minilm" if encoder_override is None else encoder_override.spec.model_key,
        dataset_condition="phase8c_original",
    )
    rec_sem_e = OfflineSemanticRecommender(
        cfg_sem_e,
        cache_dir=resolved_cache_dir,
        allow_download=allow_download,
        encoder=encoder_override,
        batch_size=batch_size,
    )
    res_e = evaluate_recommender(
        rec_sem_e, cfg_sem_e, dataset, reference_tfidf_vectors=ref_tfidf_vectors
    )

    # Cell F: Semantic-Multi — Enriched
    logger.info("  Cell F: Semantic-Multi (Enriched Metadata)...")
    cfg_sem_f = SemanticModelConfig(
        algorithm_name="Semantic-Multi (Enriched)",
        model_key="multilingual_minilm" if encoder_override is None else encoder_override.spec.model_key,
        dataset_condition="phase8c_enriched",
    )
    rec_sem_f = OfflineSemanticRecommender(
        cfg_sem_f,
        cache_dir=resolved_cache_dir,
        allow_download=allow_download,
        encoder=encoder_override,
        batch_size=batch_size,
    )
    res_f = evaluate_recommender(
        rec_sem_f, cfg_sem_f, enriched_dataset, reference_tfidf_vectors=ref_tfidf_vectors
    )

    # ── 6. Statistical Comparisons ────────────────────────────────────────
    logger.info("Step 6: Computing statistical comparisons...")
    statistical_comparisons = _compute_phase8c_statistics(
        res_a, res_b, res_c, res_d, res_e, res_f
    )

    # ── 7. Coverage Sensitivity (Exploratory) ─────────────────────────────
    logger.info("Step 7: Computing metadata coverage sensitivity analysis...")
    coverage_sensitivity = _compute_coverage_sensitivity(
        enriched_movies=enriched_movies,
        total_catalog=len(dataset.movies),
        retrieval_summary=retrieval_summary,
        mapping=mapping,
    )

    # ── 8. Temporal Validity Analysis ─────────────────────────────────────
    logger.info("Step 8: Documenting temporal validity constraints...")
    temporal_validity = _build_temporal_validity_analysis()

    total_duration = time.monotonic() - start_time

    # ── 9. Assemble Final Summary ─────────────────────────────────────────
    logger.info("Step 9: Assembling evaluation summary...")

    evaluation_cells = {
        "A_tfidf_original": {
            "cell": "A",
            "model": "TF-IDF v1.1",
            "metadata": "Original",
            "metrics": res_a.aggregate_metrics,
        },
        "B_tfidf_enriched": {
            "cell": "B",
            "model": "TF-IDF v1.1",
            "metadata": "Enriched",
            "enriched_count": retrieval_summary.successful,
            "enrichment_coverage_pct": round(
                retrieval_summary.successful / len(dataset.movies) * 100, 4
            ),
            "metrics": res_b.aggregate_metrics,
        },
        "C_semantic_en_original": {
            "cell": "C",
            "model": "Semantic-EN (all-MiniLM-L6-v2)",
            "metadata": "Original",
            "metrics": res_c.aggregate_metrics,
        },
        "D_semantic_en_enriched": {
            "cell": "D",
            "model": "Semantic-EN (all-MiniLM-L6-v2)",
            "metadata": "Enriched",
            "enriched_count": retrieval_summary.successful,
            "metrics": res_d.aggregate_metrics,
        },
        "E_semantic_multi_original": {
            "cell": "E",
            "model": "Semantic-Multi (paraphrase-multilingual-MiniLM-L12-v2)",
            "metadata": "Original",
            "metrics": res_e.aggregate_metrics,
        },
        "F_semantic_multi_enriched": {
            "cell": "F",
            "model": "Semantic-Multi (paraphrase-multilingual-MiniLM-L12-v2)",
            "metadata": "Enriched",
            "enriched_count": retrieval_summary.successful,
            "metrics": res_f.aggregate_metrics,
        },
    }

    summary_payload = {
        "phase": "Phase 8C — MovieLens-TMDB Identity Mapping, Research Metadata Enrichment, and Controlled Re-evaluation",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": env_info.get("git_commit", ""),
        "environment": env_info,
        "dataset_checksum": dataset.raw_files_checksum,
        "split_checksum": dataset.split_checksum,
        "links_checksum": mapping.links_checksum,
        "snapshot_id": snapshot_id,
        "snapshot_checksum": snapshot.snapshot_checksum,
        "cohort": {
            "catalog_size": dataset.movies_count,
            "total_users": dataset.users_count,
            "evaluated_test_users": res_a.users_with_relevant_items,
            "relevance_threshold": cfg.relevance_threshold,
            "exclude_seen_policy": cfg.exclude_seen_policy,
            "k_values": list(cfg.k_values),
        },
        "identity_mapping": {
            "total_movielens_movies": mapping.total_movielens_movies,
            "movies_with_tmdb_id": mapping.movies_with_tmdb_id,
            "tmdb_coverage_pct": mapping.tmdb_coverage_pct,
            "movies_with_imdb_id": mapping.movies_with_imdb_id,
            "duplicate_tmdb_ids": len(mapping.duplicate_tmdb_ids),
        },
        "enrichment": {
            "pilot_sample_size": cfg.pilot_sample_size,
            "seed": cfg.seed,
            "source": cfg.enrichment_source,
            "retrieval_summary": retrieval_summary.to_dict(),
        },
        "evaluation_cells": evaluation_cells,
        "statistical_comparisons": statistical_comparisons,
        "coverage_sensitivity": coverage_sensitivity,
        "temporal_validity": temporal_validity,
        "total_duration_seconds": round(total_duration, 2),
    }

    # Save artifacts
    summary_path = output_dir / "phase8c_evaluation_summary.json"
    summary_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    sig_path = output_dir / "phase8c_statistical_comparisons.json"
    sig_path.write_text(json.dumps(statistical_comparisons, indent=2), encoding="utf-8")

    _export_6cell_csv(output_dir / "phase8c_6cell_comparison.csv", evaluation_cells)
    _export_per_user_csv(
        output_dir / "phase8c_per_user_metrics.csv",
        [
            ("A_tfidf_original", res_a),
            ("B_tfidf_enriched", res_b),
            ("C_semantic_en_original", res_c),
            ("D_semantic_en_enriched", res_d),
            ("E_semantic_multi_original", res_e),
            ("F_semantic_multi_enriched", res_f),
        ],
    )

    logger.info(
        "Phase 8C evaluation completed in %.1fs. Artifacts → %s",
        total_duration,
        output_dir.resolve(),
    )
    return summary_payload


def _compute_phase8c_statistics(
    res_a: EvaluationResult,
    res_b: EvaluationResult,
    res_c: EvaluationResult,
    res_d: EvaluationResult,
    res_e: EvaluationResult,
    res_f: EvaluationResult,
) -> dict[str, Any]:
    """Compute paired statistical comparisons across all 6 cells."""
    comparisons: dict[str, Any] = {}

    pairs = [
        (
            "rq1_tfidf_enriched_vs_original",
            "Does enriching metadata improve TF-IDF v1.1 quality?",
            res_a, res_b,
        ),
        (
            "rq1_semantic_en_enriched_vs_original",
            "Does enriching metadata improve Semantic-EN quality?",
            res_c, res_d,
        ),
        (
            "rq1_semantic_multi_enriched_vs_original",
            "Does enriching metadata improve Semantic-Multi quality?",
            res_e, res_f,
        ),
        (
            "rq2_tfidf_vs_semantic_en_original",
            "TF-IDF v1.1 vs Semantic-EN on original metadata",
            res_a, res_c,
        ),
        (
            "rq2_tfidf_vs_semantic_en_enriched",
            "TF-IDF v1.1 vs Semantic-EN on enriched metadata",
            res_b, res_d,
        ),
        (
            "rq2_tfidf_vs_semantic_multi_original",
            "TF-IDF v1.1 vs Semantic-Multi on original metadata",
            res_a, res_e,
        ),
        (
            "rq2_tfidf_vs_semantic_multi_enriched",
            "TF-IDF v1.1 vs Semantic-Multi on enriched metadata",
            res_b, res_f,
        ),
        (
            "rq2_semantic_en_vs_multi_original",
            "Semantic-EN vs Semantic-Multi on original metadata",
            res_c, res_e,
        ),
        (
            "rq2_semantic_en_vs_multi_enriched",
            "Semantic-EN vs Semantic-Multi on enriched metadata",
            res_d, res_f,
        ),
    ]

    for key, question, res_baseline, res_candidate in pairs:
        comp: dict[str, Any] = {"research_question": question}
        for k in (5, 10, 20):
            for metric in ("ndcg", "precision", "recall"):
                baseline_scores = _extract_active_ndcg(res_baseline, metric, k)
                candidate_scores = _extract_active_ndcg(res_candidate, metric, k)
                comp[f"{metric}_at_{k}"] = compute_extended_paired_comparison(
                    baseline_scores, candidate_scores
                )
        comparisons[key] = comp

    return comparisons


def _compute_coverage_sensitivity(
    enriched_movies: dict[str, MovieMetadata],
    total_catalog: int,
    retrieval_summary: RetrievalSummary,
    mapping: IdentityMappingResult,
) -> dict[str, Any]:
    """
    Metadata coverage sensitivity analysis.

    Reports whether enrichment coverage is sufficient for conclusive analysis.
    """
    actually_enriched = sum(
        1 for m in enriched_movies.values()
        if m.metadata_enrichment_status in ("applied", "simulated")
    )
    mock_enriched = sum(
        1 for r in retrieval_summary.records
        if r.status == "success" and r.payload and r.payload.get("source") == "mock_catalog"
    )
    simulated_enriched = sum(
        1 for r in retrieval_summary.records
        if r.status == "success" and r.payload and r.payload.get("source") == "simulated_from_movielens"
    )

    coverage_ratio = round(actually_enriched / total_catalog * 100, 4) if total_catalog > 0 else 0.0

    # Determine evidence status
    if mock_enriched >= 50:
        evidence_status = "SUFFICIENT_FOR_EXPLORATORY"
    elif mock_enriched >= 10:
        evidence_status = "PRELIMINARY_EVIDENCE_ONLY"
    else:
        evidence_status = "INSUFFICIENT EVIDENCE"

    return {
        "total_catalog": total_catalog,
        "actually_enriched": actually_enriched,
        "mock_catalog_enriched": mock_enriched,
        "simulated_enriched": simulated_enriched,
        "enrichment_coverage_pct": coverage_ratio,
        "evidence_status": evidence_status,
        "evidence_note": (
            f"Of {total_catalog} movies, {actually_enriched} received metadata enrichment "
            f"({coverage_ratio}% coverage). Only {mock_enriched} used genuine mock TMDB data "
            f"(from Phase 8A catalog); the remaining {simulated_enriched} received simulated "
            f"enrichment based on existing MovieLens fields. Coverage sensitivity analysis "
            f"at granular levels (1%, 5%, 10%, 25%, 50%, 80%, 100%) requires live TMDB API "
            f"access with explicit authorization. Current evidence status: {evidence_status}."
        ),
        "planned_coverage_levels": [1, 5, 10, 25, 50, 80, 100],
        "requires_live_api": True,
    }


def _build_temporal_validity_analysis() -> dict[str, Any]:
    """Document temporal validity constraints for Phase 8C experiments."""
    return {
        "constraint": (
            "MovieLens interactions are historical (user ratings timestamped 1996–2018) "
            "while TMDB metadata is current. This creates a temporal mismatch: TMDB "
            "fields like overview, keywords, and genres may have been edited since the "
            "MovieLens interactions occurred."
        ),
        "time_invariant_fields": [
            "title",
            "original_title",
            "director",
            "cast",
            "release_date",
            "original_language",
        ],
        "potentially_time_varying_fields": [
            "overview",
            "keywords",
            "genres",
            "title_vi",
            "overview_vi",
        ],
        "mitigation": (
            "This experiment does NOT claim to be a strict historical temporal "
            "prediction benchmark. Results should be interpreted as measuring the "
            "effect of metadata quality on recommendation model performance, not "
            "as a causal claim about what would have happened with richer metadata "
            "at the time of user interactions."
        ),
        "recommendation": (
            "Future work should use a time-stamped metadata archive (e.g., Wikidata "
            "revision history) for truly temporal-valid experiments."
        ),
    }


def _export_6cell_csv(
    csv_path: Path, cells: dict[str, Any]
) -> None:
    """Export 6-cell comparison table to CSV."""
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = [
            "cell", "model", "metadata",
            "P@5", "R@5", "NDCG@5", "HR@5",
            "P@10", "R@10", "NDCG@10", "HR@10",
            "Coverage@10", "ILD@10", "Novelty@10",
            "P@20", "R@20", "NDCG@20", "HR@20",
            "Latency_p50_ms", "Latency_p95_ms",
        ]
        writer.writerow(header)
        for _key, cell in cells.items():
            m = cell["metrics"]["by_k"]
            lat = cell["metrics"]["latency"]
            k5, k10, k20 = m["k_5"], m["k_10"], m["k_20"]
            writer.writerow([
                cell["cell"], cell["model"], cell["metadata"],
                k5["precision"], k5["recall"], k5["ndcg"], k5["hit_rate"],
                k10["precision"], k10["recall"], k10["ndcg"], k10["hit_rate"],
                k10["catalog_coverage"], k10["intra_list_diversity"], k10["novelty"],
                k20["precision"], k20["recall"], k20["ndcg"], k20["hit_rate"],
                round(lat["p50_ms"], 4), round(lat["p95_ms"], 4),
            ])


def _export_per_user_csv(
    csv_path: Path,
    results: list[tuple[str, EvaluationResult]],
) -> None:
    """Export per-user metrics for paired verification."""
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = [
            "user_id", "cell_key", "num_train", "num_test_relevant",
            "has_relevant_items", "latency_ms",
            "P@5", "R@5", "NDCG@5", "HR@5", "MAP@5",
            "P@10", "R@10", "NDCG@10", "HR@10", "MAP@10",
            "P@20", "R@20", "NDCG@20", "HR@20", "MAP@20",
        ]
        writer.writerow(header)
        for cell_key, res in results:
            for row in res.per_user_rows:
                csv_row: list[Any] = [
                    row.user_id, cell_key, row.num_train, row.num_test_relevant,
                    int(row.has_relevant_items), round(row.latency_ms, 4),
                ]
                for k in (5, 10, 20):
                    mk = row.metrics_by_k[k]
                    csv_row.extend([
                        mk["precision"], mk["recall"], mk["ndcg"],
                        mk["hit_rate"], mk["map"],
                    ])
                writer.writerow(csv_row)

