# Phase 8E — Expansion Sampling Plan

| Field | Value |
|---|---|
| **Phase** | 8E — Scaled Enrichment Planning |
| **Date** | 2026-11-20 |
| **Proposed Cohort** | ~500 movies (staged) |
| **Status** | `PLAN_PENDING_AUTHORIZATION` |

---

## Tóm tắt

Kế hoạch mở rộng thu thập metadata TMDB từ 36 phim pilot sang ~500 phim, sử dụng
lấy mẫu phân tầng từ bộ dữ liệu MovieLens ml-latest-small (9,742 phim, 610
người dùng, 100,836 đánh giá). Kế hoạch bao gồm: tiêu chí lấy mẫu, phân tầng
theo tần suất tương tác và thể loại, ước tính ngân sách, và đánh giá tính đầy đủ
thống kê. Yêu cầu ủy quyền riêng trước khi thực thi.

> [!IMPORTANT]
> Kế hoạch này KHÔNG tự động quyết định rằng 500 phim là đủ.
> Phần 5 đánh giá tính đầy đủ.

---

## 1. Catalog Statistics (MovieLens ml-latest-small)

| Property | Value |
|---|---|
| Total movies | 9,742 |
| Total users | 610 |
| Total ratings | 100,836 |
| Movies with TMDB ID | 9,734 (99.9%) |
| Movies without TMDB ID | 8 (0.1%) |
| Movies with tags | 1,572 (16.1%) |
| Movies without tags | 8,170 (83.9%) |

### Interaction Frequency Distribution

| Stratum | Ratings per Movie | Movies | % of Catalog |
|---|---|---|---|
| Unrated | 0 | 18 | 0.2% |
| Long-tail | 1–5 | 6,456 | 66.3% |
| Low-moderate | 6–20 | 2,033 | 20.9% |
| Moderate | 21–50 | 799 | 8.2% |
| Popular | 51–100 | 302 | 3.1% |
| Highly popular | 100+ | 134 | 1.4% |

### Decade Distribution

| Decade | Movies |
|---|---|
| Pre-1950s | 383 |
| 1950s | 279 |
| 1960s | 401 |
| 1970s | 500 |
| 1980s | 1,177 |
| 1990s | 2,212 |
| 2000s | 2,849 |
| 2010s | 1,931 |

---

## 2. Stratified Sampling Protocol

### 2.1 Stratification Dimensions

A ~500 movie cohort should be stratified across:

**Dimension 1: Interaction frequency (primary)**

| Stratum | Target % | Target N | Source Pool |
|---|---|---|---|
| Highly popular (100+) | 20% | 100 | 134 available |
| Popular (51–100) | 15% | 75 | 302 available |
| Moderate (21–50) | 20% | 100 | 799 available |
| Low-moderate (6–20) | 25% | 125 | 2,033 available |
| Long-tail (1–5) | 20% | 100 | 6,456 available |
| **Total** | **100%** | **500** | |

**Rationale:** Over-samples popular movies (users interact with them, providing
evaluation signal) while including substantial long-tail representation to test
generalization beyond blockbusters.

**Dimension 2: Genre coverage**

Ensure each of the top 15 genres has ≥10 movies in the cohort. Within each frequency
stratum, sample proportionally to genre distribution.

**Dimension 3: Release decade**

Ensure each decade from 1950s through 2010s has ≥20 movies. Pre-1950s: best effort.

**Dimension 4: Original language**

Include both English and non-English originals. Target ≥50 non-English-original movies
(~10% of cohort), reflecting the catalog's international content.

**Dimension 5: Tag availability**

Include ≥80 movies with tags and ≥420 without tags, proportional to catalog distribution.

### 2.2 TMDB ID Eligibility

| Category | Count | Eligible |
|---|---|---|
| With TMDB ID | 9,734 | ✅ Yes |
| Without TMDB ID | 8 | ❌ No |
| Already retrieved (pilot) | 36 | ✅ Include, skip re-retrieval |

Movies already retrieved in the pilot (36 LIVE_VERIFIED) may be included in the
cohort for analysis but should **not** be re-retrieved. Net new retrievals:
500 − 36 overlap ≈ **~464 new movies**.

### 2.3 Seed and Reproducibility

