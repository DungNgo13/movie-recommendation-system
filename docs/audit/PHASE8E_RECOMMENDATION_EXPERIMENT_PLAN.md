# Phase 8E — Recommendation Experiment Plan

| Field | Value |
|---|---|
| **Phase** | 8E — Experiment Design |
| **Date** | 2026-11-20 |
| **Status** | `DESIGN_READY` |

---

## Tóm tắt

Thiết kế thí nghiệm so sánh công bằng giữa 6 điều kiện: TF-IDF v1.1 và Semantic
Embeddings (EN/Multi) trên metadata gốc (A) và metadata làm giàu (B). Sử dụng cùng
bộ chia dữ liệu, ngưỡng liên quan, và hệ số đánh giá. Báo cáo thí nghiệm
toàn bộ danh mục và nhóm phù hợp riêng biệt. Bao gồm phân tích đa giả thuyết
và hạn chế thời gian.

---

## 1. Experimental Conditions

| ID | Algorithm | Metadata | Description |
|---|---|---|---|
| **A-TFIDF** | TF-IDF v1.1 | Original MovieLens | Baseline: title + genres + tags |
| **B-TFIDF** | TF-IDF v1.1 | Enriched (TMDB) | + overview + cast + director + keywords |
| **C-SemEN** | Semantic-EN | Original MovieLens | `all-MiniLM-L6-v2` on original text |
| **D-SemEN** | Semantic-EN | Enriched (TMDB) | `all-MiniLM-L6-v2` on enriched text |
| **E-SemMulti** | Semantic-Multi | Original MovieLens | `paraphrase-multilingual-MiniLM-L12-v2` on original |
| **F-SemMulti** | Semantic-Multi | Enriched (TMDB) | `paraphrase-multilingual-MiniLM-L12-v2` on enriched (EN + VI) |

### Optional Frozen Baselines

| ID | Algorithm | Notes |
|---|---|---|
| **G-MMR0.5** | TF-IDF v1.1 + MMR (λ=0.5) | Frozen Phase 6 baseline |
| **H-MMR0.7** | TF-IDF v1.1 + MMR (λ=0.7) | Frozen Phase 6 baseline |

---

## 2. Frozen Evaluation Protocol

Reuse the exact protocol from Phase 8B to ensure comparability:

| Parameter | Value |
|---|---|
| Dataset | MovieLens `ml-latest-small` (100,836 ratings, 9,742 movies, 610 users) |
| Dataset SHA-256 | `d830d1e560efffd547d0360da5042a5d97884e5cd99dfd145ec9ecc0efbbaa86` |
| Split | Per-user temporal (80% train / 20% test) |
| Split SHA-256 | `48cc8f10cce949d0add60ad6320bf75668370d1753e5456d6fbd69479f931d67` |
| Relevance threshold | rating ≥ 4.0 |
| Active users | 587 (with ≥1 relevant test item) |
| Seen-item exclusion | `exclude_seen = "train"` |
| Cutoffs | K ∈ {5, 10, 20} (primary: K=10) |
| Tie-breaking | Descending score (12 decimals), ascending movie_id |

> [!CAUTION]
> Do NOT modify the dataset split, relevance threshold, or evaluation protocol.
> Any change invalidates comparisons with Phase 4/5/6/8B historical baselines.

---

## 3. Experimental Protocols

### Protocol 1: Full-Catalog Evaluation (9,742 candidates)

All 9,742 movies serve as the candidate pool. Enriched movies have TMDB metadata;
unenriched movies use original MovieLens metadata only.

| Metric | A vs. B | C vs. D | E vs. F |
|---|---|---|---|
| NDCG@K | ✓ | ✓ | ✓ |
| Precision@K | ✓ | ✓ | ✓ |
| Recall@K | ✓ | ✓ | ✓ |
| MAP@K | ✓ | ✓ | ✓ |
| Coverage | ✓ | ✓ | ✓ |
| ILD@K (diversity) | Optional | Optional | Optional |

**Users:** All 587 active users.

**Interpretation:** With ~500 enriched movies (5.1% of catalog), the effect size
will be small in full-catalog evaluation. This is the realistic scenario but may
not reach statistical significance.

