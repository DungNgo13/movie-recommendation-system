# Verified Offline Recommendation Experiment Protocol

**Status:** Canonical & Audited — Phase 5.5 Verification Pass  
**Audit Date:** 2026-10-28  
**Applicability:** Phase 4 (Baseline), Phase 5 (Ablation), Phase 6+ (MMR, Embeddings, Hybrid)  
**Maintained in:** `docs/OFFLINE_RECOMMENDATION_EVALUATION.md`

---

## Standard Cryptographic Checksums (Live Verified 2026-10-28)

| Artifact | SHA-256 |
| :--- | :--- |
| `ml-latest-small.zip` | `696d65a3dfceac7c45750ad32df2c259311949efec81f0f144fdfb91ebc9e436` |
| Combined CSV (movies + ratings + tags) | `d830d1e560efffd547d0360da5042a5d97884e5cd99dfd145ec9ecc0efbbaa86` |
| Chronological split | `48cc8f10cce949d0add60ad6320bf75668370d1753e5456d6fbd69479f931d67` |

> ⚠️ Any future experiment must verify these checksums before reporting results. A different checksum means a different experimental condition and must be named as a new protocol version.

---

## 1. Dataset Specification

**Source:** MovieLens `ml-latest-small` (GroupLens Research, University of Minnesota)  
**URL:** `https://files.grouplens.org/datasets/movielens/ml-latest-small.zip`  
**License:** GroupLens Research non-commercial research license  

| Property | Value |
| :--- | :--- |
| Catalog size | 9,742 movies |
| Total ratings | 100,836 |
| Total user-applied tags | 3,683 |
| User population | 610 users |

**Database isolation:** Strictly offline. Never imported into the production PostgreSQL or SQLite databases. All `data/` files are `.gitignore`d.

### File Manifest

| File | Size (bytes) | SHA-256 |
| :--- | :--- | :--- |
| `ml-latest-small.zip` | 978,202 | `696d65a3dfceac7c45750ad32df2c259311949efec81f0f144fdfb91ebc9e436` |
| `movies.csv` | 494,431 | `5a5f32dd9bb3797b8e728a1b98958789d2b13f294a69fdfbc5727f8a9611aa07` |
| `ratings.csv` | 2,483,723 | `aa289ca83157595d0df6aea1be6a4ded676ddc4385472e8313a8ed9805352646` |
| `tags.csv` | 118,660 | `92a9f8bb7916dceef6151209845788c3643f794dfa79d1feaec7121b5960399d` |
| `links.csv` | 197,979 | `97ad18e4e56a09363c65676b6cb3482ce3e2cea2372a24620c1599c843325f31` |

---

## 2. Temporal Split Protocol

