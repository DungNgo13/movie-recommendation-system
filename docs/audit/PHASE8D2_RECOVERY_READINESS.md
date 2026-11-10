# Phase 8D.2 — Recovery Readiness Assessment (Đánh giá sẵn sàng phục hồi)

**Date**: 2026-11-10  
**Phase**: Phase 8D.2 — TLS Connectivity Diagnosis and Safe Pilot Recovery  
**Commits**: `6183fb5` (circuit breaker code), `419a261` (Phase 8D.1 docs)  
**Test Suite**: 44 TMDB client tests, 548 backend total, 51 TEC, 418 frontend — all passing

---

## 1. Tóm tắt đánh giá / Assessment Summary

| Area | Status | Detail |
|------|--------|--------|
| **Circuit breaker implementation** | ✅ READY | Threshold=5, 12 transport failure patterns, tested |
| **Transport failure classification** | ✅ READY | `TMDB_TLS_HANDSHAKE_FAILED` vs `TMDB_NETWORK_ERROR` |
| **Request budget enforcement** | ✅ READY | `max_total_requests` with pre-entry guard |
| **Checkpoint/resume** | ✅ READY | `initial_requests_total` carries forward budget usage |
| **Secret redaction** | ✅ READY | Logs, exceptions, repr() all redact tokens |
| **Rate limiting** | ✅ READY | 4.0 RPS enforced via client-side throttle |
| **Previous pilot evidence** | ✅ PRESERVED | run_001 checkpoint immutable at 74/74 |
| **TLS diagnostics** | ⏳ PROBES PREPARED | Schannel and OpenSSL probes ready, awaiting authorization |
| **Root cause identification** | ⚠️ IN PROGRESS | ISP DPI blocking is LIKELY; requires probe execution |
| **Network connectivity** | ❌ UNRESOLVED | TLS handshake to TMDB still blocked (not retested) |
| **Recovery pilot authorization** | ❌ NOT REQUESTED | Requires network resolution first |

---

## 2. Kiểm tra Circuit Breaker / Circuit Breaker Verification

### 2.1 Test Coverage

All circuit breaker behaviors are verified by automated tests:

| Test | File | Status |
|------|------|--------|
| TLS handshake reset triggers CB | `test_tls_handshake_reset_triggers_circuit_breaker` | ✅ PASS |
| CB rejects subsequent requests | `test_circuit_breaker_rejects_subsequent_requests` | ✅ PASS |
| CB reset after success | `test_circuit_breaker_reset_after_success` | ✅ PASS |
| Connection refused triggers CB | `test_connection_refused_triggers_circuit_breaker` | ✅ PASS |
| Proxy failure triggers CB | `test_proxy_connection_failure_triggers_circuit_breaker` | ✅ PASS |
| Timeout bounded by budget | `test_http_timeout_retry_bounded_by_budget` | ✅ PASS |
| 5xx bounded retries | `test_5xx_bounded_retries_preserve_budget` | ✅ PASS |
| Budget exhaustion stops immediately | `test_budget_exhaustion_stops_immediately` | ✅ PASS |
| Checkpoint resume preserves budget | `test_checkpoint_resume_preserves_budget` | ✅ PASS |
| No repeated processing after CB | `test_no_repeated_processing_after_circuit_breaker` | ✅ PASS |
| TLS error code correct | `test_tls_error_uses_correct_error_code` | ✅ PASS |
| Generic network error code correct | `test_generic_network_error_uses_network_error_code` | ✅ PASS |
| No credentials in errors | `test_no_credentials_in_error_messages` | ✅ PASS |
| CB stats serialization | `test_circuit_breaker_stats_in_to_dict` | ✅ PASS |
| 429 retry-after respected | `test_http_429_retry_after_header_respected` | ✅ PASS |
| Failed latency recorded | `test_failed_request_latency_recorded` | ✅ PASS |
| CB disabled with threshold=0 | `test_circuit_breaker_disabled_with_zero_threshold` | ✅ PASS |

### 2.2 Circuit Breaker Behavior Confirmation

For a future pilot with the same TLS failure pattern:

```
Attempt 1: WinError 10054 → consecutive_failures=1 → retry
Attempt 2: WinError 10054 → consecutive_failures=2 → retry
Attempt 3: WinError 10054 → consecutive_failures=3 → retry
Attempt 4: WinError 10054 → consecutive_failures=4 → retry
Attempt 5: WinError 10054 → consecutive_failures=5 → CIRCUIT BREAKER OPEN
→ All remaining movies marked NOT_ATTEMPTED_NETWORK_UNAVAILABLE
→ Checkpoint saved
→ Budget preserved: only 5 of N attempts consumed
```

**Confirmed**: The circuit breaker will protect the budget if TLS failures recur.

### 2.3 No Additional Tests Needed

