# Phase 8D — TLS Connection Failure Root Cause Analysis (Phân tích nguyên nhân gốc lỗi kết nối TLS)

**Date**: 2026-11-10  
**Phase**: Phase 8D — Controlled Live TMDB Pilot (40 movies)  
**Execution ID**: `phase8d_run_001`  
**Outcome**: FAILED — 0/40 movies retrieved, 74/74 HTTP budget exhausted  
**Error Signature**: `[WinError 10054] An existing connection was forcibly closed by the remote host`

---

## 1. Tóm tắt vấn đề / Problem Summary

Phase 8D live pilot execution attempted to retrieve TMDB metadata for 40 movies
via `GET /movie/{tmdb_id}` over HTTPS. All 74 approved HTTP attempts failed at
the TLS handshake layer with `[WinError 10054]`, a Windows-specific TCP RST
(connection reset) error. No HTTP response was ever received from
`api.themoviedb.org`. The pilot consumed its entire request budget with zero
successful retrievals.

**Key paradox**: TCP connections to `api.themoviedb.org:443` succeed (277ms
round-trip), but TLS negotiation on that established connection is immediately
reset. TLS to other hosts (e.g., `google.com:443`) works normally with TLSv1.3.

---

## 2. Hiện tượng quan sát / Observed Symptoms

| # | Observation | Detail |
|---|-------------|--------|
| 1 | **TCP connectivity works** | TCP SYN/ACK to `api.themoviedb.org:443` completes in ~277ms |
| 2 | **TLS handshake fails** | Immediately after TCP connect, TLS ClientHello is sent but connection receives TCP RST |
| 3 | **Error is consistent** | All 74 attempts over ~86 seconds produced identical `[WinError 10054]` |
| 4 | **No HTTP status received** | 0 HTTP responses (no 200, 429, 5xx, etc.) — failure occurs below HTTP layer |
| 5 | **Other TLS targets work** | `google.com:443` TLS handshake succeeds with TLSv1.3 |
| 6 | **Retries do not recover** | Exponential backoff retries (1s, 2s, 4s) produce the same reset |
| 7 | **Per-attempt latency ~233–440ms** | Time-to-failure matches TCP RTT + TLS packet round-trip, consistent with reset during handshake |
| 8 | **Per-movie processing latency ~4500–5000ms** | Inflated by exponential backoff waits across 4 attempts (1+3 retries) |

---

## 3. Phân tích nguyên nhân gốc / Root Cause Analysis

### 3.1 Failure Layer Identification

```
Application Layer (HTTP)     : ── Not reached ──
Transport Layer (TLS)        : ❌ FAILURE — TCP RST during TLS handshake
Transport Layer (TCP)        : ✅ OK — 3-way handshake completes
Network Layer (IP/Routing)   : ✅ OK — normal route via Vietnamese ISP
DNS Resolution               : ✅ OK — resolves to CloudFront IPs
```

The failure is precisely isolated to the **TLS handshake phase**: after a
successful TCP connection is established, the TLS ClientHello is sent but the
remote side (or an intermediary) sends a TCP RST, causing `[WinError 10054]`.

### 3.2 Failure Scope

- **Affected**: `api.themoviedb.org` (`3.175.86.x` CloudFront)
- **Unaffected**: `google.com:443` (TLSv1.3), general internet browsing, DNS, TCP

This domain-specific TLS blocking pattern is consistent with a **middlebox
(firewall, VPN, or ISP deep packet inspection)** intercepting the TLS
ClientHello, inspecting the Server Name Indication (SNI) field for
`api.themoviedb.org`, and issuing a TCP RST to block the connection.

---

## 4. Ma trận kiểm thử kết nối / Connection Test Matrix

