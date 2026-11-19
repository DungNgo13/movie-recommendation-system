# Phase 8D.6 — Request Budget Plan

| Field | Value |
|---|---|
| **Run ID** | `phase8d_run_002` |
| **Phase** | 8D.6 — Budget Analysis |
| **Date** | 2026-11-19 |
| **Budget** | 74 HTTP attempts (hardcoded) |
| **Base requests** | 74 (37 movies × 2) |
| **Retry margin** | ⚠️ **ZERO** |

---

## Tóm tắt

Phân tích ngân sách yêu cầu HTTP cho run_002. Vấn đề quan trọng: 37 phim × 2 yêu
cầu = 74 yêu cầu cơ bản = chính xác giới hạn ngân sách 74. Điều này có nghĩa
là **không có dư địa cho bất kỳ lần thử lại nào**. Bất kỳ lỗi HTTP 429, 5xx,
timeout hoặc lỗi mạng nào sẽ khiến ít nhất một phim không được xử lý.

Chủ dự án cần quyết định: chấp nhận rủi ro hoặc ủy quyền ngân sách cao hơn.

---

## 1. Budget Allocation Breakdown

### Movie Categories

| Category | Count | Requests/Movie | Total Requests |
|---|---|---|---|
| Movies with TMDB ID | 37 | 2 | 74 |
| Movies without TMDB ID | 3 | 0 | 0 |
| **Total** | **40** | — | **74** |

### Per-Movie Request Detail

Each movie with a TMDB ID requires exactly **2 HTTP requests**:

| # | Endpoint | Purpose | Parameters |
|---|---|---|---|
| 1 | `GET /movie/{id}` | English details | `append_to_response=credits,keywords,alternative_titles,external_ids` |
| 2 | `GET /movie/{id}` | Vietnamese localization | `language=vi-VN` |

### Budget vs. Base Requests

```
Base requests:  74  ████████████████████████████████████████ (100%)
Budget cap:     74  ████████████████████████████████████████ (100%)
Retry margin:    0  (0%)
                    ↑ ZERO MARGIN
```

---

## 2. ⚠️ CRITICAL: Zero Retry Margin

> [!WARNING]
> **37 movies × 2 requests = 74 base requests = exactly the 74 budget cap.**
>
> There is **NO room for ANY retries**. The first retry attempt for any reason will
> cause at least one movie to receive `NOT_ATTEMPTED_BUDGET_EXHAUSTED` status.

### Retry triggers that consume budget:

| Trigger | HTTP Code | Budget Cost per Occurrence |
|---|---|---|
| Rate limiting | 429 | 1 attempt per retry |
| Server error | 5xx | 1 attempt per retry |
| Network timeout | — | 1 attempt per retry |
| Connection reset | — | 1 attempt per retry |
| TLS handshake failure | — | 1 attempt per retry |

### Impact example:

If movie #5's first EN request fails and is retried once:
- Budget consumed: 75 (74 base + 1 retry)
- Budget available: 74
- Result: Movie #37 (last movie) skipped → `NOT_ATTEMPTED_BUDGET_EXHAUSTED`

---

## 3. Circuit Breaker Impact Analysis

The `TMDBClient` circuit breaker trips after **5 consecutive transport failures**.

### Worst-case budget consumption on circuit breaker trip:

| Failure # | Movie | Request | Retries | Budget Used |
|---|---|---|---|---|
| 1 | Movie A | EN details | up to 3 | 4 |
| 2 | Movie A | VI local. | up to 3 | 4 |
| 3 | Movie B | EN details | up to 3 | 4 |
| 4 | Movie B | VI local. | up to 3 | 4 |
| 5 | Movie C | EN details | up to 3 | 4 |
| **Total** | | | | **up to 20** |

After circuit breaker trips with 20 budget consumed:
- Remaining budget: 74 − 20 = 54
- Maximum movies processable: 54 ÷ 2 = 27
- Movies skipped: 37 − 27 = **10 movies**

