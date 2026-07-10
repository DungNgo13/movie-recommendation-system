# Recommendation Engine Audit — Detailed Analysis

**Audit Date:** 2026-07-10  
**Focus:** AI Recommendation System (TF-IDF + Cosine Similarity)  
**Core Files:**
- [engine.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/engine.py)
- [movie_profile.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/movie_profile.py)
- [user_profile.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/user_profile.py)
- [vectorizer.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/vectorizer.py)
- [explainer.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/explainer.py)
- [explainer_admin.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/explainer_admin.py)

---

## 1. Actual Algorithm Summary

The recommendation engine implements **Content-Based Filtering** using TF-IDF and Cosine Similarity. Here is the exact pipeline as implemented in code:

### Step 1: Movie Text Profile (`movie_profile.py`)
Each movie is converted to a single text string:
```
"{title} {title} {overview} {genres joined} actor {name1} actor {name2} {kw1} {kw2} {kw1} {kw2} director {director_name}"
```

Weighting via text repetition:
| Field | Repetition | Rationale |
|-------|-----------|-----------|
| Title | ×2 | Primary identity token |
| Keywords | ×2 | Concise thematic signal |
| Overview | ×1 | Rich context with noise |
| Genres | ×1 | Categorical signal |
| Cast | ×1 (prefixed "actor") | Actor disambiguation |
| Director | ×1 (prefixed "director") | Director disambiguation |

### Step 2: TF-IDF Vectorization (`vectorizer.py`)
```python
TfidfVectorizer(
    max_features=5000,
    stop_words="english",
    ngram_range=(1, 2),
    min_df=1,
    max_df=0.95,  # set to 1.0 if corpus < 2 movies
)
```
Output: sparse matrix `(n_movies × n_features)`

### Step 3: User Preference Vector (`user_profile.py`)
Three signal sources combined with MAX rule (no double-counting):

| Signal | Weight |
|--------|--------|
| Rating 5★ | 5.0 |
| Rating 4★ | 3.0 |
| Rating 3★ | 1.0 |
| Rating ≤2★ | 0.0 (excluded) |
| Favorite | 3.0 |
| Watch | `min(base × decay, 3.0)` where `base = 1.0 + progress%/100 × 2.0` and `decay = 1.0 / (1.0 + days × 0.05)` |

Final vector: weighted average of movie TF-IDF vectors → L2 normalized.

### Step 4: Scoring (`engine.py`)
```python
scores = cosine_similarity(user_vector.reshape(1, -1), movie_matrix).flatten()
```
- Exclude favorited movies
- Sort descending by score
- Take top-N

### Step 5: Explanation (`explainer.py`)
- Score ≥ 0.5 → "Strong match"
- Score ≥ 0.2 → "Good match"
- Score < 0.2 → "You might like this"
- Combined with dominant signal source (ratings > favorites > watch)

### Step 6: Cold-Start (`engine.py`)
When `build_user_profile()` returns `None`:
- Returns recent movies from candidate pool (ORDER BY release_date DESC)
- Score = 0.0
- Reason = "Popular movie — rate or favorite some movies for personalized picks!"

---

## 2. Does Implementation Match Documentation?

| Documented Feature | Code Implementation | Match? |
|-------------------|---------------------|--------|
| TF-IDF with max_features=5000 | `TfidfVectorizer(max_features=5000, ...)` | ✅ Exact match |
| English stop words | `stop_words="english"` | ✅ Exact match |
| ngram_range (1, 2) | `ngram_range=(1, 2)` | ✅ Exact match |
| Title ×2 weight | Two `parts.append(title)` calls | ✅ Exact match |
| Keywords ×2 weight | Two `parts.append(kw_str)` calls | ✅ Exact match |
| Actor prefix "actor" | `f"actor {str(a).lower()}"` | ✅ Exact match |
| Director prefix "director" | `f"director {director}"` | ✅ Exact match |
| Rating weights 5→5.0, 4→3.0, 3→1.0, ≤2→0.0 | `RATING_WEIGHTS = {1:0, 2:0, 3:1, 4:3, 5:5}` | ✅ Exact match |
| Favorite weight 3.0 | `WEIGHT_FAVORITE = 3.0` | ✅ Exact match |
| Watch weight formula with time decay | `base * decay` with `DECAY_RATE = 0.05` | ✅ Exact match |
| MAX rule for multi-signal movies | `movie_weights[mid] = max(...)` | ✅ Exact match |
| L2 normalization | `user_vector /= norm` | ✅ Exact match |
| Cold-start fallback | `_cold_start_fallback` with recent movies | ✅ Exact match |
| `RECOMMEND_ONLY_UPLOADED_MOVIES` | `_should_filter_uploaded_only()` + `_candidate_query()` | ✅ Exact match |
| Exclude favorited from results | `exclude_ids = set(get_user_favorite_ids(...))` | ✅ Exact match |
| Docs say "exclude favorited" | Code excludes only favorites, NOT rated/watched | ✅ Matches docs |

