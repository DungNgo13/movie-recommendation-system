# MovSug — Phase 6: MMR Diversity-Aware Re-ranking Ablation Report

**Date:** `2026-10-29T05:46:14.357390+00:00`  
**Git Commit:** `42835efa607fbe6b7798fe60462fd4c357faa505`  
**Dataset Checksum (SHA256):** `d830d1e560efffd547d0360da5042a5d97884e5cd99dfd145ec9ecc0efbbaa86`  
**Split Checksum (SHA256):** `48cc8f10cce949d0add60ad6320bf75668370d1753e5456d6fbd69479f931d67`  
**Evaluated Test Users:** 587  
**Candidate Catalog:** 9742 movies  

---

## 1. Research Question

Can Maximum Marginal Relevance (MMR) re-ranking improve recommendation-list
diversity (ILD, Coverage) while preserving acceptable ranking relevance (NDCG,
Precision, Recall) and inference latency?

## 2. Experimental Design

### 2.1 MMR Objective Function

```
MMR(i) = λ × Relevance(i) − (1 − λ) × max_{j ∈ S} Similarity(i, j)
```

- **Relevance:** min-max normalized TF-IDF cosine similarity to user profile
- **Similarity:** cosine similarity between item TF-IDF vectors
- **S:** set of already-selected items (greedy iterative)

### 2.2 Variants

| Variant | λ | Pool Size | Description |
|---|---|---|---|
| TFIDF-v1.1 (no MMR) | N/A | N/A | TF-IDF v1.1 baseline without MMR re-ranking. Reference for all comparisons. |
| MMR λ=0.3 pool=50 | 0.3 | 50 | TF-IDF v1.1 + MMR re-ranking with λ=0.3, candidate pool size=50. |
| MMR λ=0.5 pool=50 | 0.5 | 50 | TF-IDF v1.1 + MMR re-ranking with λ=0.5, candidate pool size=50. |
| MMR λ=0.7 pool=50 | 0.7 | 50 | TF-IDF v1.1 + MMR re-ranking with λ=0.7, candidate pool size=50. |
| MMR λ=0.9 pool=50 | 0.9 | 50 | TF-IDF v1.1 + MMR re-ranking with λ=0.9, candidate pool size=50. |
| MMR λ=1.0 pool=50 | 1.0 | 50 | TF-IDF v1.1 + MMR re-ranking with λ=1.0, candidate pool size=50. (Equivalence control: pure relevance within pool.) |
| MMR λ=0.3 pool=100 | 0.3 | 100 | TF-IDF v1.1 + MMR re-ranking with λ=0.3, candidate pool size=100. |
| MMR λ=0.5 pool=100 | 0.5 | 100 | TF-IDF v1.1 + MMR re-ranking with λ=0.5, candidate pool size=100. |
| MMR λ=0.7 pool=100 | 0.7 | 100 | TF-IDF v1.1 + MMR re-ranking with λ=0.7, candidate pool size=100. |
| MMR λ=0.9 pool=100 | 0.9 | 100 | TF-IDF v1.1 + MMR re-ranking with λ=0.9, candidate pool size=100. |
| MMR λ=1.0 pool=100 | 1.0 | 100 | TF-IDF v1.1 + MMR re-ranking with λ=1.0, candidate pool size=100. (Equivalence control: pure relevance within pool.) |

---

## 3. Results Summary (K=10)

| Variant | NDCG@10 | Precision@10 | Recall@10 | HitRate@10 | ILD@10 | Coverage@10 | Novelty@10 | Latency p50 |
|---|---|---|---|---|---|---|---|---|
| TFIDF-v1.1 (no MMR) | 0.007153 | 0.004600 | 0.006896 | 0.040886 | 0.5719 | 13.10% | 14.05 | 5.71ms |
| MMR λ=0.3 pool=50 | 0.008152 | 0.005111 | 0.008538 | 0.049404 | 0.8044 | 14.31% | 13.84 | 19.11ms |
| MMR λ=0.5 pool=50 | 0.008615 | 0.005451 | 0.009137 | 0.052811 | 0.7248 | 13.96% | 13.86 | 19.01ms |
| MMR λ=0.7 pool=50 | 0.007723 | 0.005111 | 0.007700 | 0.049404 | 0.6427 | 13.51% | 13.95 | 18.43ms |
| MMR λ=0.9 pool=50 | 0.007836 | 0.005281 | 0.008362 | 0.047700 | 0.5894 | 13.24% | 14.03 | 18.46ms |
| MMR λ=1.0 pool=50 | 0.007153 | 0.004600 | 0.006896 | 0.040886 | 0.5719 | 13.10% | 14.05 | 18.63ms |
| MMR λ=0.3 pool=100 | 0.009401 | 0.006644 | 0.010516 | 0.059625 | 0.8677 | 16.27% | 13.81 | 35.56ms |
| MMR λ=0.5 pool=100 | 0.009091 | 0.005451 | 0.010158 | 0.052811 | 0.7686 | 14.22% | 13.84 | 35.04ms |
| MMR λ=0.7 pool=100 | 0.008508 | 0.005622 | 0.008606 | 0.054514 | 0.6624 | 13.69% | 13.91 | 35.02ms |
| MMR λ=0.9 pool=100 | 0.007707 | 0.005111 | 0.007936 | 0.047700 | 0.5951 | 13.29% | 14.02 | 35.07ms |
| MMR λ=1.0 pool=100 | 0.007153 | 0.004600 | 0.006896 | 0.040886 | 0.5719 | 13.10% | 14.05 | 34.68ms |