The existing 44 TMDB client tests (28 of which were added in Phase 8D.1) fully
cover the circuit breaker, transport classification, budget enforcement,
checkpoint resume, and error code behaviors. No additional tests were required
for Phase 8D.2.

---

## 3. Bảo toàn bằng chứng / Evidence Preservation

### 3.1 Previous Pilot (run_001) — IMMUTABLE

| File | Content | Verified |
|------|---------|----------|
| `backend/reports/phase8d_pilot/checkpoint/checkpoint.json` | `cumulative_requests: 74`, 22 completed records | ✅ Untouched |
| `backend/reports/phase8d_pilot/checkpoint/checkpoint_failed_*.json` | Archived failed checkpoint | ✅ Untouched |
| `backend/reports/phase8d_pilot/` | All execution logs, manifests, reports | ✅ Untouched |

### 3.2 Run 001 Statistics (from checkpoint)

| Metric | Value |
|--------|-------|
| Movies in manifest | 40 |
| Movies with api_error | 19 (all `[WinError 10054]`) |
| Movies not_attempted_budget_exhausted | 18 |
| Movies not_attempted_missing_tmdb_id | 3 (movieIds: 791, 2851, 32600) |
| Total records in checkpoint | 22 (completed_ids) |
| Cumulative HTTP requests | 74 (EXHAUSTED) |
| Successful HTTP responses | 0 |
| HTTP 429 responses | 0 |
| HTTP 5xx responses | 0 |
| Retry attempts | 55 |

### 3.3 Verification

The run_001 budget counter was NOT reset. The checkpoint was NOT deleted.
All Phase 8D.1 audit documents are committed (hash `419a261`).
No pilot reports were overwritten or renamed.

---

## 4. Phát hiện mới Phase 8D.2 / Phase 8D.2 New Findings

### 4.1 FortiClient Assessment Update

| Phase 8D.1 Assessment | Phase 8D.2 Assessment | Change |
|------------------------|------------------------|--------|
| **LIKELY** (primary suspect) | **UNLIKELY** | Significantly weakened |

**Reason**: Phase 8D.2 inspection revealed:
- FortiClient VPN tunnel adapter is NOT active
- FortiClient WebFilter registry key does NOT exist
- No DPI/FA_Config registry found
- Traffic routes directly via Wi-Fi, not through Fortinet

### 4.2 ISP Hypothesis Update

| Phase 8D.1 Assessment | Phase 8D.2 Assessment | Change |
|------------------------|------------------------|--------|
| **POSSIBLE** | **LIKELY** (promoted to primary suspect) | Strengthened |

**Reason**: With FortiClient weakened and proxy eliminated, ISP-level
SNI-based DPI blocking is the most likely remaining explanation for the
TCP-OK-but-TLS-RST failure pattern.

### 4.3 httpx Configuration Finding

TMDBClient does not explicitly set `trust_env=False` or `verify` on
`httpx.Client()`. However, this has **no functional impact** in the current
environment because:
- All proxy environment variables are empty
- All certificate environment variables are empty
- `trust_env=True` only reads from environment variables, not WinHTTP/WinINET

**Recommendation**: Explicitly set `trust_env=False` in TMDBClient to prevent
unexpected proxy pickup in other environments, but this is a hardening
improvement, not a fix for the current TLS failure.

---

## 5. Thay đổi phần mềm cần thiết / Software Changes Assessment

### 5.1 Required for Recovery Pilot

| Change | Needed? | Reason |
|--------|---------|--------|
| Fix TLS handshake failure | ❌ No code fix | Issue is network-level, not code-level |
| Circuit breaker | ✅ Already implemented | Protects future pilots |
| Budget enforcement | ✅ Already implemented | `max_total_requests` guard |
| Checkpoint/resume | ✅ Already implemented | `initial_requests_total` support |
| New execution ID support | ⚠️ May need code | `phase8d_run_002` report directory |

### 5.2 Recommended Hardening (Not Blocking)

| Change | Priority | Reason |
|--------|----------|--------|
| Set `trust_env=False` in httpx.Client | Low | Prevent unexpected proxy in other environments |
| Add `trust_env` to TMDBConfig | Low | Make it configurable |
| Install `truststore` package | Optional | Would allow using Windows certificate store from Python |

### 5.3 Changes NOT Needed

- ❌ No OpenSSL version change needed (3.0.18 is current)
- ❌ No httpx version change needed (0.28.1 is current)
- ❌ No cipher suite changes needed (17 ciphers including all TLS 1.3)
- ❌ No certificate bundle changes needed (certifi 2026.06.17 is current)
- ❌ No h2 installation needed (HTTP/2 is unrelated to TLS RST)

---

## 6. Danh sách kiểm tra phục hồi / Recovery Checklist

### 6.1 Before Requesting New Pilot Authorization

