# Phase 8D — Recovery Plan (Kế hoạch phục hồi)

**Date**: 2026-11-10  
**Phase**: Phase 8D — Controlled Live TMDB Pilot (40 movies)  
**Previous Run**: `phase8d_run_001` — FAILED (0/40, 74/74 budget exhausted)  
**Planned Run**: `phase8d_run_002` — Pending network issue resolution

---

## 1. Điều kiện tiên quyết / Prerequisites

Before executing `phase8d_run_002`, **all** of the following conditions must be met:

| # | Prerequisite | Verification Method |
|---|-------------|---------------------|
| 1 | **Network access to TMDB restored** | TLS handshake to `api.themoviedb.org:443` succeeds (see §4) |
| 2 | **Root cause identified and resolved** | FortiClient disabled/whitelisted, ISP bypass, or VPN configured (see `PHASE8D_TLS_ROOT_CAUSE_ANALYSIS.md`) |
| 3 | **New budget authorization obtained** | Independent authorization for `phase8d_run_002` (see §3) |
| 4 | **TMDB API token valid** | Token verified via successful test request |
| 5 | **Circuit breaker protection active** | `TMDBConfig.circuit_breaker_threshold=5` (default) |
| 6 | **Previous run data preserved** | `backend/reports/phase8d_pilot/` untouched (see §7) |

---

## 2. Mã thực thi mới / New Execution ID

| Parameter | Value |
|-----------|-------|
| **Execution ID** | `phase8d_run_002` |
| **Relationship** | Independent retry of `phase8d_run_001` |
| **Scope** | Same 40-movie manifest (seed=8042, SHA-256 `d23fc802...`) |
| **Movies to process** | All 40 (fresh start, not resuming from run_001 checkpoint) |

### 2.1 Why Fresh Start (Not Resume)

The run_001 checkpoint has `cumulative_requests: 74` (budget fully exhausted).
Resuming from this checkpoint would immediately trigger `BUDGET_EXHAUSTED` with
0 remaining attempts. A fresh start with a new budget authorization is required.

---

## 3. Thư mục báo cáo / Report Directory

| Item | Path |
|------|------|
| **New report directory** | `backend/reports/phase8d_pilot_run_002/` |
| **Checkpoint directory** | `backend/reports/phase8d_pilot_run_002/checkpoint/` |
| **Previous report directory** | `backend/reports/phase8d_pilot/` (preserved, read-only) |

### 3.1 Directory Structure

```
backend/reports/
├── phase8d_pilot/                          # run_001 (PRESERVED — DO NOT MODIFY)
│   ├── checkpoint/
│   │   ├── checkpoint.json                 # cumulative_requests: 74
│   │   └── checkpoint_failed_20261110T024550.json
│   ├── phase8d_preflight_report.json
│   ├── phase8d_request_statistics.json
│   ├── phase8d_execution_log.json
│   ├── phase8d_data_quality_report.json
│   └── ...
└── phase8d_pilot_run_002/                  # run_002 (NEW)
    ├── checkpoint/
    │   └── checkpoint.json
    ├── phase8d_preflight_report.json
    ├── phase8d_request_statistics.json
    ├── phase8d_execution_log.json
    ├── phase8d_data_quality_report.json
    └── ...
```

---

## 4. Hồ sơ ủy quyền / Authorization Record

### 4.1 Independence from run_001

The `phase8d_run_002` authorization is **completely independent** from
`phase8d_run_001`:

| Parameter | run_001 | run_002 |
|-----------|---------|---------|
| **Authorization** | Granted (executed) | **Requires new authorization** |
| **Budget** | 74 HTTP attempts (exhausted) | New budget (TBD, recommended: 74) |
| **Checkpoint** | `backend/reports/phase8d_pilot/checkpoint/` | `backend/reports/phase8d_pilot_run_002/checkpoint/` |
| **Execution scope** | 40 movies, seed=8042 | 40 movies, seed=8042 (same manifest) |
| **Rate limit** | 4.0 RPS | 4.0 RPS (same) |

### 4.2 Required Authorization Gates

Both gates must be satisfied for live execution:

1. **CLI flag**: `--phase8d-live` (or equivalent)
2. **Environment variable**: `PHASE8D_LIVE_AUTHORIZED=true`
3. **TMDB live requests**: `TMDB_ENABLE_LIVE_REQUESTS=true`
4. **API token**: `TMDB_API_READ_ACCESS_TOKEN` set and valid

---

## 5. Quy trình xác minh mạng / Network Verification Steps

Before requesting run_002 authorization, verify that the TLS issue is resolved:

### Step 1: Test DNS Resolution

```bash
# Verify TMDB domain resolves to CloudFront IPs
nslookup api.themoviedb.org
```

**Expected**: Resolves to CloudFront IPs (3.175.86.x or similar)  
**If fails**: DNS issue — check network connectivity first

### Step 2: Test TCP Connectivity

```bash
# Verify TCP connection to port 443
Test-NetConnection api.themoviedb.org -Port 443
```

**Expected**: `TcpTestSucceeded: True`  
**If fails**: Network/firewall blocking — check FortiClient, Windows Firewall

### Step 3: Test TLS Handshake

```python
# NOTE: This test requires network-test authorization
import ssl
import socket

hostname = "api.themoviedb.org"
ctx = ssl.create_default_context()
with socket.create_connection((hostname, 443), timeout=10) as sock:
    with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
        print(f"TLS version: {ssock.version()}")
        print(f"Cipher: {ssock.cipher()}")
        print("SUCCESS — TLS handshake works")
```

**Expected**: Prints TLS version (TLSv1.3) and cipher suite  
**If fails**: TLS still blocked — root cause not resolved