---

## 4. Relevance–Diversity Trade-off Analysis (K=10)

| Variant | ΔNDCG@10 | ΔILD@10 | ΔCoverage@10 | Wins | Ties | Losses |
|---|---|---|---|---|---|---|
| MMR λ=0.3 pool=50 | +0.000999 | +0.2325 | +1.21pp | 23 | 548 | 16 |
| MMR λ=0.5 pool=50 | +0.001462 | +0.1530 | +0.86pp | 17 | 557 | 13 |
| MMR λ=0.7 pool=50 | +0.000570 | +0.0709 | +0.41pp | 12 | 567 | 8 |
| MMR λ=0.9 pool=50 | +0.000683 | +0.0176 | +0.14pp | 6 | 577 | 4 |
| MMR λ=1.0 pool=50 | +0.000000 | +0.0000 | +0.00pp | 0 | 587 | 0 |
| MMR λ=0.3 pool=100 | +0.002248 | +0.2958 | +3.17pp | 30 | 540 | 17 |
| MMR λ=0.5 pool=100 | +0.001938 | +0.1967 | +1.12pp | 21 | 552 | 14 |
| MMR λ=0.7 pool=100 | +0.001355 | +0.0905 | +0.60pp | 16 | 563 | 8 |
| MMR λ=0.9 pool=100 | +0.000554 | +0.0232 | +0.20pp | 8 | 575 | 4 |
| MMR λ=1.0 pool=100 | +0.000000 | +0.0000 | +0.00pp | 0 | 587 | 0 |

---

## 5. Full Results Tables

### 5.1 K=5

| Variant | P@5 | R@5 | NDCG@5 | HR@5 | MAP@5 | ILD@5 | Cov@5 | Nov@5 |
|---|---|---|---|---|---|---|---|---|
| TFIDF-v1.1 (no MMR) | 0.005111 | 0.003798 | 0.005987 | 0.025554 | 0.003040 | 0.5247 | 8.75% | 13.96 |
| MMR λ=0.3 pool=50 | 0.005111 | 0.004760 | 0.006438 | 0.025554 | 0.003421 | 0.8348 | 9.28% | 13.77 |
| MMR λ=0.5 pool=50 | 0.006133 | 0.006021 | 0.007203 | 0.030664 | 0.003683 | 0.7482 | 8.77% | 13.75 |
| MMR λ=0.7 pool=50 | 0.006814 | 0.005380 | 0.007259 | 0.034072 | 0.003455 | 0.6306 | 8.71% | 13.86 |
| MMR λ=0.9 pool=50 | 0.005111 | 0.003798 | 0.005987 | 0.025554 | 0.003040 | 0.5487 | 8.68% | 13.94 |
| MMR λ=1.0 pool=50 | 0.005111 | 0.003798 | 0.005987 | 0.025554 | 0.003040 | 0.5247 | 8.75% | 13.96 |
| MMR λ=0.3 pool=100 | 0.005451 | 0.004812 | 0.006630 | 0.027257 | 0.003465 | 0.8930 | 10.03% | 13.74 |
| MMR λ=0.5 pool=100 | 0.005451 | 0.005775 | 0.007066 | 0.027257 | 0.003799 | 0.7889 | 8.71% | 13.74 |
| MMR λ=0.7 pool=100 | 0.006814 | 0.005751 | 0.007531 | 0.034072 | 0.003657 | 0.6558 | 8.75% | 13.82 |
| MMR λ=0.9 pool=100 | 0.005111 | 0.003798 | 0.005987 | 0.025554 | 0.003040 | 0.5598 | 8.65% | 13.93 |
| MMR λ=1.0 pool=100 | 0.005111 | 0.003798 | 0.005987 | 0.025554 | 0.003040 | 0.5247 | 8.75% | 13.96 |

