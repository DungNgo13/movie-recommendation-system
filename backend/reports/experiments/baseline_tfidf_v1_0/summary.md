# MovSug Offline Evaluation Report: TFIDF-v1.0-as-is

**Experiment ID:** `baseline_tfidf_v1_0`  
**Algorithm Version:** `1.0.0`  
**Execution Timestamp:** `2026-10-25T13:35:48.791805+00:00`  
**Git Commit:** `eb7cbbd3150e12c4ab82012acc2db3dbdd515fd7`  
**Configuration Checksum (SHA256):** `2a95408d299a28c5b7d9ba63495d839ceff79e96a964b886972a22bd8f6cf2a9`  
**Dataset Checksum (SHA256):** `d830d1e560efffd547d0360da5042a5d97884e5cd99dfd145ec9ecc0efbbaa86`  
**Split Checksum (SHA256):** `48cc8f10cce949d0add60ad6320bf75668370d1753e5456d6fbd69479f931d67`  

---

## 1. Experimental Setup & Protocol

- **Dataset:** `MovieLens ml-latest-small` (9742 movies, 610 test users)
- **Evaluation Protocol:** Per-user chronological split (70% Train / 15% Val / 15% Test)
- **Positive Relevance Ground Truth:** Rating $\ge 4.0$ in held-out test split
- **Evaluated Cohort:** 587 users with $\ge 1$ relevant test item (23 users with 0 relevant test items)
- **Seen-Item Exclusion Policy:** `none` (Defect R1 active: `True`)
- **Model Fitting Duration:** 0.50 s
- **Full Evaluation Duration:** 3.67 s

---

## 2. Key Performance Metrics

### 2.1 Ranking & Accuracy Metrics (Macro-averaged over users with $\ge 1$ relevant test item)

| Metric | K = 5 | K = 10 | K = 20 |
|---|---|---|---|
| **Precision@K** | 0.0017 | 0.0036 | 0.0032 |
| **Recall@K** | 0.0010 | 0.0052 | 0.0107 |
| **NDCG@K** | 0.0015 | 0.0037 | 0.0055 |
| **HitRate@K** | 0.0085 | 0.0341 | 0.0596 |
| **MAP@K** | 0.0006 | 0.0010 | 0.0012 |

### 2.2 Ranking Metrics Across ALL Test Users (including users with 0 test positives)

| Metric | K = 5 | K = 10 | K = 20 |
|---|---|---|---|
| **Precision@K** | 0.0016 | 0.0034 | 0.0031 |
| **Recall@K** | 0.0010 | 0.0050 | 0.0103 |
| **NDCG@K** | 0.0015 | 0.0036 | 0.0053 |
| **HitRate@K** | 0.0082 | 0.0328 | 0.0574 |
| **MAP@K** | 0.0006 | 0.0010 | 0.0012 |

### 2.3 Diversity, Coverage & Novelty Metrics

| Metric | K = 5 | K = 10 | K = 20 |
|---|---|---|---|
| **Catalog Coverage@K** | 9.46% | 15.07% | 22.33% |
| **Intra-List Diversity@K** | 0.5833 | 0.6309 | 0.6686 |
| **Novelty@K (bits)** | 12.3370 | 12.6961 | 13.0795 |

### 2.4 Recommendation Latency

| Percentile | Latency (ms) |
|---|---|
| **Median (p50)** | 5.64 ms |
| **90th Percentile (p90)** | 7.18 ms |
| **95th Percentile (p95)** | 7.95 ms |
| **Mean** | 5.98 ms |

---

## 3. Analysis & Known Limitations

### 3.1 Defect R1 Preservation
In production MovSug `TFIDF-v1.0`, only favorites are excluded from recommendation lists (`exclude_ids = set(get_user_favorite_ids())`). Rated and watched movies are NOT excluded.
In offline evaluation where ground truth ratings are split chronologically, training-set movies that the user rated highly (4-5 stars) have the highest cosine similarity with the user vector.
When `exclude_seen_policy = 'none'`, the recommender recommends already-rated training movies back to the user at the top ranks. Since those training movies cannot appear in the held-out future test set, ranking metrics against future test items are severely degraded.

### 3.2 Metadata Representation Adaptation
The production engine builds movie profiles from `title * 2`, `overview * 1`, `genres * 1`, `cast * 1`, `keywords * 2`, `director * 1`.
MovieLens `ml-latest-small` contains only `title`, `genres`, and user `tags` (acting as keywords). Plot overviews, cast, and directors are not present in MovieLens and were NOT fabricated.
Item representations in this baseline use `title * 2`, `genres * 1`, and `tags * 2`. Tag leakage prevention ensures tags applied during future test interactions are excluded from movie profiles.

### 3.3 Readiness for Phase 5
This experiment establishes the exact numerical baseline for `TFIDF-v1.0-as-is`. In Phase 5, controlled experiments will measure:
1. `TFIDF-v1.1`: Fixing Defect R1 (seen-item filtering) and Defect R2 (negative feedback suppression).
2. Algorithmic enhancements: Maximal Marginal Relevance (MMR) for diversity, Cold-start fallback re-ranking, and Hybrid recommendations.