> [!NOTE]
> This worst-case assumes 3 retries per failure. The actual retry count depends on
> the configured retry policy (exponential backoff with max 3 retries per request).
> On the working 4G network, the circuit breaker should NOT trip, as Phase 8D.5
> demonstrated successful connectivity.

---

## 4. Budget Enforcement in Code

| Component | File | Line | Mechanism |
|---|---|---|---|
| Hard cap constant | `phase8d_live_pilot.py` | 81 | `PHASE8D_APPROVED_MAX_REQUESTS = 74` |
| Budget clamping | `phase8d_live_pilot.py` | 122 | `min(PHASE8D_APPROVED_MAX_REQUESTS, int(request_budget))` |
| CLI default | `cli.py` | 134 | `--phase8d-request-budget` default=74 |
| TMDBClient tracking | `tmdb_client.py` | — | `self.stats.requests_total` incremented per attempt |
| Budget check | `tmdb_client.py` | — | Raises `TMDBBudgetExhaustedError` when exceeded |

---

## 5. Rate Limiting

| Parameter | Value |
|---|---|
| Max RPS | 4.0 (TMDB API limit: 40 req / 10 sec) |
| Minimum duration at 4.0 RPS | 74 ÷ 4.0 = **18.5 seconds** |
| Expected duration with overhead | ~25–35 seconds |
| Run_001 max observed RPS | 3.0 |

---

## 6. Owner Decision Required

> [!IMPORTANT]
> The project owner must choose one of the following options before authorizing run_002.

### Option A: Accept 74 Budget (Zero Retry Margin)

| Aspect | Detail |
|---|---|
| Budget | 74 (unchanged) |
| Retry margin | 0 |
| Risk | Any retry → partial completion |
| Code changes | None |
| Best case | 37/37 movies enriched (all requests succeed first try) |
| Likely case | 35–37/37 (1–2 retries → 1–2 movies skipped) |
| Worst case | Partial or circuit breaker trip |

**Recommendation:** Acceptable if the 4G network is stable and TMDB API is responsive.
Phase 8D.5 showed 911.72ms latency with no errors — a good indicator.

### Option B: Authorize Budget of 100 (+35% Margin)

| Aspect | Detail |
|---|---|
| Budget | 100 |
| Retry margin | 26 retries available |
| Risk | Low — covers most transient failures |
| Code changes required | Modify `PHASE8D_APPROVED_MAX_REQUESTS` from 74 to 100 |
| CLI flag | `--phase8d-request-budget 100` |

### Option C: Authorize Budget of 120 (+62% Margin)

| Aspect | Detail |
|---|---|
| Budget | 120 |
| Retry margin | 46 retries available |
| Risk | Very low — robust against rate limiting and intermittent errors |
| Code changes required | Modify `PHASE8D_APPROVED_MAX_REQUESTS` from 74 to 120 |
| CLI flag | `--phase8d-request-budget 120` |

> [!NOTE]
> Options B and C require modifying the hardcoded constant
> `PHASE8D_APPROVED_MAX_REQUESTS` on line 81 of `phase8d_live_pilot.py`.
> The `from_args()` method clamps the budget to `min(PHASE8D_APPROVED_MAX_REQUESTS, request_budget)`,
> so both the constant AND the CLI argument must be updated.

---

## 7. Budget Comparison: run_001 vs. run_002

| Metric | run_001 | run_002 (projected) |
|---|---|---|
| Budget | 74 | 74 (or owner-approved higher) |
| Base requests | 74 | 74 |
| Actual requests | 74 | ≤74 |
| Successes | 0 | Expected ≥35 |
| Retries | 55 (all failures) | Expected 0–5 |
| Circuit breaker | Tripped (5 failures) | Expected: not tripped |
| Budget exhausted events | 1 | Expected: 0 |
| Network | Broadband (blocked) | 4G WAN (verified working) |
