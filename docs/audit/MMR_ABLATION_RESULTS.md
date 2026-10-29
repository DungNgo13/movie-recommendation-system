# Phase 6: MMR Ablation Results

> **Verdict: VALID AND REPRODUCIBLE**

## 1. Executive Summary

MMR re-ranking **consistently improves both diversity and relevance** across all
tested configurations, an unexpected but verifiable result. The best configuration
(**λ=0.3, pool=100**) achieves:

- **NDCG@10: +31.4%** relative improvement (0.007153 → 0.009401)
- **ILD@10: +51.7%** (0.5719 → 0.8678)
- **Coverage@10: +24.2%** (13.10% → 16.27%)
- **HitRate@10: +45.9%** (4.09% → 5.96%)

> [!IMPORTANT]
> **Qualification:** NDCG@10 improvements are NOT statistically significant at
> p < 0.05 for any variant. This is because 92-94% of users have identical
> (zero) NDCG@10 in both baseline and MMR variants. The improvements are
> concentrated among the ~6-8% of users who receive any relevant recommendations.

## 2. Key Results Table (K=10)

| Variant | NDCG@10 | ΔNDCG | P@10 | R@10 | HR@10 | ILD@10 | ΔILD | Cov@10 | ΔCov | Latency p50 |
|---|---|---|---|---|---|---|---|---|---|---|
| **Baseline (no MMR)** | 0.007153 | — | 0.004600 | 0.006896 | 4.09% | 0.5719 | — | 13.10% | — | 5.71ms |
| **λ=0.3, pool=50** | 0.008152 | +14.0% | 0.005111 | 0.008538 | 4.94% | 0.8044 | +40.7% | 14.31% | +1.21pp | 19.11ms |
| **λ=0.5, pool=50** | 0.008615 | +20.4% | 0.005451 | 0.009137 | 5.28% | 0.7248 | +26.7% | 13.96% | +0.86pp | 19.01ms |
| **λ=0.7, pool=50** | 0.007723 | +8.0% | 0.005111 | 0.007700 | 4.94% | 0.6427 | +12.4% | 13.51% | +0.41pp | 18.43ms |
| **λ=0.9, pool=50** | 0.007836 | +9.5% | 0.005281 | 0.008362 | 4.77% | 0.5894 | +3.1% | 13.24% | +0.14pp | 18.46ms |
| **λ=1.0, pool=50** | 0.007153 | 0.0% | 0.004600 | 0.006896 | 4.09% | 0.5719 | 0.0% | 13.10% | 0.00pp | 18.63ms |
| **λ=0.3, pool=100** | **0.009401** | **+31.4%** | **0.006644** | **0.010516** | **5.96%** | **0.8678** | **+51.7%** | **16.27%** | **+3.17pp** | 35.56ms |
| **λ=0.5, pool=100** | 0.009091 | +27.1% | 0.005451 | 0.010158 | 5.28% | 0.7686 | +34.4% | 14.22% | +1.12pp | 35.04ms |
| **λ=0.7, pool=100** | 0.008508 | +18.9% | 0.005622 | 0.008606 | 5.45% | 0.6624 | +15.8% | 13.69% | +0.60pp | 35.02ms |
| **λ=0.9, pool=100** | 0.007707 | +7.7% | 0.005111 | 0.007936 | 4.77% | 0.5951 | +4.1% | 13.29% | +0.20pp | 35.07ms |
| **λ=1.0, pool=100** | 0.007153 | 0.0% | 0.004600 | 0.006896 | 4.09% | 0.5719 | 0.0% | 13.10% | 0.00pp | 34.68ms |

## 3. Equivalence Control Verification

Both λ=1.0 variants produce **exactly identical** metrics to the baseline at all K values:

| Control | NDCG@10 | ILD@10 | Coverage@10 | Status |
|---|---|---|---|---|
| λ=1.0, pool=50 | 0.007153 | 0.5719 | 13.10% | ✓ IDENTICAL |
| λ=1.0, pool=100 | 0.007153 | 0.5719 | 13.10% | ✓ IDENTICAL |

This confirms the MMR implementation correctly degenerates to pure relevance when λ=1.0.

## 4. Win/Tie/Loss Analysis (NDCG@10)

| Variant | Wins | Ties | Losses | Net Wins |
|---|---|---|---|---|
| λ=0.3, pool=50 | 23 | 548 | 16 | +7 |
| λ=0.5, pool=50 | 17 | 557 | 13 | +4 |
| λ=0.7, pool=50 | 12 | 567 | 8 | +4 |
| λ=0.9, pool=50 | 6 | 577 | 4 | +2 |
| λ=1.0, pool=50 | 0 | 587 | 0 | 0 |
| **λ=0.3, pool=100** | **30** | **540** | **17** | **+13** |
| λ=0.5, pool=100 | 21 | 552 | 14 | +7 |
| λ=0.7, pool=100 | 16 | 563 | 8 | +8 |
| λ=0.9, pool=100 | 8 | 575 | 4 | +4 |
| λ=1.0, pool=100 | 0 | 587 | 0 | 0 |

> [!NOTE]
> **Tied user concentration:** 92–98% of users are tied at zero NDCG in both
> baseline and MMR variants. This means MMR changes affect only the small subset
> of users who already receive relevant recommendations. For those users, MMR
> tends to improve ranking quality by pulling relevant items from deeper in the
> candidate pool.

## 5. Pool Size Effect

Larger candidate pools (100 vs 50) consistently produce:
- **Higher NDCG:** +31.4% vs +14.0% (at λ=0.3)
- **Higher ILD:** +51.7% vs +40.7%
- **Higher Coverage:** +3.17pp vs +1.21pp
- **Higher latency:** ~35ms vs ~19ms (p50)

The pool=100 configuration gives MMR more diversity headroom — more dissimilar
candidates to select from. The trade-off is ~2× latency overhead.

## 6. Latency Overhead

| Pool Size | Baseline p50 | MMR p50 | Overhead | Acceptable? |
|---|---|---|---|---|
| 50 | 5.71ms | ~18.5ms | ~13ms | ✓ Yes |
| 100 | 5.71ms | ~35ms | ~29ms | ⚠ Borderline |

Both remain well under 100ms per-user latency, suitable for real-time API.

## 7. Why MMR Improves NDCG (Explanation)

The counter-intuitive NDCG improvement with MMR is explained by the **pool
expansion effect**: by drawing candidates from the top-50 or top-100 instead
of just the top-10/20, MMR gives relevant items that ranked 11th-50th (or 11th-100th)
a chance to appear in the final list. For users whose relevant items were buried
just below the cutoff, MMR's diversity penalty displaces a near-duplicate
high-scored item and promotes a relevant but previously-excluded candidate.

## 8. Recommended Configuration

Based on validation-set analysis:

| Parameter | Recommended Value | Rationale |
|---|---|---|
| **λ** | 0.5 | Best balance: +27% NDCG, +34% ILD at pool=100 |
| **Pool size** | 50 | Acceptable diversity gain (+20% NDCG, +27% ILD) with lower latency |
| **Alternative** | λ=0.3, pool=100 | Maximum diversity if latency budget allows |

## 9. Source Artifacts

All results reproduced from:
- `backend/reports/experiments/mmr_controlled_ablation/mmr_ablation_summary.json`
- `backend/reports/experiments/mmr_controlled_ablation/mmr_ablation_comparison.csv`
- `backend/reports/experiments/mmr_controlled_ablation/mmr_per_user_metrics.csv`

