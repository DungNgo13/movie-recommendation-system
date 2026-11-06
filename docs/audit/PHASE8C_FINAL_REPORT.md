# Phase 8C — Final Implementation Report

## Tổng quan / Overview

Phase 8C thực hiện hệ thống ánh xạ danh tính MovieLens–TMDB, hạ tầng snapshot
metadata nghiên cứu, và đánh giá lại có kiểm soát với ma trận 6 ô (3 mô hình × 2
điều kiện metadata).

Phase 8C implements the MovieLens-TMDB identity mapping system, research metadata
snapshot infrastructure, and controlled re-evaluation with a 6-cell matrix
(3 models × 2 metadata conditions).

---

## Deliverables Status

| # | Deliverable                          | Status              |
|---|--------------------------------------|---------------------|
| 1 | MovieLens–TMDB mapping audit         | ✅ IMPLEMENTED      |
| 2 | Research metadata snapshot pipeline  | ✅ IMPLEMENTED      |
| 3 | Controlled enrichment pilot (mock)   | ✅ MOCK VERIFIED    |
| 4 | Field-level coverage report          | ✅ IMPLEMENTED      |
| 5 | Identity and retrieval failure report | ✅ IMPLEMENTED      |
| 6 | Snapshot manifest and checksums      | ✅ IMPLEMENTED      |
| 7 | 6-cell TF-IDF evaluation (A–B)      | ✅ IMPLEMENTED      |
| 8 | 6-cell Semantic evaluation (C–F)     | ✅ IMPLEMENTED      |
| 9 | Statistical and temporal analysis    | ✅ IMPLEMENTED      |
| 10| TEC consolidated report              | ✅ IMPLEMENTED      |
| 11| Vietnamese thesis summary            | ✅ IMPLEMENTED      |
| 12| Exact reproduction commands          | ✅ DOCUMENTED       |
| 13| Automated tests (30 backend + 6 TEC) | ✅ ALL PASSING     |
| 14| Audit documentation (4 reports)      | ✅ WRITTEN          |

## Implementation Files

### Core Modules
| File | Lines | Purpose |
|------|-------|---------|
| `backend/app/recommendation_evaluation/identity_mapping.py` | ~260 | MovieLens–TMDB identity mapping from links.csv |
| `backend/app/recommendation_evaluation/research_snapshot.py` | ~280 | Immutable research metadata snapshot infrastructure |
| `backend/app/recommendation_evaluation/tmdb_research_retrieval.py` | ~350 | Mock TMDB retrieval, stratified sampling, coverage reporting |
| `backend/app/recommendation_evaluation/phase8c_eval.py` | ~430 | 6-cell evaluation matrix, statistical comparisons |
| `test_center/collectors/phase8c_collector.py` | ~190 | TEC Phase 8C collector |

### Modified Files
| File | Change |
|------|--------|
| `backend/app/recommendation_evaluation/cli.py` | Added `--phase8c` and `--phase8c-pilot-size` flags |
| `test_center/collectors/__init__.py` | Added `Phase8CCollector` export |

### Test Files
| File | Tests |
|------|-------|
| `backend/tests/test_phase8c_identity_mapping.py` | 30 tests |
| `test_center/tests/test_phase8c_collector.py` | 6 tests |

### Audit Documentation
| File | Content |
|------|---------|
| `docs/audit/PHASE8C_IDENTITY_MAPPING_AUDIT.md` | Mapping layer design and validation |
| `docs/audit/PHASE8C_COVERAGE_REPORT.md` | Field-level coverage methodology |
| `docs/audit/PHASE8C_TEMPORAL_VALIDITY.md` | Temporal mismatch analysis |
| `docs/audit/PHASE8C_EVALUATION_RESULTS.md` | 6-cell matrix protocol and reproduction |
| `docs/audit/PHASE8C_FINAL_REPORT.md` | This report |

## Test Results

```
Backend: 465/465 passed (435 pre-existing + 30 new Phase 8C)
TEC: 6/6 passed
Total: 471/471 passed
```

## Key Design Decisions

1. **Separate identity mapping module** (not extending `dataset.py`):
   - `dataset.py` raw checksum only covers `movies.csv`, `ratings.csv`, `tags.csv`
   - Adding `links.csv` would change checksums and invalidate cached Phase 4–8B artifacts
   - Phase 8C creates a separate `identity_mapping.py` that works alongside `dataset.py`

