# Phase 8D.2 — TLS Connectivity Diagnosis (Chẩn đoán kết nối TLS)

**Date**: 2026-11-10  
**Phase**: Phase 8D.2 — TLS Connectivity Diagnosis and Safe Pilot Recovery  
**Previous Run**: `phase8d_run_001` — FAILED (0/40, 74/74 budget exhausted)  
**Objective**: Identify the cause of TLS handshake failures without making TMDB API requests

---

## 1. Tóm tắt / Executive Summary

This document records all offline diagnostic findings gathered to identify why
Python's HTTPS connections to `api.themoviedb.org` fail during TLS handshake
while TCP connections succeed. The diagnosis was performed without making any
TMDB API requests.

**Key finding**: The TMDBClient creates `httpx.Client()` without explicitly
setting `trust_env=False`. Since `httpx.Client` defaults to `trust_env=True`,
httpx may pick up proxy auto-configuration in some environments. However, in the
current environment, no proxy is configured at any level. The primary remaining
hypotheses are **ISP-level SNI-based DPI blocking** and **intermittent FortiClient
web-filter interference**, though the latter is significantly weakened by new
evidence.

---

## 2. Kết quả chẩn đoán / Diagnostic Results

### 2.1 Connection Stack Used During Failed Pilot

| Layer | Component | Version | Status |
|-------|-----------|---------|--------|
| HTTP Client | httpx | 0.28.1 | ✅ OK |
| HTTP Core | httpcore | 1.0.9 | ✅ OK |
| TLS Library | OpenSSL | 3.0.18 | ✅ OK (not Schannel) |
| Certificate Store | certifi | 2026.06.17 | ✅ OK |
| HTTP Protocol | HTTP/1.1 | (h2 not installed) | ✅ OK |
| Python | CPython | 3.14.3 (MSC v.1944 AMD64) | ✅ OK |

**Critical observation**: Windows `curl.exe` (v8.21.0) uses **Schannel** for TLS,
while Python/httpx uses **OpenSSL 3.0.18** via the `ssl` standard library. These
are two entirely different TLS implementations that handle certificate stores,
SNI negotiation, and potentially TLS inspection interception differently.

### 2.2 httpx.Client Configuration Analysis

The `TMDBClient.__init__()` creates `httpx.Client()` with these explicit parameters:

```python
self._client = httpx.Client(
    base_url=self._validated_base_url,
    timeout=timeout,
    limits=limits,
    transport=transport,
    follow_redirects=False,
)
```

**Parameters NOT explicitly set** (using httpx defaults):

| Parameter | Default | Implication |
|-----------|---------|-------------|
| `trust_env` | `True` | httpx reads `HTTP_PROXY`, `HTTPS_PROXY`, `SSL_CERT_FILE`, `SSL_CERT_DIR` from environment |
| `verify` | `True` | Uses certifi CA bundle, NOT Windows Schannel certificate store |
| `http2` | `False` | HTTP/1.1 only (h2 not installed anyway) |
| `proxy` | `None` | No explicit proxy |
| `cert` | `None` | No client certificate |

### 2.3 Python SSL Configuration

```
verify_mode:    ssl.CERT_REQUIRED (2)
check_hostname: True
protocol:       PROTOCOL_TLS (16)
min_version:    TLSv1.2 (771)
max_version:    Maximum available (-1, i.e., TLSv1.3)
HAS_SNI:        True
HAS_ECDH:       True
HAS_ALPN:       True
HAS_TLSv1_3:    True
```

**Default verify paths** (OpenSSL built-in):
- `cafile`: `None` (falls back to certifi when used via httpx)
- `openssl_cafile`: `C:\Program Files\Common Files\SSL/cert.pem`
- `certifi`: `D:\TLTN\...\backend\.venv\Lib\site-packages\certifi\cacert.pem`

### 2.4 TLS Backend Difference: Schannel vs OpenSSL

| Aspect | curl.exe (Schannel) | Python httpx (OpenSSL) |
|--------|---------------------|------------------------|
| TLS implementation | Windows native | OpenSSL 3.0.18 |
| Certificate store | Windows Certificate Store | certifi CA bundle |
| SNI behavior | Windows-native | Python ssl module |
| TLS inspection bypass | Can use host CA injected by DPI tools | Does NOT see Windows-injected CAs |
| Proxy awareness | WinHTTP, WinINET | Environment variables only |

