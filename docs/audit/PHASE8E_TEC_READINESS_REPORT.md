# Phase 8E — TEC Readiness Report

| Field | Value |
|---|---|
| **Phase** | 8E — TEC Readiness Assessment |
| **Date** | 2026-11-20 |
| **Status** | `NOT_READY — DATA_COLLECTION_PENDING` |

---

## Tóm tắt

Báo cáo đánh giá mức độ sẵn sàng của dữ liệu pilot Phase 8D.6 cho các thí nghiệm
khuyến nghị. Kết luận: dữ liệu pilot (36 phim) đủ cho kiểm chứng pipeline nhưng
KHÔNG đủ cho thí nghiệm khuyến nghị quy mô lớn. Cần thu thập thêm ~464 phim
(giai đoạn mở rộng). TEC collector hiện tại có vấn đề đường dẫn hardcoded cần
cập nhật cho run_002 và expansion. Snapshot nghiên cứu dẫn xuất (36 bản ghi
`LIVE_VERIFIED`) đã được tạo với các cờ xác thực ngôn ngữ.

---

## 1. Identity Coverage

| Metric | Value | Status |
|---|---|---|
| Pilot manifest | 40 movies | ✅ Reconciled |
| Movies with TMDB ID | 37 / 40 | ✅ |
| LIVE_VERIFIED | 36 / 37 queried | ✅ |
| REVIEW_REQUIRED | 1 (ML#284) | ⚠️ Ambiguous identity |
| MISSING_EXTERNAL_ID | 3 (ML#2851, #32600, #791) | — No data available |
| Identity confidence HIGH | 36 / 37 | 97.3% |

> [!NOTE]
> ML#284 (New York Cop / New York Undercover Cop) requires manual review.
> Do NOT automatically promote to LIVE_VERIFIED.

---

## 2. Field-Level Completeness (36 LIVE_VERIFIED)

| Field | Coverage | Authentic | Notes |
|---|---|---|---|
| EN overview | 36/36 (100%) | ✅ | — |
| EN keywords | 35/36 (97.2%) | ✅ | Missing: ML#70301 (Obsessed) |
| EN cast (top 10) | 36/36 (100%) | ✅ | — |
| EN director | 36/36 (100%) | ✅ | — |
| EN genres | 36/36 (100%) | ✅ | — |
| EN release_date | 36/36 (100%) | ✅ | — |
| VI title (authentic) | 18/36 (50.0%) | ✅ | Excludes 18 EN fallbacks |
| VI title (any) | 36/36 (100%) | ⚠️ | Includes 18 EN fallback titles |
| VI overview (authentic) | 12/36 (33.3%) | ✅ | No EN fallbacks — TMDB returns empty |

### Denominator Correction

The original Phase 8D.6 report used denominator 37 (all queried movies). The
research-safe denominator is **36** (LIVE_VERIFIED only), excluding ML#284.

| Field | Reported (of 37) | Corrected (of 36) |
|---|---|---|
| EN overview | 37/37 (100%) | 36/36 (100%) |
| EN keywords | 35/37 (94.6%) | 35/36 (97.2%) |
| VI title (authentic) | — | 18/36 (50.0%) |
| VI overview | 12/37 (32.4%) | 12/36 (33.3%) |

---

## 3. Language Authenticity Assessment

### Vietnamese Title Authenticity

| Determination Method | Result |
|---|---|
| Heuristic | Compare `vi-VN` title to `en-US` title |
| Authentic = different from EN | 18 movies (50.0%) |
| Fallback = identical to EN | 18 movies (50.0%) |
| Limitation | Same title in both languages misclassified as fallback |

### Vietnamese Overview Authenticity

| Category | Count |
|---|---|
| Authentic VI overview | 12 (33.3%) |
| Missing (empty from TMDB) | 24 (66.7%) |
| EN fallback | 0 (TMDB returns empty, not EN fallback) |

### For Thesis (Vietnamese)

Đối với luận văn: 18/36 phim (50.0%) có tiêu đề tiếng Việt xác thực, 12/36
(33.3%) có tóm tắt tiếng Việt. Tỷ lệ này sẽ giảm khi mở rộng sang phim ít
phổ biến (long-tail) vì TMDB ít có bản dịch tiếng Việt cho phim không phổ biến.

Phương pháp phân loại: so sánh giá trị trả về từ endpoint `vi-VN` với endpoint
`en-US`. Nếu giống nhau → fallback. Nếu khác nhau → xác thực. Phương pháp này
bảo thủ (conservative): một số phim có thể dùng cùng tiêu đề trong cả hai ngôn
ngữ nhưng bị phân loại nhầm là fallback.

---

## 4. Source Provenance Issues

### Bug: Provenance Labels Show Wrong Locale

| Issue | Detail |
|---|---|
| **Affected fields** | `title_vi`, `overview_vi` provenance labels |
| **Expected** | `tmdb:movie/{id}:vi-VN` |
| **Actual** | `tmdb:movie/{id}:en-US` |
| **Root cause** | `phase8d_live_pilot.py` copies en-US provenance template |
| **Impact** | Cannot distinguish VI source from EN source via provenance |
| **Fix status** | Documented — fix required before expansion runs |

### Bug: Snapshot Manifest Path References

| Issue | Detail |
|---|---|
| **Affected file** | `phase8d_snapshot_manifest.json` |
| **Expected paths** | `backend/reports/phase8d_pilot_run_002/...` |
| **Actual paths** | `backend/reports/phase8d_pilot/...` (run_001) |
| **Root cause** | Hardcoded in `_save_research_snapshot()` lines 1504–1509 |
| **Impact** | Checksum verification against manifest paths would fail |
| **Fix status** | Documented — fix required before expansion runs |

---

## 5. Unresolved Identity Conflicts

| ML ID | TMDB ID | ML Title | TMDB Title | Status | Recommendation |
|---|---|---|---|---|---|
| 284 | 109560 | New York Cop (1993) | New York Undercover Cop | REVIEW_REQUIRED | Manual confirmation needed |

**Decision required:** Is ML#284 the same film as TMDB#109560? The year matches
(1993), IMDb ID tt0117169 is consistent, but titles differ. This is likely an
alternative title / regional title variant. If confirmed manually, the movie can
be promoted to LIVE_VERIFIED in future runs.

---

## 6. Snapshot Validation

| Artifact | SHA-256 | Records | Status |
|---|---|---|---|
| Source snapshot (`phase8d_pilot_snapshot.json`) | `a92f40184...c153` | 37 | ✅ Immutable |
| Source manifest (`phase8d_snapshot_manifest.json`) | — | — | ⚠️ Path bug |
| **Research snapshot** (`phase8e_research_snapshot.json`) | `136de100a...7864` | **36** | ✅ Derived |

### Research Snapshot Properties

| Property | Value |
|---|---|
| Records | 36 (LIVE_VERIFIED only) |
| Excluded | ML#284 (ambiguous), ML#2851/#32600/#791 (no TMDB ID) |
| Authenticity flags | `is_vi_title_authentic`, `is_vi_overview_authentic` per movie |
| Source linkage | SHA-256 of source snapshot recorded |
| Mutability | Immutable derived artifact |

---

## 7. Proposed Expansion Request Budget

| Stage | Movies | HTTP Attempts | Retry Buffer | Output Dir |
|---|---|---|---|---|
| Stage 1 (validation) | 50 | 120 | 20 (17%) | `backend/reports/phase8e_stage1/` |
| Stage 2 (main batch) | ~414 | 920 | ~83 (9%) | `backend/reports/phase8e_stage2/` |
| **Combined** | **~464** | **1,040** | **~103** | — |

> [!IMPORTANT]
> Each stage requires separate owner authorization with explicit run ID,
> movie count, budget, rate limit, and network confirmation.
> Unused run_002 budget (26 remaining) must NOT be reused.

---

## 8. Research Comparability Assessment

### Protocol 1: Full-Catalog (9,742 candidates)

| Factor | Assessment |
|---|---|
| Candidate pool | 9,742 movies |
| Enriched movies | ~500 (5.1% of catalog) |
| Expected effect size | Small — most candidates unenriched |
| Statistical power | Low for detecting enrichment benefit |
| Comparability with Phase 4/5/6/8B | ✅ Same split, threshold, protocol |

### Protocol 2: Matched-Cohort (500 enriched candidates)

| Factor | Assessment |
|---|---|
| Candidate pool | ~500 enriched movies only |
| Minimum users | ≥30 with relevant test items in cohort |
| Expected effect size | Moderate to large |
| Statistical power | Adequate if user overlap ≥30 |
| Comparability with Phase 4/5/6/8B | ❌ Different candidate pool size |

> [!WARNING]
> NDCG@10 on a 500-item pool is NOT comparable to NDCG@10 on a 9,742-item pool.
> Report Protocol 1 and Protocol 2 results separately.

---

## 9. Experiment Readiness Verdict

| Prerequisite | Status | Blocking |
|---|---|---|
| Phase 8D.6 pilot data collected | ✅ Complete | — |
| Pilot data audited | ✅ 5 issues documented | — |
| Research snapshot created | ✅ 36 records | — |
| Expansion Stage 1 collected | ❌ Pending authorization | **YES** |
| Expansion Stage 2 collected | ❌ Pending authorization | **YES** |
| Provenance bug fixed | ❌ Documented, not yet fixed | Yes (for expansion) |
| Snapshot path bug fixed | ❌ Documented, not yet fixed | Yes (for expansion) |
| User overlap verified | ❌ Cannot verify until 500 movies enriched | **YES** |
| Text builder implemented | ❌ Design only | Yes |
| Experiment checksums recorded | ❌ Pending data | Yes |

### Verdict: **NOT READY**

The pilot data is sufficient for **pipeline validation** and **methodology design**.
It is NOT sufficient for **recommendation experiments**. The expansion data
collection (Stages 1 and 2) must be completed first.

---

## 10. TEC Collector Status

### Current State

The TEC collector at `test_center/collectors/phase8d_collector.py` has:

| Issue | Detail |
|---|---|
| **Hardcoded paths** | `backend/reports/phase8d_pilot/` (run_001 paths) |
| **Missing run_002 support** | Cannot read `phase8d_pilot_run_002/` artifacts |
| **Missing expansion support** | Cannot read `phase8e_stage1/` or `phase8e_stage2/` |
| **No multi-run awareness** | Only reads one pilot directory |

### Required Updates for Expansion

1. **Parameterize report directory** — Accept run ID as a constructor argument
   or scan multiple report directories
2. **Add run_002 paths** — Support `phase8d_pilot_run_002/` alongside run_001
3. **Add expansion paths** — Support `phase8e_stage1/` and `phase8e_stage2/`
4. **Multi-run aggregation** — Aggregate metrics across runs for TEC dashboard
5. **Research snapshot validation** — Verify `phase8e_research_snapshot.json` checksum

> [!NOTE]
> These changes should be implemented and tested BEFORE expansion execution.
> The collector code should NOT be modified without corresponding tests.

---

## 11. Vietnamese Thesis-Ready Summary

### Tóm tắt cho luận văn

**Trạng thái sẵn sàng thí nghiệm:** CHƯA SẴN SÀNG

**Dữ liệu pilot (Phase 8D.6):**
- 36 phim xác minh danh tính (`LIVE_VERIFIED`) từ bộ 40 phim thử nghiệm
- 74 HTTP request, 0 lỗi, 0 retry, trên mạng 4G WAN
- Chất lượng metadata tiếng Anh: overview 100%, keywords 97.2%, cast 100%, director 100%
- Tiêu đề tiếng Việt xác thực: 18/36 (50.0%)
- Tóm tắt tiếng Việt xác thực: 12/36 (33.3%)

**Các vấn đề đã phát hiện:**
1. Nhãn provenance tiếng Việt ghi sai `en-US` thay vì `vi-VN` → bug code
2. Snapshot manifest tham chiếu đường dẫn run_001 → bug hardcoded
3. 18 tiêu đề "tiếng Việt" thực chất là tiếng Anh fallback
4. ML#284 cần xác minh thủ công
5. Latency per-movie (~1,079ms p50) khác per-request (~535ms p50)

**Bước tiếp theo:**
1. Yêu cầu ủy quyền cho Stage 1 mở rộng (50 phim, 120 HTTP attempts)
2. Yêu cầu ủy quyền cho Stage 2 mở rộng (~414 phim, 920 HTTP attempts)
3. Sửa bug provenance và snapshot path trước khi chạy expansion
4. Tạo text builder cho 6 điều kiện thí nghiệm
5. Xác minh user overlap sau khi có 500 phim enriched
