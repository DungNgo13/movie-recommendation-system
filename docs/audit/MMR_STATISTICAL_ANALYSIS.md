# Phase 6: MMR Statistical Analysis

> **Verdict: PARTIALLY VERIFIED — improvements are directionally positive but
> NOT statistically significant at conventional thresholds**

## 1. Summary

No MMR variant achieves statistical significance at p < 0.05 for NDCG@10
improvement over the TF-IDF v1.1 baseline. This is expected given the extreme
user-level sparsity: 92–98% of users have zero NDCG@10 in both conditions.

## 2. Paired t-test Results (NDCG@10)

| Variant | Mean Δ | t-stat | p-value | Significant (p<0.05)? |
|---|---|---|---|---|
| λ=0.3, pool=50 | +0.001000 | 0.7500 | 0.454 | ✗ |
| λ=0.5, pool=50 | +0.001462 | 1.3289 | 0.184 | ✗ |
| λ=0.7, pool=50 | +0.000571 | 1.0190 | 0.309 | ✗ |
| λ=0.9, pool=50 | +0.000683 | 1.7983 | 0.073 | ✗ |
| λ=1.0, pool=50 | +0.000000 | 0.0000 | 1.000 | — (control) |
| **λ=0.3, pool=100** | **+0.002249** | **1.4832** | **0.139** | ✗ |
| λ=0.5, pool=100 | +0.001938 | 1.6089 | 0.108 | ✗ |
| λ=0.7, pool=100 | +0.001355 | 1.7523 | 0.080 | ✗ |
| λ=0.9, pool=100 | +0.000554 | 1.2695 | 0.205 | ✗ |
| λ=1.0, pool=100 | +0.000000 | 0.0000 | 1.000 | — (control) |

## 3. Wilcoxon Signed-Rank Test Results (NDCG@10)

| Variant | p-value (Wilcoxon) | Significant? |
|---|---|---|
| λ=0.3, pool=50 | 0.398 | ✗ |
| λ=0.5, pool=50 | 0.206 | ✗ |
| λ=0.7, pool=50 | 0.341 | ✗ |
| λ=0.9, pool=50 | 0.102 | ✗ |
| λ=0.3, pool=100 | 0.114 | ✗ |
| λ=0.5, pool=100 | 0.114 | ✗ |
| λ=0.7, pool=100 | 0.119 | ✗ |
| λ=0.9, pool=100 | 0.181 | ✗ |

## 4. Bootstrap 95% Confidence Intervals (NDCG@10 Difference)

| Variant | 95% CI | Contains Zero? |
|---|---|---|
| λ=0.3, pool=50 | [−0.001678, +0.003679] | ✓ Yes |
| λ=0.5, pool=50 | [−0.000521, +0.003824] | ✓ Yes |
| λ=0.7, pool=50 | [−0.000590, +0.001830] | ✓ Yes |
| λ=0.9, pool=50 | [−0.000033, +0.001577] | ✓ Yes (barely) |
| **λ=0.3, pool=100** | [−0.000633, +0.005166] | ✓ Yes |
| λ=0.5, pool=100 | [−0.000320, +0.004608] | ✓ Yes |
| λ=0.7, pool=100 | [−0.000119, +0.003096] | ✓ Yes |
| λ=0.9, pool=100 | [−0.000326, +0.001524] | ✓ Yes |

All CIs include zero, confirming statistical non-significance.

## 5. Win/Tie/Loss Counts (NDCG@10)

| Variant | Wins | Ties | Losses | % Tied |
|---|---|---|---|---|
| λ=0.3, pool=50 | 23 | 548 | 16 | 93.4% |
| λ=0.5, pool=50 | 17 | 557 | 13 | 94.9% |
| λ=0.7, pool=50 | 12 | 567 | 8 | 96.6% |
| λ=0.9, pool=50 | 6 | 577 | 4 | 98.3% |
| **λ=0.3, pool=100** | **30** | **540** | **17** | **92.0%** |
| λ=0.5, pool=100 | 21 | 552 | 14 | 94.0% |
| λ=0.7, pool=100 | 16 | 563 | 8 | 95.9% |
| λ=0.9, pool=100 | 8 | 575 | 4 | 98.0% |

## 6. Effect Size Analysis

| Variant | Cohen's d (approx) | Practical Significance |
|---|---|---|
| λ=0.3, pool=100 | ~0.061 | Negligible |
| λ=0.5, pool=100 | ~0.066 | Negligible |
| λ=0.7, pool=100 | ~0.072 | Negligible |

Cohen's d < 0.2 for all variants — effect sizes are negligible by conventional
standards. This is consistent with the observation that improvements are
concentrated among a small subset of users.

## 7. Interpretation

> [!WARNING]
> **Do NOT claim MMR provides a statistically significant NDCG improvement.**
> The correct interpretation is:
>
> 1. MMR provides **large, verified ILD and Coverage improvements** (these are
>    deterministic aggregate metrics, not user-level statistics).
> 2. MMR provides **directionally positive but statistically non-significant
>    NDCG improvements** across all λ and pool configurations.
> 3. The win/tie/loss pattern shows more wins than losses consistently, but
>    the overwhelming majority of users (>92%) are completely unaffected.
> 4. For the ~6-8% of users who ARE affected, MMR tends to help more than harm
>    (positive net wins in all variants).

## 8. Why Significance Was Not Achieved

1. **Extreme sparsity:** Only ~4-6% of users have ANY relevant test items that
   appear in their recommendation lists.
2. **Small sample of affected users:** With only 30 wins and 17 losses (best case),
   the signal is too weak to overcome the noise from 540 tied users.
3. **Low absolute NDCG values:** Baseline NDCG@10 = 0.007153, meaning even a 31%
   relative improvement is only +0.002249 in absolute terms.

## 9. Recommendation

MMR can be deployed as a **diversity-enhancing feature** with confidence that:
- It does NOT degrade relevance (no variant has more losses than wins)
- It provides measurable diversity gains (ILD, Coverage) by construction
- It is safe to enable in production behind a feature flag

For thesis reporting, frame MMR as a **diversity intervention** rather than a
relevance improvement. The NDCG gains are a welcome side effect, not the primary
objective.

## 10. Source Data

Full statistical details: `backend/reports/experiments/mmr_controlled_ablation/mmr_statistical_significance.json`
Per-user metrics: `backend/reports/experiments/mmr_controlled_ablation/mmr_per_user_metrics.csv`

