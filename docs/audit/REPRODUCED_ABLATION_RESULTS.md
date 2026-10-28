# Reproduced Controlled Ablation Results: TF-IDF v1.0 vs. v1.1

**Audit Target:** MovSug TF-IDF v1.1 Recommendation Engine Ablation Study  
**Reproducibility Verdict:** **VALID AND REPRODUCIBLE**  
**Live Execution Timestamp:** 2026-10-28T20:59:07+07:00 — 21:00:00+07:00  
**Command:**
```powershell
python -m app.recommendation_evaluation.run --data-dir data/ml-latest-small --ablation
```

---

## 1. Frozen Experimental Conditions

All five variants share the following immutable conditions — verified live:

| Property | Value | Verification |
| :--- | :--- | :--- |
| Dataset | MovieLens `ml-latest-small` | Confirmed on disk |
| ZIP SHA-256 | `696d65a3dfceac7c45750ad32df2c259311949efec81f0f144fdfb91ebc9e436` | Live `Get-FileHash` |
| Combined CSV SHA-256 | `d830d1e560efffd547d0360da5042a5d97884e5cd99dfd145ec9ecc0efbbaa86` | From `ablation_summary.json` |
| Split SHA-256 | `48cc8f10cce949d0add60ad6320bf75668370d1753e5456d6fbd69479f931d67` | Live run log |
| Split ratios | 70% train / 15% val / 15% test | `dataset.py` lines 215–217 |
| Candidate catalog | 9,742 movies | `ablation_summary.json` cohort |
| Total users | 610 | All with ≥5 interactions |
| Active test users (≥1 relevant) | 587 | Relevance threshold = 4.0★ |
| Relevance threshold | rating ≥ 4.0 | `VERIFIED_EXPERIMENT_PROTOCOL.md` |
| K values | 5, 10, 20 | `metrics.py` |
| TF-IDF parameters | max_features=5000, ngram(1,2), norm=l2 | `vectorizer.py` |
| Metric averaging | Macro over 587 active users | `evaluator.py` |
| Tag leakage prevention | Enabled | `dataset.py` line 309 |
| Bootstrap seed | 42 | `ablation.py` |

---

## 2. Variant Design

| ID | Name | Seen-Item Policy | Negative Feedback | Cold-Start |
| :--- | :--- | :--- | :--- | :--- |
| **A** | `TFIDF-v1.0-as-is` | `none` — Defect R1 active | `max()` — Defect R2 active | DB-dependent order |
| **B** | `TFIDF-v1.0 + R1` | `train` — R1 fix applied | `max()` — R2 still active | DB-dependent order |
| **C** | `TFIDF-v1.0 + R2` | `none` — R1 still active | `suppress` — R2 fix applied | DB-dependent order |
| **D** | `TFIDF-v1.0 + R1 + R2` | `train` | `suppress` | DB-dependent order |
| **E** | `TFIDF-v1.1 (Final)` | `train` | `suppress` | Deterministic R3 |

> **Note on Variant C:** MovieLens contains only explicit ratings, no watch-history events. Because Defect R2 manifests only when a disliked rating and a positive watch event exist for the same item simultaneously, Variant C is behaviorally identical to Variant A on this dataset. Its correctness is proven by 3 dedicated unit tests in `tests/test_recommendation_fixes.py::TestR2NegativeFeedbackPrecedence`, all of which PASSED in this audit.

---

## 3. Live Reproduced Results — Ablation Comparison at K = 10

| Metric | A (Baseline) | B (+R1) | C (+R2) | D (+R1+R2) | E (v1.1) | Δ (E vs A) | Rel % |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| HitRate@10 | 3.41% | 4.09% | 3.41% | 4.09% | **4.09%** | +0.68% | **+20.0%** |
| Precision@10 | 0.003578 | 0.004600 | 0.003578 | 0.004600 | **0.004600** | +0.001022 | **+28.6%** |
| Recall@10 | 0.005216 | 0.006896 | 0.005216 | 0.006896 | **0.006896** | +0.001680 | **+32.2%** |
| NDCG@10 | 0.003738 | 0.007153 | 0.003738 | 0.007153 | **0.007153** | +0.003415 | **+91.4%** |
| MAP@10 | 0.000997 | 0.003061 | 0.000997 | 0.003061 | **0.003061** | +0.002064 | **+207.0%** |
| Coverage@10 | 15.07% | 13.10% | 15.07% | 13.10% | **13.10%** | -1.97% | -13.1% |
| ILD@10 | 0.6309 | 0.5719 | 0.6309 | 0.5719 | **0.5719** | -0.0590 | -9.4% |
| Novelty@10 | 12.70 bits | 14.05 bits | 12.70 bits | 14.05 bits | **14.05 bits** | +1.35 bits | **+10.6%** |
| Latency p50 | 5.94 ms | 5.98 ms | 5.66 ms | 5.57 ms | **5.63 ms** | +<0.1 ms | negligible |

---

## 4. Detailed Results Across K ∈ {5, 10, 20}

### 4.1 Ranking Metrics (Macro-averaged over N = 587 active users)

