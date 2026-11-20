# Phase 8E — Live Pilot Data Audit

| Field | Value |
|---|---|
| **Phase** | 8E — Metadata Quality Audit |
| **Source Run** | `phase8d_run_002` |
| **Audit Date** | 2026-11-20 |
| **Auditor** | Automated + manual verification |
| **Status** | `AUDIT_COMPLETE` |

---

## Tóm tắt

Kiểm toán dữ liệu pilot Phase 8D.6 run_002. Tất cả 40 bản ghi được đối chiếu thành
chính xác một trong 5 trạng thái. Phát hiện 3 vấn đề báo cáo cần sửa chữa: (1) nhãn
provenance tiếng Việt luôn ghi `en-US` thay vì `vi-VN`, (2) snapshot manifest tham
chiếu đường dẫn run_001, (3) `has_vi_title=True` cho 19 phim thực chất là fallback
tiếng Anh. Kiểm toán xác nhận 36 phim `LIVE_VERIFIED`, 1 `REVIEW_REQUIRED`,
3 `MISSING_EXTERNAL_ID`, 0 `FAILED`, 0 `NOT_ATTEMPTED`.

---

## 1. Status Reconciliation (40 movies)

| Status | Count | Description |
|---|---|---|
| `LIVE_VERIFIED` | 36 | HTTP 200 + title match + year match + identity verified |
| `REVIEW_REQUIRED` | 1 | ML#284 — HTTP 200 but title mismatch (ambiguous identity) |
| `MISSING_EXTERNAL_ID` | 3 | ML#2851, #32600, #791 — no TMDB ID in links.csv |
| `FAILED` | 0 | — |
| `NOT_ATTEMPTED` | 0 | — |
| **Total** | **40** | ✅ All records reconciled |

### Verification against source artifacts

| Claimed Value | Source Artifact | Verified |
|---|---|---|
| 40 manifest records | `phase8d_pilot_manifest.json` (40 movies) | ✅ |
| 37 with TMDB IDs | `phase8d_identity_matching_report.json` (37) | ✅ |
| 36 LIVE_VERIFIED | `phase8d_data_quality.json` summary (36 successful) | ✅ |
| 1 ambiguous identity | `phase8d_failure_report.json` ML#284 | ✅ |
| 3 missing TMDB IDs | ML#2851, #32600, #791 | ✅ |
| 74 HTTP attempts | `phase8d_request_statistics.json` (74) | ✅ |
| 0 retries | `phase8d_request_statistics.json` (retry_count: 0) | ✅ |
| 0 API errors | `phase8d_request_statistics.json` (requests_failed: 0) | ✅ |
| Budget 100 | `phase8d_request_statistics.json` (approved: 100) | ✅ |
| run_001 unchanged | checkpoint.json last modified 2026-11-10 | ✅ |
| 0 DB writes | No database files modified | ✅ |

---

## 2. Reporting Inconsistencies Found

### Issue 1: Vietnamese Title Provenance Mislabeled

**Finding:** All 37 `title_vi` provenances in `phase8d_data_quality.json` show
`tmdb:movie/{id}:en-US` — none show `vi-VN`. This is a code-level bug in
`phase8d_live_pilot.py`'s provenance tracking: the Vietnamese localization request
(`GET /movie/{id}?language=vi-VN`) returns data, but the provenance label still
records the en-US source string.

**Impact:** Provenance metadata is unreliable for distinguishing authentic Vietnamese
translations from English fallbacks.

**Actual Vietnamese title breakdown (verified from snapshot data):**

| Category | Count | % of 37 Queried |
|---|---|---|
| Authentic Vietnamese title | 18 | 48.6% |
| English fallback (identical to EN) | 19 | 51.4% |

### Issue 2: Snapshot Manifest References Wrong Paths

**Finding:** `phase8d_snapshot_manifest.json` artifacts section references:
- `backend/reports/phase8d_pilot/phase8d_pilot_manifest.json` ← **run_001 path**
- `backend/reports/phase8d_pilot/snapshots/phase8d_pilot_snapshot.json` ← **run_001 path**

