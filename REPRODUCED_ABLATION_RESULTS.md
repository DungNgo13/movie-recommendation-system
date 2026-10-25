# Reproduced Controlled Ablation Results: TF-IDF v1.0 vs. v1.1

**Audit Target:** MovSug TF-IDF v1.1 Recommendation Engine Ablation Study  
**Reproducibility Verdict:** **VALID AND REPRODUCIBLE**  
**Execution Timestamp:** 2026-10-25T14:31:06Z  
**Dataset Checksum (Combined CSV SHA-256):** `d830d1e560efffd547d0360da5042a5d97884e5cd99dfd145ec9ecc0efbbaa86`  
**Split Checksum (SHA-256):** `48cc8f10cce949d0add60ad6320bf75668370d1753e5456d6fbd69479f931d67`  
**Candidate Catalog:** 9,742 movies  
**Evaluation Cohort:** 610 total users, 587 active users with $\ge 1$ relevant test item ($\text{rating} \ge 4.0$)

---

## 1. Controlled Ablation Experimental Design

All five variants were executed on the exact same dataset, chronological split, candidate pool, and feature representation:

- **Variant A (`TFIDF-v1.0-as-is`):** Unmodified production baseline. Defect R1 active: previously rated training items are NOT excluded. Defect R2 active: negative ratings can be overridden by watch progress. Cold-start uses database-dependent release date ordering.
- **Variant B (`TFIDF-v1.0 + R1`):** Seen-Item Exclusion fix only. Training interactions are strictly removed from candidate pools (`exclude_seen="train"`).
- **Variant C (`TFIDF-v1.0 + R2`):** Negative Feedback Precedence fix only. Explicit 1–2★ ratings suppress positive weight from watch history. *(Note: MovieLens contains ratings only and no watch events; hence on MovieLens this variant is **NOT MEASURABLE** and numerically identical to Variant A. Correctness is proven via unit tests in `tests/test_recommendation_fixes.py`)*.
- **Variant D (`TFIDF-v1.0 + R1 + R2`):** Combined R1 Seen-Item Exclusion and R2 Negative Feedback Precedence.
- **Variant E (`TFIDF-v1.1 Final`):** Complete TF-IDF v1.1 engine: R1 Seen-Item Exclusion + R2 Negative Feedback Precedence + R3 Deterministic Cold-Start (`order_by(Movie.release_date.desc().nulls_last(), Movie.id.asc())`).

---

## 2. Side-by-Side Ablation Comparison Table ($K = 10$)

| Metric | Variant A (Baseline) | Variant B (+ R1) | Variant C (+ R2) | Variant D (+ R1+R2) | Variant E (v1.1 Final) | Absolute $\Delta$ (E vs A) | Relative % (E vs A) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Seen-Item Policy** | `none` | `train` | `none` | `train` | `train` | — | — |
| **Negative Feedback** | None (`max()`) | None (`max()`) | `suppress` | `suppress` | `suppress` | — | — |
| **Cold Start** | DB-dependent | DB-dependent | DB-dependent | DB-dependent | `deterministic_v1_1` | — | — |
| **HitRate@10** | 3.41% | 4.09% | 3.41% | 4.09% | **4.09%** | +0.68% | **+20.0%** |
| **Precision@10** | 0.003578 | 0.004600 | 0.003578 | 0.004600 | **0.004600** | +0.001022 | **+28.6%** |
| **Recall@10** | 0.005216 | 0.006896 | 0.005216 | 0.006896 | **0.006896** | +0.001680 | **+32.2%** |
| **NDCG@10** | 0.003738 | 0.007153 | 0.003738 | 0.007153 | **0.007153** | +0.003414 | **+91.4%** |
| **MAP@10** | 0.000997 | 0.003061 | 0.000997 | 0.003061 | **0.003061** | +0.002064 | **+207.0%** |
| **Catalog Coverage@10**| 15.07% | 13.10% | 15.07% | 13.10% | **13.10%** | -1.97% | -13.1% |
| **Intra-List Diversity@10**| 0.6309 | 0.5719 | 0.6309 | 0.5719 | **0.5719** | -0.0590 | -9.4% |
| **Novelty@10 (bits)** | 12.70 | 14.05 | 12.70 | 14.05 | **14.05** | +1.35 b | **+10.6%** |
| **Latency p50 (ms)** | 5.66 ms | 5.71 ms | 5.88 ms | 5.89 ms | **5.80 ms** | +0.14 ms | +2.5% |

---

## 3. Detailed Cutoff Comparison ($K \in \{5, 10, 20\}$)

### 3.1 Ranking Metrics (Macro-averaged over active test users, $N = 587$)