**Verdict: Implementation matches documentation precisely.** This is commendable and important for academic integrity.

---

## 3. Strengths

1. **Intellectually Honest** — The algorithm is exactly what it claims to be. No overclaiming of "AI" capabilities. Documentation accurately describes limitations.

2. **Well-Separated Architecture** — Each concern has its own module: movie profiles, user profiles, vectorization, scoring, explanation. Easy to understand, modify, and test independently.

3. **Three-Signal User Profile** — Combining explicit (ratings, favorites) and implicit (watch history with time decay) signals is a genuine improvement over single-signal systems.

4. **MAX Rule Prevents Inflation** — The `max()` instead of `sum()` for multi-signal movies is a thoughtful design choice that prevents a single heavily-interacted movie from dominating the profile.

5. **Time Decay** — The `1/(1 + days × 0.05)` decay function naturally prioritizes recent interests without abrupt cutoffs. The half-life (~20 days) is reasonable.

6. **Actor/Director Prefix Disambiguation** — Using "actor tom hanks" instead of "tom hanks" prevents accidental matches with overview text. This is a smart NLP technique appropriate for TF-IDF.

7. **Admin Explainer** — The `explainer_admin.py` is excellent thesis defense material. It shows every weight, every factor, every intermediate value. This alone is worth highlighting in the report.

8. **Candidate Pool Control** — `RECOMMEND_ONLY_UPLOADED_MOVIES` is a practical feature that ensures recommendations are actionable (users can actually watch recommended movies).

9. **Graceful Edge Cases** — `max_df` adjusted for tiny corpora, proper None/empty handling throughout, timezone-safe datetime handling.

10. **Cache Invalidation on CRUD** — `movie_service.py` correctly calls `invalidate_cache()` on create, update, and delete operations.

---

## 4. Weaknesses

### 4.1 Stale Cache Risk (Medium)

**Current behavior:** Cache validity is checked by `movie_count` + `filter_flag`. If movie metadata changes (genres updated, keywords added) but the movie count stays the same, `_is_cache_valid()` still returns `True`.

**Mitigation already in place:** `movie_service.py` calls `invalidate_cache()` on every create/update/delete. So the cache IS properly invalidated for all normal operations.

**Remaining risk:** If metadata is changed via direct SQL, Alembic migration, or import script, the cache won't be invalidated until the next server restart or movie count change.

**Recommended fix (simple):**
```python
# In vectorizer.py, add a hash-based check:
import hashlib

def _content_hash(db: Session) -> str:
    """Quick hash of movie IDs + update timestamps to detect metadata changes."""
    movies = _candidate_query(db).with_entities(Movie.id, Movie.title).all()
    content = str([(str(m.id), m.title) for m in movies])
    return hashlib.md5(content.encode()).hexdigest()
```

**Alternative (even simpler):** Just add a comment documenting that all changes MUST go through `movie_service` and that `invalidate_cache()` is called there. This is sufficient for academic scope.

### 4.2 No Negative Feedback (Low)

Ratings 1-2★ are excluded (weight = 0.0) but not used as negative signals. The user profile is only "attracted" toward liked content, never "repelled" from disliked content.

**Impact:** Filter bubble — the system will keep recommending similar content types even if the user dislikes some of them.

**Academic position:** This is a conscious design choice documented in the algorithm explanation. For a content-based system, implementing negative feedback would add complexity (e.g., subtracting weighted vectors) with unclear benefit on a small dataset.

### 4.3 Explanation Is Generic (Low)

The user-facing explanation (`explainer.py`) generates the same reason string pattern regardless of which specific movies contributed to the recommendation. "Based on your ratings · Strong match" doesn't tell the user *which* rated movies influenced this recommendation.

**Recommended improvement (simple):**
```python
# Instead of just the dominant signal type, include a specific movie:
# "Similar to 'Inception' (5★) · Strong match"
```

### 4.4 No Diversity Mechanism (Low)

The engine returns the top-N most similar movies. If a user likes action movies, all recommendations will be action movies. No mechanism to inject diversity.

**Simple fix (optional):** After top-N, replace 1-2 slots with movies from underrepresented genres. This is a well-known technique in recommendation literature (MMR — Maximal Marginal Relevance).

### 4.5 User Profile from Non-Candidate Movies (Info)