> [!IMPORTANT]
> Step 3 makes an outbound network connection. It requires **network-test
> authorization** before execution. Do not run this test without explicit
> approval.

### Step 4: Test HTTP GET with Small Request

```python
# NOTE: This test requires network-test authorization
import httpx

response = httpx.get(
    "https://api.themoviedb.org/3/configuration",
    headers={"Authorization": "Bearer <TOKEN>"},
    timeout=10.0,
)
print(f"Status: {response.status_code}")
print(f"Content-Type: {response.headers.get('content-type')}")
```

**Expected**: HTTP 200 with `application/json` content  
**If fails**: TMDB API issue (authentication, rate limiting, etc.)

---

## 6. Quy trình khôi phục / Recovery Procedure

### Step 1: Resolve Network Issue

Based on root cause analysis (`PHASE8D_TLS_ROOT_CAUSE_ANALYSIS.md`), take one of:

| Root Cause | Resolution |
|------------|------------|
| **FortiClient blocking** | Disable FortiClient temporarily, or request IT to whitelist `api.themoviedb.org` |
| **ISP blocking** | Use mobile hotspot (different ISP) or VPN |
| **CloudFront geo-block** | Use VPN to US/EU endpoint |

### Step 2: Verify TLS Handshake Works

Run the network verification steps (§5) and confirm:
- [ ] DNS resolves ✅
- [ ] TCP connects ✅
- [ ] TLS handshake succeeds ✅
- [ ] HTTP GET returns 200 ✅

### Step 3: Create New Run Directory

```bash
mkdir -p backend/reports/phase8d_pilot_run_002/checkpoint
```

### Step 4: Set New Budget Authorization

Configure the execution environment:

```bash
# Authorization gates
export PHASE8D_LIVE_AUTHORIZED=true
export TMDB_ENABLE_LIVE_REQUESTS=true
export TMDB_API_READ_ACCESS_TOKEN=<valid_token>

# Budget configuration
# PHASE8D_APPROVED_MAX_REQUESTS=74 (or as newly authorized)
```

### Step 5: Run Pilot with Circuit Breaker Protection

Execute the pilot with circuit breaker enabled (default):

```bash
python -m backend.app.services.run_live_pilot \
    --phase8d-live \
    --report-dir backend/reports/phase8d_pilot_run_002/ \
    --budget 74
```

**Circuit breaker behavior**: If TLS failures recur, the circuit breaker will
trigger after 5 consecutive transport failures, preserving the remaining budget
and producing a clear `TMDB_CIRCUIT_OPEN` error in logs.

### Step 6: Verify Results

After execution:
- [ ] Check `phase8d_request_statistics.json` for success count
- [ ] Check `phase8d_execution_log.json` for any errors
- [ ] Check `phase8d_data_quality_report.json` for quality metrics
- [ ] Verify checkpoint `cumulative_requests` matches expected usage

---

## 7. Quy trình hoàn tác / Rollback

If `phase8d_run_002` needs to be abandoned or rolled back:

### 7.1 Rollback Steps

1. **Stop execution** (if in progress): Ctrl+C or kill process
2. **Delete new run directory**:
   ```bash
   rm -rf backend/reports/phase8d_pilot_run_002/
   ```
3. **Unset authorization**:
   ```bash
   unset PHASE8D_LIVE_AUTHORIZED
   unset TMDB_ENABLE_LIVE_REQUESTS
   ```

### 7.2 What Is NOT Affected by Rollback

- `backend/reports/phase8d_pilot/` (run_001 data) — **untouched**
- Production database — **no writes** (Phase 8D is read-only)
- Source code — **no changes** needed
- Existing audit documents — **preserved**

---

## 8. Bảo toàn dữ liệu lịch sử / Historical Data Preservation

### 8.1 Immutable run_001 Data

The following files from `phase8d_run_001` are **preserved and must not be
modified**:

| File | Content | Status |
|------|---------|--------|
| `checkpoint/checkpoint.json` | `cumulative_requests: 74`, full record state | IMMUTABLE |
| `checkpoint/checkpoint_failed_20261110T024550.json` | Archived failed checkpoint | IMMUTABLE |
| `phase8d_preflight_report.json` | 8/8 preflight checks passed | IMMUTABLE |
| `phase8d_request_statistics.json` | 74 attempts, 0 successes, 55 retries | IMMUTABLE |
| `phase8d_execution_log.json` | Timestamped per-movie execution records | IMMUTABLE |
| `phase8d_data_quality_report.json` | Quality metrics (all N/A due to 0 successes) | IMMUTABLE |
| `phase8d_manifest.json` | 40-movie manifest (seed=8042) | IMMUTABLE |

### 8.2 Audit Trail

The run_002 recovery preserves the complete audit trail:
- run_001 failure data provides evidence of the TLS issue
- Network diagnostics document the root cause investigation
- Circuit breaker implementation documents the remediation
- run_002 results (when available) provide the retry outcome

This separation ensures that the thesis documents both the failure and the
recovery, demonstrating systematic engineering methodology.

---

## 9. References / Tài liệu tham chiếu

| Document | Path |
|----------|------|
| TLS root cause analysis | `docs/audit/PHASE8D_TLS_ROOT_CAUSE_ANALYSIS.md` |
| Network diagnostics | `docs/audit/PHASE8D_NETWORK_DIAGNOSTICS.md` |
| Retry hardening report | `docs/audit/PHASE8D_RETRY_HARDENING_REPORT.md` |
| TEC failure analysis | `docs/audit/PHASE8D_TEC_FAILURE_ANALYSIS.md` |
| Live pilot results (run_001) | `docs/audit/PHASE8D_LIVE_PILOT_RESULTS.md` |
| Checkpoint (run_001) | `backend/reports/phase8d_pilot/checkpoint/checkpoint.json` |