2. **Research snapshots as JSON files** (not PostgreSQL):
   - Complete isolation from production database
   - Immutable, checksummed, version-tracked
   - Portable (no database required for offline experiments)

3. **Mock dry-run by default**:
   - No live TMDB API calls without explicit user authorization
   - Phase 8A mock catalog provides 16 realistic test movies
   - Simulated enrichment for remaining pilot movies

4. **Extend Phase 8B patterns** (not duplicate):
   - Reuses `OfflineSemanticRecommender`, `evaluate_recommender()`, `compute_extended_paired_comparison()`
   - Same evaluation protocol, metrics, and statistical tests
   - Phase 8B artifacts preserved as historical references

## Evidence Status

| Claim | Status |
|-------|--------|
| Identity mapping is complete and auditable | ✅ IMPLEMENTED |
| Research snapshots are isolated and immutable | ✅ IMPLEMENTED |
| 6-cell evaluation runs correctly with mock data | ✅ MOCK VERIFIED |
| Metadata enrichment improves TF-IDF quality | ⚠️ PRELIMINARY (11/9742 enriched) |
| Coverage sensitivity analysis | ❌ INSUFFICIENT EVIDENCE |
| Live TMDB enrichment at scale | ❌ NOT YET AUTHORIZED |

## Readiness for Phase 9: Hybrid Lexical–Semantic Recommendation

Phase 8C provides the infrastructure for Phase 9:
- ✅ Identity mapping enables batch TMDB lookup for full catalog
- ✅ Research snapshots enable reproducible metadata states
- ✅ 6-cell matrix enables fair A/B comparison
- ✅ Statistical framework enables significance testing
- ⚠️ Actual enriched metadata coverage is still very low (mock-only)
- ⚠️ Live TMDB pilot needs authorization before Phase 9 can benefit from enriched embeddings

**Recommendation**: Authorize a bounded live TMDB pilot (e.g., 500–1000 movies)
before starting Phase 9, to provide sufficient enriched coverage for meaningful
hybrid recommendation experiments.

## Tóm tắt luận văn tiếng Việt

### Phase 8C: Ánh xạ danh tính MovieLens–TMDB và đánh giá lại có kiểm soát

Phase 8C xây dựng hạ tầng ánh xạ giữa bộ dữ liệu MovieLens và cơ sở dữ liệu
TMDB thông qua tệp `links.csv`, cho phép tra cứu metadata phong phú hơn cho
mỗi phim trong danh mục.

**Kết quả chính**:
- Ánh xạ 9.742 phim MovieLens với ID TMDB (độ phủ ~99,9%)
- Hệ thống snapshot nghiên cứu bất biến, cách ly hoàn toàn với CSDL sản xuất
- Ma trận đánh giá 6 ô: TF-IDF × Semantic-EN × Semantic-Multi × Original × Enriched
- Phân tích thống kê ghép cặp (t-test, Wilcoxon, Bootstrap CI)
- 471/471 test tự động đạt (465 backend + 6 TEC)

**Hạn chế**:
- Hiện tại chỉ sử dụng dữ liệu TMDB giả lập (16 phim từ Phase 8A)
- Phân tích độ nhạy phủ metadata: CHƯA ĐỦ BẰNG CHỨNG
- Cần ủy quyền truy cập API TMDB thực để đánh giá trên quy mô lớn
- Metadata TMDB hiện tại (2026) có thể khác so với thời điểm tương tác MovieLens (1996–2018)

## Reproduction Commands

```powershell
# 1. Run Phase 8C tests
cd d:\TLTN\movie-recommendation-system\backend
.\.venv\Scripts\python.exe -m pytest tests/test_phase8c_identity_mapping.py -v

# 2. Run TEC collector tests
cd d:\TLTN\movie-recommendation-system
d:\TLTN\movie-recommendation-system\backend\.venv\Scripts\python.exe -m pytest test_center/tests/test_phase8c_collector.py -v

# 3. Run full backend test suite (regression check)
cd d:\TLTN\movie-recommendation-system\backend
.\.venv\Scripts\python.exe -m pytest tests/ -v

# 4. Run Phase 8C evaluation (mock dry-run)
cd d:\TLTN\movie-recommendation-system\backend
.\.venv\Scripts\python.exe -m app.recommendation_evaluation.cli --phase8c

# 5. Run with semantic models
.\.venv\Scripts\python.exe -m app.recommendation_evaluation.cli --phase8c --allow-model-download --phase8c-pilot-size 200
```