| Cutoff | Metric | TF-IDF v1.0 Baseline (A) | TF-IDF v1.1 Final (E) | Absolute Difference | Relative Change |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **$K = 5$** | Precision@5 | 0.001704 | **0.005111** | +0.003407 | **+199.9%** |
| | Recall@5 | 0.001044 | **0.003798** | +0.002754 | **+263.8%** |
| | NDCG@5 | 0.001535 | **0.005987** | +0.004452 | **+290.0%** |
| | HitRate@5 | 0.008518 (0.85%) | **0.025554 (2.56%)** | +0.017036 | **+200.0%** |
| | MAP@5 | 0.000625 | **0.003040** | +0.002415 | **+386.4%** |
| **$K = 10$** | Precision@10 | 0.003578 | **0.004600** | +0.001022 | **+28.6%** |
| | Recall@10 | 0.005216 | **0.006896** | +0.001680 | **+32.2%** |
| | NDCG@10 | 0.003738 | **0.007153** | +0.003414 | **+91.4%** |
| | HitRate@10 | 0.034072 (3.41%) | **0.040886 (4.09%)** | +0.006814 | **+20.0%** |
| | MAP@10 | 0.000997 | **0.003061** | +0.002064 | **+207.0%** |
| **$K = 20$** | Precision@20 | 0.003237 | **0.005451** | +0.002214 | **+68.4%** |
| | Recall@20 | 0.010686 | **0.015573** | +0.004887 | **+45.7%** |
| | NDCG@20 | 0.005508 | **0.010476** | +0.004968 | **+90.2%** |
| | HitRate@20 | 0.059625 (5.96%) | **0.095400 (9.54%)** | +0.035775 | **+60.0%** |
| | MAP@20 | 0.001227 | **0.003352** | +0.002125 | **+173.2%** |

### 3.2 Diversity, Coverage, and Novelty Metrics

| Cutoff | Metric | TF-IDF v1.0 Baseline (A) | TF-IDF v1.1 Final (E) | Trade-Off Analysis |
| :--- | :--- | :--- | :--- | :--- |
| **$K = 5$** | Catalog Coverage@5 | 9.46% (`0.094642`) | 8.87% (`0.088688`) | Minor concentration on core relevant unseen items |
| | Intra-List Diversity@5 | 0.5833 (`0.583319`) | 0.5281 (`0.528143`) | Recommender focuses more tightly on user's high-preference genres |
| | Novelty@5 | 12.3370 bits | 13.9042 bits | **+1.57 bits**: Recommends less obvious non-training catalog titles |
| **$K = 10$** | Catalog Coverage@10 | 15.07% (`0.150688`) | 13.10% (`0.130979`) | Moderate decrease as popular training titles are removed |
| | Intra-List Diversity@10| 0.6309 (`0.630877`) | 0.5719 (`0.571865`) | Content profile tightens without seen-item padding |
| | Novelty@10 | 12.6961 bits | 14.0524 bits | **+1.35 bits**: Significant novelty enhancement |
| **$K = 20$** | Catalog Coverage@20 | 22.33% (`0.223260`) | 18.25% (`0.182509`) | Broader candidate filtering focuses tail recommendations |
| | Intra-List Diversity@20| 0.6686 (`0.668630`) | 0.6123 (`0.612285`) | Expected content clustering around user profile |
| | Novelty@20 | 13.0795 bits | 14.2389 bits | **+1.16 bits**: Consistently higher across all cutoffs |

---

## 4. Latency Overhead Profile

| Percentile | Variant A (Baseline) | Variant E (v1.1 Final) | Overhead |
| :--- | :--- | :--- | :--- |
| **p50 (Median)** | 5.66 ms | 5.80 ms | +0.14 ms |
| **p90** | 7.10 ms | 7.15 ms | +0.05 ms |
| **p95** | 7.77 ms | 8.35 ms | +0.58 ms |
| **Mean** | 5.97 ms | 6.03 ms | +0.06 ms |

Seen-item set subtraction adds less than 0.15 ms to median request latency, well within production interactive SLAs (< 50 ms).

---

## 5. Artifact Cross-References

- Machine-readable JSON summary: `backend/reports/experiments/tfidf_v1_1_controlled_ablation/ablation_summary.json`
- Tabular CSV comparison: `backend/reports/experiments/tfidf_v1_1_controlled_ablation/ablation_comparison.csv`
- Statistical significance tests: `backend/reports/experiments/tfidf_v1_1_controlled_ablation/statistical_significance.json`
- Baseline historical report: `backend/reports/experiments/baseline_tfidf_v1_0/summary.md`