| Test | Target | Result | Detail |
|------|--------|--------|--------|
| **DNS Resolution** | `api.themoviedb.org` | ✅ OK | A: `3.175.86.103`, `3.175.86.37`, `3.175.86.50`, `3.175.86.67`; AAAA: 8 IPv6 records (`2600:9000:21b3:...`) |
| **TCP to :443** | `api.themoviedb.org` | ✅ OK | Connected in 277ms |
| **TLS Handshake** | `api.themoviedb.org` | 🔴 FAILED | `ConnectionResetError [WinError 10054]` during TLS negotiation |
| **TLS Handshake** | `google.com` | ✅ OK | TLSv1.3, successful handshake |
| **Python/OpenSSL** | Local | ✅ OK | Python 3.14.3, OpenSSL 3.0.18 |
| **httpx/httpcore** | Local | ✅ OK | httpx 0.28.1, httpcore 1.0.9 |
| **certifi** | Local | ✅ OK | certifi 2026.06.17 (current) |
| **HTTP/2** | Local | ⚠️ N/A | h2 not installed (HTTP/1.1 only) |
| **Proxy** | Local | ✅ None | No proxy configured |
| **Network** | Local | ✅ OK | Wi-Fi connected at 172.35.53.78 |
| **VPN/Enterprise** | Local | ⚠️ Running | FortiClient VPN Service Scheduler detected |
| **Firewall** | Local | ✅ Normal | Windows Firewall — all profiles enabled |
| **Hosts File** | Local | ✅ Clean | No TMDB override entries |
| **Traceroute** | `api.themoviedb.org` | ✅ Normal | 5 hops, Vietnamese ISP (42.116.x.x) |

---

## 5. Các giả thuyết được đánh giá / Hypotheses Evaluated

### Hypothesis 1: FortiClient TLS Inspection — **LIKELY** ⭐

| Attribute | Detail |
|-----------|--------|
| **Status** | **LIKELY — Primary suspect** |
| **Evidence FOR** | FortiClient VPN Service Scheduler is running; FortiClient is an enterprise security product that performs TLS/SSL deep packet inspection; it can selectively block or reset TLS connections to specific domains based on SNI inspection; the failure pattern (TCP OK, TLS RST) is the exact signature of SNI-based TLS interception/blocking |
| **Evidence AGAINST** | No direct proof that FortiClient is configured to block `api.themoviedb.org`; would need to disable FortiClient and retest to confirm |
| **Mechanism** | FortiClient intercepts the TLS ClientHello, reads the SNI field (`api.themoviedb.org`), determines the domain is in a blocked category (e.g., "Entertainment/Media API"), and sends TCP RST to both client and server |
| **Verification** | Temporarily disable FortiClient → retest TLS handshake → if handshake succeeds, FortiClient is confirmed as the blocking agent |

### Hypothesis 2: Vietnamese ISP Blocking — **POSSIBLE**

| Attribute | Detail |
|-----------|--------|
| **Status** | **POSSIBLE — Cannot rule out** |
| **Evidence FOR** | ISP is in Vietnamese IP range (42.116.x.x); Vietnamese ISPs have been observed performing SNI-based domain blocking; the TMDB API resolves to CloudFront (US-based CDN) which may be subject to regional filtering |
| **Evidence AGAINST** | TMDB is not a politically sensitive service; entertainment metadata APIs are not typically blocked by ISPs; TLS to `google.com` works (though Google may be treated differently) |
| **Mechanism** | ISP deep packet inspection (DPI) equipment reads SNI from TLS ClientHello and sends TCP RST for blocked domains |
| **Verification** | Test from a different ISP (mobile hotspot) or VPN to bypass ISP-level filtering |

### Hypothesis 3: CloudFront Geo-Blocking — **POSSIBLE**

| Attribute | Detail |
|-----------|--------|
| **Status** | **POSSIBLE — Less likely given TCP success** |
| **Evidence FOR** | TMDB uses CloudFront CDN; CloudFront supports geo-restriction; Vietnam connections may be blocked at CloudFront edge |
| **Evidence AGAINST** | CloudFront geo-blocking typically returns HTTP 403 (after TLS handshake), not a TCP RST during handshake; TCP connections succeed, meaning CloudFront edge servers accept TCP connections from this IP |
| **Mechanism** | CloudFront edge sends RST during TLS handshake based on source IP geolocation |
| **Verification** | Test from a non-Vietnamese IP (VPN to US/EU) to determine if TMDB responds normally |

### Hypothesis 4: Python/OpenSSL Incompatibility — **ELIMINATED** ❌

| Attribute | Detail |
|-----------|--------|
| **Status** | **ELIMINATED** |
| **Evidence** | TLS to `google.com:443` succeeds with TLSv1.3 using the same Python 3.14.3 / OpenSSL 3.0.18 stack; 17 cipher suites available including all standard TLS 1.3 and TLS 1.2 ciphers; if there were a client-side TLS issue, it would affect all targets |

### Hypothesis 5: DNS/Routing Issue — **ELIMINATED** ❌

| Attribute | Detail |
|-----------|--------|
| **Status** | **ELIMINATED** |
| **Evidence** | DNS resolves correctly to CloudFront IPs (3.175.86.x); traceroute shows normal 5-hop route; TCP connects in 277ms; no hosts file override |

