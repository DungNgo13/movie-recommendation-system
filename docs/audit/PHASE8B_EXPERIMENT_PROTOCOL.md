# MovSug Phase 8B — Experimental Protocol & Methodology

**Date:** 2026-11-04  
**Phase:** Phase 8B — Semantic Embeddings, Metadata Quality Experiments, and TEC Evaluation  
**Implementation Modules:**
- [text_builder.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/text_builder.py)
- [semantic_engine.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/semantic_engine.py)
- [semantic_eval.py](file:///d:/TLTN/movie-recommendation-system/backend/app/recommendation_evaluation/semantic_eval.py)

---

## 1. Research Questions

Phase 8B is designed to answer four empirical research questions with strict statistical controls:

- **RQ1 (Metadata Quality Effect on TF-IDF & Embeddings):** Does enriching movie metadata via Phase 8A TMDB enrichment improve TF-IDF v1.1 and semantic embedding recommendation quality?
- **RQ2 (Model Architecture Effect under Identical Metadata):** Do pretrained neural semantic embeddings (`all-MiniLM-L6-v2` and `paraphrase-multilingual-MiniLM-L12-v2`) outperform lexical TF-IDF v1.1 when both consume identical metadata?
- **RQ3 (Diversity & Re-ranking Trade-off):** Do semantic embeddings provide a useful ranking or diversity trade-off relative to `TF-IDF v1.1 + MMR` ($\lambda \in \{0.5, 0.7\}$, `pool_size=100`), and does applying MMR on top of semantic embeddings improve intra-list diversity (`ILD@K`) or ranking quality (`NDCG@K`)?
- **RQ4 (Operational & Systems Cost):** What are the CPU batch generation, cache loading, disk storage, peak RAM, and online inference latency (`p50`/`p95`) costs of semantic embeddings compared to TF-IDF v1.1?

---

## 2. Frozen Dataset & Temporal Split Protocol

To guarantee 100% comparability with Phases 4, 5, and 6, Phase 8B reuses the exact frozen MovieLens `ml-latest-small` evaluation harness ([protocol.py](file:///d:/TLTN/movie-recommendation-system/backend/app/recommendation_evaluation/protocol.py)):

| Protocol Parameter | Value |
| :--- | :--- |
| **Dataset** | MovieLens `ml-latest-small` (`100,836` ratings across `9,742` movies and `610` users) |
| **Dataset SHA-256 Checksum** | `d830d1e560efffd547d0360da5042a5d97884e5cd99dfd145ec9ecc0efbbaa86` |
| **Split Strategy** | Per-user temporal split (`80%` earliest interactions in train, `20%` latest interactions in test) |
| **Split SHA-256 Checksum** | `48cc8f10cce949d0add60ad6320bf75668370d1753e5456d6fbd69479f931d67` |
| **Relevance Threshold** | `rating >= 4.0` in the user's held-out test split |
| **Active Evaluation Cohort** | `587` users with $\ge 1$ relevant test item (`23` users without relevant test items reported separately under `all_users_*`) |
| **Seen-Item Exclusion Policy** | `exclude_seen = "train"` (all movies in user's training history excluded from candidate ranking) |
| **Cutoffs Evaluated** | $K \in \{5, 10, 20\}$ (primary cutoff: $K = 10$) |
| **Deterministic Tie-Breaking** | Primary sort: descending similarity score (`round(score, 12)`); secondary sort: ascending `movie_id` |

---

## 3. Controlled Metadata Conditions (Condition A vs. Condition B)

### 3.1 Condition A — Original Unenriched Metadata (`A_Original`)
- Uses the raw MovieLens `ml-latest-small` catalog (`movies.csv` + `tags.csv` aggregated per movie).
- **Available fields:** `title` (`100%`), `genres` (`100%`), and user-contributed `keywords`/`tags` (`~16.1%` of movies have tags).
- **Missing fields (`0%` populated in MovieLens raw):** `original_title`, `title_vi`, `overview`, `overview_vi`, `cast`, `director`.

### 3.2 Condition B — Enriched Metadata (`B1` and `B2`)
Movies in the local MovSug SQLite database (`backend/movsug.db`) that have **approved** Phase 8A TMDB enrichment (`enrichment_status = 'approved'`) are linked to MovieLens `movieId` via `links.csv` (`tmdbId`).
- Out of `13` approved enriched movies in `backend/movsug.db`, **`10` movies** exist in MovieLens `ml-latest-small` (`movieId` $\in \{1, 1721, 2571, 2959, 3578, 4993, 5952, 7153, 58559, 79132\}$: *Toy Story*, *Titanic*, *The Matrix*, *Fight Club*, *Gladiator*, *The Lord of the Rings: The Fellowship of the Ring*, *The Lord of the Rings: The Two Towers*, *The Lord of the Rings: The Return of the King*, *The Dark Knight*, and *Inception*), plus `1` title/year match (*Spirited Away*, `movieId=5618`), representing **`0.103%`–`0.113%`** of the `9,742`-movie catalog.
- Because `99.89%` of MovieLens movies are not in the local `16`-movie seed database, we evaluate two complementary protocols:
  - **Protocol B1 (Full Catalog with Partial Enrichment — `9,742` movies, `587` active users):** Evaluates the realistic catalog-wide impact of enriching the matched blockbuster movies within the full `9,742`-item candidate pool.
  - **Protocol B2 (Matched Enriched Subset — `10` movies, `33` active users):** Restricts both training profiles and candidate ranking to the `10` matched movies where `100%` of items have complete Phase 8A TMDB enrichment (`overview`, `overview_vi`, `cast`, `director`, `keywords`). Because a `10`-movie candidate pool at $K=10$ is too small for confirmatory generalization, Protocol B2 is explicitly marked **`NOT ENOUGH EVIDENCE`**.

---

## 4. Deterministic Movie Text Construction Policy

Implemented in [`build_movie_RenderText`](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/text_builder.py#L186-L315):

1. **Unicode & Whitespace Normalization:** All strings are normalized to Unicode `NFC`, stripped of control characters, and collapsed to single spaces.
2. **Deduplication & Ordering:** Multi-value lists (`genres`, `keywords`, `cast`, `director`) are deduplicated case-insensitively while preserving deterministic priority order (top `8` cast members, top `3` directors, top `25` keywords).
3. **Structured Labeled Template (`v8b.1`):**
   ```text
   Title: <title>. Original Title: <original_title>. Vietnamese Title: <title_vi>. Genres: <g1, g2, ...>. Directed by: <d1, ...>. Cast: <c1, ...>. Keywords: <k1, ...>. Overview: <overview>. Vietnamese Overview: <overview_vi>.
   ```
   - Empty fields are omitted cleanly so missing metadata never injects placeholder noise (`"None"`, `"N/A"`, or empty labels).
   - Under `language_policy="en_only"`, `Vietnamese Title` and `Vietnamese Overview` are excluded.
   - Under `language_policy="multilingual"`, all 9 fields are included when present.

---

## 5. User Profile Construction & Similarity Scoring

To isolate the effect of the item representation (`TF-IDF` vs. `Semantic Embeddings`), the user-profile aggregation policy is held **identical** across all models:

$$\mathbf{u} = \text{L2\_normalize}\left(\sum_{i \in \mathcal{I}_u^+} w(r_{u,i}) \cdot \mathbf{v}_i\right)$$

- **Offline MovieLens Weighting:** Mirrors `OfflineTfidfRecommender` (`rating >= 3.0` included; weights: $5.0 \to 5.0$, $4.5 \to 4.0$, $4.0 \to 3.0$, $3.5 \to 2.0$, $3.0 \to 1.0$; ratings $< 3.0$ suppressed with weight $0.0$).
- **Online Production Weighting ([semantic_engine.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/semantic_engine.py)):** Mirrors `user_profile.py` (5-star $= 5.0$, 4-star $= 3.0$, 3-star $= 1.0$, $\le 2$-star $= 0.0$, favorite $= 3.0$, watch history with progress + recency decay capped at $3.0$, maximum signal per movie kept).
- **Similarity Scoring:** Exact dot product $s(u, j) = \mathbf{u}^\top \mathbf{v}_j$ (equivalent to cosine similarity since $\|\mathbf{u}\|_2 = \|\mathbf{v}_j\|_2 = 1$).

---

## 6. Statistical Testing Protocol

Implemented in [`compute_extended_paired_comparison`](file:///d:/TLTN/movie-recommendation-system/backend/app/recommendation_evaluation/semantic_eval.py#L465-L534):

- **Unit of Analysis:** Paired per-user metric scores across the $N = 587$ active test users.
- **Hypothesis Tests:**
  - Two-sided paired Student's $t$-test (`scipy.stats.ttest_rel`)
  - Two-sided Wilcoxon signed-rank test (`scipy.stats.wilcoxon`, zero-method `"wilcox"`)
- **Effect Size & Uncertainty:**
  - Paired Cohen's $d = \bar{\Delta} / s_{\Delta}$
  - Non-parametric 95% bootstrap confidence interval (`2,000` resamples, fixed seed `42`)
  - Per-user Win / Tie / Loss breakdown (`|diff| > 1e-9`)