Should reference `phase8d_pilot_run_002/` paths.

**Root cause:** Hardcoded path in `_save_research_snapshot()` (line 1504–1509 of
`phase8d_live_pilot.py`), as identified in Phase 8D.6 planning.

**Impact:** Checksum verification against manifest paths would fail or verify
wrong files.

### Issue 3: `has_vi_title` Denominator Ambiguity

**Finding:** The field completeness report claims `has_vi_title: 37/37 queried (100%)`.
However, 19 of these 37 "Vietnamese titles" are identical to the English title —
they are TMDB's language fallback, not authentic translations.

**Corrected metrics (of 37 queried movies):**

| Field | Reported | Corrected | Notes |
|---|---|---|---|
| has_vi_title (any) | 37 (100%) | 37 (100%) | Technically correct — field is non-empty |
| has_vi_title (authentic) | — | **18 (48.6%)** | Actual Vietnamese translations |
| has_vi_title (EN fallback) | — | **19 (51.4%)** | English title returned as fallback |
| has_vi_overview (any) | 12 (32.4%) | 12 (32.4%) | ✅ Correct — all 12 are authentic |

### Issue 4: Completeness Denominator Choice

**Finding:** The report uses two denominators:
- "of 40" (pilot size) for `pct_of_pilot_40`
- "of 37" (queried) for `pct_of_queried`

The ambiguous movie ML#284 (REVIEW_REQUIRED) **contributes** to both denominators.
It has `has_overview=True, has_cast=True, has_director=True, has_vi_title=True`
but its identity is unverified.

**Recommendation:** For research use, report completeness using denominator of
**36 LIVE_VERIFIED movies only**. The ambiguous movie's data should not be used
in experiments without manual identity confirmation.

### Issue 5: Latency Metric Interpretation

**Finding:** The report's p50=534.97ms and p95=692.93ms are computed **per HTTP
attempt** (74 individual requests). The per-movie latency (sum of 2 requests)
has p50=1078.5ms, p95=1711.5ms.

Both are valid but serve different purposes. The report should clarify which is used.

---

## 3. ML#284 (New York Cop) — Ambiguous Identity Detail

| Property | Value |
|---|---|
| MovieLens ID | 284 |
| MovieLens title | New York Cop (Nyû Yôku no koppu) (1993) |
| TMDB ID (from links.csv) | 109560 |
| TMDB title | New York Undercover Cop |
| TMDB original title | New York Undercover Cop |
| TMDB release | 1993-08-14 |
| IMDb ID | tt0117169 |
| Title match | ❌ False |
| Year match | ✅ True |
| Classification | `ambiguous_match` / `REVIEW_REQUIRED` |

**Assessment:** The year matches but the titles differ ("New York Cop" vs.
"New York Undercover Cop"). This is likely the same film known by different titles.
However, automatic promotion to LIVE_VERIFIED is prohibited. Manual review is required.

**Data retrieved:** Overview (EN), cast, director, VI title (fallback). Missing:
keywords, VI overview.

---

## 4. Snapshot Integrity

| Check | Result |
|---|---|
| Snapshot records | 37 movies (matches queried count) |
| Snapshot timestamp | `2026-11-20T04:27:58.604887+00:00` |
| Manifest checksum | `d23fc802aefe509088127ede5d03009bc22354165d1b1adbc8f4906567d8800c` |
| Snapshot SHA-256 | `a92f40184550596322aeca21677f79c4c69a0cd07027be2d441c33354934c153` |
| Path reference bug | ⚠️ Manifest references run_001 paths (see Issue 2) |

---

## 5. Audit Verdict

The Phase 8D.6 execution was **technically successful**. The claimed metrics are
**factually correct** when taken at face value. However, 3 reporting-level issues
require amendment:

1. Vietnamese title authenticity must distinguish fallbacks from translations
2. Snapshot manifest paths must reference run_002
3. Provenance labels need a code fix for future runs

**No data was fabricated. No results were altered. Historical evidence is preserved.**