The user profile includes ALL movies the user interacted with (including those outside the candidate pool). This means if `RECOMMEND_ONLY_UPLOADED_MOVIES=true`, a user who rated movies without uploaded video still has those preferences reflected in their profile. This is actually **correct behavior** — preferences should be derived from all interactions, not just available content.

---

## 5. Edge Cases

| Edge Case | Handled? | Implementation |
|-----------|----------|----------------|
| User has no interactions | ✅ | Returns `None` → cold-start fallback |
| No movies in catalog | ✅ | `get_movie_vectors` returns `(None, [])` → empty results |
| Movie with empty metadata | ✅ | `build_movie_text` uses `getattr(movie, ..., "") or ""` |
| Movie with null genres/cast/keywords | ✅ | Checked `isinstance(genres, list)` before iteration |
| Only 1 movie in corpus | ✅ | `max_df` adjusted to `1.0` for single-doc corpus |
| User rated all movies | ⚠️ Partial | Only favorites are excluded, not rated movies — user gets recommendations but all are "already seen" |
| Movie deleted after TF-IDF fit | ⚠️ Partial | `movie_map.get(mid)` returns None, movie silently dropped from results |
| User ID not found | ✅ | `build_user_profile` queries return empty → None → cold-start |
| Concurrent requests | ⚠️ Partial | Module-level `_cache` dict is not thread-safe but FastAPI uses async; acceptable for demo |
| Very long overview text | ✅ | TF-IDF handles naturally via IDF weighting |
| Non-English content | ⚠️ | English stopwords only — Vietnamese/other content will have noisy features |

---

## 6. Cache Problems

### Current Cache Strategy
```python
_cache = {
    "vectorizer": fitted TfidfVectorizer,
    "matrix": sparse TF-IDF matrix,
    "movie_ids": list of movie ID strings,
    "movie_count": int,
    "filter_flag": bool,
}
```

| Invalidation Trigger | Works? | Notes |
|---------------------|--------|-------|
| Movie added (count increases) | ✅ | Count mismatch triggers refit |
| Movie deleted (count decreases) | ✅ | Count mismatch triggers refit |
| Movie metadata updated (same count) | ✅* | `invalidate_cache()` called by `movie_service.update_movie` |
| Direct SQL update | ❌ | Count unchanged, no invalidation signal |
| Server restart | ✅ | Cache starts empty |
| Filter flag changed | ✅ | Flag mismatch triggers refit |

*Works because `movie_service.py` explicitly calls `invalidate_cache()`. The count-based check in `_is_cache_valid()` is a secondary safety net.

### Recommended Improvement (Simple)
Add a call to `invalidate_cache()` in the HLS service when a movie's `processing_status` changes to "ready" — because this changes whether the movie is in the candidate pool when `RECOMMEND_ONLY_UPLOADED_MOVIES=true`.

```python
# In hls_service.py, after setting processing_status = "ready":
from .recommendation.vectorizer import invalidate_cache
invalidate_cache()
```

This is currently not done, meaning a newly-encoded movie won't appear in recommendations until the next cache miss (caused by a movie being added/deleted) or server restart.

---

## 7. Missing Tests

### What Exists
- `test_user_profile.py` — ~10 tests covering weight calculations, signal combination, MAX rule
- `test_candidate_filter.py` — Tests for `RECOMMEND_ONLY_UPLOADED_MOVIES` filtering

### What's Missing

1. **End-to-end recommendation test:**
```python
def test_recommendation_pipeline():
    """Create movies, create user interactions, get recommendations, verify output."""
    # Create 5+ movies with metadata
    # Create user, rate 2 movies 5★
    # Call get_recommendations()
    # Verify: results are non-empty, scores are 0-1, 
    # rated movies with score > 0, cold-start flag is False
```

2. **Cold-start test:**
```python
def test_cold_start_returns_recent_movies():
    """User with no interactions gets recent movies with score=0."""
```

3. **Cache invalidation test:**
```python
def test_cache_invalidates_on_movie_update():
    """After updating movie metadata, recommendations reflect new content."""
```

4. **Explainer consistency test:**
```python
def test_admin_explainer_matches_engine():
    """Admin explainer top-N order matches engine top-N order."""
```

5. **Empty catalog test:**
```python
def test_empty_catalog_returns_empty():
    """No movies → empty recommendation list."""
```

---

## 8. Quality Limitations Due to Dataset Size

### Current State
- ~20 seed movies in `seed.py`
- TF-IDF with `max_features=5000` on 20 documents → most features will have zero variance
- Cosine similarity on small, sparse vectors → scores cluster around 0.1-0.3 with little differentiation
- Genre overlap drives most similarity (the strongest signal with fewest unique values)