| K | Metric | A (v1.0 Baseline) | E (v1.1 Final) | Absolute Δ | Relative % |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 5 | Precision@5 | 0.001704 | **0.005111** | +0.003407 | **+200%** |
| 5 | Recall@5 | 0.001044 | **0.003798** | +0.002754 | **+264%** |
| 5 | NDCG@5 | 0.001535 | **0.005987** | +0.004452 | **+290%** |
| 5 | HitRate@5 | 0.85% | **2.56%** | +1.71% | **+200%** |
| 5 | MAP@5 | 0.000625 | **0.003040** | +0.002415 | **+386%** |
| 10 | Precision@10 | 0.003578 | **0.004600** | +0.001022 | **+29%** |
| 10 | Recall@10 | 0.005216 | **0.006896** | +0.001680 | **+32%** |
| 10 | NDCG@10 | 0.003738 | **0.007153** | +0.003415 | **+91%** |
| 10 | HitRate@10 | 3.41% | **4.09%** | +0.68% | **+20%** |
| 10 | MAP@10 | 0.000997 | **0.003061** | +0.002064 | **+207%** |
| 20 | Precision@20 | 0.003237 | **0.005451** | +0.002214 | **+68%** |
| 20 | Recall@20 | 0.010686 | **0.015573** | +0.004887 | **+46%** |
| 20 | NDCG@20 | 0.005508 | **0.010476** | +0.004968 | **+90%** |
| 20 | HitRate@20 | 5.96% | **9.54%** | +3.58% | **+60%** |
| 20 | MAP@20 | 0.001227 | **0.003352** | +0.002125 | **+173%** |

### 4.2 Diversity, Coverage, and Novelty Metrics

| K | Metric | A (v1.0) | E (v1.1) | Trade-off Analysis |
| :--- | :--- | :--- | :--- | :--- |
| 5 | Coverage@5 | 9.46% | 8.87% | Minor concentration on non-training items |
| 5 | ILD@5 | 0.5833 | 0.5281 | List tightens around user preference genre clusters |
| 5 | Novelty@5 | 12.34 bits | **13.90 bits** | +1.57 bits: less obvious items surfaced |
| 10 | Coverage@10 | 15.07% | 13.10% | Moderate: popular training items filtered |
| 10 | ILD@10 | 0.6309 | 0.5719 | Expected: content profile narrows |
| 10 | Novelty@10 | 12.70 bits | **14.05 bits** | +1.35 bits: significantly more novel |
| 20 | Coverage@20 | 22.33% | 18.25% | Broader filtering focuses tail recommendations |
| 20 | ILD@20 | 0.6686 | 0.6123 | Expected clustering around user profile |
| 20 | Novelty@20 | 13.08 bits | **14.24 bits** | +1.16 bits: consistently higher |

> **Trade-off interpretation:** The small decrease in Coverage and ILD is an expected, mechanistic consequence of excluding training-set items (many of which were popular mainstream titles). The system now recommends from a narrower but more appropriate candidate pool, yielding substantially higher novelty and relevance. This trade-off is acceptable and well-understood.

---

## 5. Latency Profile

| Percentile | A (v1.0) | E (v1.1) | Overhead |
| :--- | :--- | :--- | :--- |
| p50 (median) | 5.94 ms | 5.63 ms | -0.31 ms (faster) |
| p90 | 7.49 ms | 6.89 ms | -0.60 ms |
| p95 | 8.46 ms | 8.07 ms | -0.39 ms |
| Mean | 6.27 ms | 5.95 ms | -0.32 ms |

Seen-item exclusion (set subtraction) adds negligible overhead. The v1.1 engine is marginally faster than v1.0 in this run (set creation can produce cache-friendly access patterns for later scoring). All latencies are well within the 50 ms interactive SLA.

---

## 6. Ablation Isolation — Causal Attribution

The ablation design isolates R1 as the sole driver of all measurable quality improvements:

- **R1 (Seen-Item Exclusion):** Responsible for 100% of the ranking metric gain. Variants B, D, E are all numerically equivalent at K=5,10,20 for ranking metrics.
- **R2 (Negative Feedback Precedence):** Not measurable offline on MovieLens (no watch-history events in dataset). Effect confirmed via dedicated unit tests only.
- **R3 (Deterministic Cold-Start):** Has zero effect on the ranking metrics for warm users. Cold-start users are out of scope for precision/recall/NDCG (they have no training interactions to form a profile). R3's value is determinism and reproducibility, confirmed by `TestR3DeterministicColdStart` unit tests.

---

## 7. Artifact References

| Artifact | Path |
| :--- | :--- |
| Live ablation JSON summary | [`backend/reports/experiments/tfidf_v1_1_controlled_ablation/ablation_summary.json`](file:///d:/TLTN/movie-recommendation-system/backend/reports/experiments/tfidf_v1_1_controlled_ablation/ablation_summary.json) |
| CSV comparison table | [`backend/reports/experiments/tfidf_v1_1_controlled_ablation/ablation_comparison.csv`](file:///d:/TLTN/movie-recommendation-system/backend/reports/experiments/tfidf_v1_1_controlled_ablation/ablation_comparison.csv) |
| Statistical significance JSON | [`backend/reports/experiments/tfidf_v1_1_controlled_ablation/statistical_significance.json`](file:///d:/TLTN/movie-recommendation-system/backend/reports/experiments/tfidf_v1_1_controlled_ablation/statistical_significance.json) |
| Phase 4 baseline metrics | [`backend/reports/experiments/baseline_tfidf_v1_0/metrics.json`](file:///d:/TLTN/movie-recommendation-system/backend/reports/experiments/baseline_tfidf_v1_0/metrics.json) |
| Dataset loader | [`backend/app/recommendation_evaluation/dataset.py`](file:///d:/TLTN/movie-recommendation-system/backend/app/recommendation_evaluation/dataset.py) |
| Metrics implementation | [`backend/app/recommendation_evaluation/metrics.py`](file:///d:/TLTN/movie-recommendation-system/backend/app/recommendation_evaluation/metrics.py) |