**This difference is diagnostically significant**: If a DPI/TLS inspection tool
(FortiClient, ISP middlebox) intercepts the connection and presents its own
certificate, Schannel would accept it (if the DPI CA is in the Windows store)
while OpenSSL/certifi would **reject it** — but with a **certificate verification
error**, not a TCP RST.

However, the actual failure is a TCP RST during TLS ClientHello, **before** any
certificate exchange. This means the connection is being killed during the SNI
phase, not during certificate validation. The Schannel vs OpenSSL difference
is therefore **not the direct cause** of the TLS RST, but would matter if the
blocking mechanism were certificate-based interception.

---

## 3. Cấu hình proxy / Proxy Configuration (Comprehensive)

### 3.1 WinHTTP Proxy

```
Current WinHTTP proxy settings:
    Direct access (no proxy server).
```

**Status**: ✅ No system-level proxy

### 3.2 Internet Settings (WinINET) Proxy

```
ProxyEnable:    0  (disabled)
ProxyServer:    (not set)
ProxyOverride:  (not set)
AutoConfigURL:  (not set)
```

**Status**: ✅ No user-level proxy, no PAC file

### 3.3 Environment Variable Proxy

| Variable | Value |
|----------|-------|
| `HTTP_PROXY` | (empty) |
| `HTTPS_PROXY` | (empty) |
| `NO_PROXY` | (empty) |
| `http_proxy` | (empty) |
| `https_proxy` | (empty) |
| `no_proxy` | (empty) |
| `ALL_PROXY` | (empty) |
| `all_proxy` | (empty) |

**Status**: ✅ No proxy environment variables

### 3.4 Certificate Environment Variables

| Variable | Value |
|----------|-------|
| `SSL_CERT_FILE` | (empty) |
| `SSL_CERT_DIR` | (empty) |
| `REQUESTS_CA_BUNDLE` | (empty) |
| `CURL_CA_BUNDLE` | (empty) |
| `NODE_EXTRA_CA_CERTS` | (empty) |

**Status**: ✅ No certificate overrides — httpx uses default certifi bundle

### 3.5 httpx trust_env Behavior

With `trust_env=True` (the default that TMDBClient inherits), httpx:
1. Reads `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` from environment → **all empty**
2. Reads `SSL_CERT_FILE` / `SSL_CERT_DIR` from environment → **all empty**
3. Does NOT read WinHTTP or WinINET proxy settings
4. Does NOT read Windows Certificate Store

**Conclusion**: `trust_env=True` has no effect in the current environment because
all relevant environment variables are empty. This is NOT the cause of the
TLS failure.

---

## 4. FortiClient — Updated Assessment (Đánh giá cập nhật FortiClient)

### 4.1 FortiClient Process Status

| Process | PID | Status |
|---------|-----|--------|
| FortiTray | 10856 | Running (tray icon) |
| FortiVPN | 11036 | Running (VPN client) |
| FortiSSLVPNdaemon | 10128 | Running (SSL VPN service) |
| FortiSettings | 10356 | Running (settings UI) |

### 4.2 FortiClient VPN Tunnel Status