- [ ] Execute TLS probe commands (Probes A and B from `PHASE8D2_SAFE_PROBE_COMMANDS.md`)
- [ ] At least one probe succeeds on current or alternative network
- [ ] Root cause identified (ISP, FortiClient, or transient)
- [ ] If ISP: document which network works and plan for pilot execution
- [ ] If transient: confirm stability with multiple successful probes

### 6.2 Before Starting Recovery Pilot

- [ ] TLS handshake confirmed working (Probe B succeeds)
- [ ] HTTP connectivity confirmed (unauthenticated GET returns 401)
- [ ] New execution ID: `phase8d_run_002`
- [ ] New report directory: `backend/reports/phase8d_pilot_run_002/`
- [ ] New budget authorization obtained (recommended: 120)
- [ ] Environment variables set:
  - [ ] `PHASE8D_LIVE_AUTHORIZED=true`
  - [ ] `TMDB_ENABLE_LIVE_REQUESTS=true`
  - [ ] `TMDB_API_READ_ACCESS_TOKEN` set and valid
- [ ] Circuit breaker enabled (default threshold=5)
- [ ] Previous run_001 data preserved (untouched)
- [ ] All tests passing (548 backend + 51 TEC + 418 frontend)

### 6.3 During Recovery Pilot

- [ ] Monitor circuit breaker status in first 30 seconds
- [ ] If circuit breaker triggers → stop, investigate, do not retry
- [ ] Verify request count stays within budget
- [ ] Check for successful HTTP 200 responses in first 2-3 movies
- [ ] Checkpoint saves correctly after each movie

### 6.4 After Recovery Pilot

- [ ] Verify per-movie status totals equal 40
- [ ] Generate TEC report with LIVE_VERIFIED results
- [ ] Compare with run_001 failure report
- [ ] Document network configuration that worked
- [ ] No production database writes

---

## 7. Tổng kết / Final Assessment

### System Readiness: ✅ SOFTWARE READY, ❌ NETWORK UNRESOLVED

The MovSug system is fully prepared for a recovery pilot at the software level:
- Circuit breaker will prevent budget waste if TLS failures recur
- Request budget enforcement is working
- Checkpoint/resume is working
- All 1,061 tests pass
- Evidence from run_001 is preserved

**Blocking issue**: TLS connectivity to `api.themoviedb.org` remains unresolved.
The prepared TLS probe commands must be executed (with authorization) to
diagnose whether the issue is ISP-specific, and the recovery pilot requires
a network where TLS handshake succeeds.

### Next Action Required

**Execute the TLS probe commands** from `PHASE8D2_SAFE_PROBE_COMMANDS.md` with
owner authorization. The probes make no authenticated requests and consume no
pilot budget. Their results will determine whether:
1. A code change is needed (Case A: Schannel works, OpenSSL doesn't)
2. A network change is needed (Case B: both fail)
3. The issue is resolved (Case C: both succeed)

---

## 8. Git History / Lịch sử Git

| Hash | Message | Phase |
|------|---------|-------|
| `419a261` | `docs(phase8d.1): add TLS root cause analysis, network diagnostics, retry hardening, recovery plan, and TEC failure analysis` | 8D.1 |
| `6183fb5` | `feat: add TLS circuit breaker, transport failure classification, and retry hardening` | 8D.1 |
| `ae681cb` | `docs(phase8d): record 74/74 live execution artifacts and TEC reports` | 8D |
| `f84b5ed` | `chore: add phase 8d pilot reports and execution checkpoints` | 8D |
| `eecc22f` | `docs: add Phase 8D controlled live TMDB pilot execution and evidence report` | 8D |
| `fb97ca5` | `fix(phase8d): enforce strict 74-attempt HTTP budget cap and record live execution evidence` | 8D |

---

## 9. References / Tài liệu tham chiếu

| Document | Path |
|----------|------|
| TLS connectivity diagnosis | `docs/audit/PHASE8D2_TLS_CONNECTIVITY_DIAGNOSIS.md` |
| Network comparison plan | `docs/audit/PHASE8D2_NETWORK_COMPARISON_PLAN.md` |
| Safe probe commands | `docs/audit/PHASE8D2_SAFE_PROBE_COMMANDS.md` |
| Phase 8D.1 root cause analysis | `docs/audit/PHASE8D_TLS_ROOT_CAUSE_ANALYSIS.md` |
| Phase 8D.1 network diagnostics | `docs/audit/PHASE8D_NETWORK_DIAGNOSTICS.md` |
| Phase 8D.1 retry hardening | `docs/audit/PHASE8D_RETRY_HARDENING_REPORT.md` |
| Phase 8D.1 recovery plan | `docs/audit/PHASE8D_RECOVERY_PLAN.md` |
| Phase 8D.1 TEC failure analysis | `docs/audit/PHASE8D_TEC_FAILURE_ANALYSIS.md` |
| Checkpoint (run_001) | `backend/reports/phase8d_pilot/checkpoint/checkpoint.json` |