- Random seed: TBD (to be declared before execution, e.g., `seed=8043`)
- Sampling script: deterministic, producing a manifest with SHA-256 checksum
- Stratification parameters documented in manifest

---

## 3. Staged Execution

> [!IMPORTANT]
> The expansion should proceed in stages, not as a single 500-movie batch.

### Stage 1: Validation Batch (50 movies)

| Property | Value |
|---|---|
| Size | 50 new movies |
| Purpose | Validate pipeline at scale, estimate error rates |
| Budget | 100 + 20 retries = **120 HTTP attempts** |
| Duration | ~30 seconds at 4 RPS |
| Checkpoint | Independent from pilot |
| Authorization | Separate required |

### Stage 2: Main Batch (remaining ~414 movies)

| Property | Value |
|---|---|
| Size | ~414 new movies (adjustable after Stage 1) |
| Purpose | Complete the 500-movie target |
| Budget | 828 + ~83 retries = **~911 HTTP attempts** |
| Duration | ~4 minutes at 4 RPS |
| Checkpoint | Resumable from Stage 1 |
| Authorization | Separate required |

---

## 4. Expected Metadata Coverage

Based on the pilot's 36-movie sample:

| Field | Pilot Rate | Expected at 500 |
|---|---|---|
| EN overview | 100% | ~98–100% |
| EN keywords | 97.2% | ~90–97% |
| EN cast | 100% | ~98–100% |
| EN director | 100% | ~98–100% |
| VI title (authentic) | 48.6% | ~30–50% |
| VI overview | 32.4% | ~20–35% |

> [!NOTE]
> Pilot sample is biased toward well-known movies. Long-tail movies may have
> lower Vietnamese coverage and potentially lower keyword/cast coverage.

---

## 5. Statistical Sufficiency Assessment

### 5.1 Is 500 movies "enough" for ranking experiments?

**It depends on the experimental design:**

| Design | Requirement | 500 Movies | Verdict |
|---|---|---|---|
| Full-catalog evaluation | All 9,742 movies as candidates | 500 enriched + 9,242 unenriched | Partial enrichment (~5%) |
| Matched-cohort evaluation | Only enriched movies as candidates | 500 items | Moderate — depends on user overlap |
| Per-genre analysis | ≥30 movies per genre | Only for top ~8 genres | Insufficient for rare genres |
| Statistical significance | ≥30 users with ≥1 relevant enriched item | Needs verification | Depends on rating overlap |

**Key concern: User coverage**

With 610 users and 100,836 ratings:
- Average ratings per user: ~165
- If 500 movies are enriched, a user needs ≥1 of those 500 in their test set
- Estimated user coverage: ~300–400 users (needs verification after sampling)
- Minimum for paired t-test: ~30 users per condition

**Recommendation:** 500 movies is a **reasonable starting point** for exploratory
analysis and pilot experiments. It is NOT automatically sufficient for confirmatory
hypothesis testing. After Stage 1, compute actual user overlap and adjust if needed.

### 5.2 What would "sufficient" look like?

| Cohort Size | Catalog Coverage | Estimated User Coverage | Verdict |
|---|---|---|---|
| 500 | 5.1% | ~300–400 users | Exploratory |
| 1,000 | 10.3% | ~450–500 users | Moderate confidence |
| 2,000 | 20.5% | ~550–580 users | Strong confidence |
| 9,734 | 100% | 610 users | Full catalog |

---

## 6. Failure Handling

| Failure Type | Strategy |
|---|---|
| HTTP 429 | Retry with backoff (counted in budget) |
| HTTP 5xx | Retry with backoff (counted in budget) |
| Network timeout | Retry (counted in budget) |
| Circuit breaker trip | Stop, checkpoint, resume later |
| Budget exhausted | Stop, record NOT_ATTEMPTED for remaining |
| Identity conflict | Record as REVIEW_REQUIRED, exclude from research |
| Missing TMDB ID | Record as MISSING_EXTERNAL_ID, skip |

---

## 7. Authorization Requirements

> [!CAUTION]
> Each stage requires a **separate** owner authorization with:
> - Explicit run ID (e.g., `phase8e_stage1_run_001`)
> - Exact movie count
> - Maximum HTTP attempts (including retries)
> - Rate limit
> - Output path
> - Network confirmation

**Unused budget from run_002 (26 remaining) must NOT be reused.**
Each new run starts with a fresh budget allocation.
