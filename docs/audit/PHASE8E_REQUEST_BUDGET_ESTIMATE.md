# Phase 8E — Request Budget Estimate

| Field | Value |
|---|---|
| **Phase** | 8E — Budget Planning |
| **Date** | 2026-11-20 |
| **Status** | `ESTIMATE_READY` |

---

## Tóm tắt

Ước tính ngân sách yêu cầu HTTP cho kế hoạch mở rộng thu thập TMDB. Dựa trên kết
quả pilot (0% tỷ lệ thử lại trên mạng 4G), ước tính dự phòng 10% cho thử lại.
Tổng: Stage 1 = 120, Stage 2 = 920, tổng cộng = 1,040 HTTP attempts.

---

## 1. Pilot Baseline (run_002)

| Metric | Value |
|---|---|
| Movies retrieved | 37 |
| HTTP attempts | 74 |
| Retries | 0 (0%) |
| HTTP 429 | 0 |
| HTTP 5xx | 0 |
| Network errors | 0 |
| Latency p50 | 535 ms |
| Latency p95 | 693 ms |
| Duration | 42.3 seconds |
| Max RPS | 3.0 |

---

## 2. Stage 1: Validation Batch (50 new movies)

| Component | Count |
|---|---|
| New movies to retrieve | 50 |
| Requests per movie | 2 (EN + VI) |
| Base requests | 100 |
| Retry allowance (20%) | 20 |
| **Total budget** | **120 HTTP attempts** |

| Metric | Estimate |
|---|---|
| Duration at 4 RPS | ~30 seconds |
| Duration at 3 RPS (observed) | ~40 seconds |
| Storage | ~250 KB |
| Checkpoint | `backend/reports/phase8e_stage1/checkpoint/` |

---

## 3. Stage 2: Main Batch (~414 new movies)

| Component | Count |
|---|---|
| New movies to retrieve | ~414 |
| Requests per movie | 2 |
| Base requests | ~828 |
| Retry allowance (10%) | ~83 |
| **Total budget** | **~920 HTTP attempts** |

| Metric | Estimate |
|---|---|
| Duration at 4 RPS | ~230 seconds (~3.8 minutes) |
| Duration at 3 RPS | ~307 seconds (~5.1 minutes) |
| Storage | ~2.1 MB |
| Checkpoint | `backend/reports/phase8e_stage2/checkpoint/` |

---

## 4. Combined Total

| Component | Attempts |
|---|---|
| Stage 1 | 120 |
| Stage 2 | 920 |
| **Combined** | **1,040** |

| Metric | Total |
|---|---|
| Combined duration | ~5.5–6.5 minutes |
| Combined storage | ~2.4 MB |
| New movies enriched | ~464 |
| Total enriched (incl. pilot) | ~500 |

---

## 5. Retry Allowance Justification

| Scenario | Allowance | Rationale |
|---|---|---|
| Pilot (run_002) | 26/100 (26%) | Conservative — zero retries used |
| Stage 1 | 20/120 (17%) | Moderate — validation batch |
| Stage 2 | 83/920 (9%) | Lower — longer runs amortize transient errors |

The pilot demonstrated 0% retry rate on the 4G WAN network. The retry allowances
are conservative buffers, not expected consumption.

> [!NOTE]
> Unused retry budget from one stage does NOT carry to the next.
> Each stage has an independent budget enforced by `PHASE8D_APPROVED_MAX_REQUESTS`
> (which must be updated per stage).

---

## 6. Rate Limit Compliance

| Parameter | Value |
|---|---|
| TMDB API limit | 40 requests per 10 seconds (~4 RPS) |
| Configured limit | 4.0 RPS |
| Observed pilot max | 3.0 RPS |
| Safety margin | 25% below API limit |

---

## 7. Full-Catalog Estimate (for reference)

If a full-catalog enrichment were eventually authorized:

| Component | Count |
|---|---|
| Movies with TMDB ID | 9,734 |
| Base requests | 19,468 |
| Retry allowance (5%) | 973 |
| Total budget | ~20,441 |
| Duration at 4 RPS | ~85 minutes |
| Storage | ~48.5 MB |

> [!CAUTION]
> Full-catalog enrichment is NOT authorized and NOT requested. This estimate
> is for planning reference only.

---

## 8. Budget per Authorization

Each execution requires a separate authorization:

| Run | Budget | Movies | Output Dir |
|---|---|---|---|
| `phase8e_stage1_run_001` | 120 | 50 | `backend/reports/phase8e_stage1/` |
| `phase8e_stage2_run_001` | 920 | ~414 | `backend/reports/phase8e_stage2/` |

Code change required for each stage: update `PHASE8D_APPROVED_MAX_REQUESTS` to
match the authorized budget (120 or 920).