**Implementation:** [`dataset.py::per_user_chronological_split()`](file:///d:/TLTN/movie-recommendation-system/backend/app/recommendation_evaluation/dataset.py#L213-L297)

### 2.1 Split Construction

For each user with ≥5 interactions:

1. **Sort** all user interactions by `(timestamp ASC, movie_id ASC)` — deterministic tie-breaking.
2. **Partition:**
   - `n_train = max(1, floor(0.70 × N_total))`
   - `n_val = floor(0.15 × N_total)`
   - `n_test = N_total − n_train − n_val`
   - Edge guard: if `n_test == 0` and `N_total ≥ 3`, decrement train or val to guarantee ≥1 test item.
3. **Train:** items `[0, n_train)`
4. **Val:** items `[n_train, n_train + n_val)`
5. **Test:** items `[n_train + n_val, N_total)`

For users with <5 interactions: all items go to train, val and test are empty.

### 2.2 Temporal Non-Leakage Assertion

Strictly enforced via assertions for every user:
$$\max(T_{\text{train}}) \le \min(T_{\text{val}}) \le \max(T_{\text{val}}) \le \min(T_{\text{test}})$$

Any split that violates this assertion raises a runtime error.

### 2.3 Tag Leakage Prevention

MovieLens tags serve as keywords in movie text profiles. To prevent test-period user behavior from leaking into item representations:

$$T_{\text{train}}^{\max} = \max_{u \in \text{Users}} \left( \max_{r \in \text{Train}(u)} r.\text{timestamp} \right)$$

Only tags applied at `timestamp ≤ T_train_max` are included in movie text profiles. Tags applied after the training horizon are discarded.

**Implementation:** [`dataset.py` lines 329–341](file:///d:/TLTN/movie-recommendation-system/backend/app/recommendation_evaluation/dataset.py#L329-L341)

---

## 3. Metadata Adaptation Protocol

The production MovSug recommender uses: `text = title×2 + overview×1 + genres×1 + cast×1 + keywords×2 + director×1`

MovieLens provides: `title`, `genres`, `tags`. Missing fields (`overview`, `cast`, `director`) are **never fabricated**.

Research evaluation text representation:
$$\text{text} = \text{title} \times 2 + \text{genres} \times 1 + \text{tags} \times 2$$

**Fixed TF-IDF parameters (must not change between phases):**

| Parameter | Value |
| :--- | :--- |
| `max_features` | 5,000 |
| `ngram_range` | (1, 2) |
| `stop_words` | "english" |
| `norm` | "l2" |
| `use_idf` | True |
| `smooth_idf` | True |
| `sublinear_tf` | False |
| `min_df` | 1 |
| `max_df` | 0.95 |

---

## 4. Candidate Pool and Seen-Item Exclusion

- **Candidate catalog:** All 9,742 movies are scored for every user.
- **`exclude_seen = "none"` (Defect R1 active):** Training items remain in candidate pool. Used for Variants A and C.
- **`exclude_seen = "train"` (R1 fix applied):** All movies in the user's chronological training set are removed before ranking. Used for Variants B, D, E and all Phase 6+ experiments.
- **Integrity rule:** Validation and test items are never excluded based on future knowledge. Only training items may be excluded.

---

## 5. Evaluation Cohort and Relevance Definition

| Property | Value |
| :--- | :--- |
| **Relevance threshold** | rating ≥ 4.0 |
| **Active test users (ranked metrics)** | 587 users with ≥1 test item rated ≥4.0 |
| **Zero-positive users** | 23 users with no relevant test item (metrics tracked but excluded from macro-average denominator for ranking metrics) |
| **Total evaluated users** | 610 |
| **Catalog denominator (Coverage)** | 9,742 movies |

---

## 6. Metric Definitions

For user u with Top-K recommendations TopK(u) and relevant test items Rel(u) = {m ∈ Test(u) | rating ≥ 4.0}:

**Precision@K:**
$$\text{Prec}@K(u) = \frac{|\text{TopK}(u) \cap \text{Rel}(u)|}{K}$$

**Recall@K:**
$$\text{Rec}@K(u) = \frac{|\text{TopK}(u) \cap \text{Rel}(u)|}{|\text{Rel}(u)|}$$

**NDCG@K:**
$$\text{DCG}@K(u) = \sum_{i=1}^{K} \frac{\mathbb{1}[\text{TopK}(u)[i] \in \text{Rel}(u)]}{\log_2(i+1)}, \quad \text{NDCG}@K(u) = \frac{\text{DCG}@K(u)}{\text{IDCG}@K(u)}$$

**HitRate@K:**
$$\text{HR}@K(u) = \mathbb{1}[|\text{TopK}(u) \cap \text{Rel}(u)| > 0]$$

**MAP@K:**
$$\text{AP}@K(u) = \frac{1}{\min(K, |\text{Rel}(u)|)} \sum_{i=1}^{K} \mathbb{1}[\text{TopK}(u)[i] \in \text{Rel}(u)] \cdot \text{Prec}@i(u)$$

**Catalog Coverage@K:**
$$\text{Cov}@K = \frac{\left|\bigcup_{u \in \text{Cohort}} \text{TopK}(u)\right|}{9742}$$

**Intra-List Diversity@K (ILD):**
$$\text{ILD}@K(u) = \frac{2}{K(K-1)} \sum_{1 \le i < j \le K} (1 - \cos(\vec{m}_i, \vec{m}_j))$$

**Novelty@K (self-information, bits):**
$$\text{Nov}@K(u) = \frac{1}{K} \sum_{m \in \text{TopK}(u)} -\log_2\!\left(\frac{\max(1,\,\text{count}_{\text{train}}(m))}{N_{\text{train,total}}}\right)$$

**All ranking metrics (Prec, Rec, NDCG, HR, MAP) are macro-averaged over the 587 active test users.**  
**Coverage, ILD, and Novelty are computed across all 610 users.**

---

## 7. Statistical Testing Protocol

| Test | Implementation | Parameters |
| :--- | :--- | :--- |
| Paired t-test | `scipy.stats.ttest_rel` | Per-user Δ_u vector, N=587 |
| Wilcoxon signed-rank | `scipy.stats.wilcoxon` | Per-user Δ_u vector |
| Bootstrap 95% CI | Empirical percentile | B=1,000, seed=42, N=587 |

**Significance levels:** α = 0.05 (standard), α = 0.001 (conservative)  
**Primary metric for statistical testing:** NDCG@10  
**No hyperparameter tuning was performed using test set data in any phase.**

---

## 8. Reproducibility Commands

```powershell
cd backend
.\.venv\Scripts\Activate.ps1

# Frozen Phase 4 baseline (preserve historical artifacts)
python -m app.recommendation_evaluation.run `
  --download `
  --data-dir data/ml-latest-small `
  --output-dir reports/experiments/baseline_tfidf_v1_0 `
  --experiment-id baseline_tfidf_v1_0

# Phase 5 controlled ablation (all 5 variants)
python -m app.recommendation_evaluation.run `
  --data-dir data/ml-latest-small `
  --ablation

# Full test suite
python -m pytest tests/test_recommendation_evaluation.py `
               tests/test_recommendation_fixes.py `
               tests/test_recommendation_invariance.py `
               tests/test_recommendation_engine.py -v
```

---

## 9. Phase 6 Readiness Verdict

**Question:** Is TF-IDF v1.1 scientifically ready to serve as the baseline for MMR and cold-start experiments?

**Answer: YES — conditionally on the following:**

| Condition | Status |
| :--- | :--- |
| R1 (seen-item exclusion) active | ✅ Required for valid MMR comparison |
| R2 (negative feedback) active | ✅ Prevents profile pollution |
| R3 (deterministic cold-start) active | ✅ Enables reproducible cold-start comparison |
| Split checksum frozen | ✅ `48cc8f10...` must be identical across Phase 6 |
| Dataset checksum frozen | ✅ `d830d1e5...` must be identical across Phase 6 |
| Baseline metrics frozen | ✅ Use Phase 5 Variant E as Phase 6 baseline, not Phase 4 Variant A |
| Statistical qualification | ⚠️ Report 96.08% tied users prominently |

**Phase 6 must compare against TF-IDF v1.1 (Variant E), not v1.0 (Variant A).** Using the defect-active baseline as a Phase 6 control would artificially inflate MMR's apparent benefit.

---

## 10. Document History

| Version | Date | Change |
| :--- | :--- | :--- |
| v1.0 | 2026-10-25 | Initial Phase 4 frozen protocol |
| v1.1 | 2026-10-25 | Phase 5 ablation study executed and reported |
| v1.2 | 2026-10-28 | Phase 5.5 audit: live checksums verified, all discrepancies resolved, Phase 6 readiness confirmed |