### Impact on Demo
| Dataset Size | Recommendation Quality | Demo Impression |
|-------------|----------------------|-----------------|
| 20 movies | Low differentiation | "Recommendations seem random" |
| 50 movies | Moderate — genre clusters visible | "It knows I like action movies" |
| 100+ movies | Good — cast/keyword signals emerge | "It's actually recommending similar movies" |
| 500+ movies | Strong — TF-IDF features are meaningful | Production-quality |

### Recommendation
Import at least **100 movies** with rich metadata (genres, cast, keywords, overview) before the thesis defense. The MovieLens importer script can do this. Focus on:
- At least 5 movies per major genre
- Multiple movies with shared actors/directors
- Movies with detailed keywords

---

## 9. Honest Academic Explanation

### What This System IS
A content-based movie recommendation engine that:
- Converts movie metadata into numerical vectors using TF-IDF (a well-established NLP technique)
- Builds a user preference profile from three behavioral signals (ratings, favorites, watch progress)
- Ranks movies by cosine similarity between user and movie vectors
- Handles cold-start users with a fallback strategy
- Provides transparent explanations of scoring for academic demonstration

### What This System IS NOT
- Not collaborative filtering (does not learn from other users)
- Not deep learning (no neural networks)
- Not a "Netflix-level" recommendation engine
- Not real-time learning (profile updates require re-computation)
- Not multi-modal (does not analyze video/audio content)

### How to Present in Thesis

> "The recommendation engine uses Content-Based Filtering with TF-IDF vectorization and Cosine Similarity. This approach was chosen for its interpretability, independence from a large user base, and mathematical transparency — every recommendation score can be traced back to specific user interactions and movie features. The system demonstrates three key capabilities: (1) multi-signal user profiling combining explicit and implicit feedback, (2) configurable weighting with time decay for recency bias, and (3) full algorithmic transparency through the admin explainer interface."

---

## 10. Suggested Improvements (Simple, Appropriate)

### ✅ Should Do

| # | Improvement | Effort | Impact | Files |
|---|------------|--------|--------|-------|
| 1 | Invalidate cache when HLS processing completes | 5 min | Newly-encoded movies immediately eligible | `hls_service.py` |
| 2 | Write 3-5 recommendation e2e tests | 2-3 hours | Test coverage for core feature | New test file |
| 3 | Import 100+ movies for demo | 2-3 hours | Meaningful recommendation quality | `import_movielens.py` |
| 4 | Fix cold-start "0% match" display | 15 min | Better UX | `RecommendationCard.tsx` |
| 5 | Add specific movie reference in explanation | 30 min | "Similar to 'Inception' · Strong match" | `explainer.py` |

### 🤔 Consider (Optional)

| # | Improvement | Effort | Impact | Files |
|---|------------|--------|--------|-------|
| 6 | Negative feedback: use rating 1-2★ to push profile away | 1-2 hours | Reduces filter bubble slightly | `user_profile.py` |
| 7 | Simple diversity: replace 1-2 top-N slots with different genres | 1 hour | More varied recommendations | `engine.py` |
| 8 | Add `in_candidate_pool` flag to admin explainer | 20 min | Clearer thesis demo | `explainer_admin.py` |
| 9 | Content-based hash for cache validation | 30 min | Robustness (already mitigated by `invalidate_cache()` calls) | `vectorizer.py` |
| 10 | Exclude rated movies from recommendations (configurable) | 30 min | Avoids recommending seen movies | `engine.py` |

---

## 11. Features That Should NOT Be Added Now

| Feature | Why NOT |
|---------|---------|
| **Collaborative filtering** | Requires significant user base data, changes the algorithm category, adds complexity without demo value on small dataset |
| **Deep learning / neural networks** | Wrong scope — TF-IDF is the correct choice for an interpretable, explainable academic project |
| **Real-time ML pipeline** | Overkill — batch refit on cache miss is appropriate for this scale |
| **External movie fetching** | AI should only recommend what's in the catalog — this is correctly documented |
| **Complex ranking service** | Cosine similarity ranking is sufficient and transparent |
| **A/B testing framework** | Requires production traffic volume, not applicable to academic demo |
| **Multi-language NLP** | English stopwords only — adding Vietnamese requires additional NLP pipeline |
| **Matrix factorization** | Collaborative filtering technique, not content-based |
| **Embedding models (Word2Vec, BERT)** | Replaces TF-IDF, loses interpretability advantage |
| **User segmentation / clustering** | Requires more users than an academic demo will have |

---

*This audit was conducted as a code review only. No application code was modified.*
