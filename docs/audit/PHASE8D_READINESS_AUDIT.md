# Phase 8D — Readiness Audit (Đánh giá sẵn sàng Phase 8D)

**Date**: 2026-11-06  
**Phase**: Phase 8D — Controlled Live TMDB Pilot (40 movies)  
**Prerequisite**: Phase 8C — Identity Mapping & Controlled Re-evaluation  
**Git HEAD**: `2a4c0d8`

---

## 1. Mục đích / Purpose

Tài liệu này xác nhận rằng tất cả điều kiện tiên quyết từ Phase 8A–8C đã được
hoàn thành và xác minh, cho phép Phase 8D tiến hành với pilot TMDB trực tiếp có
kiểm soát trên 40 phim.

This document validates that all Phase 8A–8C prerequisites are satisfied and
verified, clearing Phase 8D for a controlled live TMDB pilot on 40 movies.

---

## 2. Phase 8C Results Validation / Xác nhận kết quả Phase 8C

### 2.1 Identity Mapping Coverage

| Metric | Value |
|--------|-------|
| Total movies in catalog | 9,742 |
| Movies with TMDB IDs | 9,734 (99.92%) |
| Movies without TMDB IDs | 8 |
| IMDb ID coverage | ~100% |
| Missing TMDB ID movieIds | 791, 1107, 2851, 4051, 26587, 32600, 40697, 79299 |

**Validation**: Identity mapping module (`identity_mapping.py`) produces
deterministic, reproducible mappings from `links.csv`. 30 unit tests cover
loading, coverage computation, missing ID detection, forward/reverse lookups,
duplicate detection, and error handling.

### 2.2 Metadata Enrichment Success Rates (Mock)

| Metric | Value |
|--------|-------|
| Mock catalog movies enriched | 16 (Phase 8A fixtures) |
| Simulated enrichment coverage | 11/9,742 in Phase 8C dry-run |
| Field completeness improvement | 26.56% → 84.90% (16-movie benchmark) |

**Note**: Enrichment rates above are from mock/simulated data only. Live
enrichment rates will be measured during Phase 8D pilot execution.

### 2.3 Evaluation Cell Metrics (6-cell Matrix)

| Cell | Model | Metadata | Status |
|------|-------|----------|--------|
| A | TF-IDF | Original | ✅ MOCK VERIFIED |
| B | TF-IDF | Enriched | ✅ MOCK VERIFIED |
| C | Semantic-EN | Original | ✅ MOCK VERIFIED |
| D | Semantic-EN | Enriched | ✅ MOCK VERIFIED |
| E | Semantic-Multi | Original | ✅ MOCK VERIFIED |
| F | Semantic-Multi | Enriched | ✅ MOCK VERIFIED |

Statistical framework (paired t-test, Wilcoxon, Bootstrap CI) implemented and
tested. Full significance testing requires live enriched metadata at meaningful
coverage.

---

## 3. Test Suite Status / Trạng thái bộ kiểm thử

### 3.1 Backend Tests

| Component | Tests | Status |
|-----------|-------|--------|
| Pre-Phase 8 tests | 435 | ✅ ALL PASSING |
| Phase 8C identity mapping | 30 | ✅ ALL PASSING |
| **Total backend** | **465** | **✅ ALL PASSING** |

### 3.2 TEC Tests

| Component | Tests | Status |
|-----------|-------|--------|
| Pre-Phase 8C TEC tests | 34+ | ✅ ALL PASSING |
| Phase 8C collector | 6 | ✅ ALL PASSING |
| **Total TEC** | **40+** | **✅ ALL PASSING** |

### 3.3 Combined

```
Backend: 465/465 passed
TEC:     40+/40+ passed
Total:   505+ tests, 0 failures
```

---

## 4. Dataset Checksums Verification / Xác minh checksum

| Asset | SHA-256 Checksum |
|-------|-----------------|
| Dataset (ml-latest-small) | `d830d1e560efffd547d0360da5042a5d97884e5cd99dfd145ec9ecc0efbbaa86` |
| Train/Test split | `48cc8f10cce949d0add60ad6320bf75668370d1753e5456d6fbd69479f931d67` |

Both checksums are verified at CLI startup before any evaluation proceeds. If
checksums do not match, the system aborts with a clear error message.

---

## 5. TMDB Client Security Review / Đánh giá bảo mật TMDBClient

### 5.1 SSRF Protection

- Host allowlist: `api.themoviedb.org` (API), `image.tmdb.org` (images)
- Non-HTTPS schemes rejected
- Query-string injection blocked
- Arbitrary URL redirection prevented

### 5.2 Rate Limiting

- Hard limit: 4 requests per second (TMDB allows 40+ RPS, we use 10× safety margin)
- HTTP 429 `Retry-After` header respected
- Bounded retries: maximum 3 per request

### 5.3 Secret Management

- `TMDB_API_READ_ACCESS_TOKEN` read from environment variables only
- `SecretRedactionFilter` strips `Bearer <token>` from all logs
- `redact_secrets()` strips `api_key=<value>` from exception messages
- Token never appears in reports, audit logs, or JSON output

### 5.4 Mock Transport

- Default mode: `TMDB_ENABLE_LIVE_REQUESTS=false`
- Mock transport returns deterministic fixtures
- No network calls unless explicitly authorized via both:
  1. CLI flag: `--phase8d-live`
  2. Environment variable: `PHASE8D_LIVE_AUTHORIZED=true`

### 5.5 Input Sanitization

- All TMDB API responses treated as untrusted input
- HTML/script tags stripped
- Control characters removed
- Prompt-injection patterns detected and filtered

---

## 6. Authorization Gate Design / Thiết kế cổng ủy quyền

Phase 8D implements a dual-gate authorization mechanism:

```
Live mode requires BOTH:
  1. CLI flag:       --phase8d-live
  2. Environment:    PHASE8D_LIVE_AUTHORIZED=true
  3. Environment:    TMDB_ENABLE_LIVE_REQUESTS=true
  4. Environment:    TMDB_API_READ_ACCESS_TOKEN=<valid token>
```

Without ALL four conditions, the system runs in dry-run mode with mock data.
This prevents accidental live API calls during development, testing, or
unattended CI/CD runs.

---

## 7. Kết luận / Conclusion

| Criterion | Status |
|-----------|--------|
| Phase 8C identity mapping complete | ✅ VERIFIED |
| Phase 8C evaluation framework functional | ✅ MOCK VERIFIED |
| All 465 backend tests passing | ✅ VERIFIED |
| All 40+ TEC tests passing | ✅ VERIFIED |
| Dataset checksums match | ✅ VERIFIED |
| TMDB client security controls | ✅ VERIFIED |
| Authorization gate implemented | ✅ VERIFIED |
| Pilot selection algorithm implemented | ✅ VERIFIED |

**Decision: Phase 8D is READY for controlled pilot execution.**

The project owner may authorize live TMDB API access at their discretion. Until
authorization is granted, Phase 8D operates exclusively in dry-run mode with
mock data, producing structurally valid but synthetic results.
