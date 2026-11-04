"""Tests for Phase 8B SemanticRecommendationCollector and TEC reporting."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from test_center.collectors.semantic_recommendation_collector import (
    REQUIRED_PHASE8B_KEYS,
    SemanticRecommendationCollector,
)
from test_center.config.settings import TECSettings
from test_center.reporting.html_report import generate_html_report
from test_center.reporting.json_report import generate_json_report
from test_center.reporting.markdown_report import (
    generate_markdown_report,
    generate_vietnamese_summary,
)


def _sample_phase8b_summary() -> dict:
    return {
        "phase": "Phase 8B — Semantic Embeddings, Metadata Quality Experiments, and TEC Evaluation",
        "timestamp_utc": "2026-11-04T08:54:59Z",
        "git_commit": "8f3e7071b02c6be51cd99839c0e2acfc519c8fa7",
        "dataset_checksum": "d830d1e560efffd547d0360da5042a5d97884e5cd99dfd145ec9ecc0efbbaa86",
        "split_checksum": "48cc8f10cce949d0add60ad6320bf75668370d1753e5456d6fbd69479f931d67",
        "cohort": {
            "catalog_size": 9742,
            "total_users": 610,
            "evaluated_test_users": 587,
            "relevance_threshold": 4.0,
            "exclude_seen_policy": "train",
            "k_values": [5, 10, 20],
        },
        "condition_a_variants": {
            "tfidf_v1_1": {
                "name": "TF-IDF v1.1 (no MMR)",
                "condition": "A_Original",
                "config_checksum": "c990d62156592b92",
                "metrics": {
                    "latency": {"p50_ms": 5.7412, "p95_ms": 8.9327, "mean_ms": 6.2157},
                    "by_k": {
                        "k_10": {
                            "precision": 0.004600,
                            "recall": 0.006896,
                            "ndcg": 0.007153,
                            "hit_rate": 0.040886,
                            "map": 0.003061,
                            "catalog_coverage": 0.130979,
                            "intra_list_diversity": 0.571880,
                            "novelty": 14.0472,
                        }
                    },
                },
            },
            "semantic_en": {
                "name": "English Semantic Embeddings (all-MiniLM-L6-v2)",
                "condition": "A_Original",
                "config_checksum": "2937b568da6a9791",
                "metrics": {
                    "latency": {"p50_ms": 8.5170, "p95_ms": 10.2296, "mean_ms": 8.6912},
                    "by_k": {
                        "k_10": {
                            "precision": 0.004089,
                            "recall": 0.005347,
                            "ndcg": 0.004930,
                            "hit_rate": 0.040886,
                            "map": 0.001545,
                            "catalog_coverage": 0.050606,
                            "intra_list_diversity": 0.311663,
                            "novelty": 14.5939,
                        }
                    },
                },
            },
        },
        "ablation_2x2": {
            "protocol_b1_full_catalog_partial_enrichment": {
                "protocol": "B1_full_catalog_partial_enrichment",
                "total_catalog_movies": 9742,
                "enriched_movies_matched": 10,
                "enrichment_coverage_ratio": 0.001026,
                "active_users_evaluated": 587,
            },
            "protocol_b2_matched_enriched_subset": {
                "protocol": "B2_matched_enriched_subset",
                "subset_movie_count": 10,
                "active_users_with_relevant_test_items": 33,
                "evidence_status": "NOT ENOUGH EVIDENCE",
            },
        },
        "statistical_comparisons": {
            "rq2_semantic_en_vs_tfidf_original": {
                "research_question": "RQ2a: Do English semantic embeddings (all-MiniLM-L6-v2) outperform TF-IDF v1.1 on Original Metadata?",
                "ndcg_at_10": {
                    "sample_size": 587,
                    "mean_baseline": 0.007153,
                    "mean_variant": 0.004930,
                    "mean_difference": -0.002222,
                    "cohens_d": -0.0486,
                    "t_statistic": -1.1780,
                    "p_value_ttest": 0.2393,
                    "p_value_wilcoxon": 0.4105,
                    "bootstrap_ci_95": [-0.006019, 0.001196],
                    "win_tie_loss": {"wins": 20, "ties": 543, "losses": 24},
                    "statistically_significant_05": False,
                },
            }
        },
        "performance_benchmark": {
            "catalog_size": 9742,
            "evaluated_users": 587,
            "models": {
                "tfidf_v1_1": {
                    "algorithm_name": "TFIDF-v1.1",
                    "dimensions": 5000,
                    "generation_duration_seconds": 0.4839,
                    "cache_load_ms": 483.89,
                    "storage_mb": 0.9364,
                    "peak_memory_mb": 0.9364,
                    "recommendation_latency_p50_ms": 5.7412,
                    "recommendation_latency_p95_ms": 8.9327,
                },
                "semantic_en": {
                    "algorithm_name": "Semantic-MiniLM-EN (Original Metadata)",
                    "model_name": "sentence-transformers/all-MiniLM-L6-v2",
                    "dimensions": 384,
                    "generation_duration_seconds": 29.9943,
                    "cache_load_ms": 108.62,
                    "storage_mb": 14.2556,
                    "peak_memory_mb": 49.7264,
                    "recommendation_latency_p50_ms": 8.5170,
                    "recommendation_latency_p95_ms": 10.2296,
                },
            },
        },
    }


def test_collector_reads_and_validates_phase8b_summary(tmp_path: Path) -> None:
    backend_dir = tmp_path / "backend"
    frontend_dir = tmp_path / "frontend"
    backend_dir.mkdir()
    frontend_dir.mkdir()

    settings = TECSettings.from_root(tmp_path)
    collector = SemanticRecommendationCollector(settings)

    # Missing initially -> None and NOT_RUN
    assert collector.collect_existing() is None
    not_run = collector.collect_or_run()
    assert not_run.status == "NOT_RUN"

    # Write valid summary artifact
    summary = _sample_phase8b_summary()
    collector.summary_path.parent.mkdir(parents=True, exist_ok=True)
    collector.summary_path.write_text(json.dumps(summary), encoding="utf-8")

    collected = collector.collect_existing()
    assert collected is not None
    for key in REQUIRED_PHASE8B_KEYS:
        assert key in collected

    result = collector.collect_or_run()
    assert result.status == "PASS"
    assert result.tests_total == 2
    assert result.tests_passed == 2
    assert result.metadata["dataset_checksum"].startswith("d830d1e5")


def test_reports_render_phase8b_semantic_evaluation(tmp_path: Path) -> None:
    report_data = {
        "metadata": {
            "run_id": "20261104-090000-phase8b",
            "timestamp_utc": "2026-11-04T09:00:00Z",
            "git_commit": "8f3e707",
            "platform_info": "Windows",
        },
        "overall_status": "PASS",
        "summary": {
            "functional": {"total": 10, "passed": 10, "failed": 0, "skipped": 0, "status": "PASS"},
            "backend_tests": {"total": 5, "passed": 5, "failed": 0, "skipped": 0, "status": "PASS"},
            "frontend_tests": {"total": 5, "passed": 5, "failed": 0, "skipped": 0, "status": "PASS"},
            "recommendations": {"status": "PASS", "algorithm": "TF-IDF v1.1 + MMR", "record_count": 3},
            "semantic_recommendation": {
                "status": "PASS",
                "phase": "Phase 8B — Semantic Embeddings, Metadata Quality Experiments, and TEC Evaluation",
                "evaluated_test_users": 587,
                "variant_count": 2,
            },
        },
        "functional_tests": [],
        "recommendation_metrics": {},
        "semantic_recommendation": _sample_phase8b_summary(),
        "known_limitations": [],
    }

    md_path = generate_markdown_report(report_data, tmp_path / "report.md")
    md_text = md_path.read_text(encoding="utf-8")
    assert "Phase 8B — Semantic Embeddings & Metadata Quality Ablation" in md_text
    assert "English Semantic Embeddings (all-MiniLM-L6-v2)" in md_text
    assert "Operational Cost & Resource Benchmark" in md_text

    vi_path = generate_vietnamese_summary(report_data, tmp_path / "bao_cao_tom_tat.md")
    vi_text = vi_path.read_text(encoding="utf-8")
    assert "Đánh Giá Semantic Embeddings & Ablation Chất Lượng Metadata (Phase 8B)" in vi_text
    assert "English Semantic Embeddings (all-MiniLM-L6-v2)" in vi_text

    html_path = generate_html_report(report_data, tmp_path / "report.html")
    html_text = html_path.read_text(encoding="utf-8")
    assert "Phase 8B — Semantic Embeddings" in html_text
    assert "English Semantic Embeddings (all-MiniLM-L6-v2)" in html_text

    generate_json_report(report_data, tmp_path / "summary.json")
    semantic_csv = tmp_path / "semantic_metrics.csv"
    assert semantic_csv.is_file()
    csv_text = semantic_csv.read_text(encoding="utf-8")
    assert "English Semantic Embeddings (all-MiniLM-L6-v2)" in csv_text