### 5.2 K=10

| Variant | P@10 | R@10 | NDCG@10 | HR@10 | MAP@10 | ILD@10 | Cov@10 | Nov@10 |
|---|---|---|---|---|---|---|---|---|
| TFIDF-v1.1 (no MMR) | 0.004600 | 0.006896 | 0.007153 | 0.040886 | 0.003061 | 0.5719 | 13.10% | 14.05 |
| MMR λ=0.3 pool=50 | 0.005111 | 0.008538 | 0.008152 | 0.049404 | 0.003534 | 0.8044 | 14.31% | 13.84 |
| MMR λ=0.5 pool=50 | 0.005451 | 0.009137 | 0.008615 | 0.052811 | 0.003738 | 0.7248 | 13.96% | 13.86 |
| MMR λ=0.7 pool=50 | 0.005111 | 0.007700 | 0.007723 | 0.049404 | 0.003194 | 0.6427 | 13.51% | 13.95 |
| MMR λ=0.9 pool=50 | 0.005281 | 0.008362 | 0.007836 | 0.047700 | 0.003209 | 0.5894 | 13.24% | 14.03 |
| MMR λ=1.0 pool=50 | 0.004600 | 0.006896 | 0.007153 | 0.040886 | 0.003061 | 0.5719 | 13.10% | 14.05 |
| MMR λ=0.3 pool=100 | 0.006644 | 0.010516 | 0.009401 | 0.059625 | 0.003815 | 0.8677 | 16.27% | 13.81 |
| MMR λ=0.5 pool=100 | 0.005451 | 0.010158 | 0.009091 | 0.052811 | 0.004047 | 0.7686 | 14.22% | 13.84 |
| MMR λ=0.7 pool=100 | 0.005622 | 0.008606 | 0.008508 | 0.054514 | 0.003508 | 0.6624 | 13.69% | 13.91 |
| MMR λ=0.9 pool=100 | 0.005111 | 0.007936 | 0.007707 | 0.047700 | 0.003174 | 0.5951 | 13.29% | 14.02 |
| MMR λ=1.0 pool=100 | 0.004600 | 0.006896 | 0.007153 | 0.040886 | 0.003061 | 0.5719 | 13.10% | 14.05 |

### 5.3 K=20

| Variant | P@20 | R@20 | NDCG@20 | HR@20 | MAP@20 | ILD@20 | Cov@20 | Nov@20 |
|---|---|---|---|---|---|---|---|---|
| TFIDF-v1.1 (no MMR) | 0.005451 | 0.015573 | 0.010476 | 0.095400 | 0.003352 | 0.6250 | 19.10% | 14.16 |
| MMR λ=0.3 pool=50 | 0.005622 | 0.017042 | 0.011663 | 0.103918 | 0.003978 | 0.7730 | 22.05% | 13.93 |
| MMR λ=0.5 pool=50 | 0.006303 | 0.017298 | 0.012276 | 0.110733 | 0.004209 | 0.7177 | 21.36% | 13.98 |
| MMR λ=0.7 pool=50 | 0.005366 | 0.015607 | 0.010732 | 0.095400 | 0.003553 | 0.6714 | 20.29% | 14.06 |
| MMR λ=0.9 pool=50 | 0.005537 | 0.015760 | 0.010645 | 0.098807 | 0.003407 | 0.6360 | 19.61% | 14.14 |
| MMR λ=1.0 pool=50 | 0.005451 | 0.015573 | 0.010476 | 0.095400 | 0.003352 | 0.6250 | 19.10% | 14.16 |
| MMR λ=0.3 pool=100 | 0.005281 | 0.015786 | 0.011302 | 0.093697 | 0.003979 | 0.8498 | 24.86% | 13.86 |
| MMR λ=0.5 pool=100 | 0.006303 | 0.018111 | 0.012724 | 0.112436 | 0.004517 | 0.7638 | 22.32% | 13.89 |
| MMR λ=0.7 pool=100 | 0.005366 | 0.015290 | 0.010997 | 0.095400 | 0.003775 | 0.6846 | 20.62% | 14.04 |
| MMR λ=0.9 pool=100 | 0.005451 | 0.015560 | 0.010626 | 0.095400 | 0.003457 | 0.6403 | 19.73% | 14.13 |
| MMR λ=1.0 pool=100 | 0.005451 | 0.015573 | 0.010476 | 0.095400 | 0.003352 | 0.6250 | 19.10% | 14.16 |