| Indicator | Finding | Assessment |
|-----------|---------|------------|
| FortiClient Virtual Ethernet Adapter | Present (Interface #13) | Installed but not listed in active adapters |
| Active network adapters | Wi-Fi, VirtualBox×2 | FortiClient adapter is **NOT active** |
| Default gateway | `172.35.53.1` via Wi-Fi only | No VPN tunnel routing |
| Route table | Single default route via Wi-Fi | No VPN split tunneling |

**Assessment**: The FortiClient VPN tunnel is **NOT active**. Traffic is routed
directly via Wi-Fi, not through a FortiClient VPN tunnel.

### 4.3 FortiClient Web Filter Status

| Indicator | Finding | Assessment |
|-----------|---------|------------|
| `HKLM:\SOFTWARE\Fortinet\FortiClient\WebFilter` | **NOT FOUND** | Web filter is NOT configured |
| `HKLM:\SOFTWARE\Fortinet\FortiClient\FA_Config` | **NOT FOUND** | Advanced config not present |
| FortiClient config files | Only `fdni.conf` (2 bytes) and `vsdb.json` (35KB) | Minimal virus signature database only |

**Assessment**: FortiClient appears to be installed for **VPN-only** purposes.
No web filtering, URL category blocking, or SSL deep packet inspection
configuration was found.

### 4.4 Revised FortiClient Hypothesis: WEAKENED → UNLIKELY

| Previous Assessment | New Assessment | Reason |
|---------------------|----------------|--------|
| **LIKELY** ⭐ (Primary suspect) | **UNLIKELY** ❌ | VPN not active, web filter not configured, no DPI registry keys |

The FortiClient hypothesis is significantly weakened because:
1. The VPN tunnel adapter is not active
2. No web filtering registry configuration exists
3. Traffic routes directly via Wi-Fi, not through a Fortinet tunnel
4. The configuration contains only a minimal virus signature database

FortiClient cannot be entirely ruled out (kernel-level network filter drivers
may persist even without active VPN), but it is no longer the primary suspect.

---

## 5. Revised Hypothesis Matrix (Ma trận giả thuyết cập nhật)

### Hypothesis 1: Vietnamese ISP SNI-Based DPI Blocking — **LIKELY** ⭐

| Attribute | Detail |
|-----------|--------|
| **Status** | **LIKELY — Promoted to primary suspect** |
| **Evidence FOR** | ISP is Vietnamese (42.116.x.x); the failure pattern (TCP OK, TLS RST on ClientHello) is the exact signature of SNI-based DPI blocking; TMDB is hosted on US-based CloudFront; Vietnamese ISPs have been documented performing SNI inspection; FortiClient (previous primary suspect) is significantly weakened |
| **Evidence AGAINST** | TMDB is not a politically sensitive service; no documented Vietnamese government directive to block TMDB specifically |
| **Verification** | Test from mobile hotspot (different ISP) or VPN bypassing ISP DPI |

### Hypothesis 2: FortiClient Kernel-Level Filter — **UNLIKELY**

| Attribute | Detail |
|-----------|--------|
| **Status** | **UNLIKELY — Significantly weakened** |
| **Evidence FOR** | FortiClient processes are running; FortiClient network filter drivers may persist at kernel level |
| **Evidence AGAINST** | VPN tunnel not active; no web filter configuration; traffic routes via Wi-Fi directly; no DPI registry keys |
| **Verification** | Uninstall FortiClient entirely → retest |

### Hypothesis 3: CloudFront Edge Configuration — **POSSIBLE**

| Attribute | Detail |
|-----------|--------|
| **Status** | **POSSIBLE — Cannot rule out** |
| **Evidence FOR** | CloudFront IPs rotated between sessions (3.175.86.x → 3.169.173.x); CloudFront edge may apply different behaviors per edge location; some edge configs may RST during TLS for blocked origins |
| **Evidence AGAINST** | CloudFront typically returns HTTP 403 after TLS, not RST during TLS; TCP connects normally |
| **Verification** | Test from a non-Vietnamese IP to determine if CloudFront behavior differs |

### Eliminated Hypotheses

| Hypothesis | Status | Reason |
|------------|--------|--------|
| Python/OpenSSL incompatibility | ❌ ELIMINATED | TLS to google.com works; all versions current |
| DNS/Routing issue | ❌ ELIMINATED | DNS resolves correctly; single default route via Wi-Fi |
| Certificate/CA issue | ❌ ELIMINATED | Failure is TCP RST before certificate exchange |
| Proxy misconfiguration | ❌ ELIMINATED | No proxy at any level (WinHTTP, WinINET, env vars) |
| FortiClient VPN tunnel routing | ❌ ELIMINATED | VPN tunnel adapter is not active |

---

## 6. Schannel vs OpenSSL Differential (So sánh Schannel và OpenSSL)

This is a key diagnostic axis that has NOT been tested yet.

### 6.1 Why This Matters

The SNI (Server Name Indication) field in the TLS ClientHello is what DPI
systems inspect to identify the target domain. Both Schannel and OpenSSL send
SNI, but they may construct the ClientHello differently:

- **Different cipher suite ordering**
- **Different TLS extension ordering**
- **Different supported version lists**
- **Different ALPN values** (h2 negotiation)

If the DPI system is using a fingerprint to identify and block specific TLS
clients (e.g., JA3 fingerprint), the Schannel ClientHello might pass while
the OpenSSL ClientHello is blocked. This is a known technique used by some
DPI systems to differentiate browsers from scripting tools.

### 6.2 What the Probe Commands Will Test

- **Probe A** (curl.exe/Schannel): Tests Windows-native TLS to TMDB
- **Probe B** (Python/OpenSSL): Tests the exact TLS stack used by httpx

If Probe A succeeds and Probe B fails, the issue is likely:
1. TLS client fingerprint-based blocking (JA3)
2. Different SNI encoding between Schannel and OpenSSL
3. ALPN negotiation difference

If both fail, the issue is network-path-based (ISP or intermediate) blocking
regardless of TLS implementation.

### 6.3 Unverified — Requires Authorized Probes

> [!IMPORTANT]
> The Schannel vs OpenSSL differential has NOT been tested. The probe commands
> in `PHASE8D2_SAFE_PROBE_COMMANDS.md` are prepared but require explicit
> authorization before execution.

---

## 7. Phân biệt bằng chứng và giả thuyết / Evidence vs Hypotheses

### Established Facts (Bằng chứng xác thực — Phase 8D.2)

1. **WinHTTP proxy**: Direct access (no proxy server)
2. **WinINET proxy**: Disabled (`ProxyEnable=0`), no PAC URL
3. **Environment proxy**: All 8 proxy variables empty
4. **Certificate overrides**: All 5 certificate environment variables empty
5. **FortiClient VPN tunnel**: NOT active — adapter present but not routing
6. **FortiClient web filter**: NOT configured — registry key does not exist
7. **FortiClient DPI config**: NOT found — no FA_Config registry key
8. **Traffic routing**: Single default route via Wi-Fi (172.35.53.1)
9. **httpx trust_env**: Defaults to `True` in TMDBClient (has no effect with empty env vars)
10. **httpx verify**: Defaults to `True` — uses certifi bundle, NOT Windows store
11. **Windows curl**: Uses Schannel (v8.21.0), different TLS implementation from Python
12. **DNS resolves**: CloudFront IPs rotated (3.175.86.x → 3.169.173.x) between sessions
13. **TCP connectivity**: Still succeeds (TcpTestSucceeded: True) to current IPs
14. **Python SSL**: TLSv1.2 minimum, TLSv1.3 capable, SNI enabled, ALPN enabled

### Unverified Hypotheses (Giả thuyết chưa xác minh)

1. **ISP SNI-based DPI blocking** — LIKELY but requires mobile hotspot test
2. **TLS client fingerprint blocking (JA3)** — POSSIBLE if curl succeeds but Python fails
3. **CloudFront edge behavior** — POSSIBLE but atypical
4. **FortiClient kernel-level filter** — UNLIKELY given no web filter config

### What Would Confirm Each Hypothesis

| Hypothesis | Confirmation Test | Network Traffic? |
|------------|-------------------|-----------------|
| ISP DPI | Mobile hotspot → Python TLS succeeds | Yes (authorized probe) |
| JA3 fingerprint | curl succeeds, Python fails on same network | Yes (authorized probes) |
| CloudFront edge | VPN to US/EU → Python TLS succeeds | Yes (authorized probe) |
| FortiClient kernel | Uninstall FortiClient → retest | Yes (authorized probe) |

---

## 8. References / Tài liệu tham chiếu

| Document | Path |
|----------|------|
| Safe probe commands | `docs/audit/PHASE8D2_SAFE_PROBE_COMMANDS.md` |
| Network comparison plan | `docs/audit/PHASE8D2_NETWORK_COMPARISON_PLAN.md` |
| Recovery readiness | `docs/audit/PHASE8D2_RECOVERY_READINESS.md` |
| Phase 8D.1 TLS root cause | `docs/audit/PHASE8D_TLS_ROOT_CAUSE_ANALYSIS.md` |
| Phase 8D.1 network diagnostics | `docs/audit/PHASE8D_NETWORK_DIAGNOSTICS.md` |
| Phase 8D.1 recovery plan | `docs/audit/PHASE8D_RECOVERY_PLAN.md` |
| Previous checkpoint (run_001) | `backend/reports/phase8d_pilot/checkpoint/checkpoint.json` |

