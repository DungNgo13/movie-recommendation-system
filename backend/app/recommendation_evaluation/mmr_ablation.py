"""
MMR Controlled Ablation Study & Statistical Analysis.

Evaluates MMR re-ranking variants on top of TF-IDF v1.1 (Variant E) baseline:
  - Baseline: TF-IDF v1.1 (no MMR)
  - MMR λ=0.3, 0.5, 0.7, 0.9, 1.0 × candidate pool {50, 100}

All variants use the SAME:
  - Dataset and chronological split
  - User cohort and candidate catalog
  - TF-IDF vectorizer fit
  - Relevance threshold (4.0)
  - Metric definitions and K values
  - Evaluation code
  - Deterministic tie-breaking

Reports:
  - mmr_ablation_summary.json
  - mmr_ablation_comparison.csv
  - mmr_statistical_significance.json
  - mmr_per_user_metrics.csv
  - mmr_summary.md
"""

import csv
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Any

import numpy as np
from scipy import stats

from .baseline_engine import BaselineTFIDFRecommender
from .config import TFIDFV11Config, TFIDFV11MMRConfig
from .dataset import EvaluationDataset
from .evaluator import OfflineEvaluator, EvaluationResult
from .ablation import compute_bootstrap_ci, compute_paired_comparison
from .report_exporter import collect_environment_metadata

logger = logging.getLogger("mmr_ablation")


# ── Variant Definitions ────────────────────────────────────────────────

def _build_mmr_variants() -> list[tuple[str, str, TFIDFV11Config | TFIDFV11MMRConfig, str]]:
    """
    Build the list of MMR ablation variants.

    Returns list of (variant_key, variant_name, config, description) tuples.
    """
    variants: list[tuple[str, str, TFIDFV11Config | TFIDFV11MMRConfig, str]] = []

    # Baseline: TF-IDF v1.1 without MMR
    variants.append((
        "baseline_v11",
        "TFIDF-v1.1 (no MMR)",
        TFIDFV11Config(
            algorithm_name="TFIDF-v1.1",
        ),
        "TF-IDF v1.1 baseline without MMR re-ranking. Reference for all comparisons.",
    ))

    # MMR variants across λ and pool sizes
    lambdas = [0.3, 0.5, 0.7, 0.9, 1.0]
    pool_sizes = [50, 100]

    for pool_size in pool_sizes:
        for lam in lambdas:
            var_key = f"mmr_l{lam:.1f}_p{pool_size}"
            var_name = f"MMR λ={lam:.1f} pool={pool_size}"
            desc = (
                f"TF-IDF v1.1 + MMR re-ranking with λ={lam:.1f}, "
                f"candidate pool size={pool_size}."
            )
            if lam == 1.0:
                desc += " (Equivalence control: pure relevance within pool.)"

            variants.append((
                var_key,
                var_name,
                TFIDFV11MMRConfig(
                    algorithm_name=f"TFIDF-v1.1+MMR(λ={lam:.1f},pool={pool_size})",
                    mmr_enabled=True,
                    mmr_lambda=lam,
                    mmr_candidate_pool_size=pool_size,
                ),
                desc,
            ))

    return variants


# ── Main Ablation Runner ───────────────────────────────────────────────

