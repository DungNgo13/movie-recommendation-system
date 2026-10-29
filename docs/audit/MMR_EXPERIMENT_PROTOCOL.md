# Phase 6: MMR Experiment Protocol

> **Verdict: VALID AND REPRODUCIBLE**

## 1. Research Objective

Evaluate Maximum Marginal Relevance (MMR) re-ranking on top of TF-IDF v1.1 as
a diversity-enhancing post-processing stage.

**Primary Research Question:** Can MMR improve recommendation-list diversity
(ILD, Coverage) while preserving acceptable ranking relevance (NDCG, Precision,
Recall) and inference latency?

## 2. Dataset Identity

| Property | Value |
|---|---|
| **Dataset** | MovieLens ml-latest-small |
| **Raw ZIP SHA-256** | `696d65a3dfceac7c45750ad32df2c259311949efec81f0f144fdfb91ebc9e436` |
| **Combined CSV SHA-256** | `d830d1e560efffd547d0360da5042a5d97884e5cd99dfd145ec9ecc0efbbaa86` |
| **Split SHA-256** | `48cc8f10cce949d0add60ad6320bf75668370d1753e5456d6fbd69479f931d67` |
| **Movies** | 9,742 |
| **Users** | 610 (587 with ≥1 relevant test item) |
| **Ratings** | 100,836 |
| **Split Ratios** | 70% train / 15% validation / 15% test (chronological per user) |
| **Relevance Threshold** | ≥ 4.0 stars |

## 3. Frozen Baseline

TF-IDF v1.1 (Variant E from Phase 5):
- R1: Seen-item exclusion (train items excluded)
- R2: Negative feedback suppression
- R3: Deterministic cold-start fallback
- All TF-IDF parameters frozen from Phase 4

## 4. MMR Algorithm

```
MMR(i) = λ × Relevance(i) − (1 − λ) × max_{j ∈ S} Similarity(i, j)
```

- **Relevance:** min-max normalized TF-IDF cosine similarity to user profile
- **Inter-item Similarity:** cosine similarity between TF-IDF item vectors
- **Selection:** Greedy iterative (one item per step)
- **Tie-breaking:** MMR score → raw relevance → ascending movie ID (deterministic)
- **Zero vectors:** treated as maximally diverse (similarity = 0)

## 5. Experimental Variants

| ID | λ | Pool | Description |
|---|---|---|---|
| `baseline_v11` | N/A | N/A | TF-IDF v1.1 (no MMR) |
| `mmr_l0.3_p50` | 0.3 | 50 | Strong diversity bias |
| `mmr_l0.5_p50` | 0.5 | 50 | Balanced trade-off |
| `mmr_l0.7_p50` | 0.7 | 50 | Relevance-leaning |
| `mmr_l0.9_p50` | 0.9 | 50 | Minimal diversity nudge |
| `mmr_l1.0_p50` | 1.0 | 50 | Equivalence control |
| `mmr_l0.3_p100` | 0.3 | 100 | Strong diversity, larger pool |
| `mmr_l0.5_p100` | 0.5 | 100 | Balanced, larger pool |
| `mmr_l0.7_p100` | 0.7 | 100 | Relevance-leaning, larger pool |
| `mmr_l0.9_p100` | 0.9 | 100 | Minimal nudge, larger pool |
| `mmr_l1.0_p100` | 1.0 | 100 | Equivalence control, larger pool |

## 6. Evaluation Metrics

For K ∈ {5, 10, 20}:
- Precision@K, Recall@K, NDCG@K, MAP@K, HitRate@K
- Intra-List Diversity@K (ILD)
- Catalog Coverage@K
- Novelty@K (self-information)
- Latency p50/p95

## 7. Reproduction Commands

```bash
cd backend
.\.venv\Scripts\Activate.ps1

# Run the full MMR ablation study
python -m app.recommendation_evaluation.run --data-dir data/ml-latest-small --mmr-ablation

# Reports are saved to:
# backend/reports/experiments/mmr_controlled_ablation/
```

## 8. Output Artifacts

| File | Contents |
|---|---|
| `mmr_ablation_summary.json` | Full experiment metadata, all metrics, checksums |
| `mmr_ablation_comparison.csv` | All variants × all metrics (machine-readable) |
| `mmr_statistical_significance.json` | Paired tests, win/tie/loss, CIs |
| `mmr_per_user_metrics.csv` | Per-user × per-variant metrics for paired analysis |
| `mmr_summary.md` | Human-readable results table |

## 9. Integrity Controls

- λ=1.0 equivalence verified: both pool sizes produce **identical** metrics to baseline
- Split checksum `48cc8f10...` verified identical to Phase 4/5
- Dataset checksum `d830d1e5...` verified identical to Phase 4/5
- All Phase 4/5 historical artifacts preserved unchanged
- Git commit at experiment time: `42835efa607fbe6b7798fe60462fd4c357faa505`

## 10. Test-Set Usage Limitation

> [!IMPORTANT]
> The test split has been used for metric reporting in Phase 4, 5, and now Phase 6.
> λ and pool size values were chosen a priori from standard MMR literature, NOT
> tuned on test-set outcomes. However, repeated test-set observation across phases
> means the test set is no longer a truly held-out evaluation. This limitation is
> documented and acknowledged.