---

## 6. Statistical Significance (NDCG@10 vs Baseline)

| Variant | Mean Δ | t-stat | p (t-test) | p (Wilcoxon) | 95% CI | Significant? |
|---|---|---|---|---|---|---|
| MMR λ=0.3 pool=50 | +0.001000 | 0.7500 | 4.54e-01 | 3.98e-01 | [-0.001678, 0.003679] | ✗ |
| MMR λ=0.5 pool=50 | +0.001462 | 1.3289 | 1.84e-01 | 2.06e-01 | [-0.000521, 0.003824] | ✗ |
| MMR λ=0.7 pool=50 | +0.000571 | 1.0190 | 3.09e-01 | 3.41e-01 | [-0.000590, 0.001830] | ✗ |
| MMR λ=0.9 pool=50 | +0.000683 | 1.7983 | 7.27e-02 | 1.02e-01 | [-0.000033, 0.001577] | ✗ |
| MMR λ=1.0 pool=50 | +0.000000 | 0.0000 | 1.00e+00 | 1.00e+00 | [0.000000, 0.000000] | ✗ |
| MMR λ=0.3 pool=100 | +0.002249 | 1.4832 | 1.39e-01 | 1.14e-01 | [-0.000633, 0.005166] | ✗ |
| MMR λ=0.5 pool=100 | +0.001938 | 1.6089 | 1.08e-01 | 1.14e-01 | [-0.000320, 0.004608] | ✗ |
| MMR λ=0.7 pool=100 | +0.001355 | 1.7523 | 8.02e-02 | 1.19e-01 | [-0.000119, 0.003096] | ✗ |
| MMR λ=0.9 pool=100 | +0.000554 | 1.2695 | 2.05e-01 | 1.81e-01 | [-0.000326, 0.001524] | ✗ |
| MMR λ=1.0 pool=100 | +0.000000 | 0.0000 | 1.00e+00 | 1.00e+00 | [0.000000, 0.000000] | ✗ |

---

## 7. Latency Analysis

| Variant | p50 (ms) | p95 (ms) | Overhead p50 | Overhead p95 |
|---|---|---|---|---|
| TFIDF-v1.1 (no MMR) | 5.71 | 8.16 | +0.00 | +0.00 |
| MMR λ=0.3 pool=50 | 19.11 | 21.80 | +13.40 | +13.64 |
| MMR λ=0.5 pool=50 | 19.01 | 22.29 | +13.30 | +14.13 |
| MMR λ=0.7 pool=50 | 18.43 | 20.62 | +12.72 | +12.47 |
| MMR λ=0.9 pool=50 | 18.46 | 20.69 | +12.75 | +12.53 |
| MMR λ=1.0 pool=50 | 18.63 | 22.04 | +12.92 | +13.88 |
| MMR λ=0.3 pool=100 | 35.56 | 40.45 | +29.85 | +32.29 |
| MMR λ=0.5 pool=100 | 35.04 | 38.03 | +29.33 | +29.88 |
| MMR λ=0.7 pool=100 | 35.02 | 37.82 | +29.31 | +29.66 |
| MMR λ=0.9 pool=100 | 35.07 | 38.03 | +29.36 | +29.87 |
| MMR λ=1.0 pool=100 | 34.68 | 37.38 | +28.97 | +29.22 |

---

## 8. Methodology Notes

1. **Validation vs Test:** All configurations were designed a priori based on
   standard MMR literature. λ values were NOT tuned on test-set outcomes.
   The recommended configuration should be selected using validation set
   results, then confirmed on the test set exactly once.
2. **Tied Users:** The TF-IDF v1.1 baseline has ~96% of users with identical
   NDCG@10 scores (tied at 0). Most MMR changes affect only users who already
   have non-zero relevance scores in their recommendation lists.
3. **ILD Interpretation:** Intra-List Diversity measures average pairwise
   dissimilarity within each user's recommendation list. Higher ILD means more
   diverse recommendations, but does NOT necessarily mean better user satisfaction.
4. **Coverage:** Catalog coverage measures the fraction of the item catalog
   that appears in at least one user's recommendation list. MMR is expected to
   increase this by promoting different items for different users.
5. **Determinism:** All results are fully reproducible given identical dataset,
   split checksums, and code version.