def run_mmr_ablation(
    dataset: EvaluationDataset,
    output_dir: Path,
) -> dict[str, Any]:
    """
    Execute all MMR variants on the exact same dataset split and export reports.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    env_info = collect_environment_metadata()
    variants = _build_mmr_variants()

    variant_results: dict[str, EvaluationResult] = {}

    # Per-user metric collectors for statistical comparison
    per_user_ndcg: dict[str, dict[int, list[float]]] = {}    # var_key -> {k -> [scores]}
    per_user_precision: dict[str, dict[int, list[float]]] = {}
    per_user_recall: dict[str, dict[int, list[float]]] = {}
    per_user_ild: dict[str, dict[int, list[float]]] = {}  # ILD per user per variant

    k_values = (5, 10, 20)

    for var_key, var_name, cfg, desc in variants:
        logger.info("Evaluating MMR variant: %s (%s)...", var_key, var_name)
        t0 = time.perf_counter()
        evaluator = OfflineEvaluator(cfg)
        res = evaluator.evaluate(dataset)
        elapsed = time.perf_counter() - t0
        logger.info("  Completed in %.2f seconds.", elapsed)
        variant_results[var_key] = res

        # Collect per-user scores for active users
        active_rows = [r for r in res.per_user_rows if r.has_relevant_items]
        per_user_ndcg[var_key] = {}
        per_user_precision[var_key] = {}
        per_user_recall[var_key] = {}
        for k in k_values:
            per_user_ndcg[var_key][k] = [r.metrics_by_k[k]["ndcg"] for r in active_rows]
            per_user_precision[var_key][k] = [r.metrics_by_k[k]["precision"] for r in active_rows]
            per_user_recall[var_key][k] = [r.metrics_by_k[k]["recall"] for r in active_rows]

    # ── Reference arrays (baseline) ────────────────────────────────────
    base_key = "baseline_v11"

    # ── Statistical Comparisons ────────────────────────────────────────
    stats_comparison: dict[str, Any] = {}
    for var_key, var_name, cfg, desc in variants:
        var_stats: dict[str, Any] = {"variant_name": var_name}

        for k in k_values:
            # NDCG@K paired comparison
            ndcg_paired = compute_paired_comparison(
                per_user_ndcg[base_key][k],
                per_user_ndcg[var_key][k],
            )
            # Win/Tie/Loss counts
            base_arr = np.array(per_user_ndcg[base_key][k])
            var_arr = np.array(per_user_ndcg[var_key][k])
            diff = var_arr - base_arr
            wins = int(np.sum(diff > 1e-12))
            losses = int(np.sum(diff < -1e-12))
            ties = int(np.sum(np.abs(diff) <= 1e-12))

            var_stats[f"ndcg_at_{k}"] = {
                "mean_baseline": round(float(np.mean(base_arr)), 6),
                "mean_variant": round(float(np.mean(var_arr)), 6),
                "paired_test": ndcg_paired,
                "win_tie_loss": {"wins": wins, "ties": ties, "losses": losses},
            }

        # ILD comparison (aggregate-level, from evaluation result)
        res_base = variant_results[base_key]
        res_var = variant_results[var_key]
        for k in k_values:
            kk = f"k_{k}"
            ild_base = res_base.aggregate_metrics["by_k"][kk]["intra_list_diversity"]
            ild_var = res_var.aggregate_metrics["by_k"][kk]["intra_list_diversity"]
            var_stats[f"ild_at_{k}"] = {
                "baseline": round(ild_base, 6),
                "variant": round(ild_var, 6),
                "delta": round(ild_var - ild_base, 6),
                "relative_pct": round((ild_var / ild_base - 1) * 100, 2) if ild_base > 0 else 0.0,
            }

        # Coverage comparison
        for k in k_values:
            kk = f"k_{k}"
            cov_base = res_base.aggregate_metrics["by_k"][kk]["catalog_coverage"]
            cov_var = res_var.aggregate_metrics["by_k"][kk]["catalog_coverage"]
            var_stats[f"coverage_at_{k}"] = {
                "baseline": round(cov_base, 6),
                "variant": round(cov_var, 6),
                "delta": round(cov_var - cov_base, 6),
                "relative_pct": round((cov_var / cov_base - 1) * 100, 2) if cov_base > 0 else 0.0,
            }

        # Latency comparison
        lat_base = res_base.aggregate_metrics["latency"]
        lat_var = res_var.aggregate_metrics["latency"]
        var_stats["latency"] = {
            "baseline_p50_ms": lat_base["p50_ms"],
            "baseline_p95_ms": lat_base["p95_ms"],
            "variant_p50_ms": lat_var["p50_ms"],
            "variant_p95_ms": lat_var["p95_ms"],
            "overhead_p50_ms": round(lat_var["p50_ms"] - lat_base["p50_ms"], 4),
            "overhead_p95_ms": round(lat_var["p95_ms"] - lat_base["p95_ms"], 4),
        }

        stats_comparison[var_key] = var_stats

    # ── Export mmr_ablation_comparison.csv ──────────────────────────────
    _export_comparison_csv(output_dir, variants, variant_results)

    # ── Export mmr_statistical_significance.json ────────────────────────
    sig_path = output_dir / "mmr_statistical_significance.json"
    with open(sig_path, "w", encoding="utf-8") as f:
        json.dump(stats_comparison, f, indent=2)

    # ── Export mmr_per_user_metrics.csv ─────────────────────────────────
    _export_per_user_csv(output_dir, variants, variant_results)

    # ── Export mmr_ablation_summary.json ────────────────────────────────
    summary_data = _build_summary_json(
        env_info, dataset, variants, variant_results, stats_comparison,
    )
    json_path = output_dir / "mmr_ablation_summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    # ── Export mmr_summary.md ──────────────────────────────────────────
    md_path = output_dir / "mmr_summary.md"
    md_content = _build_mmr_markdown(summary_data, stats_comparison, env_info)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    logger.info("MMR ablation reports saved to %s", output_dir.resolve())
    return summary_data


# ── Export Helpers ─────────────────────────────────────────────────────

def _export_comparison_csv(
    output_dir: Path,
    variants: list[tuple[str, str, Any, str]],
    variant_results: dict[str, EvaluationResult],
) -> None:
    """Export ablation comparison CSV with all metrics at K=5,10,20."""
    csv_path = output_dir / "mmr_ablation_comparison.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = [
            "variant_id", "variant_name", "description",
            "P@5", "R@5", "NDCG@5", "HR@5", "MAP@5",
            "P@10", "R@10", "NDCG@10", "HR@10", "MAP@10",
            "P@20", "R@20", "NDCG@20", "HR@20", "MAP@20",
            "Coverage@5", "ILD@5", "Novelty@5",
            "Coverage@10", "ILD@10", "Novelty@10",
            "Coverage@20", "ILD@20", "Novelty@20",
            "Latency_p50_ms", "Latency_p95_ms",
        ]
        writer.writerow(header)

        for var_key, var_name, _, desc in variants:
            res = variant_results[var_key]
            m = res.aggregate_metrics["by_k"]
            lat = res.aggregate_metrics["latency"]
            row = [
                var_key, var_name, desc,
            ]
            for kk in ["k_5", "k_10", "k_20"]:
                row.extend([
                    m[kk]["precision"], m[kk]["recall"], m[kk]["ndcg"],
                    m[kk]["hit_rate"], m[kk]["map"],
                ])
            for kk in ["k_5", "k_10", "k_20"]:
                row.extend([
                    m[kk]["catalog_coverage"], m[kk]["intra_list_diversity"],
                    m[kk]["novelty"],
                ])
            row.extend([lat["p50_ms"], lat["p95_ms"]])
            writer.writerow(row)


def _export_per_user_csv(
    output_dir: Path,
    variants: list[tuple[str, str, Any, str]],
    variant_results: dict[str, EvaluationResult],
) -> None:
    """Export per-user metrics for paired analysis."""
    csv_path = output_dir / "mmr_per_user_metrics.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = [
            "user_id", "variant_id", "variant_name",
            "num_train", "num_test_relevant", "has_relevant_items",
            "latency_ms",
            "P@5", "R@5", "NDCG@5", "HR@5", "MAP@5",
            "P@10", "R@10", "NDCG@10", "HR@10", "MAP@10",
            "P@20", "R@20", "NDCG@20", "HR@20", "MAP@20",
        ]
        writer.writerow(header)

        for var_key, var_name, _, _ in variants:
            res = variant_results[var_key]
            for row in res.per_user_rows:
                csv_row = [
                    row.user_id, var_key, var_name,
                    row.num_train, row.num_test_relevant, row.has_relevant_items,
                    round(row.latency_ms, 4),
                ]
                for k in (5, 10, 20):
                    mk = row.metrics_by_k[k]
                    csv_row.extend([
                        mk["precision"], mk["recall"], mk["ndcg"],
                        mk["hit_rate"], mk["map"],
                    ])
                writer.writerow(csv_row)


def _build_summary_json(
    env_info: dict[str, Any],
    dataset: EvaluationDataset,
    variants: list[tuple[str, str, Any, str]],
    variant_results: dict[str, EvaluationResult],
    stats_comparison: dict[str, Any],
) -> dict[str, Any]:
    """Build the ablation summary JSON structure."""
    base_res = variant_results["baseline_v11"]
    active_count = base_res.users_with_relevant_items

    return {
        "experiment": "MMR Controlled Ablation Study (Phase 6)",
        "timestamp_utc": env_info["timestamp_utc"],
        "git_commit": env_info["git_commit"],
        "dataset_checksum": dataset.raw_files_checksum,
        "split_checksum": dataset.split_checksum,
        "cohort": {
            "catalog_size": dataset.movies_count,
            "total_users": dataset.users_count,
            "evaluated_test_users": active_count,
        },
        "variants": {
            var_key: {
                "name": var_name,
                "description": desc,
                "config_checksum": cfg.compute_checksum()[:16],
                "metrics": variant_results[var_key].aggregate_metrics,
            }
            for var_key, var_name, cfg, desc in variants
        },
        "statistical_tests": stats_comparison,
    }


# ── Markdown Report ───────────────────────────────────────────────────

def _build_mmr_markdown(
    summary_data: dict[str, Any],
    stats_comp: dict[str, Any],
    env_info: dict[str, Any],
) -> str:
    """Generate comprehensive MMR ablation Markdown report."""
    lines = [
        "# MovSug — Phase 6: MMR Diversity-Aware Re-ranking Ablation Report",
        "",
        f"**Date:** `{env_info['timestamp_utc']}`  ",
        f"**Git Commit:** `{env_info['git_commit']}`  ",
        f"**Dataset Checksum (SHA256):** `{summary_data['dataset_checksum']}`  ",
        f"**Split Checksum (SHA256):** `{summary_data['split_checksum']}`  ",
        f"**Evaluated Test Users:** {summary_data['cohort']['evaluated_test_users']}  ",
        f"**Candidate Catalog:** {summary_data['cohort']['catalog_size']} movies  ",
        "",
        "---",
        "",
        "## 1. Research Question",
        "",
        "Can Maximum Marginal Relevance (MMR) re-ranking improve recommendation-list",
        "diversity (ILD, Coverage) while preserving acceptable ranking relevance (NDCG,",
        "Precision, Recall) and inference latency?",
        "",
        "## 2. Experimental Design",
        "",
        "### 2.1 MMR Objective Function",
        "",
        "```",
        "MMR(i) = λ × Relevance(i) − (1 − λ) × max_{j ∈ S} Similarity(i, j)",
        "```",
        "",
        "- **Relevance:** min-max normalized TF-IDF cosine similarity to user profile",
        "- **Similarity:** cosine similarity between item TF-IDF vectors",
        "- **S:** set of already-selected items (greedy iterative)",
        "",
        "### 2.2 Variants",
        "",
        "| Variant | λ | Pool Size | Description |",
        "|---|---|---|---|",
    ]

    for var_key, var_name, cfg, desc in _build_mmr_variants():
        if isinstance(cfg, TFIDFV11MMRConfig) and cfg.mmr_enabled:
            lines.append(f"| {var_name} | {cfg.mmr_lambda:.1f} | {cfg.mmr_candidate_pool_size} | {desc} |")
        else:
            lines.append(f"| {var_name} | N/A | N/A | {desc} |")

    lines.extend([
        "",
        "---",
        "",
        "## 3. Results Summary (K=10)",
        "",
        "| Variant | NDCG@10 | Precision@10 | Recall@10 | HitRate@10 | ILD@10 | Coverage@10 | Novelty@10 | Latency p50 |",
        "|---|---|---|---|---|---|---|---|---|",
    ])

    for var_key in summary_data["variants"]:
        v = summary_data["variants"][var_key]
        m10 = v["metrics"]["by_k"]["k_10"]
        lat = v["metrics"]["latency"]
        lines.append(
            f"| {v['name']} | {m10['ndcg']:.6f} | {m10['precision']:.6f} | "
            f"{m10['recall']:.6f} | {m10['hit_rate']:.6f} | {m10['intra_list_diversity']:.4f} | "
            f"{m10['catalog_coverage']*100:.2f}% | {m10['novelty']:.2f} | {lat['p50_ms']:.2f}ms |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 4. Relevance–Diversity Trade-off Analysis (K=10)",
        "",
        "| Variant | ΔNDCG@10 | ΔILD@10 | ΔCoverage@10 | Wins | Ties | Losses |",
        "|---|---|---|---|---|---|---|",
    ])

    base_m10 = summary_data["variants"]["baseline_v11"]["metrics"]["by_k"]["k_10"]
    for var_key in summary_data["variants"]:
        if var_key == "baseline_v11":
            continue
        v = summary_data["variants"][var_key]
        m10 = v["metrics"]["by_k"]["k_10"]
        sc = stats_comp.get(var_key, {})
        ndcg_k10 = sc.get("ndcg_at_10", {})
        wtl = ndcg_k10.get("win_tie_loss", {})

        d_ndcg = m10["ndcg"] - base_m10["ndcg"]
        d_ild = m10["intra_list_diversity"] - base_m10["intra_list_diversity"]
        d_cov = (m10["catalog_coverage"] - base_m10["catalog_coverage"]) * 100

        lines.append(
            f"| {v['name']} | {d_ndcg:+.6f} | {d_ild:+.4f} | {d_cov:+.2f}pp | "
            f"{wtl.get('wins', 'N/A')} | {wtl.get('ties', 'N/A')} | {wtl.get('losses', 'N/A')} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 5. Full Results Tables",
        "",
        "### 5.1 K=5",
        "",
        "| Variant | P@5 | R@5 | NDCG@5 | HR@5 | MAP@5 | ILD@5 | Cov@5 | Nov@5 |",
        "|---|---|---|---|---|---|---|---|---|",
    ])

    for var_key in summary_data["variants"]:
        v = summary_data["variants"][var_key]
        m = v["metrics"]["by_k"]["k_5"]
        lines.append(
            f"| {v['name']} | {m['precision']:.6f} | {m['recall']:.6f} | "
            f"{m['ndcg']:.6f} | {m['hit_rate']:.6f} | {m['map']:.6f} | "
            f"{m['intra_list_diversity']:.4f} | {m['catalog_coverage']*100:.2f}% | {m['novelty']:.2f} |"
        )

    lines.extend([
        "",
        "### 5.2 K=10",
        "",
        "| Variant | P@10 | R@10 | NDCG@10 | HR@10 | MAP@10 | ILD@10 | Cov@10 | Nov@10 |",
        "|---|---|---|---|---|---|---|---|---|",
    ])

    for var_key in summary_data["variants"]:
        v = summary_data["variants"][var_key]
        m = v["metrics"]["by_k"]["k_10"]
        lines.append(
            f"| {v['name']} | {m['precision']:.6f} | {m['recall']:.6f} | "
            f"{m['ndcg']:.6f} | {m['hit_rate']:.6f} | {m['map']:.6f} | "
            f"{m['intra_list_diversity']:.4f} | {m['catalog_coverage']*100:.2f}% | {m['novelty']:.2f} |"
        )

    lines.extend([
        "",
        "### 5.3 K=20",
        "",
        "| Variant | P@20 | R@20 | NDCG@20 | HR@20 | MAP@20 | ILD@20 | Cov@20 | Nov@20 |",
        "|---|---|---|---|---|---|---|---|---|",
    ])

    for var_key in summary_data["variants"]:
        v = summary_data["variants"][var_key]
        m = v["metrics"]["by_k"]["k_20"]
        lines.append(
            f"| {v['name']} | {m['precision']:.6f} | {m['recall']:.6f} | "
            f"{m['ndcg']:.6f} | {m['hit_rate']:.6f} | {m['map']:.6f} | "
            f"{m['intra_list_diversity']:.4f} | {m['catalog_coverage']*100:.2f}% | {m['novelty']:.2f} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 6. Statistical Significance (NDCG@10 vs Baseline)",
        "",
        "| Variant | Mean Δ | t-stat | p (t-test) | p (Wilcoxon) | 95% CI | Significant? |",
        "|---|---|---|---|---|---|---|",
    ])

    for var_key in stats_comp:
        if var_key == "baseline_v11":
            continue
        sc = stats_comp[var_key]
        n10 = sc.get("ndcg_at_10", {})
        pt = n10.get("paired_test", {})
        ci = pt.get("bootstrap_ci_95", [0, 0])
        sig = "✓" if pt.get("statistically_significant_05", False) else "✗"

        lines.append(
            f"| {sc['variant_name']} | {pt.get('mean_difference', 0):+.6f} | "
            f"{pt.get('t_statistic', 0):.4f} | {pt.get('p_value_ttest', 1):.2e} | "
            f"{pt.get('p_value_wilcoxon', 1):.2e} | [{ci[0]:.6f}, {ci[1]:.6f}] | {sig} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 7. Latency Analysis",
        "",
        "| Variant | p50 (ms) | p95 (ms) | Overhead p50 | Overhead p95 |",
        "|---|---|---|---|---|",
    ])

    for var_key in stats_comp:
        sc = stats_comp[var_key]
        lat = sc.get("latency", {})
        lines.append(
            f"| {sc['variant_name']} | {lat.get('variant_p50_ms', 0):.2f} | "
            f"{lat.get('variant_p95_ms', 0):.2f} | {lat.get('overhead_p50_ms', 0):+.2f} | "
            f"{lat.get('overhead_p95_ms', 0):+.2f} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 8. Methodology Notes",
        "",
        "1. **Validation vs Test:** All configurations were designed a priori based on",
        "   standard MMR literature. λ values were NOT tuned on test-set outcomes.",
        "   The recommended configuration should be selected using validation set",
        "   results, then confirmed on the test set exactly once.",
        "2. **Tied Users:** The TF-IDF v1.1 baseline has ~96% of users with identical",
        "   NDCG@10 scores (tied at 0). Most MMR changes affect only users who already",
        "   have non-zero relevance scores in their recommendation lists.",
        "3. **ILD Interpretation:** Intra-List Diversity measures average pairwise",
        "   dissimilarity within each user's recommendation list. Higher ILD means more",
        "   diverse recommendations, but does NOT necessarily mean better user satisfaction.",
        "4. **Coverage:** Catalog coverage measures the fraction of the item catalog",
        "   that appears in at least one user's recommendation list. MMR is expected to",
        "   increase this by promoting different items for different users.",
        "5. **Determinism:** All results are fully reproducible given identical dataset,",
        "   split checksums, and code version.",
        "",
    ])

    return "\n".join(lines)