### Hypothesis 6: Certificate/CA Issue — **ELIMINATED** ❌

| Attribute | Detail |
|-----------|--------|
| **Status** | **ELIMINATED** |
| **Evidence** | certifi 2026.06.17 is current; certificate validation failures produce different errors (SSLCertVerificationError), not TCP RST; the failure occurs before any certificate exchange (during ClientHello) |

### Hypothesis 7: Proxy Misconfiguration — **ELIMINATED** ❌

| Attribute | Detail |
|-----------|--------|
| **Status** | **ELIMINATED** |
| **Evidence** | No proxy configured in environment; no HTTP_PROXY, HTTPS_PROXY, or NO_PROXY variables set; httpx is not configured to use a proxy |

---

## 6. Phân biệt bằng chứng và giả thuyết / Evidence vs Hypotheses

> [!IMPORTANT]
> The following is a clear delineation of **established facts** (verified by
> diagnostic tests) versus **unverified hypotheses** (reasonable inferences that
> require further testing to confirm).

### Established Facts (Bằng chứng xác thực)

1. TCP connects to `api.themoviedb.org:443` in ~277ms — the server is reachable
2. TLS handshake to `api.themoviedb.org` fails with TCP RST every time
3. TLS handshake to `google.com:443` succeeds with TLSv1.3
4. The failure is domain-specific, not a general network or TLS issue
5. FortiClient VPN Service Scheduler is running on the machine
6. The machine's ISP is Vietnamese (42.116.x.x range)
7. TMDB resolves to CloudFront CDN IPs (3.175.86.x)
8. Python/OpenSSL/httpx/certifi versions are current and functional
9. No proxy or hosts file interference

### Unverified Hypotheses (Giả thuyết chưa xác minh)

1. **FortiClient is the blocking agent** — running ≠ blocking; need disable test
2. **ISP is performing SNI-based filtering** — possible but not proven
3. **CloudFront is geo-rejecting** — atypical for TLS-level rejection

### What Would Confirm Each Hypothesis

| Hypothesis | Confirmation Test |
|------------|-------------------|
| FortiClient | Disable FortiClient → TLS succeeds → confirmed |
| ISP blocking | Mobile hotspot (different ISP) → TLS succeeds → confirmed |
| CloudFront geo-block | VPN to US/EU → TLS succeeds → possible (but doesn't distinguish from ISP) |

---

## 7. Recommended Next Steps / Các bước tiếp theo khuyến nghị

### Immediate Actions (no network authorization required)

1. **Disable FortiClient temporarily** — Pause or disable FortiClient VPN
   Service → retest TLS handshake to `api.themoviedb.org:443`. This is the
   highest-priority test because FortiClient is the most likely blocking agent.

2. **Try mobile hotspot** — Connect to a cellular hotspot (different ISP) →
   retest TLS handshake. This simultaneously tests ISP blocking and network path
   differences.

3. **Try different network** — Test from a network without FortiClient (e.g.,
   home Wi-Fi, café). If TLS succeeds, confirms the issue is
   environment-specific.

### If FortiClient Is Confirmed

- Request IT/admin to whitelist `api.themoviedb.org` in FortiClient web
  filtering policy
- Document the FortiClient configuration for the thesis as an environmental
  constraint

### If ISP Is Confirmed

- Use a VPN or different ISP for TMDB API access
- Document as an ISP-level constraint in the thesis

### Recovery Execution

Once TLS handshake is verified working:
- Follow `PHASE8D_RECOVERY_PLAN.md` for `phase8d_run_002`
- Circuit breaker (threshold=5) will protect against regression
- New budget authorization required (independent from run_001)

---

## 8. References / Tài liệu tham chiếu

| Document | Path |
|----------|------|
| Network Diagnostics | `docs/audit/PHASE8D_NETWORK_DIAGNOSTICS.md` |
| Retry Hardening Report | `docs/audit/PHASE8D_RETRY_HARDENING_REPORT.md` |
| Recovery Plan | `docs/audit/PHASE8D_RECOVERY_PLAN.md` |
| TEC Failure Analysis | `docs/audit/PHASE8D_TEC_FAILURE_ANALYSIS.md` |
| Live Pilot Results | `docs/audit/PHASE8D_LIVE_PILOT_RESULTS.md` |
| Checkpoint (Failed) | `backend/reports/phase8d_pilot/checkpoint/checkpoint_failed_20261110T024550.json` |
| Checkpoint (Current) | `backend/reports/phase8d_pilot/checkpoint/checkpoint.json` |
