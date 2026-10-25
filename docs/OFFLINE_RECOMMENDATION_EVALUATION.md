# MovSug — Offline Recommendation Evaluation Framework & Baseline

This document specifies the offline evaluation pipeline, dataset processing protocol, standard evaluation metrics, and the frozen experimental baseline for the MovSug movie recommendation system.

---

## 1. Quickstart: Rerunning the Baseline Experiment

### Prerequisites
- Python 3.14 (or >= 3.10) in the backend virtual environment:
  ```powershell
  cd backend
  .\.venv\Scripts\Activate.ps1
  ```

### Run Evaluation
To run the frozen baseline (`TFIDF-v1.0-as-is` with Defect R1 preserved):
```bash
python -m app.recommendation_evaluation.run --download --data-dir data/ml-latest-small --output-dir reports/experiments/baseline_tfidf_v1_0 --experiment-id baseline_tfidf_v1_0
```

To run the counterfactual benchmark (`train-excluded` to quantify the impact of Defect R1):
```bash
python -m app.recommendation_evaluation.run --data-dir data/ml-latest-small --output-dir reports/experiments/diagnostic_tfidf_v1_0_train_excluded --experiment-id diagnostic_tfidf_v1_0_train_excluded --exclude-seen train
```

To run the test suite:
```bash
pytest tests/test_recommendation_evaluation.py -v
```

---

## 2. Frozen Baseline Specification (`TFIDF-v1.0-as-is`)

The baseline preserves the exact mathematical logic of the production MovSug recommendation engine without silently fixing historical defects:

| Component | Baseline Specification | Source Reference |
|---|---|---|
| **Algorithm Name** | `TFIDF-v1.0-as-is` (v1.0.0) | `app/recommendation_evaluation/config.py` |
| **TF-IDF Vocabulary** | `max_features=5000`, `ngram_range=(1, 2)`, `stop_words="english"`, `min_df=1`, `max_df=0.95`, `norm="l2"`, `use_idf=True`, `smooth_idf=True` | `app/services/recommendation/vectorizer.py` |
| **Movie Text Weights** | `title` ×2, `keywords/tags` ×2 (lowercase), `overview` ×1, `genres` ×1, `cast` ×1, `director` ×1 | `app/services/recommendation/movie_profile.py` |
| **Rating Weights** | 5★ $\to$ 5.0, 4★ $\to$ 3.0, 3★ $\to$ 1.0, 1–2★ $\to$ 0.0 (excluded) | `app/services/recommendation/user_profile.py` |
| **Favorite Weight** | 3.0 | `app/services/recommendation/user_profile.py` |
| **Watch History Weight**| $(1.0 + 2.0 \cdot \frac{progress}{100}) \cdot \frac{1}{1.0 + 0.05 \cdot days}$, capped at 3.0 | `app/services/recommendation/user_profile.py` |
| **Signal Combination** | $\max()$ per movie across all signals (no double-counting) | `app/services/recommendation/user_profile.py` |
| **User Profile Vector**| $\vec{u} = \frac{\sum w_i \vec{m}_i}{\sum w_i}$, followed by L2-normalization | `app/services/recommendation/user_profile.py` |
| **Ranking Score** | Cosine similarity: $\cos(\vec{u}, \vec{m}_j)$ | `app/services/recommendation/engine.py` |
| **Seen-Item Policy (R1)** | Excludes favorites only; rated/watched items are NOT excluded in v1.0 | `app/services/recommendation/engine.py` |
| **Negative Feedback (R2)**| Disliked ratings (1–2★) skipped, but watch history still contributes positively if present | `app/services/recommendation/user_profile.py` |

---

## 3. Dataset & Leakage Prevention Protocol

### 3.1 Research Dataset: MovieLens `ml-latest-small`
- **Origin:** GroupLens Research, University of Minnesota (`https://files.grouplens.org/datasets/movielens/ml-latest-small.zip`)
- **License:** GroupLens Research License (non-commercial research use)
- **Dataset Size:** 9,742 movies, 100,836 ratings, 3,683 tags across 610 users
- **Database Isolation:** Kept entirely separate from production PostgreSQL and SQLite databases. No research ratings are ever imported into live application databases.
- **Git Ignored:** Raw data files (`data/`, `*.csv`, `*.zip`) are strictly `.gitignore`d.

### 3.2 Metadata Adaptation
MovieLens contains `title`, `genres`, and user `tags` (acting as keywords). It does not contain `overview`, `cast`, or `director`. In accordance with scientific integrity rules, missing metadata was **NOT** fabricated.
Movie text representations use:
$$\text{text} = \text{title} \times 2 + \text{genres} \times 1 + \text{tags} \times 2$$

### 3.3 Chronological Temporal Split
For each user with $\ge 5$ interactions:
- Sort interactions chronologically by timestamp ascending (tie-breaker: movie ID).
- Split:
  - **Train:** Earliest 70%
  - **Validation:** Next 15%
  - **Test:** Latest 15%
- **Temporal Non-Leakage:**
  $$\max(\text{train.timestamp}) \le \min(\text{val.timestamp}) \le \max(\text{val.timestamp}) \le \min(\text{test.timestamp})$$
- **Tag Leakage Prevention:** User tags applied after the maximum training timestamp across the cohort are filtered out to prevent future interaction signals from leaking into movie content vectors.

---

## 4. Evaluation Metrics Definition

For $K \in \{5, 10, 20\}$ and test relevant items $Rel(u) = \{ m \in Test(u) \mid \text{rating} \ge 4.0 \}$:

1. **Precision@K:**
   $$\text{Precision}@K(u) = \frac{|\text{TopK}(u) \cap Rel(u)|}{K}$$

