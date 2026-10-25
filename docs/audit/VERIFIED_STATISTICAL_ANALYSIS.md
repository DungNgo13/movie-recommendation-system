# Verified Statistical Significance & Effect Size Analysis

**Audit Target:** Statistical Validation of TF-IDF v1.0 Baseline vs. TF-IDF v1.1 Final  
**Metric Analyzed:** Normalized Discounted Cumulative Gain at rank 10 (NDCG@10)  
**Evaluated Cohort:** $N = 587$ paired test users with $\ge 1$ relevant test item ($\text{rating} \ge 4.0$)  
**Statistical Verdict:** **STATISTICALLY SIGNIFICANT BUT HIGHLY CONCENTRATED (VALID AND REPRODUCIBLE)**

---

## 1. Summary of Statistical Hypothesis Tests

| Test / Estimator | Test Statistic | p-value / Confidence Interval | Decision ($\alpha = 0.001$) | Conclusion |
| :--- | :--- | :--- | :--- | :--- |
| **Paired Student's t-test** | $t = 3.5898$ | $p = 3.587 \times 10^{-4}$ | **Reject $H_0$** | Significant positive shift in mean NDCG@10 |
| **Wilcoxon Signed-Rank Test** | $W = 0.0$ | $p = 2.696 \times 10^{-5}$ | **Reject $H_0$** | Non-parametric significance confirmed; zero regressions |
| **Bootstrap 95% CI (1,000 resamples)** | Mean $\Delta = +0.003414$ | **$[+0.001736, +0.005354]$** | **Strictly $> 0$** | Robust positive effect; interval excludes zero |

---

## 2. Per-User Win / Tie / Loss Decomposition

A rigorous audit of recommendation metrics requires inspecting the per-user difference distribution ($\Delta_u = \text{NDCG@10}_{v1.1}(u) - \text{NDCG@10}_{v1.0}(u)$):

| Outcome | User Count | Percentage of Cohort | Description |
| :--- | :--- | :--- | :--- |
| **Wins ($\Delta_u > 0$)** | **23** | **3.92%** | Users whose NDCG@10 improved under TF-IDF v1.1 |
| **Ties ($\Delta_u = 0$)** | **564** | **96.08%** | Users whose NDCG@10 remained completely unchanged |
| **Losses ($\Delta_u < 0$)** | **0** | **0.00%** | Users whose NDCG@10 degraded under TF-IDF v1.1 |
| **Total Evaluated Cohort** | **587** | **100.00%** | All test users with $\ge 1$ relevant test item |

### Effect Size Distribution:
- **Mean difference across all 587 users:** $+0.003414$ ($+91.4\%$ relative change)
- **Mean difference across the 23 winning users:** **$+0.087138$** (substantial ranking jump)
- **Median difference across all users:** **$0.000000$**
- **Maximum individual user gain:** **$+0.267171$**
- **Minimum individual user change:** **$0.000000$** (zero degradations)

---

## 3. Critical Methodological Findings & Scientific Interpretation

### Finding 1: Why the Wilcoxon Test Statistic is $W = 0.0$
In the Wilcoxon signed-rank test, differences of zero are discarded, and the remaining absolute differences are ranked. The test statistic $W$ is the smaller of the sum of positive ranks ($W^+$) and the sum of negative ranks ($W^-$):
$$W = \min(W^+, W^-)$$
Because **Losses = 0** across all $587$ users:
- $W^- = 0$
- $W^+ = \sum_{i=1}^{23} i = \frac{23 \times 24}{2} = 276$
- Therefore, $W = 0.0$ and $p = 2.70 \times 10^{-5}$.

Every single user who experienced a change experienced a positive improvement. There was not a single regression in the entire evaluation cohort.

### Finding 2: Prominent Reporting of Tied Users (96.08%)
It is methodologically misleading to interpret a $p < 0.001$ result or a $+91.4\%$ relative improvement as meaning that "users across the board experienced a doubling of recommendation quality."

In reality:
1. **96.08% of users (564 out of 587) had an identical NDCG@10 score of 0.0 or unchanged.**
2. In offline top-K evaluation on sparse interaction datasets like MovieLens (where each user has on average only 10–25 held-out test items out of 9,742 movies), the baseline engine frequently failed to surface any relevant item in the Top-10.
3. For the 23 users (3.92%) where Defect R1 had previously pushed highly-rated training items into Top-10 slots, removing those training items allowed legitimate relevant test items to surface into ranks 1–10, resulting in large individual gains (mean $+0.087$).
4. For the remaining 96% of users, either the items newly promoted into Top-10 were not among the user's specific test items rated $\ge 4.0$, or the user had no training items occupying Top-10 slots.

### Finding 3: Practical vs. Statistical Significance
- **Statistical Significance:** Highly robust ($p < 0.001$, bootstrap CI strictly positive). The improvement is not an artifact of random sampling noise.
- **Practical Significance:** The R1 fix strictly prevents a known bug (recommending movies the user has already rated/seen) and introduces zero regressions. However, because content-based TF-IDF lacks collaborative signals, precision and NDCG remain in the low single-digit percentage range ($0.0072$).
- **Architectural Implication:** Correctness fixes alone cannot solve the fundamental representation limits of TF-IDF. Diversity reranking (MMR in Phase 6) and semantic embeddings / collaborative signals (Phase 7+) are required to lift the remaining 96% of users.

---

## 4. Bootstrap Confidence Interval Verification

Using empirical bootstrapping with $B = 1,000$ iterations and a deterministic seed (`seed = 42`):
- Resampled cohort size: $N = 587$ users with replacement
- 2.5th Percentile: $+0.001736$
- 50th Percentile (Bootstrap Median): $+0.003398$
- 97.5th Percentile: $+0.005354$

Because the lower confidence bound ($+0.0017$) is strictly greater than zero, the null hypothesis $H_0: \mu_\Delta \le 0$ is rejected at the 95% confidence level.
