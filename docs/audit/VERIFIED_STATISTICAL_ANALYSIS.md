# Verified Statistical Significance & Effect Size Analysis

**Audit Target:** Statistical Validation of TF-IDF v1.0 Baseline vs. TF-IDF v1.1 Final  
**Metric Analyzed:** NDCG@10 (Normalized Discounted Cumulative Gain at rank 10)  
**Evaluated Cohort:** N = 587 paired test users with ≥1 relevant test item (rating ≥ 4.0)  
**Comparison:** Variant E (v1.1) vs. Variant A (v1.0), per-user paired differences Δ_u = NDCG@10_v1.1(u) − NDCG@10_v1.0(u)  
**Source artifact:** [`statistical_significance.json`](file:///d:/TLTN/movie-recommendation-system/backend/reports/experiments/tfidf_v1_1_controlled_ablation/statistical_significance.json)  

---

## FINAL VERDICT

> **STATISTICALLY SIGNIFICANT BUT HIGHLY CONCENTRATED (VALID AND REPRODUCIBLE)**
>
> The improvement is real, robust, and carries zero regressions. However, the effect is concentrated in 3.92% of users (23/587). This must be stated prominently in any thesis or publication.

---

## 1. Summary of Statistical Hypothesis Tests

| Test / Estimator | Test Statistic | p-value / CI | Decision (α = 0.001) | Conclusion |
| :--- | :--- | :--- | :--- | :--- |
| **Paired Student's t-test** | t = 3.5898 | p = 3.587 × 10⁻⁴ | ✅ Reject H₀ | Significant positive shift in mean NDCG@10 |
| **Wilcoxon Signed-Rank Test** | W = 0.0 | p = 2.696 × 10⁻⁵ | ✅ Reject H₀ | Non-parametric significance confirmed; zero regressions |
| **Bootstrap 95% CI (1,000 resamples, seed=42)** | Mean Δ = +0.003414 | [+0.001736, +0.005354] | ✅ CI strictly > 0 | Robust positive effect; lower bound excludes 0 |

All three independent tests converge on the same conclusion: the null hypothesis H₀: μ_Δ ≤ 0 is rejected. The improvement is not a sampling artifact.

---

## 2. Per-User Win / Tie / Loss Decomposition

| Outcome | Count | % of Cohort | Description |
| :--- | :--- | :--- | :--- |
| **Wins (Δ_u > 0)** | **23** | **3.92%** | NDCG@10 improved under v1.1 |
| **Ties (Δ_u = 0)** | **564** | **96.08%** | NDCG@10 completely unchanged |
| **Losses (Δ_u < 0)** | **0** | **0.00%** | NDCG@10 degraded under v1.1 |
| **Total Cohort** | **587** | **100%** | All active test users |

### Effect Size Across User Groups

| Measure | Value |
| :--- | :--- |
| Mean Δ across all 587 users | **+0.003414** (+91.4% relative) |
| Mean Δ across 23 winning users only | **+0.087138** (substantial ranking recovery) |
| Median Δ across all users | **0.000000** |
| Maximum individual gain | **+0.267171** |
| Minimum individual change | **0.000000** (no degradations) |

---

## 3. Mathematical Explanation of W = 0.0

In the Wilcoxon signed-rank test, zero differences are discarded before ranking. The remaining non-zero differences are ranked by absolute value, and the test statistic W is the minimum of:
- W⁺ = sum of ranks for positive differences
- W⁻ = sum of ranks for negative differences

With Losses = 0 across all 587 users:
$$W^- = 0, \quad W^+ = \sum_{i=1}^{23} i = \frac{23 \times 24}{2} = 276, \quad W = \min(276, 0) = 0.0$$

p = 2.696 × 10⁻⁵: Every single user who experienced any change experienced a strictly positive improvement. Not one regression was introduced.

---

## 4. Bootstrap Confidence Interval Verification

Protocol:
- B = 1,000 bootstrap resamples
- Cohort size N = 587 users (sampled with replacement)
- Fixed seed = 42 (reproducible)
- Method: empirical percentile

| Percentile | Value |
| :--- | :--- |
| 2.5th (lower bound) | **+0.001736** |
| 50th (bootstrap median) | **+0.003398** |
| 97.5th (upper bound) | **+0.005354** |

The lower bound (+0.0017) is strictly greater than zero. H₀ is rejected at the 95% confidence level.

---

## 5. Critical Methodological Findings

### Finding 1: Why 96.08% of Users Are Tied

In offline top-K evaluation on a sparse dataset like MovieLens-small:
- Each user has on average only 10–25 held-out test items out of 9,742 catalog movies.
- The TF-IDF baseline's Defect R1 (recommending already-rated training items) primarily affects users who rated many training items that happened to be highly similar to their latent preference vector, and those exact items ended up occupying Top-10 slots.
- For the 23 "winning" users: their Top-10 was previously occupied by training items, and after R1 removal, legitimate relevant test items surfaced into Top-10, yielding large NDCG gains (mean +0.087 per winning user).
- For the remaining 564 users: either their training items were not occupying Top-10 slots under v1.0 (because their profile vectors pointed elsewhere), or the newly promoted items were not among their specific relevant test items.

**This is a well-understood structural property of content-based TF-IDF with sparse interaction data — not a failure of the fix.**

### Finding 2: Mandatory Qualified Reporting

Any thesis or publication MUST NOT state:
- ❌ "Users experienced a 91.4% improvement in recommendation quality."
- ❌ "TF-IDF v1.1 doubles recommendation quality."

The correct scientific statement is:
> "TF-IDF v1.1 yields a statistically significant improvement in mean NDCG@10 (Δ = +0.0034, +91.4% relative, p < 0.001). This improvement is concentrated in 23 of 587 users (3.92%) whose previously-consumed training items were occupying Top-10 recommendation slots under the baseline. For these users, the mean individual NDCG@10 improvement is +0.087. No user experienced a degradation."

### Finding 3: Practical vs. Statistical Significance

| Dimension | Assessment |
| :--- | :--- |
| **Statistical significance** | ✅ Robust at α = 0.001 across 3 independent tests |
| **Correctness improvement** | ✅ R1 definitively prevents a known behavioral defect (recommending already-seen items) |
| **Zero regressions** | ✅ No user is worse off |
| **Universal improvement** | ❌ Only 3.92% of users show measurable offline gain |
| **Ceiling lifted for Phase 6+** | ✅ R1 is a prerequisite for accurate MMR/diversity experiments — without it, diversity reranking would reorder a pool already polluted by training items |

---

## 6. Test-Set Contamination Audit

- **Model hyperparameters tuned on test set?** No. TF-IDF parameters (`max_features`, `ngram_range`, `stop_words`, `norm`) are fixed to production values from `vectorizer.py`. No grid search or tuning was performed on any split.
- **Test set used for early stopping?** Not applicable — TF-IDF is a closed-form vectorization with no iterative training.
- **Validation set purpose:** Present in dataset construction for experimental completeness and temporal non-leakage assertion; not used for any tuning decision in this phase.

**Conclusion: The test set was not contaminated at any point.**

---

## 7. Artifact References

| Artifact | Path |
| :--- | :--- |
| Raw statistical JSON | [`backend/reports/experiments/tfidf_v1_1_controlled_ablation/statistical_significance.json`](file:///d:/TLTN/movie-recommendation-system/backend/reports/experiments/tfidf_v1_1_controlled_ablation/statistical_significance.json) |
| Per-user CSV (paired differences) | [`backend/reports/experiments/tfidf_v1_1_controlled_ablation/ablation_comparison.csv`](file:///d:/TLTN/movie-recommendation-system/backend/reports/experiments/tfidf_v1_1_controlled_ablation/ablation_comparison.csv) |
| Phase 4 per-user CSV | [`backend/reports/experiments/baseline_tfidf_v1_0/per_user_metrics.csv`](file:///d:/TLTN/movie-recommendation-system/backend/reports/experiments/baseline_tfidf_v1_0/per_user_metrics.csv) |