2. **Recall@K:**
   $$\text{Recall}@K(u) = \frac{|\text{TopK}(u) \cap Rel(u)|}{|Rel(u)|}$$

3. **NDCG@K:**
   $$\text{DCG}@K(u) = \sum_{i=1}^K \frac{\mathbb{I}(\text{TopK}(u)[i-1] \in Rel(u))}{\log_2(i + 1)}, \quad \text{NDCG}@K(u) = \frac{\text{DCG}@K(u)}{\text{IDCG}@K(u)}$$

4. **HitRate@K:**
   $$\text{HitRate}@K(u) = \mathbb{I}(|\text{TopK}(u) \cap Rel(u)| > 0)$$

5. **MAP@K:**
   $$\text{AP}@K(u) = \frac{1}{\min(K, |Rel(u)|)} \sum_{i=1}^K \mathbb{I}(\text{TopK}(u)[i-1] \in Rel(u)) \cdot \text{Precision}@i(u)$$

6. **Catalog Coverage@K:**
   $$\text{Coverage}@K = \frac{|\bigcup_{u} \text{TopK}(u)|}{|Catalog|}$$

7. **Intra-List Diversity@K:**
   $$\text{ILD}@K(u) = \frac{2}{K(K-1)} \sum_{1 \le i < j \le K} (1 - \cos(\vec{m}_i, \vec{m}_j))$$

8. **Novelty@K (bits):**
   $$\text{Novelty}@K(u) = \frac{1}{K} \sum_{m \in \text{TopK}(u)} -\log_2(P(m)), \quad P(m) = \frac{\text{count}_{train}(m)}{N_{total\_train}}$$

9. **Latency (p50 / p95):**
   Measured execution duration per user recommendation request in milliseconds.

---

## 5. Measured Baseline Results

### 5.1 Baseline (`TFIDF-v1.0-as-is` — Defect R1 Active)
*Cohort: 610 test users, 587 users with $\ge 1$ relevant test item, 9,742 catalog movies.*

| Metric | K = 5 | K = 10 | K = 20 |
|---|---|---|---|
| **Precision@K** | 0.0017 | 0.0036 | 0.0032 |
| **Recall@K** | 0.0010 | 0.0052 | 0.0107 |
| **NDCG@K** | 0.0015 | 0.0037 | 0.0055 |
| **HitRate@K** | 0.0085 (0.85%) | 0.0341 (3.41%) | 0.0596 (5.96%) |
| **MAP@K** | 0.0006 | 0.0010 | 0.0012 |
| **Catalog Coverage@K** | 9.46% | 15.07% | 22.33% |
| **Intra-List Diversity@K** | 0.5833 | 0.6309 | 0.6686 |
| **Novelty@K (bits)** | 12.3370 | 12.6961 | 13.0795 |
| **Latency p50 / p95** | **5.64 ms** (p50) / **7.95 ms** (p95) | Mean: 5.98 ms | |

### 5.2 Counterfactual Diagnostic (`train-excluded` — Defect R1 Suppressed)
Demonstrating the empirical distortion caused by Defect R1:

| Metric | Baseline (`none` / R1 active) | Counterfactual (`train-excluded`) | Relative Change |
|---|---|---|---|
| **HitRate@5** | 0.0085 (0.85%) | 0.0256 (2.56%) | **+201% (3.0×)** |
| **Recall@5** | 0.0010 | 0.0038 | **+280% (3.8×)** |
| **NDCG@5** | 0.0015 | 0.0060 | **+300% (4.0×)** |
| **MAP@5** | 0.0006 | 0.0030 | **+400% (5.0×)** |
| **HitRate@20** | 0.0596 (5.96%) | 0.0954 (9.54%) | **+60% (1.6×)** |
| **Novelty@20** | 13.08 bits | 14.17 bits | **+1.09 bits** |

**Interpretation:**
Because `TFIDF-v1.0-as-is` fails to exclude already-rated movies, the user profile (a weighted sum of training movies) strongly favors those exact training movies. The recommender serves the user's past consumed movies back to them at ranks 1–5, preventing newly relevant future test items from surfacing.

---

## 6. Artifact Inventory

Every experiment run produces a standardized bundle in `backend/reports/experiments/<experiment_id>/`:
1. `metrics.json`: Full hierarchical machine-readable metrics, cohort breakdowns, and cryptographic checksums.
2. `per_user_metrics.csv`: Per-user evaluation table across all test users and all K values.
3. `experiment_config.json`: Canonical configuration parameters and config SHA256 checksum.
4. `environment.json`: Python interpreter version, OS platform, hardware architecture, Git commit hash, and package versions (`scikit-learn`, `scipy`, `numpy`).
5. `summary.md`: Human-readable graduation thesis report with markdown tables.

---

## 7. Roadmap to Phase 5

Phase 4 successfully delivers:
1. Frozen baseline configuration.
2. Dataset loader, feature constructor, and leak-free chronological splitter.
3. Tested offline ranking, diversity, coverage, and novelty metrics.
4. Reusable evaluation harness (`python -m app.recommendation_evaluation.run`).
5. Real measured baseline numbers.
6. 100% test coverage with zero regressions across the 322 existing backend tests and 415 frontend tests.

**Phase 5 Next Steps:**
- Implement `TFIDF-v1.1` correctness fixes (Defect R1 seen-item filtering and Defect R2 negative feedback dampening).
- Implement Maximal Marginal Relevance (MMR) for diversity optimization.
- Implement popularity-aware cold-start fallback.
- Run controlled comparison against this frozen `TFIDF-v1.0-as-is` baseline.