### Protocol 2: Matched-Cohort Evaluation (500 enriched candidates)

Restrict the candidate pool to only the ~500 enriched movies. Only users with ≥1
relevant (rating ≥4.0) test item in the enriched cohort are included.

| Property | Value |
|---|---|
| Candidate pool | ~500 enriched movies |
| Users | Subset with relevant test items in cohort |
| Minimum users | ≥30 (for paired statistical tests) |

**Interpretation:** Higher sensitivity to metadata quality differences, but limited
to a small candidate pool. NDCG@10 on a 500-item pool is NOT comparable to
NDCG@10 on a 9,742-item pool.

> [!WARNING]
> Report full-catalog and matched-cohort results **separately**. Do not compare
> NDCG@10 across different candidate pool sizes.

---

## 4. Text Construction Policy

Reuse the Phase 8B text builder (`build_movie_RenderText` v8b.1):

### Condition A/C/E (Original):
```
Title: <title>. Genres: <g1, g2, ...>. Keywords: <tags from MovieLens>.
```

### Condition B/D (Enriched EN-only):
```
Title: <title>. Original Title: <original_title>. Genres: <g1, g2, ...>.
Directed by: <d1, ...>. Cast: <c1, ...>. Keywords: <k1, ...>.
Overview: <overview>.
```

### Condition F (Enriched Multilingual):
```
Title: <title>. Original Title: <original_title>. Vietnamese Title: <title_vi>.
Genres: <g1, g2, ...>. Directed by: <d1, ...>. Cast: <c1, ...>.
Keywords: <k1, ...>. Overview: <overview>. Vietnamese Overview: <overview_vi>.
```

> [!NOTE]
> Only authentic Vietnamese translations should be included in Condition F.
> English fallback titles/overviews must be excluded to avoid noise.

---

## 5. Historical Baseline Preservation

| Baseline | Checksum | Status |
|---|---|---|
| TF-IDF v1.0 (Phase 4) | Recorded | Frozen |
| TF-IDF v1.1 (Phase 5) | Recorded | Frozen |
| MMR ablation (Phase 6) | Recorded | Frozen |
| Semantic 8B Condition A | Recorded | Frozen |
| Semantic 8B Condition B1/B2 | Recorded | Frozen |

New conditions (B-TFIDF, D-SemEN, F-SemMulti) will be compared against these
frozen baselines but reported as new experiments with their own checksums.

---

## 6. Multiple Hypothesis Testing

With 6 primary conditions and 3 pairwise comparisons (A↔B, C↔D, E↔F), plus
2 protocols × 3 cutoffs = 18 comparisons:

| Correction | Method |
|---|---|
| Family-wise error rate | Bonferroni correction (α/18) |
| False discovery rate | Benjamini-Hochberg (preferred for exploratory) |
| Effect sizes | Report Cohen's d alongside p-values |
| Confidence intervals | 95% CI for all primary metrics |

---

## 7. Temporal Limitations

> [!WARNING]
> **Critical caveat:** TMDB metadata is retrieved in 2026 but applied to MovieLens
> interactions from 2018. This creates a temporal mismatch:
>
> - Movie overviews may have been updated since 2018
> - Cast/crew credits may have been revised
> - Vietnamese translations may not have existed during the rating period
> - Keywords may have been added retroactively
>
> This limitation must be disclosed in any experimental report. The enrichment
> improves metadata *completeness* but does not perfectly reconstruct the
> information landscape available to users at rating time.

---

## 8. Experiment Execution Prerequisites

Before running any enriched-metadata experiment:

1. ✅ Complete Stage 1 validation batch (50 movies)
2. ✅ Complete Stage 2 main batch (~414 movies)
3. ✅ Create research-ready snapshot excluding ambiguous identities
4. ✅ Verify field-level coverage meets minimum thresholds
5. ✅ Verify user overlap in matched-cohort (≥30 active users)
6. ✅ Build enriched text representations using correct text builder
7. ✅ Compute and record all experiment checksums
8. ❌ Do NOT start experiments before data collection is complete
